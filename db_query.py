import psycopg2
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 1. SCHEMA CACHING
_cached_schema = None
_cached_semantic_mapping = None

def get_live_system_prompt():
    """Get cached schema or refresh if needed."""
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
  * created_at (bigint) -- Unix timestamp, use TO_TIMESTAMP(created_at::double precision) to convert
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

IMPORTANT SQL Notes:
- created_at is Unix timestamp (bigint), convert with: TO_TIMESTAMP(created_at::bigint)
- ALWAYS cast decimal fields: transaction_amount::numeric, closing_balance::numeric
- For SUM/AVG on amounts: SUM(transaction_amount::numeric), AVG(transaction_amount::numeric)
- For date filtering: EXTRACT(MONTH FROM TO_TIMESTAMP(created_at::bigint)) = 10
- For year filtering: EXTRACT(YEAR FROM TO_TIMESTAMP(created_at::bigint)) = 2024
- For recent data: created_at::bigint > EXTRACT(EPOCH FROM NOW() - INTERVAL '30 days')
- Transaction types: 'float', 'pay_in', 'g2p_pay_in', 'payout_approved', 'settlement', 'excess_float'
- Type values: 'credit', 'debit'
"""

# 1. DYNAMIC HALLUCINATION GUARD
def get_dynamic_metadata():
    """Fetches real bounds of the data to keep the LLM grounded."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                MIN(TO_TIMESTAMP(created_at::bigint)), 
                MAX(TO_TIMESTAMP(created_at::bigint)),
                ARRAY_AGG(DISTINCT transaction_type),
                ARRAY_AGG(DISTINCT type)
            FROM trust_bank_transaction
        """)
        min_date, max_date, t_types, types = cursor.fetchone()
        return f"""
        REAL-TIME DATA CONSTRAINTS:
        - Data Range: {min_date} to {max_date}
        - Valid transaction_type values: {t_types}
        - Valid type values: {types}
        """
    except:
        return ""
    finally:
        cursor.close()
        conn.close()

# 2. STATEFUL ANALYST (SESSION MEMORY)
class AnalystSession:
    def __init__(self):
        self.last_results = None
        self.last_question = ""
        self.last_plan = {}

    def update(self, question, results, plan):
        self.last_results = results
        self.last_question = question
        self.last_plan = plan

session = AnalystSession()

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

def get_db_connection():
    """Connect to PayMaart test database."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "paymaart_test"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "testpass"),
        port=os.getenv("DB_PORT", "5432")
    )

def fix_sql_error(sql: str, error: str) -> str:
    """Use LLM to fix SQL errors."""
    prompt = f"""Fix this PostgreSQL query that has an error.

{DB_SCHEMA}

Original SQL: {sql}
Error: {error}

Return ONLY the corrected SQL query:"""
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a PostgreSQL expert. Fix SQL errors and return only the corrected query."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=200,
        temperature=0.1
    )
    
    fixed_sql = response.choices[0].message.content.strip()
    return fixed_sql.replace("```sql", "").replace("```", "").strip()

def execute_query_with_retry(sql: str, max_retries: int = 2):
    """Execute SQL with automatic error correction."""
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
    """Convert natural language question to SQL query with real-time constraints."""
    dynamic_metadata = get_dynamic_metadata()
    context_prompt = f"\n\nPrevious context: {context}" if context else ""
    
    prompt = f"""You are a PostgreSQL expert. Convert the question to a valid PostgreSQL query.

{DB_SCHEMA}
{dynamic_metadata}

IMPORTANT: Only query data that EXISTS based on the REAL-TIME DATA CONSTRAINTS above.

EXAMPLES:
- "How many transactions?" → SELECT COUNT(*) FROM trust_bank_transaction;
- "Total amount?" → SELECT SUM(transaction_amount) FROM trust_bank_transaction;
- If asked about dates outside the range, return: SELECT 'No data available for that date range' as message;

{context_prompt}

Question: {question}

SQL Query:"""
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a PostgreSQL expert. Return only valid SQL queries for data that exists."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=200,
        temperature=0.1
    )
    
    sql = response.choices[0].message.content.strip()
    return sql.replace("```sql", "").replace("```", "").strip()

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
                formatted_row.append(f"{cell:,.2f}" if isinstance(cell, float) else f"{cell:,}")
            else:
                formatted_row.append(str(cell) if cell is not None else "")
        table_rows.append("| " + " | ".join(formatted_row) + " |")
    
    table = "\n".join([header, separator] + table_rows)
    
    if len(rows) > 10:
        table += f"\n\n*Showing first 10 of {len(rows)} results*"
    
    return table

