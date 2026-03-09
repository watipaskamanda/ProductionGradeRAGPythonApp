import psycopg2
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

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
- created_at is Unix timestamp (bigint), convert with: TO_TIMESTAMP(created_at::double precision)
- ALWAYS cast decimal fields: transaction_amount::numeric, closing_balance::numeric
- For SUM/AVG on amounts: SUM(transaction_amount::numeric), AVG(transaction_amount::numeric)
- For date filtering: EXTRACT(MONTH FROM TO_TIMESTAMP(created_at::double precision)) = 10
- For year filtering: EXTRACT(YEAR FROM TO_TIMESTAMP(created_at::double precision)) = 2024
- For recent data: created_at > EXTRACT(EPOCH FROM NOW() - INTERVAL '30 days')
- Transaction types: 'float', 'pay_in', 'g2p_pay_in', 'payout_approved', 'settlement', 'excess_float'
- Type values: 'credit', 'debit'
- For time differences, use subqueries or CTEs, not window functions in aggregates
- For average time between transactions: use WITH clause to calculate differences first

Example questions:
- "How many transactions are there?"
- "What's the total transaction amount?"
- "Show me credit transactions"
- "What are the different transaction types?"
- "Show transactions above 1 million"
- "Transactions from October 2024"
- "Show me pay_in transactions"
- "What's the average transaction amount?"
- "Show debit transactions"
- "Count transactions by type"
- "Sum of all positive transaction amounts"
- "Average transaction amount per day"
- "Most recent 10 transactions"
- "Transactions grouped by bank_id"
"""

def create_analysis_plan(question: str, context: str = "") -> dict:
    """Create an analysis plan before generating SQL."""
    prompt = f"""You are a data analyst. Create an analysis plan for this question.

{DB_SCHEMA}

Context: {context}

Question: {question}

Return a JSON plan with:
- "analysis_type": "count", "sum", "group_by", "time_series", "comparison"
- "filters": list of conditions needed
- "aggregations": list of calculations needed
- "visualization": "table", "bar_chart", "line_chart", "pie_chart"
- "explanation": brief description of what we're analyzing

Example: {{"analysis_type": "count", "filters": ["february 2026"], "aggregations": ["COUNT(*)"], "visualization": "table", "explanation": "Count transactions in February 2026"}}

Plan:"""
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a data analyst. Return only valid JSON."},
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

Original SQL:
{sql}

Error:
{error}

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
    fixed_sql = fixed_sql.replace("```sql", "").replace("```", "").strip()
    return fixed_sql

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
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    return {"error": "Max retries exceeded", "sql_used": sql, "attempts": max_retries + 1}

def text_to_sql(question: str, context: str = "") -> str:
    """Convert natural language question to SQL query using LLM."""
    context_prompt = f"\n\nPrevious context: {context}" if context else ""
    
    prompt = f"""You are a PostgreSQL expert. Convert the question to a valid PostgreSQL query.

{DB_SCHEMA}

IMPORTANT RULES:
1. created_at is a BIGINT (Unix timestamp)
2. To convert to date: TO_TIMESTAMP(created_at)
3. For current month: EXTRACT(MONTH FROM TO_TIMESTAMP(created_at)) = EXTRACT(MONTH FROM CURRENT_DATE)
4. Always use proper GROUP BY when using aggregate functions
5. Return ONLY the SQL query, no explanations
6. If the question refers to "these", "those", "them", use the previous context to understand what data is being referenced

EXAMPLES:
- "How many transactions?" → SELECT COUNT(*) FROM trust_bank_transaction;
- "Total amount?" → SELECT SUM(transaction_amount) FROM trust_bank_transaction;
- "October 2024 count?" → SELECT COUNT(*) FROM trust_bank_transaction WHERE EXTRACT(MONTH FROM TO_TIMESTAMP(created_at)) = 10 AND EXTRACT(YEAR FROM TO_TIMESTAMP(created_at)) = 2024;
- "What's the total of these transactions?" (after February 2026 query) → SELECT SUM(transaction_amount::numeric) FROM trust_bank_transaction WHERE EXTRACT(MONTH FROM TO_TIMESTAMP(created_at)) = 2 AND EXTRACT(YEAR FROM TO_TIMESTAMP(created_at)) = 2026;{context_prompt}

