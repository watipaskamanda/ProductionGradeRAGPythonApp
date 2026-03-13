"""
Simplified API for quick startup
This version works without LangGraph and complex dependencies
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from typing import List, Optional, Dict, Any
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

# Configure sentence transformers cache directory before model initialization
os.environ['SENTENCE_TRANSFORMERS_HOME'] = './models'

# Try to import optional dependencies
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("Warning: Groq not available")

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Warning: Google Generative AI not available")

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    print("Warning: SentenceTransformers not available")

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import VectorParams, Distance, PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    print("Warning: Qdrant not available")

load_dotenv()

app = FastAPI(
    title="Enterprise RAG API - Simplified",
    description="Simplified version for quick startup",
    version="1.0.0-simple"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize optional services
groq_client = None
if GROQ_AVAILABLE and os.getenv("GROQ_API_KEY"):
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Configure Google Gemini
gemini_model = None
if GEMINI_AVAILABLE and os.getenv("GEMINI_API_KEY"):
    try:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"Warning: Could not initialize Gemini: {e}")

def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 300, temperature: float = 0.1) -> str:
    """Wrapper function that tries Groq first, falls back to Gemini on rate limit."""
    try:
        # Try Groq first
        if groq_client:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content.strip()
        else:
            raise Exception("Groq client not available")
    
    except Exception as e:
        error_str = str(e).lower()
        
        # Check if it's a rate limit error
        if 'rate_limit_exceeded' in error_str or 'rate limit' in error_str:
            print("Groq rate limit exceeded, falling back to Gemini")
            
            if gemini_model:
                try:
                    # Fallback to Gemini
                    full_prompt = f"{system_prompt}\n\n{user_prompt}"
                    response = gemini_model.generate_content(full_prompt)
                    return response.text.strip()
                
                except Exception as gemini_error:
                    print(f"Both Groq and Gemini failed: Groq={e}, Gemini={gemini_error}")
                    raise Exception(f"AI service temporarily unavailable. Please try again in a moment.")
            else:
                raise Exception("I'm experiencing high demand right now. Please try again in a few minutes.")
        else:
            # Re-raise non-rate-limit errors
            raise e

embedding_model = None
if EMBEDDINGS_AVAILABLE:
    try:
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    except Exception as e:
        print(f"Warning: Could not load embedding model: {e}")

# Response models
class QueryRequest(BaseModel):
    question: str
    top_k: int = 5

class QueryResponse(BaseModel):
    answer: str
    sources: List[str] = []
    num_contexts: int = 0
    status: str = "success"

class HealthResponse(BaseModel):
    status: str
    services: Dict[str, bool]
    message: str

# Routes
@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint"""
    return {
        "message": "Enterprise RAG API - Simplified Version",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    services = {
        "groq": GROQ_AVAILABLE and groq_client is not None,
        "gemini": GEMINI_AVAILABLE and gemini_model is not None,
        "embeddings": EMBEDDINGS_AVAILABLE and embedding_model is not None,
        "qdrant": QDRANT_AVAILABLE
    }
    
    all_healthy = all(services.values())
    
    return HealthResponse(
        status="healthy" if all_healthy else "partial",
        services=services,
        message="All services operational" if all_healthy else "Some services unavailable"
    )

@app.post("/api/v1/query", response_model=QueryResponse)
async def query_simple(request: QueryRequest):
    """Simple query endpoint without vector search"""
    
    if not groq_client and not gemini_model:
        return QueryResponse(
            answer="No AI services are available. Please check your API keys.",
            status="error"
        )
    
    try:
        # Simple prompt without RAG
        prompt = f"""Answer the following question based on your knowledge:

Question: {request.question}

Please provide a helpful and accurate answer."""

        answer = call_llm(
            system_prompt="You are a helpful AI assistant.",
            user_prompt=prompt,
            max_tokens=1024,
            temperature=0.2
        )
        
        return QueryResponse(
            answer=answer,
            sources=["AI Knowledge Base"],
            num_contexts=1,
            status="success"
        )
        
    except Exception as e:
        return QueryResponse(
            answer=f"Error processing query: {str(e)}",
            status="error"
        )

@app.post("/api/v1/ingest")
async def ingest_simple(file: UploadFile = File(...)):
    """Simple file upload endpoint"""
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "Only PDF files allowed")
    
    # Save uploaded file
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    file_path = uploads_dir / file.filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return {
        "message": f"File {file.filename} uploaded successfully",
        "note": "Vector processing not available in simplified mode",
        "file_path": str(file_path)
    }

@app.get("/api/v1/status")
async def get_status():
    """Get API status and available features"""
    return {
        "version": "1.0.0-simple",
        "features": {
            "groq_llm": GROQ_AVAILABLE and groq_client is not None,
            "gemini_llm": GEMINI_AVAILABLE and gemini_model is not None,
            "embeddings": EMBEDDINGS_AVAILABLE and embedding_model is not None,
            "vector_search": QDRANT_AVAILABLE,
            "file_upload": True,
            "simple_qa": True
        },
        "message": "Simplified API for quick startup"
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Simplified Enterprise RAG API...")
    print("📍 API will be available at: http://localhost:8000")
    print("📖 API docs will be available at: http://localhost:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)