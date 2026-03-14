import sys
import subprocess
subprocess.run([sys.executable, '-m', 'pip', 'install', 'google-generativeai'], capture_output=True)

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pathlib import Path
from typing import List, Optional, Dict, Any
import uuid
import json
import asyncio
from data_loader import load_and_chunk_pdf, embed_chunks, embed_texts
from vector_db import QdrantStorage
from agentic_rag import agentic_rag_query, RAGGraphConfig, get_rag_pipeline
from db_query import (
    query_database_with_validation, 
    health_check,
    get_tenant_schema,
    set_active_table,
    get_tenant_info,
    create_tenant,
    list_tenants
)
from groq import Groq
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Warning: Google Generative AI not available")
import os
from dotenv import load_dotenv
import json

load_dotenv()

# Configure Google Gemini
gemini_model = None
if GEMINI_AVAILABLE and os.getenv('GEMINI_API_KEY'):
    try:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        gemini_model = genai.GenerativeModel('gemini-flash-latest')
    except Exception as e:
        print(f"Warning: Could not initialize Gemini: {e}")

app = FastAPI(
    title="BIZINEZI AI Assistant API",
    description="Enterprise-grade SQL Agent with semantic validation",
    version="1.0.0"
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 300, temperature: float = 0.1) -> str:
    """Wrapper function that tries Groq first, falls back to Gemini on rate limit."""
    try:
        # Try Groq first
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
    
    except Exception as e:
        error_str = str(e).lower()
        
        # Check if it's a rate limit error
        if 'rate_limit_exceeded' in error_str or 'rate limit' in error_str:
            print("Groq rate limit exceeded, falling back to Gemini")
            
            if GEMINI_AVAILABLE and gemini_model:
                try:
                    # Fallback to Gemini
                    full_prompt = f"{system_prompt}\n\n{user_prompt}"
                    response = gemini_model.generate_content(full_prompt)
                    return response.text.strip()
                
                except Exception as gemini_error:
                    print(f"Both Groq and Gemini failed: Groq={e}, Gemini={gemini_error}")
                    raise Exception(f"AI service temporarily unavailable. Please try again in a moment.")
            else:
                print("Gemini fallback not available")
                raise Exception("I'm experiencing high demand right now. Please try again in a few minutes.")
        else:
            # Re-raise non-rate-limit errors
            raise e

