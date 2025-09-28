import httpx
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

logger = logging.getLogger("workflow_api")

class HubSpotNode:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.hubapi.com"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    async def execute(self, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HubSpot node based on action type"""
        try:
            action = node_data.get('action')
            if not action:
                raise ValueError("No action specified")

            logger.info(f"Executing HubSpot action: {action}")

            if action.startswith('fetch-'):
                return await self._handle_fetch_action(action, node_data)
            elif action.startswith('create-'):
                return await self._handle_create_action(action, node_data)
            else:
                raise ValueError(f"Unsupported action: {action}")

        except Exception as e:
            logger.error(f"Error executing HubSpot node: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "data": None
            }

    async def _handle_fetch_action(self, action: str, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle fetch operations for different HubSpot objects"""
        object_type = action.replace('fetch-', '')
        
        # Map action to HubSpot API endpoints
        endpoint_map = {
            'contacts': '/crm/v3/objects/contacts',
            'companies': '/crm/v3/objects/companies',
            'deals': '/crm/v3/objects/deals',
            'tickets': '/crm/v3/objects/tickets',
            'notes': '/crm/v3/objects/notes',
            'calls': '/crm/v3/objects/calls',
            'tasks': '/crm/v3/objects/tasks',
            'meetings': '/crm/v3/objects/meetings',
            'emails': '/crm/v3/objects/emails'
        }

        endpoint = endpoint_map.get(object_type)
        if not endpoint:
            raise ValueError(f"Unsupported object type: {object_type}")

        # Build query parameters
        params = {}
        
        # Add properties to fetch
        properties = node_data.get('properties', '')
        if properties:
            params['properties'] = properties.split(',') if isinstance(properties, str) else properties

        # Add limit
        limit = node_data.get('limit', 100)
        params['limit'] = min(limit, 1000)  # HubSpot max limit

        # Add filters if provided
        filters = node_data.get('filters')
        if filters:
            try:
                filter_data = json.loads(filters) if isinstance(filters, str) else filters
                # Convert to HubSpot search format if needed
                if isinstance(filter_data, dict):
                    # Simple filter format
                    search_endpoint = endpoint + '/search'
                    return await self._search_objects(search_endpoint, filter_data, params)
            except json.JSONDecodeError:
                logger.warning("Invalid filter JSON, proceeding without filters")

        # Fetch objects without complex filtering
        return await self._fetch_objects(endpoint, params)

    async def _handle_create_action(self, action: str, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle create operations for different HubSpot objects"""
        object_type = action.replace('create-', '')
        
        # Map action to HubSpot API endpoints
        endpoint_map = {
            'contact': '/crm/v3/objects/contacts',
            'company': '/crm/v3/objects/companies',
            'deal': '/crm/v3/objects/deals',
            'ticket': '/crm/v3/objects/tickets',
            'note': '/crm/v3/objects/notes',
            'call': '/crm/v3/objects/calls',
            'task': '/crm/v3/objects/tasks',
            'meeting': '/crm/v3/objects/meetings',
            'email': '/crm/v3/objects/emails'
        }

        endpoint = endpoint_map.get(object_type)
        if not endpoint:
            raise ValueError(f"Unsupported object type: {object_type}")

        # Get object properties
        properties_data = node_data.get('properties', '{}')
        try:
            properties = json.loads(properties_data) if isinstance(properties_data, str) else properties_data
        except json.JSONDecodeError:
            raise ValueError("Invalid properties JSON format")

        # Handle special cases for notes (need association)
        if object_type == 'note':
            return await self._create_note(properties, node_data.get('objectId'))

        # Create the object
        return await self._create_object(endpoint, properties)

    async def _fetch_objects(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch objects from HubSpot API"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "data": data.get('results', []),
                    "total": data.get('total', len(data.get('results', []))),
                    "metadata": {
                        "endpoint": endpoint,
                        "params": params
                    }
                }
            else:
                raise Exception(f"HubSpot API error: {response.status_code} - {response.text}")

    async def _search_objects(self, endpoint: str, filter_data: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Search objects with filters"""
        search_payload = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": filter_data.get("propertyName"),
                            "operator": filter_data.get("operator", "EQ"),
                            "value": filter_data.get("value")
                        }
                    ]
                }
            ],
            "properties": params.get('properties', []),
            "limit": params.get('limit', 100)
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                json=search_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "data": data.get('results', []),
                    "total": data.get('total', len(data.get('results', []))),
                    "metadata": {
                        "endpoint": endpoint,
                        "search_payload": search_payload
                    }
                }
            else:
                raise Exception(f"HubSpot search API error: {response.status_code} - {response.text}")

    async def _create_object(self, endpoint: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Create an object in HubSpot"""
        payload = {
            "properties": properties
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 201:
                data = response.json()
                return {
                    "success": True,
                    "data": data,
                    "id": data.get('id'),
                    "metadata": {
                        "endpoint": endpoint,
                        "created_at": datetime.utcnow().isoformat()
                    }
                }
            else:
                raise Exception(f"HubSpot create API error: {response.status_code} - {response.text}")

    async def _create_note(self, properties: Dict[str, Any], associated_object_id: Optional[str]) -> Dict[str, Any]:
        """Create a note with optional object association"""
        endpoint = "/crm/v3/objects/notes"
        
        # Create the note first
        result = await self._create_object(endpoint, properties)
        
        # If association is requested and creation was successful
        if result["success"] and associated_object_id:
            note_id = result["id"]
            try:
                # Create association (this is a simplified version)
                # In practice, you might need to determine the object type and use appropriate association API
                association_result = await self._create_association(note_id, associated_object_id, "note_to_contact")
                result["association"] = association_result
            except Exception as e:
                logger.warning(f"Note created but association failed: {str(e)}")
                result["association_error"] = str(e)
        
        return result

    async def _create_association(self, from_object_id: str, to_object_id: str, association_type: str) -> Dict[str, Any]:
        """Create association between objects"""
        # This is a simplified association method
        # In practice, you'd use the HubSpot associations API v4
        endpoint = f"/crm/v4/objects/notes/{from_object_id}/associations/contacts/{to_object_id}"
        
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                json=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}],
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "association_created": True
                }
            else:
                raise Exception(f"HubSpot association API error: {response.status_code} - {response.text}")

    async def test_connection(self) -> Dict[str, Any]:
        """Test the HubSpot connection"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/crm/v3/owners",
                    headers=self.headers,
                    params={"limit": 1},
                    timeout=10
                )
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "message": "HubSpot connection successful"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Connection failed: {response.status_code}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Connection test failed: {str(e)}"
            }


async def create_hubspot_node(access_token: str) -> HubSpotNode:
    """Factory function to create HubSpot node instance"""
    node = HubSpotNode(access_token)
    
    # Test connection on creation
    connection_test = await node.test_connection()
    if not connection_test["success"]:
        logger.warning(f"HubSpot connection test failed: {connection_test.get('error')}")
    
    return node 