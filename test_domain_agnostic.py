#!/usr/bin/env python3
"""
Test script for Domain-Agnostic SQL Agent
Demonstrates how the agent adapts to different business domains
"""

import json
import sys
from pathlib import Path

# Add the project directory to Python path
sys.path.append(str(Path(__file__).parent))

from db_query import (
    load_domain_config, 
    get_universal_schema, 
    initialize_universal_agent,
    UniversalSemanticDictionary
)

def test_domain_switching():
    """Test switching between different business domains"""
    
    print("🧪 Testing Domain-Agnostic SQL Agent")
    print("=" * 50)
    
    # Test 1: Financial Services Domain (default)
    print("\n1️⃣ Testing Financial Services Domain")
    print("-" * 30)
    
    financial_config = load_domain_config()
    print(f"Business: {financial_config['business_name']}")
    print(f"Domain: {financial_config['domain_context']}")
    
    financial_semantic = UniversalSemanticDictionary(financial_config)
    print(f"Domain Terms: {len(financial_semantic.get_all_terms())}")
    print(f"Sample Terms: {list(financial_semantic.get_all_terms())[:5]}")
    
    # Test 2: Salon Domain
    print("\n2️⃣ Testing Salon Domain")
    print("-" * 30)
    
    try:
        with open("config_salon_example.json", 'r') as f:
            salon_config = json.load(f)
        
        print(f"Business: {salon_config['business_name']}")
        print(f"Domain: {salon_config['domain_context']}")
        
        salon_semantic = UniversalSemanticDictionary(salon_config)
        print(f"Domain Terms: {len(salon_semantic.get_all_terms())}")
        print(f"Sample Terms: {list(salon_semantic.get_all_terms())[:5]}")
        
        # Test term replacement
        test_query = "Show me premium services from recent appointments"
        enhanced_query = salon_semantic.replace_terms_in_text(test_query)
        print(f"Original: {test_query}")
        print(f"Enhanced: {enhanced_query}")
        
    except FileNotFoundError:
        print("❌ Salon config not found")
    
    # Test 3: Schema Discovery
    print("\n3️⃣ Testing Universal Schema Discovery")
    print("-" * 30)
    
    schema_result = get_universal_schema()
    if schema_result["success"]:
        print(f"✅ Schema discovered successfully")
        print(f"📊 Found {len(schema_result['tables'])} tables")
        for table_name in list(schema_result['tables'].keys())[:3]:
            print(f"   • {table_name}")
    else:
        print(f"❌ Schema discovery failed: {schema_result['error']}")
    
    # Test 4: Agent Initialization
    print("\n4️⃣ Testing Agent Initialization")
    print("-" * 30)
    
    try:
        init_result = initialize_universal_agent()
        print(f"✅ Agent initialized successfully")
        print(f"Business: {init_result['business_name']}")
        print(f"Domain: {init_result['domain']}")
        print(f"Tables: {init_result['tables_discovered']}")
        print(f"Terms: {init_result['domain_terms_loaded']}")
    except Exception as e:
        print(f"❌ Agent initialization failed: {e}")
    
    print("\n🎉 Domain-Agnostic Testing Complete!")
    print("The agent can now adapt to any business domain by updating config.json")

if __name__ == "__main__":
    test_domain_switching()