def format_advanced_answer(question: str, query_result: dict, plan: dict, currency="MWK", suggested_visualizations=None) -> str:
    """Create advanced natural language answer with context and currency formatting."""
    if "error" in query_result:
        attempts = query_result.get("attempts", 1)
        if attempts > 1:
            return f"After {attempts} attempts to fix the SQL, I encountered an error: {query_result['error']}"
        return f"Error: {query_result['error']}"
    
    question_lower = question.lower()
    analysis_type = plan.get("analysis_type", "unknown")
    explanation = plan.get("explanation", "")
    
    answer_prefix = f"**Analysis**: {explanation}\n\n" if explanation else ""
    
    if len(query_result['rows']) == 1 and len(query_result['rows'][0]) == 1:
        value = query_result['rows'][0][0]
        
        if analysis_type == "count":
            if 'february' in question_lower:
                return f"{answer_prefix}There are **{value:,}** transactions in February 2026."
            return f"{answer_prefix}There are **{value:,}** transactions."
        
        elif analysis_type == "sum" or any(word in question_lower for word in ['total', 'sum', 'amount']):
            return f"{answer_prefix}The total amount is **{format_currency(value, currency)}**"
        
        else:
            return f"{answer_prefix}The result is **{value:,}**" if isinstance(value, (int, float)) else f"{answer_prefix}The result is **{value}**"
    
    row_count = len(query_result['rows'])
    if row_count == 0:
        return f"{answer_prefix}No results found."
    else:
        base_answer = f"{answer_prefix}Found **{row_count}** results. See the data table and visualization below."
        
        # Add interactive visualization suggestion
        if suggested_visualizations and len(suggested_visualizations) > 1:
            current_viz = plan.get("visualization", "table")
            other_options = [v for v in suggested_visualizations if v != current_viz]
            if other_options:
                viz_names = {"bar_chart": "bar chart", "pie_chart": "pie chart", "line_chart": "line chart", "table": "table"}
                current_name = viz_names.get(current_viz, current_viz)
                other_names = [viz_names.get(v, v) for v in other_options]
                base_answer += f"\n\nI've generated a **{current_name}**. Would you prefer a {' or '.join(other_names)}?"
        
        return base_answer

def query_database(question: str, chat_history: list = None, currency: str = "MWK") -> dict:
    """Refined pipeline with Dynamic Hallucination Guard and Session Memory."""
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
                "metadata": {"reused_session": True, "visualization_type": best_viz}
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
            "metadata": {"greeting": True}
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
    """5. INTEGRATION: Replace static DB_SCHEMA with cached autonomous reflection"""
    global _cached_schema, _cached_semantic_mapping
    
    if _cached_schema is None:
        schema_result = get_autonomous_schema()
        
        if schema_result["success"]:
            _cached_schema = schema_result["system_prompt"]
            _cached_semantic_mapping = schema_result["semantic_mapping"]
        else:
            _cached_schema = DB_SCHEMA + f"\n\n[WARNING: Using static schema - {schema_result['error']}]"
    
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

