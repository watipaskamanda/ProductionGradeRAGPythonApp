#!/usr/bin/env python3
"""
Test script to verify DataTable functionality
"""

import requests
import json

def test_datatable_flow():
    """Test the complete DataTable flow"""
    
    print("🧪 Testing DataTable Flow...")
    print("=" * 50)
    
    # Test data
    test_queries = [
        "How many transactions were there in July 2025?",
        "show me the table",
        "show the breakdown"
    ]
    
    base_url = "http://localhost:8000"
    endpoint = f"{base_url}/api/v1/query/database"
    
    chat_history = []
    
    for i, query in enumerate(test_queries):
        print(f"\n🔍 Test {i+1}: {query}")
        print("-" * 30)
        
        # Prepare request
        payload = {
            "question": query,
            "chat_history": chat_history,
            "currency": "MWK",
            "user_level": "business",
            "debug_mode": True
        }
        
        try:
            # Make request
            response = requests.post(endpoint, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                
                print(f"✅ Status: {response.status_code}")
                print(f"📝 Answer: {data.get('answer', 'No answer')}")
                print(f"🗃️ Has raw_data: {'Yes' if data.get('raw_data') else 'No'}")
                
                if data.get('raw_data'):
                    raw_data = data['raw_data']
                    print(f"📊 Columns: {raw_data.get('columns', [])}")
                    print(f"📈 Rows: {len(raw_data.get('rows', []))}")
                    print(f"🔢 Total: {raw_data.get('total_count', 0)}")
                
                if data.get('debug_info'):
                    print(f"🔧 SQL: {data['debug_info'].get('sql', 'No SQL')}")
                
                # Add to chat history
                chat_history.append({
                    "role": "user",
                    "content": query
                })
                chat_history.append({
                    "role": "assistant", 
                    "content": data.get('answer', ''),
                    "sql": data.get('debug_info', {}).get('sql', '')
                })
                
            else:
                print(f"❌ Status: {response.status_code}")
                print(f"📝 Error: {response.text}")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    print("\n" + "=" * 50)
    print("🏁 Test Complete!")
    print("\nExpected Results:")
    print("1. First query should return count with raw_data")
    print("2. 'show me the table' should reuse previous query")
    print("3. Frontend should render DataTable with pagination")

if __name__ == "__main__":
    test_datatable_flow()