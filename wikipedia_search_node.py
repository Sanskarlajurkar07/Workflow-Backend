import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult
from bs4 import BeautifulSoup
import re
import urllib.parse

logger = logging.getLogger("workflow_api")

# Helper function to clean HTML content
def clean_html(html_content: str) -> str:
    """Clean HTML content to get plain text"""
    if not html_content:
        return ""
    
    # Use BeautifulSoup to parse and clean HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script, style, and unwanted elements
    for element in soup(["script", "style", "sup", "span.mw-editsection"]):
        element.extract()
    
    # Get text
    text = soup.get_text()
    
    # Remove extra whitespace and normalize
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)
    
    return text

async def search_wikipedia(
    query: str,
    language: str = "en",
    limit: int = 10,
    format_type: str = "json"
) -> Dict[str, Any]:
    """Search Wikipedia for query"""
    
    # Base URL for Wikipedia API
    base_url = f"https://{language}.wikipedia.org/w/api.php"
    
    # Prepare parameters for search
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": format_type
    }
    
    try:
        # Make the request
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(base_url, params=params)
            
            # Check if successful
            if response.status_code != 200:
                return {
                    "error": f"HTTP error: {response.status_code}",
                    "success": False,
                    "query": query
                }
            
            # Parse the response
            data = response.json()
            
            # Extract search results
            results = []
            for item in data.get("query", {}).get("search", []):
                result = {
                    "title": item.get("title", ""),
                    "page_id": item.get("pageid", 0),
                    "snippet": clean_html(item.get("snippet", "")),
                    "timestamp": item.get("timestamp", ""),
                    "url": f"https://{language}.wikipedia.org/wiki/{urllib.parse.quote(item.get('title', '').replace(' ', '_'))}"
                }
                results.append(result)
            
            return {
                "success": True,
                "query": query,
                "language": language,
                "results": results,
                "total_hits": data.get("query", {}).get("searchinfo", {}).get("totalhits", 0)
            }
            
    except Exception as e:
        logger.error(f"Error searching Wikipedia: {str(e)}", exc_info=True)
        return {
            "error": f"Error: {str(e)}",
            "success": False,
            "query": query
        }

async def get_wikipedia_article(
    title: str,
    language: str = "en",
    extract_format: str = "plain",
    extract_intro_only: bool = False
) -> Dict[str, Any]:
    """Get content of a specific Wikipedia article"""
    
    # Base URL for Wikipedia API
    base_url = f"https://{language}.wikipedia.org/w/api.php"
    
    # Prepare parameters
    params = {
        "action": "query",
        "prop": "extracts|info|pageimages",
        "exlimit": 1,
        "titles": title,
        "inprop": "url",
        "pithumbsize": 500,  # Thumbnail size
        "format": "json"
    }
    
    # Add extract format (HTML or plain text)
    if extract_format == "html":
        params["explaintext"] = 0
    else:
        params["explaintext"] = 1
    
    # Limit to introduction if requested
    if extract_intro_only:
        params["exintro"] = 1
    
    try:
        # Make the request
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(base_url, params=params)
            
            # Check if successful
            if response.status_code != 200:
                return {
                    "error": f"HTTP error: {response.status_code}",
                    "success": False,
                    "title": title
                }
            
            # Parse the response
            data = response.json()
            
            # Extract page data (first page in the response)
            pages = data.get("query", {}).get("pages", {})
            if not pages:
                return {
                    "error": "No page found",
                    "success": False,
                    "title": title
                }
            
            # Get the first page (there should be only one)
            page_id, page_data = next(iter(pages.items()))
            
            # Check if it's a missing page
            if int(page_id) < 0:
                return {
                    "error": "Page not found",
                    "success": False,
                    "title": title
                }
            
            # Extract content
            content = page_data.get("extract", "")
            if extract_format == "plain":
                # Content is already plain text
                pass
            else:
                # Clean HTML content
                content = clean_html(content)
            
            # Construct result
            result = {
                "success": True,
                "title": page_data.get("title", ""),
                "page_id": int(page_id),
                "content": content,
                "url": page_data.get("fullurl", f"https://{language}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"),
                "last_modified": page_data.get("touched", "")
            }
            
            # Add thumbnail if available
            if "thumbnail" in page_data:
                result["thumbnail"] = page_data["thumbnail"].get("source", "")
            
            return result
            
    except Exception as e:
        logger.error(f"Error getting Wikipedia article: {str(e)}", exc_info=True)
        return {
            "error": f"Error: {str(e)}",
            "success": False,
            "title": title
        }

async def handle_wikipedia_search_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for wikipedia_search node type to search and fetch Wikipedia content"""
    logger.info(f"Executing Wikipedia Search node {node_id}")
    
    # Extract parameters
    mode = node_data.get("params", {}).get("mode", "search")
    query = node_data.get("params", {}).get("query", "")
    article_title = node_data.get("params", {}).get("articleTitle", "")
    language = node_data.get("params", {}).get("language", "en")
    limit = node_data.get("params", {}).get("limit", 5)
    extract_format = node_data.get("params", {}).get("extractFormat", "plain")
    extract_intro_only = node_data.get("params", {}).get("extractIntroOnly", False)
    node_name = node_data.get("params", {}).get("nodeName", f"wiki_{node_id[:4]}")
    
    # Process variable replacements
    for key, value in inputs.items():
        query = query.replace(f"{{{{{key}}}}}", str(value))
        article_title = article_title.replace(f"{{{{{key}}}}}", str(value))
    
    try:
        result = None
        
        # Different modes of operation
        if mode == "search" and query:
            result = await search_wikipedia(
                query=query,
                language=language,
                limit=limit
            )
            
        elif mode == "article" and article_title:
            result = await get_wikipedia_article(
                title=article_title,
                language=language,
                extract_format=extract_format,
                extract_intro_only=extract_intro_only
            )
            
        else:
            return NodeResult(
                output={"error": f"Invalid mode or missing required parameters for mode '{mode}'"},
                type="object",
                execution_time=datetime.now().timestamp() - start_time,
                status="error",
                error=f"Invalid mode or missing required parameters for mode '{mode}'",
                node_id=node_id,
                node_name=node_name
            )
        
        # Check for errors
        if not result.get("success", False):
            return NodeResult(
                output=result,
                type="object",
                execution_time=datetime.now().timestamp() - start_time,
                status="error",
                error=result.get("error", "Unknown error"),
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
        logger.error(f"Error in Wikipedia Search node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_name
        ) 