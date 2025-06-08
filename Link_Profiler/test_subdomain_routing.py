#!/usr/bin/env python3
"""
Test script to verify subdomain routing configuration
"""

import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from Link_Profiler.config.config_loader import config_loader

def test_subdomain_config():
    """Test that subdomain configuration is loaded correctly"""
    print("=== Subdomain Configuration Test ===")
    
    # Load subdomain config
    customer_subdomain = config_loader.get("subdomains.customer", "customer")
    mission_control_subdomain = config_loader.get("subdomains.mission_control", "monitor")
    
    print(f"Customer subdomain: '{customer_subdomain}'")
    print(f"Mission control subdomain: '{mission_control_subdomain}'")
    
    # Expected URLs
    print(f"\nExpected URLs:")
    print(f"  Customer Dashboard: https://{customer_subdomain}.yspanel.com")
    print(f"  Mission Control Dashboard: https://{mission_control_subdomain}.yspanel.com")
    
    # Verify config values
    if customer_subdomain == "customer":
        print("✅ Customer subdomain configuration is correct")
    else:
        print(f"❌ Customer subdomain should be 'customer', got '{customer_subdomain}'")
    
    if mission_control_subdomain == "monitor":
        print("✅ Mission control subdomain configuration is correct")
    else:
        print(f"❌ Mission control subdomain should be 'monitor', got '{mission_control_subdomain}'")

def test_url_parsing():
    """Test URL parsing logic similar to middleware"""
    from urllib.parse import urlparse
    
    print("\n=== URL Parsing Test ===")
    
    test_urls = [
        "monitor.yspanel.com",
        "customer.yspanel.com", 
        "yspanel.com",
        "api.yspanel.com",
        "localhost:8000"
    ]
    
    customer_subdomain = config_loader.get("subdomains.customer", "customer")
    mission_control_subdomain = config_loader.get("subdomains.mission_control", "monitor")
    
    for host in test_urls:
        print(f"\nTesting host: {host}")
        
        parsed_host = urlparse(f"http://{host}")
        hostname_parts = parsed_host.hostname.split('.') if parsed_host.hostname else []
        
        print(f"  Hostname parts: {hostname_parts}")
        
        if len(hostname_parts) > 2:
            subdomain = hostname_parts[0]
            print(f"  Detected subdomain: '{subdomain}'")
            
            if subdomain == customer_subdomain:
                print(f"  ✅ Matches customer subdomain")
            elif subdomain == mission_control_subdomain:
                print(f"  ✅ Matches mission control subdomain")
            else:
                print(f"  ⚠️  Unknown subdomain")
        else:
            print(f"  ℹ️  No subdomain detected")

if __name__ == "__main__":
    test_subdomain_config()
    test_url_parsing()
    print("\n=== Test Complete ===")
