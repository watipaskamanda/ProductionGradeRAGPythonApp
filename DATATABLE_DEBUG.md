# DataTable Debugging Guide

## 🔧 What We've Fixed

### 1. **Backend Changes**
- ✅ Fixed `enterprise_db_connector.py` to include `raw_data` field
- ✅ Added intelligent "show me" request handling
- ✅ Updated API response formatting

### 2. **Frontend Changes**  
- ✅ Fixed API endpoint from `/api/database` → `/api/v1/query/database`
- ✅ Added comprehensive debugging logs
- ✅ Updated data extraction logic to handle `raw_data`
- ✅ Created DataTable component with pagination & CSV export

### 3. **API Changes**
- ✅ Updated Pydantic model to include `raw_data` field
- ✅ Modified response structure to pass through raw data

## 🧪 Testing Steps

### Step 1: Start Backend
```bash
cd ProductionGradeRAGPythonApp
python api.py
```

### Step 2: Start Frontend
```bash
cd frontend
npm run dev
```

### Step 3: Test Queries
1. **Ask a database query**: "How many transactions were there in July 2025?"
2. **Check browser console** for debugging logs:
   - `🔍 Full API response:` - Should show the complete response
   - `✅ Using raw_data from backend:` - Should show raw data extraction
   - `🔍 DataTable render check:` - Should show render conditions

### Step 4: Expected Results
- **Answer**: "There was 1 transaction in July 2025." (not "Query executed successfully")
- **DataTable**: Should render below the answer with:
  - Column headers
  - Data rows
  - Pagination controls
  - CSV export button

## 🔍 Debugging Checklist

### If DataTable Doesn't Show:

1. **Check Browser Console**:
   ```
   🔍 Full API response: {...}
   🔍 DataTable render check: {
     activeTab: "analytics",
     hasRawData: true/false,
     hasColumns: true/false, 
     hasRows: true/false,
     shouldRender: true/false
   }
   ```

2. **Verify API Response Structure**:
   ```json
   {
     "answer": "There was 1 transaction in July 2025.",
     "raw_data": {
       "columns": ["column1", "column2"],
       "rows": [["value1", "value2"]],
       "total_count": 1
     }
   }
   ```

3. **Check activeTab**:
   - Must be `"analytics"` (not `"documents"`)
   - Verify in browser console logs

4. **Verify Data Structure**:
   - `raw_data` exists
   - `raw_data.columns` is array with length > 0
   - `raw_data.rows` is array with length > 0

### If API Errors:

1. **Check Backend Logs**:
   ```
   🤖 Intent Classification: {'intent': 'SQL_QUERY', 'confidence': 0.95}
   🔍 Processing SQL query for tenant: default
   ```

2. **Verify Database Connection**:
   - PostgreSQL running on port 5432
   - Database accessible

3. **Check Enterprise Connector**:
   - `raw_data` field being added to response
   - SQL execution successful

## 🐛 Common Issues & Fixes

### Issue 1: "No tables being rendered"
**Cause**: Frontend not receiving `raw_data`
**Fix**: Check API response structure and data extraction logic

### Issue 2: "API endpoint not found"
**Cause**: Wrong endpoint path
**Fix**: Use `/api/v1/query/database` not `/api/database`

### Issue 3: "DataTable shows but no data"
**Cause**: Data structure mismatch
**Fix**: Verify `columns` and `rows` arrays are properly formatted

### Issue 4: "CSV export not working"
**Cause**: Browser blocking download or data format issue
**Fix**: Check browser console for errors, verify data structure

## 🎯 Success Indicators

### ✅ Working System Should Show:
1. **Console Logs**:
   ```
   🔍 Full API response: {answer: "...", raw_data: {...}}
   ✅ Using raw_data from backend: {columns: [...], rows: [...]}
   🔍 DataTable render check: {shouldRender: true}
   ✅ Rendering DataTable with data: {...}
   ```

2. **UI Elements**:
   - Answer text above table
   - DataTable with headers and data
   - Pagination controls (if > 10 rows)
   - "Download CSV" button
   - Dark theme styling

3. **Functionality**:
   - Pagination works (next/prev buttons)
   - CSV export downloads file
   - Table shows formatted data
   - "Show me" requests reuse previous queries

## 🚀 Next Steps After Success

1. **Test with larger datasets** (100+ rows)
2. **Verify CSV export** with complex data
3. **Test pagination** with different page sizes
4. **Check responsive design** on mobile
5. **Test "show me" variations**:
   - "show the table"
   - "display results"
   - "view the data"

## 📞 If Still Not Working

Run the test script:
```bash
python test_datatable.py
```

This will test the complete API flow and show exactly what's being returned.

The key is checking the browser console logs - they will tell you exactly where the issue is in the data flow.