import pandas as pd

def csv_to_insert_statements(csv_file, table_name, output_file):
    """Convert CSV to INSERT statements for PostgreSQL"""
    try:
        df = pd.read_csv(csv_file)
        
        # Get column names
        columns = ', '.join(df.columns)
        
        with open(output_file, 'w') as f:
            f.write(f"-- INSERT statements for {table_name}\n")
            f.write(f"-- Generated from {csv_file}\n\n")
            
            for index, row in df.iterrows():
                values = []
                for value in row:
                    if pd.isna(value) or value == '\\N':
                        values.append('NULL')
                    elif isinstance(value, str):
                        # Escape single quotes
                        escaped_value = value.replace("'", "''")
                        values.append(f"'{escaped_value}'")
                    else:
                        values.append(str(value))
                
                values_str = ', '.join(values)
                f.write(f"INSERT INTO {table_name} ({columns}) VALUES ({values_str});\n")
        
        print(f"INSERT statements generated: {output_file}")
        print(f"Total rows: {len(df)}")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    csv_file = r"C:\Users\watip\Downloads\agent_users_postgresql.csv"
    output_file = r"C:\Users\watip\Downloads\agent_users_inserts.sql"
    table_name = "agent_users"
    
    success = csv_to_insert_statements(csv_file, table_name, output_file)
    
    if success:
        print(f"\nYou can now run the SQL file: {output_file}")
        print("Or copy-paste the INSERT statements into DBeaver")