import logging
import time
from typing import Dict, Any
from fastapi import Request, HTTPException
from models.workflow import NodeResult
import httpx
import base64

logger = logging.getLogger("workflow_api")

async def handle_github_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float,
    request: Request
) -> NodeResult:
    """
    Handle GitHub node execution for workflow automation.
    
    This handles GitHub operations like:
    - Reading files from repositories
    - Creating pull requests
    - Creating issues
    - Listing repositories
    - Getting repository information
    - Listing commits
    - And other GitHub API operations
    """
    try:
        # Get user ID from request
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            raise ValueError("User authentication required for GitHub operations")

        # Check if user has GitHub OAuth connection
        oauth_connection = await request.app.mongodb["oauth_connections"].find_one({
            "user_id": user_id,
            "service_name": "github"
        })
        
        if not oauth_connection:
            raise ValueError("GitHub account not connected. Please connect your GitHub account first.")
        
        # Check if token is still valid
        from datetime import datetime
        expires_at = oauth_connection.get('expires_at')
        if expires_at and expires_at < datetime.utcnow():
            raise ValueError("GitHub token has expired. Please reconnect your GitHub account.")

        # Get GitHub access token
        access_token = oauth_connection.get('access_token')
        if not access_token:
            raise ValueError("No valid GitHub access token found.")

        # Extract parameters from node data
        params = node_data.get('params', {})
        action = params.get('action', 'read-file')
        owner_name = params.get('ownerName', '')
        repo_name = params.get('repoName', '')
        branch_name = params.get('branchName', 'main')
        file_name = params.get('fileName', '')
        title = params.get('title', '')
        body = params.get('body', '')
        pull_number = params.get('pullNumber', '')
        
        # Override with dynamic inputs if provided
        if isinstance(inputs.get("input"), dict):
            input_data = inputs.get("input", {})
            owner_name = input_data.get('ownerName', owner_name)
            repo_name = input_data.get('repoName', repo_name)
            branch_name = input_data.get('branchName', branch_name)
            file_name = input_data.get('fileName', file_name)
            title = input_data.get('title', title)
            body = input_data.get('body', body)
            pull_number = input_data.get('pullNumber', pull_number)

        # Validate required parameters based on action
        if action != 'list-repositories' and not owner_name:
            raise ValueError("Owner name is required for this GitHub action")
        
        if action not in ['list-repositories'] and not repo_name:
            raise ValueError("Repository name is required for this GitHub action")

        # Execute the GitHub action
        result_data = await execute_github_action(
            action=action,
            access_token=access_token,
            owner_name=owner_name,
            repo_name=repo_name,
            branch_name=branch_name,
            file_name=file_name,
            title=title,
            body=body,
            pull_number=pull_number,
            params=params
        )

        # Return successful result
        return NodeResult(
            output=result_data,
            type="object",
            execution_time=time.time() - start_time,
            status="success",
            node_id=node_id,
            node_name=params.get("nodeName", f"GitHub - {action}")
        )

    except Exception as e:
        logger.error(f"Error in GitHub node {node_id}: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=time.time() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "GitHub")
        )

