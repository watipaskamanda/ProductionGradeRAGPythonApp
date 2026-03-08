# RAG Application with Groq

Production-grade RAG (Retrieval-Augmented Generation) system using free Groq API for LLM inference.

## Features

- 📄 PDF ingestion and chunking
- 🔍 Semantic search with vector embeddings
- 🤖 AI-powered Q&A using Groq (Llama 3.3 70B)
- 🆓 Completely free to use (no OpenAI costs)
- 🚀 FastAPI REST API
- 🎨 Streamlit UI

## Tech Stack

- **LLM**: Groq (Llama 3.3 70B) - Free
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2) - Free
- **Vector DB**: Qdrant
- **Backend**: FastAPI
- **Frontend**: Streamlit

## Setup

### 1. Install Dependencies

```bash
pip install fastapi uvicorn groq sentence-transformers inngest llama-index-core llama-index-readers-file python-dotenv qdrant-client streamlit python-multipart
```

### 2. Set Environment Variables

Create `.env` file:

```
GROQ_API_KEY=your_groq_api_key_here
```

Get free Groq API key: https://console.groq.com

### 3. Start Qdrant (Vector Database)

```bash
docker run -p 6333:6333 qdrant/qdrant
```

### 4. Start API Server

```bash
python api.py
```

### 5. Start Streamlit UI (Optional)

```bash
streamlit run streamlit_app.py
```

## Usage

### Option 1: Streamlit UI

1. Open http://localhost:8501
2. Upload PDF files
3. Ask questions about the content

### Option 2: REST API

API docs: http://localhost:8000/docs

**Upload PDF:**
```bash
curl -X POST -F "file=@document.pdf" http://localhost:8000/ingest
```

**Ask Question:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this about?", "top_k": 5}'
```

## Project Structure

```
.
├── api.py              # FastAPI REST API
├── main.py             # Inngest workflow version
├── streamlit_app.py    # Streamlit UI
├── data_loader.py      # PDF processing & embeddings
├── vector_db.py        # Qdrant vector database
├── custom_types.py     # Pydantic models
├── pyproject.toml      # Dependencies
└── .env                # Environment variables
```

## Cost

**100% FREE** - No API costs!
- Groq: 14,400 free requests/day
- Sentence-transformers: Runs locally
- Qdrant: Self-hosted

## License

MIT
