from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Any, Literal, Optional, Union
from bson import ObjectId

# MongoDB connection model
class MongoDBCredentials(BaseModel):
    database: str
    connection_uri: str

# MySQL connection model
class MySQLCredentials(BaseModel):
    database: str
    username: str
    password: str
    host: str
    port: str = "3306"

# Base connection create model
class ConnectionCreate(BaseModel):
    name: str
    credentials: Union[MongoDBCredentials, MySQLCredentials]
    type: Literal["mongodb", "mysql"]

# Database connection representation in DB
class DatabaseConnection(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()))
    user_id: str
    name: str
    type: Literal["mongodb", "mysql"]
    credentials: Union[MongoDBCredentials, MySQLCredentials]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# MongoDB connection test model
class MongoDBTest(BaseModel):
    database: str
    connection_uri: str

# MySQL connection test model
class MySQLTest(BaseModel):
    database: str
    username: str
    password: str
    host: str
    port: str = "3306"

# Connection test response
class ConnectionTestResponse(BaseModel):
    success: bool
    message: str = ""

# Database connection response
class DatabaseConnectionResponse(BaseModel):
    id: str
    user_id: str
    name: str
    type: Literal["mongodb", "mysql"]
    credentials: Union[MongoDBCredentials, MySQLCredentials]
    created_at: datetime
    updated_at: datetime 