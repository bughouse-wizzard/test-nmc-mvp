#!/usr/bin/env python3
"""
Comprehensive test script for FastAPI application
- Checks file structure and dependencies
- Tests application startup and configuration
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

def check_file_exists(path, description):
    """Check if a file exists and print status"""
    if os.path.exists(path):
        print(f"✓ {description}: {path}")
        return True
    else:
        print(f"✗ {description}: {path} - NOT FOUND")
        return False

def check_directory_exists(path, description):
    """Check if a directory exists and print status"""
    if os.path.isdir(path):
        print(f"✓ {description}: {path}")
        return True
    else:
        print(f"✗ {description}: {path} - NOT FOUND")
        return False

def check_file_content(path, required_strings, description):
    """Check if file contains required strings"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        all_found = True
        for req_str in required_strings:
            if req_str in content:
                print(f"  ✓ Contains: {req_str}")
            else:
                print(f"  ✗ Missing: {req_str}")
                all_found = False
        
        return all_found
    except Exception as e:
        print(f"  ✗ Error reading file: {e}")
        return False

async def test_app_startup():
    """Test that the app can be created and has basic endpoints."""
    try:
        from app.main import app
        from app.core.config import settings
        
        print("\n🚀 Testing FastAPI application startup...")
        print(f"Project name: {settings.PROJECT_NAME}")
        print(f"Version: {settings.VERSION}")
        print(f"Database URL: {settings.DATABASE_URL}")
        print(f"Redis URL: {settings.CELERY_BROKER_URL}")
        
        # Check if app has routes
        routes = [{"path": route.path, "name": route.name} for route in app.routes]
        print(f"\nFound {len(routes)} routes:")
        for route in routes[:5]:  # Show first 5 routes
            print(f"  - {route['path']} ({route['name']})")
        
        if len(routes) > 5:
            print(f"  ... and {len(routes) - 5} more routes")
        
        print("\n✅ Application startup test passed!")
        return True
    except Exception as e:
        print(f"\n❌ Application startup failed: {e}")
        return False

def check_structure():
    """Check file and directory structure"""
    print("🔍 Checking FastAPI application structure...\n")
    
    all_checks_passed = True
    
    # Check directory structure
    print("📁 Directory Structure:")
    all_checks_passed &= check_directory_exists("app", "App directory")
    all_checks_passed &= check_directory_exists("app/static", "Static files directory")
    all_checks_passed &= check_directory_exists("app/static/css", "CSS directory")
    all_checks_passed &= check_directory_exists("app/static/js", "JS directory")
    
    print("\n📄 File Structure:")
    all_checks_passed &= check_file_exists("app/static/index.html", "Main HTML file")
    all_checks_passed &= check_file_exists("app/static/css/styles.css", "CSS file")
    all_checks_passed &= check_file_exists("app/static/js/app.js", "JavaScript file")
    all_checks_passed &= check_file_exists("main.py", "FastAPI application")
    all_checks_passed &= check_file_exists("requirements.txt", "Dependencies file")
    
    print("\n🔧 Application Code Checks:")
    
    # Check main.py
    print("\n1. Checking main.py:")
    if check_file_exists("main.py", ""):
        required_in_main = [
            "FastAPI",
            "StaticFiles",
            "app.mount",
            "/api/health",
            "health_check"
        ]
        check_file_content("main.py", required_in_main, "FastAPI app")
    
    # Check requirements.txt
    print("\n2. Checking requirements.txt:")
    if check_file_exists("requirements.txt", ""):
        required_in_reqs = ["fastapi", "uvicorn"]
        check_file_content("requirements.txt", required_in_reqs, "Dependencies")
    
    # Check HTML file references
    print("\n3. Checking HTML file references:")
    if check_file_exists("app/static/index.html", ""):
        required_in_html = [
            "/static/css/styles.css",
            "/static/js/app.js"
        ]
        check_file_content("app/static/index.html", required_in_html, "External references")
    
    return all_checks_passed

async def main():
    """Main test function"""
    print("="*60)
    print("NMCK Search API - Comprehensive Test Suite")
    print("="*60)
    
    # Run structure checks
    structure_ok = check_structure()
    
    # Run application startup test
    startup_ok = await test_app_startup()
    
    print("\n" + "="*60)
    
    if structure_ok and startup_ok:
        print("✅ All tests passed!")
        print("\nTo run the application:")
        print("  python main.py")
        print("\nThen visit:")
        print("  http://localhost:8000/")
        print("  http://localhost:8000/api/health")
        print("  http://localhost:8000/docs")
    else:
        print("❌ Some tests failed. Please review the structure and configuration.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
