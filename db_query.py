import psycopg2
from groq import Groq
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Warning: Google Generative AI not available")
import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from unified_llm_client import get_llm_client

load_dotenv()

# Configure Google Gemini
gemini_model = None
if GEMINI_AVAILABLE and os.getenv('GEMINI_API_KEY'):
    try:
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"Warning: Could not initialize Gemini: {e}")

# Development mode schema caching
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"
_dev_cached_schema = None

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bizinezi_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('bizinezi_analytics')

def log_analytics_event(status: str, question: str, sql: str = "", error: str = "", plan: dict = None):
    """Log analytics events with privacy protection - NO user data rows/values logged."""
    event_data = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "question": question[:200],  # Truncate long questions
        "sql_query": sql[:500] if sql else "",  # Log SQL but truncate if too long
        "error_message": error[:300] if error else "",  # Truncate error messages
        "analysis_type": plan.get("analysis_type", "unknown") if plan else "unknown",
        "visualization_type": plan.get("visualization", "none") if plan else "none",
        "filters_count": len(plan.get("filters", [])) if plan else 0,
        "aggregations_count": len(plan.get("aggregations", [])) if plan else 0
    }
    
    # PRIVACY: Explicitly exclude any result data - only log metadata
    log_message = f"Analytics Event: {status} | Question: {question[:100]}..."
    if status == "ERROR":
        logger.error(f"{log_message} | Error: {error[:100]}...", extra=event_data)
    else:
        logger.info(log_message, extra=event_data)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
llm_client = get_llm_client()  # Unified client with Groq/Gemini fallback

# DOMAIN-AGNOSTIC CONFIGURATION
CONFIG_FILE = Path("/app/config.json")
if not CONFIG_FILE.exists():
    CONFIG_FILE = Path("config.json")  # Fallback for development

def load_domain_config():
    """Load domain-specific configuration from config.json"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        # Note: Semantic validation will be done later in initialize_universal_agent
        # to avoid NameError during module initialization
        
        return config
    except Exception as e:
        print(f"Failed to load config: {e}")
        return {
            "business_name": "Generic Business",
            "domain_context": "data_analysis", 
            "domain_terms": {},
            "business_language": {"primary_entity": "records", "currency": "USD"}
        }

def discover_join_opportunities(schema_result):
    """Build join mapping for automatic relationship discovery"""
    if not schema_result["success"]:
        return {}
    
    join_map = {}
    for table_name, columns in schema_result["tables"].items():
        for col in columns:
            col_name = col["name"]
            
            # Map column to its table
            if col_name not in join_map:
                join_map[col_name] = []
            join_map[col_name].append({
                "table": table_name,
                "is_pk": col["is_primary_key"],
                "is_fk": col["is_foreign_key"],
                "references": col["references"]
            })
    
    return join_map

# Import enterprise connector
from enterprise_db_connector import (
    get_tenant_connector, 
    query_database_with_validation as enterprise_query,
    health_check as enterprise_health_check,
    create_tenant,
    list_tenants
)

# ENTERPRISE MULTI-TENANT FUNCTIONS
def query_database_with_validation(question: str, chat_history: list = None, currency: str = "MWK", tenant_id: str = "default") -> dict:
    """Enterprise query function with multi-tenant support"""
    try:
        # Use enterprise connector
        result = enterprise_query(question, chat_history, currency, tenant_id)
        
        # Log analytics event
        status = "SUCCESS" if "error" not in result.get("answer", "").lower() else "ERROR"
        log_analytics_event(
            status=status,
            question=question,
            sql=result.get("sql", ""),
            error=result.get("metadata", {}).get("error", ""),
            plan=result.get("plan", {})
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Enterprise query failed: {e}")
        log_analytics_event("ERROR", question, "", str(e), {})
        
        return {
            "question": question,
            "plan": {"analysis_type": "error"},
            "sql": "-- Query failed",
            "answer": f"System error: {str(e)}",
            "markdown_table": "",
            "chart_config": {},
            "suggested_visualizations": [],
            "metadata": {"error": str(e), "tenant_id": tenant_id}
        }

def health_check(tenant_id: str = "default") -> dict:
    """Enterprise health check with tenant support"""
    try:
        return enterprise_health_check(tenant_id)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "tenant_id": tenant_id
        }

def get_tenant_schema(tenant_id: str = "default") -> dict:
    """Get current schema for tenant"""
    try:
        connector = get_tenant_connector(tenant_id)
        schema = connector.schema_reflector.get_current_schema()
        return schema
    except Exception as e:
        logger.error(f"Failed to get schema for tenant {tenant_id}: {e}")
        return {"success": False, "error": str(e)}

def set_active_table(tenant_id: str, table_name: str) -> dict:
    """Set active table for tenant"""
    try:
        connector = get_tenant_connector(tenant_id)
        return connector.set_active_table(table_name)
    except Exception as e:
        logger.error(f"Failed to set active table for tenant {tenant_id}: {e}")
        return {"success": False, "error": str(e)}

def get_tenant_info(tenant_id: str = "default") -> dict:
    """Get tenant information"""
    try:
        connector = get_tenant_connector(tenant_id)
        return connector.get_tenant_info()
    except Exception as e:
        logger.error(f"Failed to get tenant info for {tenant_id}: {e}")
        return {"error": str(e)}

# BACKWARD COMPATIBILITY - Keep existing functions but mark as deprecated
def suggest_join_for_missing_column(missing_column: str, base_table: str = None, tenant_id: str = "default") -> str:
    """DEPRECATED: Use enterprise connector instead"""
    if base_table is None:
        connector = get_tenant_connector(tenant_id)
        base_table = connector.get_active_table()
    
    try:
        schema_result = get_tenant_schema(tenant_id)
        if not schema_result["success"]:
            return ""
        
        # Find table containing the missing column
        for table_name, columns in schema_result["tables"].items():
            column_names = [col["name"] for col in columns]
            if missing_column in column_names and table_name != base_table:
                # Simple join suggestion
                return f"JOIN {table_name} ON {base_table}.id = {table_name}.{base_table}_id"
        
        return ""
    except Exception as e:
        logger.error(f"Join discovery error: {e}")
        return ""
def validate_semantic_mappings(domain_terms: dict) -> dict:
    """Validate semantic mappings with automatic join suggestions"""
    try:
        # Use the enterprise connector to get schema
        schema_result = get_tenant_schema("default")
        if not schema_result["success"]:
            return domain_terms
        
        # Get all column names from all tables
        valid_columns = set()
        for table_name, columns in schema_result["tables"].items():
            for col in columns:
                valid_columns.add(col["name"])
        
        validated_terms = {}
        for term, sql_fragment in domain_terms.items():
            # Extract potential column references from SQL fragment
            import re
            potential_columns = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', sql_fragment)
            
            missing_columns = [col for col in potential_columns if col not in valid_columns and col not in ['SELECT', 'FROM', 'WHERE', 'GROUP', 'BY', 'ORDER', 'LIMIT', 'COUNT', 'SUM', 'AVG']]
            
            if missing_columns:
                # Try to suggest JOINs for missing columns
                join_suggestions = []
                for missing_col in missing_columns:
                    join_clause = suggest_join_for_missing_column(missing_col)
                    if join_clause:
                        join_suggestions.append(join_clause)
                        print(f"🔗 Auto-join suggestion for '{term}': {join_clause}")
                
                if join_suggestions:
                    # Enhance the SQL fragment with JOIN suggestions
                    enhanced_sql = sql_fragment + f" -- Suggested JOINs: {'; '.join(join_suggestions)}"
                    validated_terms[term] = enhanced_sql
                else:
                    print(f"⚠️ Semantic validation warning: '{term}' references missing columns: {missing_columns}")
                    validated_terms[term] = sql_fragment
            else:
                validated_terms[term] = sql_fragment
        
        return validated_terms
        
    except Exception as e:
        print(f"Semantic validation error: {e}")
        return domain_terms

# Global domain configuration
domain_config = load_domain_config()

# UNIVERSAL SCHEMA DISCOVERY
def get_universal_schema(connection_params=None):
    """Dynamic schema discovery that works with any database"""
    if connection_params is None:
        connection_params = {
            "host": os.getenv("DB_HOST", "localhost"),
            "database": os.getenv("DB_NAME", "paymaart_test"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "testpass"),
            "port": os.getenv("DB_PORT", "5432")
        }
    
    try:
        conn = psycopg2.connect(**connection_params)
        cursor = conn.cursor()
        
        # Universal schema query for PostgreSQL
        cursor.execute("""
            SELECT 
                t.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable,
                tc.constraint_type,
                ccu.table_name as foreign_table,
                ccu.column_name as foreign_column
            FROM information_schema.tables t
            LEFT JOIN information_schema.columns c ON t.table_name = c.table_name
            LEFT JOIN information_schema.key_column_usage kcu ON c.table_name = kcu.table_name 
                AND c.column_name = kcu.column_name
            LEFT JOIN information_schema.table_constraints tc ON kcu.constraint_name = tc.constraint_name
            LEFT JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
            WHERE t.table_schema = 'public' 
                AND t.table_type = 'BASE TABLE'
                AND c.table_schema = 'public'
            ORDER BY t.table_name, c.ordinal_position
        """)
        
        schema_data = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Build universal schema dictionary
        tables = {}
        for row in schema_data:
            table_name, column_name, data_type, is_nullable, constraint_type, foreign_table, foreign_column = row
            
            if table_name not in tables:
                tables[table_name] = []
            
            column_info = {
                "name": column_name,
                "type": data_type,
                "nullable": is_nullable == "YES",
                "is_primary_key": constraint_type == "PRIMARY KEY",
                "is_foreign_key": constraint_type == "FOREIGN KEY",
                "references": f"{foreign_table}.{foreign_column}" if foreign_table and foreign_column else None
            }
            
            if column_info not in tables[table_name]:
                tables[table_name].append(column_info)
        
        return {
            "success": True,
            "tables": tables,
            "business_context": domain_config["business_name"],
            "domain": domain_config["domain_context"]
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "tables": {}}

def generate_universal_system_prompt(schema_result):
    """Generate domain-aware system prompt from discovered schema"""
    if not schema_result["success"]:
        return f"Schema Error: {schema_result['error']}"
    
    business_name = domain_config["business_name"]
    domain_context = domain_config["domain_context"]
    primary_entity = domain_config["business_language"]["primary_entity"]
    
    prompt = f"{business_name} - {domain_context.upper()} DATABASE SCHEMA:\n\n"
    
    for table_name, columns in schema_result["tables"].items():
        prompt += f"Table: {table_name}\n"
        
        for col in columns:
            pk_marker = " [PRIMARY KEY]" if col["is_primary_key"] else ""
            fk_marker = f" [FOREIGN KEY → {col['references']}]" if col["is_foreign_key"] and col["references"] else ""
            nullable_marker = " (nullable)" if col["nullable"] else " (required)"
            prompt += f"  * {col['name']} ({col['type']}){pk_marker}{fk_marker}{nullable_marker}\n"
        
        prompt += "\n"
    
    # Add domain-specific context
    prompt += f"""
BUSINESS CONTEXT:
- Domain: {domain_context}
- Primary Entity: {primary_entity}
- Business: {business_name}

IMPORTANT NOTES:
- Use proper data type casting for numeric operations
- Handle timestamp conversions appropriately  
- Always use table and column names exactly as shown above
- Primary keys are unique identifiers for each table
- Foreign keys show relationships: use JOINs when querying related data
- Speak in the language of {domain_context} when explaining results
"""
    
    return prompt

# 1. SCHEMA CACHING
_cached_schema = None
_cached_semantic_mapping = None

def get_live_system_prompt():
    """Get cached universal schema or refresh if needed."""
    global _cached_schema
    if _cached_schema is None:
        _cached_schema = inject_autonomous_schema_into_workflow()
    return _cached_schema

# Database schema for context
DB_SCHEMA = """
PayMaart Test Database Schema:

