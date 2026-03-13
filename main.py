import logging
from fastapi import FastAPI
import inngest
import inngest.fast_api
from dotenv import load_dotenv
import uuid
import os
import datetime
from groq import Groq
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Warning: Google Generative AI not available")
from data_loader import load_and_chunk_pdf, embed_texts
from vector_db import QdrantStorage
from custom_types import RAQQueryResult, RAGSearchResult, RAGUpsertResult, RAGChunkAndSrc

load_dotenv()

# Configure Google Gemini
gemini_model = None
if GEMINI_AVAILABLE and os.getenv('GEMINI_API_KEY'):
    try:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        gemini_model = genai.GenerativeModel('gemini-flash-latest')
    except Exception as e:
        print(f"Warning: Could not initialize Gemini: {e}")

inngest_client = inngest.Inngest(
    app_id="rag_app",
    logger=logging.getLogger("uvicorn"),
    is_production=False,
    serializer=inngest.PydanticSerializer()
)

# Initialize Groq client for LLM inference
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

@inngest_client.create_function(
    fn_id="RAG: Ingest PDF",
    trigger=inngest.TriggerEvent(event="rag/ingest_pdf"),
    throttle=inngest.Throttle(
        count=2, period=datetime.timedelta(minutes=1)
    ),
    rate_limit=inngest.RateLimit(
        limit=1,
        period=datetime.timedelta(hours=4),
        key="event.data.source_id",
  ),
)
async def rag_ingest_pdf(ctx: inngest.Context):
    """Ingests a PDF file by loading, chunking, embedding, and storing in vector database."""
    
    def _load(ctx: inngest.Context) -> RAGChunkAndSrc:
        """Loads PDF and splits it into text chunks."""
        pdf_path = ctx.event.data["pdf_path"]
        source_id = ctx.event.data.get("source_id", pdf_path)
        chunks = load_and_chunk_pdf(pdf_path)
        return RAGChunkAndSrc(chunks=chunks, source_id=source_id)

    def _upsert(chunks_and_src: RAGChunkAndSrc) -> RAGUpsertResult:
        """Generates embeddings for chunks and stores them in Qdrant vector database."""
        chunks = chunks_and_src.chunks
        source_id = chunks_and_src.source_id
        vecs = embed_texts(chunks)
        ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{i}")) for i in range(len(chunks))]
        payloads = [{"source": source_id, "text": chunks[i]} for i in range(len(chunks))]
        QdrantStorage().upsert(ids, vecs, payloads)
        return RAGUpsertResult(ingested=len(chunks))

    chunks_and_src = await ctx.step.run("load-and-chunk", lambda: _load(ctx), output_type=RAGChunkAndSrc)
    ingested = await ctx.step.run("embed-and-upsert", lambda: _upsert(chunks_and_src), output_type=RAGUpsertResult)
    return ingested.model_dump()


@inngest_client.create_function(
    fn_id="RAG: Query PDF",
    trigger=inngest.TriggerEvent(event="rag/query_pdf_ai")
)
async def rag_query_pdf_ai(ctx: inngest.Context):
    """Answers questions by searching vector database and using LLM to generate response."""
    
    def _search(question: str, top_k: int = 5) -> RAGSearchResult:
        """Embeds question and searches for most similar chunks in vector database."""
        query_vec = embed_texts([question])[0]
        store = QdrantStorage()
        found = store.search(query_vec, top_k)
        return RAGSearchResult(contexts=found["contexts"], sources=found["sources"])

    question = ctx.event.data["question"]
    top_k = int(ctx.event.data.get("top_k", 5))

    found = await ctx.step.run("embed-and-search", lambda: _search(question, top_k), output_type=RAGSearchResult)

    context_block = "\n\n".join(f"- {c}" for c in found.contexts)
    user_content = (
        "Use the following context to answer the question.\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {question}\n"
        "Answer concisely using the context above."
    )

    response_text = call_llm(
        system_prompt="You answer questions using only the provided context.",
        user_prompt=user_content,
        max_tokens=1024,
        temperature=0.2
    )

    # Extract answer from LLM response
    answer = response_text
    return {"answer": answer, "sources": found.sources, "num_contexts": len(found.contexts)}

# Initialize FastAPI application
app = FastAPI()

# Serve Inngest functions via FastAPI
inngest.fast_api.serve(app, inngest_client, [rag_ingest_pdf, rag_query_pdf_ai])