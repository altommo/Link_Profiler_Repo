#!/usr/bin/env python3
"""
Import Fix Script
Fixes the import issues in your WebCrawler files
"""

import os
import re
from typing import List, Tuple

def fix_imports_in_file(file_path: str) -> Tuple[bool, List[str]]:
    """Fix imports in a single file"""
    changes = []
    
    if not os.path.exists(file_path):
        return False, [f"File not found: {file_path}"]
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Fix Link_Profiler imports to relative imports
        import_fixes = [
            # Core models import
            (r'from Link_Profiler\.core\.models import', 'from core.models import'),
            (r'from Link_Profiler\.database\.database import', 'from database.database import'),
            (r'from Link_Profiler\.database\.models import', 'from database.models import'),
            (r'from Link_Profiler\.database\.clickhouse_loader import', 'from database.clickhouse_loader import'),
            (r'from Link_Profiler\.utils\.', 'from utils.'),
            (r'from Link_Profiler\.config\.', 'from config.'),
            (r'from Link_Profiler\.services\.', 'from services.'),
            (r'from Link_Profiler\.crawlers\.', 'from crawlers.'),
            (r'from Link_Profiler\.queue_system\.', 'from queue_system.'),
            (r'from Link_Profiler\.monitoring\.', 'from monitoring.'),
            (r'from Link_Profiler\.api\.', 'from api.'),
        ]
        
        for old_pattern, new_import in import_fixes:
            if re.search(old_pattern, content):
                content = re.sub(old_pattern, new_import, content)
                changes.append(f"Fixed: {old_pattern} -> {new_import}")
        
        # Save the file if changes were made
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, changes
        else:
            return False, ["No changes needed"]
            
    except Exception as e:
        return False, [f"Error processing file: {str(e)}"]


def find_python_files(directory: str) -> List[str]:
    """Find all Python files in directory"""
    python_files = []
    
    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != '__pycache__']
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    return python_files


def main():
    """Main import fix function"""
    print("🔧 Import Fix Script")
    print("=" * 50)
    
    current_dir = os.getcwd()
    print(f"Working directory: {current_dir}")
    
    # Find all Python files
    python_files = find_python_files(current_dir)
    print(f"Found {len(python_files)} Python files")
    
    # Files to prioritize (most important for crawler functionality)
    priority_files = [
        'crawlers/web_crawler.py',
        'database/database.py',
        'core/models.py',
        'main.py',
        'api/routes.py'
    ]
    
    print(f"\n🎯 Processing priority files first...")
    
    total_fixed = 0
    total_changes = 0
    
    # Process priority files first
    for priority_file in priority_files:
        if os.path.exists(priority_file):
            print(f"\n📝 Processing: {priority_file}")
            fixed, changes = fix_imports_in_file(priority_file)
            
            if fixed:
                total_fixed += 1
                total_changes += len(changes)
                print(f"   ✅ Fixed {len(changes)} imports")
                for change in changes[:3]:  # Show first 3 changes
                    print(f"      - {change}")
                if len(changes) > 3:
                    print(f"      ... and {len(changes) - 3} more")
            else:
                print(f"   ℹ️  {changes[0] if changes else 'No changes needed'}")
    
    print(f"\n🔍 Processing remaining files...")
    
    # Process all other files
    for file_path in python_files:
        # Skip if already processed
        rel_path = os.path.relpath(file_path, current_dir).replace('\\', '/')
        if rel_path in priority_files:
            continue
        
        print(f"   📝 {rel_path}", end=" ... ")
        fixed, changes = fix_imports_in_file(file_path)
        
        if fixed:
            total_fixed += 1
            total_changes += len(changes)
            print(f"✅ Fixed {len(changes)} imports")
        else:
            print("ℹ️  No changes")
    
    # Summary
    print(f"\n{'='*50}")
    print(f"🎉 Import Fix Summary")
    print(f"{'='*50}")
    print(f"Files processed: {len(python_files)}")
    print(f"Files fixed: {total_fixed}")
    print(f"Total import changes: {total_changes}")
    
    if total_fixed > 0:
        print(f"\n✅ Import fixes applied!")
        print(f"🧪 Try running your tests again:")
        print(f"   python import_test.py")
        print(f"   python fixed_crawler_test.py")
    else:
        print(f"\nℹ️  No import fixes were needed.")
    
    # Create a simple test script to verify the fixes
    create_verification_script()


def create_verification_script():
    """Create a simple verification script"""
    verification_script = '''#!/usr/bin/env python3
"""
Quick verification script to test if imports work after fixes
"""

def test_imports():
    """Test if imports work"""
    print("🧪 Testing imports after fixes...")
    
    try:
        from core.models import CrawlConfig
        print("✅ core.models import successful")
    except ImportError as e:
        print(f"❌ core.models import failed: {e}")
    
    try:
        from crawlers.web_crawler import WebCrawler
        print("✅ crawlers.web_crawler import successful")
    except ImportError as e:
        print(f"❌ crawlers.web_crawler import failed: {e}")
    
    try:
        from database.database import Database
        print("✅ database.database import successful")
    except ImportError as e:
        print(f"❌ database.database import failed: {e}")
    
    print("\\n🎯 Import test complete!")

if __name__ == "__main__":
    test_imports()
'''
    
    try:
        with open('verify_imports.py', 'w') as f:
            f.write(verification_script)
        print(f"\n📝 Created verification script: verify_imports.py")
        print(f"   Run with: python verify_imports.py")
    except Exception as e:
        print(f"⚠️  Could not create verification script: {e}")


if __name__ == "__main__":
    main()
