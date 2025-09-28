# HubSpot Integration Guide

## Overview

This guide describes the complete HubSpot CRM integration for the Workflow Automation platform. The integration allows users to connect their HubSpot account and perform various CRM operations including fetching and creating contacts, companies, deals, tickets, notes, calls, tasks, meetings, and emails.

## Features

### Supported HubSpot Objects

1. **Contacts** - Fetch and create contacts
2. **Companies** - Fetch and create companies
3. **Deals** - Fetch and create deals
4. **Tickets** - Fetch and create support tickets
5. **Notes** - Fetch and create notes (with object associations)
6. **Calls** - Fetch and create call records
7. **Tasks** - Fetch and create tasks
8. **Meetings** - Fetch and create meeting records
9. **Emails** - Fetch and create email records

### Supported Operations

- **Fetch Operations**: Retrieve data with filtering, property selection, and pagination
- **Create Operations**: Create new records with custom properties
- **Advanced Filtering**: JSON-based search with HubSpot's filter syntax
- **Property Management**: Select specific properties to fetch or set

## OAuth 2.0 Configuration

### HubSpot App Settings

The integration uses the following OAuth 2.0 configuration:

- **Client ID**: `cbecf41d-26a0-4c8c-b78d-7c3ff4a84250`
- **Client Secret**: `c1910040-c624-4fb5-a32e-438ef09b07d8`
- **Redirect URI**: `http://localhost:8000/api/auth/hubspot/auth`

### Required Scopes

The integration requests the following HubSpot scopes:

```
crm.objects.contacts.read
crm.objects.contacts.write
crm.objects.companies.read
crm.objects.companies.write
crm.objects.deals.read
crm.objects.deals.write
crm.objects.custom.read
crm.objects.custom.write
crm.objects.owners.read
timeline
communications-bridge.read
```

## Backend Implementation

### Authentication Routes

#### GET `/api/auth/hubspot/login`
Initiates the HubSpot OAuth flow by redirecting users to HubSpot's authorization server.

#### GET `/api/auth/hubspot/auth` 
Handles the OAuth callback, exchanges the authorization code for access tokens, and stores credentials.

#### GET `/api/auth/hubspot/status`
Checks the current connection status and token validity.

### HubSpot Node Handler

The `HubSpotNode` class in `backend/hubspot_node.py` provides:

- **Connection Management**: Handles OAuth token storage and validation
- **API Operations**: Implements all fetch and create operations
- **Error Handling**: Comprehensive error handling with logging
- **Rate Limiting**: Respects HubSpot API limits

### Key Methods

```python
async def execute(node_data: Dict[str, Any]) -> Dict[str, Any]
async def _handle_fetch_action(action: str, node_data: Dict[str, Any]) -> Dict[str, Any]
async def _handle_create_action(action: str, node_data: Dict[str, Any]) -> Dict[str, Any]
async def test_connection() -> Dict[str, Any]
```

## Frontend Implementation

### HubSpot OAuth Hook

The `useHubSpotOAuth` hook provides:

- **Connection Status**: Real-time connection status monitoring
- **OAuth Flow**: Handles redirect-based OAuth authentication
- **Error Handling**: Comprehensive error states and messages

### HubSpot Node Component

The `HubSpotNode` component features:

1. **Three-Step Configuration**:
   - Step 1: Action Selection (organized by object type)
   - Step 2: OAuth Authentication
   - Step 3: Action Configuration

2. **Action Categories**:
   - Visual organization by CRM object type
   - Color-coded fetch vs. create operations
   - Intuitive icons for each object type

3. **Dynamic Configuration**:
   - Context-sensitive configuration forms
   - JSON validation for complex inputs
   - Real-time connection status

## Usage Examples

### Fetching Contacts

```json
{
  "action": "fetch-contacts",
  "properties": "firstname,lastname,email,company,phone",
  "filters": {
    "propertyName": "email",
    "operator": "CONTAINS",
    "value": "@example.com"
  },
  "limit": 50
}
```

### Creating a Contact

```json
{
  "action": "create-contact",
  "properties": {
    "firstname": "John",
    "lastname": "Doe",
    "email": "john.doe@example.com",
    "phone": "+1234567890",
    "company": "Example Corp"
  }
}
```

### Creating a Deal

```json
{
  "action": "create-deal",
  "properties": {
    "dealname": "New Opportunity",
    "amount": "10000",
    "dealstage": "qualifiedtobuy",
    "pipeline": "default"
  }
}
```