# Query Router Agent
class QueryRouter:
    """Intent classification router for SQL, RAG, and conversational queries"""
    
    def __init__(self):
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    def classify_intent(self, question: str) -> dict:
        """Classify user intent as SQL_QUERY, RAG_QUERY, or CONVERSATIONAL"""
        system_prompt = """
Classify the user's input as either: SQL_QUERY, RAG_QUERY, or CONVERSATIONAL.

SQL_QUERY: Questions about data analysis, transactions, counts, totals, amounts, statistics, reports, or database queries.
Examples: "How many transactions?", "Show me high value transactions", "What's the total amount?", "Monthly breakdown"

RAG_QUERY: Questions about document content, policies, procedures, or information retrieval from uploaded documents.
Examples: "What does the policy say about refunds?", "Explain the procedure", "What are the requirements?"

CONVERSATIONAL: Greetings, personal questions, general chat, or questions about the assistant itself.
Examples: "Hi", "What is your name?", "How are you?", "What can you do?", "Thank you"

Return ONLY a JSON object with "intent" and "confidence" (0.0-1.0):
{"intent": "SQL_QUERY|RAG_QUERY|CONVERSATIONAL", "confidence": 0.95}
"""
        
        try:
            response_text = call_llm(
                system_prompt=system_prompt,
                user_prompt=f"Classify this input: {question}",
                max_tokens=100,
                temperature=0.1
            )
            
            # Clean up response and parse JSON
            result_text = response_text.replace("```json", "").replace("```", "").strip()
            result = json.loads(result_text)
            
            # Validate result
            if "intent" not in result or "confidence" not in result:
                raise ValueError("Invalid response format")
            
            if result["intent"] not in ["SQL_QUERY", "RAG_QUERY", "CONVERSATIONAL"]:
                raise ValueError("Invalid intent classification")
            
            return result
            
        except Exception as e:
            print(f"Intent classification error: {e}")
            # Fallback classification based on keywords
            return self._fallback_classification(question)
    
    def _fallback_classification(self, question: str) -> dict:
        """Fallback intent classification using keyword matching"""
        question_lower = question.lower().strip()
        
        # Conversational patterns
        conversational_keywords = [
            'hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening',
            'how are you', 'thanks', 'thank you', 'bye', 'goodbye', 'see you',
            'what is your name', 'who are you', 'what can you do', 'help me'
        ]
        
        if any(keyword in question_lower for keyword in conversational_keywords):
            return {"intent": "CONVERSATIONAL", "confidence": 0.8}
        
        # SQL query patterns
        sql_keywords = [
            'transaction', 'amount', 'count', 'total', 'sum', 'show', 'list', 
            'how many', 'what is', 'find', 'search', 'highest', 'lowest',
            'average', 'maximum', 'minimum', 'breakdown', 'analysis'
        ]
        
        if any(keyword in question_lower for keyword in sql_keywords):
            return {"intent": "SQL_QUERY", "confidence": 0.7}
        
        # Default to RAG for document-related queries
        return {"intent": "RAG_QUERY", "confidence": 0.6}
    
    def handle_conversational(self, question: str) -> dict:
        """Handle conversational queries with appropriate responses"""
        question_lower = question.lower().strip()
        
        # Greeting responses
        if any(word in question_lower for word in ['hi', 'hello', 'hey', 'good morning', 'good afternoon']):
            return {
                "answer": "Hello! I am BIZINEZI AI, your financial assistant. I can help you analyze your transaction data and answer questions about your documents. How can I assist you today?",
                "type": "greeting"
            }
        
        # Identity questions
        if any(phrase in question_lower for phrase in ['what is your name', 'who are you', 'what are you']):
            return {
                "answer": "I am BIZINEZI AI, your intelligent financial assistant. I specialize in analyzing transaction data and helping you understand your financial information. I can answer questions about your transactions, generate reports, and provide insights from your documents.",
                "type": "identity"
            }
        
        # Capability questions
        if any(phrase in question_lower for phrase in ['what can you do', 'help', 'capabilities']):
            return {
                "answer": "I can help you with:\n\n• **Transaction Analysis**: Count transactions, calculate totals, find high-value transactions\n• **Financial Reports**: Monthly breakdowns, trend analysis, transaction summaries\n• **Document Q&A**: Answer questions about uploaded PDFs and documents\n• **Data Insights**: Identify patterns and provide financial insights\n\nTry asking: 'How many transactions were there last month?' or 'What's the total transaction amount?'",
                "type": "capabilities"
            }
        
        # Thank you responses
        if any(word in question_lower for word in ['thanks', 'thank you']):
            return {
                "answer": "You're welcome! I'm here whenever you need help with your financial data or document analysis. Feel free to ask me anything!",
                "type": "thanks"
            }
        
        # Default conversational response
        return {
            "answer": "I'm BIZINEZI AI, your financial assistant. I'm here to help you analyze your transaction data and answer questions about your documents. What would you like to know?",
            "type": "general"
        }

# Initialize router
query_router = QueryRouter()

# Enhanced response models for progressive disclosure
class EnterpriseQueryResponse(BaseModel):
    question: str
    answer: str
    markdown_table: Optional[str] = ""
    chart_config: Optional[Dict[str, Any]] = {}
    suggested_visualizations: Optional[List[str]] = []
    metadata: Dict[str, Any]
    debug_info: Optional[Dict[str, Any]] = None  # Hidden by default
    raw_data: Optional[Dict[str, Any]] = None  # Raw data for table rendering
    
class DebugInfo(BaseModel):
    sql: str
    plan: Dict[str, Any]
    execution_steps: List[str]
    validation_results: Dict[str, Any]
    
class SSEMessage(BaseModel):
    type: str  # "status", "progress", "result", "error"
    data: Dict[str, Any]
class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    enable_self_improvement: bool = True  # Enable agentic RAG
    max_retries: int = 3
    min_context_score: float = 0.7
    min_generation_score: float = 0.6
    thread_id: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    num_contexts: int
    source_details: Optional[List[Dict[str, Any]]] = []  # Enhanced source information

class DBQueryRequest(BaseModel):
    question: str
    chat_history: list = []
    currency: str = "MWK"
    debug_mode: bool = False  # Progressive disclosure control
    user_level: str = "business"  # "business", "analyst", "developer"
    tenant_id: str = "default"  # Multi-tenant support

class DBQueryResponse(BaseModel):
    question: str
    plan: dict
    sql: str
    answer: str
    markdown_table: str = ""
    chart_config: dict = {}
    suggested_visualizations: list = []
    metadata: dict = {}

