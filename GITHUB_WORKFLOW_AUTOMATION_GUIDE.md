# GitHub Workflow Automation - Complete Guide

## 🎯 Overview

The GitHub workflow automation system provides powerful integration with GitHub's API, allowing you to automate repository operations, code analysis, and development workflows. This guide covers everything you need to know about using GitHub nodes in your automation workflows.

## 🔧 Setup & Authentication

### 1. Connect Your GitHub Account

1. **In the Workflow Builder**:
   - Drag a GitHub node onto the canvas
   - Click "Connect GitHub Account"
   - You'll be redirected to GitHub for authorization
   - After authorization, you'll return to your workflow (NOT the dashboard)

2. **Permissions Granted**:
   - `user:email` - Access to your email address
   - `repo` - Full access to repositories (read/write)

### 2. Verify Connection

- The GitHub node will show "Connected as @username" when successful
- Click the refresh button to check connection status
- If expired, reconnect by clicking "Connect GitHub Account" again

## 📋 Available Actions

### 1. **Read File** 📄
Read content from any file in a repository.

**Required Fields**:
- Owner Name (e.g., "octocat")
- Repository Name (e.g., "Hello-World")
- Branch Name (e.g., "main")
- File Path (e.g., "README.md", "src/index.js")

**Output**:
```json
{
  "action": "read-file",
  "file_path": "README.md",
  "content": "# Hello World\nThis is a test repository...",
  "size": 1024,
  "sha": "abc123...",
  "download_url": "https://raw.githubusercontent.com/...",
  "repository": "octocat/Hello-World",
  "branch": "main",
  "encoding": "utf-8"
}
```

**Use Cases**:
- Code analysis and review
- Configuration file processing
- Documentation extraction
- License compliance checking

### 2. **List Repositories** 📚
Get all repositories for a user or organization.

**Required Fields**:
- Owner Name (user/organization name)

**Output**:
```json
{
  "action": "list-repositories",
  "owner": "octocat",
  "repositories": [
    {
      "name": "Hello-World",
      "full_name": "octocat/Hello-World",
      "description": "My first repository on GitHub!",
      "private": false,
      "html_url": "https://github.com/octocat/Hello-World",
      "clone_url": "https://github.com/octocat/Hello-World.git",
      "ssh_url": "git@github.com:octocat/Hello-World.git",
      "default_branch": "main",
      "language": "JavaScript",
      "stars": 1420,
      "forks": 42,
      "watchers": 1420,
      "open_issues": 5,
      "size": 108,
      "created_at": "2011-01-26T19:01:12Z",
      "updated_at": "2011-01-26T19:14:43Z",
      "pushed_at": "2011-01-26T19:06:43Z",
      "topics": ["octocat", "atom", "electron", "api"],
      "archived": false,
      "disabled": false
    }
  ],
  "count": 1
}
```

**Use Cases**:
- Repository discovery and cataloging
- Bulk operations across repositories
- Portfolio analysis
- License auditing

### 3. **Get Repository Info** ℹ️
Get detailed information about a specific repository.

**Required Fields**:
- Owner Name
- Repository Name

**Output**:
```json
{
  "action": "get-repository-info",
  "repository": {
    "name": "Hello-World",
    "full_name": "octocat/Hello-World",
    "description": "My first repository on GitHub!",
    "private": false,
    "html_url": "https://github.com/octocat/Hello-World",
    "clone_url": "https://github.com/octocat/Hello-World.git",
    "ssh_url": "git@github.com:octocat/Hello-World.git",
    "default_branch": "main",
    "language": "JavaScript",
    "stars": 1420,
    "forks": 42,
    "watchers": 1420,
    "open_issues": 5,
    "size": 108,
    "created_at": "2011-01-26T19:01:12Z",
    "updated_at": "2011-01-26T19:14:43Z",
    "pushed_at": "2011-01-26T19:06:43Z",
    "topics": ["octocat", "atom", "electron", "api"],
    "license": "MIT",
    "archived": false,
    "disabled": false,
    "owner": {
      "login": "octocat",
      "type": "User",
      "avatar_url": "https://github.com/images/error/octocat_happy.gif"
    }
  }
}
```

**Use Cases**:
- Repository health checks
- Metadata extraction
- Compliance verification
- Analytics and reporting

### 4. **List Commits** 📝
Get recent commits from a repository branch.

**Required Fields**:
- Owner Name
- Repository Name
- Branch Name

**Output**:
```json
{
  "action": "list-commits",
  "repository": "octocat/Hello-World",
  "branch": "main",
  "commits": [
    {
      "sha": "6dcb09b5b57875f334f61aebed695e2e4193db5e",
      "message": "Fix all the bugs",
      "author": {
        "name": "Monalisa Octocat",
        "email": "support@github.com",
        "date": "2011-04-14T16:00:49Z"
      },
      "committer": {
        "name": "Monalisa Octocat",
        "email": "support@github.com",
        "date": "2011-04-14T16:00:49Z"
      },
      "html_url": "https://github.com/octocat/Hello-World/commit/6dcb09b5b57875f334f61aebed695e2e4193db5e",
      "stats": {
        "additions": 104,
        "deletions": 4,
        "total": 108
      },
      "files_changed": 5
    }
  ],
  "count": 1
}
```