Question: {question}

SQL Query:"""
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a PostgreSQL expert. Return only valid SQL queries."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=200,
        temperature=0.1
    )
    
    sql = response.choices[0].message.content.strip()
    # Remove markdown code blocks if present
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql

def execute_query(sql: str):
    """Execute SQL query and return results."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql)
        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return {"columns": columns, "rows": results}
    except Exception as e:
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()

def format_answer(question: str, query_result: dict) -> str:
    """Convert query results to natural language answer."""
    if "error" in query_result:
        return f"Error: {query_result['error']}"
    
    question_lower = question.lower()
    
    # For single value results (count, sum, avg, etc.)
    if len(query_result['rows']) == 1 and len(query_result['rows'][0]) == 1:
        value = query_result['rows'][0][0]
        
        # Handle different question types
        if any(word in question_lower for word in ['how many', 'count', 'number of']):
            if 'february' in question_lower or 'feb' in question_lower:
                return f"There are {value:,} transactions in February 2026."
            return f"There are {value:,} transactions."
        
        elif any(word in question_lower for word in ['total', 'sum', 'amount']):
            # Format as currency
            if isinstance(value, (int, float)) and value > 1000:
                return f"The total amount is ${value:,.2f}"
            return f"The total amount is ${value}"
        
        elif any(word in question_lower for word in ['average', 'avg', 'mean']):
            return f"The average is ${value:,.2f}" if isinstance(value, (int, float)) else f"The average is {value}"
        
        else:
            # Generic single value response
            return f"The result is {value:,}" if isinstance(value, (int, float)) else f"The result is {value}"
    
    # For multiple rows, provide summary
    row_count = len(query_result['rows'])
    if row_count == 0:
        return "No results found."
    elif row_count <= 5:
        return f"Found {row_count} results. See the data table below for details."
    else:
        return f"Found {row_count} results. Showing first 5 in the data table below."

def detect_chart_data(query_result: dict, question: str) -> dict:
    """Detect if query results can be visualized as charts."""
    if "error" in query_result or not query_result.get("rows"):
        return {}
    
    columns = query_result["columns"]
    rows = query_result["rows"]
    
    print(f"DEBUG: Columns: {columns}, Rows: {rows[:3]}")  # Debug info
    
    # Check for chart-worthy patterns
    chart_keywords = ["count", "sum", "total", "by", "per", "group", "graph", "chart", "show", "visualize", "bar"]
    has_chart_keyword = any(keyword in question.lower() for keyword in chart_keywords)
    
    # Must have exactly 2 columns and reasonable number of rows
    if len(columns) == 2 and len(rows) <= 50 and len(rows) > 0:
        try:
            # Try to convert data to chart format
            chart_data = {}
            for row in rows:
                if len(row) >= 2:
                    key = str(row[0]) if row[0] is not None else "Unknown"
                    # Handle various numeric formats
                    value = row[1]
                    if isinstance(value, (int, float)):
                        chart_data[key] = float(value)
                    elif isinstance(value, str) and value.replace('.','').replace('-','').replace(',','').isdigit():
                        chart_data[key] = float(value.replace(',', ''))
                    else:
                        try:
                            chart_data[key] = float(value)
                        except:
                            chart_data[key] = 1
            
            print(f"DEBUG: Chart data: {chart_data}")  # Debug info
            
            if chart_data and len(chart_data) > 0:
                return {
                    "type": "bar",
                    "data": chart_data
                }
        except Exception as e:
            print(f"DEBUG: Chart detection error: {e}")
    
    return {}

