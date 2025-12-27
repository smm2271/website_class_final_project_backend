import requests
import pprint

class test_class():
    def __init__(self, user_id, password):
        self.user_id = user_id
        self.password = password
        self.token = self.login()
    
    def login(self):
        url = "http://127.0.0.1:8000/user/login"
        payload = {
            "user_id": self.user_id,
            "password": self.password
        }
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            token = response.cookies.get("access_token")
            print("Login successful, access token:", token)
            return token
        else:
            print("Login failed:", response.text)
            return None
        
    def get_rooms(self):
        url = "http://127.0.0.1:8000/message/get_rooms"
        cookies = {
            "access_token": self.token
        }
        response = requests.get(url, cookies=cookies)
        if response.status_code == 200:
            print("Get rooms successful")
            pprint.pprint(response.json())
        else:
            print("Get rooms failed:", response.text)
            return None
    
    def create_room(self, room_name=None):
        url = "http://127.0.0.1:8000/message/create_room"
        cookies = {
            "access_token": self.token
        }
        payload = {}
        if room_name:
            payload["room_name"] = room_name
        response = requests.post(url, json=payload, cookies=cookies)
        if response.status_code == 200:
            print("Create room successful")
            pprint.pprint(response.json())
        else:
            print("Create room failed:", response.text)
            return None

if __name__ == "__main__":
    tester = test_class()
    tester.get_rooms()
    tester.create_room("test_room_2")
    tester.get_rooms()