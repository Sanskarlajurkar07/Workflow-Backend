#!/usr/bin/env python3
"""
Simple FastAPI server for workflow automation
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging
import uuid
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Workflow Automation API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mock data storage
mock_workflows = {
    "1": {
        "id": "1",
        "name": "Sample Workflow",
        "description": "A sample workflow for demonstration",
        "nodes": [],
        "edges": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
}

@app.get("/")
async def root():
    return {"message": "Workflow Automation API is running", "status": "ok"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "workflow-automation-backend"}

@app.get("/api/health")
async def api_health():
    return {"status": "healthy", "api": "ready"}

@app.get("/api/workflows")
async def get_workflows():
    """Get all workflows"""
    return list(mock_workflows.values())

@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get a specific workflow"""
    if workflow_id in mock_workflows:
        return mock_workflows[workflow_id]
    return JSONResponse(status_code=404, content={"detail": "Workflow not found"})

@app.post("/api/workflows")
async def create_workflow(request: Request):
    """Create a new workflow"""
    data = await request.json()
    workflow_id = str(uuid.uuid4())
    workflow = {
        "id": workflow_id,
        "name": data.get("name", "Untitled Workflow"),
        "description": data.get("description", ""),
        "nodes": data.get("nodes", []),
        "edges": data.get("edges", []),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    mock_workflows[workflow_id] = workflow
    return workflow

@app.put("/api/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, request: Request):
    """Update a workflow"""
    if workflow_id not in mock_workflows:
        return JSONResponse(status_code=404, content={"detail": "Workflow not found"})
    
    data = await request.json()
    workflow = mock_workflows[workflow_id]
    
    workflow.update({
        "name": data.get("name", workflow["name"]),
        "description": data.get("description", workflow["description"]),
        "nodes": data.get("nodes", workflow["nodes"]),
        "edges": data.get("edges", workflow["edges"]),
        "updated_at": datetime.now().isoformat()
    })
    
    return workflow

@app.delete("/api/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Delete a workflow"""
    if workflow_id not in mock_workflows:
        return JSONResponse(status_code=404, content={"detail": "Workflow not found"})
    
    del mock_workflows[workflow_id]
    return {"message": "Workflow deleted successfully"}

@app.post("/api/workflows/{workflow_id}/execute")
async def execute_workflow_by_id(workflow_id: str, request: Request):
    """Execute a specific workflow by ID"""
    try:
        data = await request.json()
        logger.info(f"Received execution request for workflow {workflow_id}: {data}")
        
        # Check if workflow exists
        if workflow_id not in mock_workflows:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": "Workflow not found",
                    "message": f"Workflow with ID {workflow_id} not found"
                }
            )
        
        # Mock successful execution
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "execution_id": str(uuid.uuid4()),
                "workflow_id": workflow_id,
                "status": "completed",
                "message": "Workflow executed successfully (mock)",
                "execution_time": 1.23,
                "results": {
                    "output_0": "Mock execution result"
                },
                "details": {
                    "received_inputs": data.get("inputs", {}),
                    "mode": data.get("mode", "standard"),
                    "note": "This is a mock execution. Backend server is running but workflow execution requires full setup with MongoDB, Redis, and node handlers."
                }
            }
        )
    except Exception as e:
        logger.error(f"Error processing workflow execution for {workflow_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal Server Error",
                "message": str(e)
            }
        )

@app.post("/api/workflows/execute")
async def execute_workflow(request: Request):
    """Legacy workflow execution endpoint"""
    try:
        data = await request.json()
        logger.info(f"Received workflow execution request: {data}")
        
        # Return a helpful error message explaining the issue
        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "error": "Network Error",
                "message": "Backend server is running but workflow execution requires full setup with MongoDB, Redis, and other dependencies. Please check the backend configuration.",
                "details": {
                    "received_data": data,
                    "server_status": "running",
                    "issue": "Missing workflow execution dependencies"
                }
            }
        )
    except Exception as e:
        logger.error(f"Error processing workflow request: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal Server Error",
                "message": str(e)
            }
        )

@app.options("/api/workflows/execute")
async def options_execute_workflow():
    return {"message": "CORS preflight"}

@app.options("/api/workflows/{workflow_id}/execute")
async def options_execute_workflow_by_id(workflow_id: str):
    return {"message": "CORS preflight"}

if __name__ == "__main__":
    print("Starting Workflow Automation Backend on http://localhost:8002")
    print("Available endpoints:")
    print("  GET  /api/workflows - List all workflows")
    print("  POST /api/workflows - Create new workflow")
    print("  GET  /api/workflows/{id} - Get specific workflow")
    print("  PUT  /api/workflows/{id} - Update workflow")
    print("  POST /api/workflows/{id}/execute - Execute workflow")
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info") 