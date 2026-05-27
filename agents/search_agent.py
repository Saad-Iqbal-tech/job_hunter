import os
import re
import json
import asyncio
import logging

from typing import List, Set
from urllib.parse import urlparse, urlunparse

import serpapi

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SERPAPI_API_KEY = os.getenv("serp_api")
GROQ_API_KEY = os.getenv("groq_api")

if not SERPAPI_API_KEY:
    raise ValueError("Missing SERPAPI_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("Missing GROQ_API_KEY")


groq_client = Groq(
    api_key=GROQ_API_KEY
)


JOB_SITES = [
    "linkedin.com/jobs",
    "jobs.lever.co",
    "boards.greenhouse.io",
    "wellfound.com",
    "ycombinator.com/jobs",
]



BLOCKED_PATTERNS = [
    r"/blog/",
    r"/blogs/",
    r"/articles/",
    r"/category/",
    r"/categories/",
    r"/tag/",
    r"/tags/",
    r"/search",
    r"/feed",
    r"/page/\d+",
    r"\?page=",
    r"jobs\?keywords=",
]



QUERY_EXPANSION_SYSTEM_PROMPT = """
You are an AI job search query expansion engine.

Your ONLY task is to generate highly relevant,
high-recall semantic search queries for internet
job discovery systems.

You are NOT a chatbot.

You are helping an AI recruitment infrastructure platform discover jobs from:

- LinkedIn Jobs
- Lever
- Greenhouse
- Wellfound
- YC Jobs
- company career pages

GOALS:
- maximize relevant job discovery
- maintain strong semantic relevance
- expand role terminology intelligently
- infer related engineering titles
- infer stack synonyms
- infer adjacent backend roles
- infer remote-friendly terminology
- infer startup hiring language

IMPORTANT RULES:

1. Return ONLY valid JSON.
2. Do NOT explain anything.
3. Do NOT include markdown.
4. Do NOT include numbering.
5. Generate BETWEEN 8 and 15 search queries.
6. Queries must be SHORT and optimized for Google search.
7. Queries must target REALISTIC job titles used by recruiters.
8. Preserve important technologies from the user query.
9. Expand related role terminology intelligently.
10. Avoid generic garbage like:
   - software jobs
   - IT jobs
   - engineer hiring

GOOD QUERY EXAMPLES:
- remote fastapi backend engineer
- python api developer mongodb
- backend platform engineer python
- remote python microservices engineer
- docker aws backend engineer

BAD QUERY EXAMPLES:
- best jobs for python developers
- software engineering opportunities
- backend jobs hiring now

OUTPUT FORMAT:
{
  "queries": [
    "...",
    "...",
    "..."
  ]
}
"""



async def generate_search_queries(user_query: str) -> List[str]:
    """
    Use Groq to generate semantic search expansions.
    
    Args:
        user_query: User's job search criteria
        
    Returns:
        List of expanded search queries
    """

    try:

        user_prompt = f"""
User Search Query:
{user_query}

Task:
Generate semantic search query expansions that preserve the user's intent EXACTLY.

CRITICAL RULES:
- Do NOT change the domain of the user query
- If user asks frontend roles, keep frontend roles
- If user asks DevOps, keep DevOps
- If user asks full-stack, keep full-stack
- Do NOT default to backend unless explicitly mentioned
- Respect technologies mentioned by the user
- Respect location, seniority, and remote preferences

You may enhance queries by adding:
- equivalent job titles
- recruiter-friendly synonyms
- relevant tech stack expansions
- ATS-friendly variations

But NEVER change:
- job domain (frontend/backend/devops/data/etc.)
- role intent

Output JSON:
{{
  "queries": ["..."]
}}
"""

        completion = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": QUERY_EXPANSION_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        content = completion.choices[0].message.content

        parsed = json.loads(content)

        queries = parsed.get("queries", [])

        cleaned_queries = []

        for query in queries:

            query = query.strip()

            if query and len(query) > 5:
                cleaned_queries.append(query)

        logger.info(
            f"Generated {len(cleaned_queries)} AI search queries"
        )

        return cleaned_queries

    except Exception as e:

        logger.error(
            f"Groq query generation failed: {str(e)}"
        )

        return [user_query]



def normalize_url(url: str) -> str:
    """
    Remove tracking params and fragments.
    
    Args:
        url: Raw URL to normalize
        
    Returns:
        Cleaned URL without params/fragments
    """

    try:

        parsed = urlparse(url)

        cleaned = parsed._replace(
            query="",
            fragment=""
        )

        return urlunparse(cleaned).rstrip("/")

    except Exception:
        return url



def is_valid_job_url(url: str) -> bool:
    """
    Reject SEO spam and invalid pages.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is valid job listing
    """

    if not url:
        return False

    url = url.lower()

    if not any(site in url for site in JOB_SITES):
        return False

    for pattern in BLOCKED_PATTERNS:

        if re.search(pattern, url):
            return False

    return True



async def serpapi_search(query: str) -> List[str]:
    """
    Execute a single Google search using SerpAPI.
    
    Args:
        query: Search query string
        
    Returns:
        List of discovered job URLs
    """

    discovered_urls = []

    try:

        client = serpapi.Client(
            api_key=SERPAPI_API_KEY,
            timeout=20
        )

        for site in JOB_SITES:

            final_query = f"site:{site} {query}"

            results = await asyncio.to_thread(
                client.search,
                {
                    "engine": "google",
                    "q": final_query,
                    "num": 10,
                    "gl": "us",
                    "hl": "en",
                    "google_domain": "google.com"
                }
            )

            organic_results = results.get(
                "organic_results",
                []
            )

            for result in organic_results:

                url = result.get("link")

                if not url:
                    continue

                normalized = normalize_url(url)

                if is_valid_job_url(normalized):
                    discovered_urls.append(normalized)

        logger.info(
            f"Discovered {len(discovered_urls)} URLs for query: {query}"
        )

        return discovered_urls

    except Exception as e:

        logger.error(
            f"SerpAPI failed for query '{query}': {str(e)}"
        )

        return []



async def search_jobs(user_query: str) -> List[str]:
    """
    AI-powered job discovery pipeline.
    
    Main entry point that:
    1. Expands user query into semantic variations
    2. Searches each variation across job sites
    3. Deduplicates and returns unique URLs
    
    Args:
        user_query: User's job search criteria
        
    Returns:
        List of unique job listing URLs
    """

    semantic_queries = await generate_search_queries(
        user_query
    )

    logger.info(
        f"Generated semantic queries: {semantic_queries}"
    )

    tasks = [
        serpapi_search(query)
        for query in semantic_queries
    ]

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True
    )

    unique_urls: Set[str] = set()

    for result in results:

        if isinstance(result, Exception):
            logger.error(f"Search task failed: {result}")
            continue

        for url in result:
            unique_urls.add(url)

    logger.info(
        f"Final unique URLs discovered: {len(unique_urls)}"
    )

    return list(unique_urls)