# API v1 Routes
@app.post("/api/v1/ingest")
async def ingest_pdf(file: UploadFile = File(...)):
    """Upload and ingest a PDF into the vector database with enhanced metadata."""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "Only PDF files allowed")
    
    # Save uploaded file
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    file_path = uploads_dir / file.filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Process PDF with enhanced chunking
    chunks = load_and_chunk_pdf(str(file_path))
    chunks_with_embeddings = embed_chunks(chunks)
    
    # Store in vector DB using new method
    store = QdrantStorage()
    store.upsert_chunks(chunks_with_embeddings)
    
    return {
        "message": f"Ingested {len(chunks)} chunks from {file.filename}",
        "chunks_processed": len(chunks),
        "pages_processed": len(set(chunk['metadata']['page_number'] for chunk in chunks)),
        "headers_detected": len([chunk for chunk in chunks if chunk['metadata']['header_context']])
    }

@app.post("/api/v1/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """Ask a question and get an answer from the RAG system with optional self-improvement."""
    
    if request.enable_self_improvement:
        # Use agentic RAG pipeline
        try:
            config = RAGGraphConfig(
                max_retries=request.max_retries,
                min_context_score=request.min_context_score,
                min_generation_score=request.min_generation_score,
                top_k_retrieval=request.top_k,
                enable_quality_check=True,
                enable_context_grading=True
            )
            
            result = await agentic_rag_query(
                question=request.question,
                config=config,
                thread_id=request.thread_id
            )
            
            return QueryResponse(
                answer=result["answer"],
                sources=result["sources"],
                num_contexts=result["num_contexts"],
                source_details=result.get("source_details", [])
            )
            
        except Exception as e:
            # Fallback to traditional RAG if agentic fails
            print(f"Agentic RAG failed, falling back to traditional: {e}")
            request.enable_self_improvement = False
    
    # Traditional RAG pipeline (fallback or explicitly requested)
    # Search vector DB
    query_vec = embed_texts([request.question])[0]
    store = QdrantStorage()
    found = store.search(query_vec, request.top_k)
    
    # Build enhanced context with source attribution
    context_blocks = []
    for i, (context, result) in enumerate(zip(found["contexts"], found.get("detailed_results", []))):
        source_info = f"[Source: {result.get('file_name', 'Unknown')} - Page {result.get('page_number', 'N/A')}]"
        if result.get('header_context'):
            source_info += f" [Section: {result.get('header_context')}]"
        context_blocks.append(f"{source_info}\n{context}")
    
    context_block = "\n\n".join(context_blocks)
    user_content = (
        "Use the following context to answer the question. When referencing information, "
        "mention the specific document and page number.\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {request.question}\n"
        "Answer concisely using the context above. Include source references like "
        "'According to [Document Name] on page X' when possible."
    )
    
    # Get LLM response
    response_text = call_llm(
        system_prompt="You answer questions using only the provided context. Always include source references when mentioning specific information.",
        user_prompt=user_content,
        max_tokens=1024,
        temperature=0.2
    )
    
    answer = response_text
    
    return QueryResponse(
        answer=answer,
        sources=found["sources"],
        num_contexts=len(found["contexts"]),
        source_details=found.get("detailed_results", [])
    )

def calculate_query_complexity(result: dict) -> float:
    """Calculate query complexity score for progressive disclosure."""
    score = 0.0
    
    # SQL complexity indicators
    sql = result.get("sql", "").upper()
    if "JOIN" in sql: score += 0.3
    if "GROUP BY" in sql: score += 0.2
    if "HAVING" in sql: score += 0.2
    if "SUBQUERY" in sql or "SELECT" in sql[sql.find("SELECT")+6:]: score += 0.4
    
    # Result complexity
    if result.get("metadata", {}).get("row_count", 0) > 100: score += 0.2
    if len(result.get("metadata", {}).get("columns", [])) > 5: score += 0.1
    
    # Error indicators
    if "error" in result.get("answer", "").lower(): score += 0.5
    if result.get("metadata", {}).get("attempts", 1) > 1: score += 0.3
    
    return min(score, 1.0)

@app.post("/api/v1/query/database", response_model=EnterpriseQueryResponse)
async def query_db(request: DBQueryRequest):
    """Enterprise database query with intent routing and progressive disclosure."""
    # Step 1: Classify intent using Query Router
    intent_result = query_router.classify_intent(request.question)
    print(f"🤖 Intent Classification: {intent_result}")
    
    # Step 2: Route based on intent
    if intent_result["intent"] == "CONVERSATIONAL":
        # Handle conversational queries directly
        conversational_response = query_router.handle_conversational(request.question)
        
        return EnterpriseQueryResponse(
            question=request.question,
            answer=conversational_response["answer"],
            markdown_table="",
            chart_config={},
            suggested_visualizations=[],
            metadata={
                "intent": "CONVERSATIONAL",
                "confidence": intent_result["confidence"],
                "response_type": conversational_response["type"],
                "analysis_type": "conversational",
                "tenant_id": request.tenant_id
            }
        )
    
    elif intent_result["intent"] == "RAG_QUERY":
        # TODO: Implement RAG pipeline routing
        return EnterpriseQueryResponse(
            question=request.question,
            answer="RAG queries are not yet implemented in this endpoint. Please use the /api/v1/query endpoint for document-based questions.",
            markdown_table="",
            chart_config={},
            suggested_visualizations=[],
            metadata={
                "intent": "RAG_QUERY",
                "confidence": intent_result["confidence"],
                "analysis_type": "rag_redirect",
                "tenant_id": request.tenant_id
            }
        )
    
    # Step 3: Handle SQL_QUERY intent
    print(f"🔍 Processing SQL query for tenant: {request.tenant_id}")
    print(f"🔍 Chat history length: {len(request.chat_history)}")
    
    result = query_database_with_validation(
        request.question, 
        request.chat_history, 
        request.currency,
        request.tenant_id
    )
    
    # Auto-detect complexity for progressive disclosure
    complexity_score = calculate_query_complexity(result)
    auto_debug = complexity_score > 0.7 or "error" in result["answer"].lower()
    
    # Progressive disclosure: hide technical details unless debug mode or high complexity
    response_data = {
        "question": result["question"],
        "answer": result["answer"],
        "markdown_table": result["markdown_table"],
        "chart_config": result["chart_config"],
        "suggested_visualizations": result.get("suggested_visualizations", []),
        "metadata": {
            "intent": "SQL_QUERY",
            "confidence": intent_result["confidence"],
            "analysis_type": result["metadata"].get("analysis_type"),
            "visualization_type": result["metadata"].get("visualization_type"),
            "has_chart": result["metadata"].get("has_chart", False),
            "complexity_score": complexity_score,
            "auto_debug_triggered": auto_debug,
            "tenant_id": request.tenant_id,
            "row_count": result["metadata"].get("row_count", 0),
            "columns": result["metadata"].get("columns", [])
        }
    }
    
    # Add raw_data if available
    if "raw_data" in result and result["raw_data"]:
        response_data["raw_data"] = result["raw_data"]
    
    response = EnterpriseQueryResponse(**response_data)
    
    # Add debug info if requested OR auto-detected complexity
    if request.debug_mode or auto_debug:
        response.debug_info = {
            "sql": result["sql"],
            "plan": result["plan"],
            "execution_steps": ["Intent classification", "Schema validation", "SQL generation", "Query execution"],
            "validation_results": {"passed": True, "warnings": []},
            "complexity_reason": "High complexity detected" if auto_debug else "Debug mode enabled",
            "intent_classification": intent_result
        }
    
    return response

@app.get("/api/v1/query/database/stream")
async def query_db_stream(question: str, currency: str = "MWK", debug_mode: bool = False, tenant_id: str = "default"):
    """Server-Sent Events endpoint for real-time query progress with intent routing."""
    async def generate_sse():
        # Step 1: Intent classification
        yield f"""data: {json.dumps({'type': 'status', 'data': {'message': 'Classifying intent...', 'step': 1, 'total': 5}})}

"""
        await asyncio.sleep(0.3)
        
        intent_result = query_router.classify_intent(question)
        
        # Handle conversational queries
        if intent_result["intent"] == "CONVERSATIONAL":
            yield f"""data: {json.dumps({'type': 'progress', 'data': {'message': 'Handling conversational query...', 'step': 2, 'total': 2}})}

"""
            await asyncio.sleep(0.2)
            
            conversational_response = query_router.handle_conversational(question)
            
            response_data = {
                'type': 'result',
                'data': {
                    'question': question,
                    'answer': conversational_response["answer"],
                    'markdown_table': '',
                    'chart_config': {},
                    'metadata': {
                        'intent': 'CONVERSATIONAL',
                        'confidence': intent_result['confidence'],
                        'response_type': conversational_response['type']
                    }
                }
            }
            
            yield f"""data: {json.dumps(response_data)}

"""
            return
        
        # Handle RAG queries
        if intent_result["intent"] == "RAG_QUERY":
            yield f"""data: {json.dumps({'type': 'progress', 'data': {'message': 'Redirecting to RAG pipeline...', 'step': 2, 'total': 2}})}

"""
            await asyncio.sleep(0.2)
            
            response_data = {
                'type': 'result',
                'data': {
                    'question': question,
                    'answer': 'RAG queries should use the /api/v1/query endpoint for document-based questions.',
                    'markdown_table': '',
                    'chart_config': {},
                    'metadata': {
                        'intent': 'RAG_QUERY',
                        'confidence': intent_result['confidence']
                    }
                }
            }
            
            yield f"""data: {json.dumps(response_data)}

"""
            return
        
        # Handle SQL queries
        yield f"""data: {json.dumps({'type': 'progress', 'data': {'message': 'Validating schema...', 'step': 2, 'total': 5}})}

"""
        await asyncio.sleep(0.5)
        
        yield f"""data: {json.dumps({'type': 'progress', 'data': {'message': 'Generating SQL...', 'step': 3, 'total': 5}})}

"""
        await asyncio.sleep(0.5)
        
        yield f"""data: {json.dumps({'type': 'progress', 'data': {'message': 'Executing query...', 'step': 4, 'total': 5}})}

"""
        await asyncio.sleep(0.5)
        
        try:
            result = query_database_with_validation(question, [], currency, tenant_id)
            
            # Send final result
            response_data = {
                'type': 'result',
                'data': {
                    'question': result['question'],
                    'answer': result['answer'],
                    'markdown_table': result['markdown_table'],
                    'chart_config': result['chart_config'],
                    'metadata': {
                        'intent': 'SQL_QUERY',
                        'confidence': intent_result['confidence'],
                        'tenant_id': tenant_id
                    }
                }
            }
            
            if debug_mode:
                response_data['data']['debug_info'] = {
                    'sql': result['sql'],
                    'plan': result['plan'],
                    'intent_classification': intent_result
                }
            
            yield f"""data: {json.dumps(response_data)}

"""
            
        except Exception as e:
            yield f"""data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}

