# Google OAuth2 Implementation Guide

## 🎯 Overview

This document outlines the complete Google OAuth2 implementation for all Google services in the workflow automation system. The implementation uses popup-based OAuth (similar to GitHub/Airtable/Notion) to keep users in the workflow after authentication.

## 🏗️ Architecture

### Backend Components

1. **Google Auth Router** (`backend/routers/google_auth.py`)
   - 11 total routes for Google OAuth2 handling
   - Separate callback routes for each Google service
   - Proper token exchange and error handling

2. **Main Application** (`backend/main.py`)
   - Google auth router included with `/api` prefix
   - All routes accessible at `/api/auth/{service}/callback`

### Frontend Components

1. **Google OAuth Hook** (`src/hooks/useGoogleOAuth.ts`)
   - Reusable hook for all Google services
   - Popup-based OAuth flow
   - Message handling between popup and parent window

2. **Updated Node Components**
   - GoogleDocsNode ✅
   - GoogleDriveNode ✅
   - GmailNode ✅
   - GoogleCalendarNode ✅
   - GoogleSheetNode (exists but not updated in this session)

3. **OAuth Callback Page** (`src/pages/OAuthCallback.tsx`)
   - Enhanced to handle Google service tokens
   - Supports workflow-specific redirects

## 🔧 Configuration

### Google Cloud Console Setup

**Client ID:** `168656444308-5049dq3j9b326q5lrf7828eaolv703t9.apps.googleusercontent.com`  
**Client Secret:** `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`

**Required Redirect URIs:**
```
http://localhost:8000/api/auth/googledocs/callback
http://localhost:8000/api/auth/googledrive/callback
http://localhost:8000/api/auth/gmail/callback
http://localhost:8000/api/auth/googlesheet/callback
http://localhost:8000/api/auth/googlecalendar/callback
```

### Scopes by Service

- **Google Docs:** 
  - `https://www.googleapis.com/auth/documents`
  - `https://www.googleapis.com/auth/drive.file`

- **Google Drive:**
  - `https://www.googleapis.com/auth/drive.file`
  - `https://www.googleapis.com/auth/drive.readonly`

- **Gmail:**
  - `https://www.googleapis.com/auth/gmail.modify`
  - `https://www.googleapis.com/auth/gmail.compose`

- **Google Calendar:**
  - `https://www.googleapis.com/auth/calendar.events`
  - `https://www.googleapis.com/auth/calendar.readonly`

- **Google Sheets:**
  - `https://www.googleapis.com/auth/spreadsheets`
  - `https://www.googleapis.com/auth/drive.file`

## 🚀 Implementation Flow

### 1. User Clicks "Connect" in Node
```typescript
const handleConnect = () => {
  const scopes = ['scope1', 'scope2'];
  connectToGoogle('servicename', scopes);
};
```

### 2. Popup Opens with OAuth URL
- State parameter for security
- Current path stored in localStorage
- Popup window opens with Google consent screen

### 3. User Completes OAuth in Popup
- Google redirects to backend callback
- Backend exchanges code for tokens
- Backend redirects to frontend callback page

### 4. Frontend Callback Handles Response
- Extracts tokens from URL parameters
- Sends message to parent window with tokens
- Popup closes automatically

### 5. Parent Window Updates Node
- Receives message from popup
- Updates node data with tokens
- Node shows as authenticated

## 🔄 OAuth Flow Diagram

```
[Node] → [Hook] → [Popup] → [Google] → [Backend] → [Frontend Callback] → [Parent Window] → [Node Update]
   ↓        ↓        ↓         ↓          ↓              ↓                    ↓              ↓
Connect → Open → Consent → Redirect → Exchange → Parse Tokens → Message → Update State
```

## ✅ Current Status

### ✅ Completed
- [x] Google OAuth hook created
- [x] Backend routes for all services
- [x] GoogleDocsNode updated
- [x] GoogleDriveNode updated  
- [x] GmailNode updated
- [x] GoogleCalendarNode updated
- [x] OAuth callback page enhanced
- [x] Error handling improved

### 🔄 Pending
- [ ] GoogleSheetNode update (exists but needs hook integration)
- [ ] React Router routes for OAuth callbacks
- [ ] Production environment configuration
- [ ] Google Cloud Console verification process

## 🛠️ Usage Example

```typescript
// In any Google node component
import { useGoogleOAuth } from '../../../../hooks/useGoogleOAuth';

const MyGoogleNode = ({ id, data }) => {
  const { isLoading, error, connectToGoogle } = useGoogleOAuth(id, updateNodeData);
  
  const handleConnect = () => {
    const scopes = ['https://www.googleapis.com/auth/service'];
    connectToGoogle('servicename', scopes);
  };
  
  return (
    <button onClick={handleConnect} disabled={isLoading}>
      {isLoading ? 'Connecting...' : 'Connect to Google'}
    </button>
  );
};
```

## 🐛 Troubleshooting

### "Access blocked: App not verified"
- Add user email to test users in Google Cloud Console
- App is in testing mode and requires approved test users

### "Popup blocked"
- User needs to allow popups for the domain
- Hook will show error message automatically

### "Invalid redirect URI"
- Check Google Cloud Console redirect URI configuration
- Ensure exact match including protocol and port

## 🔐 Security Notes

- State parameter prevents CSRF attacks
- Tokens stored in node data (consider encryption for production)
- Popup origin validation prevents XSS
- HTTPS required for production deployment

## 📱 Frontend Router Configuration

Ensure these routes exist in your React Router:

```typescript
<Route path="/oauth/callback/googledocs" element={<OAuthCallback />} />
<Route path="/oauth/callback/googledrive" element={<OAuthCallback />} />
<Route path="/oauth/callback/gmail" element={<OAuthCallback />} />
<Route path="/oauth/callback/googlesheet" element={<OAuthCallback />} />
<Route path="/oauth/callback/googlecalendar" element={<OAuthCallback />} />
```

---

 