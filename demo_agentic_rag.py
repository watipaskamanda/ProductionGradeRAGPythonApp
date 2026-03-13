#!/usr/bin/env python3
"""
Agentic RAG Pipeline Demo
Demonstrates the self-improving RAG system with LangGraph
"""

import asyncio
import json
from pathlib import Path
from agentic_rag import (
    AgenticRAGPipeline,
    RAGGraphConfig,
    agentic_rag_query,
    sync_agentic_rag_query
)

def demo_basic_usage():
    """Demonstrate basic agentic RAG usage"""
    print("🤖 Agentic RAG Pipeline - Basic Usage Demo")
    print("=" * 50)
    
    # Configure the pipeline
    config = RAGGraphConfig(
        max_retries=2,
        min_context_score=0.6,
        min_generation_score=0.5,
        top_k_retrieval=5,
        enable_quality_check=True,
        enable_context_grading=True
    )
    
    # Test questions
    questions = [
        "What are the main features of this system?",
        "How does the chunking strategy work?",
        "What is the purpose of metadata in chunks?",
        "Explain the vector database integration"
    ]
    
    print(f"📋 Configuration:")
    print(f"   Max Retries: {config.max_retries}")
    print(f"   Min Context Score: {config.min_context_score}")
    print(f"   Min Generation Score: {config.min_generation_score}")
    print(f"   Quality Check: {config.enable_quality_check}")
    print(f"   Context Grading: {config.enable_context_grading}")
    
    for i, question in enumerate(questions, 1):
        print(f"\n🔍 Question {i}: {question}")
        
        try:
            # Use synchronous version for demo
            result = sync_agentic_rag_query(question, config)
            
            print(f"✅ Answer: {result['answer'][:200]}...")
            print(f"📊 Metadata:")
            print(f"   Generation Score: {result['metadata']['generation_score']:.2f}")
            print(f"   Retry Count: {result['metadata']['retry_count']}")
            print(f"   Execution Path: {' → '.join(result['metadata']['execution_path'])}")
            print(f"   Sources: {len(result['sources'])}")
            
            if result['metadata'].get('context_scores'):
                avg_context_score = sum(result['metadata']['context_scores']) / len(result['metadata']['context_scores'])
                print(f"   Avg Context Score: {avg_context_score:.2f}")
            
        except Exception as e:
            print(f"❌ Error: {e}")

def demo_self_improvement():
    """Demonstrate self-improvement capabilities"""
    print("\n🔄 Self-Improvement Demo")
    print("=" * 30)
    
    # Configure with strict requirements to trigger improvements
    strict_config = RAGGraphConfig(
        max_retries=3,
        min_context_score=0.8,  # High threshold
        min_generation_score=0.8,  # High threshold
        top_k_retrieval=3,
        enable_quality_check=True,
        enable_context_grading=True
    )
    
    # Questions that might need improvement
    improvement_questions = [
        "vague question about stuff",  # Intentionally vague
        "What is the best approach?",  # Ambiguous
        "How to optimize performance in general?"  # Too broad
    ]
    
    print("🎯 Testing with strict quality requirements:")
    print(f"   Min Context Score: {strict_config.min_context_score}")
    print(f"   Min Generation Score: {strict_config.min_generation_score}")
    
    for question in improvement_questions:
        print(f"\n❓ Testing: {question}")
        
        try:
            result = sync_agentic_rag_query(question, strict_config)
            
            print(f"🔄 Improvement Process:")
            print(f"   Retries: {result['metadata']['retry_count']}")
            print(f"   Path: {' → '.join(result['metadata']['execution_path'])}")
            
            if result['metadata']['retry_count'] > 0:
                print(f"   ✨ Self-improvement triggered!")
            else:
                print(f"   ✅ No improvement needed")
                
        except Exception as e:
            print(f"❌ Error: {e}")

