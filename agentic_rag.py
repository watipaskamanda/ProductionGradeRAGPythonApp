"""
Self-Improving Agentic RAG Pipeline using LangGraph
Implements iterative retrieval, grading, and generation with quality feedback loops
"""

from typing import Dict, List, Any, Optional, TypedDict, Annotated
from pydantic import BaseModel, Field
try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.sqlite import SqliteSaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    print("Warning: LangGraph not available. Agentic RAG features disabled.")
    LANGGRAPH_AVAILABLE = False
    # Create dummy classes for compatibility
    class StateGraph:
        def __init__(self, *args, **kwargs): pass
    class SqliteSaver:
        def __init__(self, *args, **kwargs): pass
    END = "END"

import sqlite3
import asyncio
import threading
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
import logging
from datetime import datetime
from pathlib import Path

# Import existing components
from data_loader import embed_texts
from vector_db import QdrantStorage

load_dotenv()

# Configure Google Gemini
gemini_model = None
if GEMINI_AVAILABLE and os.getenv('GEMINI_API_KEY'):
    try:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        gemini_model = genai.GenerativeModel('gemini-flash-latest')
    except Exception as e:
        print(f"Warning: Could not initialize Gemini: {e}")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Groq client
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
            logger.warning("Groq rate limit exceeded, falling back to Gemini")
            
            if GEMINI_AVAILABLE and gemini_model:
                try:
                    # Fallback to Gemini
                    full_prompt = f"{system_prompt}\n\n{user_prompt}"
                    response = gemini_model.generate_content(full_prompt)
                    return response.text.strip()
                
                except Exception as gemini_error:
                    logger.error(f"Both Groq and Gemini failed: Groq={e}, Gemini={gemini_error}")
                    raise Exception(f"AI service temporarily unavailable. Please try again in a moment.")
            else:
                logger.warning("Gemini fallback not available")
                raise Exception("I'm experiencing high demand right now. Please try again in a few minutes.")
        else:
            # Re-raise non-rate-limit errors
            raise e

class GraphState(TypedDict):
    """State that persists across all graph nodes"""
    question: str
    original_question: str
    generated_answer: str
    retrieved_contexts: List[Dict[str, Any]]
    generation_score: float
    retry_count: int
    needs_rewrite: bool
    rewrite_reason: str
    context_scores: List[float]
    final_sources: List[str]
    execution_path: List[str]
    error_message: str

class RAGGraphConfig(BaseModel):
    """Configuration for the RAG graph"""
    max_retries: int = 3
    min_context_score: float = 0.7
    min_generation_score: float = 0.6
    top_k_retrieval: int = 5
    enable_quality_check: bool = True
    enable_context_grading: bool = True

