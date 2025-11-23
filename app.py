import fastapi
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from routes import user

app = fastapi.FastAPI()
app.include_router(user.router, prefix="/user", tags=["user"])
print("User routes loaded.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    return {"Hello": "World"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