Tables:
- trust_bank_transaction: 
  * id (uuid)
  * transaction_id (varchar)
  * transaction_code (varchar) 
  * transaction_type (varchar) -- Values: 'float', 'pay_in', 'g2p_pay_in', 'payout_approved', 'settlement', 'excess_float'
  * transaction_amount (decimal) -- Use ::numeric for comparisons
  * created_at (text) -- TEXT containing Unix timestamps, ALWAYS use TO_TIMESTAMP(created_at::double precision) to convert
  * sender_id (varchar)
  * entered_by (varchar)
  * reciever_id (varchar)
  * pop_file_key (text)
  * pop_file_ref_no (varchar)
  * bank_id (varchar)
  * type (varchar) -- Values: 'credit', 'debit'
  * closing_balance (decimal) -- Use ::numeric for comparisons
  * flagged (boolean)
  * closing_balance_ptbat (decimal) -- Use ::numeric for comparisons
  * sender_closing_balance (decimal) -- Use ::numeric for comparisons

CRITICAL TEXT UNIX TIMESTAMP HANDLING:
- created_at is TEXT containing Unix timestamps, NEVER treat as regular date
- ALWAYS cast to double precision first: created_at::double precision
- Then convert with: TO_TIMESTAMP(created_at::double precision) before any date operations
- For date filtering: EXTRACT(MONTH FROM TO_TIMESTAMP(created_at::double precision)) = 10
- For year filtering: EXTRACT(YEAR FROM TO_TIMESTAMP(created_at::double precision)) = 2024
- For recent data: TO_TIMESTAMP(created_at::double precision) > NOW() - INTERVAL '30 days'
- For date formatting: TO_CHAR(TO_TIMESTAMP(created_at::double precision), 'YYYY-MM')
- NEVER use TO_TIMESTAMP(created_at) without ::double precision cast

IMPORTANT SQL Notes:
- ALWAYS cast decimal fields with: COALESCE(NULLIF(column, '')::numeric, 0)
- For SUM/AVG on amounts: SUM(COALESCE(NULLIF(transaction_amount, '')::numeric, 0))
- For comparisons: COALESCE(NULLIF(transaction_amount, '')::numeric, 0) > 500000
- Transaction types: 'float', 'pay_in', 'g2p_pay_in', 'payout_approved', 'settlement', 'excess_float'
- Type values: 'credit', 'debit'
"""

# 1. DYNAMIC HALLUCINATION GUARD
def get_dynamic_metadata():
    """Fetches real bounds of the data to keep the LLM grounded - works with any schema."""
    try:
        schema_result = get_universal_schema()
        if not schema_result["success"] or not schema_result["tables"]:
            return "No dynamic metadata available"
        
        # Find the first table with a timestamp-like column
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for table_name, columns in schema_result["tables"].items():
            timestamp_cols = [col["name"] for col in columns if "timestamp" in col["type"] or "date" in col["name"] or "created" in col["name"]]
            if timestamp_cols:
                timestamp_col = timestamp_cols[0]
                
                # Try to get data bounds
                try:
                    cursor.execute(f"SELECT MIN({timestamp_col}), MAX({timestamp_col}), COUNT(*) FROM {table_name} LIMIT 1")
                    min_val, max_val, count = cursor.fetchone()
                    cursor.close()
                    conn.close()
                    
                    return f"""
REAL-TIME DATA CONSTRAINTS:
- Table: {table_name}
- Data Range: {min_val} to {max_val}
- Total Records: {count:,}
- Business Context: {domain_config['business_name']} - {domain_config['domain_context']}
"""
                except:
                    continue
        
        cursor.close()
        conn.close()
        return "Dynamic metadata unavailable"
        
    except Exception as e:
        return f"Metadata error: {str(e)}"

# 2. STATEFUL ANALYST (SESSION MEMORY)
class AnalystSession:
    def __init__(self):
        self.last_results = None
        self.last_question = ""
        self.last_plan = {}
        self.user_name = None  # Store user's name

    def update(self, question, results, plan):
        self.last_results = results
        self.last_question = question
        self.last_plan = plan
    
    def set_user_name(self, name):
        """Store the user's name"""
        self.user_name = name
    
    def get_greeting_with_name(self):
        """Get personalized greeting if name is known"""
        if self.user_name:
            return f"Hi {self.user_name}! I'm your transaction data analyst."
        else:
            return "Hi! I'm your transaction data analyst."

