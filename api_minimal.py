"""
Minimal API for immediate testing
This version removes complex dependencies to get the backend running quickly
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Enterprise RAG API - Minimal Version",
    description="Minimal version for testing",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic models
class QueryRequest(BaseModel):
    question: str
    top_k: int = 5

class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    num_contexts: int

# Basic endpoints
@app.get("/")
async def root():
    return {"message": "Enterprise RAG API - Minimal Version", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "minimal"}

@app.get("/health/simple")
async def simple_health():
    return {"status": "healthy"}

@app.post("/api/v1/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """Basic query endpoint for testing"""
    return QueryResponse(
        answer=f"This is a test response for: {request.question}",
        sources=["test_source.pdf"],
        num_contexts=1
    )

@app.get("/api/v1/status")
async def get_status():
    return {
        "status": "running",
        "version": "minimal",
        "features": {
            "basic_api": True,
            "rag_pipeline": False,
            "agentic_features": False,
            "multi_tenant": False
        }
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting minimal API server...")
    print("📍 API available at: http://localhost:8000")
    print("📖 API docs at: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)