-- Create test database schema and populate with sample data

-- Agents table
CREATE TABLE IF NOT EXISTS agents (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100),
    phone VARCHAR(20),
    region VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Sales table
CREATE TABLE IF NOT EXISTS sales (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER REFERENCES agents(id),
    customer_name VARCHAR(100),
    product VARCHAR(100),
    amount DECIMAL(10, 2),
    commission DECIMAL(10, 2),
    sale_date DATE DEFAULT CURRENT_DATE,
    status VARCHAR(20) DEFAULT 'completed'
);

-- Products table
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    category VARCHAR(50),
    price DECIMAL(10, 2),
    stock INTEGER,
    is_active BOOLEAN DEFAULT true
);

-- Insert sample agents
INSERT INTO agents (name, email, phone, region, created_at) VALUES
('John Doe', 'john@paymaart.com', '+265888111111', 'North', CURRENT_DATE - INTERVAL '30 days'),
('Jane Smith', 'jane@paymaart.com', '+265888222222', 'South', CURRENT_DATE - INTERVAL '25 days'),
('Mike Johnson', 'mike@paymaart.com', '+265888333333', 'Central', CURRENT_DATE - INTERVAL '20 days'),
('Sarah Williams', 'sarah@paymaart.com', '+265888444444', 'North', CURRENT_DATE - INTERVAL '15 days'),
('David Brown', 'david@paymaart.com', '+265888555555', 'South', CURRENT_DATE - INTERVAL '10 days'),
('Emma Davis', 'emma@paymaart.com', '+265888666666', 'Central', CURRENT_DATE - INTERVAL '5 days'),
('Tom Wilson', 'tom@paymaart.com', '+265888777777', 'North', CURRENT_DATE),
('Lisa Anderson', 'lisa@paymaart.com', '+265888888888', 'South', CURRENT_DATE);

-- Insert sample products
INSERT INTO products (name, category, price, stock) VALUES
('Airtel 1GB Bundle', 'Data', 2500.00, 1000),
('Airtel 5GB Bundle', 'Data', 10000.00, 500),
('TNM 2GB Bundle', 'Data', 3000.00, 800),
('Cash-in Service', 'Transaction', 0.00, 9999),
('Cash-out Service', 'Transaction', 0.00, 9999),
('Bill Payment', 'Utility', 0.00, 9999);

-- Insert sample sales (last 30 days)
INSERT INTO sales (agent_id, customer_name, product, amount, commission, sale_date, status) VALUES
-- Today's sales
(1, 'Customer A', 'Airtel 1GB Bundle', 2500.00, 125.00, CURRENT_DATE, 'completed'),
(2, 'Customer B', 'Airtel 5GB Bundle', 10000.00, 500.00, CURRENT_DATE, 'completed'),
(3, 'Customer C', 'Cash-in Service', 50000.00, 250.00, CURRENT_DATE, 'completed'),
(7, 'Customer D', 'TNM 2GB Bundle', 3000.00, 150.00, CURRENT_DATE, 'completed'),
(8, 'Customer E', 'Bill Payment', 15000.00, 75.00, CURRENT_DATE, 'completed'),

-- Yesterday's sales
(1, 'Customer F', 'Airtel 5GB Bundle', 10000.00, 500.00, CURRENT_DATE - INTERVAL '1 day', 'completed'),
(2, 'Customer G', 'Cash-out Service', 30000.00, 150.00, CURRENT_DATE - INTERVAL '1 day', 'completed'),
(4, 'Customer H', 'Airtel 1GB Bundle', 2500.00, 125.00, CURRENT_DATE - INTERVAL '1 day', 'completed'),
(5, 'Customer I', 'TNM 2GB Bundle', 3000.00, 150.00, CURRENT_DATE - INTERVAL '1 day', 'completed'),

-- This week's sales
(1, 'Customer J', 'Airtel 1GB Bundle', 2500.00, 125.00, CURRENT_DATE - INTERVAL '3 days', 'completed'),
(2, 'Customer K', 'Cash-in Service', 75000.00, 375.00, CURRENT_DATE - INTERVAL '3 days', 'completed'),
(3, 'Customer L', 'Airtel 5GB Bundle', 10000.00, 500.00, CURRENT_DATE - INTERVAL '4 days', 'completed'),
(4, 'Customer M', 'Bill Payment', 20000.00, 100.00, CURRENT_DATE - INTERVAL '5 days', 'completed'),
(5, 'Customer N', 'TNM 2GB Bundle', 3000.00, 150.00, CURRENT_DATE - INTERVAL '6 days', 'completed'),

-- This month's sales
(1, 'Customer O', 'Airtel 5GB Bundle', 10000.00, 500.00, CURRENT_DATE - INTERVAL '10 days', 'completed'),
(2, 'Customer P', 'Cash-in Service', 100000.00, 500.00, CURRENT_DATE - INTERVAL '12 days', 'completed'),
(3, 'Customer Q', 'Airtel 1GB Bundle', 2500.00, 125.00, CURRENT_DATE - INTERVAL '15 days', 'completed'),
(4, 'Customer R', 'TNM 2GB Bundle', 3000.00, 150.00, CURRENT_DATE - INTERVAL '18 days', 'completed'),
(5, 'Customer S', 'Bill Payment', 25000.00, 125.00, CURRENT_DATE - INTERVAL '20 days', 'completed'),
(6, 'Customer T', 'Airtel 5GB Bundle', 10000.00, 500.00, CURRENT_DATE - INTERVAL '22 days', 'completed');

-- Add some pending sales
INSERT INTO sales (agent_id, customer_name, product, amount, commission, sale_date, status) VALUES
(1, 'Customer U', 'Airtel 1GB Bundle', 2500.00, 125.00, CURRENT_DATE, 'pending'),
(3, 'Customer V', 'Cash-in Service', 40000.00, 200.00, CURRENT_DATE, 'pending');

-- Create useful views
CREATE OR REPLACE VIEW daily_sales_summary AS
SELECT 
    DATE(sale_date) as date,
    COUNT(*) as total_sales,
    SUM(amount) as total_amount,
    SUM(commission) as total_commission
FROM sales
WHERE status = 'completed'
GROUP BY DATE(sale_date)
ORDER BY date DESC;

CREATE OR REPLACE VIEW agent_performance AS
SELECT 
    a.id,
    a.name,
    a.region,
    COUNT(s.id) as total_sales,
    SUM(s.amount) as total_revenue,
    SUM(s.commission) as total_commission
FROM agents a
LEFT JOIN sales s ON a.id = s.agent_id AND s.status = 'completed'
GROUP BY a.id, a.name, a.region
ORDER BY total_revenue DESC;
