import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
import feedparser
from models.workflow import NodeResult
from bs4 import BeautifulSoup
import re

logger = logging.getLogger("workflow_api")

# Helper function to clean HTML content
def clean_html(html_content: str) -> str:
    """Clean HTML content to get plain text"""
    if not html_content:
        return ""
    
    # Use BeautifulSoup to parse and clean HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.extract()
    
    # Get text
    text = soup.get_text()
    
    # Remove extra whitespace
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)
    
    return text

async def fetch_rss_feed(
    url: str,
    max_entries: int = 10,
    include_content: bool = True,
    clean_content: bool = True,
    timeout: int = 30
) -> Dict[str, Any]:
    """Fetch and parse RSS feed content"""
    
    try:
        # Make the request
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            
            # Check if successful
            if response.status_code != 200:
                return {
                    "error": f"HTTP error: {response.status_code}",
                    "success": False,
                    "url": url
                }
            
            # Parse the feed
            feed = feedparser.parse(response.text)
            
            # Check if feed is valid
            if feed.get('bozo', 0) == 1 and not feed.get('entries'):
                return {
                    "error": f"Invalid feed format: {feed.get('bozo_exception', 'Unknown error')}",
                    "success": False,
                    "url": url
                }
            
            # Extract feed metadata
            result = {
                "success": True,
                "url": url,
                "feed_info": {
                    "title": feed.feed.get('title', ''),
                    "subtitle": feed.feed.get('subtitle', ''),
                    "link": feed.feed.get('link', ''),
                    "description": feed.feed.get('description', feed.feed.get('subtitle', '')),
                    "language": feed.feed.get('language', ''),
                    "updated": feed.feed.get('updated', ''),
                    "updated_parsed": feed.feed.get('updated_parsed')
                },
                "entries": []
            }
            
            # Extract entries
            for i, entry in enumerate(feed.entries[:max_entries]):
                item = {
                    "title": entry.get('title', ''),
                    "link": entry.get('link', ''),
                    "id": entry.get('id', entry.get('link', '')),
                    "published": entry.get('published', entry.get('updated', '')),
                    "published_parsed": entry.get('published_parsed', entry.get('updated_parsed')),
                    "authors": [author.get('name', '') for author in entry.get('authors', [])],
                    "tags": [tag.get('term', '') for tag in entry.get('tags', [])]
                }
                
                # Extract and clean content if needed
                if include_content:
                    # Try different content fields
                    content = entry.get('content', [{}])[0].get('value', '') or \
                              entry.get('summary', '') or \
                              entry.get('description', '')
                    
                    if clean_content:
                        item['content'] = clean_html(content)
                    else:
                        item['content'] = content
                
                result["entries"].append(item)
            
            return result
            
    except Exception as e:
        logger.error(f"Error fetching RSS feed: {str(e)}", exc_info=True)
        return {
            "error": f"Error: {str(e)}",
            "success": False,
            "url": url
        }

async def handle_rss_feed_loader_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for rss_feed_loader node type to fetch and process RSS feeds"""
    logger.info(f"Executing RSS Feed Loader node {node_id}")
    
    # Extract parameters
    feed_url = node_data.get("params", {}).get("feedUrl", "")
    max_entries = node_data.get("params", {}).get("maxEntries", 10)
    include_content = node_data.get("params", {}).get("includeContent", True)
    clean_content = node_data.get("params", {}).get("cleanContent", True)
    timeout = node_data.get("params", {}).get("timeout", 30)
    node_name = node_data.get("params", {}).get("nodeName", f"rss_{node_id[:4]}")
    
    # Process variable replacements in URL
    for key, value in inputs.items():
        feed_url = feed_url.replace(f"{{{{{key}}}}}", str(value))
    
    # Validate URL
    if not feed_url:
        return NodeResult(
            output={"error": "Feed URL is required"},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error="Feed URL is required",
            node_id=node_id,
            node_name=node_name
        )
        
    # Add protocol if missing
    if not feed_url.startswith(('http://', 'https://')):
        feed_url = f"https://{feed_url}"
    
    try:
        # Fetch RSS feed
        result = await fetch_rss_feed(
            url=feed_url,
            max_entries=max_entries,
            include_content=include_content,
            clean_content=clean_content,
            timeout=timeout
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
        logger.error(f"Error in RSS Feed Loader node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_name
        ) 