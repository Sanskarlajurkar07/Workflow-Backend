from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from models.user import UserCreate, UserInDB, User
from config import settings
from typing import Optional, Dict, Any
from database import get_user_collection
from starlette.responses import RedirectResponse, JSONResponse, HTMLResponse
from authlib.integrations.starlette_client import OAuth
import secrets
import urllib.parse
import logging
from bson import ObjectId
import httpx
import base64
import hashlib
import time

# Add a logger at the top of the file
logger = logging.getLogger("workflow_api")

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
oauth = OAuth()

# Configure Google OAuth2
logger.info(f"Configuring Google OAuth with client_id: {settings.GOOGLE_CLIENT_ID[:8]}...")
if (settings.GOOGLE_CLIENT_ID not in ["placeholder", "your-google-client-id"] and 
    settings.GOOGLE_CLIENT_SECRET not in ["placeholder", "your-google-client-secret"]):
    oauth.register(
        name='google',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        authorize_url="https://accounts.google.com/o/oauth2/auth",
        authorize_params=None,
        access_token_url="https://accounts.google.com/o/oauth2/token",
        access_token_params=None,
        refresh_token_url="https://accounts.google.com/o/oauth2/token",
        jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
        userinfo_endpoint="https://openidconnect.googleapis.com/v1/userinfo",
        client_kwargs={
            'scope': 'openid email profile',
            'token_endpoint_auth_method': 'client_secret_post'
        }
    )
    logger.info("Google OAuth client registration complete")
else:
    logger.warning("Google OAuth credentials are placeholders, skipping Google OAuth setup")

# Configure Airtable OAuth2
logger.info(f"Configuring Airtable OAuth with client_id: {settings.AIRTABLE_CLIENT_ID[:8] if settings.AIRTABLE_CLIENT_ID != 'placeholder' else 'placeholder'}...")
oauth.register(
    name='airtable',
    client_id=settings.AIRTABLE_CLIENT_ID,
    client_secret=settings.AIRTABLE_CLIENT_SECRET,
    authorize_url="https://airtable.com/oauth2/v1/authorize",
    authorize_params=None,
    access_token_url="https://airtable.com/oauth2/v1/token",
    access_token_params=None,
    client_kwargs={
        'scope': 'data.records:read data.records:write schema.bases:read',
        'token_endpoint_auth_method': 'client_secret_post'
    }
)
logger.info("Airtable OAuth client registration complete")

# Configure GitHub OAuth2
logger.info(f"Configuring GitHub OAuth with client_id: {settings.GITHUB_CLIENT_ID[:8] if hasattr(settings, 'GITHUB_CLIENT_ID') and settings.GITHUB_CLIENT_ID != 'placeholder' else 'placeholder'}...")
if hasattr(settings, 'GITHUB_CLIENT_ID') and hasattr(settings, 'GITHUB_CLIENT_SECRET'):
    oauth.register(
        name='github',
        client_id=settings.GITHUB_CLIENT_ID,
        client_secret=settings.GITHUB_CLIENT_SECRET,
        authorize_url="https://github.com/login/oauth/authorize",
        authorize_params=None,
        access_token_url="https://github.com/login/oauth/access_token",
        access_token_params=None,
        api_base_url="https://api.github.com/",
        client_kwargs={
            'scope': 'user:email repo',
            'token_endpoint_auth_method': 'client_secret_post'
        }
    )
    logger.info("GitHub OAuth client registration complete")
else:
    logger.warning("GitHub OAuth credentials not found, skipping GitHub OAuth setup")

# Configure HubSpot OAuth2
logger.info(f"Configuring HubSpot OAuth with client_id: {settings.HUBSPOT_CLIENT_ID[:8] if hasattr(settings, 'HUBSPOT_CLIENT_ID') and settings.HUBSPOT_CLIENT_ID != 'placeholder' else 'placeholder'}...")
if hasattr(settings, 'HUBSPOT_CLIENT_ID') and hasattr(settings, 'HUBSPOT_CLIENT_SECRET'):
    oauth.register(
        name='hubspot',
        client_id=settings.HUBSPOT_CLIENT_ID,
        client_secret=settings.HUBSPOT_CLIENT_SECRET,
        authorize_url="https://app.hubspot.com/oauth/authorize",
        authorize_params=None,
        access_token_url="https://api.hubapi.com/oauth/v1/token",
        access_token_params=None,
        api_base_url="https://api.hubapi.com/",
        client_kwargs={
            'scope': 'crm.objects.contacts.read crm.objects.contacts.write crm.objects.companies.read crm.objects.companies.write crm.objects.deals.read crm.objects.deals.write crm.objects.custom.read crm.objects.custom.write crm.objects.owners.read timeline communications-bridge.read',
            'token_endpoint_auth_method': 'client_secret_post'
        }
    )
    logger.info("HubSpot OAuth client registration complete")
else:
    logger.warning("HubSpot OAuth credentials not found, skipping HubSpot OAuth setup")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_SECRET_KEY, 
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt

async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme)
) -> User:
    user_doc = None
    auth_method = "None"

    # 1. Try to authenticate with JWT token if present
    if token:
        auth_method = "JWT"
        try:
            payload = jwt.decode(
                token, 
                settings.JWT_SECRET_KEY, 
                algorithms=[settings.JWT_ALGORITHM]
            )
            email: Optional[str] = payload.get("sub")
            if email:
                user_collection = await get_user_collection(request)
                user_doc = await user_collection.find_one({"email": email})
                if user_doc:
                    logger.info(f"JWT authentication successful for email: {email}")
                else:
                    logger.warning(f"JWT auth: User not found for email {email} in token.")
            else:
                logger.warning("JWT token validation failed: missing subject (sub) claim.")
        except JWTError as e:
            logger.warning(f"JWT token validation failed (JWTError): {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error validating JWT token: {str(e)}")

    # 2. If JWT auth failed or no token was provided, try session authentication
    if not user_doc:
        auth_method = "Session (fallback)" if token else "Session"
        try:
            user_id = request.session.get("user_id")
            if user_id:
                logger.debug(f"Session auth: Found user_id in session: {user_id}")
                user_collection = await get_user_collection(request)
                user_doc = await user_collection.find_one({"_id": ObjectId(user_id)})
                if user_doc:
                    logger.info(f"Session authentication successful for user ID: {user_id}")
                else:
                    logger.warning(f"Session auth: User not found in DB for session user_id: {user_id}. Clearing session.")
                    request.session.clear()
            else:
                logger.debug(f"Session auth: No user_id found in session.")
        except Exception as e:
            logger.error(f"Session authentication error: {str(e)}", exc_info=True)
            user_doc = None

    # 3. If user_doc is populated by either method, return User model
    if user_doc:
        return User(
            id=str(user_doc["_id"]),
            email=user_doc["email"],
            full_name=user_doc.get("full_name"),
            picture=user_doc.get("picture")
        )

    # 4. If we reach here, authentication failed by all methods
    logger.warning(f"Authentication failed ({auth_method} attempted). Neither JWT nor session auth succeeded.")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

