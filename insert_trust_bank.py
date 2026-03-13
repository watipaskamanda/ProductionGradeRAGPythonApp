import pandas as pd
import html

def clean_and_insert_trust_bank_data():
    """Clean trust_bank_transaction data and insert into RAG database"""
    
    # File paths
    input_file = r"C:\Users\watip\Downloads\trust_bank_transaction.txt"
    
    try:
        print("Reading trust_bank_transaction data...")
        df = pd.read_csv(input_file)
        
        print(f"Original data shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        
        # Clean HTML entities and NULL values
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].fillna('')
                df[col] = df[col].astype(str).apply(lambda x: html.unescape(x) if x and x != 'nan' else x)
        
        # Replace various NULL representations
        null_values = ['NULL', 'null', 'nan', '', '""', '"NULL"']
        for null_val in null_values:
            df = df.replace(null_val, None)
        
        # Handle numeric columns - replace empty strings with None
        numeric_columns = [
            'transaction_amount', 'closing_balance', 'closing_balance_ptbat', 
            'sender_closing_balance', 'created_at', 'updated_at'
        ]
        
        for col in numeric_columns:
            if col in df.columns:
                df[col] = df[col].replace(['', '""', 'NULL', 'null'], None)
        
        print(f"Cleaned data shape: {df.shape}")
        print("Sample of cleaned data:")
        print(df.head(2))
        
        # Create table schema (adjust based on your actual columns)
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS trust_bank_transaction (
            id SERIAL PRIMARY KEY,
            paymaart_id VARCHAR(50),
            transaction_id VARCHAR(100),
            transaction_type VARCHAR(50),
            transaction_amount NUMERIC,
            type VARCHAR(20),
            closing_balance NUMERIC,
            closing_balance_ptbat NUMERIC,
            sender_closing_balance NUMERIC,
            description TEXT,
            created_at BIGINT,
            updated_at BIGINT,
            status VARCHAR(50),
            reference VARCHAR(100),
            sender_id VARCHAR(50),
            receiver_id VARCHAR(50)
        );
        """
        
        print("Table schema created (adjust columns as needed):")
        print(create_table_sql)
        
        # Save cleaned data to CSV for manual inspection
        cleaned_file = r"C:\Users\watip\Downloads\trust_bank_transaction_cleaned.csv"
        df.to_csv(cleaned_file, index=False, na_rep='')
        
        print(f"Cleaned data saved to: {cleaned_file}")
        print("You can now:")
        print("1. Review the cleaned data")
        print("2. Adjust the table schema if needed")
        print("3. Import using DBeaver or psql")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = clean_and_insert_trust_bank_data()
    
    if success:
        print("\nNext steps:")
        print("1. Connect to your RAG database")
        print("2. Create the trust_bank_transaction table")
        print("3. Import the cleaned CSV file")
    else:
        print("Data cleaning failed!")