"""
Enterprise Multi-Tenant Database Connector
Supports any database schema with dynamic reflection and tenant isolation
"""

import psycopg2
import sqlalchemy
from sqlalchemy import create_engine, MetaData, inspect
from groq import Groq
import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, List, Any, Optional
import threading
from contextlib import contextmanager
from unified_llm_client import get_llm_client

load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enterprise_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('enterprise_db_connector')

class TenantConfig:
    """Multi-tenant configuration manager"""
    
    def __init__(self, tenant_id: str = "default"):
        self.tenant_id = tenant_id
        self.config_file = Path(f"config_{tenant_id}.json")
        # Try to load from app/tenant_config.json first, then fallback to tenant-specific config
        self.config = self._load_tenant_config()
        
    def _load_tenant_config(self) -> Dict[str, Any]:
        """Load tenant-specific configuration"""
        try:
            # First try to load from app/tenant_config.json
            app_config_file = Path("app/tenant_config.json")
            if app_config_file.exists():
                with open(app_config_file, 'r') as f:
                    config = json.load(f)
                    logger.info(f"Loaded tenant config from app/tenant_config.json for tenant {self.tenant_id}")
                    
                    # Ensure database config exists with environment variables
                    if "database" not in config:
                        config["database"] = {
                            "host": os.getenv("DB_HOST", "localhost"),
                            "database": os.getenv("DB_NAME", "default_db"),
                            "user": os.getenv("DB_USER", "postgres"),
                            "password": os.getenv("DB_PASSWORD", "password"),
                            "port": os.getenv("DB_PORT", "5432"),
                            "driver": "postgresql"
                        }
                        logger.info(f"Added database config from environment variables for tenant {self.tenant_id}")
                    
                    return config
            
            # Fallback to tenant-specific config file
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            else:
                # Create default config for new tenant
                config = self._create_default_config()
                self._save_config(config)
            
            return config
        except Exception as e:
            logger.error(f"Failed to load config for tenant {self.tenant_id}: {e}")
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration for new tenant"""
        return {
            "tenant_id": self.tenant_id,
            "business_name": f"Tenant {self.tenant_id}",
            "domain_context": "data_analysis",
            "database": {
                "host": os.getenv("DB_HOST", "localhost"),
                "database": os.getenv("DB_NAME", "default_db"),
                "user": os.getenv("DB_USER", "postgres"),
                "password": os.getenv("DB_PASSWORD", "password"),
                "port": os.getenv("DB_PORT", "5432"),
                "driver": "postgresql"
            },
            "active_table": "transactions",  # Dynamic table name
            "approved_tables": [],  # Security: only these tables are accessible
            "domain_terms": {},
            "business_language": {
                "primary_entity": "records",
                "currency": "USD"
            }
        }
    
    def _save_config(self, config: Dict[str, Any]):
        """Save tenant configuration"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config for tenant {self.tenant_id}: {e}")
    
    def get_db_connection_params(self) -> Dict[str, str]:
        """Get database connection parameters for this tenant"""
        db_config = self.config["database"]
        return {
            "host": db_config["host"],
            "database": db_config["database"],
            "user": db_config["user"],
            "password": db_config["password"],
            "port": db_config["port"]
        }
    
    def get_active_table(self) -> str:
        """Get the active table name for this tenant"""
        return self.config.get("active_table", "transactions")
    
    def get_approved_tables(self) -> List[str]:
        """Get list of approved tables (security layer)"""
        approved = self.config.get("approved_tables", [])
        if not approved:
            # If no approved tables specified, allow all discovered tables
            return []
        return approved
    
    def update_active_table(self, table_name: str):
        """Update the active table for this tenant"""
        self.config["active_table"] = table_name
        self._save_config(self.config)