# Create a version of get_current_user that can handle optional token
class OptionalOAuth2PasswordBearer(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        try:
            return await super().__call__(request)
        except HTTPException:
            return None

optional_oauth2_scheme = OptionalOAuth2PasswordBearer(tokenUrl="token")

async def get_current_user_optional_token(
    request: Request,
    token: Optional[str] = Depends(optional_oauth2_scheme)
) -> User:
    if token:
        # First try token-based auth
        try:
            payload = jwt.decode(
                token, 
                settings.JWT_SECRET_KEY, 
                algorithms=[settings.JWT_ALGORITHM]
            )
            email: str = payload.get("sub")
            if email:
                user_collection = await get_user_collection(request)
                user = await user_collection.find_one({"email": email})
                if user:
                    logger.info(f"JWT authentication successful for email: {email}")
                    return User(
                        id=str(user["_id"]),
                        email=user["email"],
                        full_name=user.get("full_name", ""),
                        picture=user.get("picture", "")
                    )
        except Exception as e:
            logger.debug(f"Optional token auth failed: {str(e)}")

    # Try session-based auth
    try:
        user_id = request.session.get("user_id")
        if user_id:
            user = await request.app.mongodb["users"].find_one({"_id": ObjectId(user_id)})
            if user:
                logger.info(f"Session authentication successful for user ID: {user_id}")
                return User(
                    id=str(user["_id"]),
                    email=user["email"],
                    full_name=user.get("full_name", ""),
                    picture=user.get("picture", "")
                )
            else:
                logger.warning(f"Session user not found for ID: {user_id}")
                request.session.clear()
        else:
            logger.debug("No user_id in session")
    except Exception as e:
        logger.error(f"Session authentication error: {str(e)}")

    logger.warning("Authentication failed - neither JWT nor session auth succeeded")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

@router.post("/token")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    user_collection = await get_user_collection(request)
    user = await user_collection.find_one({"email": form_data.username})

    # Check if user exists and has a hashed_password
    if not user or "hashed_password" not in user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password, or account uses OAuth login.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=User)
