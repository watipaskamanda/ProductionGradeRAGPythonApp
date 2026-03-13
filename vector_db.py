from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from typing import List, Dict, Any


class QdrantStorage:
    def __init__(self, url="http://localhost:6333", collection="docs", dim=384):
        self.client = QdrantClient(url=url, timeout=30)
        self.collection = collection
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    def upsert(self, ids, vectors, payloads):
        points = [PointStruct(id=ids[i], vector=vectors[i], payload=payloads[i]) for i in range(len(ids))]
        self.client.upsert(self.collection, points=points)

    def upsert_chunks(self, chunks: List[Dict[str, Any]]):
        """Upsert chunks with enhanced metadata structure."""
        points = []
        for i, chunk in enumerate(chunks):
            payload = {
                "text": chunk['text'],
                "file_name": chunk['metadata']['file_name'],
                "page_number": chunk['metadata']['page_number'],
                "chunk_index": chunk['metadata']['chunk_index'],
                "header_context": chunk['metadata']['header_context'],
                "source": f"{chunk['metadata']['file_name']} (Page {chunk['metadata']['page_number']})"
            }
            
            point = PointStruct(
                id=i,
                vector=chunk['embedding'],
                payload=payload
            )
            points.append(point)
        
        self.client.upsert(self.collection, points=points)

    def search(self, query_vector, top_k: int = 5):
        results = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            with_payload=True,
            limit=top_k
        ).points
        
        contexts = []
        sources = set()
        detailed_results = []

        for r in results:
            payload = getattr(r, "payload", None) or {}
            text = payload.get("text", "")
            file_name = payload.get("file_name", "")
            page_number = payload.get("page_number", "")
            header_context = payload.get("header_context", "")
            source = payload.get("source", "")
            
            if text:
                contexts.append(text)
                sources.add(source)
                
                # Enhanced result with metadata
                detailed_results.append({
                    "text": text,
                    "file_name": file_name,
                    "page_number": page_number,
                    "header_context": header_context,
                    "source": source,
                    "score": getattr(r, "score", 0.0)
                })

        return {
            "contexts": contexts, 
            "sources": list(sources),
            "detailed_results": detailed_results
        }