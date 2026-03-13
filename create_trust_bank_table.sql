-- Create trust_bank_transaction table with correct schema
-- Based on actual columns: ['id', 'transaction_id', 'transaction_code', 'transaction_type', 'transaction_amount', 'created_at', 'sender_id', 'entered_by', 'reciever_id', 'pop_file_key', 'pop_file_ref_no', 'bank_id', 'type', 'closing_balance', 'flagged', 'closing_balance_ptbat', 'sender_closing_balance']

CREATE TABLE IF NOT EXISTS trust_bank_transaction (
    id VARCHAR(100) PRIMARY KEY,  -- UUID from your data
    transaction_id VARCHAR(100),
    transaction_code VARCHAR(50),
    transaction_type VARCHAR(50),
    transaction_amount NUMERIC,
    created_at BIGINT,
    sender_id VARCHAR(50),
    entered_by VARCHAR(50),
    reciever_id VARCHAR(50),  -- Note: keeping original spelling
    pop_file_key TEXT,
    pop_file_ref_no VARCHAR(100),
    bank_id VARCHAR(50),
    type VARCHAR(20),
    closing_balance NUMERIC,
    flagged BOOLEAN,
    closing_balance_ptbat NUMERIC,
    sender_closing_balance NUMERIC
);

-- After creating the table, import the data:
-- \copy trust_bank_transaction FROM 'C:\Users\watip\Downloads\trust_bank_transaction_cleaned.csv' WITH CSV HEADER;