async def register(request: Request, user: UserCreate):
    user_collection = await get_user_collection(request)
    
    # Check if user exists
    if await user_collection.find_one({"email": user.email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    user_in_db = UserInDB(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name
    )
    
    result = await user_collection.insert_one(user_in_db.dict())
    
    return User(
        id=str(result.inserted_id),
        email=user.email,
        full_name=user.full_name
    )

@router.get("/google/login")
async def google_login(request: Request):
    # Check if Google OAuth is configured
    if (settings.GOOGLE_CLIENT_ID in ["placeholder", "your-google-client-id"] or 
        settings.GOOGLE_CLIENT_SECRET in ["placeholder", "your-google-client-secret"]):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth not configured. Please set up Google OAuth credentials in the backend configuration."
        )
    
    # Generate state parameter and timestamp
    state = secrets.token_urlsafe(32)
    timestamp = datetime.utcnow()
    
    # Store state in MongoDB instead of session for better persistence
    try:
        oauth_states_collection = request.app.mongodb["oauth_states"]
        
        # Clean up old states (older than 1 hour)
        await oauth_states_collection.delete_many({
            "created_at": {"$lt": timestamp - timedelta(hours=1)}
        })
        
        # Store new state
        state_data = {
            "state": state,
            "created_at": timestamp,
            "user_agent": request.headers.get('user-agent', 'unknown'),
            "ip_address": request.client.host if request.client else 'unknown'
        }
        
        await oauth_states_collection.insert_one(state_data)
        logger.info(f"Stored OAuth state in database: {state}")
        
    except Exception as e:
        logger.error(f"Failed to store OAuth state in database: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize OAuth flow"
        )
    
    # Build redirect URI dynamically
    redirect_uri = str(request.base_url.replace(path='/api/auth/google/auth'))
    logger.info(f"Google OAuth login initiated - redirect_uri: {redirect_uri}, state: {state}")
    
    try:
        return await oauth.google.authorize_redirect(
            request,
            redirect_uri,
            state=state
        )
    except Exception as e:
        logger.error(f"Google OAuth authorize_redirect error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize Google OAuth: {str(e)}"
        )

@router.get("/google/auth")
async def google_auth(request: Request):
    try:
        # Get current state from query parameters
        received_state = request.query_params.get('state')
        
        logger.info(f"Google OAuth callback received - state: {received_state}")
        
        # Validate state parameter
        if not received_state:
            logger.error("No state parameter received in OAuth callback")
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/auth/callback?error=missing_state",
                status_code=302
            )
        
        # Look up state in database
        try:
            oauth_states_collection = request.app.mongodb["oauth_states"]
            stored_state_doc = await oauth_states_collection.find_one({"state": received_state})
            
            if not stored_state_doc:
                logger.error(f"Invalid or expired state parameter: {received_state}")
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/auth/callback?error=invalid_state",
                    status_code=302
                )
            
            # Check if state has expired (10 minutes)
            state_age = datetime.utcnow() - stored_state_doc["created_at"]
            if state_age.total_seconds() > 600:
                logger.error(f"OAuth state has expired - age: {state_age.total_seconds()} seconds")
                # Clean up expired state
                await oauth_states_collection.delete_one({"state": received_state})
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/auth/callback?error=state_expired",
                    status_code=302
                )
            
            # State is valid, clean it up (one-time use)
            await oauth_states_collection.delete_one({"state": received_state})
            logger.info(f"Valid OAuth state found and cleaned up: {received_state}")
            
        except Exception as e:
            logger.error(f"Database error during state validation: {str(e)}")
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/auth/callback?error=database_error",
                status_code=302
            )
        
        # Get OAuth2 token - bypass session-based state validation
        logger.info("Attempting to get OAuth access token from Google")
        try:
            # Create a temporary request object without session state validation
            token_url = "https://oauth2.googleapis.com/token"
            code = request.query_params.get('code')
            
            if not code:
                logger.error("No authorization code received")
                return RedirectResponse(
                    url=f"{settings.FRONTEND_URL}/auth/callback?error=no_code",
                    status_code=302
                )
            
            # Exchange code for tokens directly
            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    token_url,
                    data={
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": str(request.base_url.replace(path='/api/auth/google/auth'))
                    }
                )
                
                if token_response.status_code != 200:
                    logger.error(f"Token exchange failed: {token_response.text}")
                    return RedirectResponse(
                        url=f"{settings.FRONTEND_URL}/auth/callback?error=token_exchange_failed",
                        status_code=302
                    )
                
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                
                if not access_token:
                    logger.error("No access token in response")
                    return RedirectResponse(
                        url=f"{settings.FRONTEND_URL}/auth/callback?error=no_access_token",
                        status_code=302
                    )
                
                logger.info("Successfully obtained access token from Google")
                
                # Get user info using the access token
                userinfo_response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if userinfo_response.status_code != 200:
                    logger.error(f"Failed to get user info: {userinfo_response.text}")
                    return RedirectResponse(
                        url=f"{settings.FRONTEND_URL}/auth/callback?error=userinfo_failed",
                        status_code=302
                    )
                
                user_info = userinfo_response.json()
                logger.info("Successfully retrieved user info from Google")
                
        except Exception as e:
            logger.error(f"Error during token exchange: {str(e)}", exc_info=True)
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/auth/callback?error=token_error",
                status_code=302
            )
        
        # Process user info and create/update user
        try:
            user_collection = await get_user_collection(request)
            user = await user_collection.find_one({"email": user_info['email']})
            
            is_new_user = False
            if not user:
                user_data = {
                    "email": user_info['email'],
                    "full_name": user_info.get('name', ''),
                    "oauth_provider": "google",
                    "oauth_id": user_info['id'],
                    "picture": user_info.get('picture', ''),
                    "created_at": datetime.utcnow()
                }
                result = await user_collection.insert_one(user_data)
                user_id = str(result.inserted_id)
                is_new_user = True
                logger.info(f"Created new user: {user_info['email']}")
            else:
                await user_collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": {
                        "oauth_provider": "google",
                        "oauth_id": user_info['id'],
                        "picture": user_info.get('picture', ''),
                        "last_login": datetime.utcnow()
                    }}
                )
                user_id = str(user['_id'])
                logger.info(f"Updated existing user: {user_info['email']}")
            
            # Create JWT token
            access_token = create_access_token(
                data={
                    "sub": user_info['email'],
                    "name": user_info.get('name', ''),
                    "picture": user_info.get('picture', ''),
                    "oauth_provider": "google",
                    "oauth_id": user_info['id']
                },
                expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            )
            
            # Redirect to frontend with token
            redirect_url = f"{settings.FRONTEND_URL}/auth/callback?token={access_token}"
            if is_new_user:
                redirect_url += "&new_user=true"
            
            logger.info(f"OAuth flow completed successfully for: {user_info['email']}")
            return RedirectResponse(url=redirect_url, status_code=302)
            
        except Exception as e:
            logger.error(f"Error processing user data: {str(e)}", exc_info=True)
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/auth/callback?error=user_processing_error",
                status_code=302
            )
            
    except Exception as e:
        logger.error(f"Unexpected error in Google OAuth callback: {str(e)}", exc_info=True)
        error_message = urllib.parse.quote(f"OAuth error: {str(e)}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?error={error_message}",
            status_code=302
        )