class SchemaReflector:
    """Universal schema reflection using SQLAlchemy"""
    
    def __init__(self, tenant_config: TenantConfig):
        self.tenant_config = tenant_config
        self.engine = None
        self.metadata = None
        self.current_schema = {}
        self._schema_lock = threading.Lock()
    
    def _get_engine(self):
        """Create SQLAlchemy engine for tenant database"""
        if self.engine is None:
            db_params = self.tenant_config.get_db_connection_params()
            # Log connection params for debugging (without password)
            debug_params = {k: v for k, v in db_params.items() if k != 'password'}
            debug_params['password'] = '***' if db_params.get('password') else 'None'
            logger.info(f"SQLAlchemy connection params for tenant {self.tenant_config.tenant_id}: {debug_params}")
            
            driver = self.tenant_config.config["database"].get("driver", "postgresql")
            
            if driver == "postgresql":
                connection_string = f"postgresql://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{db_params['database']}"
            elif driver == "mysql":
                connection_string = f"mysql://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{db_params['database']}"
            elif driver == "sqlite":
                connection_string = f"sqlite:///{db_params['database']}"
            else:
                raise ValueError(f"Unsupported database driver: {driver}")
            
            logger.info(f"Creating SQLAlchemy engine with driver: {driver}")
            self.engine = create_engine(connection_string)
            self.metadata = MetaData()
        
        return self.engine
    
    @contextmanager
    def schema_lock(self):
        """Thread-safe schema operations"""
        with self._schema_lock:
            yield
    
    def reflect_schema(self) -> Dict[str, Any]:
        """Reflect database schema using SQLAlchemy"""
        try:
            with self.schema_lock():
                engine = self._get_engine()
                inspector = inspect(engine)
                
                # Get all table names
                table_names = inspector.get_table_names()
                
                # Apply security filter if approved tables are specified
                approved_tables = self.tenant_config.get_approved_tables()
                if approved_tables:
                    table_names = [t for t in table_names if t in approved_tables]
                
                schema = {}
                for table_name in table_names:
                    columns = inspector.get_columns(table_name)
                    primary_keys = inspector.get_pk_constraint(table_name)
                    foreign_keys = inspector.get_foreign_keys(table_name)
                    
                    # Build column information
                    table_columns = []
                    for col in columns:
                        column_info = {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "nullable": col["nullable"],
                            "is_primary_key": col["name"] in primary_keys.get("constrained_columns", []),
                            "is_foreign_key": any(col["name"] in fk["constrained_columns"] for fk in foreign_keys),
                            "references": None
                        }
                        
                        # Add foreign key reference information
                        for fk in foreign_keys:
                            if col["name"] in fk["constrained_columns"]:
                                idx = fk["constrained_columns"].index(col["name"])
                                ref_table = fk["referred_table"]
                                ref_column = fk["referred_columns"][idx]
                                column_info["references"] = f"{ref_table}.{ref_column}"
                                break
                        
                        table_columns.append(column_info)
                    
                    schema[table_name] = table_columns
                
                self.current_schema = {
                    "success": True,
                    "tables": schema,
                    "tenant_id": self.tenant_config.tenant_id,
                    "business_context": self.tenant_config.config["business_name"],
                    "domain": self.tenant_config.config["domain_context"],
                    "active_table": self.tenant_config.get_active_table()
                }
                
                logger.info(f"Schema reflected for tenant {self.tenant_config.tenant_id}: {len(schema)} tables")
                return self.current_schema
                
        except Exception as e:
            logger.error(f"Schema reflection failed for tenant {self.tenant_config.tenant_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tables": {},
                "tenant_id": self.tenant_config.tenant_id
            }
    
    def get_current_schema(self) -> Dict[str, Any]:
        """Get current schema (cached or reflect if needed)"""
        if not self.current_schema or not self.current_schema.get("success"):
            return self.reflect_schema()
        return self.current_schema
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema for specific table"""
        schema = self.get_current_schema()
        if schema["success"] and table_name in schema["tables"]:
            return {
                "success": True,
                "table": table_name,
                "columns": schema["tables"][table_name]
            }
        return {"success": False, "error": f"Table {table_name} not found"}

class DynamicPromptGenerator:
    """Generate dynamic prompts based on current schema"""
    
    def __init__(self, schema_reflector: SchemaReflector):
        self.schema_reflector = schema_reflector
        self.llm_client = get_llm_client()
    
    def generate_system_prompt(self) -> str:
        """Generate system prompt with current schema"""
        schema = self.schema_reflector.get_current_schema()
        
        if not schema["success"]:
            return f"Schema Error: {schema['error']}"
        
        tenant_id = schema["tenant_id"]
        business_name = schema["business_context"]
        domain_context = schema["domain"]
        active_table = schema["active_table"]
        
        prompt = f"""You are working with the following schema for {business_name} (Tenant: {tenant_id}):