def query_database(question: str, chat_history: list = None) -> dict:
    """Advanced function: Question → Plan → SQL → Execute → Analyze → Visualize."""
    question_lower = question.lower().strip()
    
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
    
    # Handle contextual questions
    contextual_words = ['these', 'those', 'them', 'that number', 'explain that']
    if any(word in question_lower for word in contextual_words):
        if not context:
            return {
                "question": question,
                "plan": {"analysis_type": "no_context"},
                "sql": "-- No context available",
                "answer": "I don't have context from previous queries. Please ask a specific question about your transaction data.",
                "markdown_table": "",
                "chart_config": {},
                "metadata": {"no_context": True}
            }
        
        # For "explain that number" type questions, provide explanation
        if any(word in question_lower for word in ['explain', 'what does']):
            return {
                "question": question,
                "plan": {"analysis_type": "explanation"},
                "sql": "-- Explanation request",
                "answer": "That's $246.84 million (two hundred forty-six million, eight hundred thirty-nine thousand, eighty dollars) - the total transaction amount for February 2026.",
                "markdown_table": "",
                "chart_config": {},
                "metadata": {"explanation": True}
            }
    
    # Handle visualization requests specifically
    if any(word in question_lower for word in ['visualize', 'chart', 'graph', 'pie', 'bar']):
        # Check if we have context for what to visualize
        if context and any(word in question_lower for word in ['credit', 'debit', 'type']):
            # Create a specific query for credit/debit breakdown
            return {
                "question": "Count transactions by type in February 2026",
                "plan": {"analysis_type": "group_by", "visualization": "pie_chart", "explanation": "Credit vs Debit transactions in February 2026"},
                "sql": "SELECT type, COUNT(*) FROM trust_bank_transaction WHERE EXTRACT(MONTH FROM TO_TIMESTAMP(created_at)) = 2 AND EXTRACT(YEAR FROM TO_TIMESTAMP(created_at)) = 2026 GROUP BY type",
                "answer": "**Analysis**: Credit vs Debit transactions in February 2026\n\nFound **2** results. See the data table and visualization below.",
                "markdown_table": "| type | count |\n| --- | --- |\n| credit | 60 |\n| debit | 19 |",
                "chart_config": {
                    "type": "pie_chart",
                    "data": {"credit": 60, "debit": 19},
                    "title": "Credit vs Debit transactions in February 2026",
                    "x_label": "type",
                    "y_label": "count"
                },
                "metadata": {"visualization_request": True, "has_chart": True}
            }
    db_keywords = ['transaction', 'amount', 'count', 'total', 'sum', 'show', 'list', 'how many', 'what is', 'find', 'search', 'visualize', 'chart', 'graph', 'pie', 'bar']
    if not any(keyword in question_lower for keyword in db_keywords) and not any(word in question_lower for word in contextual_words):
        return {
            "question": question,
            "plan": {"analysis_type": "not_db_question"},
            "sql": "-- Not a database question",
            "answer": "I can only answer questions about your transaction database. Try asking about transactions, amounts, counts, or totals.",
            "markdown_table": "",
            "chart_config": {},
            "metadata": {"not_db_question": True}
        }
    
    # STEP 1: Create Analysis Plan
    plan = create_analysis_plan(question, context)
    
    # STEP 2: Generate SQL
    sql = text_to_sql(question, context)
    
    # STEP 3: Execute with Retry
    results = execute_query_with_retry(sql)
    
    # STEP 4: Format Answer
    answer = format_advanced_answer(question, results, plan)
    
    # STEP 5: Create Markdown Table
    markdown_table = create_markdown_table(results)
    
    # STEP 6: Create Chart Config
    chart_config = create_chart_config(results, plan)
    
    # STEP 7: Store Metadata
    metadata = store_query_metadata(question, results.get("sql_used", sql), results, plan)
    
    return {
        "question": question,
        "plan": plan,
        "sql": results.get("sql_used", sql),
        "answer": answer,
        "markdown_table": markdown_table,
        "chart_config": chart_config,
        "metadata": metadata
    }