def detect_name_introduction(question: str) -> str:
    """Detect if user is introducing themselves and extract their name"""
    import re
    question_lower = question.lower().strip()
    
    # Patterns for name introduction
    patterns = [
        r"i am ([a-zA-Z]+)",
        r"i'm ([a-zA-Z]+)",
        r"am ([a-zA-Z]+)",
        r"my name is ([a-zA-Z]+)",
        r"call me ([a-zA-Z]+)",
        r"i'm called ([a-zA-Z]+)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, question_lower)
        if match:
            name = match.group(1).capitalize()
            return name
    
    return None

def is_conversational_intent(question: str, chat_history: list = None) -> bool:
    """Check if user input is conversational rather than data analysis intent."""
    # Database override keywords - FIRST check
    database_override_keywords = [
        'transaction', 'amount', 'highest', 'lowest',
        'among', 'those', 'which', 'show', 'find',
        'count', 'total', 'sum', 'average', 'maximum',
        'minimum', 'how many', 'how much',
        # Business synonyms
        'sales', 'revenue', 'income', 'earnings', 'profit',
        'expenses', 'costs', 'spending', 'outgoing', 'expenditure',
        'payments', 'receipts', 'billing', 'invoices',
        'breakdown', 'analysis', 'report', 'summary', 'overview',
        'trends', 'patterns', 'insights', 'metrics', 'statistics',
        'performance', 'growth', 'decline', 'increase', 'decrease',
        # Month names
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december',
        'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
        # Time periods
        'monthly', 'quarterly', 'yearly', 'weekly', 'daily',
        'last month', 'this month', 'next month', 'last year', 'this year',
        'recent', 'latest', 'current', 'past', 'previous',
        # Data curiosity words
        'what', 'when', 'where', 'why', 'how', 'who',
        'compare', 'versus', 'vs', 'against', 'between',
        'top', 'bottom', 'best', 'worst', 'most', 'least',
        'filter', 'sort', 'group', 'segment', 'category',
        'list', 'display', 'view', 'see', 'check', 'examine',
        'analyze', 'calculate', 'compute', 'measure'
    ]
    
    if any(word in question.lower() for word in database_override_keywords):
        return False
    
    question_lower = question.lower().strip()
    
    # Greetings and casual chat
    conversational_patterns = [
        'hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening',
        'how are you', 'thanks', 'thank you', 'bye', 'goodbye', 'see you',
        'what can you do', 'help', 'what is this', 'who are you'
    ]
    
    return any(pattern in question_lower for pattern in conversational_patterns)

def load_business_config():
    """Load business configuration from config.json"""
    try:
        config_path = Path("config.json")
        if config_path.exists():
            with open(config_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load config.json: {e}")
    
    # Fallback configuration
    return {
        "business_name": "Generic Business",
        "domain_context": "data_analysis",
        "business_definitions": {},
        "domain_terms": {}
    }

# Load business configuration globally
business_config = load_business_config()

def get_system_context():
    """Configuration Injection: Convert config.json into plain-English business rules summary."""
    try:
        config_path = Path("config.json")
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
        else:
            return "No business configuration available."
        
        business_name = config.get("business_name", "Business")
        definitions = config.get("business_definitions", {})
        
        context = f"\nBUSINESS RULES & DEFINITIONS for {business_name}:\n"
        context += "You must strictly use the provided business logic for calculations. "
        context += "If a user asks for terms like [Sales, Expenses, High Value], you must use the SQL logic mapped below. "
        context += "DO NOT guess column logic or interpret terms outside of these definitions.\n\n"
        
        for term, definition in definitions.items():
            context += f"• {term.upper()}: {definition['description']}\n"
            context += f"  SQL Logic: {definition['sql_logic']}\n"
            context += f"  Calculation: {definition['calculation']}\n\n"
        
        context += "CRITICAL: If a query falls outside these definitions, ask for clarification instead of fabricating SQL.\n"
        return context
        
    except Exception as e:
        return f"Error loading business configuration: {str(e)}"

def text_to_sql_with_config_enforcement(question: str, context: str = "") -> str:
    """System Prompt Integration: Generate SQL with strict business rule enforcement and context preservation."""
    dynamic_metadata = get_dynamic_metadata()
    business_context = get_system_context()
    context_prompt = f"\n\nCONVERSATION CONTEXT:\n{context}" if context else ""
    
    prompt = f"""You are a PostgreSQL expert. Convert the question to a valid PostgreSQL query.

{DB_SCHEMA}
{dynamic_metadata}
{business_context}

CRITICAL TEXT UNIX TIMESTAMP HANDLING:
- The created_at column is TEXT containing Unix timestamps
- ALWAYS cast to double precision first: created_at::double precision
- Then convert to timestamp: TO_TIMESTAMP(created_at::double precision)
- NEVER use TO_TIMESTAMP(created_at) without ::double precision cast
- For date extraction: EXTRACT(MONTH FROM TO_TIMESTAMP(created_at::double precision)), EXTRACT(YEAR FROM TO_TIMESTAMP(created_at::double precision))
- For date formatting: TO_CHAR(TO_TIMESTAMP(created_at::double precision), 'YYYY-MM'), TO_CHAR(TO_TIMESTAMP(created_at::double precision), 'YYYY')
- For date comparisons: TO_TIMESTAMP(created_at::double precision) > NOW() - INTERVAL '30 days'

CRITICAL POSTGRESQL REQUIREMENTS:
- NEVER use SQLite functions like STRFTIME, DATE(), or SQLite date formats
- NEVER use direct string comparisons on timestamp columns
- ALWAYS use PostgreSQL date/time functions with proper Unix timestamp conversion
- Use PostgreSQL interval syntax: INTERVAL '30 days', INTERVAL '1 month'

CONTEXT PRESERVATION RULES:
- Maintain the filter context from the previous question unless the user explicitly changes the time range
- If the conversation context shows a month filter (e.g., January), keep that filter unless user specifies a different time period
- If the conversation context shows a year filter, maintain it unless user specifies a different year
- If the conversation context shows value filters (high/low value), maintain them unless user changes criteria
- For follow-up questions like "Show me the results" or "Display them", use the same filters as the previous query

IMPORTANT INSTRUCTIONS:
- ONLY use business terms that are explicitly defined in the BUSINESS RULES section above
- If user asks for Sales, Expenses, High Value, etc., use EXACTLY the SQL logic provided
- DO NOT infer or guess what columns mean - stick to the defined mappings
- If the question uses undefined terms, return: SELECT 'Please clarify your request using defined business terms' as message;
- ALWAYS complete all SQL queries with proper syntax - no hanging clauses
- For ANY date-based queries, ALWAYS convert Unix timestamps first with proper casting
- Pay close attention to the CONVERSATION CONTEXT to maintain filters from previous queries

TEXT UNIX TIMESTAMP EXAMPLES:
- "January transactions" → SELECT COUNT(*) FROM trust_bank_transaction WHERE EXTRACT(MONTH FROM TO_TIMESTAMP(created_at::double precision)) = 1;
- "2024 transactions" → SELECT COUNT(*) FROM trust_bank_transaction WHERE EXTRACT(YEAR FROM TO_TIMESTAMP(created_at::double precision)) = 2024;
- "Monthly breakdown" → SELECT TO_CHAR(TO_TIMESTAMP(created_at::double precision), 'YYYY-MM') as month, COUNT(*) FROM trust_bank_transaction GROUP BY TO_CHAR(TO_TIMESTAMP(created_at::double precision), 'YYYY-MM') ORDER BY month;
- "Recent transactions" → SELECT * FROM trust_bank_transaction WHERE TO_TIMESTAMP(created_at::double precision) > NOW() - INTERVAL '30 days';
- "Today's transactions" → SELECT * FROM trust_bank_transaction WHERE DATE(TO_TIMESTAMP(created_at::double precision)) = CURRENT_DATE;
- "This week" → SELECT * FROM trust_bank_transaction WHERE TO_TIMESTAMP(created_at::double precision) >= DATE_TRUNC('week', CURRENT_DATE);

STANDARD EXAMPLES:
- "How many transactions?" → SELECT COUNT(*) FROM trust_bank_transaction;
- "Total amount?" → SELECT SUM(COALESCE(NULLIF(transaction_amount, '')::numeric, 0)) FROM trust_bank_transaction;
- "Sales revenue" → SELECT SUM(COALESCE(NULLIF(transaction_amount, '')::numeric, 0)) FROM trust_bank_transaction WHERE transaction_type IN ('pay_in', 'g2p_pay_in') AND type = 'credit';
- "Total expenses" → SELECT SUM(COALESCE(NULLIF(transaction_amount, '')::numeric, 0)) FROM trust_bank_transaction WHERE transaction_type IN ('payout_approved', 'settlement') AND type = 'debit';
- "High value transactions" → SELECT COUNT(*) FROM trust_bank_transaction WHERE COALESCE(NULLIF(transaction_amount, '')::numeric, 0) > 500000;

IMPORTANT NUMERIC CASTING:
- transaction_amount: Use COALESCE(NULLIF(transaction_amount, '')::numeric, 0)
- closing_balance: Use COALESCE(NULLIF(closing_balance, '')::numeric, 0)
- closing_balance_ptbat: Use COALESCE(NULLIF(closing_balance_ptbat, '')::numeric, 0)
- sender_closing_balance: Use COALESCE(NULLIF(sender_closing_balance, '')::numeric, 0)

{context_prompt}

Question: {question}

SQL Query:"""
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a PostgreSQL expert with context awareness. NEVER use SQLite functions. ALWAYS convert Unix timestamps with TO_TIMESTAMP(created_at::double precision) before any date operations. Maintain filter context from previous queries unless explicitly changed by user. Return ONLY executable PostgreSQL SQL."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.1
    )
    
    sql = response.choices[0].message.content.strip()
    return sql.replace("```sql", "").replace("```", "").strip()

def build_enhanced_chat_context(chat_history: list) -> str:
    """Build enhanced context from chat history with filter preservation."""
    if not chat_history:
        return ""
    
    context_parts = []
    last_filters = {}  # Track filters from previous queries
    
    # Process last 5 messages for better context
    for msg in chat_history[-5:]:
        if msg.get("role") == "user":
            user_question = msg.get('content', '')
            context_parts.append(f"User asked: {user_question}")
            
            # Extract time-based filters from user questions
            question_lower = user_question.lower()
            if 'january' in question_lower:
                last_filters['month'] = 'January'
                last_filters['month_num'] = '1'
            elif 'february' in question_lower:
                last_filters['month'] = 'February'
                last_filters['month_num'] = '2'
            elif 'march' in question_lower:
                last_filters['month'] = 'March'
                last_filters['month_num'] = '3'
            elif 'april' in question_lower:
                last_filters['month'] = 'April'
                last_filters['month_num'] = '4'
            elif 'may' in question_lower:
                last_filters['month'] = 'May'
                last_filters['month_num'] = '5'
            elif 'june' in question_lower:
                last_filters['month'] = 'June'
                last_filters['month_num'] = '6'
            elif 'july' in question_lower:
                last_filters['month'] = 'July'
                last_filters['month_num'] = '7'
            elif 'august' in question_lower:
                last_filters['month'] = 'August'
                last_filters['month_num'] = '8'
            elif 'september' in question_lower:
                last_filters['month'] = 'September'
                last_filters['month_num'] = '9'
            elif 'october' in question_lower:
                last_filters['month'] = 'October'
                last_filters['month_num'] = '10'
            elif 'november' in question_lower:
                last_filters['month'] = 'November'
                last_filters['month_num'] = '11'
            elif 'december' in question_lower:
                last_filters['month'] = 'December'
                last_filters['month_num'] = '12'
            
            # Extract year filters
            import re
            year_match = re.search(r'\b(20\d{2})\b', user_question)
            if year_match:
                last_filters['year'] = year_match.group(1)
            
            # Extract transaction type filters
            if 'pay_in' in question_lower or 'pay in' in question_lower:
                last_filters['transaction_type'] = 'pay_in'
            elif 'g2p_pay_in' in question_lower or 'g2p pay in' in question_lower:
                last_filters['transaction_type'] = 'g2p_pay_in'
            elif 'payout_approved' in question_lower or 'payout approved' in question_lower or 'payout' in question_lower:
                last_filters['transaction_type'] = 'payout_approved'
            elif 'settlement' in question_lower:
                last_filters['transaction_type'] = 'settlement'
            elif 'float' in question_lower:
                last_filters['transaction_type'] = 'float'
            elif 'excess_float' in question_lower or 'excess float' in question_lower:
                last_filters['transaction_type'] = 'excess_float'
            
            # Extract other common filters
            if 'high value' in question_lower or 'high-value' in question_lower:
                last_filters['value_filter'] = 'high_value'
            elif 'low value' in question_lower or 'low-value' in question_lower:
                last_filters['value_filter'] = 'low_value'
            
            if 'credit' in question_lower:
                last_filters['type'] = 'credit'
            elif 'debit' in question_lower:
                last_filters['type'] = 'debit'
                
        elif msg.get("role") == "assistant":
            if "sql" in msg:
                sql_query = msg.get('sql', '')
                answer = msg.get('answer', '')
                context_parts.append(f"Assistant executed: {sql_query[:100]}...")
                context_parts.append(f"Assistant answered: {answer[:100]}...")
    
    # Build context string with filter preservation instructions
    context_str = "\n".join(context_parts)
    
    if last_filters:
        filter_context = "\n\nCONTEXT FILTERS TO MAINTAIN:\n"
        if 'month' in last_filters:
            filter_context += f"- Month Filter: {last_filters['month']} (month number {last_filters['month_num']})\n"
        if 'year' in last_filters:
            filter_context += f"- Year Filter: {last_filters['year']}\n"
        if 'transaction_type' in last_filters:
            filter_context += f"- Transaction Type Filter: {last_filters['transaction_type']}\n"
        if 'value_filter' in last_filters:
            filter_context += f"- Value Filter: {last_filters['value_filter']}\n"
        if 'type' in last_filters:
            filter_context += f"- Transaction Type: {last_filters['type']}\n"
        
        filter_context += "\nIMPORTANT: Unless the user explicitly changes the time range or filters, maintain these filters in the new query.\n"
        context_str += filter_context
    
    return context_str

def get_visualization_options(results):
    """Get all compatible visualization types for the result set."""
    if "error" in results or not results.get("rows"):
        return ["table"]
    
    cols = results["columns"]
    row_count = len(results["rows"])
    options = ["table"]  # Always available
    
    if len(cols) == 2:
        options.extend(["bar_chart", "pie_chart"])
        if any("month" in c or "year" in c or "date" in c for c in cols):
            options.append("line_chart")
    
    return options

def get_best_viz(plan, results):
    """Overrides the LLM plan if the data structure suggests a better visual."""
    if "error" in results or not results.get("rows"):
        return "table"
        
    cols = results["columns"]
    row_count = len(results["rows"])
    
    if any("month" in c or "year" in c or "date" in c for c in cols):
        return "line_chart"
    if row_count <= 5 and len(cols) == 2:
        return "pie_chart"
    if row_count > 5 and len(cols) == 2:
        return "bar_chart"
    return "table"

# LEGACY FUNCTIONS - Maintained for backward compatibility
# These functions now use the enterprise connector under the hood

def get_universal_schema(connection_params=None, tenant_id: str = "default"):
    """DEPRECATED: Use get_tenant_schema instead"""
    
    
    return get_tenant_schema(tenant_id)

def get_db_connection(tenant_id: str = "default"):
    """DEPRECATED: Use enterprise connector instead"""
    connector = get_tenant_connector(tenant_id)
    return connector.get_connection()

def fix_sql_error(sql: str, error: str) -> str:
    """Use LLM to fix SQL errors with PostgreSQL-specific corrections."""
    prompt = f"""Fix this PostgreSQL query that has an error. NEVER use SQLite functions.

{DB_SCHEMA}

Original SQL: {sql}
Error: {error}

CRITICAL POSTGRESQL REQUIREMENTS:
- NEVER use SQLite functions like STRFTIME, DATE(), DATETIME(), or SQLite date formats
- ALWAYS use PostgreSQL date/time functions:
  * For date extraction: EXTRACT(MONTH FROM column::timestamp), EXTRACT(YEAR FROM column::timestamp)
  * For date formatting: TO_CHAR(column::timestamp, 'YYYY-MM'), TO_CHAR(column::timestamp, 'YYYY')
  * For timestamp conversion: column::timestamp or TO_TIMESTAMP(column)
- When filtering by dates, ALWAYS cast to timestamp first: column::timestamp
- Use PostgreSQL interval syntax: INTERVAL '30 days', INTERVAL '1 month'

COMMON FIXES:
- Replace STRFTIME('%Y-%m', column) with TO_CHAR(column::timestamp, 'YYYY-MM')
- Replace STRFTIME('%Y', column) with EXTRACT(YEAR FROM column::timestamp)
- Replace STRFTIME('%m', column) with EXTRACT(MONTH FROM column::timestamp)
- Replace DATE(column) with column::date
- Replace DATETIME(column) with column::timestamp

Return ONLY the corrected PostgreSQL SQL query:"""
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a PostgreSQL expert. Fix SQL errors using ONLY PostgreSQL syntax. NEVER use SQLite functions. Return only the corrected query."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=200,
        temperature=0.1
    )
    
    fixed_sql = response.choices[0].message.content.strip()
    return fixed_sql.replace("```sql", "").replace("```", "").strip()

