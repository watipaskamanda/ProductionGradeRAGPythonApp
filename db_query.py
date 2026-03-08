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

def get_db_connection():
    """Connect to PayMaart test database."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "paymaart_test"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "testpass"),
        port=os.getenv("DB_PORT", "5432")
    )

def text_to_sql(question: str) -> str:
    """Convert natural language question to SQL query using LLM."""
    prompt = f"""You are a SQL expert. Convert the question to a PostgreSQL query.

{DB_SCHEMA}

Question: {question}

Return ONLY the SQL query, nothing else. No explanations.
"""
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a SQL expert. Return only SQL queries."},
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
    
    # Format results as text
    result_text = f"Query returned {len(query_result['rows'])} rows:\n"
    for row in query_result['rows'][:5]:  # Limit to 5 rows
        result_text += f"{row}\n"
    
    # Ask LLM to format nicely
    prompt = f"""Convert this database query result into a natural language answer.

Question: {question}
Results: {result_text}

Provide a clear, concise answer."""
    
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You format database results into natural language."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=200,
        temperature=0.2
    )
    
    return response.choices[0].message.content.strip()

def detect_chart_data(query_result: dict, question: str) -> dict:
    """Detect if query results can be visualized as charts."""
    if "error" in query_result or not query_result.get("rows"):
        return {}
    
    columns = query_result["columns"]
    rows = query_result["rows"]
    
    # Check for chart-worthy patterns
    chart_keywords = ["count", "sum", "total", "by", "per", "group", "graph", "chart", "show"]
    has_chart_keyword = any(keyword in question.lower() for keyword in chart_keywords)
    
    # Must have exactly 2 columns and reasonable number of rows
    if len(columns) == 2 and len(rows) <= 50 and len(rows) > 0:
        try:
            # Try to convert second column to numeric
            chart_data = {}
            for row in rows:
                key = str(row[0]) if row[0] is not None else "Unknown"
                value = float(row[1]) if row[1] is not None and str(row[1]).replace('.','').replace('-','').isdigit() else 1
                chart_data[key] = value
            
            if chart_data and (has_chart_keyword or len(rows) <= 10):
                return {
                    "type": "bar",
                    "data": chart_data
                }
        except (ValueError, TypeError, IndexError):
            pass
    
    return {}

def query_database(question: str) -> dict:
    """Main function: Question → SQL → Execute → Answer."""
    # Convert to SQL
    sql = text_to_sql(question)
    
    # Execute query
    results = execute_query(sql)
    
    # Format answer
    answer = format_answer(question, results)
    
    # Detect chart data
    chart_data = detect_chart_data(results, question)
    
    return {
        "question": question,
        "sql": sql,
        "answer": answer,
        "raw_results": results,
        "chart_data": chart_data
    }