ACTIVE TABLE: {active_table}
DOMAIN: {domain_context}

DATABASE SCHEMA:

"""
        
        for table_name, columns in schema["tables"].items():
            is_active = " [ACTIVE]" if table_name == active_table else ""
            prompt += f"Table: {table_name}{is_active}\n"
            
            for col in columns:
                pk_marker = " [PRIMARY KEY]" if col["is_primary_key"] else ""
                fk_marker = f" [FOREIGN KEY → {col['references']}]" if col["is_foreign_key"] and col["references"] else ""
                nullable_marker = " (nullable)" if col["nullable"] else " (required)"
                prompt += f"  * {col['name']} ({col['type']}){pk_marker}{fk_marker}{nullable_marker}\n"
            
            prompt += "\n"
        
        prompt += f"""
IMPORTANT NOTES:
- Generate SQL that is compatible with this specific structure
- Use proper data type casting for numeric operations
- Handle timestamp conversions appropriately
- Always use table and column names exactly as shown above
- Primary keys are unique identifiers for each table
- Foreign keys show relationships: use JOINs when querying related data
- Focus queries on the ACTIVE TABLE: {active_table} unless joins are needed
- This is a {domain_context} domain for {business_name}
"""
        
        return prompt

class EnterpriseDBConnector:
    """Main enterprise database connector with multi-tenancy"""
    
    def __init__(self, tenant_id: str = "default"):
        self.tenant_id = tenant_id
        self.tenant_config = TenantConfig(tenant_id)
        self.schema_reflector = SchemaReflector(self.tenant_config)
        self.prompt_generator = DynamicPromptGenerator(self.schema_reflector)
        self.llm_client = get_llm_client()
        
        # Initialize schema on startup
        self.refresh_schema()
    
    def refresh_schema(self):
        """Refresh schema from database"""
        logger.info(f"Refreshing schema for tenant {self.tenant_id}")
        return self.schema_reflector.reflect_schema()
    
    def get_active_table(self) -> str:
        """Get current active table name"""
        return self.tenant_config.get_active_table()
    
    def set_active_table(self, table_name: str) -> Dict[str, Any]:
        """Set active table for this tenant"""
        schema = self.schema_reflector.get_current_schema()
        if schema["success"] and table_name in schema["tables"]:
            self.tenant_config.update_active_table(table_name)
            logger.info(f"Active table updated to {table_name} for tenant {self.tenant_id}")
            return {"success": True, "active_table": table_name}
        else:
            return {"success": False, "error": f"Table {table_name} not found in schema"}
    
    def get_connection(self):
        """Get database connection for this tenant"""
        params = self.tenant_config.get_db_connection_params()
        # Log connection params for debugging (without password)
        debug_params = {k: v for k, v in params.items() if k != 'password'}
        debug_params['password'] = '***' if params.get('password') else 'None'
        logger.info(f"Database connection params for tenant {self.tenant_id}: {debug_params}")
        return psycopg2.connect(**params)
    
    def text_to_sql(self, question: str, context: str = "") -> str:
        """Convert natural language to SQL using dynamic schema"""
        system_prompt = self.prompt_generator.generate_system_prompt()
        active_table = self.get_active_table()
        
        # Get tenant config for few-shot examples and table routing
        tenant_config = self.tenant_config.config
        few_shot_examples = tenant_config.get("few_shot_examples", [])
        table_routing = tenant_config.get("table_routing", {})
        timestamp_cast = tenant_config.get("timestamp_cast", "TO_TIMESTAMP(REGEXP_REPLACE({column}, '\\.\\d+$', '')::bigint)")
        
        # Build few-shot examples section
        examples_text = ""
        if few_shot_examples:
            examples_text = "\n\nFEW-SHOT EXAMPLES:\n"
            for i, example in enumerate(few_shot_examples, 1):
                examples_text += f"{i}. Question: {example['question']}\n   SQL: {example['sql']}\n\n"
        
        # Build table routing section
        routing_text = ""
        if table_routing:
            routing_text = "\n\nTABLE ROUTING RULES:\n"
            for pattern, table in table_routing.items():
                routing_text += f"- {pattern} → use table: {table}\n"
        
        user_prompt = f"""Convert this question to SQL using the schema provided.

