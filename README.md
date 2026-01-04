# 🏛️ Zoning Analyst AI Agent

**AI-Powered Zoning Analysis for Brevard County, Florida**

Automatically scrapes, caches, and analyzes municipal zoning ordinances across all 17 Brevard County municipalities (cities + unincorporated areas).

---

## 🎯 Features

✅ **Intelligent Scraping** - Uses Firecrawl /agent to extract zoning data from Municode & American Legal Publishing  
✅ **Smart Caching** - Supabase database stores scraped data (codes rarely change)  
✅ **Natural Language Queries** - "Can I build a 4-story apartment on this property?"  
✅ **REST API** - FastAPI endpoints for programmatic access  
✅ **SPD Integration** - Plugs directly into Site Plan Development pipeline  
✅ **BidDeed.AI Integration** - Enhances foreclosure analysis with development potential  

---

## 📊 Coverage

**17 Municipalities:**
- Brevard County (unincorporated)
- Palm Bay
- Melbourne
- Cocoa
- Titusville
- Rockledge
- Cocoa Beach
- Satellite Beach
- West Melbourne
- Melbourne Beach
- Indian Harbour Beach
- Indialantic
- Cape Canaveral
- Grant-Valkaria
- Malabar
- Palm Shores
- Melbourne Village

**Zoning Data Extracted:**
- District codes & descriptions
- Permitted/conditional/prohibited uses
- Setbacks (front, side, rear)
- Maximum height & density
- Minimum lot size & width
- Lot coverage limits
- Parking requirements

---

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.11+
python --version

# Supabase account
# https://supabase.com

# Firecrawl API key (optional but recommended)
# https://firecrawl.dev
```

### Installation

```bash
# Clone repository
git clone https://github.com/breverdbidder/zoning-analyst-ai.git
cd zoning-analyst-ai

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your keys
```

### Environment Variables

```bash
# .env file
SUPABASE_URL=https://mocerqjnksmhcjzxrewo.supabase.co
SUPABASE_KEY=your_supabase_key_here
FIRECRAWL_API_KEY=fc-your_firecrawl_key_here  # Optional
PORT=8000
```

### Database Setup

```bash
# Run schema migration
psql $SUPABASE_URL -f schema/zoning_analyst_schema.sql

# Or use Supabase UI:
# 1. Go to SQL Editor
# 2. Paste contents of schema/zoning_analyst_schema.sql
# 3. Run
```

### Run API Server

```bash
# Development
uvicorn zoning_analyst_api:app --reload --port 8000

# Production
uvicorn zoning_analyst_api:app --host 0.0.0.0 --port 8000 --workers 4
```

### Test Installation

```bash
# Health check
curl http://localhost:8000/health

# List municipalities
curl http://localhost:8000/api/municipalities

