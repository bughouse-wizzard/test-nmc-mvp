import requests
import subprocess
import time
import sys

def test_fastapi():
    """Test the FastAPI application"""
    print("Testing FastAPI application...")
    
    # Start the server in background
    print("Starting FastAPI server...")
    server = subprocess.Popen(
        ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Give server time to start
    time.sleep(3)
    
    try:
        # Test root endpoint
        print("Testing root endpoint...")
        response = requests.get("http://localhost:8000/")
        if response.status_code == 200:
            print(f"✓ Root endpoint OK: {response.json()}")
        else:
            print(f"✗ Root endpoint failed: {response.status_code}")
            return False
        
        # Test health endpoint
        print("Testing health endpoint...")
        response = requests.get("http://localhost:8000/api/health")
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                print(f"✓ Health endpoint OK: {data}")
            else:
                print(f"✗ Health endpoint status mismatch: {data}")
                return False
        else:
            print(f"✗ Health endpoint failed: {response.status_code}")
            return False
        
        # Test info endpoint
        print("Testing info endpoint...")
        response = requests.get("http://localhost:8000/api/info")
        if response.status_code == 200:
            print(f"✓ Info endpoint OK: {response.json()}")
        else:
            print(f"✗ Info endpoint failed: {response.status_code}")
            return False
        
        print("\n✅ All API tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Error during testing: {e}")
        return False
    finally:
        # Kill the server
        server.terminate()
        server.wait()

def test_static_files():
    """Test that static files are accessible"""
    print("\nTesting static files...")
    
    # Check if files exist
    import os
    static_files = [
        "app/static/index.html",
        "app/static/js/app.js",
        "app/static/css/styles.css"
    ]
    
    for file_path in static_files:
        if os.path.exists(file_path):
            print(f"✓ {file_path} exists")
        else:
            print(f"✗ {file_path} missing")
            return False
    
    # Check HTML file references
    with open("app/static/index.html", "r") as f:
        html_content = f.read()
        
    if 'href="css/styles.css"' in html_content:
        print("✓ HTML references CSS correctly")
    else:
        print("✗ HTML missing CSS reference")
        return False
        
    if 'src="js/app.js"' in html_content:
        print("✓ HTML references JS correctly")
    else:
        print("✗ HTML missing JS reference")
        return False
    
    print("✅ Static files test passed!")
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("Running integration tests for Task 2")
    print("=" * 50)
    
    # Test static files first
    if not test_static_files():
        sys.exit(1)
    
    # Test FastAPI
    if not test_fastapi():
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("✅ All tests passed! Task 2 completed successfully.")
    print("=" * 50)