async def execute_github_action(
    action: str,
    access_token: str,
    owner_name: str = "",
    repo_name: str = "",
    branch_name: str = "main",
    file_name: str = "",
    title: str = "",
    body: str = "",
    pull_number: str = "",
    params: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Execute a specific GitHub action using the GitHub API"""
    
    headers = {
        "Authorization": f"token {access_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Workflow-Automation-App"
    }
    
    async with httpx.AsyncClient() as client:
        if action == "read-file":
            # Read a file from the repository
            if not file_name:
                raise ValueError("File name is required for reading files")
            
            url = f"https://api.github.com/repos/{owner_name}/{repo_name}/contents/{file_name}"
            if branch_name:
                url += f"?ref={branch_name}"
            
            response = await client.get(url, headers=headers)
            if response.status_code == 404:
                raise ValueError(f"File '{file_name}' not found in repository '{owner_name}/{repo_name}' on branch '{branch_name}'")
            elif response.status_code != 200:
                raise ValueError(f"GitHub API error: {response.status_code} - {response.text}")
            
            file_data = response.json()
            
            # Decode file content if it's base64 encoded
            if file_data.get('encoding') == 'base64':
                content = base64.b64decode(file_data['content']).decode('utf-8')
            else:
                content = file_data.get('content', '')
            
            return {
                "action": "read-file",
                "file_path": file_name,
                "content": content,
                "size": file_data.get('size', 0),
                "sha": file_data.get('sha', ''),
                "download_url": file_data.get('download_url', ''),
                "repository": f"{owner_name}/{repo_name}",
                "branch": branch_name,
                "encoding": file_data.get('encoding', 'utf-8')
            }
        
        elif action == "list-repositories":
            # List repositories for the owner
            if owner_name:
                # List repositories for a specific user/organization
                url = f"https://api.github.com/users/{owner_name}/repos"
                params_dict = {"sort": "updated", "per_page": 100}
            else:
                # List repositories for the authenticated user
                url = "https://api.github.com/user/repos"
                params_dict = {"sort": "updated", "per_page": 100}
            
            response = await client.get(url, headers=headers, params=params_dict)
            if response.status_code != 200:
                raise ValueError(f"GitHub API error: {response.status_code} - {response.text}")
            
            repos = response.json()
            
            # Format repository data
            repo_list = []
            for repo in repos:
                repo_list.append({
                    "name": repo.get('name', ''),
                    "full_name": repo.get('full_name', ''),
                    "description": repo.get('description', ''),
                    "private": repo.get('private', False),
                    "html_url": repo.get('html_url', ''),
                    "clone_url": repo.get('clone_url', ''),
                    "ssh_url": repo.get('ssh_url', ''),
                    "default_branch": repo.get('default_branch', 'main'),
                    "language": repo.get('language', ''),
                    "stars": repo.get('stargazers_count', 0),
                    "forks": repo.get('forks_count', 0),
                    "watchers": repo.get('watchers_count', 0),
                    "open_issues": repo.get('open_issues_count', 0),
                    "size": repo.get('size', 0),
                    "created_at": repo.get('created_at', ''),
                    "updated_at": repo.get('updated_at', ''),
                    "pushed_at": repo.get('pushed_at', ''),
                    "topics": repo.get('topics', []),
                    "archived": repo.get('archived', False),
                    "disabled": repo.get('disabled', False)
                })
            
            return {
                "action": "list-repositories",
                "owner": owner_name or "authenticated_user",
                "repositories": repo_list,
                "count": len(repo_list)
            }
        
        elif action == "get-repository-info":
            # Get detailed repository information
            url = f"https://api.github.com/repos/{owner_name}/{repo_name}"
            
            response = await client.get(url, headers=headers)
            if response.status_code == 404:
                raise ValueError(f"Repository '{owner_name}/{repo_name}' not found")
            elif response.status_code != 200:
                raise ValueError(f"GitHub API error: {response.status_code} - {response.text}")
            
            repo = response.json()
            
            return {
                "action": "get-repository-info",
                "repository": {
                    "name": repo.get('name', ''),
                    "full_name": repo.get('full_name', ''),
                    "description": repo.get('description', ''),
                    "private": repo.get('private', False),
                    "html_url": repo.get('html_url', ''),
                    "clone_url": repo.get('clone_url', ''),
                    "ssh_url": repo.get('ssh_url', ''),
                    "default_branch": repo.get('default_branch', 'main'),
                    "language": repo.get('language', ''),
                    "stars": repo.get('stargazers_count', 0),
                    "forks": repo.get('forks_count', 0),
                    "watchers": repo.get('watchers_count', 0),
                    "open_issues": repo.get('open_issues_count', 0),
                    "size": repo.get('size', 0),
                    "created_at": repo.get('created_at', ''),
                    "updated_at": repo.get('updated_at', ''),
                    "pushed_at": repo.get('pushed_at', ''),
                    "topics": repo.get('topics', []),
                    "license": repo.get('license', {}).get('name', '') if repo.get('license') else '',
                    "archived": repo.get('archived', False),
                    "disabled": repo.get('disabled', False),
                    "owner": {
                        "login": repo.get('owner', {}).get('login', ''),
                        "type": repo.get('owner', {}).get('type', ''),
                        "avatar_url": repo.get('owner', {}).get('avatar_url', '')
                    }
                }
            }
        
        elif action == "list-commits":
            # List commits for the repository
            url = f"https://api.github.com/repos/{owner_name}/{repo_name}/commits"
            params_dict = {"per_page": 30}
            if branch_name:
                params_dict["sha"] = branch_name
            
            response = await client.get(url, headers=headers, params=params_dict)
            if response.status_code != 200:
                raise ValueError(f"GitHub API error: {response.status_code} - {response.text}")
            
            commits = response.json()
            
            # Format commit data
            commit_list = []
            for commit in commits:
                commit_list.append({
                    "sha": commit.get('sha', ''),
                    "message": commit.get('commit', {}).get('message', ''),
                    "author": {
                        "name": commit.get('commit', {}).get('author', {}).get('name', ''),
                        "email": commit.get('commit', {}).get('author', {}).get('email', ''),
                        "date": commit.get('commit', {}).get('author', {}).get('date', '')
                    },
                    "committer": {
                        "name": commit.get('commit', {}).get('committer', {}).get('name', ''),
                        "email": commit.get('commit', {}).get('committer', {}).get('email', ''),
                        "date": commit.get('commit', {}).get('committer', {}).get('date', '')
                    },
                    "html_url": commit.get('html_url', ''),
                    "stats": commit.get('stats', {}),
                    "files_changed": len(commit.get('files', []))
                })
            
            return {
                "action": "list-commits",
                "repository": f"{owner_name}/{repo_name}",
                "branch": branch_name,
                "commits": commit_list,
                "count": len(commit_list)
            }
        
        elif action == "create-issue":
            # Create a new issue
            if not title:
                raise ValueError("Title is required for creating issues")
            
            url = f"https://api.github.com/repos/{owner_name}/{repo_name}/issues"
            data = {
                "title": title,
                "body": body or ""
            }
            
            response = await client.post(url, headers=headers, json=data)
            if response.status_code != 201:
                raise ValueError(f"GitHub API error: {response.status_code} - {response.text}")
            
            issue = response.json()
            
            return {
                "action": "create-issue",
                "issue_number": issue.get('number'),
                "title": issue.get('title'),
                "body": issue.get('body'),
                "html_url": issue.get('html_url'),
                "state": issue.get('state'),
                "created_at": issue.get('created_at'),
                "repository": f"{owner_name}/{repo_name}",
                "author": issue.get('user', {}).get('login', '')
            }
        
        elif action == "create-pull-request":
            # Create a new pull request
            if not title:
                raise ValueError("Title is required for creating pull requests")
            
            head = params.get('head', branch_name)
            base = params.get('base', 'main')
            
            url = f"https://api.github.com/repos/{owner_name}/{repo_name}/pulls"
            data = {
                "title": title,
                "body": body or "",
                "head": head,
                "base": base
            }
            
            response = await client.post(url, headers=headers, json=data)
            if response.status_code != 201:
                raise ValueError(f"GitHub API error: {response.status_code} - {response.text}")
            
            pr = response.json()
            
            return {
                "action": "create-pull-request",
                "pr_number": pr.get('number'),
                "title": pr.get('title'),
                "body": pr.get('body'),
                "html_url": pr.get('html_url'),
                "state": pr.get('state'),
                "head": pr.get('head', {}).get('ref'),
                "base": pr.get('base', {}).get('ref'),
                "created_at": pr.get('created_at'),
                "repository": f"{owner_name}/{repo_name}",
                "author": pr.get('user', {}).get('login', ''),
                "mergeable": pr.get('mergeable'),
                "merged": pr.get('merged', False)
            }
        
        elif action == "update-pull-request":
            # Update an existing pull request
            if not pull_number:
                raise ValueError("Pull request number is required for updating pull requests")
            
            url = f"https://api.github.com/repos/{owner_name}/{repo_name}/pulls/{pull_number}"
            data = {}
            
            if title:
                data["title"] = title
            if body:
                data["body"] = body
            
            # Only update if there's something to update
            if not data:
                raise ValueError("At least title or body must be provided for updating pull requests")
            
            response = await client.patch(url, headers=headers, json=data)
            if response.status_code != 200:
                raise ValueError(f"GitHub API error: {response.status_code} - {response.text}")
            
            pr = response.json()
            
            return {
                "action": "update-pull-request",
                "pr_number": pr.get('number'),
                "title": pr.get('title'),
                "body": pr.get('body'),
                "html_url": pr.get('html_url'),
                "state": pr.get('state'),
                "head": pr.get('head', {}).get('ref'),
                "base": pr.get('base', {}).get('ref'),
                "updated_at": pr.get('updated_at'),
                "repository": f"{owner_name}/{repo_name}",
                "author": pr.get('user', {}).get('login', ''),
                "mergeable": pr.get('mergeable'),
                "merged": pr.get('merged', False)
            }
        
        else:
            raise ValueError(f"Unsupported GitHub action: {action}") 