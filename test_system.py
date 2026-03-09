#!/usr/bin/env python3
"""
Quick system test to validate the RAG + Analytics pipeline
"""

def test_imports():
    """Test if all modules can be imported"""
    try:
        print("Testing imports...")
        
        # Test basic imports first
        import os
        import json
        from pathlib import Path
        print("✅ Basic Python modules")
        
        # Test external dependencies
        try:
            import psycopg2
            print("✅ psycopg2 (PostgreSQL)")
        except ImportError:
            print("❌ psycopg2 missing - run: pip install psycopg2-binary")
            return False
            
        try:
            import pandas as pd
            print("✅ pandas")
        except ImportError:
            print("❌ pandas missing - run: pip install pandas")
            return False
            
        try:
            import requests
            print("✅ requests")
        except ImportError:
            print("❌ requests missing - run: pip install requests")
            return False
            
        # Test project modules
        try:
            import db_query
            print("✅ db_query module")
        except Exception as e:
            print(f"❌ db_query failed: {e}")
            return False
            
        try:
            import api
            print("✅ api module")
        except Exception as e:
            print(f"❌ api module failed: {e}")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def test_config():
    """Test if config files exist"""
    print("\nTesting configuration...")
    
    config_file = Path("config.json")
    if config_file.exists():
        print("✅ config.json found")
        try:
            with open(config_file) as f:
                config = json.load(f)
            print(f"✅ Config loaded: {config.get('business_name', 'Unknown')}")
        except Exception as e:
            print(f"❌ Config parse error: {e}")
            return False
    else:
        print("❌ config.json missing")
        return False
        
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file found")
    else:
        print("⚠️ .env file missing (create with GROQ_API_KEY)")
        
    return True

def test_health():
    """Test health check function"""
    print("\nTesting health check...")
    try:
        from db_query import health_check
        result = health_check()
        if result["status"] == "healthy":
            print("✅ Health check passed")
            return True
        else:
            print(f"❌ Health check failed: {result}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 BIZINEZI System Test\n")
    
    success = True
    success &= test_imports()
    success &= test_config() 
    
    if success:
        success &= test_health()
    
    print(f"\n{'✅ All tests passed!' if success else '❌ Some tests failed'}")
    print("\nNext steps:")
    if not success:
        print("1. Install missing dependencies: pip install psycopg2-binary pandas requests")
        print("2. Create .env file with GROQ_API_KEY")
        print("3. Ensure database is running")
    else:
        print("1. Start API: python api.py")
        print("2. Start UI: streamlit run chat_app.py")
        print("3. Test complete pipeline")