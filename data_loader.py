from sentence_transformers import SentenceTransformer
from llama_index.readers.file import PDFReader
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import Settings
try:
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
except ImportError:
    # Fallback for older versions
    try:
        from llama_index.legacy.embeddings.huggingface import HuggingFaceEmbedding
    except ImportError:
        # Use sentence transformers directly if LlamaIndex embedding not available
        HuggingFaceEmbedding = None
        print("Warning: LlamaIndex HuggingFaceEmbedding not available, using sentence-transformers directly")

from dotenv import load_dotenv
import os
import re
from pathlib import Path
from typing import List, Dict, Any

load_dotenv()

# Configure sentence transformers cache directory before model initialization
os.environ['SENTENCE_TRANSFORMERS_HOME'] = './models'

# Embedding configuration
EMBED_MODEL = "all-MiniLM-L6-v2"
EMBED_DIM = 384

# Initialize embedding model for LlamaIndex (if available)
if HuggingFaceEmbedding:
    try:
        embedding_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)
        Settings.embed_model = embedding_model
    except Exception as e:
        print(f"Warning: Could not initialize LlamaIndex embedding model: {e}")
        print("Using sentence-transformers directly")
else:
    print("Using sentence-transformers directly (LlamaIndex embedding not available)")

# Sentence transformer for direct encoding
model = SentenceTransformer(EMBED_MODEL)

# Optimized splitter for financial documents
splitter = SentenceSplitter(
    chunk_size=1200,  # Slightly larger for financial context
    chunk_overlap=300,  # More overlap for financial continuity
    separator=" "
)

def extract_headers(text: str) -> List[str]:
    """Extract potential headers from financial document text."""
    lines = text.split('\n')
    headers = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Financial document header patterns
        if (len(line) < 100 and  # Not too long
            (line.isupper() or  # ALL CAPS headers
             re.match(r'^[A-Z][^.]*$', line) or  # Title case without periods
             re.match(r'^\d+\.\s+[A-Z]', line) or  # Numbered sections
             re.match(r'^[A-Z]+\s+[A-Z]+', line) or  # Multi-word caps
             any(keyword in line.upper() for keyword in [
                 'STATEMENT', 'SUMMARY', 'BALANCE', 'INCOME', 'CASH FLOW',
                 'ASSETS', 'LIABILITIES', 'EQUITY', 'REVENUE', 'EXPENSES'
             ]))):
            headers.append(line)
    
    return headers

def find_current_header(text: str, chunk_start: int) -> str:
    """Find the most relevant header for a chunk position."""
    lines = text[:chunk_start].split('\n')
    current_header = ""
    
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
            
        # Check if this looks like a header
        if (len(line) < 100 and
            (line.isupper() or
             re.match(r'^[A-Z][^.]*$', line) or
             re.match(r'^\d+\.\s+[A-Z]', line) or
             any(keyword in line.upper() for keyword in [
                 'STATEMENT', 'SUMMARY', 'BALANCE', 'INCOME', 'CASH FLOW',
                 'ASSETS', 'LIABILITIES', 'EQUITY', 'REVENUE', 'EXPENSES'
             ]))):
            current_header = line
            break
    
    return current_header

def load_and_chunk_pdf(path: str) -> List[Dict[str, Any]]:
    """Load PDF and create chunks with metadata and contextual headers."""
    file_name = Path(path).name
    docs = PDFReader().load_data(file=path)
    
    enhanced_chunks = []
    
    for page_idx, doc in enumerate(docs):
        if not hasattr(doc, 'text') or not doc.text:
            continue
            
        page_text = doc.text
        page_number = page_idx + 1
        
        # Split text into chunks
        text_chunks = splitter.split_text(page_text)
        
        for chunk_idx, chunk_text in enumerate(text_chunks):
            # Find chunk position in original text for header detection
            chunk_start = page_text.find(chunk_text[:50])  # Approximate position
            current_header = find_current_header(page_text, chunk_start)
            
            # Prepend header context if found
            enhanced_text = chunk_text
            if current_header:
                enhanced_text = f"[{current_header}]\n\n{chunk_text}"
            
            # Create chunk with metadata
            chunk_data = {
                'text': enhanced_text,
                'metadata': {
                    'file_name': file_name,
                    'page_number': page_number,
                    'chunk_index': chunk_idx,
                    'header_context': current_header,
                    'original_text': chunk_text  # Keep original for reference
                }
            }
            
            enhanced_chunks.append(chunk_data)
    
    return enhanced_chunks

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed texts using the configured model."""
    return model.encode(texts).tolist()

def embed_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Embed chunks and return with embeddings included."""
    texts = [chunk['text'] for chunk in chunks]
    embeddings = embed_texts(texts)
    
    for chunk, embedding in zip(chunks, embeddings):
        chunk['embedding'] = embedding
    
    return chunks