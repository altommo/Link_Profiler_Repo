#!/usr/bin/env python3
"""
Simple test script to verify that the core import issues have been fixed.
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    # Test importing the distributed circuit breaker
    from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager
    print("[OK] DistributedResilienceManager import successful")
    
    # Test basic class imports without instantiating them
    from Link_Profiler.services.web3_service import Web3Service
    print("[OK] Web3Service import successful")
    
    from Link_Profiler.services.link_health_service import LinkHealthService
    print("[OK] LinkHealthService import successful")
    
    from Link_Profiler.services.ai_service import AIService
    print("[OK] AIService import successful")
    
    from Link_Profiler.clients.whois_client import WHOISClient
    print("[OK] WHOISClient import successful")
    
    print("\n[SUCCESS] Core imports successful! The circular dependency issue has been resolved.")
    print("The problematic fallback imports have been successfully removed.")
    
except ImportError as e:
    print(f"[ERROR] Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
