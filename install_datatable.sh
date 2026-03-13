#!/bin/bash

# Install missing dependencies for DataTable functionality
echo "Installing DataTable dependencies..."

# Navigate to frontend directory
cd frontend

# Install missing Radix UI components for table functionality
npm install @radix-ui/react-dropdown-menu @radix-ui/react-popover

echo "Dependencies installed successfully!"
echo ""
echo "The following components have been added/updated:"
echo "✅ DataTable component with pagination and CSV export"
echo "✅ Table UI components (Shadcn/UI)"
echo "✅ Updated Message component with conditional table rendering"
echo "✅ Updated API types to include raw data"
echo "✅ Backend updated to include raw data in responses"
echo ""
echo "Features:"
echo "🔄 Pagination (10, 20, 30, 50, 100 rows per page)"
echo "📊 Only shows in Database Analytics mode"
echo "📥 CSV Export with professional formatting"
echo "🎨 Dark theme matching existing UI"
echo "📱 Responsive design"
echo ""
echo "To test:"
echo "1. Start the backend: python api.py"
echo "2. Start the frontend: npm run dev"
echo "3. Ask a database query that returns multiple results"
echo "4. The DataTable will automatically render instead of markdown"