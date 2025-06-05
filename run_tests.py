#!/usr/bin/env python3
"""
Test runner script for Link Profiler
"""
import os
import sys
import subprocess
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["PYTHONPATH"] = str(PROJECT_ROOT)

def run_tests(test_type="unit", verbose=False):
    """Run tests with specified type and verbosity."""
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    # Add markers based on test type
    if test_type == "unit":
        cmd.extend(["-m", "unit"])
    elif test_type == "integration":
        cmd.extend(["-m", "integration"])
    elif test_type == "slow":
        cmd.extend(["-m", "slow"])
    elif test_type == "all":
        pass  # Run all tests
    else:
        print(f"Unknown test type: {test_type}")
        print("Available types: unit, integration, slow, all")
        return 1
    
    # Add test directory
    cmd.append("tests/")
    
    print(f"Running {test_type} tests...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT)
        return result.returncode
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        return 1
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1

def main():
    """Main function to parse arguments and run tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Link Profiler tests")
    parser.add_argument(
        "test_type", 
        nargs="?", 
        default="unit",
        choices=["unit", "integration", "slow", "all"],
        help="Type of tests to run (default: unit)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Run tests in verbose mode"
    )
    
    args = parser.parse_args()
    
    return run_tests(args.test_type, args.verbose)

if __name__ == "__main__":
    sys.exit(main())
