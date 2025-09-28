import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult
from bs4 import BeautifulSoup
import json
import re
import urllib.parse

logger = logging.getLogger("workflow_api")

# Helper function to clean text from HTML
def clean_text(text: str) -> str:
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing whitespace
    return text.strip()

# Helper function to extract main content from HTML
def extract_main_content(soup: BeautifulSoup) -> str:
    """Extract main content from HTML using heuristics"""
    # Try common content containers
    content_tags = [
        soup.find('main'),
        soup.find('article'),
        soup.find(id=re.compile(r'content|main|article', re.I)),
        soup.find(class_=re.compile(r'content|main|article', re.I)),
    ]
    
    for tag in content_tags:
        if tag:
            # Remove script, style, and nav elements
            for element in tag.select('script, style, nav, header, footer, aside'):
                element.decompose()
            return clean_text(tag.get_text())
    
    # Fallback: extract from body
    body = soup.find('body')
    if body:
        # Remove script, style, and nav elements
        for element in body.select('script, style, nav, header, footer, aside'):
            element.decompose()
        return clean_text(body.get_text())
    
    # Last resort: get all text
    return clean_text(soup.get_text())

# Helper function to extract metadata from HTML
def extract_metadata(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    """Extract metadata from HTML document"""
    metadata = {
        "url": url,
        "title": "",
        "description": "",
        "keywords": [],
        "author": "",
        "site_name": "",
        "image": "",
        "favicon": "",
    }
    
    # Extract title
    title_tag = soup.find('title')
    if title_tag:
        metadata["title"] = clean_text(title_tag.string) if title_tag.string else ""
    
    # Extract meta tags
    for meta in soup.find_all('meta'):
        name = meta.get('name', '').lower()
        property = meta.get('property', '').lower()
        content = meta.get('content', '')
        
        if name == 'description' or property == 'og:description':
            metadata["description"] = content
        elif name == 'keywords':
            metadata["keywords"] = [k.strip() for k in content.split(',')]
        elif name == 'author' or property == 'og:author':
            metadata["author"] = content
        elif property == 'og:site_name':
            metadata["site_name"] = content
        elif property == 'og:image' or name == 'twitter:image':
            if content and not metadata["image"]:
                metadata["image"] = content
    
    # Extract favicon
    favicon_link = soup.find('link', rel='icon') or soup.find('link', rel='shortcut icon')
    if favicon_link and favicon_link.get('href'):
        favicon_href = favicon_link['href']
        # Convert relative URL to absolute
        if not favicon_href.startswith(('http://', 'https://')):
            parsed_url = urllib.parse.urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            if favicon_href.startswith('/'):
                metadata["favicon"] = f"{base_url}{favicon_href}"
            else:
                path = '/'.join(parsed_url.path.split('/')[:-1])
                metadata["favicon"] = f"{base_url}{path}/{favicon_href}"
        else:
            metadata["favicon"] = favicon_href
            
    return metadata

# Helper function to extract links from HTML
def extract_links(soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
    """Extract links from HTML document"""
    links = []
    
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        text = clean_text(a_tag.get_text())
        
        # Skip empty links or anchors
        if not href or href.startswith('#'):
            continue
            
        # Convert relative URLs to absolute
        if not href.startswith(('http://', 'https://')):
            parsed_url = urllib.parse.urlparse(base_url)
            base = f"{parsed_url.scheme}://{parsed_url.netloc}"
            if href.startswith('/'):
                href = f"{base}{href}"
            else:
                path = '/'.join(parsed_url.path.split('/')[:-1])
                href = f"{base}{path}/{href}"
        
        links.append({
            "url": href,
            "text": text
        })
        
    return links

async def fetch_url_content(
    url: str,
    extract_mode: str = "full",
    follow_redirects: bool = True,
    timeout: int = 30,
    headers: Dict[str, str] = None
) -> Dict[str, Any]:
    """Fetch and extract content from a URL"""
    
    # Default headers to mimic a browser
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    # Merge with custom headers if provided
    if headers:
        default_headers.update(headers)
    
    try:
        # Make the request
        async with httpx.AsyncClient(follow_redirects=follow_redirects, timeout=timeout) as client:
            response = await client.get(url, headers=default_headers)
            
            # Check if successful
            if response.status_code != 200:
                return {
                    "error": f"HTTP error: {response.status_code}",
                    "success": False,
                    "url": url
                }
                
            # Check content type
            content_type = response.headers.get("Content-Type", "").lower()
            
            # Handle JSON content
            if "application/json" in content_type:
                try:
                    json_data = response.json()
                    return {
                        "content_type": "json",
                        "success": True,
                        "url": str(response.url),
                        "data": json_data,
                        "status_code": response.status_code,
                        "headers": dict(response.headers)
                    }
                except json.JSONDecodeError:
                    return {
                        "error": "Invalid JSON content",
                        "success": False,
                        "url": str(response.url)
                    }
            
            # Handle HTML content
            elif "text/html" in content_type:
                # Parse HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract based on mode
                result = {
                    "content_type": "html",
                    "success": True,
                    "url": str(response.url),
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "metadata": extract_metadata(soup, str(response.url))
                }
                
                if extract_mode == "full" or extract_mode == "text":
                    result["text"] = extract_main_content(soup)
                    
                if extract_mode == "full" or extract_mode == "links":
                    result["links"] = extract_links(soup, str(response.url))
                
                return result
                
            # Handle other text content
            elif any(text_type in content_type for text_type in ["text/plain", "text/css", "text/javascript"]):
                return {
                    "content_type": "text",
                    "success": True,
                    "url": str(response.url),
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "text": response.text
                }
                
            # Handle binary content
            else:
                return {
                    "content_type": content_type,
                    "success": True,
                    "url": str(response.url),
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "content_length": len(response.content),
                    "is_binary": True
                }
    
    except httpx.RequestError as e:
        return {
            "error": f"Request error: {str(e)}",
            "success": False,
            "url": url
        }
    except Exception as e:
        return {
            "error": f"Error: {str(e)}",
            "success": False,
            "url": url
        }

async def handle_url_loader_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for url_loader node type to fetch and process web content"""
    logger.info(f"Executing URL Loader node {node_id}")
    
    # Extract parameters
    url = node_data.get("params", {}).get("url", "")
    extract_mode = node_data.get("params", {}).get("extractMode", "full")
    follow_redirects = node_data.get("params", {}).get("followRedirects", True)
    timeout = node_data.get("params", {}).get("timeout", 30)
    headers_list = node_data.get("params", {}).get("headers", [])
    node_name = node_data.get("params", {}).get("nodeName", f"url_{node_id[:4]}")
    
    # Process variable replacements in URL
    for key, value in inputs.items():
        url = url.replace(f"{{{{{key}}}}}", str(value))
    
    # Validate URL
    if not url:
        return NodeResult(
            output={"error": "URL is required"},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error="URL is required",
            node_id=node_id,
            node_name=node_name
        )
        
    # Add protocol if missing
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    
    # Convert headers from array of objects to dictionary
    headers = {}
    for header in headers_list:
        if header.get("key") and header.get("value"):
            # Replace variables in header values
            header_value = header.get("value", "")
            for key, value in inputs.items():
                header_value = header_value.replace(f"{{{{{key}}}}}", str(value))
            headers[header.get("key")] = header_value
    
    try:
        # Fetch URL content
        result = await fetch_url_content(
            url=url,
            extract_mode=extract_mode,
            follow_redirects=follow_redirects,
            timeout=timeout,
            headers=headers
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
        logger.error(f"Error in URL Loader node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_name
        ) 