import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult

logger = logging.getLogger("workflow_api")

async def handle_notification_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for notification node type
    
    This node sends notifications through various channels.
    """
    logger.info(f"Executing Notification node {node_id}")
    
    # Extract parameters
    notification_type = node_data.get("params", {}).get("notificationType", "email")
    recipients = node_data.get("params", {}).get("recipients", [])
    subject = node_data.get("params", {}).get("subject", "Workflow Notification")
    message = node_data.get("params", {}).get("message", "")
    priority = node_data.get("params", {}).get("priority", "normal")
    variable_name = node_data.get("params", {}).get("variableName", f"notification_{node_id[:4]}")
    
    # Process variables in parameters
    for key, value in workflow_data.items():
        if isinstance(value, (str, int, float, bool)):
            var_placeholder = f"{{{{workflow.variables.{key}}}}}"
            if var_placeholder in subject:
                subject = subject.replace(var_placeholder, str(value))
            if var_placeholder in message:
                message = message.replace(var_placeholder, str(value))
            
            # Process recipients if they're strings
            if isinstance(recipients, list):
                for i, recipient in enumerate(recipients):
                    if isinstance(recipient, str) and var_placeholder in recipient:
                        recipients[i] = recipient.replace(var_placeholder, str(value))
    
    # Get input content if provided
    input_content = inputs.get("input", "")
    
    # Process variables in message
    processed_message = message
    if "{{input}}" in processed_message:
        processed_message = processed_message.replace("{{input}}", str(input_content))
    
    # For testing/simulation purposes
    # In a real implementation, this would send actual notifications
    notification_result = {
        "sent": True,
        "type": notification_type,
        "recipients": recipients,
        "subject": subject,
        "message": processed_message,
        "timestamp": datetime.now().isoformat()
    }
    
    # Simulate different notification types
    if notification_type == "email":
        notification_result["provider"] = "SMTP"
    elif notification_type == "slack":
        notification_result["provider"] = "Slack API"
        notification_result["channels"] = recipients
    elif notification_type == "webhook":
        notification_result["provider"] = "HTTP Webhook"
        notification_result["endpoint"] = recipients[0] if recipients else "https://example.com/webhook"
    elif notification_type == "sms":
        notification_result["provider"] = "Twilio"
        notification_result["phone_numbers"] = recipients
    
    # Add a short delay to simulate notification sending
    await asyncio_sleep(0.5)
    
    # Store result in workflow data for variable access
    workflow_data[variable_name] = notification_result
    
    return NodeResult(
        output=notification_result,
        type="object",
        execution_time=datetime.now().timestamp() - start_time,
        status="success", 
        node_id=node_id,
        node_name=node_data.get("params", {}).get("nodeName", "Notification")
    )

# Helper function to simulate async sleep without importing asyncio
async def asyncio_sleep(seconds):
    """Simple sleep function to avoid importing asyncio"""
    start = time.time()
    while time.time() - start < seconds:
        await asyncio_sleep_yield()  # Yield control

async def asyncio_sleep_yield():
    """Yield control to allow other async functions to run"""
    # This is a simplified way to yield control in async code
    # In production code, use proper asyncio.sleep
    pass 