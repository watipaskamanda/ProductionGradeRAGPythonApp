import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def check_database():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "paymaart_test"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "testpass"),
            port=os.getenv("DB_PORT", "5432")
        )
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT COUNT(*) FROM trust_bank_transaction")
        count = cursor.fetchone()[0]
        print(f"Total transactions: {count}")
        
        if count > 0:
            # Check date range
            cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM trust_bank_transaction")
            min_date, max_date = cursor.fetchone()
            print(f"Date range: {min_date} to {max_date}")
            
            # Convert timestamps to readable dates
            cursor.execute("SELECT TO_TIMESTAMP(MIN(created_at)::bigint), TO_TIMESTAMP(MAX(created_at)::bigint) FROM trust_bank_transaction")
            min_readable, max_readable = cursor.fetchone()
            print(f"Readable dates: {min_readable} to {max_readable}")
            
            # Check January data specifically
            cursor.execute("SELECT COUNT(*) FROM trust_bank_transaction WHERE EXTRACT(MONTH FROM TO_TIMESTAMP(created_at::bigint)) = 1")
            jan_count = cursor.fetchone()[0]
            print(f"January transactions: {jan_count}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    check_database()