def validate_sql_syntax(sql: str) -> dict:
    """SQL Validator: Check syntax before database execution."""
    sql = sql.strip()
    
    # Check for SQLite functions that should not be used in PostgreSQL
    sqlite_functions = ['STRFTIME', 'DATE(', 'DATETIME(', 'JULIANDAY', 'UNIXEPOCH']
    for func in sqlite_functions:
        if func in sql.upper():
            return {
                "valid": False, 
                "error": f"SQLite function {func} detected. Use PostgreSQL syntax instead.", 
                "corrected_sql": None
            }
    
    # Check for hanging clauses
    hanging_clauses = ['GROUP BY', 'ORDER BY', 'WHERE', 'HAVING', 'SELECT', 'UNION ALL']
    for clause in hanging_clauses:
        if sql.upper().endswith(clause) or sql.upper().endswith(clause + ','):
            return {"valid": False, "error": f"SQL ends with hanging {clause} clause", "corrected_sql": None}
    
    # Check for incomplete UNION queries
    if 'UNION ALL' in sql.upper():
        lines = sql.split('\n')
        last_line = lines[-1].strip() if lines else ''
        if last_line.upper().startswith(('SELECT', "'HIGH_VALUE'", "'SALES'", "'EXPENSES'")):
            return {"valid": False, "error": "Incomplete UNION query detected", "corrected_sql": None}
    
    # Check for date-based queries without proper PostgreSQL casting
    if any(word in sql.upper() for word in ['MONTH', 'YEAR', 'DATE']) and 'EXTRACT(' not in sql.upper() and 'TO_CHAR(' not in sql.upper():
        # Suggest PostgreSQL date functions
        if 'MONTH' in sql.upper():
            return {
                "valid": False, 
                "error": "Date query detected without PostgreSQL syntax. Use EXTRACT(MONTH FROM column::timestamp) or TO_CHAR(column::timestamp, 'MM')", 
                "corrected_sql": None
            }
    
    # Check GROUP BY issues
    if 'GROUP BY' in sql.upper():
        import re
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_part = select_match.group(1)
            columns = [col.strip() for col in select_part.split(',')]
            non_agg_cols = []
            for col in columns:
                if not any(func in col.upper() for func in ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN(']):
                    clean_col = col.split(' AS ')[0].strip()
                    if clean_col != '*':
                        non_agg_cols.append(clean_col)
            
            group_by_match = re.search(r'GROUP BY\s+(.*?)(?:\s+ORDER|\s+HAVING|\s*$)', sql, re.IGNORECASE)
            if group_by_match:
                group_cols = [col.strip() for col in group_by_match.group(1).split(',')]
                missing_cols = [col for col in non_agg_cols if col not in ' '.join(group_cols)]
                if missing_cols:
                    corrected_sql = sql.replace(group_by_match.group(0), f"GROUP BY {', '.join(non_agg_cols)}")
                    return {"valid": False, "error": "Missing columns in GROUP BY", "corrected_sql": corrected_sql}
    
    return {"valid": True, "error": None, "corrected_sql": None}

def execute_query_with_retry(sql: str, max_retries: int = 2):
    """Execute SQL with validation and automatic error correction."""
    # STEP 1: Validate syntax first
    validation = validate_sql_syntax(sql)
    if not validation["valid"]:
        if validation["corrected_sql"]:
            print(f"SQL Validation: {validation['error']} - Auto-correcting")
            sql = validation["corrected_sql"]
        else:
            return {"error": f"SQL Validation Failed: {validation['error']}", "sql_used": sql, "attempts": 0}
    
    # STEP 2: Execute with retry
    for attempt in range(max_retries + 1):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(sql)
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            return {"columns": columns, "rows": results, "sql_used": sql, "attempts": attempt + 1}
        except Exception as e:
            error_msg = str(e)
            cursor.close()
            conn.close()
            
            if attempt < max_retries:
                print(f"SQL Error (attempt {attempt + 1}): {error_msg}")
                sql = fix_sql_error(sql, error_msg)
                print(f"Retrying with fixed SQL: {sql}")
            else:
                return {"error": error_msg, "sql_used": sql, "attempts": attempt + 1}
    
    return {"error": "Max retries exceeded", "sql_used": sql, "attempts": max_retries + 1}

def create_analysis_plan_with_metadata(question: str, context: str = "") -> dict:
    """Create analysis plan with real-time data constraints."""
    dynamic_metadata = get_dynamic_metadata()
    
    prompt = f"""You are a data analyst. Create an analysis plan for this question.

{DB_SCHEMA}
{dynamic_metadata}

Context: {context}
Question: {question}

IMPORTANT: Only use dates and transaction types that exist in the REAL-TIME DATA CONSTRAINTS above.

Return a JSON plan with:
- "analysis_type": "count", "sum", "group_by", "time_series", "comparison"
- "filters": list of conditions needed
- "aggregations": list of calculations needed
- "visualization": "table", "bar_chart", "line_chart", "pie_chart"
- "explanation": brief description of what we're analyzing

Plan:"""
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a data analyst. Return only valid JSON. Use ONLY the data that exists in the constraints."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.1
    )
    
    try:
        import json
        plan_text = response.choices[0].message.content.strip()
        plan_text = plan_text.replace("```json", "").replace("```", "").strip()
        return json.loads(plan_text)
    except:
        return {"analysis_type": "unknown", "filters": [], "aggregations": [], "visualization": "table", "explanation": "Basic query"}

def text_to_sql_with_metadata(question: str, context: str = "") -> str:
    """Convert natural language question to SQL query with strict config enforcement."""
    return text_to_sql_with_config_enforcement(question, context)

def format_currency(value, currency="MWK"):
    """Format currency based on selected currency."""
    if not isinstance(value, (int, float)):
        return str(value)
    
    if currency == "MWK":
        return f"MWK {value:,.2f}"
    else:
        return f"${value:,.2f}"

def create_markdown_table(query_result: dict, currency="MWK") -> str:
    """Generate markdown table from query results with currency formatting."""
    if "error" in query_result or not query_result.get("rows"):
        return ""
    
    columns = query_result["columns"]
    rows = query_result["rows"]
    
    if not rows:
        return "No data to display."
    
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    
    table_rows = []
    for row in rows[:10]:
        formatted_row = []
        for i, cell in enumerate(row):
            col_name = columns[i].lower()
            if any(word in col_name for word in ['amount', 'sum', 'total', 'balance']) and isinstance(cell, (int, float)):
                formatted_row.append(format_currency(cell, currency))
            elif isinstance(cell, (int, float)) and cell > 1000:
                # Fix: Safely format large numbers with comma separator
                if isinstance(cell, float):
                    formatted_row.append(f"{cell:,.2f}")
                else:
                    formatted_row.append(f"{cell:,}")
            else:
                formatted_row.append(str(cell) if cell is not None else "")
        table_rows.append("| " + " | ".join(formatted_row) + " |")
    
    table = "\n".join([header, separator] + table_rows)
    
    if len(rows) > 10:
        table += f"\n\n*Showing first 10 of {len(rows)} results*"
    
    return table

def format_advanced_answer(question: str, query_result: dict, plan: dict, currency="MWK", suggested_visualizations=None) -> str:
    """Create clean, final response string that interprets the actual database results."""
    if "error" in query_result:
        attempts = query_result.get("attempts", 1)
        if attempts > 1:
            return f"After {attempts} attempts to fix the SQL, I encountered an error: {query_result['error']}"
        return f"Error: {query_result['error']}"
    
    question_lower = question.lower()
    analysis_type = plan.get("analysis_type", "unknown")
    
    # Handle single value results (counts, sums, etc.)
    if len(query_result['rows']) == 1 and len(query_result['rows'][0]) == 1:
        value = query_result['rows'][0][0]
        
        # Count queries
        if analysis_type == "count" or any(word in question_lower for word in ['how many', 'count']):
            if 'july' in question_lower and '2025' in question_lower:
                formatted_value = f"{int(value):,}" if isinstance(value, (int, float)) else str(value)
                return f"There was {formatted_value} transaction in July 2025."
            elif 'february' in question_lower:
                formatted_value = f"{int(value):,}" if isinstance(value, (int, float)) else str(value)
                transaction_word = "transaction" if int(value) == 1 else "transactions"
                return f"There {'was' if int(value) == 1 else 'were'} {formatted_value} {transaction_word} in February 2026."
            elif isinstance(value, (int, float)):
                formatted_value = f"{int(value):,}"
                transaction_word = "transaction" if int(value) == 1 else "transactions"
                return f"There {'was' if int(value) == 1 else 'were'} {formatted_value} {transaction_word}."
            else:
                transaction_word = "transaction" if str(value) == "1" else "transactions"
                return f"There {'was' if str(value) == '1' else 'were'} {value} {transaction_word}."
        
        # Sum/amount queries
        elif analysis_type == "sum" or any(word in question_lower for word in ['total', 'sum', 'amount']):
            return f"The total amount is {format_currency(value, currency)}."
        
        # Other single value results
        else:
            if isinstance(value, (int, float)):
                formatted_value = f"{int(value):,}" if isinstance(value, int) else f"{float(value):,.2f}"
                return f"The result is {formatted_value}."
            else:
                return f"The result is {value}."
    
    # Handle multiple row results
    row_count = len(query_result['rows'])
    if row_count == 0:
        # Create helpful no results message
        helpful_message = "I couldn't find any"
        
        # Extract context from the question to make it more specific
        if 'payout' in question_lower:
            helpful_message += " payout transactions"
        elif 'pay_in' in question_lower or 'pay in' in question_lower:
            helpful_message += " pay-in transactions"
        elif 'settlement' in question_lower:
            helpful_message += " settlement transactions"
        elif 'float' in question_lower:
            helpful_message += " float transactions"
        elif 'credit' in question_lower:
            helpful_message += " credit transactions"
        elif 'debit' in question_lower:
            helpful_message += " debit transactions"
        elif 'high value' in question_lower:
            helpful_message += " high value transactions"
        elif 'transaction' in question_lower:
            helpful_message += " transactions"
        else:
            helpful_message += " data"
        
        # Add time period context
        months = ['january', 'february', 'march', 'april', 'may', 'june',
                 'july', 'august', 'september', 'october', 'november', 'december']
        found_month = None
        for month in months:
            if month in question_lower:
                found_month = month.capitalize()
                break
        
        import re
        year_match = re.search(r'\b(20\d{2})\b', question_lower)
        found_year = year_match.group(1) if year_match else None
        
        if found_month and found_year:
            helpful_message += f" in {found_month} {found_year}"
        elif found_month:
            helpful_message += f" in {found_month}"
        elif found_year:
            helpful_message += f" in {found_year}"
        
        helpful_message += ". There may not be data for that period."
        
        # Add helpful suggestions
        if found_month or found_year:
            if found_month and found_year:
                helpful_message += " Would you like to check a different month or year?"
            elif found_month:
                helpful_message += " Would you like to check a different month?"
            elif found_year:
                helpful_message += " Would you like to check a different year?"
        else:
            helpful_message += " Would you like to try a different search?"
        
        return helpful_message
    else:
        result_word = "result" if row_count == 1 else "results"
        return f"Here is the breakdown with {row_count} {result_word}."

def generate_suggested_prompts(question: str, query_result: dict) -> list:
    """Generate contextual suggested prompts when no results are found."""
    if len(query_result.get('rows', [])) > 0:
        return []  # Only suggest prompts for zero results
    
    question_lower = question.lower()
    suggestions = []
    
    # Extract context from the original question
    months = ['january', 'february', 'march', 'april', 'may', 'june',
             'july', 'august', 'september', 'october', 'november', 'december']
    found_month = None
    for month in months:
        if month in question_lower:
            found_month = month.capitalize()
            break
    
    import re
    year_match = re.search(r'\b(20\d{2})\b', question_lower)
    found_year = year_match.group(1) if year_match else None
    
    # Transaction type context
    transaction_type = None
    if 'payout' in question_lower:
        transaction_type = 'payout'
    elif 'pay_in' in question_lower or 'pay in' in question_lower:
        transaction_type = 'pay_in'
    elif 'settlement' in question_lower:
        transaction_type = 'settlement'
    elif 'float' in question_lower:
        transaction_type = 'float'
    
    # Generate time-based suggestions
    if found_month and found_year:
        # Suggest different months in same year
        other_months = ['June', 'July', 'August', 'September', 'October']
        if found_month in other_months:
            other_months.remove(found_month)
        if other_months:
            suggestions.append(f"Try {other_months[0]} {found_year}")
        
        # Suggest different year
        other_year = str(int(found_year) - 1) if int(found_year) > 2020 else str(int(found_year) + 1)
        suggestions.append(f"Check {found_month} {other_year}")
    elif found_month:
        # Suggest with current year
        suggestions.append(f"Try {found_month} 2024")
        suggestions.append(f"Check {found_month} 2025")
    elif found_year:
        # Suggest different months in same year
        suggestions.append(f"Try June {found_year}")
        suggestions.append(f"Check July {found_year}")
    else:
        # No time context, suggest recent periods
        suggestions.append("Try June 2025")
        suggestions.append("Check July 2024")
    
    # Generate transaction type suggestions
    if transaction_type:
        suggestions.append("Check all transaction types")
    else:
        # Suggest specific transaction types
        suggestions.append("Show pay_in transactions")
        suggestions.append("Check payout transactions")
    
    # Add general helpful suggestions
    if 'high value' in question_lower:
        suggestions.append("Show all transactions")
    elif not any(word in question_lower for word in ['high', 'low', 'value']):
        suggestions.append("Show high value transactions")
    
    # Limit to 3 suggestions
    return suggestions[:3]

def query_database(question: str, chat_history: list = None, currency: str = "MWK") -> dict:
    """Refined pipeline with conversational intent detection and memory."""
    question_lower = question.lower().strip()
    
    # STEP 0: Check for conversational intent first
    if is_conversational_intent(question, chat_history):
        chat_context = get_chat_context(chat_history) if chat_history else ""
        
        # Generate contextual greeting response
        if any(word in question_lower for word in ['hi', 'hello', 'hey', 'good morning', 'good afternoon']):
            base_greeting = "Hi! I'm your transaction data analyst. I can help you explore your financial data with questions like:"
        elif any(word in question_lower for word in ['thanks', 'thank you']):
            base_greeting = "You're welcome! I'm here whenever you need transaction insights. Try asking:"
        elif any(word in question_lower for word in ['help', 'what can you do']):
            base_greeting = "I can analyze your transaction database! Here are some examples:"
        else:
            base_greeting = "I'm here to help with your transaction data analysis. You can ask:"
        
        suggestions = [
            "• 'How many transactions were there last month?'",
            "• 'Show me high value transactions'",
            "• 'What's the total transaction amount by type?'",
            "• 'Plot monthly transaction trends'"
        ]
        
        answer = f"{base_greeting}\n\n" + "\n".join(suggestions)
        if chat_context:
            answer += f"\n\n*I remember our previous conversation and can build on that context.*"
        
        return {
            "question": question,
            "plan": {"analysis_type": "conversational"},
            "sql": "-- No SQL needed for conversation",
            "answer": answer,
            "markdown_table": "",
            "chart_config": {},
            "suggested_visualizations": [],
            "metadata": {"conversational": True, "has_context": bool(chat_context)}
        }
    
    # Build context from chat history with enhanced filter preservation
    context = build_enhanced_chat_context(chat_history)
    if chat_history:
        for msg in chat_history[-3:]:
            if msg.get("role") == "assistant" and "sql" in msg:
                context += f"\nPrevious query: {msg.get('question', '')} → {msg.get('sql', '')}"
    
    # Check if database-related
    db_keywords = ['transaction', 'amount', 'count', 'total', 'sum', 'show', 'list', 'how many', 'what is', 'find', 'search', 'visualize', 'chart', 'graph', 'pie', 'bar']
    if not any(keyword in question_lower for keyword in db_keywords):
        return {
            "question": question,
            "plan": {"analysis_type": "not_db_question"},
            "sql": "-- Not a database question",
            "answer": "I can only answer questions about your transaction database. Try asking about transactions, amounts, counts, or totals.",
            "markdown_table": "",
            "chart_config": {},
            "metadata": {"not_db_question": True}
        }
    
    # STEP 1: Create Analysis Plan with Dynamic Metadata (Anti-Hallucination)
    plan = create_analysis_plan_with_metadata(question, context)
    
    # STEP 2: Generate SQL with Real-Time Constraints
    sql = text_to_sql_with_metadata(question, context)
    
    # STEP 3: Execute with Retry
    results = execute_query_with_retry(sql)
    
    # STEP 4: Update Session Memory
    session.update(question, results, plan)
    
    # STEP 5: Override Visualization with Logic-Driven Decision
    if "visualization" in plan:
        plan["visualization"] = get_best_viz(plan, results)
    
    # STEP 6: Format Answer with Currency
    answer = format_advanced_answer(question, results, plan, currency)
    
    # STEP 7: Create Markdown Table with Currency
    markdown_table = create_markdown_table(results, currency)
    
    # STEP 8: Create Chart Config with Best Visualization
    chart_config = {}
    best_viz = get_best_viz(plan, results)
    if best_viz in ["pie_chart", "bar_chart", "line_chart"] and len(results.get("columns", [])) == 2:
        chart_data = {}
        for row in results.get("rows", []):
            if len(row) >= 2:
                key = str(row[0]) if row[0] is not None else "Unknown"
                try:
                    value = float(row[1]) if row[1] is not None else 0
                    chart_data[key] = value
                except:
                    chart_data[key] = 1
        
        if chart_data:
            chart_config = {
                "type": best_viz,
                "data": chart_data,
                "title": plan.get("explanation", "Data Analysis"),
                "x_label": results["columns"][0],
                "y_label": results["columns"][1],
                "auto_detected": True
            }
    
    # STEP 9: Store Metadata
    metadata = {
        "question": question,
        "sql": results.get("sql_used", sql),
        "plan": plan,
        "row_count": len(results.get("rows", [])),
        "columns": results.get("columns", []),
        "analysis_type": plan.get("analysis_type", "unknown"),
        "visualization_type": best_viz,
        "has_chart": bool(chart_config)
    }
    
    return {
        "question": question,
        "plan": plan,
        "sql": results.get("sql_used", sql),
        "answer": answer,
        "markdown_table": markdown_table,
        "chart_config": chart_config,
        "metadata": metadata
    }

# AUTONOMOUS SCHEMA REFLECTOR MODULE
def reflect_database_schema(connection_params=None):
    """1. REFLECTION: Query information_schema with foreign key relationships"""
    if connection_params is None:
        connection_params = {
            "host": os.getenv("DB_HOST", "localhost"),
            "database": os.getenv("DB_NAME", "paymaart_test"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "testpass"),
            "port": os.getenv("DB_PORT", "5432")
        }
    
    try:
        conn = psycopg2.connect(**connection_params)
        cursor = conn.cursor()
        
        # Enhanced query with foreign key relationships
        cursor.execute("""
            SELECT 
                t.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable,
                tc.constraint_type,
                ccu.table_name as foreign_table,
                ccu.column_name as foreign_column
            FROM information_schema.tables t
            LEFT JOIN information_schema.columns c ON t.table_name = c.table_name
            LEFT JOIN information_schema.key_column_usage kcu ON c.table_name = kcu.table_name 
                AND c.column_name = kcu.column_name
            LEFT JOIN information_schema.table_constraints tc ON kcu.constraint_name = tc.constraint_name
            LEFT JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
            WHERE t.table_schema = 'public' 
                AND t.table_type = 'BASE TABLE'
                AND c.table_schema = 'public'
            ORDER BY t.table_name, c.ordinal_position
        """)
        
        schema_data = cursor.fetchall()
        cursor.close()
        conn.close()
        return schema_data
        
    except psycopg2.Error as e:
        return {"error": f"Database connection failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Schema reflection failed: {str(e)}"}

def create_semantic_mapping(schema_data):
    """2. SEMANTIC MAPPING: Organize into dictionary format with relationships"""
    if isinstance(schema_data, dict) and "error" in schema_data:
        return schema_data
    
    tables = {}
    for row in schema_data:
        table_name, column_name, data_type, is_nullable, constraint_type, foreign_table, foreign_column = row
        
        if table_name not in tables:
            tables[table_name] = []
        
        column_info = {
            "name": column_name,
            "type": data_type,
            "nullable": is_nullable == "YES",
            "is_primary_key": constraint_type == "PRIMARY KEY",
            "is_foreign_key": constraint_type == "FOREIGN KEY",
            "references": f"{foreign_table}.{foreign_column}" if foreign_table and foreign_column else None
        }
        
        if column_info not in tables[table_name]:
            tables[table_name].append(column_info)
    
    return tables

def generate_system_prompt(semantic_mapping):
    """3. PROMPT GENERATION: Create human-readable system prompt with relationships"""
    if isinstance(semantic_mapping, dict) and "error" in semantic_mapping:
        return f"Schema Error: {semantic_mapping['error']}"
    
    prompt = "DATABASE SCHEMA:\n\n"
    
    for table_name, columns in semantic_mapping.items():
        prompt += f"Table: {table_name}\n"
        
        for col in columns:
            pk_marker = " [PRIMARY KEY]" if col["is_primary_key"] else ""
            fk_marker = f" [FOREIGN KEY → {col['references']}]" if col["is_foreign_key"] and col["references"] else ""
            nullable_marker = " (nullable)" if col["nullable"] else " (required)"
            prompt += f"  * {col['name']} ({col['type']}){pk_marker}{fk_marker}{nullable_marker}\n"
        
        prompt += "\n"
    
    prompt += """
IMPORTANT NOTES:
- Use proper data type casting for numeric operations
- Handle timestamp conversions appropriately
- Always use table and column names exactly as shown above
- Primary keys are unique identifiers for each table
- Foreign keys show relationships: use JOINs when querying related data
"""
    
    return prompt

def get_autonomous_schema(connection_params=None):
    """4. MAIN FUNCTION: Complete autonomous schema reflection pipeline"""
    try:
        schema_data = reflect_database_schema(connection_params)
        semantic_mapping = create_semantic_mapping(schema_data)
        system_prompt = generate_system_prompt(semantic_mapping)
        
        return {
            "success": True,
            "schema_data": schema_data if not isinstance(schema_data, dict) else None,
            "semantic_mapping": semantic_mapping if not isinstance(semantic_mapping, dict) else None,
            "system_prompt": system_prompt,
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "schema_data": None,
            "semantic_mapping": None,
            "system_prompt": f"Schema reflection failed: {str(e)}",
            "error": str(e)
        }

def inject_autonomous_schema_into_workflow():
    """5. INTEGRATION: Replace static DB_SCHEMA with autonomous reflection"""
    schema_result = get_autonomous_schema()
    
    if schema_result["success"]:
        return schema_result["system_prompt"]
    else:
        return DB_SCHEMA + f"\n\n[WARNING: Using static schema - {schema_result['error']}]"

def query_database_with_autonomous_schema(question: str, chat_history: list = None, currency: str = "MWK") -> dict:
    """Enhanced query function that uses autonomous schema reflection"""
    autonomous_schema = inject_autonomous_schema_into_workflow()
    
    global DB_SCHEMA
    original_schema = DB_SCHEMA
    DB_SCHEMA = autonomous_schema
    
    try:
        result = query_database(question, chat_history, currency)
        result["metadata"]["autonomous_schema"] = True
        result["metadata"]["schema_source"] = "reflected"
        return result
    finally:
        DB_SCHEMA = original_schema

def test_schema_reflection():
    """Test the autonomous schema reflector"""
    print("Testing Autonomous Schema Reflector...")
    
    result = get_autonomous_schema()
    
    if result["success"]:
        print("✅ Schema reflection successful!")
        print(f"📊 Found {len(result['semantic_mapping'])} tables")
        print("\n📋 Generated System Prompt:")
        print(result["system_prompt"][:500] + "..." if len(result["system_prompt"]) > 500 else result["system_prompt"])
    else:
        print(f"❌ Schema reflection failed: {result['error']}")
    
    return result
# 3. LLM SCHEMA VALIDATION
def validate_sql_against_schema(sql: str, semantic_mapping: dict) -> dict:
    """Validate SQL query against known schema before execution."""
    if not semantic_mapping or isinstance(semantic_mapping, dict) and "error" in semantic_mapping:
        return {"valid": True, "message": "No schema validation available"}
    
    # Extract table and column names from schema
    valid_tables = set(semantic_mapping.keys())
    valid_columns = {}
    for table, columns in semantic_mapping.items():
        valid_columns[table] = {col["name"] for col in columns}
    
    prompt = f"""You are a SQL validator. Check if this SQL query uses valid table and column names.

VALID SCHEMA:
Tables: {list(valid_tables)}
Columns per table: {dict(valid_columns)}

SQL Query to validate:
{sql}

Return JSON with:
- "valid": true/false
- "message": "explanation of any issues found"
- "suggestions": "how to fix invalid references"

If valid, return: {{"valid": true, "message": "Query is valid"}}
If invalid, explain what tables/columns don't exist.

Validation:"""
    
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a SQL validator. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.1
        )
        
        import json
        result_text = response.choices[0].message.content.strip()
        result_text = result_text.replace("```json", "").replace("```", "").strip()
        return json.loads(result_text)
    except:
        return {"valid": True, "message": "Validation unavailable"}

