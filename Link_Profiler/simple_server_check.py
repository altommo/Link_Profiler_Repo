#!/usr/bin/env python3
"""
Simple Remote Server Status Check
Checks if the remote server has our configuration fixes applied
"""

import urllib.request
import json
import ssl

def check_mission_control_status():
    """Check the mission control status via HTTP"""
    
    print("=" * 60)
    print("REMOTE SERVER STATUS CHECK")
    print("=" * 60)
    
    # Create SSL context that doesn't verify certificates (for testing)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        # Check if the mission control test endpoint exists
        print("\n1. Testing Mission Control test endpoint...")
        try:
            url = "https://monitor.yspanel.com/test"
            print(f"   Requesting: {url}")
            
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Mission-Control-Diagnostic/1.0')
            
            with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
                if response.getcode() == 200:
                    data = json.loads(response.read().decode())
                    print("[SUCCESS] Mission Control test endpoint accessible")
                    print(f"   Service available: {data.get('service_available')}")
                    print(f"   WebSocket enabled: {data.get('websocket_enabled')}")
                    print(f"   Full response: {data}")
                    
                    if data.get('service_available') and data.get('websocket_enabled'):
                        print("[SUCCESS] Configuration appears to be working!")
                        return True
                    else:
                        print("[WARNING] Configuration may still have issues")
                        return False
                else:
                    print(f"[ERROR] Test endpoint returned {response.getcode()}")
                    return False
                    
        except urllib.error.HTTPError as e:
            print(f"[ERROR] HTTP Error {e.code}: {e.reason}")
            if e.code == 404:
                print("   The /test endpoint doesn't exist - server may not be updated")
            return False
        except urllib.error.URLError as e:
            print(f"[ERROR] URL Error: {e.reason}")
            return False
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")
            return False
    
    except Exception as e:
        print(f"[ERROR] Overall test failed: {e}")
        return False

def check_main_api():
    """Check the main API health endpoint"""
    
    print("\n2. Testing main API health endpoint...")
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        url = "https://api.yspanel.com/health"
        print(f"   Requesting: {url}")
        
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mission-Control-Diagnostic/1.0')
        
        with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode())
                print("[SUCCESS] Main API health endpoint accessible")
                print(f"   Status: {data.get('status')}")
                print(f"   Database connected: {data.get('database_connected')}")
                return True
            else:
                print(f"[ERROR] Health endpoint returned {response.getcode()}")
                return False
                
    except Exception as e:
        print(f"[ERROR] Health endpoint failed: {e}")
        return False

def main():
    print("Checking remote server status...")
    
    mission_control_ok = check_mission_control_status()
    main_api_ok = check_main_api()
    
    print("\n" + "=" * 60)
    print("STATUS CHECK COMPLETE")
    print("=" * 60)
    
    if mission_control_ok:
        print("\n[SUCCESS] Mission Control configuration is working!")
        print("The WebSocket issue may be due to:")
        print("1. SSL/TLS configuration for WebSocket upgrades")
        print("2. Reverse proxy blocking WebSocket connections")
        print("3. Firewall rules")
        print("\nTo debug further, check server logs during WebSocket connection attempts.")
        
    elif main_api_ok:
        print("\n[PARTIAL] Main API is working but Mission Control has issues.")
        print("This suggests the server is running but:")
        print("1. Configuration changes may not be applied yet")
        print("2. Server needs to be restarted")
        print("3. Mission Control service initialization failed")
        
    else:
        print("\n[ERROR] Server appears to be down or unreachable.")
        print("1. Check if the server is running")
        print("2. Verify network connectivity")
        print("3. Check DNS resolution")

if __name__ == "__main__":
    main()
