# AWS RDS Aurora PostgreSQL Setup

## 1. Aurora Connection Details

Update your `.env` file with:
```
DB_HOST=your-aurora-cluster-endpoint.cluster-xxxxxxxxx.region.rds.amazonaws.com
DB_NAME=paymaart_db
DB_USER=your_aurora_username
DB_PASSWORD=your_aurora_password
DB_PORT=5432
```

## 2. Security Group Configuration

Ensure your Aurora cluster's security group allows inbound connections on port 5432 from your IP address or application.

## 3. SSL Connection (Recommended)

For production, add SSL parameters to your connection:

```python
# In enterprise_db_connector.py, modify the connection string:
connection_string = f"postgresql://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{db_params['database']}?sslmode=require"
```

## 4. Connection Pooling (Optional)

For better performance with Aurora, consider adding connection pooling:

```bash
pip install psycopg2-pool
```

## 5. Aurora Serverless v2 (Optional)

If using Aurora Serverless v2, the connection remains the same but provides automatic scaling.

## 6. Verify Connection

Test your connection:
```bash
python -c "from enterprise_db_connector import get_tenant_connector; print(get_tenant_connector().get_tenant_info())"
```