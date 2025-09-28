from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="FlowMind AI API - Simplified")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    expose_headers=["Content-Length", "X-Process-Time"],
    max_age=600
)

@app.get("/")
async def root():
    return {"message": "FlowMind AI API is running!"}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "service": "FlowMind AI API"}

# Basic workflows endpoint
@app.get("/api/workflows")
async def get_workflows():
    return [
        {
            "id": "1",
            "name": "Sample Workflow",
            "description": "A sample workflow for testing",
            "nodes": [],
            "edges": [],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }
    ]

@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    return {
        "id": workflow_id,
        "name": f"Workflow {workflow_id}",
        "description": f"Workflow with ID {workflow_id}",
        "nodes": [],
        "edges": [],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }

@app.post("/api/workflows")
async def create_workflow(workflow_data: dict):
    return {
        "id": "new_workflow_id",
        "name": workflow_data.get("name", "New Workflow"),
        "description": workflow_data.get("description", ""),
        "nodes": workflow_data.get("nodes", []),
        "edges": workflow_data.get("edges", []),
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }

@app.put("/api/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, workflow_data: dict):
    return {
        "id": workflow_id,
        "name": workflow_data.get("name", f"Workflow {workflow_id}"),
        "description": workflow_data.get("description", ""),
        "nodes": workflow_data.get("nodes", []),
        "edges": workflow_data.get("edges", []),
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }

@app.delete("/api/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    return {"message": f"Workflow {workflow_id} deleted successfully"}

@app.post("/api/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, execution_data: dict = None):
    return {
        "success": True,
        "message": f"Workflow {workflow_id} executed successfully",
        "workflow_id": workflow_id,
        "execution_id": "exec_123",
        "execution_time": 1.5,
        "status": "completed",
        "results": {"output_0": "Workflow execution completed!"}
    }

if __name__ == "__main__":
    print("Starting FlowMind API Server on http://localhost:8002")
    uvicorn.run(app, host="0.0.0.0", port=8002) 