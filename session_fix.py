# Minimal fix for session reuse in query_database_with_validation function
# Replace line ~1080 in db_query.py

# OLD CODE:
# if any(word in question_lower for word in ['these', 'those', 'that', 'them']) and session.last_results:

# NEW CODE:
if (any(word in question_lower for word in ['visualize', 'graph', 'chart']) or 
    any(word in question_lower for word in ['these', 'those', 'that', 'them'])) and session.last_results: