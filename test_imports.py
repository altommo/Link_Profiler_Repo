#!/usr/bin/env python3
"""
Test script to verify that the import issues have been fixed.
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
    
    # Test importing some of the services that were fixed
    from Link_Profiler.services.domain_service import DomainService
    print("[OK] DomainService import successful")
    
    from Link_Profiler.services.web3_service import Web3Service
    print("[OK] Web3Service import successful")
    
    from Link_Profiler.services.link_health_service import LinkHealthService
    print("[OK] LinkHealthService import successful")
    
    from Link_Profiler.services.ai_service import AIService
    print("[OK] AIService import successful")
    
    from Link_Profiler.services.serp_service import SERPService
    print("[OK] SERPService import successful")
    
    from Link_Profiler.clients.whois_client import WHOISClient
    print("[OK] WHOISClient import successful")
    
    print("\n[SUCCESS] All imports successful! The ImportError issue has been resolved.")
    
except ImportError as e:
    print(f"[ERROR] Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Unexpected error: {e}")
    sys.exit(1)
