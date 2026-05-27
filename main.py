import os
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import uvicorn

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import agents
try:
    from agents.search_agent import search_jobs
    from agents.crawling_agent import crawl_jobs
    from agents.scoring_agent import score_jobs, filter_jobs
    from agents.analyze_agent import analyze_jobs
except ImportError as e:
    logger.error(f"Failed to import agents: {str(e)}")
    raise


# ==================== Models ====================

class JobSearchRequest(BaseModel):
    """Request for job search"""
    query: str
    preferences: Optional[str] = None
    min_score: int = 60
    
    class Config:
        example = {
            "query": "remote backend engineer python fastapi",
            "preferences": "Looking for senior role, 5+ years experience, $150k+, fully remote",
            "min_score": 60
        }


class JobSearchResponse(BaseModel):
    """Response with job listings"""
    search_query: str
    total_discovered: int
    total_crawled: int
    total_scored: int
    high_quality_jobs: int
    top_matches: List[Dict]
    analysis: Dict
    
    class Config:
        example = {
            "search_query": "python backend engineer",
            "total_discovered": 50,
            "total_crawled": 45,
            "total_scored": 45,
            "high_quality_jobs": 12,
            "top_matches": [],
            "analysis": {}
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    message: str


# ==================== Lifespan ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app startup and shutdown"""
    # Startup
    logger.info("Starting Job Hunter API...")
    logger.info("All agents loaded successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Job Hunter API...")


# ==================== FastAPI App ====================

app = FastAPI(
    title="Job Hunter API",
    description="AI-powered job discovery and analysis pipeline",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Routes ====================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        message="Job Hunter API is running"
    )


@app.post("/search", response_model=JobSearchResponse)
async def search_and_analyze(request: JobSearchRequest):
    """
    Execute the full job hunter pipeline:
    1. Search for relevant jobs
    2. Crawl job listings
    3. Score by relevance
    4. Analyze market trends
    
    Args:
        request: JobSearchRequest with search criteria
        
    Returns:
        JobSearchResponse with results and analysis
    """
    
    try:
        logger.info(f"Starting job search: {request.query}")
        
        # Step 1: Search for jobs
        logger.info("Step 1: Searching for jobs...")
        discovered_urls = await search_jobs(request.query)
        
        if not discovered_urls:
            logger.warning("No jobs discovered")
            raise HTTPException(
                status_code=404,
                detail="No job listings found. Try different search terms."
            )
        
        logger.info(f"Discovered {len(discovered_urls)} job URLs")
        
        # Step 2: Crawl job listings
        logger.info("Step 2: Crawling job listings...")
        crawled_jobs = await crawl_jobs(discovered_urls)
        
        if not crawled_jobs:
            logger.warning("No jobs crawled successfully")
            raise HTTPException(
                status_code=500,
                detail="Failed to crawl job listings. Please try again."
            )
        
        logger.info(f"Crawled {len(crawled_jobs)} jobs")
        
        # Step 3: Score jobs
        logger.info("Step 3: Scoring jobs...")
        preferences = request.preferences or f"Looking for {request.query}"
        scored_jobs = await score_jobs(crawled_jobs, preferences)
        
        # Filter by minimum score
        filtered_jobs = await filter_jobs(scored_jobs, request.min_score)
        
        logger.info(f"Scored {len(scored_jobs)} jobs, {len(filtered_jobs)} above threshold")
        
        # Step 4: Analyze market
        logger.info("Step 4: Analyzing market trends...")
        analysis = await analyze_jobs(filtered_jobs)
        
        logger.info("Pipeline completed successfully")
        
        # Build response
        response = JobSearchResponse(
            search_query=request.query,
            total_discovered=len(discovered_urls),
            total_crawled=len(crawled_jobs),
            total_scored=len(scored_jobs),
            high_quality_jobs=len(filtered_jobs),
            top_matches=filtered_jobs[:10],  # Top 10 matches
            analysis=analysis
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline error: {str(e)}"
        )


@app.post("/search-async")
async def search_async(
    request: JobSearchRequest,
    background_tasks: BackgroundTasks
):
    """
    Async job search with background processing.
    Useful for long-running searches.
    
    Args:
        request: JobSearchRequest
        background_tasks: FastAPI background tasks
        
    Returns:
        Task acknowledgment
    """
    
    def run_search():
        """Run search in background"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                _execute_search(request)
            )
        except Exception as e:
            logger.error(f"Async search failed: {str(e)}")
    
    background_tasks.add_task(run_search)
    
    return {
        "status": "processing",
        "message": "Search started in background",
        "query": request.query
    }


async def _execute_search(request: JobSearchRequest):
    """Execute search pipeline for background task"""
    try:
        discovered_urls = await search_jobs(request.query)
        crawled_jobs = await crawl_jobs(discovered_urls)
        preferences = request.preferences or f"Looking for {request.query}"
        scored_jobs = await score_jobs(crawled_jobs, preferences)
        filtered_jobs = await filter_jobs(scored_jobs, request.min_score)
        analysis = await analyze_jobs(filtered_jobs)
        
        logger.info(f"Async search completed: {len(filtered_jobs)} quality jobs found")
        
    except Exception as e:
        logger.error(f"Async search pipeline error: {str(e)}")


@app.get("/stats")
async def get_stats():
    """Get pipeline statistics"""
    return {
        "message": "Pipeline statistics",
        "info": {
            "agents": ["search", "crawling", "scoring", "analyzing"],
            "apis": ["SerpAPI", "FireCrawl", "Groq"],
            "features": [
                "Semantic query expansion",
                "Multi-site job crawling",
                "AI relevance scoring",
                "Market trend analysis"
            ]
        }
    }


@app.post("/validate")
async def validate_preferences(request: JobSearchRequest):
    """
    Validate search query and preferences.
    
    Args:
        request: JobSearchRequest to validate
        
    Returns:
        Validation result
    """
    
    issues = []
    
    # Validate query
    if not request.query or len(request.query.strip()) < 3:
        issues.append("Query too short (minimum 3 characters)")
    
    if len(request.query) > 200:
        issues.append("Query too long (maximum 200 characters)")
    
    # Validate score
    if request.min_score < 0 or request.min_score > 100:
        issues.append("Min score must be between 0-100")
    
    # Check preferences
    if request.preferences and len(request.preferences) > 1000:
        issues.append("Preferences too long (maximum 1000 characters)")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "query": request.query,
        "min_score": request.min_score
    }


# ==================== Error Handlers ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return {
        "error": exc.detail,
        "status_code": exc.status_code
    }


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return {
        "error": "Internal server error",
        "status_code": 500
    }




if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    
    logger.info(f"Starting server on port {port}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )