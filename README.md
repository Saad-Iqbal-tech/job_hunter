Job Hunter

AI-powered job discovery and analysis pipeline built with FastAPI, asynchronous processing, and multi-agent orchestration.

Overview

Job Hunter API is a backend system that automates the process of discovering, crawling, scoring, and analyzing job listings from multiple sources. The system uses a modular multi-agent architecture to process job searches intelligently and return highly relevant opportunities based on user preferences.

The platform is designed to support scalable job intelligence workflows by integrating semantic search, web crawling, AI-based scoring, and market analysis into a single API service.

Features
Intelligent Job Discovery

Searches for relevant job listings using semantic search expansion and recruiter-style terminology.

Multi-Agent Architecture

The pipeline is divided into specialized agents:

Search Agent
Crawling Agent
Scoring Agent
Analysis Agent

Each agent handles a dedicated stage of the workflow independently.

AI-Based Job Scoring

Evaluates job relevance based on:

Search query
User preferences
Seniority level
Technology stack
Compensation expectations
Remote requirements
Market Trend Analysis

Analyzes discovered job listings to identify:

Popular technologies
Hiring patterns
Remote job availability
Market demand trends
Asynchronous Processing

Uses Python async workflows and FastAPI background tasks for scalable and non-blocking execution.

Structured API Design

Includes:

Request validation
Error handling
Health monitoring
Logging
Background processing support
Architecture
Client Request
      │
      ▼
Search Agent
      │
      ▼
Crawling Agent
      │
      ▼
Scoring Agent
      │
      ▼
Analysis Agent
      │
      ▼
Structured API Response
Tech Stack
Backend
Python
FastAPI
AsyncIO
Uvicorn
AI and Search
Groq API
SerpAPI
Firecrawl
Data Validation
Pydantic
Infrastructure
REST API Architecture
Background Task Processing
Structured Logging
Project Structure
project/
│
├── agents/
│   ├── search_agent.py
│   ├── crawling_agent.py
│   ├── scoring_agent.py
│   └── analyze_agent.py
│
├── main.py
├── requirements.txt
├── .env
└── README.md
Installation
Clone Repository
git clone https://github.com/yourusername/job-hunter-api.git

cd job-hunter-api
Create Virtual Environment
Windows
python -m venv venv

venv\Scripts\activate
Linux / macOS
python3 -m venv venv

source venv/bin/activate
Install Dependencies
pip install -r requirements.txt
Environment Variables

Create a .env file in the root directory.

GROQ_API_KEY=your_groq_api_key

SERPAPI_API_KEY=your_serpapi_key

FIRECRAWL_API_KEY=your_firecrawl_key

PORT=8000
Running the Server
python main.py

The API will start on:

http://localhost:8000
API Endpoints
Health Check
GET /health

Checks API status.

Response
{
  "status": "healthy",
  "message": "Job Hunter API is running"
}
Search Jobs
POST /search

Executes the complete job intelligence pipeline.

Request Body
{
  "query": "remote backend engineer python fastapi",
  "preferences": "Looking for senior role, 5+ years experience, fully remote",
  "min_score": 60
}
Workflow
Discover job listings
Crawl job pages
Score job relevance
Analyze market data
Return ranked results
Response
{
  "search_query": "python backend engineer",
  "total_discovered": 50,
  "total_crawled": 45,
  "total_scored": 45,
  "high_quality_jobs": 12,
  "top_matches": [],
  "analysis": {}
}
Async Search
POST /search-async

Runs the search pipeline in the background.

Response
{
  "status": "processing",
  "message": "Search started in background",
  "query": "backend engineer"
}
Validate Query
POST /validate

Validates search requests and user preferences.

Response
{
  "valid": true,
  "issues": [],
  "query": "python backend engineer",
  "min_score": 60
}
Pipeline Statistics
GET /stats

Returns information about the system architecture and supported features.

Response
{
  "message": "Pipeline statistics",
  "info": {
    "agents": [
      "search",
      "crawling",
      "scoring",
      "analyzing"
    ]
  }
}
Multi-Agent Workflow
1. Search Agent

Responsible for discovering job listings using semantic query expansion and external search APIs.

Responsibilities
Expand search intent
Find relevant job URLs
Reduce irrelevant search results
2. Crawling Agent

Extracts structured job data from discovered job pages.

Responsibilities
Crawl job listings
Parse structured information
Extract company and role details
3. Scoring Agent

Ranks job listings using AI-based relevance analysis.

Responsibilities
Match user preferences
Score relevance
Filter low-quality jobs
4. Analysis Agent

Analyzes aggregated results to generate market insights.

Responsibilities
Identify hiring trends
Detect popular technologies
Analyze remote job availability
Error Handling

The API includes centralized exception handling for:

Invalid requests
Agent failures
External API errors
Crawling failures
Unexpected runtime exceptions
Logging

Structured logging is enabled across the pipeline to monitor:

Search execution
Crawling progress
Agent activity
Pipeline failures
Background task execution
Scalability Considerations

The system is designed to support scalable workloads using:

Asynchronous processing
Modular agent separation
Background task execution
Stateless API architecture
Future Improvements

Potential future enhancements include:

Resume parsing support
Vector database integration
Embedding-based semantic ranking
Personalized recommendation memory
Real-time job monitoring
User authentication
Dashboard analytics
Distributed crawling infrastructure
Use Cases
AI-powered job search platforms
Career intelligence systems
Hiring market analysis
Automated opportunity discovery
Recruitment automation tools
