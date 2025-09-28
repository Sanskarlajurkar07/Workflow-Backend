import logging
import httpx
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult
import urllib.parse
import xml.etree.ElementTree as ET

logger = logging.getLogger("workflow_api")

# Helper function to parse Arxiv's Atom feed response
def parse_arxiv_atom(xml_content: str) -> List[Dict[str, Any]]:
    """Parse Arxiv's Atom feed response into structured data"""
    root = ET.fromstring(xml_content)
    
    # Define namespace mappings
    namespaces = {
        'atom': 'http://www.w3.org/2005/Atom',
        'arxiv': 'http://arxiv.org/schemas/atom'
    }
    
    results = []
    
    # Extract entries
    for entry in root.findall('atom:entry', namespaces):
        paper = {}
        
        # Extract basic metadata
        paper['title'] = entry.find('atom:title', namespaces).text.strip()
        paper['summary'] = entry.find('atom:summary', namespaces).text.strip()
        paper['published'] = entry.find('atom:published', namespaces).text
        paper['updated'] = entry.find('atom:updated', namespaces).text
        
        # Extract authors
        authors = []
        for author in entry.findall('atom:author', namespaces):
            author_name = author.find('atom:name', namespaces).text
            authors.append(author_name)
        paper['authors'] = authors
        
        # Extract links
        links = {}
        for link in entry.findall('atom:link', namespaces):
            link_rel = link.get('rel', '')
            link_href = link.get('href', '')
            link_type = link.get('type', '')
            
            if link_rel == 'alternate' and link_type == 'text/html':
                links['html'] = link_href
            elif link_rel == 'self':
                links['self'] = link_href
            elif link_type == 'application/pdf':
                links['pdf'] = link_href
                
        paper['links'] = links
        
        # Extract Arxiv specific metadata
        arxiv_id = entry.find('atom:id', namespaces).text
        paper['arxiv_id'] = arxiv_id.split('/')[-1]
        
        # Extract categories/subjects
        categories = []
        for category in entry.findall('atom:category', namespaces):
            cat_term = category.get('term', '')
            if cat_term:
                categories.append(cat_term)
        paper['categories'] = categories
        
        # Extract DOI if available
        arxiv_doi = entry.find('arxiv:doi', namespaces)
        if arxiv_doi is not None:
            paper['doi'] = arxiv_doi.text
        
        # Extract journal reference if available
        arxiv_journal_ref = entry.find('arxiv:journal_ref', namespaces)
        if arxiv_journal_ref is not None:
            paper['journal_ref'] = arxiv_journal_ref.text
            
        results.append(paper)
        
    return results

async def search_arxiv(
    query: str, 
    max_results: int = 10, 
    sort_by: str = 'relevance', 
    sort_order: str = 'descending',
    categories: List[str] = None
) -> List[Dict[str, Any]]:
    """Search Arxiv papers by query"""
    
    # Base URL for Arxiv API
    base_url = "http://export.arxiv.org/api/query"
    
    # Prepare search parameters
    search_query = query
    
    # Add category filters if provided
    if categories and len(categories) > 0:
        category_filter = " OR ".join([f"cat:{cat}" for cat in categories])
        if query:
            search_query = f"({search_query}) AND ({category_filter})"
        else:
            search_query = category_filter
    
    # Prepare parameters
    params = {
        "search_query": search_query,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order
    }
    
    # Make the request
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(base_url, params=params)
        
        if response.status_code != 200:
            logger.error(f"Arxiv API error: {response.status_code} - {response.text}")
            return None
            
        # Parse the Atom feed response
        return parse_arxiv_atom(response.text)

async def get_arxiv_by_id(paper_id: str) -> Dict[str, Any]:
    """Get a specific Arxiv paper by ID"""
    
    # Base URL for Arxiv API
    base_url = "http://export.arxiv.org/api/query"
    
    # Remove version information if present
    if 'v' in paper_id:
        paper_id = paper_id.split('v')[0]
    
    # Prepare parameters
    params = {
        "id_list": paper_id
    }
    
    # Make the request
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(base_url, params=params)
        
        if response.status_code != 200:
            logger.error(f"Arxiv API error: {response.status_code} - {response.text}")
            return None
            
        # Parse the Atom feed response
        results = parse_arxiv_atom(response.text)
        return results[0] if results else None

async def handle_arxiv_loader_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for arxiv_loader node type to fetch Arxiv papers"""
    logger.info(f"Executing Arxiv Loader node {node_id}")
    
    # Extract parameters
    mode = node_data.get("params", {}).get("mode", "search")
    query = node_data.get("params", {}).get("query", "")
    paper_id = node_data.get("params", {}).get("paperId", "")
    max_results = node_data.get("params", {}).get("maxResults", 10)
    sort_by = node_data.get("params", {}).get("sortBy", "relevance")
    sort_order = node_data.get("params", {}).get("sortOrder", "descending")
    categories = node_data.get("params", {}).get("categories", [])
    node_name = node_data.get("params", {}).get("nodeName", f"arxiv_{node_id[:4]}")
    
    # Process variable replacements
    for key, value in inputs.items():
        query = query.replace(f"{{{{{key}}}}}", str(value))
        paper_id = paper_id.replace(f"{{{{{key}}}}}", str(value))
    
    try:
        result = None
        
        # Different modes of operation
        if mode == "search":
            result = await search_arxiv(query, max_results, sort_by, sort_order, categories)
            
        elif mode == "paper":
            if not paper_id:
                return NodeResult(
                    output={"error": "Paper ID is required for 'paper' mode"},
                    type="object",
                    execution_time=datetime.now().timestamp() - start_time,
                    status="error",
                    error="Paper ID is required for 'paper' mode",
                    node_id=node_id,
                    node_name=node_name
                )
                
            result = await get_arxiv_by_id(paper_id)
            
        else:
            return NodeResult(
                output={"error": f"Invalid mode '{mode}'"},
                type="object",
                execution_time=datetime.now().timestamp() - start_time,
                status="error",
                error=f"Invalid mode '{mode}'",
                node_id=node_id,
                node_name=node_name
            )
        
        if not result:
            return NodeResult(
                output={"error": "No data found or API error"},
                type="object",
                execution_time=datetime.now().timestamp() - start_time,
                status="error",
                error="No data found or API error",
                node_id=node_id,
                node_name=node_name
            )
        
        # Store result in workflow data for variable access
        workflow_data[node_name] = result
        
        return NodeResult(
            output=result,
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="success",
            node_id=node_id,
            node_name=node_name
        )
        
    except Exception as e:
        logger.error(f"Error in Arxiv Loader node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_name
        ) 