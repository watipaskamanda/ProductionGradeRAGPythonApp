# Fix for SQL type mismatch in db_query.py
# Replace COALESCE usage with proper casting

# PROBLEM: 
# COALESCE(transaction_amount, 0)::numeric

# SOLUTION:
# COALESCE(transaction_amount::numeric, 0)

# Apply this pattern wherever transaction_amount is used with COALESCE
# Cast to numeric BEFORE the COALESCE operation, not after