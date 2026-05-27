import os
import json
import asyncio
import logging
from typing import List, Dict
from collections import Counter
import statistics

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("groq_api")

if not GROQ_API_KEY:
    raise ValueError("Missing GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)


ANALYSIS_SYSTEM_PROMPT = """You are an expert career advisor and job market analyst.

Your task is to analyze job market trends and provide insights.

ANALYSIS TASKS:
1. Identify common tech stacks and skills in demand
2. Analyze salary ranges and location trends
3. Identify red flags and common requirements
4. Provide actionable recommendations
5. Flag skill gaps the user should work on

CRITICAL RULES:
1. Return ONLY valid JSON.
2. Do NOT explain beyond JSON.
3. Do NOT include markdown.
4. Be concise and actionable.

OUTPUT FORMAT:
{
  "market_trends": {
    "top_skills": ["Python", "FastAPI", "PostgreSQL"],
    "top_companies": ["Company A", "Company B"],
    "salary_insights": "Market average is $120k-$150k",
    "remote_percentage": 75
  },
  "recommendations": [
    "Learn Kubernetes (requested in 60% of roles)",
    "Polish your system design skills",
    "Consider moving to tech hubs (SF, NYC, Austin)"
  ],
  "red_flags": [
    "Many roles require 5+ years experience",
    "Only 20% offer competitive benefits"
  ],
  "skill_gaps": [
    "DevOps/Infrastructure",
    "Machine Learning"
  ]
}"""


def extract_text_data(jobs: List[Dict]) -> Dict[str, List[str]]:
    """
    Extract text data from job listings for analysis.
    
    Args:
        jobs: List of job listings
        
    Returns:
        Extracted text fields
    """
    
    titles = []
    companies = []
    locations = []
    descriptions = []
    
    for job in jobs:
        titles.append(job.get("title", ""))
        companies.append(job.get("company", ""))
        locations.append(job.get("location", ""))
        descriptions.append(job.get("description", ""))
    
    return {
        "titles": titles,
        "companies": companies,
        "locations": locations,
        "descriptions": descriptions
    }


def extract_numeric_insights(jobs: List[Dict]) -> Dict:
    """
    Extract numeric insights from jobs.
    
    Args:
        jobs: List of scored jobs
        
    Returns:
        Numeric statistics
    """
    
    scores = [job.get("relevance_score", 0) for job in jobs]
    salaries = []
    remote_jobs = 0
    
    # Parse salary ranges
    import re
    
    for job in jobs:
        salary_str = job.get("salary", "")
        
        # Extract numbers from salary strings
        numbers = re.findall(r'\d+', salary_str.replace(',', ''))
        if numbers:
            salaries.extend([int(n) for n in numbers])
    
    # Count remote jobs
    for job in jobs:
        if "remote" in job.get("location", "").lower() or \
           "remote" in job.get("description", "").lower():
            remote_jobs += 1
    
    insights = {
        "total_jobs": len(jobs),
        "avg_score": round(statistics.mean(scores), 2) if scores else 0,
        "median_score": round(statistics.median(scores), 2) if scores else 0,
        "high_quality_jobs": len([j for j in jobs if j.get("relevance_score", 0) >= 70]),
        "avg_salary": round(statistics.mean(salaries), 0) if salaries else None,
        "remote_percentage": round((remote_jobs / len(jobs) * 100), 1) if jobs else 0,
        "salary_range": f"${min(salaries)}-${max(salaries)}" if salaries else "Not available"
    }
    
    return insights


def extract_keywords(text_list: List[str], min_length: int = 3) -> List[tuple]:
    """
    Extract and count keywords from text.
    
    Args:
        text_list: List of text strings
        min_length: Minimum word length to consider
        
    Returns:
        List of (keyword, count) tuples
    """
    
    keywords = []
    
    # Common tech keywords to look for
    tech_keywords = [
        "python", "javascript", "typescript", "go", "rust", "java", "c++",
        "fastapi", "django", "flask", "react", "vue", "angular",
        "postgres", "mongodb", "mysql", "redis", "elasticsearch",
        "docker", "kubernetes", "aws", "gcp", "azure",
        "git", "linux", "ci/cd", "jenkins", "gitlab",
        "rest", "graphql", "microservices", "sql",
        "api", "backend", "frontend", "fullstack", "devops"
    ]
    
    # Extract keywords
    for text in text_list:
        text_lower = text.lower()
        for keyword in tech_keywords:
            if keyword in text_lower:
                keywords.append(keyword)
    
    # Count and sort
    counted = Counter(keywords)
    
    return counted.most_common(15)


async def analyze_market(jobs: List[Dict]) -> Dict:
    """
    Perform market analysis using Groq.
    
    Args:
        jobs: List of job listings
        
    Returns:
        Market analysis results
    """
    
    try:
        # Extract data
        text_data = extract_text_data(jobs)
        numeric_data = extract_numeric_insights(jobs)
        
        # Get top keywords
        titles_keywords = extract_keywords(text_data["titles"])
        companies_keywords = Counter(text_data["companies"]).most_common(10)
        locations_keywords = Counter(text_data["locations"]).most_common(10)
        
        # Find common requirements from descriptions
        descriptions_keywords = extract_keywords(text_data["descriptions"])
        
        # Build analysis prompt
        analysis_prompt = f"""
MARKET DATA FROM {numeric_data.get('total_jobs', 0)} JOB LISTINGS:

Numeric Insights:
- Average job relevance score: {numeric_data.get('avg_score', 'N/A')}
- High quality jobs (score >= 70): {numeric_data.get('high_quality_jobs', 0)}
- Remote positions: {numeric_data.get('remote_percentage', 0)}%
- Average salary: {numeric_data.get('avg_salary', 'N/A')}
- Salary range: {numeric_data.get('salary_range', 'N/A')}

Top Technologies/Keywords:
{format_keyword_list(descriptions_keywords)}

Top Companies Hiring:
{format_keyword_list(companies_keywords)}

Top Locations:
{format_keyword_list(locations_keywords)}

Analyze this market data and provide insights, trends, and recommendations.
"""

        completion = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model="llama-3.3-70b-versatile",
            temperature=0.5,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": ANALYSIS_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": analysis_prompt
                }
            ]
        )

        content = completion.choices[0].message.content
        parsed = json.loads(content)

        return {
            "numeric_insights": numeric_data,
            "keyword_analysis": {
                "top_skills": [kw[0] for kw in descriptions_keywords[:10]],
                "top_companies": [kw[0] for kw in companies_keywords[:10]],
                "top_locations": [kw[0] for kw in locations_keywords[:10]]
            },
            "ai_analysis": parsed
        }

    except Exception as e:
        logger.error(f"Market analysis failed: {str(e)}")
        return {
            "numeric_insights": extract_numeric_insights(jobs),
            "keyword_analysis": {},
            "ai_analysis": {
                "error": str(e)
            }
        }


