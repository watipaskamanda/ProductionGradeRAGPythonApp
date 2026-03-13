#!/usr/bin/env python3
"""
Quick test script to verify the installation and API functionality
"""

import sys
import os
from pathlib import Path

# Configure sentence transformers cache directory before any imports
os.environ['SENTENCE_TRANSFORMERS_HOME'] = './models'

def test_imports():
    """Test if all required modules can be imported"""
    print("🧪 Testing imports...")
    
    required_modules = [
        ('fastapi', 'FastAPI'),
        ('uvicorn', 'Uvicorn'),
        ('groq', 'Groq'),
        ('sentence_transformers', 'SentenceTransformers'),
        ('qdrant_client', 'Qdrant Client'),
        ('psycopg2', 'PostgreSQL adapter'),
        ('sqlalchemy', 'SQLAlchemy'),
        ('pydantic', 'Pydantic')
    ]
    
    optional_modules = [
        ('llama_index.core', 'LlamaIndex Core'),
        ('llama_index.readers.file', 'LlamaIndex PDF Reader'),
        ('langgraph', 'LangGraph'),
        ('langchain_core', 'LangChain Core')
    ]
    
    success_count = 0
    
    # Test required modules
    for module_name, display_name in required_modules:
        try:
            __import__(module_name)
            print(f"  ✅ {display_name}")
            success_count += 1
        except ImportError as e:
            print(f"  ❌ {display_name}: {e}")
    
    # Test optional modules
    print("\n🔧 Testing optional modules...")
    for module_name, display_name in optional_modules:
        try:
            __import__(module_name)
            print(f"  ✅ {display_name}")
        except ImportError:
            print(f"  ⚠️ {display_name}: Not available (optional)")
    
    print(f"\n📊 Required modules: {success_count}/{len(required_modules)} installed")
    return success_count == len(required_modules)

def test_environment():
    """Test environment configuration"""
    print("\n🌍 Testing environment...")
    
    # Check for .env file
    env_file = Path(".env")
    if env_file.exists():
        print("  ✅ .env file found")
        
        # Check for required environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            print("  ✅ GROQ_API_KEY configured")
        else:
            print("  ⚠️ GROQ_API_KEY not found in .env")
            
    else:
        print("  ⚠️ .env file not found")
        print("     Create .env file with: GROQ_API_KEY=your_key_here")

def test_api_imports():
    """Test if the API modules can be imported"""
    print("\n🚀 Testing API modules...")
    
    try:
        # Test data_loader
        from data_loader import embed_texts
        print("  ✅ data_loader module")
    except ImportError as e:
        print(f"  ❌ data_loader module: {e}")
    
    try:
        # Test vector_db
        from vector_db import QdrantStorage
        print("  ✅ vector_db module")
    except ImportError as e:
        print(f"  ❌ vector_db module: {e}")
    
    try:
        # Test agentic_rag (should work even without LangGraph)
        from agentic_rag import RAGGraphConfig
        print("  ✅ agentic_rag module")
    except ImportError as e:
        print(f"  ❌ agentic_rag module: {e}")
    
    try:
        # Test enterprise_db_connector
        from enterprise_db_connector import EnterpriseDBConnector
        print("  ✅ enterprise_db_connector module")
    except ImportError as e:
        print(f"  ❌ enterprise_db_connector module: {e}")
    
    try:
        # Test main API
        from api import app
        print("  ✅ api module")
        return True
    except ImportError as e:
        print(f"  ❌ api module: {e}")
        return False

def test_basic_functionality():
    """Test basic functionality"""
    print("\n⚡ Testing basic functionality...")
    
    try:
        # Test sentence transformers
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        test_embedding = model.encode(["test sentence"])
        print(f"  ✅ Sentence embedding: {len(test_embedding[0])} dimensions")
    except Exception as e:
        print(f"  ❌ Sentence embedding failed: {e}")
    
    try:
        # Test Groq client (if API key available)
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            from groq import Groq
            client = Groq(api_key=groq_key)
            print("  ✅ Groq client initialized")
        else:
            print("  ⚠️ Groq client: No API key available")
    except Exception as e:
        print(f"  ❌ Groq client failed: {e}")

def main():
    """Run all tests"""
    print("🧪 Enterprise RAG System - Installation Test")
    print("=" * 50)
    
    # Test imports
    imports_ok = test_imports()
    
    # Test environment
    test_environment()
    
    # Test API imports
    api_ok = test_api_imports()
    
    # Test basic functionality
    test_basic_functionality()
    
    # Summary
    print("\n" + "=" * 50)
    if imports_ok and api_ok:
        print("🎉 Installation test PASSED!")
        print("\n✅ You can now start the backend with:")
        print("   python start_backend.py")
        print("\n✅ Or use the batch file:")
        print("   start_backend.bat")
    else:
        print("❌ Installation test FAILED!")
        print("\n💡 Try running:")
        print("   install_dependencies.bat")
        print("\n💡 Or manually install missing packages:")
        print("   pip install -r requirements.txt")
    
    return imports_ok and api_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)