@router.get("/google/manual-complete")
async def manual_complete_google_auth(request: Request, code: str, state: Optional[str] = None):
    """
    Manually completes the OAuth flow when the frontend receives a code but not a token.
    This endpoint is called directly from the frontend when the normal flow fails.
    """
    try:
        # Set up the token request
        token_request = {
            'code': code,
            'redirect_uri': str(request.base_url.replace(path='/api/auth/google/auth')),
        }
        
        # Get token from Google
        try:
            token = await oauth.google.fetch_access_token(**token_request)
            if not token or 'access_token' not in token:
                logger.error("Failed to get access token from Google in manual completion")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get access token from Google"
                )
            logger.info("Successfully obtained access token in manual completion")
            logger.debug(f"Token keys: {token.keys()}")

        except Exception as e:
            logger.error(f"Error getting access token in manual completion: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Token error: {str(e)}"
            )
            
        # Get user info
        try:
            user_info = None
            # First attempt to parse id_token
            logger.info("Attempting to parse ID token in manual completion")
            try:
                if 'id_token' in token:
                    user_info = await oauth.google.parse_id_token(request, token)
                    logger.info("Successfully parsed ID token in manual completion")
            except Exception as e:
                logger.error(f"Error parsing ID token in manual completion: {str(e)}", exc_info=True)
            
            # If parse_id_token fails, try to get user info directly
            if not user_info:
                logger.info("Falling back to userinfo endpoint in manual completion")
                try:
                    user_info = await oauth.google.userinfo(token=token)
                    logger.info("Successfully retrieved user info from userinfo endpoint in manual completion")
                except Exception as e:
                    logger.error(f"Error from userinfo endpoint in manual completion: {str(e)}", exc_info=True)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Userinfo error: {str(e)}"
                    )
            
            if not user_info:
                logger.error("Failed to get user info via both methods in manual completion")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get user info via all methods"
                )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logger.error(f"User info error in manual completion: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User info error: {str(e)}"
            )

        # Find or create user in database
        user_collection = await get_user_collection(request)
        user = await user_collection.find_one({"email": user_info['email']})
        
        is_new_user = False
        if not user:
            # Create new user
            user_data = {
                "email": user_info['email'],
                "full_name": user_info.get('name', ''),
                "oauth_provider": "google",
                "oauth_id": user_info['sub'],
                "picture": user_info.get('picture', ''),
                "created_at": datetime.utcnow()
            }
            result = await user_collection.insert_one(user_data)
            user_id = str(result.inserted_id)
            is_new_user = True
        else:
            # Update existing user's OAuth info
            await user_collection.update_one(
                {"_id": user["_id"]},
                {"$set": {
                    "oauth_provider": "google",
                    "oauth_id": user_info['sub'],
                    "picture": user_info.get('picture', ''),
                    "last_login": datetime.utcnow()
                }}
            )
            user_id = str(user['_id'])
        
        # Create JWT token
        access_token = create_access_token(
            data={
                "sub": user_info['email'],
                "name": user_info.get('name', ''),
                "picture": user_info.get('picture', ''),
                "oauth_provider": "google",
                "oauth_id": user_info['sub']
            },
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        # Return the token directly as JSON
        return {"access_token": access_token, "token_type": "bearer"}
        
    except Exception as e:
        logger.error(f"Unexpected error in Google OAuth manual completion: {str(e)}", exc_info=True)
        error_message = urllib.parse.quote(f"OAuth error: {str(e)}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?error={error_message}",
            status_code=302
        )

@router.get("/validate")
async def validate_token(current_user: User = Depends(get_current_user)):
    """Endpoint to validate the current token"""
    return {"status": "valid", "user": current_user}

@router.get("/verify")
async def verify_session(request: Request):
    """Verify if the user's session is valid."""
    try:
        # Check if user is authenticated via session cookie
        user_id = request.session.get("user_id")
        if not user_id:
            logger.warning("Session verification failed: No user_id in session")
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get user from database
        user = await request.app.mongodb["users"].find_one({"_id": ObjectId(user_id)})
        if not user:
            # Clear invalid session
            logger.warning(f"Session verification failed: User {user_id} not found in database")
            request.session.clear()
            raise HTTPException(status_code=401, detail="User not found")
        
        # Return basic user info
        logger.info(f"Session verification successful for user {user_id}")
        return {
            "authenticated": True,
            "user_id": str(user["_id"]),
            "email": user["email"]
        }
    except Exception as e:
        logger.error(f"Session verification error: {str(e)}")
        # Clear the session if there's an error
        request.session.clear()
        raise HTTPException(status_code=401, detail="Authentication failed")

@router.post("/session")
async def create_session(request: Request, data: dict):
    """Exchange a temporary token for a session cookie."""
    token = data.get("token")
    if not token:
        logger.error("Session creation failed: No token provided")
        raise HTTPException(status_code=400, detail="Token is required")
    
    try:
        logger.info(f"Attempting to decode token starting with: {token[:10]}...")
        
        # Verify the token
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        user_email = payload.get("sub")
        if not user_email:
            logger.error("Token is missing subject claim")
            raise HTTPException(status_code=401, detail="Invalid token: missing subject")
        
        logger.info(f"Looking up user with email: {user_email}")
        
        # Get user from database
        user = await request.app.mongodb["users"].find_one({"email": user_email})
        if not user:
            logger.error(f"User not found for email: {user_email}")
            raise HTTPException(status_code=401, detail="User not found")
        
        # Set session data server-side (SessionMiddleware) for convenience
        logger.info(f"Setting session for user ID: {str(user['_id'])}")
        request.session["user_id"] = str(user["_id"])
        request.session["email"] = user["email"]

        # Also explicitly set a secure cookie for clients that prefer cookie-based auth
        response = JSONResponse({
            "success": True,
            "user_id": str(user["_id"]),
            "email": user["email"]
        })

        # Cookie parameters: httponly, secure (when FRONTEND_URL is https), samesite=None for cross-site
        is_https_frontend = settings.FRONTEND_URL.startswith("https")
        response.set_cookie(
            key=settings.SESSION_COOKIE_NAME,
            value="1",
            httponly=True,
            secure=is_https_frontend,
            samesite="none" if is_https_frontend else "lax",
            path='/',
            domain=settings.SESSION_COOKIE_DOMAIN or None,
            max_age=86400
        )

        logger.info(f"Session created successfully for: {user_email}")
        return response
    except jwt.JWTError as e:
        logger.error(f"JWT error: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token format: {str(e)}")
    except Exception as e:
        logger.error(f"Session creation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")

@router.post("/logout")
async def logout(request: Request):
    """Clear the user's session cookie."""
    request.session.clear()
    response = JSONResponse({"message": "Logged out successfully"})
    # Clear the cookie for the client
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path='/',
        domain=settings.SESSION_COOKIE_DOMAIN or None
    )
    return response

