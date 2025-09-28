# Working with Integration Nodes

This document provides instructions for setting up and using the GitHub, Airtable, and Notion integration nodes in your workflows.

## Overview

The workflow automation system includes the following integration nodes:

1. **GitHub Integration Node**: Connect with GitHub repositories, issues, pull requests, and more.
2. **Airtable Integration Node**: Interact with Airtable bases, tables, and records.
3. **Notion Integration Node**: Work with Notion databases, pages, and comments.

## Prerequisites

Before using these integration nodes, you need to set up API credentials for each service:

### GitHub API Credentials

1. Go to your GitHub settings: https://github.com/settings/apps
2. Create a Personal Access Token (PAT) with appropriate scopes:
   - For repositories: `repo`
   - For user info: `user`
3. Save the token securely - you'll need it when configuring the GitHub node.

### Airtable API Credentials

1. Go to Airtable account settings: https://airtable.com/create/tokens
2. Create a Personal Access Token with scopes appropriate for your use case.
3. Save the token securely - you'll need it when configuring the Airtable node.

### Notion API Credentials

1. Go to Notion integrations: https://www.notion.so/my-integrations
2. Create a new integration.
3. Configure the capabilities and content access permissions.
4. Save the integration token - you'll need it when configuring the Notion node.
5. Remember to share your Notion database with your integration.

## Storing Your Credentials

There are two ways to provide API credentials to the integration nodes:

1. **User-specific credentials**: Users can store their own API credentials in their account settings.
   - Go to the user profile menu
   - Select "Integrations"
   - Click on the integration you want to configure
   - Enter your API key/token
   - Click "Save"

2. **System-wide credentials** (only for GitHub): Administrators can set up GitHub App credentials in the `.env` file:
   ```
   GITHUB_APP_CLIENT_ID=your-github-client-id
   GITHUB_APP_CLIENT_SECRET=your-github-client-secret
   ```

## Using Integration Nodes in Workflows

### GitHub Integration Node

The GitHub node provides the following actions:

- **List Repositories**: List repositories for the authenticated user.
- **Get Repository Info**: Get details about a specific repository.
- **List Issues**: List issues in a repository.
- **Get Issue**: Get details about a specific issue.
- **Create Issue**: Create a new issue in a repository.
- **Create Pull Request**: Create a new pull request.
- **List Branches**: List branches in a repository.
- **Create Comment**: Add a comment to an issue or pull request.

#### Example Workflow with GitHub Integration

1. Create a new workflow
2. Add an Input node
3. Add a GitHub node
   - Set action to "Create Issue"
   - Enter repository owner and name
   - Set title and body fields
4. Connect the Input node to the GitHub node
5. Add an Output node
6. Connect the GitHub node to the Output node

### Airtable Integration Node

The Airtable node provides the following actions:

- **List Bases**: List all bases accessible to the authenticated user.
- **List Tables**: List all tables in a base.
- **List Records**: Retrieve records from a table.
- **Get Record**: Get a specific record by ID.
- **Create Record**: Create a new record in a table.
- **Update Record**: Update an existing record.
- **Delete Record**: Delete a record from a table.

#### Example Workflow with Airtable Integration

1. Create a new workflow
2. Add an Input node
3. Add an Airtable node
   - Set action to "Create Record"
   - Enter base ID and table ID
   - Set the fields JSON object
4. Connect the Input node to the Airtable node
5. Add an Output node
6. Connect the Airtable node to the Output node

### Notion Integration Node

The Notion node provides the following actions:

- **List Databases**: List all databases accessible to the integration.
- **Query Database**: Query a database for pages matching certain criteria.
- **Get Page**: Get details of a specific page.
- **Create Page**: Create a new page in a database or as a child of another page.
- **Update Page**: Update an existing page's properties.
- **Create Comment**: Add a comment to a page or block.
- **List Users**: List users in the workspace.

#### Example Workflow with Notion Integration

1. Create a new workflow
2. Add an Input node
3. Add a Notion node
   - Set action to "Create Page"
   - Enter parent ID (database ID)
   - Configure the properties JSON object
4. Connect the Input node to the Notion node
5. Add an Output node
6. Connect the Notion node to the Output node

## Dynamic Configuration with Input Data

All integration nodes can accept dynamic configuration from their input connections. This allows you to build workflows where the API operation parameters come from previous nodes.

For example, to dynamically set the title of a GitHub issue:

1. Configure an AI node to generate a title
2. Connect it to the GitHub node
3. In the GitHub node input, map the AI output to the title field

## Troubleshooting

Common issues and solutions:

- **Authentication Errors**: Ensure your API keys are correctly stored and have sufficient permissions.
- **Not Found Errors**: Verify that IDs for repositories, bases, tables, records, databases, or pages are correct.
- **Permission Errors**: Check that your API token has the necessary scopes or permissions.
- **Rate Limiting**: If you encounter rate limit errors, implement a delay node before the integration node.

For more help, check the API documentation for each service:

- GitHub API: https://docs.github.com/en/rest
- Airtable API: https://airtable.com/developers/web/api
- Notion API: https://developers.notion.com/reference 