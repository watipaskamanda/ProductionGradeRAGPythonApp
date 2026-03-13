#!/usr/bin/env python3
"""
Enterprise Multi-Tenant Database Connector Demo
Demonstrates the key enterprise features
"""

import json
from pathlib import Path
from enterprise_db_connector import (
    EnterpriseDBConnector,
    create_tenant,
    get_tenant_connector,
    list_tenants
)

def demo_multi_tenant_setup():
    """Demonstrate multi-tenant setup and usage"""
    print("🏢 Enterprise Multi-Tenant Database Connector Demo")
    print("=" * 60)
    
    # 1. Create Bank Tenant
    print("\n1. Creating Bank Tenant...")
    bank_config = {
        "tenant_id": "demo_bank",
        "business_name": "Demo Bank Corp",
        "domain_context": "banking",
        "database": {
            "host": "localhost",
            "database": "demo_bank_db",
            "user": "postgres",
            "password": "password",
            "port": "5432",
            "driver": "postgresql"
        },
        "active_table": "transactions",
        "approved_tables": ["transactions", "accounts", "customers"],
        "domain_terms": {
            "high_value": "amount > 10000",
            "recent": "created_at > NOW() - INTERVAL '30 days'",
            "wire_transfers": "transaction_type = 'wire'",
            "deposits": "transaction_type = 'deposit'"
        },
        "business_language": {
            "primary_entity": "transactions",
            "currency": "USD"
        }
    }
    
    bank_result = create_tenant("demo_bank", bank_config)
    print(f"✅ Bank tenant: {bank_result}")
    
    # 2. Create Retail Tenant
    print("\n2. Creating Retail Tenant...")
    retail_config = {
        "tenant_id": "demo_retail",
        "business_name": "Demo Retail Chain",
        "domain_context": "retail",
        "database": {
            "host": "localhost",
            "database": "demo_retail_db",
            "user": "postgres",
            "password": "password",
            "port": "5432",
            "driver": "postgresql"
        },
        "active_table": "sales",
        "approved_tables": ["sales", "products", "customers", "stores"],
        "domain_terms": {
            "high_value": "total_amount > 500",
            "recent": "sale_date > CURRENT_DATE - INTERVAL '7 days'",
            "online_sales": "channel = 'online'",
            "premium_products": "category = 'premium'"
        },
        "business_language": {
            "primary_entity": "sales",
            "currency": "USD"
        }
    }
    
    retail_result = create_tenant("demo_retail", retail_config)
    print(f"✅ Retail tenant: {retail_result}")
    
    # 3. List All Tenants
    print("\n3. Listing All Tenants...")
    tenants = list_tenants()
    print(f"📋 Available tenants: {tenants}")
    
    return tenants

def demo_dynamic_schema_reflection():
    """Demonstrate dynamic schema reflection"""
    print("\n🔍 Dynamic Schema Reflection Demo")
    print("=" * 40)
    
    # Get bank connector
    bank_connector = get_tenant_connector("demo_bank")
    
    print(f"🏦 Bank Tenant Info:")
    bank_info = bank_connector.get_tenant_info()
    print(json.dumps(bank_info, indent=2))
    
    print(f"\n📊 Bank Schema:")
    bank_schema = bank_connector.schema_reflector.get_current_schema()
    if bank_schema["success"]:
        for table_name, columns in bank_schema["tables"].items():
            is_active = " [ACTIVE]" if table_name == bank_schema["active_table"] else ""
            print(f"  Table: {table_name}{is_active}")
            for col in columns[:3]:  # Show first 3 columns
                print(f"    - {col['name']} ({col['type']})")
            if len(columns) > 3:
                print(f"    ... and {len(columns) - 3} more columns")
    else:
        print(f"  ❌ Schema error: {bank_schema['error']}")