@router.post("/refresh")
async def refresh_session(request: Request):
    """Refresh the current session"""
    try:
        # Check if user has a valid session
        user_id = request.session.get('user_id')
        email = request.session.get('email')
        
        if not user_id or not email:
            logger.error("No valid session found for refresh")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No valid session found"
            )
        
        # Verify user still exists in database
        user = await request.app.mongodb["users"].find_one({"_id": ObjectId(user_id)})
        if not user:
            logger.error(f"User not found during session refresh: {user_id}")
            request.session.clear()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Update session timestamp (optional - sessions are already maintained)
        logger.info(f"Session refreshed for user: {email}")
        
        return JSONResponse({
            "success": True,
            "message": "Session refreshed successfully",
            "authenticated": True,
            "user": {
                "id": str(user["_id"]),
                "email": user["email"],
                "name": user.get("full_name", ""),
                "picture": user.get("picture", "")
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing session: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh session: {str(e)}"
        )

# PKCE helper functions for Airtable OAuth
def generate_code_verifier():
    """Generate a code verifier for PKCE"""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

def generate_code_challenge(code_verifier):
    """Generate a code challenge from the code verifier"""
    digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

# Airtable OAuth Routes
@router.get("/airtable/login")
async def airtable_login(request: Request):
    """Initiate Airtable OAuth login"""
    try:
        # Generate and store state parameter for security
        state = secrets.token_urlsafe(32)
        request.session['airtable_oauth_state'] = state
        
        # Generate PKCE parameters
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)
        
        # Store code_verifier in session for later use
        request.session['airtable_code_verifier'] = code_verifier
        
        # Set redirect URI to the backend callback endpoint
        redirect_uri = str(request.base_url.replace(path='/api/auth/airtable/auth'))
        
        logger.info(f"Airtable OAuth login initiated - redirect_uri: {redirect_uri}")
        
        # Redirect to Airtable authorization URL with PKCE parameters
        return await oauth.airtable.authorize_redirect(
            request, 
            redirect_uri,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method='S256'
        )
    except Exception as e:
        logger.error(f"Airtable OAuth authorize_redirect error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize Airtable OAuth: {str(e)}"
        )

@router.get("/airtable/auth")
async def airtable_auth(request: Request):
    """Handle Airtable OAuth callback"""
    try:
        # Verify state parameter
        state = request.query_params.get("state")
        stored_state = request.session.pop('airtable_oauth_state', None)
        
        logger.info(f"Airtable OAuth callback received - state valid: {state == stored_state}")
        
        if not state or state != stored_state:
            logger.error("State parameter mismatch or missing")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid state parameter"
            )
        
        # Get stored code_verifier
        code_verifier = request.session.pop('airtable_code_verifier', None)
        if not code_verifier:
            logger.error("No code_verifier found in session")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing code_verifier"
            )
        
        # Get OAuth2 token with PKCE
        logger.info("Attempting to get Airtable OAuth access token with PKCE")
        
        # Store code_verifier in request for authlib to use
        request.session['code_verifier'] = code_verifier
        
        token = await oauth.airtable.authorize_access_token(request)
        logger.info(f"Airtable OAuth token received - token type: {type(token)}")
        
        if not token or 'access_token' not in token:
            logger.error("Failed to get access token from Airtable")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get access token from Airtable"
            )
        
        # Store the Airtable token for the user
        user_id = request.session.get("user_id")
        if not user_id:
            logger.error("No user session found during Airtable OAuth")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not authenticated"
            )
        
        # Save Airtable OAuth connection to database
        oauth_connection = {
            "user_id": user_id,
            "service_name": "airtable",
            "access_token": token['access_token'],
            "refresh_token": token.get('refresh_token'),
            "expires_at": datetime.utcnow() + timedelta(seconds=token.get('expires_in', 7200)),
            "scope": token.get('scope'),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Update or insert OAuth connection
        await request.app.mongodb["oauth_connections"].update_one(
            {"user_id": user_id, "service_name": "airtable"},
            {"$set": oauth_connection},
            upsert=True
        )
        
        logger.info(f"Airtable OAuth connection saved for user: {user_id}")
        
        # Redirect back to frontend with success
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/oauth/callback/airtable?success=true")
        
    except Exception as e:
        logger.error(f"Error during Airtable OAuth callback: {str(e)}", exc_info=True)
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/oauth/callback/airtable?error={str(e)}")

@router.get("/airtable/status")
async def airtable_status(request: Request, current_user: User = Depends(get_current_user)):
    """Check if user has connected Airtable"""
    try:
        oauth_connection = await request.app.mongodb["oauth_connections"].find_one({
            "user_id": current_user.id,
            "service_name": "airtable"
        })
        
        if oauth_connection:
            # Check if token is still valid
            expires_at = oauth_connection.get('expires_at')
            is_expired = expires_at and expires_at < datetime.utcnow()
            
            return {
                "connected": True,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "is_expired": is_expired,
                "scope": oauth_connection.get('scope')
            }
        else:
            return {"connected": False}
            
    except Exception as e:
        logger.error(f"Error checking Airtable status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check Airtable connection status"
        )

# GitHub OAuth Routes
@router.get("/github/login")
async def github_login(request: Request):
    """Initiate GitHub OAuth login/integration"""
    try:
        # Generate and store state parameter for security
        state = secrets.token_urlsafe(32)
        request.session['github_oauth_state'] = state
        
        # Set redirect URI to the backend callback endpoint
        redirect_uri = str(request.base_url.replace(path='/api/auth/github/auth'))
        
        # Check if user is already logged in
        user_id = request.session.get("user_id")
        if user_id:
            logger.info(f"GitHub OAuth integration initiated for user: {user_id} - redirect_uri: {redirect_uri}")
        else:
            logger.info(f"GitHub OAuth authentication initiated - redirect_uri: {redirect_uri}")
        
        # Check if GitHub OAuth is configured
        if not hasattr(settings, 'GITHUB_CLIENT_ID') or settings.GITHUB_CLIENT_ID == 'placeholder':
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GitHub OAuth not configured. Please set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET."
            )
        
        # Redirect to GitHub authorization URL with appropriate scope
        # Request email scope for authentication, repo scope for integration
        scope = "user:email repo" if user_id else "user:email"
        
        return await oauth.github.authorize_redirect(
            request, 
            redirect_uri,
            state=state,
            scope=scope
        )
    except Exception as e:
        logger.error(f"GitHub OAuth authorize_redirect error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize GitHub OAuth: {str(e)}"
        )

