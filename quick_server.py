from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Server is working!"}

@app.get("/api/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: str):
    return {
        "success": True,
        "message": "Mock execution - Backend is running!",
        "workflow_id": workflow_id,
        "execution_time": 1.0,
        "results": {"output_0": "Backend connected successfully!"}
    }

if __name__ == "__main__":
    print("Starting Quick Server on http://localhost:3001")
    uvicorn.run(app, host="0.0.0.0", port=3001) 