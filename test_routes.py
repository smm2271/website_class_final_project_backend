import sys
sys.path.insert(0, 'j:/final_project_backend')

from app import app
from routes import user

print("\n=== Router Object ===")
print(f"Router from routes.user: {user.router}")
print(f"Router routes: {user.router.routes}")

print("\n=== Registered Routes in App ===")
for route in app.routes:
    if hasattr(route, 'methods') and hasattr(route, 'path'):
        print(f"{list(route.methods)} {route.path} - {route.endpoint if hasattr(route, 'endpoint') else 'N/A'}")
print("======================\n")

# Test if we can manually call the endpoint
print("\n=== Testing Direct Import ===")
print(f"login_user function: {user.login_user if hasattr(user, 'login_user') else 'NOT FOUND'}")
print(f"Router prefix in app.py include: /user")
print(f"Router prefix in routes/user.py: {user.router.prefix if hasattr(user.router, 'prefix') else 'None'}")
