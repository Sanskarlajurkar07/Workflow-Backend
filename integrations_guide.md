# Connecting Your External Accounts

To use GitHub, Airtable, and Notion nodes in your workflows, you need to first connect your accounts. This guide will walk you through the process.

## Why Connect Your Accounts?

The GitHub, Airtable, and Notion nodes need access to your accounts to perform actions on your behalf, such as:

- **GitHub**: Creating issues, pull requests, or comments; listing repositories or branches
- **Airtable**: Reading, creating, or updating records in your bases
- **Notion**: Managing pages, databases, and comments

Without connecting your accounts, these nodes won't be able to function in your workflows.

## How to Connect Your Accounts

1. Go to the **Integrations** page by clicking on your profile icon in the top-right corner and selecting "Integrations" or by navigating to `/integrations`
2. For each service (GitHub, Airtable, Notion), you'll need to provide an API token or key

### GitHub

1. Go to your [GitHub Token Settings](https://github.com/settings/tokens)
2. Click "Generate new token" → "Generate new token (classic)"
3. Add a note like "Workflow Automation"
4. Select the `repo` scope (for repository access)
5. Click "Generate token" and copy the token value
6. Paste the token in the GitHub section of the Integrations page

### Airtable

1. Go to [Airtable API tokens](https://airtable.com/create/tokens)
2. Click "Create new token"
3. Name your token (e.g., "Workflow Automation")
4. Select the appropriate scopes for your bases
5. Copy the generated API key
6. Paste the API key in the Airtable section of the Integrations page

### Notion

1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Click "New integration"
3. Name your integration and select the workspace
4. Click "Submit"
5. Copy the "Internal Integration Token"
6. Paste the token in the Notion section of the Integrations page
7. **Important**: You need to share each database with your integration:
   - Go to each Notion database you want to access
   - Click the "..." menu in the top-right corner
   - Select "Add connections"
   - Choose your integration from the list

## Security Information

- Your API tokens and keys are stored securely in our database
- We only use your tokens to perform the actions you specify in your workflows
- You can disconnect your accounts at any time from the Integrations page
- We recommend using tokens with the minimum permissions necessary for your workflows

## Troubleshooting

If you encounter issues when connecting your accounts:

- **GitHub**: Make sure you've selected the correct scopes for your token
- **Airtable**: Verify that your API key has permissions for the bases you want to access
- **Notion**: Ensure you've shared your databases with your integration

For additional help, please contact our support team. 