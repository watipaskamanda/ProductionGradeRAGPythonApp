from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from pathlib import Path
import uuid
from data_loader import load_and_chunk_pdf, embed_texts
from vector_db import QdrantStorage
from db_query import query_database
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="RAG API", version="1.0.0")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Request/Response models
class QueryRequest(BaseModel):
    question: str
    top_k: int = 5

class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    num_contexts: int

class DBQueryRequest(BaseModel):
    question: str
    chat_history: list = []
    currency: str = "MWK"

class DBQueryResponse(BaseModel):
    question: str
    plan: dict
    sql: str
    answer: str
    markdown_table: str = ""
    chart_config: dict = {}
    suggested_visualizations: list = []
    metadata: dict = {}

@app.post("/ingest")
async def ingest_pdf(file: UploadFile = File(...)):
    """Upload and ingest a PDF into the vector database."""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(400, "Only PDF files allowed")
    
    # Save uploaded file
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    file_path = uploads_dir / file.filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Process PDF
    chunks = load_and_chunk_pdf(str(file_path))
    vecs = embed_texts(chunks)
    
    # Store in vector DB
    source_id = file.filename
    ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{i}")) for i in range(len(chunks))]
    payloads = [{"source": source_id, "text": chunks[i]} for i in range(len(chunks))]
    QdrantStorage().upsert(ids, vecs, payloads)
    
    return {"message": f"Ingested {len(chunks)} chunks from {file.filename}"}

@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """Ask a question and get an answer from the RAG system."""
    # Search vector DB
    query_vec = embed_texts([request.question])[0]
    store = QdrantStorage()
    found = store.search(query_vec, request.top_k)
    
    # Build prompt
    context_block = "\n\n".join(f"- {c}" for c in found["contexts"])
    user_content = (
        "Use the following context to answer the question.\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {request.question}\n"
        "Answer concisely using the context above."
    )
    
    # Get LLM response
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You answer questions using only the provided context."},
            {"role": "user", "content": user_content}
        ],
        max_tokens=1024,
        temperature=0.2
    )
    
    answer = response.choices[0].message.content.strip()
    
    return QueryResponse(
        answer=answer,
        sources=found["sources"],
        num_contexts=len(found["contexts"])
    )

@app.post("/query/database", response_model=DBQueryResponse)
async def query_db(request: DBQueryRequest):
    """Ask questions about live database data (Advanced Text-to-SQL with Planning)."""
    result = query_database(request.question, request.chat_history, request.currency)
    return DBQueryResponse(
        question=result["question"],
        plan=result["plan"],
        sql=result["sql"],
        answer=result["answer"],
        markdown_table=result["markdown_table"],
        chart_config=result["chart_config"],
        suggested_visualizations=result.get("suggested_visualizations", []),
        metadata=result["metadata"]
    )

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