"""
    
    return StreamingResponse(generate_sse(), media_type="text/plain")

@app.get("/health")
async def health():
    """Enhanced health check with regression testing."""
    result = health_check()
    
    if result["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=result)
    
    return result

@app.get("/health/{tenant_id}")
async def tenant_health(tenant_id: str):
    """Health check for specific tenant."""
    result = health_check(tenant_id)
    
    if result["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=result)
    
    return result

# Multi-tenant management endpoints
@app.get("/api/v1/tenants")
async def list_all_tenants():
    """List all available tenants."""
    try:
        tenants = list_tenants()
        tenant_info = []
        for tenant_id in tenants:
            info = get_tenant_info(tenant_id)
            tenant_info.append(info)
        
        return {
            "tenants": tenants,
            "tenant_details": tenant_info,
            "total_tenants": len(tenants)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/tenants/{tenant_id}")
async def get_tenant_details(tenant_id: str):
    """Get details for specific tenant."""
    try:
        info = get_tenant_info(tenant_id)
        if "error" in info:
            raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/tenants/{tenant_id}/schema")
async def get_tenant_schema_endpoint(tenant_id: str):
    """Get database schema for specific tenant."""
    try:
        schema = get_tenant_schema(tenant_id)
        if not schema["success"]:
            raise HTTPException(status_code=500, detail=schema["error"])
        return schema
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/tenants/{tenant_id}/active-table")
async def set_tenant_active_table(tenant_id: str, table_name: str):
    """Set active table for tenant."""
    try:
        result = set_active_table(tenant_id, table_name)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/tenants")
async def create_new_tenant(tenant_config: dict):
    """Create new tenant with configuration."""
    try:
        if "tenant_id" not in tenant_config:
            raise HTTPException(status_code=400, detail="tenant_id is required")
        
        tenant_id = tenant_config["tenant_id"]
        result = create_tenant(tenant_id, tenant_config)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Agentic RAG management endpoints
@app.get("/api/v1/rag/status")
async def get_rag_status():
    """Get status of the agentic RAG pipeline."""
    try:
        pipeline = get_rag_pipeline()
        return {
            "status": "active",
            "config": {
                "max_retries": pipeline.config.max_retries,
                "min_context_score": pipeline.config.min_context_score,
                "min_generation_score": pipeline.config.min_generation_score,
                "top_k_retrieval": pipeline.config.top_k_retrieval,
                "enable_quality_check": pipeline.config.enable_quality_check,
                "enable_context_grading": pipeline.config.enable_context_grading
            }
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/v1/rag/reset")
async def reset_rag_pipeline():
    """Reset the agentic RAG pipeline."""
    try:
        from agentic_rag import reset_rag_pipeline
        reset_rag_pipeline()
        return {"status": "reset", "message": "RAG pipeline reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health/simple")
async def simple_health():
    """Simple health check for basic liveness probe."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