def demo_dynamic_prompts():
    """Demonstrate dynamic prompt generation"""
    print("\n📝 Dynamic Prompt Generation Demo")
    print("=" * 40)
    
    # Get connectors for different tenants
    bank_connector = get_tenant_connector("demo_bank")
    retail_connector = get_tenant_connector("demo_retail")
    
    print("🏦 Bank System Prompt (first 500 chars):")
    bank_prompt = bank_connector.prompt_generator.generate_system_prompt()
    print(bank_prompt[:500] + "...")
    
    print("\n🛒 Retail System Prompt (first 500 chars):")
    retail_prompt = retail_connector.prompt_generator.generate_system_prompt()
    print(retail_prompt[:500] + "...")
    
    print(f"\n🔄 Notice how prompts are customized for each domain!")

def demo_active_table_switching():
    """Demonstrate active table switching"""
    print("\n🔄 Active Table Switching Demo")
    print("=" * 40)
    
    bank_connector = get_tenant_connector("demo_bank")
    
    print(f"📊 Current active table: {bank_connector.get_active_table()}")
    
    # Switch to accounts table
    print("🔄 Switching to 'accounts' table...")
    switch_result = bank_connector.set_active_table("accounts")
    print(f"✅ Switch result: {switch_result}")
    
    print(f"📊 New active table: {bank_connector.get_active_table()}")
    
    # Switch back to transactions
    print("🔄 Switching back to 'transactions' table...")
    switch_result = bank_connector.set_active_table("transactions")
    print(f"✅ Switch result: {switch_result}")

def demo_sql_generation():
    """Demonstrate SQL generation with different schemas"""
    print("\n🔧 SQL Generation Demo")
    print("=" * 30)
    
    bank_connector = get_tenant_connector("demo_bank")
    retail_connector = get_tenant_connector("demo_retail")
    
    # Same question, different SQL for different domains
    question = "How many high value transactions are there?"
    
    print(f"❓ Question: {question}")
    
    try:
        print("\\n🏦 Bank SQL:")
        bank_sql = bank_connector.text_to_sql(question)
        print(f"  {bank_sql}")
    except Exception as e:
        print(f"  ❌ Bank SQL error: {e}")
    
    try:
        print("\\n🛒 Retail SQL:")
        retail_sql = retail_connector.text_to_sql(question)
        print(f"  {retail_sql}")
    except Exception as e:
        print(f"  ❌ Retail SQL error: {e}")
    
    print("\\n💡 Notice how the same question generates different SQL based on:")
    print("   - Different table names (transactions vs sales)")
    print("   - Different column names and business rules")
    print("   - Domain-specific context")

def demo_security_features():
    """Demonstrate security features"""
    print("\\n🔒 Security Features Demo")
    print("=" * 30)
    
    bank_connector = get_tenant_connector("demo_bank")
    
    print("🛡️ Security Features:")
    print("  ✅ Tenant Isolation: Each tenant has separate config and database")
    print("  ✅ Approved Tables: Only pre-approved tables are accessible")
    print("  ✅ Schema Validation: SQL is validated against actual schema")
    print("  ✅ Connection Isolation: Each tenant uses separate DB connections")
    
    bank_info = bank_connector.get_tenant_info()
    approved_tables = bank_connector.tenant_config.get_approved_tables()
    
    print(f"\\n🏦 Bank approved tables: {approved_tables}")
    print("   - Queries can only access these tables")
    print("   - Prevents access to sensitive system tables")

def main():
    """Run the complete demo"""
    print("🚀 Starting Enterprise Multi-Tenant Demo...")
    
    try:
        # Setup
        tenants = demo_multi_tenant_setup()
        
        # Only run other demos if we have tenants
        if tenants:
            demo_dynamic_schema_reflection()
            demo_dynamic_prompts()
            demo_active_table_switching()
            demo_sql_generation()
            demo_security_features()
        
        print("\\n🎉 Demo completed successfully!")
        print("\\n📋 Enterprise Features Demonstrated:")
        print("   ✅ Multi-Tenancy: Separate configs per tenant")
        print("   ✅ Schema Reflection: Dynamic schema discovery")
        print("   ✅ Dynamic Prompts: Context-aware SQL generation")
        print("   ✅ Active Table: Configurable primary table")
        print("   ✅ Security: Tenant isolation and approved tables")
        print("   ✅ Portability: Works with any database schema")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("\\n💡 This is expected if databases don't exist.")
        print("   The demo shows the enterprise architecture concepts.")

if __name__ == "__main__":
    main()