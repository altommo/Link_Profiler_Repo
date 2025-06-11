// Simple WebSocket Test - paste this in browser console

// Close any existing WebSocket connections first
if (window.testWS) {
    window.testWS.close();
}

// Create a simple WebSocket connection
window.testWS = new WebSocket('wss://monitor.yspanel.com/ws/mission-control');

window.testWS.onopen = function(event) {
    console.log('✅ Test WebSocket Connected');
};

window.testWS.onmessage = function(event) {
    console.log('📨 Raw event.data type:', typeof event.data);
    console.log('📨 Raw event.data content:', event.data);
    
    try {
        const parsed = JSON.parse(event.data);
        console.log('✅ JSON parsed successfully:', parsed);
        console.log('✅ Parsed type:', typeof parsed);
        console.log('✅ Parsed.type:', parsed.type);
    } catch (e) {
        console.error('❌ JSON parse failed:', e);
        console.error('❌ Data was:', event.data);
    }
};

window.testWS.onerror = function(error) {
    console.error('❌ Test WebSocket Error:', error);
};

window.testWS.onclose = function(event) {
    console.log('🔌 Test WebSocket Closed:', event.code, event.reason);
};

console.log('Test WebSocket created. Watch for messages...');
console.log('To close: window.testWS.close()');
