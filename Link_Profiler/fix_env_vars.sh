#!/bin/bash
# Fix Link Profiler Authentication Environment Variables
# This script adds the missing environment variables to your systemd service

echo "🔧 Link Profiler Environment Variable Fix Script"
echo "================================================"

SERVICE_FILE="/etc/systemd/system/linkprofiler-api.service"
BACKUP_FILE="/etc/systemd/system/linkprofiler-api.service.backup.$(date +%Y%m%d_%H%M%S)"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root: sudo $0"
    exit 1
fi

# Backup the original service file
echo "📄 Creating backup of service file..."
cp "$SERVICE_FILE" "$BACKUP_FILE"
echo "✅ Backup created: $BACKUP_FILE"

# Check if the required environment variables are already present
echo "🔍 Checking current environment variables in service file..."

if grep -q "LP_AUTH_SECRET_KEY" "$SERVICE_FILE"; then
    echo "✅ LP_AUTH_SECRET_KEY already exists in service file"
    HAS_AUTH_KEY=true
else
    echo "❌ LP_AUTH_SECRET_KEY missing from service file"
    HAS_AUTH_KEY=false
fi

if grep -q "LP_REDIS_URL" "$SERVICE_FILE"; then
    echo "✅ LP_REDIS_URL already exists in service file"
    HAS_REDIS_URL=true
else
    echo "❌ LP_REDIS_URL missing from service file"
    HAS_REDIS_URL=false
fi

# Generate a secure secret key if needed
if [ "$HAS_AUTH_KEY" = false ]; then
    echo "🔑 Generating secure secret key..."
    SECRET_KEY=$(openssl rand -hex 32)
    echo "Generated secret key: ${SECRET_KEY:0:16}..."
fi

# Add missing environment variables
if [ "$HAS_AUTH_KEY" = false ] || [ "$HAS_REDIS_URL" = false ]; then
    echo "📝 Adding missing environment variables to service file..."
    
    # Create a temporary file with the modifications
    TEMP_FILE=$(mktemp)
    
    # Copy the file and add missing environment variables after the existing Environment= lines
    while IFS= read -r line; do
        echo "$line" >> "$TEMP_FILE"
        
        # Add missing variables after the last Environment= line
        if [[ "$line" =~ ^Environment= ]] && [ "$HAS_AUTH_KEY" = false ]; then
            echo "Environment=LP_AUTH_SECRET_KEY=$SECRET_KEY" >> "$TEMP_FILE"
            HAS_AUTH_KEY=true
            echo "✅ Added LP_AUTH_SECRET_KEY"
        fi
        
        if [[ "$line" =~ ^Environment= ]] && [ "$HAS_REDIS_URL" = false ]; then
            echo "Environment=LP_REDIS_URL=redis://localhost:6379/0" >> "$TEMP_FILE"
            HAS_REDIS_URL=true
            echo "✅ Added LP_REDIS_URL"
        fi
    done < "$SERVICE_FILE"
    
    # Replace the original file
    mv "$TEMP_FILE" "$SERVICE_FILE"
    echo "✅ Service file updated"
else
    echo "✅ All required environment variables are already present"
fi

# Reload systemd and restart the service
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

echo "🔄 Restarting Link Profiler API service..."
systemctl restart linkprofiler-api

# Check service status
echo "📊 Checking service status..."
sleep 2
if systemctl is-active --quiet linkprofiler-api; then
    echo "✅ Link Profiler API service is running"
else
    echo "❌ Link Profiler API service failed to start"
    echo "📋 Service status:"
    systemctl status linkprofiler-api --no-pager -l
    echo ""
    echo "📋 Recent logs:"
    journalctl -u linkprofiler-api --no-pager -l -n 20
fi

echo ""
echo "🔧 Next steps:"
echo "1. Test the authentication: cd /opt/Link_Profiler_Repo/Link_Profiler && python fixed_auth_check.py"
echo "2. Check service logs: journalctl -u linkprofiler-api -f"
echo "3. Access the dashboard at: http://your-server-ip:8000"

echo ""
echo "📄 Backup file location: $BACKUP_FILE"
echo "   (Restore with: sudo cp $BACKUP_FILE $SERVICE_FILE && sudo systemctl daemon-reload)"
