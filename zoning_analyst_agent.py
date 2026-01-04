"""
Zoning Analyst AI Agent
Brevard County, FL - All Cities + Unincorporated

Automatically scrapes, caches, and analyzes zoning ordinances using:
- Firecrawl /agent for intelligent scraping
- Supabase for caching
- Pydantic for structured data
- NLP for query understanding

Author: Ariel Shapira, Everest Capital USA
Date: January 4, 2026
"""

import os
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from supabase import create_client, Client
import httpx


# ==============================================
# PYDANTIC SCHEMAS
# ==============================================

class ZoningDistrict(BaseModel):
    """Structured zoning district data"""
    district_code: str = Field(..., description="Zoning district code (e.g., RM-20, R-1A)")
    description: str = Field(..., description="Description of the zoning district")
    future_land_use: Optional[str] = Field(None, description="Future Land Use category")
    
    # Dimensional requirements
    min_lot_size: Optional[str] = Field(None, description="Minimum lot size")
    min_lot_width: Optional[str] = Field(None, description="Minimum lot width")
    front_setback: Optional[str] = Field(None, description="Front setback requirement")
    side_setback: Optional[str] = Field(None, description="Side setback requirement")
    rear_setback: Optional[str] = Field(None, description="Rear setback requirement")
    max_height: Optional[str] = Field(None, description="Maximum building height")
    max_coverage: Optional[str] = Field(None, description="Maximum lot coverage")
    max_density: Optional[str] = Field(None, description="Maximum density (units/acre or FAR)")
    min_floor_area: Optional[str] = Field(None, description="Minimum floor area")
    
    # Uses
    permitted_uses: List[str] = Field(default_factory=list, description="Permitted uses")
    conditional_uses: List[str] = Field(default_factory=list, description="Conditional uses")
    prohibited_uses: List[str] = Field(default_factory=list, description="Prohibited uses")
    
    # Metadata
    source_section: Optional[str] = Field(None, description="Code section reference")
    notes: Optional[str] = Field(None, description="Additional notes")


class Municipality(BaseModel):
    """Brevard County municipality"""
    name: str
    code_platform: str  # 'municode', 'american_legal', 'general_code'
    code_url: Optional[str]
    scraping_priority: int


# ==============================================
# ZONING ANALYST AGENT
# ==============================================

