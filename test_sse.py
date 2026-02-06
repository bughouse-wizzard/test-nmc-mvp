#!/usr/bin/env python3
"""
Test script for SSE endpoint.
"""
import asyncio
import aiohttp
import json
import sys
import uuid


async def test_sse_endpoint():
    """Test the SSE endpoint."""
    # Create a search ID for testing
    search_id = uuid.uuid4()
    print(f"Testing SSE endpoint for search ID: {search_id}")
    
    # Start the SSE connection
    url = f"http://localhost:8000/api/search/{search_id}/events"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                print(f"Response status: {response.status}")
                print(f"Content-Type: {response.headers.get('Content-Type')}")
                
                # Read SSE events
                print("\nWaiting for events (timeout: 10 seconds)...")
                
                # We'll read for 10 seconds to see if we get any events
                timeout = 10
                start_time = asyncio.get_event_loop().time()
                
                async for line in response.content:
                    if line:
                        line = line.decode('utf-8').strip()
                        if line:
                            print(f"Received: {line}")
                    
                    # Check timeout
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        print(f"\nTimeout reached after {timeout} seconds")
                        break
                        
    except aiohttp.ClientError as e:
        print(f"Client error: {e}")
    except Exception as e:
        print(f"Error: {e}")


async def test_create_search_and_sse():
    """Test creating a search and then listening to SSE events."""
    import requests
    
    # First, create a search
    print("Creating a search...")
    create_url = "http://localhost:8000/api/search/"
    
    search_data = {
        "object_name": "Test Object",
        "ktru_code": "123456",
        "okpd2_code": None,
        "customer_region": "СЗФО",
        "law": "44-ФЗ",
        "date_from": "2023-01-01T00:00:00Z",
        "date_to": "2024-01-01T00:00:00Z",
        "execution_statuses": ["Исполнение завершено"],
        "limit_contracts": 30,
        "characteristics_text": "Test description",
        "manufacturer": None
    }
    
    try:
        response = requests.post(create_url, json=search_data)
        print(f"Create search response: {response.status_code}")
        
        if response.status_code == 200:
            search_response = response.json()
            search_id = search_response["id"]
            print(f"Search created with ID: {search_id}")
            
            # Now test SSE endpoint
            print(f"\nTesting SSE endpoint for search ID: {search_id}")
            await test_sse_for_search(search_id)
        else:
            print(f"Failed to create search: {response.text}")
            
    except Exception as e:
        print(f"Error creating search: {e}")


async def test_sse_for_search(search_id):
    """Test SSE endpoint for a specific search ID."""
    url = f"http://localhost:8000/api/search/{search_id}/events"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                print(f"SSE Response status: {response.status}")
                print(f"SSE Content-Type: {response.headers.get('Content-Type')}")
                
                # Read SSE events for 15 seconds
                print("\nListening for SSE events (timeout: 15 seconds)...")
                
                timeout = 15
                start_time = asyncio.get_event_loop().time()
                event_count = 0
                
                buffer = ""
                async for line in response.content:
                    if line:
                        line = line.decode('utf-8')
                        buffer += line
                        
                        # Check if we have a complete SSE event (ends with double newline)
                        if buffer.endswith("\n\n"):
                            event_count += 1
                            print(f"\nEvent #{event_count}:")
                            print(buffer.strip())
                            buffer = ""
                    
                    # Check timeout
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        print(f"\nTimeout reached after {timeout} seconds")
                        print(f"Total events received: {event_count}")
                        break
                        
                if event_count == 0:
                    print("No events received. The search may not have started processing yet.")
                    
    except aiohttp.ClientError as e:
        print(f"Client error: {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    # Check if we should run the server first
    if len(sys.argv) > 1 and sys.argv[1] == "--server":
        # Run the server
        import subprocess
        import os
        
        print("Starting FastAPI server...")
        os.chdir("/workspace/workspace_ai-feat-task_302_af85661174ab40ecbf67ed35794a0cf3")
        proc = subprocess.Popen(
            ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
            cwd="backend",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait a bit for server to start
        import time
        time.sleep(3)
        
        # Run the test
        asyncio.run(test_create_search_and_sse())
        
        # Kill the server
        proc.terminate()
    else:
        # Just run the test (assuming server is already running)
        asyncio.run(test_create_search_and_sse())