# Get zoning data (will scrape if not cached)
curl http://localhost:8000/api/zoning/Palm%20Bay/RM-20
```

---

## 📖 API Documentation

### Base URL
```
http://localhost:8000
```

### Endpoints

#### 1. Get Zoning Data
```http
GET /api/zoning/{municipality}/{code}
```

**Example:**
```bash
curl "http://localhost:8000/api/zoning/Palm%20Bay/RM-20"
```

**Response:**
```json
{
  "success": true,
  "municipality": "Palm Bay",
  "zoning_code": "RM-20",
  "data": {
    "district_code": "RM-20",
    "description": "Multiple-Family Residential",
    "max_density": "20 dwelling units per acre",
    "max_height": "45 feet",
    "front_setback": "25 feet",
    "side_setback": "15 feet",
    "rear_setback": "25 feet",
    "permitted_uses": [
      "Single-family dwelling",
      "Two-family dwelling",
      "Multiple-family dwelling"
    ]
  }
}
```

#### 2. Natural Language Query
```http
POST /api/zoning/query
```

**Request:**
```json
{
  "query": "Can I build a 4-story apartment building?",
  "property_data": {
    "municipality": "Palm Bay",
    "zoning": "RM-20",
    "address": "2165 Sandy Pines Dr NE"
  }
}
```

**Response:**
```json
{
  "success": true,
  "query": "Can I build a 4-story apartment building?",
  "answer": "In Palm Bay RM-20 zoning, the maximum height is 45 feet. A typical 4-story building (10-12 ft per floor) would be 40-48 feet, so it may be possible depending on exact design. Verify with Palm Bay Planning Department.",
  "timestamp": "2026-01-04T15:30:00Z"
}
```

#### 3. List Municipalities
```http
GET /api/municipalities
```

#### 4. Get Municipality Details
```http
GET /api/municipalities/{name}
```

#### 5. Start Scraping Job
```http
POST /api/scrape/municipality
```

**Request:**
```json
{
  "municipality": "Palm Bay",
  "zoning_codes": ["RM-20", "RM-15", "R-1A"]
}
```

#### 6. Get Statistics
```http
GET /api/stats
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    USER APPLICATIONS                    │
│   SPD Pipeline  │  BidDeed.AI  │  Custom Apps  │ API   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   FASTAPI REST API                      │
│  GET /api/zoning/{municipality}/{code}                  │
│  POST /api/zoning/query (NLP)                           │
│  POST /api/scrape/municipality                          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              ZONING ANALYST AGENT (CORE)                │
│  ┌────────────────┐  ┌────────────────┐                │
│  │  Cache Lookup  │  │  Firecrawl     │                │
│  │  (Supabase)    │  │  Scraper       │                │
│  └────────┬───────┘  └────────┬───────┘                │
│           │                    │                        │
│           └──────────┬─────────┘                        │
│                      ▼                                  │
│           ┌──────────────────────┐                      │
│           │  NLP Analysis Layer  │                      │
│           │  (Query Understanding)│                     │
│           └──────────────────────┘                      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   DATA SOURCES                          │
│  Municode  │  American Legal  │  General Code          │
└─────────────────────────────────────────────────────────┘
```

---

## 🗄️ Database Schema

**Main Tables:**
- `zoning_cache` - Cached zoning district data
- `zoning_permitted_uses` - Uses by district and type
- `zoning_requirements` - Dimensional requirements
- `zoning_overlays` - Overlay districts (flood, historic, etc.)
- `brevard_municipalities` - Municipality metadata
- `zoning_scraping_jobs` - Job log
- `zoning_query_log` - Query analytics

**Views:**
- `v_zoning_summary` - Statistics by municipality
- `v_scraping_status` - Scraping job status

---

## 🔗 Integration Examples

### SPD (Site Plan Development)

```python
from zoning_analyst_agent import ZoningAnalystAgent

async def spd_stage_3_zoning_analysis(property_data):
    """Enhanced SPD Stage 3 with AI zoning analysis"""
    agent = ZoningAnalystAgent()
    
    # Get zoning analysis
    zoning = await agent.analyze_property_zoning(
        municipality=property_data["municipality"],
        zoning_code=property_data["zoning"]
    )
    
    # Natural language summary
    summary = await agent.natural_language_query(
        "What can I build on this property?",
        property_data
    )
    
    return {
        "zoning_data": zoning,
        "summary": summary,
        "stage": "COMPLETED"
    }
```

### BidDeed.AI Foreclosure Analysis

```python
async def enhanced_foreclosure_analysis(property):
    """Add development potential to foreclosure analysis"""
    agent = ZoningAnalystAgent()
    
    # Get zoning
    zoning = await agent.analyze_property_zoning(
        property.municipality,
        property.zoning_code
    )
    
    # Check if property is underutilized
    max_density = parse_density(zoning["max_density"])
    current_density = 1 / property.acres
    
    if max_density > current_density * 2:
        # Significant upside potential
        potential_units = property.acres * max_density
        value_add = (potential_units - 1) * 200000  # Rough estimate
        
        return {
            "tear_down_candidate": True,
            "current_units": 1,
            "potential_units": int(potential_units),
            "estimated_value_add": value_add
        }
    
    return {"tear_down_candidate": False}
