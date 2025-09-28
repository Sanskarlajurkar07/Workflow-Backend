from motor.motor_asyncio import AsyncIOMotorCollection
from fastapi import FastAPI, Request, Depends
from contextlib import asynccontextmanager

async def get_database(request: Request):
    return request.app.mongodb

async def get_user_collection(request: Request):
    return request.app.mongodb["users"]

async def get_workflow_collection(request: Request):
    return request.app.mongodb["workflows"]