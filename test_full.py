import sys
import os

# Make sure we're using the right path
os.chdir('j:/final_project_backend')
sys.path.insert(0, 'j:/final_project_backend')

print("=== Testing App Import ===")
from app import app

print("\n=== All Routes ===")
for route in app.routes:
    print(f"{route}")
    
print("\n=== API Routes Only ===")
from fastapi.routing import APIRoute
api_routes = [route for route in app.routes if isinstance(route, APIRoute)]
for route in api_routes:
    print(f"Path: {route.path}, Methods: {route.methods}, Name: {route.name}")

# Now let's test the actual endpoint
print("\n=== Testing with TestClient ===")
from fastapi.testclient import TestClient
client = TestClient(app)

# Test register endpoint first
print("Testing REGISTER...")
response = client.post("/user/register", json={"user_id": "test123", "username": "Test User", "password": "testpass"})
print(f"POST /user/register -> Status: {response.status_code}, Body: {response.text}")

# Test login endpoint
print("\nTesting LOGIN...")
response = client.post("/user/login", json={"user_id": "test", "password": "test"})
print(f"POST /user/login -> Status: {response.status_code}, Body: {response.text[:200]}")
