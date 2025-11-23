import requests
import json

url = "http://localhost:8000/user/login"
payload = {
    "user_id": "test123",
    "password": "testpass"
}

print(f"Sending POST request to {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(url, json=payload)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
