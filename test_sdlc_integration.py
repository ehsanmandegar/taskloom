#!/usr/bin/env python3
"""
Test script to verify SDLC backend integration
"""
import json
import requests
import sys

API_URL = "http://localhost:8000"

def test_sdlc_endpoints():
    """Test SDLC API endpoints"""
    print("Testing SDLC API endpoints...")
    
    # Test projects endpoint
    try:
        response = requests.get(f"{API_URL}/api/sdlc/projects")
        if response.status_code == 200:
            projects = response.json()
            print(f"✓ Projects endpoint OK. Found {len(projects)} projects")
        else:
            print(f"✗ Projects endpoint failed: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"✗ Error calling projects endpoint: {e}")
    
    # Test tasks endpoint
    try:
        response = requests.get(f"{API_URL}/api/sdlc/tasks")
        if response.status_code == 200:
            tasks = response.json()
            print(f"✓ Tasks endpoint OK. Found {len(tasks)} tasks")
        else:
            print(f"✗ Tasks endpoint failed: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"✗ Error calling tasks endpoint: {e}")
    
    # Test human intervention endpoint
    try:
        response = requests.get(f"{API_URL}/api/sdlc/human-inbox/pending")
        if response.status_code == 200:
            interventions = response.json()
            print(f"✓ Human interventions endpoint OK. Found {len(interventions)} pending interventions")
        elif response.status_code == 404:
            print("✓ Human interventions endpoint returns 404 (no pending interventions)")
        else:
            print(f"✗ Human interventions endpoint failed: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"✗ Error calling human interventions endpoint: {e}")
    
    # Create a test project if none exists
    try:
        response = requests.get(f"{API_URL}/api/sdlc/projects")
        if response.status_code == 200 and len(response.json()) == 0:
            test_project = {
                "id": "test-sdlc-project",
                "name": "SDLC Test Project",
                "description": "Test project for SDLC platform",
                "enabled": True,
                "sdlc_enabled": True,
                "workflow": {
                    "stages": ["analysis", "backend", "frontend", "testing", "deployment"],
                    "triggers": ["manual"]
                },
                "agents": {
                    "analysis": {"enabled": True, "model": "gpt-4"},
                    "backend": {"enabled": True, "model": "gpt-4"},
                    "frontend": {"enabled": True, "model": "gpt-4"},
                    "qa": {"enabled": True, "model": "gpt-4"}
                }
            }
            
            create_response = requests.post(
                f"{API_URL}/api/sdlc/projects",
                json=test_project
            )
            if create_response.status_code == 200:
                print("✓ Created test project")
            else:
                print(f"✗ Failed to create test project: {create_response.status_code}")
                print(f"Response: {create_response.text}")
    except Exception as e:
        print(f"✗ Error creating test project: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("SDLC Platform Integration Test")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        API_URL = sys.argv[1]
    
    test_sdlc_endpoints()
    
    print("\nFrontend integration instructions:")
    print("1. Start the backend: python main.py")
    print("2. Start the frontend: cd frontend && npm run dev")
    print("3. Open browser to: http://localhost:5173")
    print("4. Click on 'پلتفرم SDLC' in the navigation menu")
    print("=" * 60)