### Creating a Note with Association

```json
{
  "action": "create-note",
  "properties": {
    "hs_note_body": "Follow-up call scheduled for next week",
    "hs_timestamp": "2024-01-15T10:00:00Z"
  },
  "objectId": "12345"
}
```

## Configuration Steps

### 1. HubSpot App Setup

1. Go to [HubSpot Developer Portal](https://developers.hubspot.com/)
2. Create a new app or use existing app
3. Configure OAuth settings:
   - Add redirect URI: `http://localhost:8000/api/auth/hubspot/auth`
   - Add required scopes (see above)
4. Get Client ID and Client Secret

### 2. Backend Configuration

The credentials are already configured in `backend/config.py`:

```python
HUBSPOT_CLIENT_ID: str = "cbecf41d-26a0-4c8c-b78d-7c3ff4a84250"
HUBSPOT_CLIENT_SECRET: str = "c1910040-c624-4fb5-a32e-438ef09b07d8"
```

### 3. Frontend Integration

The HubSpot node is automatically available in the node palette under "Integrations".

## Error Handling

### Common Errors

1. **OAuth Configuration Errors**
   - Invalid client credentials
   - Incorrect redirect URI
   - Missing scopes

2. **API Errors**
   - Invalid access token
   - Rate limit exceeded
   - Invalid property names
   - Malformed JSON in filters/properties

3. **Connection Errors**
   - Network timeouts
   - HubSpot service unavailable

### Error Response Format

```json
{
  "success": false,
  "error": "Error description",
  "data": null
}
```

## Security Considerations

1. **Token Storage**: Access tokens are encrypted and stored securely
2. **Scope Limitation**: Only requests necessary permissions
3. **Token Refresh**: Implements automatic token refresh when available
4. **HTTPS Required**: OAuth flow requires HTTPS in production

## Testing

### Connection Test

The integration includes a built-in connection test that verifies:

- Token validity
- API accessibility
- Basic permissions

### Test Endpoints

```bash
# Test OAuth status
GET /api/auth/hubspot/status

# Initiate OAuth flow
GET /api/auth/hubspot/login
```

## Production Deployment

### Environment Variables

```bash
HUBSPOT_CLIENT_ID=your_production_client_id
HUBSPOT_CLIENT_SECRET=your_production_client_secret
FRONTEND_URL=https://your-domain.com
```

### Redirect URI Update

Update HubSpot app settings to use production redirect URI:
```
https://your-domain.com/api/auth/hubspot/auth
```

## Troubleshooting

### Common Issues

1. **OAuth Redirect Mismatch**
   - Ensure redirect URI matches exactly in HubSpot app settings
   - Check for trailing slashes and protocol (http vs https)

2. **Scope Permission Denied**
   - Verify all required scopes are enabled in HubSpot app
   - Re-authenticate if scopes were added after initial auth

3. **API Rate Limits**
   - HubSpot has API rate limits (100 requests per 10 seconds)
   - Implement exponential backoff for retries

4. **Token Expiration**
   - HubSpot access tokens expire after 30 minutes
   - Refresh tokens are valid for 6 months
   - Implement automatic token refresh

## API Reference

### HubSpot API Endpoints Used

- **CRM Objects API v3**: `/crm/v3/objects/{objectType}`
- **Search API**: `/crm/v3/objects/{objectType}/search`
- **Associations API v4**: `/crm/v4/objects/{fromObjectType}/{objectId}/associations/{toObjectType}/{toObjectId}`
- **Owners API**: `/crm/v3/owners`

### Response Formats

All responses follow the standardized format:

```json
{
  "success": boolean,
  "data": object | array,
  "total": number,
  "metadata": {
    "endpoint": string,
    "params": object
  }
}
```

## Next Steps

1. **Enhanced Filtering**: Add support for complex multi-filter queries
2. **Bulk Operations**: Implement batch create/update operations
3. **Custom Properties**: Add support for custom property discovery
4. **Webhooks**: Add webhook support for real-time updates
5. **Pipeline Management**: Add deal pipeline and stage management
6. **File Attachments**: Add support for file uploads to HubSpot

## Support

For issues or questions regarding the HubSpot integration:

1. Check the connection status in the node
2. Review the backend logs for detailed error messages
3. Verify OAuth configuration in HubSpot developer portal
4. Test API endpoints directly using the provided credentials 