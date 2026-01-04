-- ==============================================
-- ZONING ANALYST AI AGENT - DATABASE SCHEMA
-- Brevard County, FL - All Cities + Unincorporated
-- ==============================================

-- Main zoning cache table
CREATE TABLE IF NOT EXISTS zoning_cache (
  id SERIAL PRIMARY KEY,
  municipality TEXT NOT NULL,
  code TEXT NOT NULL,
  description TEXT,
  future_land_use TEXT,
  
  -- Dimensional requirements
  min_lot_size TEXT,
  min_lot_width TEXT,
  front_setback TEXT,
  side_setback TEXT,
  rear_setback TEXT,
  max_height TEXT,
  max_coverage TEXT,
  max_density TEXT,
  min_floor_area TEXT,
  
  -- Metadata
  source_url TEXT,
  scraped_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  confidence_score DECIMAL(3,2),  -- 0.00 to 1.00
  
  -- Full data JSON
  data JSONB NOT NULL,
  
  UNIQUE(municipality, code)
);

CREATE INDEX idx_zoning_municipality ON zoning_cache(municipality);
CREATE INDEX idx_zoning_code ON zoning_cache(code);
CREATE INDEX idx_zoning_updated ON zoning_cache(updated_at DESC);

-- Permitted uses
CREATE TABLE IF NOT EXISTS zoning_permitted_uses (
  id SERIAL PRIMARY KEY,
  zoning_id INTEGER REFERENCES zoning_cache(id) ON DELETE CASCADE,
  use_name TEXT NOT NULL,
  use_type TEXT CHECK (use_type IN ('permitted', 'conditional', 'prohibited')),
  use_category TEXT,  -- residential, commercial, industrial, institutional
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_uses_zoning_id ON zoning_permitted_uses(zoning_id);
CREATE INDEX idx_uses_type ON zoning_permitted_uses(use_type);
CREATE INDEX idx_uses_category ON zoning_permitted_uses(use_category);

-- Specific requirements
CREATE TABLE IF NOT EXISTS zoning_requirements (
  id SERIAL PRIMARY KEY,
  zoning_id INTEGER REFERENCES zoning_cache(id) ON DELETE CASCADE,
  requirement_type TEXT NOT NULL,  -- 'setback', 'height', 'density', 'lot_size', 'parking', 'landscaping'
  requirement_name TEXT,
  requirement_value TEXT,
  unit TEXT,  -- 'feet', 'acres', 'units/acre', '%'
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_requirements_zoning_id ON zoning_requirements(zoning_id);
CREATE INDEX idx_requirements_type ON zoning_requirements(requirement_type);

-- Overlay districts
CREATE TABLE IF NOT EXISTS zoning_overlays (
  id SERIAL PRIMARY KEY,
  municipality TEXT NOT NULL,
  overlay_name TEXT NOT NULL,
  overlay_code TEXT,
  description TEXT,
  additional_requirements JSONB,
  source_url TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(municipality, overlay_code)
);

CREATE INDEX idx_overlays_municipality ON zoning_overlays(municipality);

-- Brevard County municipalities
CREATE TABLE IF NOT EXISTS brevard_municipalities (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  code_platform TEXT,  -- 'municode', 'american_legal', 'general_code'
  code_url TEXT,
  population INTEGER,
  area_sq_miles DECIMAL(10,2),
  incorporated BOOLEAN DEFAULT TRUE,
  scraping_priority INTEGER,  -- 1 = highest
  last_scraped TIMESTAMP,
  total_zoning_districts INTEGER DEFAULT 0,
  notes TEXT
);

-- Insert Brevard municipalities
INSERT INTO brevard_municipalities (name, code_platform, code_url, scraping_priority) VALUES
('Brevard County', 'municode', 'https://library.municode.com/fl/brevard_county/codes/code_of_ordinances', 1),
('Palm Bay', 'american_legal', 'https://codelibrary.amlegal.com/codes/palmbay/latest/palmbay_fl/0-0-0-1', 1),
('Melbourne', 'american_legal', 'https://library.amlegal.com/nxt/gateway.dll/Florida/melbourne/cityofmelbournefloridacodeofordinances', 1),
('Cocoa', 'american_legal', 'https://library.amlegal.com/nxt/gateway.dll/Florida/cocoa/cityofcocoafloridacodeofordinances', 2),
('Titusville', 'american_legal', 'https://library.amlegal.com/nxt/gateway.dll/Florida/titusville/cityoftitusvillefloridacodeofordinances', 2),
('Rockledge', 'american_legal', 'https://library.amlegal.com/nxt/gateway.dll/Florida/rockledge/cityofrockledgefloridacodeofordinances', 2),
('Cocoa Beach', 'municode', 'https://library.municode.com/fl/cocoa_beach/codes/code_of_ordinances', 2),
('Satellite Beach', 'american_legal', 'https://library.amlegal.com/nxt/gateway.dll/Florida/satellitebeach/cityofsatellitebeachfloridacodeofordinanc', 2),
('West Melbourne', 'unknown', NULL, 3),
('Melbourne Beach', 'unknown', NULL, 3),
('Indian Harbour Beach', 'unknown', NULL, 3),
('Indialantic', 'unknown', NULL, 3),
('Cape Canaveral', 'unknown', NULL, 3),
('Grant-Valkaria', 'unknown', NULL, 3),
('Malabar', 'unknown', NULL, 3),
('Palm Shores', 'unknown', NULL, 3),
('Melbourne Village', 'unknown', NULL, 3)
ON CONFLICT (name) DO NOTHING;

-- Scraping job log
CREATE TABLE IF NOT EXISTS zoning_scraping_jobs (
  id SERIAL PRIMARY KEY,
  municipality TEXT NOT NULL,
  job_type TEXT,  -- 'full', 'incremental', 'verification'
  status TEXT CHECK (status IN ('pending', 'running', 'completed', 'failed')),
  started_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP,
  districts_scraped INTEGER DEFAULT 0,
  credits_used INTEGER DEFAULT 0,
  error_message TEXT,
  metadata JSONB
);

CREATE INDEX idx_scraping_jobs_municipality ON zoning_scraping_jobs(municipality);
CREATE INDEX idx_scraping_jobs_status ON zoning_scraping_jobs(status);
CREATE INDEX idx_scraping_jobs_started ON zoning_scraping_jobs(started_at DESC);

-- Query log (for analytics)
CREATE TABLE IF NOT EXISTS zoning_query_log (
  id SERIAL PRIMARY KEY,
  query_type TEXT,  -- 'lookup', 'nlp_query', 'api_call'
  municipality TEXT,
  zoning_code TEXT,
  query_text TEXT,
  response_time_ms INTEGER,
  cache_hit BOOLEAN,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_query_log_created ON zoning_query_log(created_at DESC);
CREATE INDEX idx_query_log_municipality ON zoning_query_log(municipality);

-- Helper views
CREATE OR REPLACE VIEW v_zoning_summary AS
SELECT 
  municipality,
  COUNT(*) as total_districts,
  COUNT(CASE WHEN confidence_score >= 0.90 THEN 1 END) as high_confidence,
  COUNT(CASE WHEN confidence_score < 0.90 THEN 1 END) as needs_review,
  MAX(updated_at) as last_updated,
  AVG(confidence_score) as avg_confidence
FROM zoning_cache
GROUP BY municipality;

CREATE OR REPLACE VIEW v_scraping_status AS
SELECT 
  m.name as municipality,
  m.code_platform,
  m.scraping_priority,
  m.total_zoning_districts,
  m.last_scraped,
  COALESCE(j.status, 'not_started') as last_job_status,
  j.started_at as last_job_started,
  j.districts_scraped as last_job_districts,
  j.credits_used as last_job_credits
FROM brevard_municipalities m
LEFT JOIN LATERAL (
  SELECT * FROM zoning_scraping_jobs 
  WHERE municipality = m.name 
  ORDER BY started_at DESC 
  LIMIT 1
) j ON TRUE
ORDER BY m.scraping_priority, m.name;

COMMENT ON TABLE zoning_cache IS 'Main cache of zoning district data for Brevard County municipalities';
COMMENT ON TABLE zoning_permitted_uses IS 'Permitted, conditional, and prohibited uses by zoning district';
COMMENT ON TABLE zoning_requirements IS 'Specific dimensional and regulatory requirements by district';
COMMENT ON TABLE brevard_municipalities IS 'List of all Brevard County municipalities with scraping metadata';
COMMENT ON TABLE zoning_scraping_jobs IS 'Log of all scraping jobs and their results';
