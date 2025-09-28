from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Union
from enum import Enum

class IntegrationType(str, Enum):
    GITHUB = "github"
    AIRTABLE = "airtable"
    NOTION = "notion"

class GitHubActionType(str, Enum):
    CREATE_ISSUE = "create_issue"
    CREATE_PR = "create_pull_request"
    GET_REPO_INFO = "get_repo_info"
    LIST_ISSUES = "list_issues"
    GET_ISSUE = "get_issue"
    LIST_REPOS = "list_repos"
    LIST_BRANCHES = "list_branches"
    CREATE_COMMENT = "create_comment"

class AirtableActionType(str, Enum):
    LIST_RECORDS = "list_records"
    GET_RECORD = "get_record"
    CREATE_RECORD = "create_record"
    UPDATE_RECORD = "update_record"
    DELETE_RECORD = "delete_record"
    LIST_BASES = "list_bases"
    LIST_TABLES = "list_tables"

class NotionActionType(str, Enum):
    LIST_DATABASES = "list_databases"
    QUERY_DATABASE = "query_database"
    GET_PAGE = "get_page"
    CREATE_PAGE = "create_page"
    UPDATE_PAGE = "update_page"
    CREATE_COMMENT = "create_comment"
    LIST_USERS = "list_users"
    
class IntegrationCredentials(BaseModel):
    integration_type: IntegrationType
    user_id: str
    credentials: Dict[str, Any]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class GitHubCredentials(BaseModel):
    access_token: str
    
class AirtableCredentials(BaseModel):
    api_key: str
    
class NotionCredentials(BaseModel):
    access_token: str

# GitHub Models
class GitHubIssueCreate(BaseModel):
    repo_owner: str
    repo_name: str
    title: str
    body: str
    labels: Optional[List[str]] = None
    assignees: Optional[List[str]] = None

class GitHubPRCreate(BaseModel):
    repo_owner: str
    repo_name: str
    title: str
    body: str
    head: str
    base: str = "main"
    
class GitHubRepoInfo(BaseModel):
    repo_owner: str
    repo_name: str

class GitHubIssueList(BaseModel):
    repo_owner: str
    repo_name: str
    state: str = "open"
    
class GitHubIssueGet(BaseModel):
    repo_owner: str
    repo_name: str
    issue_number: int
    
class GitHubCommentCreate(BaseModel):
    repo_owner: str
    repo_name: str
    issue_number: int
    body: str

# Airtable Models
class AirtableListRecords(BaseModel):
    base_id: str
    table_id: str
    max_records: Optional[int] = None
    view: Optional[str] = None
    
class AirtableGetRecord(BaseModel):
    base_id: str
    table_id: str
    record_id: str
    
class AirtableCreateRecord(BaseModel):
    base_id: str
    table_id: str
    fields: Dict[str, Any]
    
class AirtableUpdateRecord(BaseModel):
    base_id: str
    table_id: str
    record_id: str
    fields: Dict[str, Any]
    
class AirtableDeleteRecord(BaseModel):
    base_id: str
    table_id: str
    record_id: str

# Notion Models
class NotionListDatabases(BaseModel):
    page_size: Optional[int] = 100
    
class NotionQueryDatabase(BaseModel):
    database_id: str
    filter: Optional[Dict[str, Any]] = None
    sorts: Optional[List[Dict[str, Any]]] = None
    
class NotionGetPage(BaseModel):
    page_id: str
    
class NotionCreatePage(BaseModel):
    parent_id: str
    parent_type: str = "database_id"  # Can be database_id or page_id
    properties: Dict[str, Any]
    content: Optional[List[Dict[str, Any]]] = None
    
class NotionUpdatePage(BaseModel):
    page_id: str
    properties: Dict[str, Any]
    
class NotionCreateComment(BaseModel):
    parent_id: str
    parent_type: str = "page_id"  # Can be page_id or block_id
    comment_text: str 