Question: {question}
Context: {context}{examples_text}{routing_text}

CRITICAL UNIX TIMESTAMP HANDLING:
- Use the configured timestamp cast: {timestamp_cast}
- Replace {{column}} with the actual column name
- For date extraction: EXTRACT(MONTH FROM {timestamp_cast.replace('{column}', 'column_name')})
- For date comparisons: {timestamp_cast.replace('{column}', 'column_name')} > NOW() - INTERVAL '30 days'

CRITICAL POSTGRESQL REQUIREMENTS:
- NEVER use SQLite functions like STRFTIME, DATE(), or SQLite date formats
- NEVER use direct string comparisons on timestamp columns
- ALWAYS use PostgreSQL date/time functions with proper Unix timestamp conversion
- Use PostgreSQL interval syntax: INTERVAL '30 days', INTERVAL '1 month'

IMPORTANT:
- Use the ACTIVE TABLE ({active_table}) as the primary table
- Follow the table routing rules above to select the correct table
- Generate SQL that is compatible with the specific schema structure shown
- Use proper column names and data types as defined in the schema
- Include JOINs only when necessary to access related data
- Follow the few-shot examples for similar question patterns

Return only the PostgreSQL SQL query:"""
        
        try:
            # Use unified LLM client with automatic fallback
            response_text = self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt + "\n\nCRITICAL: NEVER use SQLite functions. For TEXT Unix timestamps, ALWAYS cast to double precision first: column::double precision, then TO_TIMESTAMP(column::double precision). Use ONLY PostgreSQL syntax."},
                    {"role": "user", "content": user_prompt}
                ],
                model="llama-3.3-70b-versatile",
                max_tokens=300,
                temperature=0.1
            )
            
            sql = response_text.strip()
            return sql.replace("```sql", "").replace("```", "").strip()
            
        except Exception as e:
            # The unified client already handles rate limits and provides user-friendly messages
            logger.error(f"LLM API error for tenant {self.tenant_id}: {e}")
            raise e
    
    def execute_query(self, sql: str) -> Dict[str, Any]:
        """Execute SQL query with error handling"""
        # Log the generated SQL before execution
        logger.info(f'Generated SQL: {sql}')
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(sql)
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            cursor.close()
            conn.close()
            
            return {
                "success": True,
                "columns": columns,
                "rows": results,
                "row_count": len(results)
            }
            
        except Exception as e:
            logger.error(f"Query execution failed for tenant {self.tenant_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "columns": [],
                "rows": []
            }
    
    def query_database(self, question: str, context: str = "") -> Dict[str, Any]:
        """Complete query pipeline: question -> SQL -> results"""
        try:
            # Generate SQL
            sql = self.text_to_sql(question, context)
            
            # Execute query
            results = self.execute_query(sql)
            
            # Add metadata
            results["tenant_id"] = self.tenant_id
            results["active_table"] = self.get_active_table()
            results["sql_used"] = sql
            results["question"] = question
            
            return results
            
        except Exception as e:
            logger.error(f"Database query failed for tenant {self.tenant_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tenant_id": self.tenant_id,
                "question": question
            }
    
    def get_tenant_info(self) -> Dict[str, Any]:
        """Get tenant information and status"""
        schema = self.schema_reflector.get_current_schema()
        return {
            "tenant_id": self.tenant_id,
            "business_name": self.tenant_config.config["business_name"],
            "domain_context": self.tenant_config.config["domain_context"],
            "active_table": self.get_active_table(),
            "available_tables": list(schema.get("tables", {}).keys()) if schema["success"] else [],
            "schema_status": "healthy" if schema["success"] else "error",
            "database_driver": self.tenant_config.config["database"]["driver"]
        }

# Global tenant connectors cache
_tenant_connectors: Dict[str, EnterpriseDBConnector] = {}
_connector_lock = threading.Lock()

def get_tenant_connector(tenant_id: str = "default") -> EnterpriseDBConnector:
    """Get or create tenant connector (thread-safe)"""
    with _connector_lock:
        if tenant_id not in _tenant_connectors:
            _tenant_connectors[tenant_id] = EnterpriseDBConnector(tenant_id)
        return _tenant_connectors[tenant_id]

def create_tenant(tenant_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Create new tenant with configuration"""
    try:
        # Create tenant config file
        config_file = Path(f"config_{tenant_id}.json")
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Initialize connector
        connector = EnterpriseDBConnector(tenant_id)
        
        # Cache connector
        with _connector_lock:
            _tenant_connectors[tenant_id] = connector
        
        logger.info(f"Tenant {tenant_id} created successfully")
        return {
            "success": True,
            "tenant_id": tenant_id,
            "message": f"Tenant {tenant_id} created and initialized"
        }
        
    except Exception as e:
        logger.error(f"Failed to create tenant {tenant_id}: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def list_tenants() -> List[str]:
    """List all available tenants"""
    config_files = Path(".").glob("config_*.json")
    tenants = []
    for config_file in config_files:
        tenant_id = config_file.stem.replace("config_", "")
        tenants.append(tenant_id)
    return tenants

# Backward compatibility function
def query_database_with_validation(question: str, chat_history: list = None, currency: str = "USD", tenant_id: str = "default") -> dict:
    """Backward compatible query function with multi-tenant support and enhanced context preservation"""
    connector = get_tenant_connector(tenant_id)
    
    # Check if this is a "show me" request that should reuse previous results
    question_lower = question.lower().strip()
    show_keywords = ['show me', 'show the', 'display', 'view the', 'see the', 'show table', 'display table']
    
    if any(keyword in question_lower for keyword in show_keywords) and chat_history:
        # Look for the most recent assistant response with data
        for msg in reversed(chat_history):
            if (msg.get("role") == "assistant" and 
                "sql" in msg and 
                msg.get("sql") and 
                "SELECT" in msg.get("sql", "").upper()):
                
                # Re-execute the previous query to get fresh results
                try:
                    result = connector.execute_query(msg["sql"])
                    if result["success"] and result["row_count"] > 0:
                        return {
                            "question": question,
                            "plan": {"analysis_type": "display_previous", "tenant_id": tenant_id},
                            "sql": msg["sql"],
                            "answer": f"Here are the {result['row_count']} results from your previous query:",
                            "markdown_table": _create_markdown_table(result, currency),
                            "chart_config": {},
                            "suggested_visualizations": ["table"],
                            "metadata": {
                                "tenant_id": tenant_id,
                                "active_table": connector.get_active_table(),
                                "row_count": result["row_count"],
                                "columns": result["columns"],
                                "reused_query": True
                            },
                            "raw_data": {
                                "columns": result["columns"],
                                "rows": result["rows"],
                                "total_count": result["row_count"]
                            } if result["row_count"] > 0 else None
                        }
                except Exception as e:
                    logger.warning(f"Failed to reuse previous query: {e}")
                    break
    
    # Build enhanced context from chat history with filter preservation
    context = ""
    last_filters = {}  # Track filters from previous queries
    
    if chat_history:
        # Process last 5 messages for better context
        for msg in chat_history[-5:]:
            if msg.get("role") == "user":
                user_question = msg.get('content', '')
                context += f"User asked: {user_question}\n"
                
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
                    context += f"Assistant executed: {sql_query[:100]}...\n"
                    context += f"Assistant answered: {answer[:100]}...\n"
        
        # Add filter preservation instructions
        if last_filters:
            context += "\nCONTEXT FILTERS TO MAINTAIN:\n"
            if 'month' in last_filters:
                context += f"- Month Filter: {last_filters['month']} (month number {last_filters['month_num']})\n"
            if 'year' in last_filters:
                context += f"- Year Filter: {last_filters['year']}\n"
            if 'value_filter' in last_filters:
                context += f"- Value Filter: {last_filters['value_filter']}\n"
            if 'type' in last_filters:
                context += f"- Transaction Type: {last_filters['type']}\n"
            
            context += "\nIMPORTANT: Unless the user explicitly changes the time range or filters, maintain these filters in the new query.\n"
    
    # Execute query with enhanced context
    result = connector.query_database(question, context)
    
    # Format response with LLM-generated conversational answer
    if result["success"]:
        # Generate conversational answer using LLM
        answer = _format_query_answer(question, result, currency)
        
        # Create table only if 2+ rows
        markdown_table = _create_markdown_table(result, currency)
        
        # Create chart config only if explicitly requested and suitable data
        chart_config = {}
        if _should_show_chart(question, result) and len(result["columns"]) == 2:
            chart_data = {}
            for row in result["rows"]:
                if len(row) >= 2:
                    key = str(row[0]) if row[0] is not None else "Unknown"
                    try:
                        value = float(row[1]) if row[1] is not None else 0
                        chart_data[key] = value
                    except:
                        chart_data[key] = 1
            
            if chart_data:
                chart_config = {
                    "type": "bar_chart",
                    "data": chart_data,
                    "title": f"Visualization: {question}",
                    "x_label": result["columns"][0],
                    "y_label": result["columns"][1]
                }
        
        # Determine suggested visualizations
        suggested_visualizations = ["table"] if _should_show_table(result) else []
        if _should_show_chart(question, result) and len(result["columns"]) == 2:
            suggested_visualizations.extend(["bar_chart", "pie_chart"])
        
        return {
            "question": question,
            "plan": {"analysis_type": "query", "tenant_id": tenant_id},
            "sql": result["sql_used"],
            "answer": answer,
            "markdown_table": markdown_table,
            "chart_config": chart_config,
            "suggested_visualizations": suggested_visualizations,
            "metadata": {
                "tenant_id": tenant_id,
                "active_table": result["active_table"],
                "row_count": result["row_count"],
                "columns": result["columns"],
                "context_filters": last_filters,
                "show_table": _should_show_table(result),
                "show_chart": _should_show_chart(question, result)
            },
            "raw_data": {
                "columns": result["columns"],
                "rows": result["rows"],
                "total_count": result["row_count"]
            } if _should_show_table(result) else None
        }
    else:
        return {
            "question": question,
            "plan": {"analysis_type": "error", "tenant_id": tenant_id},
            "sql": result.get("sql_used", "-- Query failed"),
            "answer": f"Query failed: {result['error']}",
            "markdown_table": "",
            "chart_config": {},
            "suggested_visualizations": [],
            "metadata": {"tenant_id": tenant_id, "error": result["error"], "context_filters": last_filters}
        }

def _format_query_answer(question: str, result: Dict[str, Any], currency: str = "USD") -> str:
    """Generate conversational answer using LLM based on query results"""
    if not result["success"]:
        return f"I encountered an issue: {result['error']}"
    
    # Prepare results summary for LLM
    row_count = result["row_count"]
    columns = result["columns"]
    rows = result["rows"]
    
    if row_count == 0:
        results_summary = "No data found matching the criteria."
    elif row_count == 1 and len(columns) == 1:
        # Single value result
        value = rows[0][0]
        if isinstance(value, (int, float)):
            formatted_value = f"{value:,}" if isinstance(value, int) else f"{value:,.2f}"
        else:
            formatted_value = str(value)
        results_summary = f"Single result: {columns[0]} = {formatted_value}"
    else:
        # Multiple rows/columns
        results_summary = f"Found {row_count} records with columns: {', '.join(columns)}. "
        if row_count <= 5:
            # Include actual data for small result sets
            data_preview = []
            for row in rows:
                row_data = []
                for i, cell in enumerate(row):
                    if isinstance(cell, (int, float)) and cell > 1000:
                        formatted_cell = f"{cell:,}" if isinstance(cell, int) else f"{cell:,.2f}"
                    else:
                        formatted_cell = str(cell) if cell is not None else "null"
                    row_data.append(f"{columns[i]}: {formatted_cell}")
                data_preview.append("(" + ", ".join(row_data) + ")")
            results_summary += "Data: " + "; ".join(data_preview)
        else:
            # Just summary for large result sets
            results_summary += f"Sample from first row: "
            sample_data = []
            for i, cell in enumerate(rows[0]):
                if isinstance(cell, (int, float)) and cell > 1000:
                    formatted_cell = f"{cell:,}" if isinstance(cell, int) else f"{cell:,.2f}"
                else:
                    formatted_cell = str(cell) if cell is not None else "null"
                sample_data.append(f"{columns[i]}: {formatted_cell}")
            results_summary += ", ".join(sample_data)
    
    # System prompt for conversational response
    system_prompt = """You are BIZINEZI AI, a friendly financial assistant for PayMaart. Given the user's question and the database results, provide a conversational 1-2 sentence answer that directly addresses what was asked. Use natural language, format numbers with commas, include the currency MWK where relevant, and end with one relevant follow-up suggestion. Never say "There were X transactions" — instead say something natural like "In 2025, PayMaart processed 6 G2P transactions."""
    
    # User prompt with context
    user_prompt = f"""Question: {question}
Database Results: {results_summary}
Currency: {currency}

Provide a natural, conversational response that directly answers the question based on these results."""
    
    try:
        # Use the unified LLM client
        from unified_llm_client import get_llm_client
        llm_client = get_llm_client()
        
        response = llm_client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=150,
            temperature=0.3
        )
        
        return response
        
    except Exception as e:
        logger.error(f"LLM response generation failed: {e}")
        # Fallback to simple response
        if row_count == 0:
            return "I couldn't find any matching data for your query."
        elif row_count == 1 and len(columns) == 1:
            value = rows[0][0]
            if isinstance(value, (int, float)):
                formatted_value = f"{value:,}" if isinstance(value, int) else f"{value:,.2f}"
                return f"The result is {formatted_value}."
            else:
                return f"The result is {value}."
        else:
            return f"I found {row_count} results for your query."

