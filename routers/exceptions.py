from fastapi import HTTPException, status
from typing import Any, Dict, Optional, Union
import logging

logger = logging.getLogger("workflow_api")

class WorkflowException(HTTPException):
    """Base exception for all workflow-related errors."""
    def __init__(
        self, 
        status_code: int, 
        detail: str, 
        error_code: str = None,
        data: Dict[str, Any] = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
        self.data = data or {}
        logger.error(f"WorkflowException: {error_code} - {detail}")

class AuthenticationError(WorkflowException):
    """Raised when a user is not authenticated or credentials are invalid."""
    def __init__(
        self, 
        detail: str = "Authentication failed", 
        error_code: str = "AUTH_ERROR"
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code=error_code
        )

class AuthorizationError(WorkflowException):
    """Raised when a user doesn't have permission to access a resource."""
    def __init__(
        self, 
        detail: str = "You don't have permission to access this resource", 
        error_code: str = "FORBIDDEN"
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code=error_code
        )

class ResourceNotFoundError(WorkflowException):
    """Raised when a requested resource doesn't exist."""
    def __init__(
        self, 
        resource_type: str,
        resource_id: Union[str, int],
        detail: str = None, 
        error_code: str = "NOT_FOUND"
    ):
        if detail is None:
            detail = f"{resource_type} with ID {resource_id} not found"
        
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            error_code=error_code,
            data={"resource_type": resource_type, "resource_id": resource_id}
        )

class ValidationError(WorkflowException):
    """Raised when input validation fails."""
    def __init__(
        self, 
        detail: str = "Validation error", 
        errors: Dict[str, Any] = None,
        error_code: str = "VALIDATION_ERROR"
    ):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code=error_code,
            data={"errors": errors or {}}
        )

class NodeExecutionError(WorkflowException):
    """Raised when a workflow node fails to execute."""
    def __init__(
        self, 
        node_id: str,
        error_message: str,
        node_type: Optional[str] = None,
        workflow_id: Optional[str] = None,
        error_code: str = "NODE_EXECUTION_ERROR"
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Node execution failed: {error_message}",
            error_code=error_code,
            data={
                "node_id": node_id,
                "node_type": node_type,
                "workflow_id": workflow_id,
                "error_message": error_message
            }
        )

class ExternalServiceError(WorkflowException):
    """Raised when an external service (AI model, API, etc.) returns an error."""
    def __init__(
        self, 
        service_name: str,
        error_message: str,
        status_code: Optional[int] = None,
        error_code: str = "EXTERNAL_SERVICE_ERROR"
    ):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{service_name} service error: {error_message}",
            error_code=error_code,
            data={
                "service_name": service_name,
                "service_status_code": status_code,
                "error_message": error_message
            }
        )

class RateLimitExceededError(WorkflowException):
    """Raised when a user exceeds rate limits."""
    def __init__(
        self, 
        limit_type: str,
        reset_time: Optional[int] = None,
        error_code: str = "RATE_LIMIT_EXCEEDED"
    ):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {limit_type}",
            error_code=error_code,
            data={
                "limit_type": limit_type,
                "reset_time": reset_time
            }
        )

class DatabaseError(WorkflowException):
    """Raised when a database operation fails."""
    def __init__(
        self, 
        operation: str,
        error_message: str,
        error_code: str = "DATABASE_ERROR"
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database {operation} failed: {error_message}",
            error_code=error_code,
            data={
                "operation": operation,
                "error_message": error_message
            }
        ) 