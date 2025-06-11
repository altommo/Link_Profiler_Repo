#!/usr/bin/env python3
"""
WebSocket Server-Side Test
Tests the Mission Control WebSocket endpoint directly from the server
"""

import asyncio
import websockets
import json
import ssl
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

async def test_websocket_local():
    """Test WebSocket connection to local server"""
    
    print("Testing local WebSocket connection...")
    
    try:
        # Test local connection (assuming the app runs on localhost:8000)
        uri = "ws://localhost:8000/ws/mission-control"
        print(f"Connecting to: {uri}")
        
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connection successful!")
            
            # Wait for a message
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                print(f"📩 Received message: {message[:200]}...")
                
                # Try to parse as JSON
                try:
                    data = json.loads(message)
                    print(f"📊 Parsed JSON - timestamp: {data.get('timestamp')}")
                    print(f"🔧 Mission status available: {'crawler_mission_status' in data}")
                except json.JSONDecodeError:
                    print("⚠️  Message is not valid JSON")
                    
            except asyncio.TimeoutError:
                print("⏰ No message received within 10 seconds (this might be normal)")
                
    except ConnectionRefusedError:
        print("❌ Connection refused - is the server running on localhost:8000?")
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")

async def test_websocket_production():
    """Test WebSocket connection to production server"""
    
    print("\nTesting production WebSocket connection...")
    
    try:
        # Test production connection with SSL
        uri = "wss://monitor.yspanel.com/ws/mission-control"
        print(f"Connecting to: {uri}")
        
        # Create SSL context
        ssl_context = ssl.create_default_context()
        
        async with websockets.connect(uri, ssl=ssl_context) as websocket:
            print("✅ Production WebSocket connection successful!")
            
            # Wait for a message
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                print(f"📩 Received message: {message[:200]}...")
                
            except asyncio.TimeoutError:
                print("⏰ No message received within 10 seconds")
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ WebSocket connection closed: {e}")
    except Exception as e:
        print(f"❌ Production WebSocket connection failed: {e}")

async def test_http_endpoint():
    """Test the HTTP endpoint to see if the server is responding"""
    
    print("\nTesting HTTP endpoints...")
    
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test the mission control test endpoint
            async with session.get("https://monitor.yspanel.com/test") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Mission Control test endpoint accessible")
                    print(f"📊 Service available: {data.get('service_available')}")
                    print(f"🔧 WebSocket enabled: {data.get('websocket_enabled')}")
                else:
                    print(f"⚠️  Mission Control test endpoint returned {response.status}")
                    
    except Exception as e:
        print(f"❌ HTTP test failed: {e}")

async def main():
    """Run all tests"""
    
    print("=" * 60)
    print("MISSION CONTROL WEBSOCKET SERVER-SIDE DIAGNOSTICS")
    print("=" * 60)
    
    # Test local WebSocket
    await test_websocket_local()
    
    # Test production WebSocket
    await test_websocket_production()
    
    # Test HTTP endpoint
    await test_http_endpoint()
    
    print("\n" + "=" * 60)
    print("DIAGNOSTICS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