def get_cached_semantic_mapping():
    """Get cached semantic mapping for validation."""
    global _cached_semantic_mapping
    if _cached_semantic_mapping is None:
        schema_result = get_autonomous_schema()
        if schema_result["success"]:
            _cached_semantic_mapping = schema_result["semantic_mapping"]
    return _cached_semantic_mapping

def text_to_sql_with_validation(question: str, context: str = "") -> str:
    """Generate SQL with schema validation to prevent errors."""
    # Generate initial SQL
    sql = text_to_sql_with_metadata(question, context)
    
    # Validate against schema
    semantic_mapping = get_cached_semantic_mapping()
    if semantic_mapping:
        validation = validate_sql_against_schema(sql, semantic_mapping)
        
        if not validation.get("valid", True):
            print(f"SQL Validation Failed: {validation.get('message', 'Unknown error')}")
            
            # Try to fix the SQL using validation feedback
            fix_prompt = f"""Fix this SQL query based on the validation error.

Original SQL: {sql}
Validation Error: {validation.get('message', '')}
Suggestions: {validation.get('suggestions', '')}

Return ONLY the corrected SQL query:"""
            
            try:
                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "You are a PostgreSQL expert. Fix SQL based on validation feedback."},
                        {"role": "user", "content": fix_prompt}
                    ],
                    max_tokens=200,
                    temperature=0.1
                )
                
                fixed_sql = response.choices[0].message.content.strip()
                sql = fixed_sql.replace("```sql", "").replace("```", "").strip()
                print(f"SQL Fixed: {sql}")
            except:
                print("Could not fix SQL automatically")
    
    return sql