def _format_currency(value, currency: str = "USD") -> str:
    """Format currency values"""
    if not isinstance(value, (int, float)):
        return str(value)
    
    if currency == "MWK":
        return f"MWK {value:,.2f}"
    else:
        return f"${value:,.2f}"

def _should_show_table(result: Dict[str, Any]) -> bool:
    """Determine if table should be shown - only for 2+ rows"""
    return result["success"] and result["row_count"] >= 2

def _should_show_chart(question: str, result: Dict[str, Any]) -> bool:
    """Determine if chart should be shown - only when explicitly requested"""
    if not result["success"] or result["row_count"] < 2:
        return False
    
    # Check for visualization keywords in the question
    question_lower = question.lower()
    chart_keywords = ['chart', 'graph', 'plot', 'visualize', 'show me visually', 'visual']
    
    return any(keyword in question_lower for keyword in chart_keywords)

def _create_markdown_table(result: Dict[str, Any], currency: str = "USD") -> str:
    """Create markdown table from query results - only if should show table"""
    if not _should_show_table(result):
        return ""
    
    columns = result["columns"]
    rows = result["rows"]
    
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    
    table_rows = []
    for row in rows[:10]:  # Limit to first 10 rows
        formatted_row = []
        for i, cell in enumerate(row):
            col_name = columns[i].lower()
            if any(word in col_name for word in ['amount', 'sum', 'total', 'balance']) and isinstance(cell, (int, float)):
                formatted_row.append(_format_currency(cell, currency))
            elif isinstance(cell, (int, float)) and cell > 1000:
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