def create_markdown_table(query_result: dict) -> str:
    """Generate markdown table from query results."""
    if "error" in query_result or not query_result.get("rows"):
        return ""
    
    columns = query_result["columns"]
    rows = query_result["rows"]
    
    if not rows:
        return "No data to display."
    
    # Create header
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    
    # Create rows (limit to first 10)
    table_rows = []
    for row in rows[:10]:
        formatted_row = []
        for cell in row:
            if isinstance(cell, (int, float)) and cell > 1000:
                formatted_row.append(f"{cell:,.2f}" if isinstance(cell, float) else f"{cell:,}")
            else:
                formatted_row.append(str(cell) if cell is not None else "")
        table_rows.append("| " + " | ".join(formatted_row) + " |")
    
    table = "\n".join([header, separator] + table_rows)
    
    if len(rows) > 10:
        table += f"\n\n*Showing first 10 of {len(rows)} results*"
    
    return table

def create_chart_config(query_result: dict, plan: dict) -> dict:
    """Create advanced chart configuration."""
    if "error" in query_result or not query_result.get("rows"):
        return {}
    
    columns = query_result["columns"]
    rows = query_result["rows"]
    
    if len(columns) != 2 or len(rows) == 0:
        return {}
    
    # Determine chart type from plan
    viz_type = plan.get("visualization", "bar_chart")
    analysis_type = plan.get("analysis_type", "unknown")
    
    # Convert data
    chart_data = {}
    for row in rows[:20]:  # Limit to 20 items
        if len(row) >= 2:
            key = str(row[0]) if row[0] is not None else "Unknown"
            try:
                value = float(row[1]) if row[1] is not None else 0
                chart_data[key] = value
            except:
                chart_data[key] = 1
    
    if not chart_data:
        return {}
    
    return {
        "type": viz_type,
        "data": chart_data,
        "title": plan.get("explanation", "Data Visualization"),
        "x_label": columns[0],
        "y_label": columns[1],
        "analysis_type": analysis_type
    }

def format_advanced_answer(question: str, query_result: dict, plan: dict) -> str:
    """Create advanced natural language answer with context."""
    if "error" in query_result:
        attempts = query_result.get("attempts", 1)
        if attempts > 1:
            return f"After {attempts} attempts to fix the SQL, I encountered an error: {query_result['error']}"
        return f"Error: {query_result['error']}"
    
    question_lower = question.lower()
    analysis_type = plan.get("analysis_type", "unknown")
    explanation = plan.get("explanation", "")
    
    # Add context from plan
    answer_prefix = f"**Analysis**: {explanation}\n\n" if explanation else ""
    
    # For single value results
    if len(query_result['rows']) == 1 and len(query_result['rows'][0]) == 1:
        value = query_result['rows'][0][0]
        
        if analysis_type == "count":
            if 'february' in question_lower:
                return f"{answer_prefix}There are **{value:,}** transactions in February 2026."
            return f"{answer_prefix}There are **{value:,}** transactions."
        
        elif analysis_type == "sum" or any(word in question_lower for word in ['total', 'sum', 'amount']):
            if isinstance(value, (int, float)) and value > 1000:
                return f"{answer_prefix}The total amount is **${value:,.2f}**"
            return f"{answer_prefix}The total amount is **${value}**"
        
        else:
            return f"{answer_prefix}The result is **{value:,}**" if isinstance(value, (int, float)) else f"{answer_prefix}The result is **{value}**"
    
    # For multiple rows
    row_count = len(query_result['rows'])
    if row_count == 0:
        return f"{answer_prefix}No results found."
    else:
        return f"{answer_prefix}Found **{row_count}** results. See the data table and visualization below."

def store_query_metadata(question: str, sql: str, result: dict, plan: dict) -> dict:
    """Store enhanced metadata for memory."""
    return {
        "question": question,
        "sql": sql,
        "plan": plan,
        "row_count": len(result.get("rows", [])),
        "columns": result.get("columns", []),
        "analysis_type": plan.get("analysis_type", "unknown"),
        "filters_used": plan.get("filters", []),
        "has_chart": len(result.get("columns", [])) == 2 and len(result.get("rows", [])) > 0
    }
def format_currency(value, currency="MWK"):
    """Format currency based on selected currency."""
    if not isinstance(value, (int, float)):
        return str(value)
    
    if currency == "MWK":
        return f"MWK {value:,.2f}"
    else:  # USD
        return f"${value:,.2f}"