@router.get("/github/auth")
async def github_auth(request: Request):
    """Handle GitHub OAuth callback"""
    try:
        # Verify state parameter
        state = request.query_params.get("state")
        stored_state = request.session.pop('github_oauth_state', None)
        
        logger.info(f"GitHub OAuth callback received - state valid: {state == stored_state}")
        
        if not state or state != stored_state:
            logger.error("State parameter mismatch or missing")
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/callback?error=Invalid+state+parameter")
        
        # Get OAuth2 token
        logger.info("Attempting to get GitHub OAuth access token")
        
        token = await oauth.github.authorize_access_token(request)
        logger.info(f"GitHub OAuth token received - token type: {type(token)}")
        
        if not token or 'access_token' not in token:
            logger.error("Failed to get access token from GitHub")
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/callback?error=Failed+to+get+access+token")
        
        # Get user info from GitHub (emails endpoint)
        user_info_response = await oauth.github.get('https://api.github.com/user', token=token)
        user_info = user_info_response.json()
        
        # Get user email from GitHub (emails endpoint)
        email_response = await oauth.github.get('https://api.github.com/user/emails', token=token)
        emails = email_response.json()
        primary_email = None
        for email_data in emails:
            if email_data.get('primary', False):
                primary_email = email_data['email']
                break
        
        if not primary_email and emails:
            primary_email = emails[0]['email']  # Fallback to first email
            
        if not primary_email:
            logger.error("No email found in GitHub user data")
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/callback?error=No+email+found")
        
        # Check if user is already logged in (integration flow)
        user_id = request.session.get("user_id")
        
        if user_id:
            # User is already logged in - this is an integration flow
            logger.info(f"GitHub OAuth integration for logged-in user: {user_id}")
            
            # Save GitHub OAuth connection to database
            oauth_connection = {
                "user_id": user_id,
                "service_name": "github",
                "access_token": token['access_token'],
                "refresh_token": token.get('refresh_token'),
                "expires_at": datetime.utcnow() + timedelta(seconds=token.get('expires_in', 28800)),
                "scope": token.get('scope'),
                "github_username": user_info.get('login'),
                "github_user_id": user_info.get('id'),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Update or insert OAuth connection
            await request.app.mongodb["oauth_connections"].update_one(
                {"user_id": user_id, "service_name": "github"},
                {"$set": oauth_connection},
                upsert=True
            )
            
            logger.info(f"GitHub OAuth connection saved for user: {user_id}")
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/oauth/callback/github?success=true")
        
        else:
            # User is not logged in - this is an authentication flow
            logger.info(f"GitHub OAuth authentication for email: {primary_email}")
            
            # Find or create user in database
            user_collection = await get_user_collection(request)
            user = await user_collection.find_one({"email": primary_email})
            
            is_new_user = False
            if not user:
                # Create new user
                user_data = {
                    "email": primary_email,
                    "full_name": user_info.get('name', user_info.get('login', '')),
                    "oauth_provider": "github",
                    "oauth_id": str(user_info['id']),
                    "picture": user_info.get('avatar_url', ''),
                    "created_at": datetime.utcnow()
                }
                result = await user_collection.insert_one(user_data)
                user_id = str(result.inserted_id)
                is_new_user = True
                logger.info(f"Created new user from GitHub OAuth: {user_id}")
            else:
                # Update existing user's OAuth info
                await user_collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": {
                        "oauth_provider": "github",
                        "oauth_id": str(user_info['id']),
                        "picture": user_info.get('avatar_url', ''),
                        "last_login": datetime.utcnow()
                    }}
                )
                user_id = str(user['_id'])
                logger.info(f"Updated existing user from GitHub OAuth: {user_id}")
            
            # Store user session
            request.session["user_id"] = user_id
            
            # Save GitHub OAuth connection to database
            oauth_connection = {
                "user_id": user_id,
                "service_name": "github",
                "access_token": token['access_token'],
                "refresh_token": token.get('refresh_token'),
                "expires_at": datetime.utcnow() + timedelta(seconds=token.get('expires_in', 28800)),
                "scope": token.get('scope'),
                "github_username": user_info.get('login'),
                "github_user_id": user_info.get('id'),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Update or insert OAuth connection
            await request.app.mongodb["oauth_connections"].update_one(
                {"user_id": user_id, "service_name": "github"},
                {"$set": oauth_connection},
                upsert=True
            )
            
            # Create JWT token
            access_token = create_access_token(
                data={
                    "sub": primary_email,
                    "name": user_info.get('name', user_info.get('login', '')),
                    "picture": user_info.get('avatar_url', ''),
                    "oauth_provider": "github",
                    "oauth_id": str(user_info['id'])
                },
                expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            )
            
            # Redirect to frontend with token and new user status
            redirect_url = f"{settings.FRONTEND_URL}/auth/callback?token={access_token}"
            if is_new_user:
                redirect_url += "&new_user=true"
                
            return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        logger.error(f"Error during GitHub OAuth callback: {str(e)}", exc_info=True)
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/auth/callback?error={str(e)}")

@router.get("/github/status")
async def github_status(request: Request, current_user: User = Depends(get_current_user)):
    """Check if user has connected GitHub"""
    try:
        oauth_connection = await request.app.mongodb["oauth_connections"].find_one({
            "user_id": current_user.id,
            "service_name": "github"
        })
        
        if oauth_connection:
            # Check if token is still valid
            expires_at = oauth_connection.get('expires_at')
            is_expired = expires_at and expires_at < datetime.utcnow()
            
            return {
                "connected": True,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "is_expired": is_expired,
                "scope": oauth_connection.get('scope'),
                "github_username": oauth_connection.get('github_username')
            }
        else:
            return {"connected": False}
            
    except Exception as e:
        logger.error(f"Error checking GitHub status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check GitHub connection status"
        )

# Add new GitHub Workflow OAuth Routes (separate from login OAuth)
@router.get("/github/workflow/login")
async def github_workflow_login(request: Request):
    """Initiate GitHub OAuth for workflow nodes"""
    try:
        # Check if user is authenticated
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        logger.info(f"GitHub Workflow OAuth initiated for user: {user_id}")
        
        # Generate state parameter for security
        state = secrets.token_urlsafe(32)
        request.session['github_workflow_oauth_state'] = state
        
        # Store current path to redirect back to after OAuth
        current_path = request.headers.get('referer', '/workflow-builder')
        if current_path.startswith(settings.FRONTEND_URL):
            current_path = current_path[len(settings.FRONTEND_URL):]
        request.session['workflow_redirect_path'] = current_path
        
        # Set redirect URI to workflow OAuth callback
        redirect_uri = str(request.base_url.replace(path='/api/auth/github/workflow/auth'))
        
        logger.info(f"GitHub OAuth integration initiated for user: {user_id} - redirect_uri: {redirect_uri}")
        
        # Check if GitHub Workflow OAuth is configured
        if not hasattr(settings, 'GITHUB_WORKFLOW_CLIENT_ID') or settings.GITHUB_WORKFLOW_CLIENT_ID == 'placeholder':
            # Fall back to regular GitHub OAuth if workflow OAuth is not configured
            logger.warning("GitHub Workflow OAuth not configured, falling back to regular GitHub OAuth")
            return await github_login(request)
        
        # Build GitHub OAuth URL manually for workflow
        github_auth_url = (
            f"https://github.com/login/oauth/authorize"
            f"?client_id={settings.GITHUB_WORKFLOW_CLIENT_ID}"
            f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
            f"&scope=repo%20user%3Aemail"
            f"&state={state}"
            f"&response_type=code"
        )
        
        logger.info(f"Redirecting to GitHub OAuth URL: {github_auth_url}")
        return RedirectResponse(url=github_auth_url)
    except Exception as e:
        logger.error(f"GitHub Workflow OAuth error: {str(e)}")
        # Fall back to regular GitHub OAuth on error
        logger.warning("GitHub Workflow OAuth failed, falling back to regular GitHub OAuth")
        return await github_login(request)

@router.get("/github/workflow/auth")
async def github_workflow_auth(request: Request):
    """Handle GitHub OAuth callback for workflow nodes"""
    try:
        # Verify state parameter
        state = request.query_params.get("state")
        stored_state = request.session.pop('github_workflow_oauth_state', None)
        
        if not state or state != stored_state:
            logger.error("GitHub Workflow OAuth state parameter mismatch")
            # Fall back to regular OAuth callback
            return await github_auth(request)
        
        # Get workflow redirect path from session
        workflow_path = request.session.get('workflow_redirect_path', '/workflow-builder')
        
        # Get authorization code
        code = request.query_params.get("code")
        if not code:
            raise HTTPException(status_code=400, detail="No authorization code received")
        
        # Exchange code for token manually using httpx
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                'https://github.com/login/oauth/access_token',
                data={
                    'client_id': settings.GITHUB_WORKFLOW_CLIENT_ID,
                    'client_secret': settings.GITHUB_WORKFLOW_CLIENT_SECRET,
                    'code': code,
                    'state': state
                },
                headers={
                    'Accept': 'application/json',
                    'User-Agent': 'Workflow-Automation-App'
                }
            )
            
            if token_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to exchange code for token")
            
            token_data = token_response.json()
            access_token = token_data.get('access_token')
            
            if not access_token:
                raise HTTPException(status_code=400, detail="No access token received")
        
        # Get user info to save connection details
        async with httpx.AsyncClient() as client:
            user_response = await client.get(
                'https://api.github.com/user',
                headers={
                    'Authorization': f'token {access_token}',
                    'Accept': 'application/vnd.github.v3+json',
                    'User-Agent': 'Workflow-Automation-App'
                }
            )
            
            if user_response.status_code == 200:
                user_info = user_response.json()
            else:
                user_info = {}
        
        # Store the token in database
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")
            
        # Save GitHub OAuth connection
        oauth_connection = {
            "user_id": user_id,
            "service_name": "github",
            "access_token": access_token,
            "refresh_token": token_data.get('refresh_token'),
            "expires_at": datetime.utcnow() + timedelta(seconds=token_data.get('expires_in', 28800)),
            "scope": token_data.get('scope', 'repo user:email'),
            "github_username": user_info.get('login'),
            "github_user_id": user_info.get('id'),
                    "token_type": "workflow",
            "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
        
        await request.app.mongodb["oauth_connections"].update_one(
            {"user_id": user_id, "service_name": "github"},
            {"$set": oauth_connection},
            upsert=True
        )
        
        logger.info(f"GitHub Workflow OAuth connection saved for user: {user_id}")
        
        # Clean up session
        request.session.pop('workflow_redirect_path', None)
        
        # Redirect back to workflow with success parameter
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/oauth/callback/github?success=true&workflow=true"
        )
        
    except Exception as e:
        logger.error(f"GitHub Workflow OAuth callback error: {str(e)}")
        # Fall back to regular OAuth callback
        return await github_auth(request)