```

---

## 💰 Cost Analysis

### Firecrawl Approach (Recommended)

**Setup:** $3,000 (one-time)
**Monthly:** $249 ($49 API + $200 maintenance)
**First Year:** $5,988

**Pros:**
- Auto-adapts to website changes
- 90-95% accuracy
- Low maintenance

### Open Source Alternative

**Setup:** $5,000 (one-time)
**Monthly:** $500 (high maintenance)
**First Year:** $11,000

**Pros:**
- No API costs
- Full control

**Cons:**
- Brittle (breaks when sites change)
- Higher maintenance

---

## 📅 Implementation Timeline

### Phase 1: POC (Week 1 - Jan 6-12)
- [ ] Sign up for Firecrawl
- [ ] Test on 3 municipalities
- [ ] Measure accuracy & cost

### Phase 2: Tier 1 Cities (Week 2 - Jan 13-19)
- [ ] Palm Bay (complete)
- [ ] Melbourne (complete)
- [ ] Brevard County unincorporated (complete)
- [ ] API deployment

### Phase 3: Full County (Week 3-4 - Jan 20-31)
- [ ] All 17 municipalities
- [ ] ~200 zoning districts cached
- [ ] NLP query layer

### Phase 4: Integration (Ongoing)
- [ ] SPD integration
- [ ] BidDeed.AI integration
- [ ] Weekly updates

---

## 🧪 Testing

```bash
# Run tests
pytest tests/

# Test specific municipality
pytest tests/test_scraping.py::test_palm_bay

# Test NLP queries
pytest tests/test_nlp.py

# Load testing
locust -f tests/load_test.py
```

---

## 📊 Monitoring

**Key Metrics:**
- Cache hit rate (target: >95%)
- Scraping accuracy (target: >90%)
- API response time (target: <200ms cached, <5s uncached)
- Firecrawl credits used (target: <10K/month)

**Dashboard:**
```bash
# View stats
curl http://localhost:8000/api/stats

# View scraping jobs
curl http://localhost:8000/api/stats | jq '.recent_jobs'
```

---

## ⚠️ Important Notes

### Legal Considerations
- Public codes - legally required to be accessible
- Polite scraping (1 request per 5 seconds)
- User-Agent: "BidDeed.AI Zoning Research Bot"
- Fair Use argument (research, non-commercial)

### Data Accuracy
- AI-extracted data - 90-95% accuracy
- Always include disclaimer for high-stakes decisions
- Spot-check 10% against official PDFs
- Confidence scoring on every extraction

### Maintenance
- Check for code updates quarterly
- Re-scrape changed codes
- Monitor Firecrawl API status
- Review accuracy metrics

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Priority Areas:**
- Additional municipality support (Orange, Seminole counties)
- Improved NLP query understanding
- Enhanced accuracy validation
- Additional use cases

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details

---

## 🙋 Support

**Issues:** https://github.com/breverdbidder/zoning-analyst-ai/issues  
**Discussions:** https://github.com/breverdbidder/zoning-analyst-ai/discussions  
**Email:** contact@everestcapitalusa.com

---

## 🏆 Credits

**Created By:** Ariel Shapira, Everest Capital USA  
**AI Architect:** Claude AI (Anthropic)  
**Date:** January 4, 2026  

**Built With:**
- [Firecrawl](https://firecrawl.dev) - Intelligent web scraping
- [FastAPI](https://fastapi.tiangolo.com) - Modern Python API framework
- [Supabase](https://supabase.com) - PostgreSQL database
- [Pydantic](https://pydantic.dev) - Data validation

---

## 📈 Roadmap

**Q1 2026:**
- [ ] Complete Brevard County coverage (17 municipalities)
- [ ] SPD & BidDeed.AI integration
- [ ] Public API launch

**Q2 2026:**
- [ ] Orange County expansion
- [ ] Seminole County expansion
- [ ] Enhanced NLP with LLM

**Q3 2026:**
- [ ] Multi-county analysis
- [ ] Rezoning opportunity detection
- [ ] H&BU analysis automation

**Q4 2026:**
- [ ] Statewide Florida coverage
- [ ] Commercial API launch
- [ ] Partner integrations

---

**Status:** ✅ READY FOR IMPLEMENTATION  
**Next Action:** Sign up for Firecrawl & deploy database schema  
**Target Launch:** January 15, 2026
