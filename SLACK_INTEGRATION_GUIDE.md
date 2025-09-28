# Slack Integration Guide

This guide explains how to set up and use the Slack integration in the Workflow Automation platform.

## Setup Instructions

1. **Create a Slack App**
   - Go to [Slack API](https://api.slack.com/apps)
   - Click "Create New App"
   - Choose "From scratch"
   - Name your app and select your workspace

2. **Configure OAuth & Permissions**
   - Navigate to "OAuth & Permissions" in your Slack app settings
   - Add the following scopes:
     - `chat:write` - Send messages
     - `channels:read` - View channels
     - `channels:history` - View message history
   - Add your redirect URL: `http://localhost:8000/api/slack/oauth/callback` (development)
   - For production, add: `https://your-domain.com/api/slack/oauth/callback`

3. **Install App to Workspace**
   - Click "Install to Workspace"
   - Authorize the requested permissions

## Environment Variables

Add these variables to your `.env` file:

```env
SLACK_CLIENT_ID=8803196426178.8946644524070
SLACK_CLIENT_SECRET=48bc071ec2284bfa3f753b5ea3b70194
SLACK_SIGNING_SECRET=32409b58869324f982aa32c5ace42e80
```

## Using the Slack Node

The Slack node supports two main actions:

1. **Send Message**
   - Select a channel from the dropdown
   - Enter your message text
   - The message will be sent when the workflow runs

2. **Read Messages**
   - Select a channel from the dropdown
   - Specify how many messages to read (1-100)
   - The node will fetch the most recent messages when the workflow runs

## Security Considerations

- Keep your Slack credentials secure
- Use environment variables for sensitive data
- Implement proper error handling
- Monitor API rate limits
- Use HTTPS in production

## Troubleshooting

1. **OAuth Errors**
   - Verify your client ID and secret
   - Check redirect URL configuration
   - Ensure proper scopes are set

2. **API Errors**
   - Check token validity
   - Verify channel names and permissions
   - Monitor rate limits

3. **Connection Issues**
   - Verify network connectivity
   - Check SSL/TLS configuration
   - Validate API endpoint URLs

## API Endpoints

### OAuth Callback
```http
GET /api/slack/oauth/callback
```
Handles the OAuth flow callback from Slack.

### Get Channels
```http
GET /api/slack/channels
Authorization: Bearer <token>
```
Returns a list of available channels for the authenticated user.

## Support

For additional help:
- Check Slack's [API documentation](https://api.slack.com/docs)
- Review our [troubleshooting guide](./TROUBLESHOOTING.md)
- Contact support at support@flowmind.ai 