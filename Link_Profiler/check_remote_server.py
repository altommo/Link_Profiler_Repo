#!/usr/bin/env python3
"""
Remote Server Status Check
Checks if the remote server has our configuration fixes applied
"""

import asyncio
import aiohttp
import json

async def check_mission_control_status():
    """Check the mission control status via HTTP"""
    
    print("=" * 60)
    print("REMOTE SERVER STATUS CHECK")
    print("=" * 60)
    
    try:
        async with aiohttp.ClientSession() as session:
            
            # Check if the mission control test endpoint exists
            print("\n1. Testing Mission Control test endpoint...")
            try:
                async with session.get("https://monitor.yspanel.com/test", timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        print("✅ Mission Control test endpoint accessible")
                        print(f"   📊 Service available: {data.get('service_available')}")
                        print(f"   🔧 WebSocket enabled: {data.get('websocket_enabled')}")
                        print(f"   📝 Full response: {data}")
                        
                        if data.get('service_available') and data.get('websocket_enabled'):
                            print("🎉 Configuration appears to be working!")
                        else:
                            print("⚠️  Configuration may still have issues")
                            
                    else:
                        print(f"❌ Test endpoint returned {response.status}")
                        text = await response.text()
                        print(f"   Response: {text[:200]}...")
                        
            except asyncio.TimeoutError:
                print("❌ Request timed out - server may be down")
            except aiohttp.ClientConnectorError:
                print("❌ Cannot connect to server - check if it's running")
            except Exception as e:
                print(f"❌ Request failed: {e}")
            
            # Check the main health endpoint
            print("\n2. Testing main health endpoint...")
            try:
                async with session.get("https://api.yspanel.com/health", timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        print("✅ Main API health endpoint accessible")
                        print(f"   📊 Status: {data.get('status')}")
                        print(f"   🗄️  Database connected: {data.get('database_connected')}")
                    else:
                        print(f"❌ Health endpoint returned {response.status}")
                        
            except Exception as e:
                print(f"❌ Health endpoint failed: {e}")
            
            # Check if the WebSocket endpoint responds to HTTP (should return an error but confirms routing)
            print("\n3. Testing WebSocket endpoint routing...")
            try:
                async with session.get("https://monitor.yspanel.com/ws/mission-control", timeout=10) as response:
                    print(f"   📡 WebSocket endpoint HTTP response: {response.status}")
                    if response.status == 400 or response.status == 426:
                        print("   ✅ WebSocket endpoint is routed correctly (HTTP upgrade required)")
                    else:
                        print(f"   ⚠️  Unexpected response: {response.status}")
                        
            except Exception as e:
                print(f"   ❌ WebSocket endpoint routing test failed: {e}")
    
    except Exception as e:
        print(f"❌ Overall test failed: {e}")
    
    print("\n" + "=" * 60)
    print("STATUS CHECK COMPLETE")
    print("=" * 60)
    
    print("\n📋 NEXT STEPS:")
    print("1. If the configuration is working but WebSocket still fails:")
    print("   - Check server logs for WebSocket connection attempts")
    print("   - Verify SSL/TLS configuration for WebSocket upgrades")
    print("   - Check if a reverse proxy is blocking WebSocket connections")
    print("\n2. If the configuration is not working:")
    print("   - Restart the application server to load the new config")
    print("   - Check if the config_loader.py changes were applied")
    print("   - Verify environment variables are set correctly")

if __name__ == "__main__":
    asyncio.run(check_mission_control_status())
