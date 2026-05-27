import os
import asyncio
import logging
import json
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import aiohttp

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

FIRECRAWL_API_KEY = os.getenv("firecrawl_api")

if not FIRECRAWL_API_KEY:
    raise ValueError("Missing FIRECRAWL_API_KEY")

FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v0"


@dataclass
class JobListing:
    """Structured job listing data"""
    url: str
    title: str
    company: str
    description: str
    location: Optional[str] = None
    salary: Optional[str] = None
    job_type: Optional[str] = None
    raw_content: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)


async def fetch_url_with_firecrawl(url: str) -> Optional[str]:
    """
    Fetch and extract content from URL using FireCrawl API.
    
    Args:
        url: URL to crawl
        
    Returns:
        Extracted markdown content or None if failed
    """
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "url": url,
                "formats": ["markdown", "html"],
                "screenshot": False,
                "waitFor": 3000,
                "timeout": 30000
            }
            
            async with session.post(
                f"{FIRECRAWL_BASE_URL}/scrape",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=40)
            ) as response:
                
                if response.status != 200:
                    logger.error(
                        f"FireCrawl failed for {url}: {response.status}"
                    )
                    return None
                
                data = await response.json()
                
                if data.get("success"):
                    content = data.get("data", {})
                    markdown = content.get("markdown", "")
                    return markdown if markdown else None
                else:
                    logger.error(
                        f"FireCrawl error for {url}: {data.get('error')}"
                    )
                    return None
                    
    except asyncio.TimeoutError:
        logger.error(f"FireCrawl timeout for {url}")
        return None
    except Exception as e:
        logger.error(f"FireCrawl exception for {url}: {str(e)}")
        return None


def extract_job_fields(content: str, url: str) -> Dict:
    """
    Extract job fields from crawled content using pattern matching.
    
    Args:
        content: Extracted markdown content
        url: Original URL
        
    Returns:
        Dictionary with extracted job fields
    """
    
    try:
        # Split content into lines for analysis
        lines = content.split('\n')
        
        # Extract title (usually first heading)
        title = ""
        for line in lines:
            if line.strip().startswith('#'):
                title = line.strip().lstrip('#').strip()
                if title:
                    break
        
        # Extract company (look for common patterns)
        company = ""
        content_lower = content.lower()
        
        # Pattern: "Company: XXX" or "At XXX" or "From XXX"
        import re
        
        company_patterns = [
            r'company:\s*([^\n]+)',
            r'at\s+([A-Z][A-Za-z\s&]+?)(?:\n|$)',
            r'from\s+([A-Z][A-Za-z\s&]+?)(?:\n|$)',
        ]
        
        for pattern in company_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                if company:
                    break
        
        # Extract location
        location_patterns = [
            r'location:\s*([^\n]+)',
            r'based in\s+([^\n]+)',
            r'located in\s+([^\n]+)',
        ]
        
        location = ""
        for pattern in location_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                if location:
                    break
        
        # Extract salary
        salary_patterns = [
            r'\$[\d,]+\s*-\s*\$[\d,]+',
            r'salary:\s*([^\n]+)',
            r'compensation:\s*([^\n]+)',
        ]
        
        salary = ""
        for pattern in salary_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                salary = match.group(0) if salary_patterns.index(pattern) == 0 else match.group(1)
                if salary:
                    break
        
        # Extract job type (Full-time, Part-time, Contract, etc.)
        job_type_patterns = [
            r'(Full-time|Part-time|Contract|Freelance|Temporary)',
        ]
        
        job_type = ""
        for pattern in job_type_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                job_type = match.group(1)
                if job_type:
                    break
        
        # Description is first 500 chars of main content (excluding metadata)
        description = content[:1000] if len(content) > 1000 else content
        
        return {
            "title": title or "Unknown Position",
            "company": company or "Unknown Company",
            "location": location or "Not specified",
            "salary": salary or "Not specified",
            "job_type": job_type or "Not specified",
            "description": description.strip()
        }
        
    except Exception as e:
        logger.error(f"Field extraction failed: {str(e)}")
        return {
            "title": "Unknown Position",
            "company": "Unknown Company",
            "location": "Not specified",
            "salary": "Not specified",
            "job_type": "Not specified",
            "description": content[:500] if content else ""
        }


async def crawl_job_urls(urls: List[str]) -> List[JobListing]:
    """
    Crawl multiple job URLs and extract structured data.
    
    Args:
        urls: List of job listing URLs
        
    Returns:
        List of JobListing objects with extracted data
    """
    
    logger.info(f"Starting crawl of {len(urls)} URLs")
    
    jobs: List[JobListing] = []
    
    # Create tasks for all URLs with rate limiting
    tasks = []
    for url in urls:
        tasks.append(
            _crawl_single_job(url, jobs)
        )
    
    # Execute with concurrency limit (5 concurrent requests)
    semaphore = asyncio.Semaphore(5)
    
    async def bounded_crawl(url):
        async with semaphore:
            await _crawl_single_job(url, jobs)
    
    await asyncio.gather(
        *[bounded_crawl(url) for url in urls],
        return_exceptions=True
    )
    
    logger.info(f"Successfully crawled {len(jobs)} jobs")
    
    return jobs


async def _crawl_single_job(url: str, jobs_list: List[JobListing]):
    """
    Helper to crawl a single job URL.
    
    Args:
        url: URL to crawl
        jobs_list: List to append results to
    """
    
    try:
        logger.info(f"Crawling: {url}")
        
        content = await fetch_url_with_firecrawl(url)
        
        if not content:
            logger.warning(f"No content extracted from {url}")
            return
        
        # Extract fields from content
        fields = extract_job_fields(content, url)
        
        job_listing = JobListing(
            url=url,
            title=fields["title"],
            company=fields["company"],
            description=fields["description"],
            location=fields["location"],
            salary=fields["salary"],
            job_type=fields["job_type"],
            raw_content=content
        )
        
        jobs_list.append(job_listing)
        
        logger.info(
            f"Extracted: {fields['title']} at {fields['company']}"
        )
        
    except Exception as e:
        logger.error(f"Error crawling {url}: {str(e)}")


async def crawl_jobs(urls: List[str]) -> List[Dict]:
    """
    Main entry point for crawling agent.
    
    Args:
        urls: List of job URLs to crawl
        
    Returns:
        List of crawled job listings as dictionaries
    """
    
    job_listings = await crawl_job_urls(urls)
    
    # Convert to dictionaries for API response
    return [job.to_dict() for job in job_listings]