class AgenticRAGPipeline:
    """Self-improving RAG pipeline using LangGraph"""
    
    def __init__(self, config: RAGGraphConfig = None):
        self.config = config or RAGGraphConfig()
        self.vector_store = QdrantStorage()
        self.graph = None
        self._lock = threading.Lock()
        
        if not LANGGRAPH_AVAILABLE:
            logger.warning("LangGraph not available. Using fallback implementation.")
            return
        
        # Initialize SQLite checkpointer for state persistence
        try:
            self.checkpointer = SqliteSaver(sqlite3.connect("rag_checkpoints.db", check_same_thread=False))
        except Exception as e:
            logger.warning(f"Could not initialize checkpointer: {e}")
            self.checkpointer = None
        
        # Build the graph
        self._build_graph()
    
    def _build_graph(self):
        """Build the LangGraph workflow"""
        if not LANGGRAPH_AVAILABLE:
            logger.warning("LangGraph not available. Graph features disabled.")
            return
            
        try:
            workflow = StateGraph(GraphState)
            
            # Add nodes
            workflow.add_node("retrieve", self._retrieve_node)
            workflow.add_node("grade", self._grade_node)
            workflow.add_node("rewrite", self._rewrite_node)
            workflow.add_node("generate", self._generate_node)
            workflow.add_node("quality_check", self._quality_check_node)
            
            # Set entry point
            workflow.set_entry_point("retrieve")
            
            # Add conditional edges
            workflow.add_conditional_edges(
                "grade",
                self._should_rewrite,
                {
                    "rewrite": "rewrite",
                    "generate": "generate"
                }
            )
            
            workflow.add_conditional_edges(
                "rewrite",
                self._after_rewrite,
                {
                    "retrieve": "retrieve",
                    "end": END
                }
            )
            
            workflow.add_conditional_edges(
                "quality_check",
                self._should_retry,
                {
                    "rewrite": "rewrite",
                    "end": END
                }
            )
            
            # Connect nodes
            workflow.add_edge("retrieve", "grade")
            workflow.add_edge("generate", "quality_check")
            
            # Compile graph with checkpointer
            if self.checkpointer:
                self.graph = workflow.compile(checkpointer=self.checkpointer)
            else:
                self.graph = workflow.compile()
                
        except Exception as e:
            logger.error(f"Failed to build graph: {e}")
            self.graph = None
    
    def _retrieve_node(self, state: GraphState) -> GraphState:
        """Retrieve relevant contexts from vector database"""
        try:
            logger.info(f"🔍 Retrieving contexts for: {state['question']}")
            
            # Embed the question
            query_vector = embed_texts([state["question"]])[0]
            
            # Search vector database
            search_results = self.vector_store.search(query_vector, self.config.top_k_retrieval)
            
            # Format retrieved contexts with metadata
            contexts = []
            for i, (context, detail) in enumerate(zip(
                search_results["contexts"], 
                search_results.get("detailed_results", [])
            )):
                contexts.append({
                    "text": context,
                    "source": detail.get("source", f"Document {i+1}"),
                    "file_name": detail.get("file_name", "Unknown"),
                    "page_number": detail.get("page_number", "N/A"),
                    "header_context": detail.get("header_context", ""),
                    "score": detail.get("score", 0.0)
                })
            
            # Update state
            state["retrieved_contexts"] = contexts
            state["final_sources"] = search_results["sources"]
            state["execution_path"].append("retrieve")
            
            logger.info(f"✅ Retrieved {len(contexts)} contexts")
            return state
            
        except Exception as e:
            logger.error(f"❌ Retrieval failed: {e}")
            state["error_message"] = f"Retrieval error: {str(e)}"
            state["execution_path"].append("retrieve_error")
            return state
    
    def _grade_node(self, state: GraphState) -> GraphState:
        """Grade the relevance of retrieved contexts"""
        try:
            if not self.config.enable_context_grading:
                state["context_scores"] = [1.0] * len(state["retrieved_contexts"])
                state["needs_rewrite"] = False
                state["execution_path"].append("grade_skipped")
                return state
            
            logger.info("📊 Grading context relevance...")
            
            context_scores = []
            for i, context in enumerate(state["retrieved_contexts"]):
                score = self._grade_context_relevance(state["question"], context["text"])
                context_scores.append(score)
                logger.info(f"   Context {i+1}: {score:.2f}")
            
            # Calculate average score
            avg_score = sum(context_scores) / len(context_scores) if context_scores else 0.0
            
            # Determine if rewrite is needed
            needs_rewrite = avg_score < self.config.min_context_score
            
            # Update state
            state["context_scores"] = context_scores
            state["needs_rewrite"] = needs_rewrite
            state["execution_path"].append("grade")
            
            if needs_rewrite:
                state["rewrite_reason"] = f"Low context relevance: {avg_score:.2f} < {self.config.min_context_score}"
                logger.info(f"🔄 Rewrite needed: {state['rewrite_reason']}")
            else:
                logger.info(f"✅ Context quality sufficient: {avg_score:.2f}")
            
            return state
            
        except Exception as e:
            logger.error(f"❌ Grading failed: {e}")
            state["error_message"] = f"Grading error: {str(e)}"
            state["needs_rewrite"] = False
            state["execution_path"].append("grade_error")
            return state
    
    def _rewrite_node(self, state: GraphState) -> GraphState:
        """Rewrite the query for better retrieval"""
        try:
            logger.info("✏️ Rewriting query for better retrieval...")
            
            # Increment retry count
            state["retry_count"] += 1
            
            # Generate rewritten query
            rewritten_query = self._rewrite_query(
                state["original_question"], 
                state["question"],
                state.get("rewrite_reason", "")
            )
            
            # Update state
            state["question"] = rewritten_query
            state["execution_path"].append("rewrite")
            
            logger.info(f"📝 Query rewritten: {rewritten_query}")
            return state
            
        except Exception as e:
            logger.error(f"❌ Rewrite failed: {e}")
            state["error_message"] = f"Rewrite error: {str(e)}"
            state["execution_path"].append("rewrite_error")
            return state
    
    def _generate_node(self, state: GraphState) -> GraphState:
        """Generate the final answer based on retrieved contexts"""
        try:
            logger.info("🤖 Generating answer...")
            
            # Build context for generation
            context_blocks = []
            for i, context in enumerate(state["retrieved_contexts"]):
                source_info = f"[Source: {context.get('file_name', 'Unknown')} - Page {context.get('page_number', 'N/A')}]"
                if context.get('header_context'):
                    source_info += f" [Section: {context.get('header_context')}]"
                
                context_blocks.append(f"{source_info}\n{context['text']}")
            
            context_text = "\n\n".join(context_blocks)
            
            # Generate answer
            answer = self._generate_answer(state["original_question"], context_text)
            
            # Update state
            state["generated_answer"] = answer
            state["execution_path"].append("generate")
            
            logger.info("✅ Answer generated successfully")
            return state
            
        except Exception as e:
            logger.error(f"❌ Generation failed: {e}")
            state["error_message"] = f"Generation error: {str(e)}"
            state["generated_answer"] = f"I apologize, but I encountered an error while generating the answer: {str(e)}"
            state["execution_path"].append("generate_error")
            return state
    
    def _quality_check_node(self, state: GraphState) -> GraphState:
        """Check the quality of the generated answer"""
        try:
            if not self.config.enable_quality_check:
                state["generation_score"] = 1.0
                state["execution_path"].append("quality_check_skipped")
                return state
            
            logger.info("🎯 Checking answer quality...")
            
            # Grade the generated answer
            quality_score = self._grade_answer_quality(
                state["original_question"],
                state["generated_answer"],
                state["retrieved_contexts"]
            )
            
            # Update state
            state["generation_score"] = quality_score
            state["execution_path"].append("quality_check")
            
            logger.info(f"📊 Answer quality score: {quality_score:.2f}")
            return state
            
        except Exception as e:
            logger.error(f"❌ Quality check failed: {e}")
            state["error_message"] = f"Quality check error: {str(e)}"
            state["generation_score"] = 0.5  # Default moderate score
            state["execution_path"].append("quality_check_error")
            return state
    
    def _grade_context_relevance(self, question: str, context: str) -> float:
        """Grade how relevant a context is to the question"""
        prompt = f"""Grade the relevance of this context to the question on a scale of 0.0 to 1.0.

Question: {question}

Context: {context}

Consider:
- Does the context contain information that could help answer the question?
- Is the context topically related to the question?
- Would this context be useful for generating a good answer?

Return only a number between 0.0 and 1.0 (e.g., 0.8)"""

        try:
            score_text = call_llm(
                system_prompt="You are a relevance grader. Return only a decimal number between 0.0 and 1.0.",
                user_prompt=prompt,
                max_tokens=10,
                temperature=0.1
            )
            
            score = float(score_text)
            return max(0.0, min(1.0, score))  # Clamp between 0 and 1
            
        except Exception as e:
            logger.warning(f"Context grading failed: {e}")
            return 0.5  # Default moderate score
    
    def _rewrite_query(self, original_question: str, current_question: str, reason: str) -> str:
        """Rewrite the query for better retrieval"""
        prompt = f"""Rewrite this query to improve document retrieval results.

Original Question: {original_question}
Current Question: {current_question}
Reason for Rewrite: {reason}

Guidelines:
- Make the query more specific and detailed
- Add relevant keywords that might appear in documents
- Rephrase to match how information might be written in documents
- Keep the core intent of the original question

Return only the rewritten query:"""

        try:
            response_text = call_llm(
                system_prompt="You are a query optimization expert. Rewrite queries to improve document retrieval.",
                user_prompt=prompt,
                max_tokens=100,
                temperature=0.3
            )
            
            return response_text
            
        except Exception as e:
            logger.warning(f"Query rewrite failed: {e}")
            return current_question  # Return current question if rewrite fails
    
    def _generate_answer(self, question: str, context: str) -> str:
        """Generate the final answer based on context"""
        prompt = f"""Use the following context to answer the question. When referencing information, mention the specific document and page number.

Context:
{context}

Question: {question}

Instructions:
- Answer based only on the provided context
- Include source references like "According to [Document Name] on page X"
- If the context doesn't contain enough information, say so clearly
- Be concise but comprehensive

Answer:"""

        try:
            response_text = call_llm(
                system_prompt="You are a helpful assistant that answers questions based on provided context. Always include source references.",
                user_prompt=prompt,
                max_tokens=1024,
                temperature=0.2
            )
            
            return response_text
            
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return f"I apologize, but I encountered an error while generating the answer: {str(e)}"
    
    def _grade_answer_quality(self, question: str, answer: str, contexts: List[Dict]) -> float:
        """Grade the quality of the generated answer"""
        context_text = "\n".join([ctx["text"] for ctx in contexts])
        
        prompt = f"""Grade the quality of this answer on a scale of 0.0 to 1.0.

Question: {question}
Answer: {answer}
Available Context: {context_text[:1000]}...

Evaluate based on:
- Accuracy: Does the answer correctly use the context?
- Completeness: Does it address all parts of the question?
- Clarity: Is the answer clear and well-structured?
- Source Attribution: Does it properly reference sources?

Return only a number between 0.0 and 1.0 (e.g., 0.85)"""

        try:
            score_text = call_llm(
                system_prompt="You are an answer quality evaluator. Return only a decimal number between 0.0 and 1.0.",
                user_prompt=prompt,
                max_tokens=10,
                temperature=0.1
            )
            
            score = float(score_text)
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            logger.warning(f"Answer quality grading failed: {e}")
            return 0.7  # Default good score
    
    def _should_rewrite(self, state: GraphState) -> str:
        """Decide whether to rewrite the query or proceed to generation"""
        if state.get("error_message"):
            return "generate"  # Skip rewrite if there's an error
        
        if state["needs_rewrite"] and state["retry_count"] < self.config.max_retries:
            return "rewrite"
        else:
            return "generate"
    
    def _after_rewrite(self, state: GraphState) -> str:
        """Decide what to do after rewriting"""
        if state.get("error_message"):
            return "end"
        
        if state["retry_count"] >= self.config.max_retries:
            logger.warning(f"⚠️ Max retries ({self.config.max_retries}) reached")
            return "end"
        else:
            return "retrieve"
    
    def _should_retry(self, state: GraphState) -> str:
        """Decide whether to retry based on answer quality"""
        if state.get("error_message"):
            return "end"
        
        if (state["generation_score"] < self.config.min_generation_score and 
            state["retry_count"] < self.config.max_retries):
            logger.info(f"🔄 Retrying due to low quality: {state['generation_score']:.2f}")
            return "rewrite"
        else:
            return "end"
    
    async def arun(self, question: str, thread_id: str = None) -> Dict[str, Any]:
        """Run the RAG pipeline asynchronously"""
        with self._lock:
            return await self._run_pipeline(question, thread_id)
    
    def run(self, question: str, thread_id: str = None) -> Dict[str, Any]:
        """Run the RAG pipeline synchronously"""
        with self._lock:
            return asyncio.run(self._run_pipeline(question, thread_id))
    
    async def _run_pipeline(self, question: str, thread_id: str = None) -> Dict[str, Any]:
        """Execute the RAG pipeline"""
        try:
            # Generate thread ID if not provided
            if thread_id is None:
                thread_id = f"rag_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            logger.info(f"🚀 Starting RAG pipeline for: {question}")
            logger.info(f"🔗 Thread ID: {thread_id}")
            
            # If LangGraph is not available, use fallback implementation
            if not LANGGRAPH_AVAILABLE or self.graph is None:
                return await self._fallback_pipeline(question, thread_id)
            
            # Initialize state
            initial_state = GraphState(
                question=question,
                original_question=question,
                generated_answer="",
                retrieved_contexts=[],
                generation_score=0.0,
                retry_count=0,
                needs_rewrite=False,
                rewrite_reason="",
                context_scores=[],
                final_sources=[],
                execution_path=[],
                error_message=""
            )
            
            # Run the graph
            config = {"configurable": {"thread_id": thread_id}}
            final_state = None
            
            for state in self.graph.stream(initial_state, config):
                final_state = state
                # Log progress
                for node_name, node_state in state.items():
                    if "execution_path" in node_state:
                        last_step = node_state["execution_path"][-1] if node_state["execution_path"] else "unknown"
                        logger.info(f"📍 Completed: {last_step}")
            
            # Extract final state
            if final_state:
                # Get the last node's state
                final_node_state = list(final_state.values())[-1]
                
                # Format response
                response = {
                    "answer": final_node_state.get("generated_answer", "No answer generated"),
                    "sources": final_node_state.get("final_sources", []),
                    "num_contexts": len(final_node_state.get("retrieved_contexts", [])),
                    "source_details": final_node_state.get("retrieved_contexts", []),
                    "metadata": {
                        "generation_score": final_node_state.get("generation_score", 0.0),
                        "retry_count": final_node_state.get("retry_count", 0),
                        "execution_path": final_node_state.get("execution_path", []),
                        "context_scores": final_node_state.get("context_scores", []),
                        "thread_id": thread_id,
                        "self_improving": True
                    }
                }
                
                if final_node_state.get("error_message"):
                    response["error"] = final_node_state["error_message"]
                
                logger.info(f"✅ Pipeline completed. Score: {response['metadata']['generation_score']:.2f}, Retries: {response['metadata']['retry_count']}")
                return response
            else:
                raise Exception("No final state received from graph")
                
        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}")
            return {
                "answer": f"I apologize, but I encountered an error: {str(e)}",
                "sources": [],
                "num_contexts": 0,
                "source_details": [],
                "error": str(e),
                "metadata": {
                    "generation_score": 0.0,
                    "retry_count": 0,
                    "execution_path": ["error"],
                    "thread_id": thread_id or "unknown",
                    "self_improving": True
                }
            }
    
    async def _fallback_pipeline(self, question: str, thread_id: str) -> Dict[str, Any]:
        """Fallback implementation when LangGraph is not available"""
        logger.info("Using fallback RAG implementation (LangGraph not available)")
        
        try:
            # Simple linear pipeline
            state = {
                "question": question,
                "original_question": question,
                "retry_count": 0,
                "execution_path": []
            }
            
            # Retrieve
            state = self._retrieve_node(state)
            
            # Generate (skip grading and rewriting for simplicity)
            state = self._generate_node(state)
            
            # Format response
            return {
                "answer": state.get("generated_answer", "No answer generated"),
                "sources": state.get("final_sources", []),
                "num_contexts": len(state.get("retrieved_contexts", [])),
                "source_details": state.get("retrieved_contexts", []),
                "metadata": {
                    "generation_score": 0.8,  # Default score
                    "retry_count": 0,
                    "execution_path": state.get("execution_path", []),
                    "context_scores": [],
                    "thread_id": thread_id,
                    "self_improving": False,  # Fallback mode
                    "fallback_mode": True
                }
            }
            
        except Exception as e:
            logger.error(f"Fallback pipeline failed: {e}")
            return {
                "answer": f"I apologize, but I encountered an error: {str(e)}",
                "sources": [],
                "num_contexts": 0,
                "source_details": [],
                "error": str(e),
                "metadata": {
                    "generation_score": 0.0,
                    "retry_count": 0,
                    "execution_path": ["error"],
                    "thread_id": thread_id,
                    "self_improving": False,
                    "fallback_mode": True
                }
            }

