import os
import json
import asyncio
import logging
from typing import List, Dict
from dataclasses import dataclass, asdict

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("groq_api")

if not GROQ_API_KEY:
    raise ValueError("Missing GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)


@dataclass
class ScoredJob:
    """Job with relevance score and reasoning"""
    url: str
    title: str
    company: str
    location: str
    salary: str
    job_type: str
    description: str
    relevance_score: float  # 0-100
    match_reasons: List[str]
    red_flags: List[str]
    
    def to_dict(self):
        return asdict(self)


SCORING_SYSTEM_PROMPT = """You are an expert job relevance scorer for software engineers.

Your task is to evaluate job listings against user preferences and score them from 0-100.

SCORING CRITERIA:
- Tech stack match (30 points): Do the technologies align with what they want?
- Role relevance (25 points): Is this actually the role they're looking for?
- Seniority level (15 points): Does it match their experience level?
- Location/Remote (15 points): Does it match location preferences?
- Compensation (10 points): Is salary competitive?
- Company quality (5 points): Is it a reputable company?

CRITICAL RULES:
1. Return ONLY valid JSON.
2. Do NOT explain beyond JSON output.
3. Do NOT include markdown.
4. Score must be 0-100 integer.
5. Provide 2-4 match reasons.
6. List any red flags (missing info, mismatches, etc.).

OUTPUT FORMAT:
{
  "relevance_score": 75,
  "match_reasons": [
    "Strong Python/FastAPI match",
    "Remote opportunity",
    "Series A startup (good growth potential)"
  ],
  "red_flags": [
    "Salary range not specified",
    "Requires 5+ years (you have 3)"
  ]
}"""


async def score_job(
    job: Dict,
    user_preferences: str
) -> Dict:
    """
    Score a single job using Groq AI.
    
    Args:
        job: Job listing data
        user_preferences: User's job preferences/requirements
        
    Returns:
        Score and reasoning
    """
    
    try:
        user_prompt = f"""
USER PREFERENCES:
{user_preferences}

JOB LISTING:
Title: {job.get('title', 'Unknown')}
Company: {job.get('company', 'Unknown')}
Location: {job.get('location', 'Not specified')}
Salary: {job.get('salary', 'Not specified')}
Job Type: {job.get('job_type', 'Not specified')}

Description:
{job.get('description', 'No description available')[:1500]}

Score this job listing against the user preferences.
"""

        completion = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": SCORING_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        content = completion.choices[0].message.content
        parsed = json.loads(content)

        return {
            "relevance_score": parsed.get("relevance_score", 0),
            "match_reasons": parsed.get("match_reasons", []),
            "red_flags": parsed.get("red_flags", [])
        }

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return {
            "relevance_score": 0,
            "match_reasons": [],
            "red_flags": ["Failed to parse AI response"]
        }
    except Exception as e:
        logger.error(f"Scoring failed: {str(e)}")
        return {
            "relevance_score": 0,
            "match_reasons": [],
            "red_flags": [f"Error: {str(e)}"]
        }


async def score_jobs(
    jobs: List[Dict],
    user_preferences: str
) -> List[Dict]:
    """
    Score multiple jobs concurrently.
    
    Args:
        jobs: List of job listings
        user_preferences: User's preferences
        
    Returns:
        Scored jobs sorted by relevance
    """
    
    logger.info(f"Scoring {len(jobs)} jobs")
    
    # Score jobs with concurrency limit
    semaphore = asyncio.Semaphore(5)
    
    async def bounded_score(job):
        async with semaphore:
            return await score_job(job, user_preferences)
    
    scores = await asyncio.gather(
        *[bounded_score(job) for job in jobs],
        return_exceptions=True
    )
    
    # Combine jobs with scores
    scored_jobs = []
    
    for job, score in zip(jobs, scores):
        if isinstance(score, Exception):
            logger.error(f"Scoring error: {score}")
            continue
        
        scored_job = {
            **job,
            "relevance_score": score.get("relevance_score", 0),
            "match_reasons": score.get("match_reasons", []),
            "red_flags": score.get("red_flags", [])
        }
        
        scored_jobs.append(scored_job)
    
    # Sort by relevance score (highest first)
    scored_jobs.sort(
        key=lambda x: x.get("relevance_score", 0),
        reverse=True
    )
    
    logger.info(
        f"Scored {len(scored_jobs)} jobs. "
        f"Top score: {scored_jobs[0].get('relevance_score', 0) if scored_jobs else 0}"
    )
    
    return scored_jobs


async def filter_jobs(
    jobs: List[Dict],
    min_score: int = 60
) -> List[Dict]:
    """
    Filter jobs by minimum relevance score.
    
    Args:
        jobs: List of scored jobs
        min_score: Minimum score threshold
        
    Returns:
        Jobs above threshold
    """
    
    filtered = [
        job for job in jobs
        if job.get("relevance_score", 0) >= min_score
    ]
    
    logger.info(
        f"Filtered {len(jobs)} jobs -> {len(filtered)} above {min_score} score"
    )
    
    return filtered