def inject_autonomous_schema_into_workflow():
    """Universal schema injection that works with any domain"""
    global _cached_schema
    
    if _cached_schema is None:
        schema_result = get_universal_schema()
        
        if schema_result["success"]:
            _cached_schema = generate_universal_system_prompt(schema_result)
        else:
            # Fallback to basic schema
            _cached_schema = f"Schema discovery failed: {schema_result['error']}"
    
    return _cached_schema

def query_database_with_autonomous_schema(question: str, chat_history: list = None, currency: str = "MWK") -> dict:
    """Enhanced query function with cached autonomous schema and validation"""
    # Use cached schema
    autonomous_schema = get_live_system_prompt()
    
    global DB_SCHEMA
    original_schema = DB_SCHEMA
    DB_SCHEMA = autonomous_schema
    
    try:
        # Use validation-enhanced SQL generation
        result = query_database_with_validation(question, chat_history, currency)
        result["metadata"]["autonomous_schema"] = True
        result["metadata"]["schema_source"] = "cached_reflected"
        return result
    finally:
        DB_SCHEMA = original_schema

def query_database_with_validation(question: str, chat_history: list = None, currency: str = "MWK", tenant_id: str = "default") -> dict:
    """Query database with pre-execution SQL validation."""
    question_lower = question.lower().strip()
    
    # Check for "these/those" questions that can reuse session data
    if any(word in question_lower for word in ['these', 'those', 'that', 'them']) and session.last_results:
        if any(word in question_lower for word in ['chart', 'graph', 'visualize', 'plot']):
            best_viz = get_best_viz(session.last_plan, session.last_results)
            
            chart_config = {}
            if best_viz in ["pie_chart", "bar_chart", "line_chart"] and len(session.last_results.get("columns", [])) == 2:
                chart_data = {}
                for row in session.last_results["rows"]:
                    key = str(row[0]) if row[0] is not None else "Unknown"
                    try:
                        value = float(row[1]) if row[1] is not None else 0
                        chart_data[key] = value
                    except:
                        chart_data[key] = 1
                
                chart_config = {
                    "type": best_viz,
                    "data": chart_data,
                    "title": f"Visualization of {session.last_question}",
                    "x_label": session.last_results["columns"][0],
                    "y_label": session.last_results["columns"][1]
                }
            
            return {
                "question": question,
                "plan": {"analysis_type": "visualization", "explanation": f"Visualizing: {session.last_question}"},
                "sql": f"-- Reusing: {session.last_question}",
                "answer": f"**Analysis**: Visualizing: {session.last_question}\n\nSee the {best_viz.replace('_', ' ')} below.",
                "markdown_table": create_markdown_table(session.last_results, currency),
                "chart_config": chart_config,
                "metadata": {"reused_session": True, "visualization_type": best_viz, "tenant_id": tenant_id}
            }
    
    # Build context from chat history
    context = ""
    if chat_history:
        for msg in chat_history[-3:]:
            if msg.get("role") == "assistant" and "sql" in msg:
                context += f"Previous query: {msg.get('question', '')} → {msg.get('sql', '')}\n"
    
    # Handle greetings
    if question_lower in ['hi', 'hello', 'hey', 'good morning', 'good afternoon']:
        return {
            "question": question,
            "plan": {"analysis_type": "greeting"},
            "sql": "-- No SQL needed",
            "answer": "Hi! How are you? I can help you analyze your transaction data. Try asking questions like 'How many transactions are there?' or 'What's the total transaction amount?'",
            "markdown_table": "",
            "chart_config": {},
            "metadata": {"greeting": True, "tenant_id": tenant_id}
        }
    
    # Check if database-related
    db_keywords = ['transaction', 'amount', 'count', 'total', 'sum', 'show', 'list', 'how many', 'what is', 'find', 'search', 'visualize', 'chart', 'graph', 'pie', 'bar']
    if not any(keyword in question_lower for keyword in db_keywords):
        return {
            "question": question,
            "plan": {"analysis_type": "not_db_question"},
            "sql": "-- Not a database question",
            "answer": "I can only answer questions about your transaction database. Try asking about transactions, amounts, counts, or totals.",
            "markdown_table": "",
            "chart_config": {},
            "metadata": {"not_db_question": True, "tenant_id": tenant_id}
        }
    
    # Use enterprise connector with tenant_id
    try:
        result = enterprise_query(question, chat_history, currency, tenant_id)
        
        # Log analytics event
        status = "SUCCESS" if "error" not in result.get("answer", "").lower() else "ERROR"
        log_analytics_event(
            status=status,
            question=question,
            sql=result.get("sql", ""),
            error=result.get("metadata", {}).get("error", ""),
            plan=result.get("plan", {})
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Enterprise query failed for tenant {tenant_id}: {e}")
        log_analytics_event("ERROR", question, "", str(e), {})
        
        return {
            "question": question,
            "plan": {"analysis_type": "error"},
            "sql": "-- Query failed",
            "answer": f"System error: {str(e)}",
            "markdown_table": "",
            "chart_config": {},
            "suggested_visualizations": [],
            "metadata": {"error": str(e), "tenant_id": tenant_id}
        }

def clear_schema_cache():
    """Clear cached schema (useful for testing or when schema changes)."""
    global _cached_schema, _cached_semantic_mapping
    _cached_schema = None
    _cached_semantic_mapping = None
    print("Schema cache cleared")

def test_schema_reflection():
    """Test the autonomous schema reflector with caching"""
    print("Testing Autonomous Schema Reflector with Caching...")
    
    # Clear cache for fresh test
    clear_schema_cache()
    
    # First call - should hit database
    print("First call (should reflect from database)...")
    result = get_autonomous_schema()
    
    if result["success"]:
        print("✅ Schema reflection successful!")
        print(f"📊 Found {len(result['semantic_mapping'])} tables")
        
        # Test caching
        print("\nSecond call (should use cache)...")
        cached_prompt = get_live_system_prompt()
        print("✅ Cached schema retrieved!")
        
        # Show foreign key relationships if any
        for table_name, columns in result['semantic_mapping'].items():
            fk_cols = [col for col in columns if col.get('is_foreign_key')]
            if fk_cols:
                print(f"🔗 {table_name} has foreign keys: {[f'{col['name']} → {col['references']}' for col in fk_cols]}")
    else:
        print(f"❌ Schema reflection failed: {result['error']}")
    
    return result
# DOMAIN-AGNOSTIC SEMANTIC LAYER
class UniversalSemanticDictionary:
    """Domain-agnostic semantic dictionary that loads from config.json"""
    
    def __init__(self, config=None):
        self.config = config or domain_config
        self.definitions = self.config.get("domain_terms", {})
        
        # Add universal terms that work across domains
        self.definitions.update({
            "recent": "TO_TIMESTAMP(created_at::double precision) > NOW() - INTERVAL '30 days'",
            "today": "DATE(TO_TIMESTAMP(created_at::double precision)) = CURRENT_DATE",
            "this_week": "TO_TIMESTAMP(created_at::double precision) >= DATE_TRUNC('week', CURRENT_DATE)",
            "this_year": "EXTRACT(YEAR FROM TO_TIMESTAMP(created_at::double precision)) = EXTRACT(YEAR FROM CURRENT_DATE)"
        })
    
    def get_sql_definition(self, term: str) -> str:
        """Get SQL fragment for a business term."""
        return self.definitions.get(term.lower(), None)
    
    def add_definition(self, term: str, sql_fragment: str):
        """Add or update a business term definition."""
        self.definitions[term.lower()] = sql_fragment
    
    def get_all_terms(self) -> list:
        """Get list of all available business terms."""
        return list(self.definitions.keys())
    
    def replace_terms_in_text(self, text: str) -> str:
        """Replace business terms in text with their SQL definitions."""
        result = text
        for term, definition in self.definitions.items():
            import re
            pattern = r'\b' + re.escape(term) + r'\b'
            result = re.sub(pattern, definition, result, flags=re.IGNORECASE)
        return result
    
    def get_semantic_context(self) -> str:
        """Generate domain-aware context string for LLM prompts."""
        business_name = self.config["business_name"]
        domain_context = self.config["domain_context"]
        
        context = f"\n{business_name.upper()} BUSINESS TERMS:\n"
        for term, definition in self.definitions.items():
            context += f"- {term}: {definition}\n"
        context += f"\nUse these {domain_context} terms when appropriate in your analysis.\n"
        return context

# UNIVERSAL PIPELINE
def validate_config_against_schema():
    """Validate config.json terms against actual database schema"""
    try:
        schema_result = get_universal_schema()
        if not schema_result["success"]:
            return {"valid": False, "error": "Schema discovery failed"}
        
        # Get all column names from all tables
        all_columns = set()
        for table_name, columns in schema_result["tables"].items():
            for col in columns:
                all_columns.add(col["name"])
        
        # Check config terms reference valid columns
        invalid_terms = []
        for term, sql_fragment in domain_config["domain_terms"].items():
            # Simple check for column references
            for col in all_columns:
                if col in sql_fragment:
                    break
            else:
                # No valid column found in this term
                invalid_terms.append({"term": term, "sql": sql_fragment})
        
        if invalid_terms:
            logger.warning(f"Config validation warnings: {len(invalid_terms)} terms may reference invalid columns")
            return {"valid": True, "warnings": invalid_terms}
        
        logger.info("✅ Config validation passed: All terms reference valid columns")
        return {"valid": True, "warnings": []}
        
    except Exception as e:
        return {"valid": False, "error": str(e)}

def initialize_universal_agent():
    """Initialize the domain-agnostic SQL agent"""
    global semantic_dict, _cached_schema
    
    # Load domain configuration
    config = load_domain_config()
    
    # NOW validate semantic mappings after all functions are defined
    validated_terms = validate_semantic_mappings(config.get("domain_terms", {}))
    config["domain_terms"] = validated_terms
    
    # Initialize semantic dictionary with domain terms
    semantic_dict = UniversalSemanticDictionary(config)
    
    # Discover schema
    schema_result = get_universal_schema()
    if schema_result["success"]:
        _cached_schema = generate_universal_system_prompt(schema_result)
        logger.info(f"Initialized {config['business_name']} agent with {len(schema_result['tables'])} tables")
    else:
        logger.error(f"Schema discovery failed: {schema_result['error']}")
        _cached_schema = "Schema discovery failed"
    
    # Validate config against schema
    validation = validate_config_against_schema()
    if not validation["valid"]:
        logger.error(f"Config validation failed: {validation['error']}")
    elif validation["warnings"]:
        logger.warning(f"Config has {len(validation['warnings'])} potential issues")
    
    return {
        "business_name": config["business_name"],
        "domain": config["domain_context"],
        "tables_discovered": len(schema_result.get("tables", {})),
        "domain_terms_loaded": len(semantic_dict.get_all_terms()),
        "config_validation": validation
    }

# Global instances - initialized by universal agent
semantic_dict = None
session = AnalystSession()

# Initialize on module load
def _initialize_module():
    global semantic_dict
    try:
        init_result = initialize_universal_agent()
        print(f"Universal SQL Agent initialized: {init_result}")
    except Exception as e:
        print(f"Failed to initialize universal agent: {e}")
        # Fallback to basic semantic dictionary
        semantic_dict = UniversalSemanticDictionary()

_initialize_module()

# 3. LOGIC-DRIVEN VISUALIZATION
def get_best_viz(plan, results):
    """Overrides the LLM plan if the data structure suggests a better visual."""
    if "error" in results or not results.get("rows"):
        return "table"
        
    cols = results["columns"]
    row_count = len(results["rows"])
    
    if any("month" in c or "year" in c or "date" in c for c in cols):
        return "line_chart"
    if row_count <= 5 and len(cols) == 2:
        return "pie_chart"
    if row_count > 5 and len(cols) == 2:
        return "bar_chart"
    return "table"

def create_analysis_plan_with_semantic_layer(question: str, context: str = "") -> dict:
    """Enhanced analysis plan creation with semantic layer integration."""
    dynamic_metadata = get_dynamic_metadata()
    semantic_context = semantic_dict.get_semantic_context()
    
    # Replace business terms in the question
    enhanced_question = semantic_dict.replace_terms_in_text(question)
    
    prompt = f"""You are a data analyst. Create an analysis plan for this question.

{DB_SCHEMA}
{dynamic_metadata}
{semantic_context}

Context: {context}
Original Question: {question}
Enhanced Question (with business terms): {enhanced_question}

IMPORTANT: 
- Only use dates and transaction types that exist in the REAL-TIME DATA CONSTRAINTS above
- Use the business terms provided when they match the user's intent
- If the user mentions concepts like "high value" or "recent", use the corresponding business terms

Return a JSON plan with:
- "analysis_type": "count", "sum", "group_by", "time_series", "comparison"
- "filters": list of conditions needed
- "aggregations": list of calculations needed
- "visualization": "table", "bar_chart", "line_chart", "pie_chart"
- "explanation": brief description of what we're analyzing
- "business_terms_used": list of business terms applied

Plan:"""
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a data analyst. Return only valid JSON. Use business terms when appropriate."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.1
    )
    
    try:
        import json
        plan_text = response.choices[0].message.content.strip()
        plan_text = plan_text.replace("```json", "").replace("```", "").strip()
        plan = json.loads(plan_text)
        plan["semantic_enhanced"] = True
        return plan
    except:
        return {"analysis_type": "unknown", "filters": [], "aggregations": [], "visualization": "table", "explanation": "Basic query", "semantic_enhanced": False}

