import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

# Connect directly to Aurora
conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    port=os.getenv('DB_PORT')
)

cursor = conn.cursor()

# Get all tables
cursor.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    ORDER BY table_name;
""")

tables = cursor.fetchall()
print(f'Found {len(tables)} tables in Aurora database:')
for table in tables:
    print(f'  - {table[0]}')

# Get sample data from first few tables
print("\nSample row counts from first 5 tables:")
for i, table in enumerate(tables[:5]):
    table_name = table[0]
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        print(f'  - {table_name}: {count:,} rows')
    except Exception as e:
        print(f'  - {table_name}: Error - {e}')

cursor.close()
conn.close()