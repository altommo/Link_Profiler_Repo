// Browser Console Commands for WebSocket Testing
// Copy and paste these commands in your browser's developer console

console.log("🚀 Starting WebSocket Connection Test...");

// Test WebSocket connection
const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/mission-control`;
console.log(`WebSocket URL: ${wsUrl}`);

const ws = new WebSocket(wsUrl);

ws.onopen = function(event) {
    console.log('✅ WebSocket Connected!', event);
};

ws.onmessage = function(event) {
    console.log('📨 Message received:', event.data);
    try {
        const data = JSON.parse(event.data);
        console.log('📊 Parsed data:', data);
    } catch (e) {
        console.log('📄 Raw message:', event.data);
    }
};

ws.onerror = function(error) {
    console.error('❌ WebSocket Error:', error);
};

ws.onclose = function(event) {
    console.log('🔌 WebSocket Closed:', event.code, event.reason);
};

// Test function to check connection status
window.checkWebSocketStatus = function() {
    console.log('WebSocket Ready State:', ws.readyState);
    const states = {
        0: 'CONNECTING',
        1: 'OPEN',
        2: 'CLOSING',
        3: 'CLOSED'
    };
    console.log('Status:', states[ws.readyState] || 'UNKNOWN');
};

// Test API endpoint
fetch('/api/mission-control/test')
    .then(response => response.json())
    .then(data => console.log('✅ API Test Response:', data))
    .catch(error => console.error('❌ API Test Error:', error));

console.log("Test setup complete! WebSocket connection initiated.");
console.log("Use checkWebSocketStatus() to check connection status.");
