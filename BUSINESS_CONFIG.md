# Business Configuration Guide

## 🚀 Deploy for Any Business in 3 Steps

### Step 1: Deploy Container
```bash
# Point to your database
docker run -d \
  -e DB_HOST=your_db_host \
  -e DB_NAME=your_database \
  -e DB_USER=your_user \
  -e DB_PASSWORD=your_password \
  -e GROQ_API_KEY=your_groq_key \
  -p 8000:8000 \
  -v ./config.json:/app/config.json \
  rag-app
```

### Step 2: Create config.json
```json
{
  "business_name": "Your Business Name",
  "domain_context": "your_industry",
  "domain_terms": {
    "your_business_term": "your_sql_condition"
  },
  "business_language": {
    "primary_entity": "your_main_records",
    "currency": "USD"
  }
}
```

### Step 3: Test
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many records do we have?"}'
```

## 📋 Business Examples

### Salon Business
```json
{
  "business_name": "Bella Salon & Spa",
  "domain_context": "salon_management", 
  "domain_terms": {
    "premium_service": "service_price > 100",
    "busy_day": "COUNT(appointment_id) > 15",
    "peak_hours": "EXTRACT(HOUR FROM appointment_time) BETWEEN 10 AND 16",
    "vip_clients": "client_tier = 'vip'",
    "hair_services": "service_type IN ('haircut', 'coloring', 'styling')"
  },
  "business_language": {
    "primary_entity": "appointments",
    "currency": "USD"
  }
}
```

### Restaurant Business  
```json
{
  "business_name": "Mario's Pizzeria",
  "domain_context": "restaurant_management",
  "domain_terms": {
    "large_order": "order_total > 50",
    "peak_hours": "EXTRACT(HOUR FROM order_time) BETWEEN 12 AND 14",
    "weekend_orders": "EXTRACT(DOW FROM order_date) IN (0, 6)",
    "pizza_orders": "item_category = 'pizza'",
    "delivery_orders": "order_type = 'delivery'"
  },
  "business_language": {
    "primary_entity": "orders", 
    "currency": "USD"
  }
}
```

### Retail Store
```json
{
  "business_name": "TechMart Electronics",
  "domain_context": "retail_management",
  "domain_terms": {
    "high_value_sale": "sale_amount > 500",
    "electronics": "category IN ('laptop', 'phone', 'tablet')",
    "weekend_sales": "EXTRACT(DOW FROM sale_date) IN (0, 6)",
    "bulk_purchase": "quantity > 5",
    "premium_customer": "customer_tier = 'gold'"
  },
  "business_language": {
    "primary_entity": "sales",
    "currency": "USD"
  }
}
```

## 🔧 Configuration Fields

| Field | Description | Example |
|-------|-------------|---------|
| `business_name` | Your business name | "Bella Salon & Spa" |
| `domain_context` | Industry type | "salon_management" |
| `domain_terms` | Business shortcuts | `"busy_day": "COUNT(*) > 15"` |
| `primary_entity` | Main data type | "appointments", "orders", "sales" |
| `currency` | Currency format | "USD", "EUR", "MWK" |

## ⚠️ Common Mistakes

**Wrong**: `"high_sales": "amount > 1000"` (if column is `sale_amount`)
**Right**: `"high_sales": "sale_amount > 1000"`

**Wrong**: `"recent": "date > '2024-01-01'"` (hardcoded date)
**Right**: `"recent": "date > NOW() - INTERVAL '30 days'"`

## 🧪 Test Your Config

```bash
# Check if agent loaded your config
curl http://localhost:8000/health

# Test a business term
curl -X POST http://localhost:8000/query \
  -d '{"question": "Show me premium services"}'
```

## 🔄 Update Business Rules

1. Edit `config.json`
2. Restart container: `docker restart container_name`
3. Agent automatically reloads with new terms

**Zero code changes needed!**