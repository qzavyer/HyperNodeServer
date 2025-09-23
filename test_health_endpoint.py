#!/usr/bin/env python3
"""Simple test script for health endpoint."""

import requests
import json
import time

def test_health_endpoint():
    """Test the health endpoint."""
    try:
        # Start the server in background (this is just for testing)
        print("Testing health endpoint...")
        
        # Test the health endpoint
        response = requests.get("http://localhost:8000/api/v1/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Health endpoint is working!")
            print(f"Status: {data.get('status')}")
            
            if 'data' in data:
                health_data = data['data']
                print(f"Node Status: {health_data.get('nodeStatus')}")
                print(f"Error Count: {health_data.get('errorCount')}")
                print(f"Response Time: {health_data.get('responseTime')} ms")
                print(f"Uptime: {health_data.get('uptime')} seconds")
                print(f"Critical Alerts: {len(health_data.get('criticalAlerts', []))}")
                
                # Check if all required fields are present
                required_fields = ['nodeStatus', 'lastUpdate', 'errorCount', 'responseTime', 'uptime', 'criticalAlerts']
                missing_fields = [field for field in required_fields if field not in health_data]
                
                if missing_fields:
                    print(f"❌ Missing fields: {missing_fields}")
                else:
                    print("✅ All required fields present")
                    
                return True
            else:
                print("❌ No 'data' field in response")
                return False
        else:
            print(f"❌ Health endpoint returned status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure HyperNodeServer is running on localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Error testing health endpoint: {e}")
        return False

if __name__ == "__main__":
    print("Health Endpoint Test")
    print("=" * 50)
    success = test_health_endpoint()
    
    if success:
        print("\n✅ Health endpoint test PASSED")
    else:
        print("\n❌ Health endpoint test FAILED")
