import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult
import httpx
import json
import os
import time

# Import handlers from dedicated files
from notification_node import handle_notification_node
from crm_enricher_node import handle_crm_enricher_node

logger = logging.getLogger("workflow_api")

# Export the imported handlers directly
__all__ = [
    "handle_gmail_trigger_node",
    "handle_outlook_trigger_node",
    "handle_notification_node",
    "handle_crm_enricher_node"
]

# Still implement the remaining handlers directly in this file
async def handle_gmail_trigger_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for gmail_trigger node type
    
    This node triggers workflows based on Gmail events.
    """
    # This would be implemented based on Gmail API integration
    # Currently outside the scope of this file
    pass

async def handle_outlook_trigger_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for outlook_trigger node type
    
    This node triggers workflows based on Outlook events.
    """
    # This would be implemented based on Microsoft Graph API integration
    # Currently outside the scope of this file
    pass

async def handle_notification_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for notification node type"""
    logger.info(f"Executing Notification node {node_id}")
    
    # Extract parameters
    notification_type = node_data.get("params", {}).get("notificationType", "email")
    recipients = node_data.get("params", {}).get("recipients", [])
    subject = node_data.get("params", {}).get("subject", "Workflow Notification")
    message = node_data.get("params", {}).get("message", "")
    priority = node_data.get("params", {}).get("priority", "normal")
    
    # Get input content if provided
    input_content = inputs.get("input", "")
    
    # Process variables in message
    processed_message = message
    if "{{input}}" in processed_message:
        processed_message = processed_message.replace("{{input}}", str(input_content))
    
    # For variable references like {{workflow.variables.x}}
    for key, value in workflow_data.items():
        if isinstance(value, (str, int, float, bool)):
            var_placeholder = f"{{{{workflow.variables.{key}}}}}"
            if var_placeholder in processed_message:
                processed_message = processed_message.replace(var_placeholder, str(value))
    
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
    var_name = node_data.get("params", {}).get("variableName", f"notif_{node_id[:4]}")
    workflow_data[var_name] = notification_result
    
    return NodeResult(
        output=notification_result,
        type="object",
        execution_time=datetime.now().timestamp() - start_time,
        status="success", 
        node_id=node_id,
        node_name=node_data.get("params", {}).get("nodeName", "Notification")
    )

async def handle_crm_enricher_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for crm_enricher node type"""
    logger.info(f"Executing CRM Enricher node {node_id}")
    
    # Extract parameters
    crm_type = node_data.get("params", {}).get("crmType", "generic")
    enrichment_type = node_data.get("params", {}).get("enrichmentType", "contact")
    data_sources = node_data.get("params", {}).get("dataSources", ["internal"])
    
    # Get input data
    input_data = inputs.get("input", {})
    
    # Extract key identifiers based on input type
    identifier = None
    if isinstance(input_data, dict):
        # Try to find an identifier in the input
        identifier = input_data.get("email") or input_data.get("domain") or input_data.get("name")
    elif isinstance(input_data, str):
        # Use the string as identifier
        identifier = input_data
    
    if not identifier:
        return NodeResult(
            output={"error": "No valid identifier found in input"},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error="No valid identifier found in input",
            node_id=node_id,
            node_name=node_data.get("params", {}).get("nodeName", "CRM Enricher")
        )
    
    # For testing/simulation purposes
    # In a real implementation, this would connect to CRM and data enrichment APIs
    enriched_data = {}
    
    if enrichment_type == "contact":
        enriched_data = {
            "contact": {
                "email": identifier if "@" in identifier else f"{identifier.lower().replace(' ', '.')}@example.com",
                "name": identifier if not "@" in identifier else identifier.split("@")[0].replace(".", " ").title(),
                "phone": "+1 (555) 123-4567",
                "title": "Product Manager",
                "linkedin": f"https://linkedin.com/in/{identifier.lower().replace(' ', '-').replace('@', '-')}",
                "twitter": f"@{identifier.lower().split('@')[0].replace('.', '_')}",
                "company": "Acme Corporation",
                "last_contacted": "2023-05-15T10:30:00Z"
            }
        }
    elif enrichment_type == "company":
        enriched_data = {
            "company": {
                "name": identifier.title() if not "." in identifier else identifier.split(".")[0].title(),
                "domain": identifier if "." in identifier else f"{identifier.lower().replace(' ', '')}.com",
                "industry": "Technology",
                "size": "51-200 employees",
                "founded": "2010",
                "location": "San Francisco, CA",
                "description": f"{identifier.title()} provides innovative solutions for enterprise customers.",
                "technologies": ["React", "Node.js", "AWS"],
                "funding": "$5.2M Series A"
            }
        }
    
    # Add source information
    enriched_data["sources"] = data_sources
    enriched_data["timestamp"] = datetime.now().isoformat()
    enriched_data["crm_type"] = crm_type
    
    # Store result in workflow data for variable access
    var_name = node_data.get("params", {}).get("variableName", f"crm_{node_id[:4]}")
    workflow_data[var_name] = enriched_data
    
    return NodeResult(
        output=enriched_data,
        type="object",
        execution_time=datetime.now().timestamp() - start_time,
        status="success",
        node_id=node_id,
        node_name=node_data.get("params", {}).get("nodeName", "CRM Enricher")
    )

# Helper function to simulate async sleep without importing asyncio
async def asyncio_sleep(seconds):
    """Simple sleep function to avoid importing asyncio"""
    start = time.time()
    while time.time() - start < seconds:
        await httpx.AsyncClient().aclose()  # Yield control 