# Notion Authentication Routes (Token-based system)
@router.get("/notion/login")
async def notion_login(request: Request):
    """Initiate Notion token connection flow"""
    try:
        # Check if user is authenticated
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")
        
        logger.info(f"Notion token connection initiated for user: {user_id}")
        
        # Since Notion uses token-based auth instead of OAuth, redirect to a page 
        # that will guide the user through the token setup process
        # For now, we'll redirect to frontend with a special parameter
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/integrations/notion/setup"
        )
        
    except Exception as e:
        logger.error(f"Notion login error: {str(e)}")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?error=notion_login_failed"
        )

@router.get("/notion/status")
async def notion_status(request: Request, current_user: User = Depends(get_current_user)):
    """Check if user has Notion credentials configured"""
    try:
        # Check if user has Notion credentials in the integrations collection
        integration_creds = await request.app.mongodb["integration_credentials"].find_one({
            "user_id": current_user.id,
            "integration_type": "notion"
        })
        
        if integration_creds:
            # Check if the token is still valid by making a test API call
            access_token = integration_creds.get("credentials", {}).get("access_token")
            if access_token:
                try:
                    # Test the token with a simple API call
                    async with httpx.AsyncClient() as client:
                        test_response = await client.get(
                            "https://api.notion.com/v1/users",
                            headers={
                                "Authorization": f"Bearer {access_token}",
                                "Content-Type": "application/json",
                                "Notion-Version": "2022-06-28"
                            },
                            timeout=10
                        )
                        
                        if test_response.status_code == 200:
                            return {
                                "connected": True,
                                "expires_at": None,  # Notion tokens don't expire
                                "is_expired": False,
                                "scope": "read write",
                                "token_valid": True
                            }
                        else:
                            logger.warning(f"Notion token validation failed: {test_response.status_code}")
                            return {
                                "connected": False,
                                "token_valid": False,
                                "error": "Token validation failed"
                            }
                            
                except Exception as e:
                    logger.error(f"Error validating Notion token: {str(e)}")
                    return {
                        "connected": False,
                        "token_valid": False,
                        "error": "Token validation error"
                    }
            else:
                return {
                    "connected": False,
                    "token_valid": False,
                    "error": "No access token found"
                }
        else:
            return {"connected": False}
            
    except Exception as e:
        logger.error(f"Error checking Notion status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check Notion connection status"
        )