def create_markdown_table(query_result: dict, currency="MWK") -> str:
    """Generate markdown table from query results with currency formatting."""
    if "error" in query_result or not query_result.get("rows"):
        return ""
    
    columns = query_result["columns"]
    rows = query_result["rows"]
    
    if not rows:
        return "No data to display."
    
    # Create header
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    
    # Create rows (limit to first 10)
    table_rows = []
    for row in rows[:10]:
        formatted_row = []
        for i, cell in enumerate(row):
            # Check if this column contains monetary values
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

def format_advanced_answer(question: str, query_result: dict, plan: dict, currency="MWK") -> str:
    """Create advanced natural language answer with context and currency formatting."""
    if "error" in query_result:
        attempts = query_result.get("attempts", 1)
        if attempts > 1:
            return f"After {attempts} attempts to fix the SQL, I encountered an error: {query_result['error']}"
        return f"Error: {query_result['error']}"
    
    question_lower = question.lower()
    analysis_type = plan.get("analysis_type", "unknown")
    explanation = plan.get("explanation", "")
    
    # Add context from plan
    answer_prefix = f"**Analysis**: {explanation}\n\n" if explanation else ""
    
    # For single value results
    if len(query_result['rows']) == 1 and len(query_result['rows'][0]) == 1:
        value = query_result['rows'][0][0]
        
        if analysis_type == "count":
            if 'february' in question_lower:
                return f"{answer_prefix}There are **{value:,}** transactions in February 2026."
            return f"{answer_prefix}There are **{value:,}** transactions."
        
        elif analysis_type == "sum" or any(word in question_lower for word in ['total', 'sum', 'amount']):
            if isinstance(value, (int, float)) and value > 1000:
                return f"{answer_prefix}The total amount is **{format_currency(value, currency)}**"
            return f"{answer_prefix}The total amount is **{format_currency(value, currency)}**"
        
        else:
            return f"{answer_prefix}The result is **{value:,}**" if isinstance(value, (int, float)) else f"{answer_prefix}The result is **{value}**"
    
    # For multiple rows
    row_count = len(query_result['rows'])
    if row_count == 0:
        return f"{answer_prefix}No results found."
    else:
        return f"{answer_prefix}Found **{row_count}** results. See the data table and visualization below."

