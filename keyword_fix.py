# Minimal fixes for db_query.py

# 1. EXPAND DB_KEYWORDS (around line 1140)
db_keywords = [
    'transaction', 'amount', 'count', 'total', 'sum', 'show', 'list', 
    'how many', 'what is', 'find', 'search', 'visualize', 'chart', 'graph', 
    'pie', 'bar', 'who', 'biggest', 'top', 'client', 'customer', 'largest', 
    'highest', 'most', 'best', 'worst', 'average', 'mean', 'sender', 'receiver',
    'friday', 'monday', 'tuesday', 'wednesday', 'thursday', 'saturday', 'sunday',
    'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
    'september', 'october', 'november', 'december', 'yesterday', 'today', 'when'
]

# 2. RELAX BUSINESS TERM ENFORCEMENT (in text_to_sql_with_config_enforcement)
# Change this line:
# - If the question uses undefined terms, return: SELECT 'Please clarify your request using defined business terms' as message;

# To this:
# - If the question uses undefined terms, try to interpret using standard SQL patterns, or ask for clarification if completely unclear

# 3. ADD FALLBACK LOGIC
# If business terms don't match, fall back to general SQL generation instead of strict rejection