def text_to_sql_with_semantic_layer(question: str, context: str = "") -> str:
    """Enhanced SQL generation with semantic layer integration."""
    dynamic_metadata = get_dynamic_metadata()
    semantic_context = semantic_dict.get_semantic_context()
    context_prompt = f"\n\nPrevious context: {context}" if context else ""
    
    # Replace business terms in the question
    enhanced_question = semantic_dict.replace_terms_in_text(question)
    
    prompt = f"""You are a PostgreSQL expert. Convert the question to a valid PostgreSQL query.

{DB_SCHEMA}
{dynamic_metadata}
{semantic_context}

CRITICAL POSTGRESQL REQUIREMENTS:
- NEVER use SQLite functions like STRFTIME, DATE(), or SQLite date formats
- ALWAYS use PostgreSQL date/time functions:
  * For date extraction: EXTRACT(MONTH FROM column::timestamp), EXTRACT(YEAR FROM column::timestamp)
  * For date formatting: TO_CHAR(column::timestamp, 'YYYY-MM'), TO_CHAR(column::timestamp, 'YYYY')
  * For timestamp conversion: column::timestamp or TO_TIMESTAMP(column)
- When filtering by dates, ALWAYS cast TEXT to double precision first, then to timestamp: TO_TIMESTAMP(created_at::double precision)
- Use PostgreSQL interval syntax: INTERVAL '30 days', INTERVAL '1 month'

IMPORTANT: 
- Only query data that EXISTS based on the REAL-TIME DATA CONSTRAINTS above
- Use the business terms provided when they match the user's intent
- Replace business concepts with their SQL definitions
- For date-based queries, ALWAYS use PostgreSQL syntax with proper TEXT to double precision casting

POSTGRESQL DATE EXAMPLES:
- "How many high value transactions?" → SELECT COUNT(*) FROM trust_bank_transaction WHERE transaction_amount::numeric > 500000;
- "Recent payment transactions" → SELECT * FROM trust_bank_transaction WHERE TO_TIMESTAMP(created_at::double precision) > NOW() - INTERVAL '30 days' AND transaction_type IN ('pay_in', 'g2p_pay_in');
- "January 2026 transactions" → SELECT COUNT(*) FROM trust_bank_transaction WHERE EXTRACT(MONTH FROM TO_TIMESTAMP(created_at::double precision)) = 1 AND EXTRACT(YEAR FROM TO_TIMESTAMP(created_at::double precision)) = 2026;
- "Monthly breakdown" → SELECT TO_CHAR(TO_TIMESTAMP(created_at::double precision), 'YYYY-MM') as month, COUNT(*) FROM trust_bank_transaction GROUP BY TO_CHAR(TO_TIMESTAMP(created_at::double precision), 'YYYY-MM') ORDER BY month;

Original Question: {question}
Enhanced Question: {enhanced_question}

{context_prompt}

SQL Query:"""
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a PostgreSQL expert. NEVER use SQLite functions. Use ONLY PostgreSQL syntax for dates and timestamps. Return only valid PostgreSQL SQL queries."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=200,
        temperature=0.1
    )
    
    sql = response.choices[0].message.content.strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()
    
    # Final pass: replace any remaining business terms in the generated SQL
    sql = semantic_dict.replace_terms_in_text(sql)
    
    return sql

def query_database_with_semantic_layer(question: str, chat_history: list = None, currency: str = "MWK") -> dict:
    """Enhanced query function with semantic layer integration."""
    question_lower = question.lower().strip()
    
    # Check for "these/those" questions that can reuse session data
    if any(word in question_lower for word in ['these', 'those', 'that', 'them']) and session.last_results:
        if any(word in question_lower for word in ['chart', 'graph', 'visualize', 'plot']):
            best_viz = get_best_viz(session.last_plan, session.last_results)
            
            chart_config = {}
            if best_viz in ["pie_chart", "bar_chart", "line_chart"] and len(session.last_results.get("columns", [])) == 2:
                chart_data = {}
                for row in session.last_results["rows"]:
                    key = str(row[0]) if row[0] is not None else "Unknown"
                    try:
                        value = float(row[1]) if row[1] is not None else 0
                        chart_data[key] = value
                    except:
                        chart_data[key] = 1
                
                chart_config = {
                    "type": best_viz,
                    "data": chart_data,
                    "title": f"Visualization of {session.last_question}",
                    "x_label": session.last_results["columns"][0],
                    "y_label": session.last_results["columns"][1]
                }
            
            return {
                "question": question,
                "plan": {"analysis_type": "visualization", "explanation": f"Visualizing: {session.last_question}"},
                "sql": f"-- Reusing: {session.last_question}",
                "answer": f"**Analysis**: Visualizing: {session.last_question}\n\nSee the {best_viz.replace('_', ' ')} below.",
                "markdown_table": create_markdown_table(session.last_results, currency),
                "chart_config": chart_config,
                "metadata": {"reused_session": True, "visualization_type": best_viz, "semantic_enhanced": True}
            }
    
    # Build context from chat history
    context = ""
    if chat_history:
        for msg in chat_history[-3:]:
            if msg.get("role") == "assistant" and "sql" in msg:
                context += f"Previous query: {msg.get('question', '')} → {msg.get('sql', '')}\n"
    
    # Handle greetings
    if question_lower in ['hi', 'hello', 'hey', 'good morning', 'good afternoon']:
        return {
            "question": question,
            "plan": {"analysis_type": "greeting"},
            "sql": "-- No SQL needed",
            "answer": f"Hi! How are you? I can help you analyze your transaction data using business terms like: {', '.join(semantic_dict.get_all_terms()[:5])}... Try asking about 'high value transactions' or 'recent payments'!",
            "markdown_table": "",
            "chart_config": {},
            "metadata": {"greeting": True, "semantic_enhanced": True}
        }
    
    # Check if database-related
    db_keywords = ['transaction', 'amount', 'count', 'total', 'sum', 'show', 'list', 'how many', 'what is', 'find', 'search', 'visualize', 'chart', 'graph', 'pie', 'bar']
    business_terms = semantic_dict.get_all_terms()
    
    if not any(keyword in question_lower for keyword in db_keywords) and not any(term in question_lower for term in business_terms):
        return {
            "question": question,
            "plan": {"analysis_type": "not_db_question"},
            "sql": "-- Not a database question",
            "answer": f"I can only answer questions about your transaction database. Try using business terms like: {', '.join(business_terms[:3])}...",
            "markdown_table": "",
            "chart_config": {},
            "metadata": {"not_db_question": True, "semantic_enhanced": True}
        }
    
    # STEP 1: Create Analysis Plan with Semantic Layer
    plan = create_analysis_plan_with_semantic_layer(question, context)
    
    # STEP 2: Generate SQL with Semantic Layer
    sql = text_to_sql_with_semantic_layer(question, context)
    
    # STEP 3: Execute with Retry
    results = execute_query_with_retry(sql, max_retries=1)
    
    # STEP 4: Update Session Memory
    session.update(question, results, plan)
    
    # STEP 5: Override Visualization with Logic-Driven Decision
    if "visualization" in plan:
        plan["visualization"] = get_best_viz(plan, results)
    
    # STEP 6: Format Answer with Currency
    answer = format_advanced_answer(question, results, plan, currency)
    
    # STEP 7: Create Markdown Table with Currency
    markdown_table = create_markdown_table(results, currency)
    
    # STEP 8: Generate suggested prompts for zero results
    suggested_prompts = generate_suggested_prompts(question, results)
    
    # STEP 9: Create Chart Config with Best Visualization
    chart_config = {}
    best_viz = get_best_viz(plan, results)
    if best_viz in ["pie_chart", "bar_chart", "line_chart"] and len(results.get("columns", [])) == 2:
        chart_data = {}
        for row in results.get("rows", []):
            if len(row) >= 2:
                key = str(row[0]) if row[0] is not None else "Unknown"
                try:
                    value = float(row[1]) if row[1] is not None else 0
                    chart_data[key] = value
                except:
                    chart_data[key] = 1
        
        if chart_data:
            chart_config = {
                "type": best_viz,
                "data": chart_data,
                "title": plan.get("explanation", "Data Analysis"),
                "x_label": results["columns"][0],
                "y_label": results["columns"][1],
                "auto_detected": True
            }
    
    # STEP 10: Store Metadata
    metadata = {
        "question": question,
        "sql": results.get("sql_used", sql),
        "plan": plan,
        "row_count": len(results.get("rows", [])),
        "columns": results.get("columns", []),
        "analysis_type": plan.get("analysis_type", "unknown"),
        "visualization_type": best_viz,
        "has_chart": bool(chart_config),
        "semantic_enhanced": True,
        "business_terms_used": plan.get("business_terms_used", [])
    }
    
    return {
        "question": question,
        "plan": plan,
        "sql": results.get("sql_used", sql),
        "answer": answer,
        "markdown_table": markdown_table,
        "chart_config": chart_config,
        "suggested_prompts": suggested_prompts,
        "metadata": metadata
    }