def format_keyword_list(keywords: List[tuple], max_items: int = 10) -> str:
    """
    Format keyword list for display.
    
    Args:
        keywords: List of (keyword, count) tuples
        max_items: Maximum items to show
        
    Returns:
        Formatted string
    """
    
    lines = []
    for i, (keyword, count) in enumerate(keywords[:max_items], 1):
        lines.append(f"{i}. {keyword} ({count} mentions)")
    
    return "\n".join(lines) if lines else "No data available"


def generate_summary(
    analyzed_jobs: List[Dict],
    analysis: Dict
) -> Dict:
    """
    Generate executive summary of findings.
    
    Args:
        analyzed_jobs: Analyzed job listings
        analysis: Market analysis results
        
    Returns:
        Summary report
    """
    
    top_3_jobs = analyzed_jobs[:3]
    insights = analysis.get("numeric_insights", {})
    keywords = analysis.get("keyword_analysis", {})
    
    summary = {
        "total_opportunities": insights.get("total_jobs", 0),
        "high_quality_matches": insights.get("high_quality_jobs", 0),
        "remote_friendly": insights.get("remote_percentage", 0),
        "market_salary_avg": insights.get("avg_salary", "N/A"),
        "top_matches": [
            {
                "rank": i + 1,
                "title": job.get("title"),
                "company": job.get("company"),
                "score": job.get("relevance_score"),
                "url": job.get("url")
            }
            for i, job in enumerate(top_3_jobs)
        ],
        "in_demand_skills": keywords.get("top_skills", [])[:5],
        "hiring_hotspots": keywords.get("top_locations", [])[:5],
        "ai_recommendations": analysis.get("ai_analysis", {}).get("recommendations", [])
    }
    
    return summary


async def analyze_jobs(
    jobs: List[Dict]
) -> Dict:
    """
    Main entry point for analyzing agent.
    
    Performs market analysis and generates insights.
    
    Args:
        jobs: List of scored job listings
        
    Returns:
        Complete analysis report
    """
    
    logger.info(f"Analyzing {len(jobs)} jobs")
    
    # Perform market analysis
    analysis = await analyze_market(jobs)
    
    # Generate summary
    summary = generate_summary(jobs, analysis)
    
    return {
        "summary": summary,
        "detailed_analysis": analysis
    }