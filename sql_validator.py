def validate_sql_syntax(sql: str) -> dict:
    """SQL Validator: Check syntax before database execution."""
    sql = sql.strip()
    
    # Check for hanging clauses
    hanging_clauses = ['GROUP BY', 'ORDER BY', 'WHERE', 'HAVING']
    for clause in hanging_clauses:
        if sql.upper().endswith(clause):
            return {"valid": False, "error": f"SQL ends with hanging {clause} clause", "corrected_sql": None}
    
    # Check GROUP BY issues
    if 'GROUP BY' in sql.upper():
        # Extract SELECT columns (simplified regex)
        import re
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_part = select_match.group(1)
            # Find non-aggregated columns
            columns = [col.strip() for col in select_part.split(',')]
            non_agg_cols = []
            for col in columns:
                if not any(func in col.upper() for func in ['COUNT(', 'SUM(', 'AVG(', 'MAX(', 'MIN(']):
                    # Clean column name
                    clean_col = col.split(' AS ')[0].strip()
                    if clean_col != '*':
                        non_agg_cols.append(clean_col)
            
            # Check if GROUP BY exists and has columns
            group_by_match = re.search(r'GROUP BY\s+(.*?)(?:\s+ORDER|\s+HAVING|\s*$)', sql, re.IGNORECASE)
            if group_by_match:
                group_cols = [col.strip() for col in group_by_match.group(1).split(',')]
                # If we have non-aggregated columns not in GROUP BY, auto-correct
                missing_cols = [col for col in non_agg_cols if col not in ' '.join(group_cols)]
                if missing_cols:
                    corrected_sql = sql.replace(group_by_match.group(0), f"GROUP BY {', '.join(non_agg_cols)}")
                    return {"valid": False, "error": "Missing columns in GROUP BY", "corrected_sql": corrected_sql}
    
    return {"valid": True, "error": None, "corrected_sql": None}

def execute_query_with_validation(sql: str, max_retries: int = 2):
    """Execute SQL with validation and automatic error correction."""
    # STEP 1: Validate syntax first
    validation = validate_sql_syntax(sql)
    if not validation["valid"]:
        if validation["corrected_sql"]:
            print(f"SQL Validation: {validation['error']} - Auto-correcting")
            sql = validation["corrected_sql"]
        else:
            return {"error": f"SQL Validation Failed: {validation['error']}", "sql_used": sql, "attempts": 0}
    
    # STEP 2: Execute with retry (existing logic)
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