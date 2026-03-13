import pandas as pd

def create_insert_statements():
    """Generate INSERT statements for trust_bank_transaction"""
    
    # Read the cleaned CSV
    df = pd.read_csv(r"C:\Users\watip\Downloads\trust_bank_transaction_cleaned.csv")
    
    print(f"Creating INSERT statements for {len(df)} rows...")
    
    # Generate INSERT statements (first 10 rows to test)
    with open('trust_bank_inserts.sql', 'w') as f:
        f.write("-- INSERT statements for trust_bank_transaction\n\n")
        
        for index, row in df.head(10).iterrows():  # Start with just 10 rows
            values = []
            for value in row:
                if pd.isna(value) or value == '' or value == 'None':
                    values.append('NULL')
                elif isinstance(value, str):
                    # Escape single quotes
                    escaped_value = str(value).replace("'", "''")
                    values.append(f"'{escaped_value}'")
                else:
                    values.append(str(value))
            
            columns = ', '.join(df.columns)
            values_str = ', '.join(values)
            
            f.write(f"INSERT INTO trust_bank_transaction ({columns}) VALUES ({values_str});\n")
    
    print("INSERT statements created in 'trust_bank_inserts.sql'")
    print("Copy and paste these into pgAdmin to test first 10 rows")

if __name__ == "__main__":
    create_insert_statements()