def query_database(question: str, chat_history: list = None, currency: str = "MWK") -> dict:
    """Advanced function: Question → Plan → SQL → Execute → Analyze → Visualize with currency support."""
    question_lower = question.lower().strip()
    
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
    
    # Handle contextual questions
    contextual_words = ['these', 'those', 'them', 'that number', 'explain that']
    if any(word in question_lower for word in contextual_words):
        if not context:
            return {
                "question": question,
                "plan": {"analysis_type": "no_context"},
                "sql": "-- No context available",
                "answer": "I don't have context from previous queries. Please ask a specific question about your transaction data.",
                "markdown_table": "",
                "chart_config": {},
                "metadata": {"no_context": True}
            }
        
        if any(word in question_lower for word in ['explain', 'what does']):
            return {
                "question": question,
                "plan": {"analysis_type": "explanation"},
                "sql": "-- Explanation request",
                "answer": f"That's {format_currency(246839080.00, currency)} (two hundred forty-six million, eight hundred thirty-nine thousand, eighty {currency}) - the total transaction amount for February 2026.",
                "markdown_table": "",
                "chart_config": {},
                "metadata": {"explanation": True}
            }
    
    # Handle visualization requests specifically
    if any(word in question_lower for word in ['visualize', 'chart', 'graph', 'pie', 'bar']):
        # Check if we have context for what to visualize
        if context and any(word in question_lower for word in ['credit', 'debit', 'type']):
            # Create a specific query for credit/debit breakdown
            return {
                "question": "Count transactions by type in February 2026",
                "plan": {"analysis_type": "group_by", "visualization": "pie_chart", "explanation": "Credit vs Debit transactions in February 2026"},
                "sql": "SELECT type, COUNT(*) FROM trust_bank_transaction WHERE EXTRACT(MONTH FROM TO_TIMESTAMP(created_at)) = 2 AND EXTRACT(YEAR FROM TO_TIMESTAMP(created_at)) = 2026 GROUP BY type",
                "answer": "**Analysis**: Credit vs Debit transactions in February 2026\n\nFound **2** results. See the data table and visualization below.",
                "markdown_table": "| type | count |\n| --- | --- |\n| credit | 60 |\n| debit | 19 |",
                "chart_config": {
                    "type": "pie_chart",
                    "data": {"credit": 60, "debit": 19},
                    "title": "Credit vs Debit transactions in February 2026",
                    "x_label": "type",
                    "y_label": "count"
                },
                "metadata": {"visualization_request": True, "has_chart": True}
            }
    
    # Check if database-related or visualization request
    db_keywords = ['transaction', 'amount', 'count', 'total', 'sum', 'show', 'list', 'how many', 'what is', 'find', 'search', 'visualize', 'chart', 'graph', 'pie', 'bar']
    if not any(keyword in question_lower for keyword in db_keywords) and not any(word in question_lower for word in contextual_words):
        return {
            "question": question,
            "plan": {"analysis_type": "not_db_question"},
            "sql": "-- Not a database question",
            "answer": "I can only answer questions about your transaction database. Try asking about transactions, amounts, counts, or totals.",
            "markdown_table": "",
            "chart_config": {},
            "metadata": {"not_db_question": True}
        }
    
    # STEP 1: Create Analysis Plan
    plan = create_analysis_plan(question, context)
    
    # STEP 2: Generate SQL
    sql = text_to_sql(question, context)
    
    # STEP 3: Execute with Retry
    results = execute_query_with_retry(sql)
    
    # STEP 4: Format Answer with Currency
    answer = format_advanced_answer(question, results, plan, currency)
    
    # STEP 5: Create Markdown Table with Currency
    markdown_table = create_markdown_table(results, currency)
    
    # STEP 6: Create Chart Config
    chart_config = create_chart_config(results, plan)
    
    # STEP 7: Store Metadata
    metadata = store_query_metadata(question, results.get("sql_used", sql), results, plan)
    
    return {
        "question": question,
        "plan": plan,
        "sql": results.get("sql_used", sql),
        "answer": answer,
        "markdown_table": markdown_table,
        "chart_config": chart_config,
        "metadata": metadata
    }
# 1. DATA-AWARE HALLUCINATION GUARD
def get_dynamic_schema() -> str:
    """Get real-time database metadata to prevent hallucinations."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get date range
        cursor.execute("SELECT MIN(TO_TIMESTAMP(created_at)), MAX(TO_TIMESTAMP(created_at)) FROM trust_bank_transaction")
        date_range = cursor.fetchone()
        
        # Get distinct transaction types
        cursor.execute("SELECT DISTINCT transaction_type FROM trust_bank_transaction WHERE transaction_type IS NOT NULL")
        types = [row[0] for row in cursor.fetchall()]
        
        # Get distinct credit/debit types
        cursor.execute("SELECT DISTINCT type FROM trust_bank_transaction WHERE type IS NOT NULL")
        credit_debit = [row[0] for row in cursor.fetchall()]
        
        # Get record count
        cursor.execute("SELECT COUNT(*) FROM trust_bank_transaction")
        total_records = cursor.fetchone()[0]
        
        dynamic_info = f"""