**Use Cases**:
- Change tracking and analysis
- Release note generation
- Code review automation
- Activity monitoring

### 5. **Create Issue** 🐛
Create a new issue in a repository.

**Required Fields**:
- Owner Name
- Repository Name
- Title

**Optional Fields**:
- Body (description)

**Output**:
```json
{
  "action": "create-issue",
  "issue_number": 1,
  "title": "Found a bug",
  "body": "I'm having a problem with this.",
  "html_url": "https://github.com/octocat/Hello-World/issues/1",
  "state": "open",
  "created_at": "2011-04-22T13:33:48Z",
  "repository": "octocat/Hello-World",
  "author": "octocat"
}
```

**Use Cases**:
- Automated bug reporting
- Task creation from monitoring
- Issue templating
- Workflow-driven issue management

### 6. **Create Pull Request** 🔄
Create a new pull request between branches.

**Required Fields**:
- Owner Name
- Repository Name
- Title
- Head Branch (source)
- Base Branch (target, defaults to "main")

**Optional Fields**:
- Body (description)

**Output**:
```json
{
  "action": "create-pull-request",
  "pr_number": 1,
  "title": "New feature",
  "body": "Please pull these awesome changes",
  "html_url": "https://github.com/octocat/Hello-World/pull/1",
  "state": "open",
  "head": "new-feature",
  "base": "main",
  "created_at": "2011-01-26T19:01:12Z",
  "repository": "octocat/Hello-World",
  "author": "octocat",
  "mergeable": true,
  "merged": false
}
```

**Use Cases**:
- Automated code deployment
- Feature branch management
- Code review automation
- Release preparation

### 7. **Update Pull Request** ✏️
Update an existing pull request.

**Required Fields**:
- Owner Name
- Repository Name
- Pull Request Number

**Optional Fields**:
- Title (new title)
- Body (new description)

**Output**:
```json
{
  "action": "update-pull-request",
  "pr_number": 1,
  "title": "Updated feature",
  "body": "Updated description with more details",
  "html_url": "https://github.com/octocat/Hello-World/pull/1",
  "state": "open",
  "head": "new-feature",
  "base": "main",
  "updated_at": "2011-01-26T19:14:43Z",
  "repository": "octocat/Hello-World",
  "author": "octocat",
  "mergeable": true,
  "merged": false
}
```

**Use Cases**:
- PR description automation
- Status updates
- Review process management
- Automated documentation updates

## 🔗 Workflow Examples

### Example 1: Code Analysis Pipeline
```
Input Node → GitHub (Read File) → AI Node (Analyze Code) → GitHub (Create Issue) → Output Node
```

### Example 2: Repository Health Check
```
Input Node → GitHub (List Repos) → GitHub (Get Repo Info) → AI Node (Generate Report) → Notification Node
```

### Example 3: Automated Release Notes
```
Input Node → GitHub (List Commits) → AI Node (Summarize Changes) → GitHub (Create PR) → Output Node
```

### Example 4: Multi-Repository Analysis
```
Input Node → GitHub (List Repos) → Loop Node → GitHub (Read File) → AI Node (Analyze) → Data Collector
```

## 🛠️ Advanced Usage

### Dynamic Inputs
GitHub nodes can accept dynamic inputs from previous nodes:

```json
{
  "ownerName": "{{previous_node.owner}}",
  "repoName": "{{previous_node.repository}}",
  "fileName": "{{user_input.file_path}}"
}
```

### Error Handling
Common errors and solutions:

1. **"GitHub account not connected"**
   - Solution: Connect your GitHub account in the node

2. **"Token has expired"**
   - Solution: Reconnect your GitHub account

3. **"File not found"**
   - Check file path, branch name, and repository access

4. **"Repository not found"**
   - Verify owner name, repository name, and permissions

### Rate Limits
- GitHub API has rate limits (5000 requests/hour for authenticated users)
- The system automatically handles rate limiting
- For high-volume workflows, consider caching strategies

## 🔒 Security & Best Practices

### Security
- OAuth tokens are stored securely in the database
- Tokens are automatically refreshed when possible
- Minimal required permissions are requested
- No sensitive data is logged

### Best Practices
1. **Use specific branch names** instead of defaulting to "main"
2. **Validate inputs** before making API calls
3. **Handle errors gracefully** in your workflows
4. **Cache repository data** for repeated operations
5. **Use descriptive node names** for better workflow readability

## 🧪 Testing

Use the provided test script to verify functionality:

```bash
cd backend
python test_github_workflow.py
```

Make sure to:
1. Update the test configuration with your repositories
2. Have a user logged in with GitHub connected
3. Test with repositories you have access to

## 📞 Support

If you encounter issues:
1. Check the browser console for errors
2. Review backend logs for API errors
3. Verify GitHub permissions and token status
4. Test with public repositories first
5. Check GitHub API status at status.github.com

## 🚀 Future Enhancements

Planned features:
- Webhook support for real-time triggers
- Advanced search and filtering
- Bulk operations across multiple repositories
- GitHub Actions integration
- Advanced analytics and reporting

---

**Happy Automating! 🎉** 