import logging
from fastapi import FastAPI
import inngest
import inngest.fast_api
from dotenv import load_dotenv
import uuid
import os
import datetime
from groq import Groq
from data_loader import load_and_chunk_pdf, embed_texts
from vector_db import QdrantStorage
from custom_types import RAQQueryResult, RAGSearchResult, RAGUpsertResult, RAGChunkAndSrc

load_dotenv()

inngest_client = inngest.Inngest(
    app_id="rag_app",
    logger=logging.getLogger("uvicorn"),
    is_production=False,
    serializer=inngest.PydanticSerializer()
)

# Initialize Groq client for LLM inference
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

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

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You answer questions using only the provided context."},
            {"role": "user", "content": user_content}
        ],
        max_tokens=1024,
        temperature=0.2
    )

    # Extract answer from LLM response
    answer = response.choices[0].message.content.strip()
    return {"answer": answer, "sources": found.sources, "num_contexts": len(found.contexts)}

# Initialize FastAPI application
app = FastAPI()

# Serve Inngest functions via FastAPI
inngest.fast_api.serve(app, inngest_client, [rag_ingest_pdf, rag_query_pdf_ai])