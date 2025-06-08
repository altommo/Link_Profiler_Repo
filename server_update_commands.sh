#!/bin/bash
# Commands to update your server with the fixed code

echo "🔄 Updating server with dashboard fixes..."

# Navigate to your repository
cd /opt/Link_Profiler_Repo

# Create a backup before updating
echo "📦 Creating backup of current main.py..."
cp Link_Profiler/main.py Link_Profiler/main.py.backup.$(date +%Y%m%d_%H%M%S)

# Pull the latest changes from GitHub
echo "⬇️  Pulling latest changes from GitHub..."
git fetch origin
git pull origin master

# Check if the update was successful
echo "🔍 Verifying changes..."
echo "Checking for admin-management references (should be none):"
grep -n "admin-management" Link_Profiler/main.py || echo "✅ No admin-management references found!"

echo ""
echo "Checking for mission-control references (should exist):"
grep -n "mission-control" Link_Profiler/main.py || echo "⚠️  No mission-control references found"

# Test Python syntax
echo ""
echo "🔬 Testing Python syntax..."
if python3 -m py_compile Link_Profiler/main.py; then
    echo "✅ Python syntax is valid!"
else
    echo "❌ Python syntax error detected!"
    exit 1
fi

# Show what changed
echo ""
echo "📋 Recent changes:"
git log --oneline -3

echo ""
echo "🎉 Server update completed successfully!"
echo ""
echo "💡 Next steps:"
echo "1. Restart your server:"
echo "   cd /opt/Link_Profiler_Repo"
echo "   python3 -m uvicorn Link_Profiler.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "2. Check your dashboards:"
echo "   - Mission Control: http://your-server:8001"
echo "   - API: http://your-server:8000"