import pandas as pd
import html

def clean_csv_data(input_file, output_file):
    """Clean CSV data by fixing HTML entities and NULL values"""
    try:
        # Read the CSV file
        print(f"Reading file: {input_file}")
        df = pd.read_csv(input_file)
        
        print(f"Original data shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        
        # Fix HTML entities in all text columns
        for col in df.columns:
            if df[col].dtype == 'object':
                # Handle NaN values first
                df[col] = df[col].fillna('')
                df[col] = df[col].astype(str).apply(lambda x: html.unescape(x) if x and x != 'nan' else x)
        
        # Replace 'NULL' strings with actual NULL values
        df = df.replace('NULL', None)
        df = df.replace('null', None)
        df = df.replace('nan', None)
        
        # Handle numeric columns that should be NULL when empty
        numeric_columns = ['last_logged_in', 'login_attempts']
        for col in numeric_columns:
            if col in df.columns:
                # Replace empty strings with None for numeric columns
                df[col] = df[col].replace('', None)
                df[col] = df[col].replace('""', None)
        
        # Save cleaned file
        df.to_csv(output_file, index=False, na_rep='')
        
        print(f"Cleaned data saved to: {output_file}")
        print(f"Sample of first few rows:")
        print(df.head(2).to_string())
        
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    input_file = r"C:\Users\watip\Downloads\agent_users.txt"
    output_file = r"C:\Users\watip\Downloads\agent_users_cleaned.csv"
    
    success = clean_csv_data(input_file, output_file)
    
    if success:
        print("\nData cleaning completed successfully!")
        print(f"Import the cleaned file: {output_file}")
    else:
        print("\nData cleaning failed!")