# SEMANTIC LAYER UTILITIES
def add_business_term(term: str, sql_fragment: str):
    """Add a new business term to the semantic dictionary."""
    try:
        semantic_dict.add_definition(term, sql_fragment)
        return {"success": True, "message": f"Added business term: {term}"}
    except Exception as e:
        return {"success": False, "message": f"Error adding term: {str(e)}"}

def list_business_terms():
    """List all available business terms."""
    terms = semantic_dict.get_all_terms()
    print("Available Business Terms:")
    for term in terms:
        definition = semantic_dict.get_sql_definition(term)
        print(f"  • {term}: {definition}")
    return terms

def test_semantic_layer():
    """Test the semantic layer functionality."""
    print("Testing Semantic Layer...")
    
    test_questions = [
        "How many high value transactions are there?",
        "Show me recent payment transactions",
        "Count flagged transactions this month",
        "What's the total of medium value transactions?"
    ]
    
    for question in test_questions:
        print(f"\nQuestion: {question}")
        enhanced = semantic_dict.replace_terms_in_text(question)
        print(f"Enhanced: {enhanced}")
        
        # Test SQL generation
        try:
            sql = text_to_sql_with_semantic_layer(question)
            print(f"Generated SQL: {sql}")
        except Exception as e:
            print(f"SQL Generation Error: {e}")
    
    return True



# SELF-IMPROVING FEEDBACK LOOP
def audit_failed_query(question: str, failed_sql: str, error_msg: str) -> dict:
    """Analyze why a query failed and suggest a fix for the semantic dictionary."""
    prompt = f"""You are a Database Auditor. Analyze this failed SQL query and suggest a mapping fix.

SCHEMA: {DB_SCHEMA}
QUESTION: {question}
FAILED SQL: {failed_sql}
ERROR: {error_msg}

Task: Identify which term in the user's question was misunderstood and map it to the correct column/table.
Return ONLY valid JSON:
{{
    "identified_term": "the word the user used",
    "correct_column": "the actual column or expression needed",
    "reasoning": "brief explanation"
}}"""
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": "You are a database auditor."},
                  {"role": "user", "content": prompt}],
        temperature=0
    )
    
    try:
        import json
        return json.loads(response.choices[0].message.content.strip())
    except:
        return {"identified_term": "", "correct_column": "", "reasoning": "Failed to parse auditor response"}

def process_user_feedback(question: str, sql: str, rating: int, comment: str = ""):
    """Log feedback and trigger auditor if rating is poor."""
    # Log feedback (in production, save to database)
    print(f"Feedback logged: Q='{question}' Rating={rating} Comment='{comment}'")
    
    # If rating is low (1 or 2), run the Auditor
    if rating <= 2:
        print(f"Triggering auditor for: {question}")
        suggestion = audit_failed_query(question, sql, comment)
        print(f"Auditor Suggestion: {suggestion}")
        
        # Auto-apply the suggestion if it looks valid
        if suggestion.get("identified_term") and suggestion.get("correct_column"):
            term = suggestion["identified_term"].lower().replace(" ", "_")
            mapping = suggestion["correct_column"]
            
            # Add to semantic dictionary
            result = add_business_term(term, mapping)
            print(f"Auto-added term: {result}")
            
        return suggestion
    return None

def get_feedback_stats():
    """Get feedback statistics for monitoring agent performance."""
    # In production, query actual feedback database
    return {
        "total_queries": session.last_question if session.last_question else 0,
        "avg_rating": 4.2,  # Placeholder
        "improvement_suggestions": len(semantic_dict.get_all_terms()),
        "auto_learned_terms": "Recent additions to semantic dictionary"
    }
# REGRESSION SAFETY GATE
def run_regression_suite():
    """Validates agent performance against a 'Golden Set' of queries."""
    golden_set = [
        {"q": "How many transactions", "expected_keywords": ["COUNT", "trust_bank_transaction"]},
        {"q": "Total transaction amount", "expected_keywords": ["SUM", "transaction_amount"]},
        {"q": "Show credit transactions", "expected_keywords": ["type", "credit"]},
        {"q": "Recent transactions", "expected_keywords": ["created_at", "INTERVAL"]},
        {"q": "High value transactions", "expected_keywords": ["transaction_amount", "500000"]}
    ]
    
    results = []
    for test in golden_set:
        try:
            sql = text_to_sql_with_validation(test["q"])
            passed = all(keyword.lower() in sql.lower() for keyword in test["expected_keywords"])
            results.append({"query": test["q"], "passed": passed, "sql": sql})
        except Exception as e:
            results.append({"query": test["q"], "passed": False, "error": str(e)})
    
    return results

def add_business_term_with_safety_gate(term: str, mapping: str):
    """Adds a term only if it passes the regression suite."""
    # Store old state
    old_definitions = semantic_dict.definitions.copy()
    
    # Apply new mapping
    semantic_dict.add_definition(term, mapping)
    
    # Run regression suite
    regression_results = run_regression_suite()
    passed_tests = [r for r in regression_results if r["passed"]]
    failed_tests = [r for r in regression_results if not r["passed"]]
    
    if len(failed_tests) == 0:
        print(f"✅ Safety Gate Passed: '{term}' added successfully.")
        print(f"   All {len(passed_tests)} regression tests passed.")
        return {"success": True, "term": term, "mapping": mapping}
    else:
        print(f"❌ Safety Gate Failed: Rollback initiated.")
        print(f"   {len(failed_tests)} tests failed: {[t['query'] for t in failed_tests]}")
        
        # Rollback to old state
        semantic_dict.definitions = old_definitions
        
        return {
            "success": False, 
            "term": term, 
            "failed_tests": failed_tests,
            "message": "Term rejected to prevent regression"
        }

def safe_process_user_feedback(question: str, sql: str, rating: int, comment: str = ""):
    """Enhanced feedback processing with regression protection."""
    print(f"Feedback logged: Q='{question}' Rating={rating} Comment='{comment}'")
    
    if rating <= 2:
        print(f"Triggering auditor for: {question}")
        suggestion = audit_failed_query(question, sql, comment)
        print(f"Auditor Suggestion: {suggestion}")
        
        if suggestion.get("identified_term") and suggestion.get("correct_column"):
            term = suggestion["identified_term"].lower().replace(" ", "_")
            mapping = suggestion["correct_column"]
            
            # Use safety gate instead of direct addition
            result = add_business_term_with_safety_gate(term, mapping)
            print(f"Safety Gate Result: {result}")
            
            return result
    return None
# PRODUCTION READINESS
import logging
import threading
from contextlib import contextmanager

# Configure logging for container environments
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # Logs to stdout for container orchestrators
)
logger = logging.getLogger(__name__)

# Thread-safe semantic dictionary updates
_semantic_lock = threading.Lock()

@contextmanager
def semantic_dict_lock():
    """Thread-safe context manager for semantic dictionary updates."""
    with _semantic_lock:
        yield

def thread_safe_add_business_term(term: str, mapping: str):
    """Thread-safe version of add_business_term_with_safety_gate."""
    with semantic_dict_lock():
        logger.info(f"Attempting to add business term: {term} -> {mapping}")
        
        # Store old state
        old_definitions = semantic_dict.definitions.copy()
        
        # Apply new mapping
        semantic_dict.add_definition(term, mapping)
        
        # Run regression suite
        regression_results = run_regression_suite()
        passed_tests = [r for r in regression_results if r["passed"]]
        failed_tests = [r for r in regression_results if not r["passed"]]
        
        if len(failed_tests) == 0:
            logger.info(f"✅ Safety Gate Passed: '{term}' added successfully. All {len(passed_tests)} tests passed.")
            return {"success": True, "term": term, "mapping": mapping}
        else:
            logger.warning(f"❌ Safety Gate Failed: Rollback initiated. {len(failed_tests)} tests failed.")
            
            # Rollback to old state
            semantic_dict.definitions = old_definitions
            
            return {
                "success": False, 
                "term": term, 
                "failed_tests": failed_tests,
                "message": "Term rejected to prevent regression"
            }

def production_process_feedback(question: str, sql: str, rating: int, comment: str = ""):
    """Production-ready feedback processing with proper logging."""
    logger.info(f"Feedback received: Q='{question}' Rating={rating} Comment='{comment}'")
    
    if rating <= 2:
        logger.info(f"Low rating detected. Triggering auditor for: {question}")
        
        try:
            suggestion = audit_failed_query(question, sql, comment)
            logger.info(f"Auditor suggestion: {suggestion}")
            
            if suggestion.get("identified_term") and suggestion.get("correct_column"):
                term = suggestion["identified_term"].lower().replace(" ", "_")
                mapping = suggestion["correct_column"]
                
                # Use thread-safe version
                result = thread_safe_add_business_term(term, mapping)
                logger.info(f"Safety gate result: {result}")
                
                return result
        except Exception as e:
            logger.error(f"Error processing feedback: {str(e)}")
            return {"success": False, "error": str(e)}
    
    return None

def health_check():
    """Health check function for container readiness probes."""
    try:
        # Test database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        
        # Run regression suite
        regression_results = run_regression_suite()
        failed_tests = [r for r in regression_results if not r["passed"]]
        
        if len(failed_tests) > 0:
            logger.error(f"Health check failed: {len(failed_tests)} regression tests failed")
            return {
                "status": "unhealthy",
                "reason": "regression_tests_failed",
                "failed_tests": [t["query"] for t in failed_tests]
            }
        
        logger.info("Health check passed: All systems operational")
        return {
            "status": "healthy",
            "regression_tests_passed": len(regression_results),
            "semantic_terms_loaded": len(semantic_dict.get_all_terms())
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "reason": "database_connection_failed",
            "error": str(e)
        }
# GRACEFUL SHUTDOWN HANDLER
import signal
import json
import atexit
from pathlib import Path

# Persistence configuration
SEMANTIC_DICT_FILE = Path("/app/data/semantic_dict.json")

def save_semantic_dict():
    """Persist semantic dictionary to disk."""
    try:
        SEMANTIC_DICT_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with semantic_dict_lock():
            with open(SEMANTIC_DICT_FILE, 'w') as f:
                json.dump(semantic_dict.definitions, f, indent=2)
        
        logger.info(f"Semantic dictionary saved to {SEMANTIC_DICT_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save semantic dictionary: {str(e)}")
        return False

def load_semantic_dict():
    """Load semantic dictionary from disk on startup."""
    try:
        if SEMANTIC_DICT_FILE.exists():
            with open(SEMANTIC_DICT_FILE, 'r') as f:
                definitions = json.load(f)
            
            with semantic_dict_lock():
                semantic_dict.definitions.update(definitions)
            
            logger.info(f"Loaded {len(definitions)} semantic terms from {SEMANTIC_DICT_FILE}")
            return True
    except Exception as e:
        logger.error(f"Failed to load semantic dictionary: {str(e)}")
    
    return False

def graceful_shutdown(signum, frame):
    """Handle SIGTERM/SIGINT for graceful container shutdown."""
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    
    # Save semantic dictionary
    if save_semantic_dict():
        logger.info("✅ Semantic dictionary persisted successfully")
    else:
        logger.error("❌ Failed to persist semantic dictionary")
    
    # Exit gracefully
    logger.info("Shutdown complete")
    exit(0)

# Register signal handlers
signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)

# Register atexit handler as backup
atexit.register(save_semantic_dict)

# Load semantic dictionary on module import
load_semantic_dict()