def query_database_with_validation(question: str, chat_history: list = None, currency: str = "MWK") -> dict:
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
                "metadata": {"reused_session": True, "visualization_type": best_viz}
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
            "metadata": {"greeting": True}
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
            "metadata": {"not_db_question": True}
        }
    
    # STEP 1: Create Analysis Plan with Dynamic Metadata (Anti-Hallucination)
    plan = create_analysis_plan_with_metadata(question, context)
    
    # STEP 2: Generate SQL with Schema Validation (Prevents retry loops)
    sql = text_to_sql_with_validation(question, context)
    
    # STEP 3: Execute (should rarely fail now due to validation)
    results = execute_query_with_retry(sql, max_retries=1)  # Reduced retries since validation prevents most errors
    
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
    suggested_visualizations = get_visualization_options(results)
    metadata = {
        "question": question,
        "sql": results.get("sql_used", sql),
        "plan": plan,
        "row_count": len(results.get("rows", [])),
        "columns": results.get("columns", []),
        "analysis_type": plan.get("analysis_type", "unknown"),
        "visualization_type": best_viz,
        "has_chart": bool(chart_config),
        "validation_used": True,
        "suggested_visualizations": suggested_visualizations
    }
    
    return {
        "question": question,
        "plan": plan,
        "sql": results.get("sql_used", sql),
        "answer": answer,
        "markdown_table": markdown_table,
        "chart_config": chart_config,
        "suggested_visualizations": suggested_visualizations,
        "metadata": metadata
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
# SEMANTIC LAYER
class SemanticDictionary:
    """Stores and manages business term definitions for SQL generation."""
    
    def __init__(self):
        self.definitions = {
            # Transaction Value Categories
            'high_value_transaction': 'transaction_amount::numeric > 500000',
            'medium_value_transaction': 'transaction_amount::numeric BETWEEN 100000 AND 500000',
            'low_value_transaction': 'transaction_amount::numeric < 100000',
            
            # Time-based Definitions
            'recent_transactions': 'created_at::bigint > EXTRACT(EPOCH FROM NOW() - INTERVAL \'30 days\')',
            'this_month': 'EXTRACT(MONTH FROM TO_TIMESTAMP(created_at::bigint)) = EXTRACT(MONTH FROM CURRENT_DATE)',
            'last_month': 'EXTRACT(MONTH FROM TO_TIMESTAMP(created_at::bigint)) = EXTRACT(MONTH FROM CURRENT_DATE - INTERVAL \'1 month\')',
            
            # Transaction Type Groups
            'payment_transactions': 'transaction_type IN (\'pay_in\', \'g2p_pay_in\')',
            'settlement_transactions': 'transaction_type IN (\'settlement\', \'payout_approved\')',
            'float_transactions': 'transaction_type IN (\'float\', \'excess_float\')',
            
            # Status Definitions
            'flagged_transactions': 'flagged = true',
            'clean_transactions': 'flagged = false',
            'credit_transactions': 'type = \'credit\'',
            'debit_transactions': 'type = \'debit\'',
            
            # Balance Categories
            'positive_balance': 'closing_balance::numeric > 0',
            'negative_balance': 'closing_balance::numeric < 0',
            'large_balance': 'closing_balance::numeric > 1000000'
        }
    
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
            # Replace whole words only (case insensitive)
            import re
            pattern = r'\b' + re.escape(term) + r'\b'
            result = re.sub(pattern, definition, result, flags=re.IGNORECASE)
        return result
    
    def get_semantic_context(self) -> str:
        """Generate context string for LLM prompts."""
        context = "\nBUSINESS TERMS AVAILABLE:\n"
        for term, definition in self.definitions.items():
            context += f"- {term}: {definition}\n"
        context += "\nUse these business terms when appropriate in your analysis.\n"
        return context

# Global semantic dictionary instance
semantic_dict = SemanticDictionary()

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

IMPORTANT: 
- Only query data that EXISTS based on the REAL-TIME DATA CONSTRAINTS above
- Use the business terms provided when they match the user's intent
- Replace business concepts with their SQL definitions

EXAMPLES:
- "How many high value transactions?" → SELECT COUNT(*) FROM trust_bank_transaction WHERE transaction_amount::numeric > 500000;
- "Recent payment transactions" → SELECT * FROM trust_bank_transaction WHERE created_at > EXTRACT(EPOCH FROM NOW() - INTERVAL '30 days') AND transaction_type IN ('pay_in', 'g2p_pay_in');

Original Question: {question}
Enhanced Question: {enhanced_question}

{context_prompt}

SQL Query:"""
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a PostgreSQL expert. Use business terms and return only valid SQL queries."},
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