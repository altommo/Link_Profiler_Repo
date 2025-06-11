#!/bin/bash

# Quick server management commands for Link Profiler

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function definitions
start_server() {
    echo -e "${YELLOW}Starting Link Profiler server...${NC}"
    chmod +x restart_server.sh
    ./restart_server.sh
}

stop_server() {
    echo -e "${YELLOW}Stopping Link Profiler server...${NC}"
    pkill -f "uvicorn main:app"
    echo -e "${GREEN}Server stopped${NC}"
}

check_status() {
    if pgrep -f "uvicorn main:app" > /dev/null; then
        echo -e "${GREEN}✅ Server is running${NC}"
        echo "PID: $(pgrep -f 'uvicorn main:app')"
        echo "Listening on: http://0.0.0.0:8000"
    else
        echo -e "${RED}❌ Server is not running${NC}"
    fi
}

view_logs() {
    if [ -f "server.log" ]; then
        tail -f server.log
    else
        echo -e "${RED}No server.log found${NC}"
    fi
}

test_websocket() {
    echo -e "${YELLOW}Testing WebSocket connection...${NC}"
    python3 debug_websocket_connection.py
}

test_api() {
    echo -e "${YELLOW}Testing API endpoints...${NC}"
    echo "Testing health endpoint..."
    curl -s https://monitor.yspanel.com/health | jq . || echo "Health check failed"
    
    echo -e "\nTesting mission control endpoint..."
    curl -s https://monitor.yspanel.com/api/mission-control/test | jq . || echo "Mission control test failed"
}

# Main command processing
case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 2
        start_server
        ;;
    status)
        check_status
        ;;
    logs)
        view_logs
        ;;
    test-ws)
        test_websocket
        ;;
    test-api)
        test_api
        ;;
    *)
        echo "Link Profiler Server Management"
        echo "Usage: $0 {start|stop|restart|status|logs|test-ws|test-api}"
        echo ""
        echo "Commands:"
        echo "  start     - Start the server"
        echo "  stop      - Stop the server"
        echo "  restart   - Restart the server"
        echo "  status    - Check server status"
        echo "  logs      - View live server logs"
        echo "  test-ws   - Test WebSocket connection"
        echo "  test-api  - Test API endpoints"
        exit 1
        ;;
esac
