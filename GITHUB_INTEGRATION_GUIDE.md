# GitHub Integration Guide

This workflow automation platform has **two different GitHub integrations** that serve different purposes:

## 1. GitHub OAuth for User Authentication 🔐

**Purpose**: User login and account management
**Location**: Login/Signup pages
**Usage**: Allows users to sign in to the platform using their GitHub account

### Features:
- Sign in with GitHub button on login page
- Creates user account automatically
- Redirects to dashboard after successful login
- Manages user sessions

### Setup:
- Configured in `backend/routers/auth.py`
- Uses GitHub OAuth App credentials
- Handles user authentication flow

---

## 2. GitHub Nodes for Workflow Automation 🤖

**Purpose**: Automate GitHub operations within workflows
**Location**: Workflow builder (drag-and-drop nodes)
**Usage**: Perform GitHub actions like reading files, creating PRs, managing repositories

### Features:
- **Read Files**: Get content from any repository file
- **List Repositories**: Get all repos for a user/organization
- **Create Issues**: Automatically create GitHub issues
- **Create Pull Requests**: Generate PRs programmatically
- **Repository Management**: Access repo metadata and information

### Available Actions:
1. **Read a File**
   - Read content from any file in a repository
   - Specify owner, repo, branch, and file path
   - Returns file content and metadata

2. **List Repositories**
   - Get all repositories for a user or organization
   - Returns repo details, stars, forks, languages, etc.

3. **Create Issue**
   - Create new issues in repositories
   - Set title, description, and other properties

4. **Create Pull Request**
   - Generate pull requests between branches
   - Set title, description, head, and base branches

5. **Update Pull Request** (planned)
   - Modify existing pull requests

### How to Use GitHub Nodes:

1. **Connect Your Account**:
   - Drag a GitHub node into your workflow
   - Click "Connect GitHub Account"
   - Authorize the application
   - You'll be redirected back to your workflow

2. **Configure the Node**:
   - Select the action you want to perform
   - Fill in required parameters (owner, repo, etc.)
   - Set up any dynamic inputs from previous nodes

3. **Execute the Workflow**:
   - The node will use your connected GitHub account
   - Perform the specified action
   - Return results to the next node

### Example Workflow:
```
Input Node → GitHub Node (Read File) → AI Node (Analyze Code) → Output Node
```

### Authentication:
- Uses OAuth2 with GitHub API
- Stores access tokens securely
- Checks token expiration automatically
- Prompts for reconnection when needed

### Permissions:
The GitHub nodes request these permissions:
- `repo`: Access to repositories (read/write)
- `user:email`: Access to user's email address

### Error Handling:
- Clear error messages for missing parameters
- Token expiration detection
- File not found handling
- API rate limit awareness

---

## Key Differences:

| Feature | Login OAuth | Workflow Nodes |
|---------|-------------|----------------|
| **Purpose** | User authentication | Automation tasks |
| **Scope** | Platform access | Repository operations |
| **Usage** | One-time login | Repeated workflow actions |
| **Redirect** | To dashboard | Back to workflow |
| **Token Storage** | Session-based | Persistent for automation |

---

## Technical Implementation:

### Frontend:
- `useGitHubOAuth.ts`: Hook for node authentication
- `GitHubNode.tsx`: Node component with UI
- `OAuthCallback.tsx`: Handles OAuth redirects
- `Login.tsx`: Login page OAuth

### Backend:
- `github_node.py`: Node execution handler
- `routers/auth.py`: OAuth endpoints
- `node_handlers.py`: Node registration
- OAuth connections stored in MongoDB

---

## Troubleshooting:

### Common Issues:
1. **"GitHub account not connected"**
   - Solution: Click "Connect GitHub Account" in the node

2. **"Token has expired"**
   - Solution: Reconnect your GitHub account

3. **"Owner name is required"**
   - Solution: Fill in the repository owner field

4. **"File not found"**
   - Solution: Check file path, branch name, and repository access

### Debug Steps:
1. Check connection status in the node
2. Verify repository permissions
3. Test with public repositories first
4. Check browser console for errors
5. Review backend logs for API errors

---

## Security Notes:

- Tokens are stored securely in the database
- OAuth state parameters prevent CSRF attacks
- Minimal required permissions requested
- Automatic token expiration handling
- No sensitive data logged

This dual GitHub integration provides both secure user authentication and powerful workflow automation capabilities! 