# Health check for enterprise deployment
def health_check(tenant_id: str = "default") -> Dict[str, Any]:
    """Health check for specific tenant"""
    try:
        connector = get_tenant_connector(tenant_id)
        
        # Test database connection
        conn = connector.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        
        # Get tenant info
        tenant_info = connector.get_tenant_info()
        
        return {
            "status": "healthy",
            "tenant_id": tenant_id,
            "tenant_info": tenant_info,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed for tenant {tenant_id}: {e}")
        return {
            "status": "unhealthy",
            "tenant_id": tenant_id,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    # Example usage
    print("Enterprise DB Connector - Multi-Tenant Example")
    
    # Create a test tenant
    test_config = {
        "tenant_id": "test_bank",
        "business_name": "Test Bank",
        "domain_context": "banking",
        "database": {
            "host": "localhost",
            "database": "test_bank_db",
            "user": "postgres",
            "password": "password",
            "port": "5432",
            "driver": "postgresql"
        },
        "active_table": "transactions",
        "approved_tables": ["transactions", "customers", "accounts"],
        "domain_terms": {
            "high_value": "amount > 10000",
            "recent": "created_at > NOW() - INTERVAL '30 days'"
        }
    }
    
    # Create tenant
    result = create_tenant("test_bank", test_config)
    print(f"Tenant creation: {result}")
    
    # Get connector and test
    connector = get_tenant_connector("test_bank")
    tenant_info = connector.get_tenant_info()
    print(f"Tenant info: {tenant_info}")
    
    # Test query
    query_result = connector.query_database("How many transactions are there?")
    print(f"Query result: {query_result}")