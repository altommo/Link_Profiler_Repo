#!/bin/bash

# Update system packages
sudo apt-get update

# Install Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install Python and basic tools
sudo apt-get install -y python3 python3-venv python3-pip sqlite3

# Navigate to workspace
cd /workspace/Link_Profiler_Repo

# Set up Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install testing dependencies first
echo "Installing test dependencies..."
pip install -r requirements-test.txt

# Install Python dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing main dependencies..."
    pip install -r requirements.txt
else
    echo "Installing basic dependencies..."
    pip install fastapi uvicorn sqlalchemy psycopg2-binary redis python-jose bcrypt python-multipart
fi

# Set PYTHONPATH correctly for tests
export PYTHONPATH=/workspace/Link_Profiler_Repo
echo "export PYTHONPATH=/workspace/Link_Profiler_Repo" >> ~/.bashrc

# Create basic .env file
if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "Created .env file from .env.example"
else
    echo "Creating basic .env file..."
    cat > .env << EOF
DATABASE_URL=sqlite:///./test_link_profiler.db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=test-secret-key-for-development
ADMIN_PASSWORD=admin123
API_BASE_URL=http://localhost:8000
DEBUG=true
ENVIRONMENT=development
EOF
fi

# Install React dashboard dependencies
echo "Installing Customer Dashboard dependencies..."
cd customer-dashboard
if [ -f "package.json" ]; then
    npm install
    npm install react-router-dom axios recharts @mui/material @emotion/react @emotion/styled
else
    echo "Customer dashboard package.json not found"
fi
cd ..

echo "Installing Admin Dashboard dependencies..."
cd admin-dashboard  
if [ -f "package.json" ]; then
    npm install
    npm install react-router-dom axios @mui/material @emotion/react @emotion/styled
else
    echo "Admin dashboard package.json not found"
fi
cd ..

# Make scripts executable
chmod +x run_tests.py
find . -name "*.py" -path "./Link_Profiler/*" -exec chmod +x {} \;

# Run a quick test to verify setup
echo "Running quick test to verify setup..."
python3 run_tests.py unit -v

echo "=========================="
echo "Setup completed successfully!"
echo "=========================="
echo "Available commands:"
echo "  - Activate Python env: source venv/bin/activate"
echo "  - Run unit tests: python run_tests.py unit"
echo "  - Run all tests: python run_tests.py all -v"
echo "  - Customer Dashboard: cd customer-dashboard && npm run dev"
echo "  - Admin Dashboard: cd admin-dashboard && npm run dev"  
echo "  - Python API: source venv/bin/activate && python Link_Profiler/main.py"
echo "=========================="
