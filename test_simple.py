#!/usr/bin/env python3
"""
Very simple test script
"""
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Test server working!"}

@app.get("/test")
async def test():
    return {"status": "ok", "message": "API is responding"}

if __name__ == "__main__":
    print("Starting test server on http://localhost:8003")
    uvicorn.run(app, host="127.0.0.1", port=8003) 