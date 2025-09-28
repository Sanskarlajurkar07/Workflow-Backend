import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult

logger = logging.getLogger("workflow_api")

async def handle_crm_enricher_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for crm_enricher node type
    
    This node enhances contact and company data with additional information.
    """
    logger.info(f"Executing CRM Enricher node {node_id}")
    
    # Extract parameters
    crm_type = node_data.get("params", {}).get("crmType", "generic")
    enrichment_type = node_data.get("params", {}).get("enrichmentType", "contact")
    data_sources = node_data.get("params", {}).get("dataSources", ["internal"])
    variable_name = node_data.get("params", {}).get("variableName", f"crm_data_{node_id[:4]}")
    
    # Process variables in parameters
    for key, value in workflow_data.items():
        if isinstance(value, (str, int, float, bool)):
            var_placeholder = f"{{{{workflow.variables.{key}}}}}"
            
            # Process data_sources if they're strings
            if isinstance(data_sources, list):
                for i, source in enumerate(data_sources):
                    if isinstance(source, str) and var_placeholder in source:
                        data_sources[i] = source.replace(var_placeholder, str(value))
    
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
    workflow_data[variable_name] = enriched_data
    
    return NodeResult(
        output=enriched_data,
        type="object",
        execution_time=datetime.now().timestamp() - start_time,
        status="success",
        node_id=node_id,
        node_name=node_data.get("params", {}).get("nodeName", "CRM Enricher")
    ) 