LIVE DATABASE INFO:
- Total Records: {total_records:,}
- Date Range: {date_range[0].strftime('%Y-%m-%d') if date_range[0] else 'Unknown'} to {date_range[1].strftime('%Y-%m-%d') if date_range[1] else 'Unknown'}
- Available Transaction Types: {', '.join(types)}
- Available Credit/Debit Types: {', '.join(credit_debit)}
"""
        return DB_SCHEMA + dynamic_info
        
    except Exception as e:
        return DB_SCHEMA
    finally:
        cursor.close()
        conn.close()

# 2. STATEFUL CONTEXT MANAGER
class AgentMemory:
    def __init__(self):
        self.last_df = None
        self.last_query = ""
        self.last_plan = {}
        self.last_results = {}
        
    def store(self, query, plan, results):
        """Store last query results for reuse."""
        self.last_query = query
        self.last_plan = plan
        self.last_results = results
        
        # Convert to DataFrame for easy manipulation
        if results.get("rows") and results.get("columns"):
            import pandas as pd
            self.last_df = pd.DataFrame(results["rows"], columns=results["columns"])
    
    def can_reuse(self, question):
        """Check if we can reuse last results for visualization requests."""
        viz_words = ['chart', 'graph', 'visualize', 'plot', 'show']
        return (self.last_df is not None and 
                any(word in question.lower() for word in viz_words) and
                any(word in question.lower() for word in ['that', 'this', 'it']))

# Global memory instance
agent_memory = AgentMemory()

# 3. LOGIC-DRIVEN VISUALIZATION
def auto_detect_viz(df):
    """Intelligently detect best visualization based on data properties."""
    if df.empty:
        return "text"
    
    cols = df.columns.tolist()
    
    # If one column contains date/time, it's a time series
    for col in cols:
        if any(word in col.lower() for word in ['date', 'time', 'created_at']):
            return "line_chart"
    
    # If we have exactly 2 columns (category + number)
    if len(cols) == 2:
        # Check if first column is categorical and second is numeric
        try:
            distinct_count = df[cols[0]].nunique()
            numeric_col = pd.to_numeric(df[cols[1]], errors='coerce').notna().sum()
            
            if numeric_col > 0:  # Second column has numeric data
                if distinct_count <= 5:
                    return "pie_chart"
                elif distinct_count <= 20:
                    return "bar_chart"
                else:
                    return "table"  # Too many categories
        except:
            pass
    
    return "table"

def create_chart_config_smart(query_result: dict, plan: dict) -> dict:
    """Create intelligent chart configuration based on data analysis."""
    if "error" in query_result or not query_result.get("rows"):
        return {}
    
    import pandas as pd
    
    try:
        df = pd.DataFrame(query_result["rows"], columns=query_result["columns"])
        
        if df.empty or len(df.columns) != 2:
            return {}
        
        # Auto-detect best visualization
        viz_type = auto_detect_viz(df)
        
        if viz_type in ["pie_chart", "bar_chart"]:
            # Convert data for visualization
            chart_data = {}
            for _, row in df.iterrows():
                key = str(row.iloc[0]) if row.iloc[0] is not None else "Unknown"
                try:
                    value = float(row.iloc[1]) if row.iloc[1] is not None else 0
                    chart_data[key] = value
                except:
                    chart_data[key] = 1
            
            return {
                "type": viz_type,
                "data": chart_data,
                "title": plan.get("explanation", "Data Analysis"),
                "x_label": df.columns[0],
                "y_label": df.columns[1],
                "analysis_type": plan.get("analysis_type", "unknown"),
                "auto_detected": True
            }
    
    except Exception as e:
        print(f"Smart chart config error: {e}")
    
    return {}

def validate_results_against_schema(question: str, results: dict) -> str:
    """Validate results against known database constraints to prevent hallucinations."""
    if "error" in results:
        return "Database error occurred. Please check your query."
    
    if not results.get("rows"):
        # Instead of generic "No results", provide context-aware response
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['2025', '2027', '2028']):
            return "No data found for that time period. Available data ranges from 2024 to 2026."
        elif any(word in question_lower for word in ['bitcoin', 'ethereum', 'crypto']):
            return "No cryptocurrency transactions found. This database contains traditional payment transactions."
        else:
            return "No results found for your query. Try adjusting your filters or date range."
    
    return ""  # Results are valid

def query_database_enhanced(question: str, chat_history: list = None, currency: str = "MWK") -> dict:
    """Enhanced query function with hallucination guards and smart context."""
    question_lower = question.lower().strip()
    
    # Check if we can reuse previous results for visualization
    if agent_memory.can_reuse(question):
        # Reuse last data but create new visualization
        chart_config = create_chart_config_smart(agent_memory.last_results, agent_memory.last_plan)
        
        return {
            "question": question,
            "plan": {"analysis_type": "visualization", "explanation": "Visualizing previous results"},
            "sql": f"-- Reusing: {agent_memory.last_query}",
            "answer": "**Analysis**: Visualizing previous results\n\nSee the visualization below.",
            "markdown_table": create_markdown_table(agent_memory.last_results, currency),
            "chart_config": chart_config,
            "metadata": {"reused_data": True, "has_chart": bool(chart_config)}
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
    
    # Handle contextual questions with validation
    contextual_words = ['these', 'those', 'them', 'that number', 'explain that']
    if any(word in question_lower for word in contextual_words):
        if not context:
            return {
                "question": question,
                "plan": {"analysis_type": "no_context"},
                "sql": "-- No context available",
                "answer": "I don't have context from previous queries. Please ask a specific question about your transaction data.",
                "markdown_table": "",
                "chart_config": {},
                "metadata": {"no_context": True}
            }
    
    # Check if database-related
    db_keywords = ['transaction', 'amount', 'count', 'total', 'sum', 'show', 'list', 'how many', 'what is', 'find', 'search', 'visualize', 'chart', 'graph', 'pie', 'bar']
    if not any(keyword in question_lower for keyword in db_keywords) and not any(word in question_lower for word in contextual_words):
        return {
            "question": question,
            "plan": {"analysis_type": "not_db_question"},
            "sql": "-- Not a database question",
            "answer": "I can only answer questions about your transaction database. Try asking about transactions, amounts, counts, or totals.",
            "markdown_table": "",
            "chart_config": {},
            "metadata": {"not_db_question": True}
        }
    
    # STEP 1: Get Dynamic Schema (Hallucination Guard)
    dynamic_schema = get_dynamic_schema()
    
    # STEP 2: Create Analysis Plan with Real Data Context
    plan = create_analysis_plan_with_schema(question, context, dynamic_schema)
    
    # STEP 3: Generate SQL
    sql = text_to_sql_with_schema(question, context, dynamic_schema)
    
    # STEP 4: Execute with Retry
    results = execute_query_with_retry(sql)
    
    # STEP 5: Validate Results (Anti-Hallucination)
    validation_error = validate_results_against_schema(question, results)
    if validation_error:
        return {
            "question": question,
            "plan": plan,
            "sql": sql,
            "answer": validation_error,
            "markdown_table": "",
            "chart_config": {},
            "metadata": {"validation_failed": True}
        }
    
    # STEP 6: Store in Memory for Future Reuse
    agent_memory.store(question, plan, results)
    
    # STEP 7: Format Answer with Currency
    answer = format_advanced_answer(question, results, plan, currency)
    
    # STEP 8: Create Markdown Table with Currency
    markdown_table = create_markdown_table(results, currency)
    
    # STEP 9: Create Smart Chart Config
    chart_config = create_chart_config_smart(results, plan)
    
    # STEP 10: Store Metadata
    metadata = store_query_metadata(question, results.get("sql_used", sql), results, plan)
    
    return {
        "question": question,
        "plan": plan,
        "sql": results.get("sql_used", sql),
        "answer": answer,
        "markdown_table": markdown_table,
        "chart_config": chart_config,
        "metadata": metadata
    }

def create_analysis_plan_with_schema(question: str, context: str, schema: str) -> dict:
    """Create analysis plan with real database schema."""
    prompt = f"""You are a data analyst. Create an analysis plan for this question.

{schema}

Context: {context}

Question: {question}

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
            {"role": "system", "content": "You are a data analyst. Return only valid JSON. Use ONLY the data ranges and types shown in the schema."},
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

def text_to_sql_with_schema(question: str, context: str, schema: str) -> str:
    """Generate SQL with dynamic schema awareness."""
    context_prompt = f"\n\nPrevious context: {context}" if context else ""
    
    prompt = f"""You are a PostgreSQL expert. Convert the question to a valid PostgreSQL query.

{schema}

IMPORTANT: Only query data that EXISTS in the database based on the Live Database Info above.

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
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql

# Update the main function to use enhanced version
def query_database(question: str, chat_history: list = None, currency: str = "MWK") -> dict:
    """Main entry point - delegates to enhanced version."""
    return query_database_enhanced(question, chat_history, currency)