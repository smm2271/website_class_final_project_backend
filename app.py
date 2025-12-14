import fastapi
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from routes import user
from routes import message

app = fastapi.FastAPI()
app.include_router(user.router, prefix="/user", tags=["user"])
app.include_router(message.router, prefix="/message", tags=["message"])
print("User routes loaded.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://192.168.4.43:4200", "http://localhost:8000","http://localhost:4200","http://sumou.ddns.net:8080","http://10.8.0.1:4200"],
    # allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    return {"Hello": "World"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
