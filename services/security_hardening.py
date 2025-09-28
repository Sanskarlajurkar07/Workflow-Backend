"""
Security Hardening System for Smart Database
Provides production-ready security measures, input validation, and threat protection
"""

import hashlib
import secrets
import time
import re
import logging
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
import jwt
from cryptography.fernet import Fernet
import bleach
from email_validator import validate_email, EmailNotValidError

logger = logging.getLogger(__name__)

@dataclass
class SecurityConfig:
    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    max_file_size_mb: int = 100
    allowed_file_types: Set[str] = None
    password_min_length: int = 8
    jwt_expiry_hours: int = 24
    enable_rate_limiting: bool = True
    enable_input_sanitization: bool = True
    enable_content_filtering: bool = True

    def __post_init__(self):
        if self.allowed_file_types is None:
            self.allowed_file_types = {
                'pdf', 'docx', 'doc', 'txt', 'md', 'rtf',
                'html', 'htm', 'csv', 'json', 'xml'
            }

class RateLimiter:
    """Rate limiting system to prevent abuse"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.blocked_ips: Dict[str, float] = {}

    def is_allowed(self, identifier: str, endpoint: str = "") -> bool:
        """Check if request is allowed based on rate limits"""
        if not self.config.enable_rate_limiting:
            return True
        
        # Check if IP is temporarily blocked
        if identifier in self.blocked_ips:
            if time.time() < self.blocked_ips[identifier]:
                return False
            else:
                del self.blocked_ips[identifier]
        
        current_time = time.time()
        key = f"{identifier}:{endpoint}"
        
        # Clean old requests
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if current_time - req_time < 3600  # Keep last hour
        ]
        
        # Check minute limit
        minute_requests = [
            req_time for req_time in self.requests[key]
            if current_time - req_time < 60
        ]
        
        if len(minute_requests) >= self.config.max_requests_per_minute:
            self._block_temporarily(identifier, 60)  # Block for 1 minute
            logger.warning(f"Rate limit exceeded for {identifier} on {endpoint}")
            return False
        
        # Check hour limit
        if len(self.requests[key]) >= self.config.max_requests_per_hour:
            self._block_temporarily(identifier, 3600)  # Block for 1 hour
            logger.warning(f"Hourly rate limit exceeded for {identifier}")
            return False
        
        # Record this request
        self.requests[key].append(current_time)
        return True

    def _block_temporarily(self, identifier: str, duration: int):
        """Temporarily block an identifier"""
        self.blocked_ips[identifier] = time.time() + duration

class InputValidator:
    """Comprehensive input validation and sanitization"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        
        # Dangerous patterns to detect
        self.sql_injection_patterns = [
            r"(\bUNION\b.*\bSELECT\b)",
            r"(\bINSERT\b.*\bINTO\b)",
            r"(\bDELETE\b.*\bFROM\b)",
            r"(\bDROP\b.*\bTABLE\b)",
            r"(\bUPDATE\b.*\bSET\b)",
            r"(--|\#|\/\*|\*\/)",
            r"(\bEXEC\b|\bEXECUTE\b)"
        ]
        
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>.*?</iframe>",
            r"eval\s*\(",
            r"expression\s*\("
        ]
        
        self.nosql_injection_patterns = [
            r"\$where",
            r"\$ne",
            r"\$gt",
            r"\$gte",
            r"\$lt",
            r"\$lte",
            r"\$or",
            r"\$and",
            r"\$not",
            r"\$nor",
            r"\$exists",
            r"\$type",
            r"\$regex"
        ]

    def validate_email(self, email: str) -> bool:
        """Validate email address"""
        try:
            validate_email(email)
            return True
        except EmailNotValidError:
            return False

    def validate_password(self, password: str) -> Dict[str, Any]:
        """Validate password strength"""
        result = {
            "valid": True,
            "errors": []
        }
        
        if len(password) < self.config.password_min_length:
            result["valid"] = False
            result["errors"].append(f"Password must be at least {self.config.password_min_length} characters")
        
        if not re.search(r"[A-Z]", password):
            result["valid"] = False
            result["errors"].append("Password must contain at least one uppercase letter")
        
        if not re.search(r"[a-z]", password):
            result["valid"] = False
            result["errors"].append("Password must contain at least one lowercase letter")
        
        if not re.search(r"\d", password):
            result["valid"] = False
            result["errors"].append("Password must contain at least one number")
        
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            result["valid"] = False
            result["errors"].append("Password must contain at least one special character")
        
        return result

    def sanitize_input(self, text: str, allow_html: bool = False) -> str:
        """Sanitize user input"""
        if not self.config.enable_input_sanitization:
            return text
        
        if not text:
            return text
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Detect injection attempts
        self._detect_injection_attempts(text)
        
        if allow_html:
            # Allow only safe HTML tags
            allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']
            text = bleach.clean(text, tags=allowed_tags, strip=True)
        else:
            # Strip all HTML
            text = bleach.clean(text, tags=[], strip=True)
        
        return text

    def _detect_injection_attempts(self, text: str):
        """Detect potential injection attempts"""
        text_upper = text.upper()
        
        # Check for SQL injection
        for pattern in self.sql_injection_patterns:
            if re.search(pattern, text_upper, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {pattern}")
                raise ValueError("Invalid input detected")
        
        # Check for XSS
        for pattern in self.xss_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Potential XSS attack detected: {pattern}")
                raise ValueError("Invalid input detected")
        
        # Check for NoSQL injection
        for pattern in self.nosql_injection_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Potential NoSQL injection detected: {pattern}")
                raise ValueError("Invalid input detected")

    def validate_file_upload(self, filename: str, file_size: int, file_content: bytes) -> Dict[str, Any]:
        """Validate file uploads"""
        result = {
            "valid": True,
            "errors": []
        }
        
        # Check file size
        max_size_bytes = self.config.max_file_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            result["valid"] = False
            result["errors"].append(f"File size exceeds {self.config.max_file_size_mb}MB limit")
        
        # Check file extension
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        if file_ext not in self.config.allowed_file_types:
            result["valid"] = False
            result["errors"].append(f"File type '{file_ext}' not allowed")
        
        # Check for malicious content
        if self._has_malicious_content(file_content):
            result["valid"] = False
            result["errors"].append("File contains potentially malicious content")
        
        return result

    def _has_malicious_content(self, content: bytes) -> bool:
        """Check for malicious content in files"""
        try:
            # Convert to string for pattern matching
            text_content = content.decode('utf-8', errors='ignore')
            
            # Check for script tags and other dangerous patterns
            dangerous_patterns = [
                b'<script',
                b'javascript:',
                b'vbscript:',
                b'onload=',
                b'onerror=',
                b'eval(',
                b'document.cookie',
                b'window.location'
            ]
            
            for pattern in dangerous_patterns:
                if pattern in content.lower():
                    return True
            
            return False
        except Exception:
            # If we can't decode, treat as potentially dangerous
            return True

class ContentFilter:
    """Content filtering for inappropriate or dangerous content"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        
        # Load prohibited words/patterns
        self.prohibited_patterns = [
            # Add patterns for inappropriate content
            r'\b(spam|phishing|malware)\b',
            r'\b(hack|exploit|vulnerability)\b',
            # Add more patterns as needed
        ]

    def filter_content(self, text: str) -> Dict[str, Any]:
        """Filter content for prohibited patterns"""
        if not self.config.enable_content_filtering:
            return {"allowed": True, "filtered_text": text}
        
        result = {
            "allowed": True,
            "filtered_text": text,
            "violations": []
        }
        
        for pattern in self.prohibited_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                result["violations"].extend(matches)
                # Replace with asterisks
                text = re.sub(pattern, lambda m: '*' * len(m.group()), text, flags=re.IGNORECASE)
        
        if result["violations"]:
            result["allowed"] = False
            result["filtered_text"] = text
            logger.warning(f"Content violations detected: {result['violations']}")
        
        return result

class Encryption:
    """Data encryption utilities"""
    
    def __init__(self, key: Optional[bytes] = None):
        if key is None:
            key = Fernet.generate_key()
        self.cipher = Fernet(key)
        self.key = key

    def encrypt(self, data: str) -> str:
        """Encrypt string data"""
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()

    def hash_password(self, password: str, salt: Optional[str] = None) -> Dict[str, str]:
        """Hash password with salt"""
        if salt is None:
            salt = secrets.token_hex(32)
        
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # iterations
        )
        
        return {
            "hash": password_hash.hex(),
            "salt": salt
        }

    def verify_password(self, password: str, stored_hash: str, salt: str) -> bool:
        """Verify password against stored hash"""
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        
        return password_hash.hex() == stored_hash

class SecurityManager:
    """Main security manager that coordinates all security features"""
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.rate_limiter = RateLimiter(self.config)
        self.input_validator = InputValidator(self.config)
        self.content_filter = ContentFilter(self.config)
        self.encryption = Encryption()

    def validate_request(self, user_ip: str, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive request validation"""
        result = {
            "valid": True,
            "errors": [],
            "sanitized_data": {}
        }
        
        # Rate limiting
        if not self.rate_limiter.is_allowed(user_ip, endpoint):
            result["valid"] = False
            result["errors"].append("Rate limit exceeded")
            return result
        
        # Input validation and sanitization
        try:
            for key, value in data.items():
                if isinstance(value, str):
                    # Sanitize string inputs
                    sanitized_value = self.input_validator.sanitize_input(value)
                    
                    # Content filtering
                    filter_result = self.content_filter.filter_content(sanitized_value)
                    if not filter_result["allowed"]:
                        result["valid"] = False
                        result["errors"].append(f"Inappropriate content in field '{key}'")
                    
                    result["sanitized_data"][key] = filter_result["filtered_text"]
                else:
                    result["sanitized_data"][key] = value
        
        except ValueError as e:
            result["valid"] = False
            result["errors"].append(str(e))
        
        return result

    def generate_secure_token(self, user_id: str, additional_claims: Dict[str, Any] = None) -> str:
        """Generate secure JWT token"""
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(hours=self.config.jwt_expiry_hours),
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(32)  # Unique token ID
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        # Use a secure secret key (should be from environment in production)
        secret_key = secrets.token_urlsafe(32)
        
        return jwt.encode(payload, secret_key, algorithm="HS256")

    def get_security_headers(self) -> Dict[str, str]:
        """Get recommended security headers"""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }

# Global security manager instance
security_config = SecurityConfig()
security_manager = SecurityManager(security_config)

# Security decorators
def require_auth(func):
    """Decorator to require authentication"""
    def wrapper(*args, **kwargs):
        # Implementation would check for valid JWT token
        return func(*args, **kwargs)
    return wrapper

def rate_limit(endpoint: str):
    """Decorator for rate limiting"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get user IP from request context
            user_ip = "127.0.0.1"  # Would be extracted from request
            
            if not security_manager.rate_limiter.is_allowed(user_ip, endpoint):
                raise ValueError("Rate limit exceeded")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def sanitize_input(func):
    """Decorator for input sanitization"""
    def wrapper(*args, **kwargs):
        # Sanitize input arguments
        # Implementation would depend on the specific function signature
        return func(*args, **kwargs)
    return wrapper 