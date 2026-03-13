import pandas as pd
import html

def clean_csv_for_postgresql(input_file, output_file):
    """Clean CSV data specifically for PostgreSQL import"""
    try:
        print(f"Reading file: {input_file}")
        df = pd.read_csv(input_file)
        
        print(f"Original data shape: {df.shape}")
        
        # Fix HTML entities in all columns
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].fillna('')
                df[col] = df[col].astype(str).apply(lambda x: html.unescape(x) if x and x != 'nan' else x)
        
        # Replace various NULL representations with actual None
        null_values = ['NULL', 'null', 'nan', '', '""', '"NULL"']
        for null_val in null_values:
            df = df.replace(null_val, None)
        
        # Identify and clean numeric columns based on your schema
        numeric_columns = [
            'last_logged_in', 'login_attempts', 'created_at', 'updated_at'
        ]
        
        for col in numeric_columns:
            if col in df.columns:
                # Convert empty strings and various null representations to None
                df[col] = df[col].replace(['', '""', 'NULL', 'null'], None)
        
        # Clean boolean columns
        boolean_columns = ['is_deleted', 'is_locked']
        for col in boolean_columns:
            if col in df.columns:
                df[col] = df[col].replace(['', '""', 'NULL', 'null'], None)
        
        # Save with PostgreSQL-compatible NULL representation
        df.to_csv(output_file, index=False, na_rep='\\N')
        
        print(f"Cleaned data saved to: {output_file}")
        print("\\nSample of cleaned data:")
        print(df[['paymaart_id', 'last_logged_in', 'login_attempts']].head(3))
        
        # Show NULL counts for problematic columns
        print("\\nNULL counts in numeric columns:")
        for col in numeric_columns:
            if col in df.columns:
                null_count = df[col].isnull().sum()
                print(f"  {col}: {null_count} NULLs")
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    input_file = r"C:\Users\watip\Downloads\agent_users.txt"
    output_file = r"C:\Users\watip\Downloads\agent_users_postgresql.csv"
    
    success = clean_csv_for_postgresql(input_file, output_file)
    
    if success:
        print("\\nData cleaning completed successfully!")
        print(f"Use this file for PostgreSQL import: {output_file}")
        print("\\nPostgreSQL COPY command:")
        print(f"COPY agent_users FROM '{output_file.replace(chr(92), '/')}'")
        print("WITH (FORMAT csv, HEADER true, NULL '\\\\N');")
    else:
        print("\\nData cleaning failed!")