class ZoningAnalystAgent:
    """
    AI-powered zoning analyst for Brevard County, FL
    
    Capabilities:
    - Scrape zoning codes from Municode/American Legal
    - Cache results in Supabase
    - Answer natural language queries
    - Integrate with SPD and BidDeed.AI
    """
    
    def __init__(self):
        # Supabase connection
        self.supabase: Client = create_client(
            os.getenv("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co"),
            os.getenv("SUPABASE_KEY")
        )
        
        # Firecrawl API (if available)
        self.firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")
        self.firecrawl_enabled = bool(self.firecrawl_api_key)
        
        # HTTP client
        self.http_client = httpx.AsyncClient(timeout=60.0)
    
    async def get_municipality_info(self, municipality_name: str) -> Optional[Dict[str, Any]]:
        """Get municipality metadata from database"""
        result = self.supabase.table("brevard_municipalities").select("*").eq(
            "name", municipality_name
        ).execute()
        
        if result.data:
            return result.data[0]
        return None
    
    async def get_zoning_from_cache(
        self, 
        municipality: str, 
        zoning_code: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if zoning data exists in cache
        
        Returns:
            Cached zoning data or None if not found
        """
        result = self.supabase.table("zoning_cache").select("*").eq(
            "municipality", municipality
        ).eq("code", zoning_code).execute()
        
        if result.data:
            # Log cache hit
            self.supabase.table("zoning_query_log").insert({
                "query_type": "lookup",
                "municipality": municipality,
                "zoning_code": zoning_code,
                "cache_hit": True,
                "response_time_ms": 0
            }).execute()
            
            return result.data[0]
        
        return None
    
    async def scrape_with_firecrawl(
        self,
        municipality: str,
        zoning_code: str,
        municipality_url: str
    ) -> Optional[ZoningDistrict]:
        """
        Scrape zoning data using Firecrawl /agent endpoint
        
        Args:
            municipality: City name
            zoning_code: Zoning district code (e.g., "RM-20")
            municipality_url: Base URL for the municipality's code
        
        Returns:
            Structured ZoningDistrict or None if failed
        """
        if not self.firecrawl_enabled:
            print("⚠️ Firecrawl not configured - set FIRECRAWL_API_KEY")
            return None
        
        # Construct prompt
        prompt = f"""
        Navigate to {municipality_url} and find the complete zoning requirements for district {zoning_code} in {municipality}, Florida.
        
        Extract ALL of the following information:
        1. District description and purpose
        2. Future Land Use category (if mentioned)
        3. Permitted uses (by-right uses)
        4. Conditional uses (special exception/CUP required)
        5. Prohibited uses
        6. Minimum lot size (in square feet or acres)
        7. Minimum lot width (in feet)
        8. Front setback (in feet)
        9. Side setback (in feet or as formula)
        10. Rear setback (in feet or as formula)
        11. Maximum building height (in feet and/or stories)
        12. Maximum lot coverage (in percentage)
        13. Maximum density (units per acre for residential, or FAR for commercial)
        14. Minimum floor area (if specified)
        15. Code section reference
        
        If a requirement is not found, leave it empty. Be thorough and accurate.
        """
        
        try:
            # Call Firecrawl agent
            response = await self.http_client.post(
                "https://api.firecrawl.dev/v0/agent",
                headers={
                    "Authorization": f"Bearer {self.firecrawl_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "prompt": prompt,
                    "schema": ZoningDistrict.schema()
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse response into ZoningDistrict
                if "data" in data:
                    zoning_data = ZoningDistrict(**data["data"])
                    return zoning_data
            
            print(f"❌ Firecrawl error: {response.status_code}")
            return None
            
        except Exception as e:
            print(f"❌ Scraping error: {e}")
            return None
    
    async def cache_zoning_data(
        self,
        municipality: str,
        zoning_data: ZoningDistrict,
        source_url: str,
        confidence_score: float = 0.85
    ) -> bool:
        """
        Store zoning data in Supabase cache
        
        Args:
            municipality: City name
            zoning_data: Structured zoning district data
            source_url: URL where data was scraped from
            confidence_score: AI confidence (0.0 to 1.0)
        
        Returns:
            True if successful
        """
        try:
            # Upsert main zoning record
            zoning_record = {
                "municipality": municipality,
                "code": zoning_data.district_code,
                "description": zoning_data.description,
                "future_land_use": zoning_data.future_land_use,
                "min_lot_size": zoning_data.min_lot_size,
                "min_lot_width": zoning_data.min_lot_width,
                "front_setback": zoning_data.front_setback,
                "side_setback": zoning_data.side_setback,
                "rear_setback": zoning_data.rear_setback,
                "max_height": zoning_data.max_height,
                "max_coverage": zoning_data.max_coverage,
                "max_density": zoning_data.max_density,
                "min_floor_area": zoning_data.min_floor_area,
                "source_url": source_url,
                "confidence_score": confidence_score,
                "data": zoning_data.dict(),
                "updated_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table("zoning_cache").upsert(
                zoning_record,
                on_conflict="municipality,code"
            ).execute()
            
            if result.data:
                zoning_id = result.data[0]["id"]
                
                # Insert permitted uses
                for use in zoning_data.permitted_uses:
                    self.supabase.table("zoning_permitted_uses").insert({
                        "zoning_id": zoning_id,
                        "use_name": use,
                        "use_type": "permitted"
                    }).execute()
                
                # Insert conditional uses
                for use in zoning_data.conditional_uses:
                    self.supabase.table("zoning_permitted_uses").insert({
                        "zoning_id": zoning_id,
                        "use_name": use,
                        "use_type": "conditional"
                    }).execute()
                
                # Insert prohibited uses
                for use in zoning_data.prohibited_uses:
                    self.supabase.table("zoning_permitted_uses").insert({
                        "zoning_id": zoning_id,
                        "use_name": use,
                        "use_type": "prohibited"
                    }).execute()
                
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Cache error: {e}")
            return False
    
    async def analyze_property_zoning(
        self,
        municipality: str,
        zoning_code: str
    ) -> Optional[Dict[str, Any]]:
        """
        Main method: Get zoning analysis for a property
        
        Workflow:
        1. Check cache first
        2. If not cached, scrape with Firecrawl
        3. Store in cache
        4. Return structured data
        
        Args:
            municipality: City name (e.g., "Palm Bay")
            zoning_code: Zoning district (e.g., "RM-20")
        
        Returns:
            Complete zoning analysis
        """
        start_time = datetime.now()
        
        # Step 1: Check cache
        cached = await self.get_zoning_from_cache(municipality, zoning_code)
        if cached:
            print(f"✅ Cache hit: {municipality} {zoning_code}")
            return cached
        
        print(f"🔍 Cache miss: {municipality} {zoning_code} - scraping...")
        
        # Step 2: Get municipality info
        muni_info = await self.get_municipality_info(municipality)
        if not muni_info or not muni_info.get("code_url"):
            print(f"❌ No code URL for {municipality}")
            return None
        
        # Step 3: Scrape with Firecrawl
        zoning_data = await self.scrape_with_firecrawl(
            municipality=municipality,
            zoning_code=zoning_code,
            municipality_url=muni_info["code_url"]
        )
        
        if not zoning_data:
            print(f"❌ Scraping failed for {municipality} {zoning_code}")
            return None
        
        # Step 4: Cache the result
        success = await self.cache_zoning_data(
            municipality=municipality,
            zoning_data=zoning_data,
            source_url=muni_info["code_url"]
        )
        
        if success:
            print(f"✅ Cached: {municipality} {zoning_code}")
            
            # Log query
            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self.supabase.table("zoning_query_log").insert({
                "query_type": "scrape",
                "municipality": municipality,
                "zoning_code": zoning_code,
                "cache_hit": False,
                "response_time_ms": elapsed_ms
            }).execute()
            
            return zoning_data.dict()
        
        return None
    
    async def natural_language_query(self, query: str, property_data: Dict[str, Any]) -> str:
        """
        Answer natural language questions about zoning
        
        Examples:
        - "Can I build a 4-story apartment building?"
        - "What are the setback requirements?"
        - "Is a home office permitted?"
        
        Args:
            query: User's question
            property_data: Property context (municipality, zoning_code, etc.)
        
        Returns:
            Natural language answer
        """
        municipality = property_data.get("municipality")
        zoning_code = property_data.get("zoning")
        
        if not municipality or not zoning_code:
            return "❌ Missing municipality or zoning code in property data"
        
        # Get zoning analysis
        zoning = await self.analyze_property_zoning(municipality, zoning_code)
        if not zoning:
            return f"❌ Could not find zoning data for {municipality} {zoning_code}"
        
        # Simple NLP response (can be enhanced with LLM later)
        query_lower = query.lower()
        
        # Height questions
        if "story" in query_lower or "stories" in query_lower or "height" in query_lower:
            max_height = zoning.get("max_height", "Not specified")
            return f"In {municipality} {zoning_code} zoning, the maximum height is {max_height}."
        
        # Setback questions
        if "setback" in query_lower:
            front = zoning.get("front_setback", "Not specified")
            side = zoning.get("side_setback", "Not specified")
            rear = zoning.get("rear_setback", "Not specified")
            return f"""Setback requirements for {municipality} {zoning_code}:
- Front: {front}
- Side: {side}
- Rear: {rear}"""
        
        # Use questions
        if "permit" in query_lower or "allow" in query_lower or "use" in query_lower:
            data = zoning.get("data", {})
            permitted = data.get("permitted_uses", [])
            conditional = data.get("conditional_uses", [])
            
            permitted_text = "\n- ".join(permitted) if permitted else "None listed"
            conditional_text = "\n- ".join(conditional) if conditional else "None listed"
            
            return f"""Uses in {municipality} {zoning_code}:

**Permitted (by-right):**
- {permitted_text}

**Conditional (special approval required):**
- {conditional_text}"""
        
        # Default: return summary
        return f"""Zoning summary for {municipality} {zoning_code}:

{zoning.get('description', 'No description available')}

**Key requirements:**
- Max height: {zoning.get('max_height', 'Not specified')}
- Max density: {zoning.get('max_density', 'Not specified')}
- Min lot size: {zoning.get('min_lot_size', 'Not specified')}
- Setbacks: Front {zoning.get('front_setback', '?')} | Side {zoning.get('side_setback', '?')} | Rear {zoning.get('rear_setback', '?')}

For detailed information, visit: {zoning.get('source_url', 'N/A')}"""
    
    async def close(self):
        """Cleanup"""
        await self.http_client.aclose()


# ==============================================
# CLI INTERFACE (for testing)
# ==============================================

async def main():
    """Test the zoning analyst agent"""
    agent = ZoningAnalystAgent()
    
    print("\n🏛️ ZONING ANALYST AI AGENT - POC TEST")
    print("=" * 50)
    
    # Test 1: Palm Bay RM-20
    print("\n📍 TEST 1: Palm Bay, RM-20")
    result = await agent.analyze_property_zoning("Palm Bay", "RM-20")
    if result:
        print(f"✅ Success! Found {len(result.get('data', {}).get('permitted_uses', []))} permitted uses")
    else:
        print("⚠️ Not found - would need Firecrawl API key to scrape")
    
    # Test 2: Natural language query
    print("\n💬 TEST 2: Natural language query")
    property_data = {
        "municipality": "Palm Bay",
        "zoning": "RM-20",
        "address": "2165 Sandy Pines Dr NE"
    }
    answer = await agent.natural_language_query(
        "Can I build a 4-story apartment building?",
        property_data
    )
    print(answer)
    
    await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
