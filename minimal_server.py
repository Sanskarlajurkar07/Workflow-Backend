from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# Simple CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Backend is running!"}

@app.get("/api/health")
async def health():
    return {"status": "healthy"}

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
        },
        {
            "id": "new_workflow_id",
            "name": "New Workflow",
            "description": "A new workflow",
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
        "description": "A sample workflow",
        "nodes": [],
        "edges": [],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }

@app.put("/api/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, workflow_data: dict = None):
    return {
        "success": True,
        "message": f"Workflow {workflow_id} updated successfully",
        "workflow": {
            "id": workflow_id,
            "name": workflow_data.get("name", f"Updated Workflow {workflow_id}") if workflow_data else f"Updated Workflow {workflow_id}",
            "description": workflow_data.get("description", "Updated description") if workflow_data else "Updated description",
            "nodes": workflow_data.get("nodes", []) if workflow_data else [],
            "edges": workflow_data.get("edges", []) if workflow_data else [],
            "updated_at": "2024-01-01T00:00:00Z"
        }
    }

@app.post("/api/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, execution_data: dict = None):
    return {
        "success": True,
        "message": f"Workflow {workflow_id} executed successfully",
        "workflow_id": workflow_id,
        "execution_id": "exec_123",
        "execution_time": 1.5,
        "status": "completed",
        "outputs": {
            "output_0": {
                "output": "Hello! This is a sample workflow output. Your workflow executed successfully!",
                "type": "Text",
                "node_id": "output-0",
                "node_name": "Output 0"
            }
        },
        "execution_path": ["input-0", "output-0"],
        "nodes_executed": 2
    }

# Authentication endpoints for OAuth compatibility
@app.get("/api/auth/verify")
async def verify_auth():
    return {"authenticated": True, "user": {"id": "1", "email": "user@example.com"}}

@app.post("/api/auth/session")
async def create_session(data: dict = None):
    return {"success": True, "message": "Session created"}

@app.post("/api/auth/logout")
async def logout():
    return {"success": True, "message": "Logged out"}

@app.post("/api/auth/refresh")
async def refresh_session():
    return {"success": True, "message": "Session refreshed"}

# OAuth provider status endpoints
@app.get("/api/auth/google/status")
async def google_auth_status():
    return {"connected": True, "is_expired": False}

@app.get("/api/auth/github/status")
async def github_auth_status():
    return {"connected": True, "is_expired": False}

@app.get("/api/auth/hubspot/status")
async def hubspot_auth_status():
    return {"connected": True, "is_expired": False}

@app.get("/api/auth/notion/status")
async def notion_auth_status():
    return {"connected": True, "is_expired": False}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 