# Global pipeline instance
_rag_pipeline = None
_pipeline_lock = threading.Lock()

def get_rag_pipeline(config: RAGGraphConfig = None) -> AgenticRAGPipeline:
    """Get or create the global RAG pipeline instance (thread-safe)"""
    global _rag_pipeline
    with _pipeline_lock:
        if _rag_pipeline is None:
            _rag_pipeline = AgenticRAGPipeline(config)
        return _rag_pipeline

def reset_rag_pipeline():
    """Reset the global RAG pipeline (useful for testing)"""
    global _rag_pipeline
    with _pipeline_lock:
        _rag_pipeline = None

# Convenience functions for backward compatibility
async def agentic_rag_query(question: str, config: RAGGraphConfig = None, thread_id: str = None) -> Dict[str, Any]:
    """Run agentic RAG query asynchronously"""
    pipeline = get_rag_pipeline(config)
    return await pipeline.arun(question, thread_id)

def sync_agentic_rag_query(question: str, config: RAGGraphConfig = None, thread_id: str = None) -> Dict[str, Any]:
    """Run agentic RAG query synchronously"""
    pipeline = get_rag_pipeline(config)
    return pipeline.run(question, thread_id)

if __name__ == "__main__":
    # Test the pipeline
    import asyncio
    
    async def test_pipeline():
        config = RAGGraphConfig(
            max_retries=2,
            min_context_score=0.6,
            min_generation_score=0.5,
            enable_quality_check=True
        )
        
        result = await agentic_rag_query(
            "What are the key features of this system?",
            config=config
        )
        
        print("🎯 Test Result:")
        print(f"Answer: {result['answer']}")
        print(f"Sources: {result['sources']}")
        print(f"Metadata: {result['metadata']}")
    
    asyncio.run(test_pipeline())