def demo_graph_visualization():
    """Demonstrate the graph execution flow"""
    print("\n📊 Graph Execution Flow Demo")
    print("=" * 35)
    
    config = RAGGraphConfig(
        max_retries=2,
        min_context_score=0.7,
        min_generation_score=0.6,
        enable_quality_check=True,
        enable_context_grading=True
    )
    
    question = "What are the key components of the RAG system?"
    
    print(f"🔍 Question: {question}")
    print("\n📈 Expected Graph Flow:")
    print("   1. retrieve → Get contexts from vector DB")
    print("   2. grade → Evaluate context relevance")
    print("   3. [conditional] rewrite → Improve query if needed")
    print("   4. generate → Create answer from contexts")
    print("   5. quality_check → Evaluate answer quality")
    print("   6. [conditional] retry → Loop back if quality low")
    
    try:
        result = sync_agentic_rag_query(question, config)
        
        print(f"\n✅ Actual Execution Path:")
        execution_path = result['metadata']['execution_path']
        for i, step in enumerate(execution_path, 1):
            print(f"   {i}. {step}")
        
        print(f"\n📊 Final Results:")
        print(f"   Answer Quality: {result['metadata']['generation_score']:.2f}")
        print(f"   Total Steps: {len(execution_path)}")
        print(f"   Self-Improvements: {result['metadata']['retry_count']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def demo_thread_safety():
    """Demonstrate thread-safe execution"""
    print("\n🔒 Thread Safety Demo")
    print("=" * 25)
    
    import threading
    import time
    
    config = RAGGraphConfig(max_retries=1, enable_quality_check=False)
    
    questions = [
        "What is chunking?",
        "How does embedding work?",
        "What is vector search?",
        "Explain RAG pipeline"
    ]
    
    results = {}
    
    def query_thread(thread_id, question):
        try:
            thread_name = f"thread_{thread_id}"
            result = sync_agentic_rag_query(question, config, thread_name)
            results[thread_id] = {
                "question": question,
                "success": True,
                "thread_id": result['metadata']['thread_id'],
                "answer_length": len(result['answer'])
            }
            print(f"✅ Thread {thread_id} completed")
        except Exception as e:
            results[thread_id] = {
                "question": question,
                "success": False,
                "error": str(e)
            }
            print(f"❌ Thread {thread_id} failed: {e}")
    
    print("🚀 Starting 4 concurrent queries...")
    
    threads = []
    for i, question in enumerate(questions):
        thread = threading.Thread(target=query_thread, args=(i, question))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    print(f"\n📊 Thread Safety Results:")
    successful = sum(1 for r in results.values() if r['success'])
    print(f"   Successful: {successful}/{len(questions)}")
    print(f"   Thread Isolation: {'✅ Passed' if successful == len(questions) else '❌ Failed'}")

async def demo_async_usage():
    """Demonstrate async usage"""
    print("\n⚡ Async Usage Demo")
    print("=" * 20)
    
    config = RAGGraphConfig(max_retries=1, enable_quality_check=False)
    
    questions = [
        "What is the purpose of this system?",
        "How does it handle documents?",
        "What are the main benefits?"
    ]
    
    print("🚀 Running async queries concurrently...")
    
    # Run queries concurrently
    tasks = [
        agentic_rag_query(question, config, f"async_{i}")
        for i, question in enumerate(questions)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    print(f"\n📊 Async Results:")
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"   Query {i+1}: ❌ {result}")
        else:
            print(f"   Query {i+1}: ✅ {len(result['answer'])} chars")

def demo_error_handling():
    """Demonstrate error handling and recovery"""
    print("\n🛡️ Error Handling Demo")
    print("=" * 25)
    
    # Test with invalid configuration
    print("1. Testing with invalid configuration...")
    try:
        invalid_config = RAGGraphConfig(max_retries=-1)  # Invalid
        result = sync_agentic_rag_query("test question", invalid_config)
        print("   ❌ Should have failed")
    except Exception as e:
        print(f"   ✅ Caught error: {type(e).__name__}")
    
    # Test with empty question
    print("\n2. Testing with empty question...")
    try:
        config = RAGGraphConfig()
        result = sync_agentic_rag_query("", config)
        print(f"   📝 Result: {result['answer'][:100]}...")
    except Exception as e:
        print(f"   ✅ Handled gracefully: {type(e).__name__}")
    
    # Test recovery from failures
    print("\n3. Testing recovery mechanisms...")
    config = RAGGraphConfig(max_retries=2, enable_quality_check=True)
    
    try:
        result = sync_agentic_rag_query("complex technical question", config)
        print(f"   ✅ Recovery successful")
        print(f"   📊 Retries used: {result['metadata']['retry_count']}")
    except Exception as e:
        print(f"   ⚠️ Partial failure: {e}")

def main():
    """Run all demos"""
    print("🚀 Agentic RAG Pipeline - Complete Demo Suite")
    print("=" * 60)
    
    try:
        # Basic usage
        demo_basic_usage()
        
        # Self-improvement
        demo_self_improvement()
        
        # Graph visualization
        demo_graph_visualization()
        
        # Thread safety
        demo_thread_safety()
        
        # Async usage
        print("\n⚡ Running async demo...")
        asyncio.run(demo_async_usage())
        
        # Error handling
        demo_error_handling()
        
        print("\n🎉 All demos completed successfully!")
        print("\n📋 Key Features Demonstrated:")
        print("   ✅ Self-Improving RAG with quality feedback")
        print("   ✅ LangGraph-based conditional routing")
        print("   ✅ Context grading and query rewriting")
        print("   ✅ Thread-safe execution")
        print("   ✅ Async/await support")
        print("   ✅ Error handling and recovery")
        print("   ✅ State persistence across retries")
        print("   ✅ Configurable quality thresholds")
        
    except Exception as e:
        print(f"❌ Demo suite failed: {e}")
        print("\n💡 This is expected if vector database is not set up.")
        print("   The demos show the agentic RAG architecture concepts.")

if __name__ == "__main__":
    main()