@router.post("/notion/store-token")
async def store_notion_token(
    request: Request, 
    token_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Store Notion token and verify it works"""
    try:
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token provided")
        
        # Validate the token by making a request to Notion API
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            # Test the token by getting user info
            response = await client.get(
                "https://api.notion.com/v1/users",
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"Notion token validation failed: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid token: {response.json().get('message', 'Unknown error')}"
                )
        
        # Store the validated token
        integration_collection = request.app.mongodb["integration_credentials"]
        
        # Update or insert the credentials
        await integration_collection.update_one(
            {
                "user_id": current_user.id,
                "integration": "notion"
            },
            {
                "$set": {
                    "user_id": current_user.id,
                    "integration": "notion",
                    "credentials": {
                        "access_token": access_token,
                    },
                    "created_at": datetime.utcnow(),
                    "expires_at": None  # Notion tokens don't expire
                }
            },
            upsert=True
        )
        
        logger.info(f"Notion token stored successfully for user {current_user.id}")
        return {"success": True, "message": "Token stored successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing Notion token: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to store token: {str(e)}")

@router.get("/hubspot/login")
async def hubspot_login(request: Request):
    """Initiate HubSpot OAuth flow"""
    try:
        # Check if HubSpot OAuth is configured
        if not hasattr(settings, 'HUBSPOT_CLIENT_ID') or settings.HUBSPOT_CLIENT_ID == 'placeholder':
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="HubSpot OAuth not configured. Please set up HubSpot OAuth credentials in the backend configuration."
            )
        
        # Generate and store state parameter
        state = secrets.token_urlsafe(16)
        request.session['hubspot_oauth_state'] = state
        
        # Build redirect URI
        redirect_uri = str(request.base_url.replace(path='/api/auth/hubspot/auth'))
        logger.info(f"HubSpot OAuth login initiated - redirect_uri: {redirect_uri}")
        
        # Redirect to HubSpot OAuth
        return await oauth.hubspot.authorize_redirect(
            request,
            redirect_uri,
            state=state
        )
        
    except Exception as e:
        logger.error(f"HubSpot OAuth authorize_redirect error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize HubSpot OAuth: {str(e)}"
        )

@router.get("/hubspot/auth")
async def hubspot_auth(request: Request):
    """Handle HubSpot OAuth callback"""
    try:
        # Verify state parameter
        state = request.query_params.get('state')
        stored_state = request.session.pop('hubspot_oauth_state', None)
        
        logger.info(f"HubSpot OAuth callback received - state valid: {state == stored_state}")
        
        if not state or state != stored_state:
            logger.error(f"Invalid state parameter - received: {state}, stored: {stored_state}")
            # Return a popup callback page that will close itself and notify parent
            return HTMLResponse(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>HubSpot OAuth Error</title>
            </head>
            <body>
                <script>
                    // Notify parent window of error and close popup
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'oauth_error',
                            provider: 'hubspot',
                            error: 'Invalid state parameter'
                        }}, '{settings.FRONTEND_URL}');
                    }}
                    window.close();
                </script>
                <p>Authentication error. This window should close automatically.</p>
            </body>
            </html>
            """)
        
        # Get user ID from session
        user_id = request.session.get("user_id")
        if not user_id:
            return HTMLResponse(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>HubSpot OAuth Error</title>
            </head>
            <body>
                <script>
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'oauth_error',
                            provider: 'hubspot',
                            error: 'Not authenticated'
                        }}, '{settings.FRONTEND_URL}');
                    }}
                    window.close();
                </script>
                <p>Authentication error. This window should close automatically.</p>
            </body>
            </html>
            """)
        
        # Exchange code for token
        try:
            token = await oauth.hubspot.authorize_access_token(request)
            
            if not token or 'access_token' not in token:
                logger.error("Failed to get access token from HubSpot")
                return HTMLResponse(f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>HubSpot OAuth Error</title>
                </head>
                <body>
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{
                                type: 'oauth_error',
                                provider: 'hubspot',
                                error: 'Failed to get access token'
                            }}, '{settings.FRONTEND_URL}');
                        }}
                        window.close();
                    </script>
                    <p>Authentication error. This window should close automatically.</p>
                </body>
                </html>
                """)
            
            logger.info("Successfully obtained HubSpot access token")
            
            # Get refresh token if available
            refresh_token = token.get('refresh_token')
            expires_in = token.get('expires_in', 21600)  # HubSpot tokens expire in 6 hours by default
            
            # Store credentials in database
            integration_collection = request.app.mongodb["integration_credentials"]
            
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None
            
            await integration_collection.update_one(
                {
                    "user_id": user_id,
                    "integration": "hubspot"
                },
                {
                    "$set": {
                        "user_id": user_id,
                        "integration": "hubspot",
                        "credentials": {
                            "access_token": token['access_token'],
                            "refresh_token": refresh_token,
                            "token_type": token.get('token_type', 'bearer'),
                            "scope": token.get('scope', '')
                        },
                        "created_at": datetime.utcnow(),
                        "expires_at": expires_at
                    }
                },
                upsert=True
            )
            
            logger.info(f"HubSpot credentials stored for user {user_id}")
            
            # Return success popup callback page
            return HTMLResponse(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>HubSpot OAuth Success</title>
            </head>
            <body>
                <script>
                    // Notify parent window of success and close popup
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'oauth_success',
                            provider: 'hubspot'
                        }}, '{settings.FRONTEND_URL}');
                    }}
                    window.close();
                </script>
                <p>Successfully connected to HubSpot! This window should close automatically.</p>
            </body>
            </html>
            """)
            
        except Exception as e:
            logger.error(f"Error exchanging HubSpot code for token: {str(e)}")
            return HTMLResponse(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>HubSpot OAuth Error</title>
            </head>
            <body>
                <script>
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'oauth_error',
                            provider: 'hubspot',
                            error: 'Token exchange failed'
                        }}, '{settings.FRONTEND_URL}');
                    }}
                    window.close();
                </script>
                <p>Authentication error. This window should close automatically.</p>
            </body>
            </html>
            """)
            
    except Exception as e:
        logger.error(f"HubSpot OAuth callback error: {str(e)}")
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>HubSpot OAuth Error</title>
        </head>
        <body>
            <script>
                if (window.opener) {{
                    window.opener.postMessage({{
                        type: 'oauth_error',
                        provider: 'hubspot',
                        error: 'OAuth callback error'
                    }}, '{settings.FRONTEND_URL}');
                }}
                window.close();
            </script>
            <p>Authentication error. This window should close automatically.</p>
        </body>
        </html>
        """)

@router.get("/hubspot/status")
async def hubspot_status(request: Request, current_user: User = Depends(get_current_user)):
    """Check HubSpot connection status"""
    try:
        integration_collection = request.app.mongodb["integration_credentials"]
        
        # Find HubSpot credentials for the user
        credentials = await integration_collection.find_one({
            "user_id": current_user.id,
            "integration": "hubspot"
        })
        
        if not credentials:
            return {
                "connected": False,
                "error": "No HubSpot credentials found"
            }
        
        # Check if token is expired
        expires_at = credentials.get("expires_at")
        is_expired = False
        if expires_at and isinstance(expires_at, datetime):
            is_expired = datetime.utcnow() > expires_at
        
        # If expired and we have a refresh token, try to refresh
        if is_expired and credentials.get("credentials", {}).get("refresh_token"):
            logger.info(f"HubSpot token expired for user {current_user.id}, attempting refresh")
            # TODO: Implement token refresh logic
            pass
        
        return {
            "connected": True,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "is_expired": is_expired,
            "scope": credentials.get("credentials", {}).get("scope", "")
        }
        
    except Exception as e:
        logger.error(f"Error checking HubSpot status: {str(e)}")
        return {
            "connected": False,
            "error": str(e)
        }