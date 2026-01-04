"""
Zoning Analyst API
REST API for accessing Brevard County zoning data

Endpoints:
- GET /api/zoning/{municipality}/{code}
- POST /api/zoning/query (natural language)
- GET /api/municipalities
- POST /api/scrape/municipality/{name}

Author: Ariel Shapira, Everest Capital USA
Date: January 4, 2026
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import os

# Import our zoning agent
from zoning_analyst_agent import ZoningAnalystAgent


# ==============================================
# FASTAPI APP
# ==============================================

app = FastAPI(
    title="Zoning Analyst API",
    description="AI-powered zoning analysis for Brevard County, FL",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance
agent = ZoningAnalystAgent()


# ==============================================
# REQUEST/RESPONSE MODELS
# ==============================================

class ZoningRequest(BaseModel):
    municipality: str
    zoning_code: str


class NaturalLanguageQuery(BaseModel):
    query: str
    property_data: Dict[str, Any]


class ScrapingJobRequest(BaseModel):
    municipality: str
    zoning_codes: Optional[List[str]] = None  # If None, scrape all


# ==============================================
# ENDPOINTS
# ==============================================

@app.get("/")
async def root():
    """API root"""
    return {
        "name": "Zoning Analyst API",
        "version": "1.0.0",
        "status": "operational",
        "firecrawl_enabled": agent.firecrawl_enabled,
        "endpoints": [
            "GET /api/zoning/{municipality}/{code}",
            "POST /api/zoning/query",
            "GET /api/municipalities",
            "GET /api/municipalities/{name}",
            "POST /api/scrape/municipality",
            "GET /api/stats"
        ]
    }


@app.get("/api/zoning/{municipality}/{code}")
async def get_zoning(municipality: str, code: str):
    """
    Get zoning data for a specific district
    
    Example: GET /api/zoning/Palm%20Bay/RM-20
    """
    try:
        result = await agent.analyze_property_zoning(municipality, code)
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Zoning data not found for {municipality} {code}"
            )
        
        return {
            "success": True,
            "municipality": municipality,
            "zoning_code": code,
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/zoning/query")
async def natural_language_query(request: NaturalLanguageQuery):
    """
    Answer natural language questions about zoning
    
    Example:
    {
        "query": "Can I build a 4-story building?",
        "property_data": {
            "municipality": "Palm Bay",
            "zoning": "RM-20",
            "address": "2165 Sandy Pines Dr NE"
        }
    }
    """
    try:
        answer = await agent.natural_language_query(
            request.query,
            request.property_data
        )
        
        return {
            "success": True,
            "query": request.query,
            "answer": answer,
            "property": request.property_data,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/municipalities")
async def list_municipalities():
    """
    Get list of all Brevard County municipalities
    """
    try:
        result = agent.supabase.table("brevard_municipalities").select(
            "name, code_platform, scraping_priority, total_zoning_districts, last_scraped"
        ).order("scraping_priority").execute()
        
        return {
            "success": True,
            "total": len(result.data),
            "municipalities": result.data,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/municipalities/{name}")
async def get_municipality(name: str):
    """
    Get details for a specific municipality
    """
    try:
        info = await agent.get_municipality_info(name)
        
        if not info:
            raise HTTPException(
                status_code=404,
                detail=f"Municipality '{name}' not found"
            )
        
        # Get zoning districts for this municipality
        zones = agent.supabase.table("zoning_cache").select(
            "code, description, confidence_score, updated_at"
        ).eq("municipality", name).execute()
        
        return {
            "success": True,
            "municipality": info,
            "zoning_districts": zones.data,
            "total_districts": len(zones.data),
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def run_scraping_job(municipality: str, zoning_codes: Optional[List[str]]):
    """
    Background task: Scrape zoning data for a municipality
    """
    job_id = None
    
    try:
        # Create job record
        job = agent.supabase.table("zoning_scraping_jobs").insert({
            "municipality": municipality,
            "job_type": "full" if not zoning_codes else "incremental",
            "status": "running"
        }).execute()
        
        job_id = job.data[0]["id"]
        
        # Get municipality info
        muni_info = await agent.get_municipality_info(municipality)
        if not muni_info:
            raise Exception(f"Municipality {municipality} not found")
        
        # If no codes specified, scrape common ones
        if not zoning_codes:
            # Default codes to scrape (residential focus)
            zoning_codes = [
                "R-1", "R-1A", "R-1AA", "R-2", "R-3",
                "RM-10", "RM-15", "RM-20",
                "BU-1", "BU-2", "GC"
            ]
        
        # Scrape each code
        districts_scraped = 0
        for code in zoning_codes:
            result = await agent.analyze_property_zoning(municipality, code)
            if result:
                districts_scraped += 1
        
        # Update job status
        agent.supabase.table("zoning_scraping_jobs").update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "districts_scraped": districts_scraped
        }).eq("id", job_id).execute()
        
    except Exception as e:
        # Update job with error
        if job_id:
            agent.supabase.table("zoning_scraping_jobs").update({
                "status": "failed",
                "completed_at": datetime.now().isoformat(),
                "error_message": str(e)
            }).eq("id", job_id).execute()


@app.post("/api/scrape/municipality")
async def scrape_municipality(
    request: ScrapingJobRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a scraping job for a municipality
    
    Example:
    {
        "municipality": "Palm Bay",
        "zoning_codes": ["RM-20", "RM-15"]  # Optional
    }
    """
    try:
        # Verify municipality exists
        info = await agent.get_municipality_info(request.municipality)
        if not info:
            raise HTTPException(
                status_code=404,
                detail=f"Municipality '{request.municipality}' not found"
            )
        
        if not info.get("code_url"):
            raise HTTPException(
                status_code=400,
                detail=f"No code URL configured for {request.municipality}"
            )
        
        # Start background scraping job
        background_tasks.add_task(
            run_scraping_job,
            request.municipality,
            request.zoning_codes
        )
        
        return {
            "success": True,
            "message": f"Scraping job started for {request.municipality}",
            "municipality": request.municipality,
            "codes_to_scrape": request.zoning_codes or "all common codes",
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """
    Get overall statistics
    """
    try:
        # Total districts cached
        total_result = agent.supabase.table("zoning_cache").select(
            "id", count="exact"
        ).execute()
        
        # By municipality
        muni_stats = agent.supabase.table("v_zoning_summary").select("*").execute()
        
        # Recent scraping jobs
        jobs = agent.supabase.table("zoning_scraping_jobs").select(
            "*"
        ).order("started_at", desc=True).limit(10).execute()
        
        # Query stats
        query_result = agent.supabase.table("zoning_query_log").select(
            "id", count="exact"
        ).execute()
        
        return {
            "success": True,
            "total_districts_cached": total_result.count,
            "municipalities_with_data": len(muni_stats.data),
            "total_queries": query_result.count,
            "municipality_breakdown": muni_stats.data,
            "recent_jobs": jobs.data,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await agent.close()


# ==============================================
# HEALTH CHECK
# ==============================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test Supabase connection
        result = agent.supabase.table("brevard_municipalities").select(
            "name", count="exact"
        ).limit(1).execute()
        
        return {
            "status": "healthy",
            "database": "connected",
            "firecrawl": "enabled" if agent.firecrawl_enabled else "disabled",
            "municipalities_available": result.count,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "zoning_analyst_api:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )
