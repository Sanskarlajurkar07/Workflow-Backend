import logging
import httpx
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from models.workflow import NodeResult
import re

logger = logging.getLogger("workflow_api")

# Helper function to extract video information
async def fetch_video_info(video_id: str, api_key: str):
    """Fetch video information from YouTube API"""
    url = f"https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet,contentDetails,statistics",
        "id": video_id,
        "key": api_key
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            return None
        
        data = response.json()
        if not data.get("items"):
            return None
            
        video = data["items"][0]
        return {
            "id": video_id,
            "title": video["snippet"]["title"],
            "description": video["snippet"]["description"],
            "channel": video["snippet"]["channelTitle"],
            "published_at": video["snippet"]["publishedAt"],
            "thumbnail": video["snippet"]["thumbnails"]["high"]["url"],
            "duration": video["contentDetails"]["duration"],
            "view_count": video["statistics"].get("viewCount", "0"),
            "like_count": video["statistics"].get("likeCount", "0"),
            "comment_count": video["statistics"].get("commentCount", "0")
        }

# Helper function to extract video ID from various YouTube URL formats
def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats"""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"(?:embed\/)([0-9A-Za-z_-]{11})",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# Helper function to extract channel ID from URL
def extract_channel_id(url: str) -> Optional[str]:
    """Extract YouTube channel ID from URL"""
    patterns = [
        r"(?:channel\/)([0-9A-Za-z_-]+)",
        r"(?:c\/)([0-9A-Za-z_-]+)",
        r"(?:user\/)([0-9A-Za-z_-]+)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

async def search_videos(query: str, api_key: str, max_results: int = 10):
    """Search YouTube videos by query"""
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "maxResults": max_results,
        "type": "video",
        "key": api_key
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            return None
        
        data = response.json()
        videos = []
        
        for item in data.get("items", []):
            video = {
                "id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "channel": item["snippet"]["channelTitle"],
                "published_at": item["snippet"]["publishedAt"],
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
            }
            videos.append(video)
            
        return videos

async def get_channel_videos(channel_id: str, api_key: str, max_results: int = 10):
    """Get videos from a specific channel"""
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "channelId": channel_id,
        "maxResults": max_results,
        "type": "video",
        "order": "date",
        "key": api_key
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            return None
        
        data = response.json()
        videos = []
        
        for item in data.get("items", []):
            video = {
                "id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "channel": item["snippet"]["channelTitle"],
                "published_at": item["snippet"]["publishedAt"],
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
            }
            videos.append(video)
            
        return videos

async def handle_youtube_loader_node(
    node_id: str,
    node_data: Dict[str, Any],
    inputs: Dict[str, Any],
    workflow_data: Dict[str, Any],
    start_time: float
) -> NodeResult:
    """Handler for youtube_loader node type to fetch YouTube content"""
    logger.info(f"Executing YouTube Loader node {node_id}")
    
    # Extract parameters
    mode = node_data.get("params", {}).get("mode", "video")
    query = node_data.get("params", {}).get("query", "")
    video_url = node_data.get("params", {}).get("videoUrl", "")
    channel_url = node_data.get("params", {}).get("channelUrl", "")
    api_key = node_data.get("params", {}).get("apiKey", "")
    max_results = node_data.get("params", {}).get("maxResults", 10)
    node_name = node_data.get("params", {}).get("nodeName", f"youtube_{node_id[:4]}")
    
    # Process variable replacements
    for key, value in inputs.items():
        query = query.replace(f"{{{{{key}}}}}", str(value))
        video_url = video_url.replace(f"{{{{{key}}}}}", str(value))
        channel_url = channel_url.replace(f"{{{{{key}}}}}", str(value))
    
    try:
        result = None
        
        # Different modes of operation
        if mode == "video" and video_url:
            video_id = extract_video_id(video_url)
            if not video_id:
                return NodeResult(
                    output={"error": "Invalid YouTube video URL"},
                    type="object",
                    execution_time=datetime.now().timestamp() - start_time,
                    status="error",
                    error="Invalid YouTube video URL",
                    node_id=node_id,
                    node_name=node_name
                )
            
            result = await fetch_video_info(video_id, api_key)
            if result:
                result["url"] = video_url
        
        elif mode == "search" and query:
            result = await search_videos(query, api_key, max_results)
        
        elif mode == "channel" and channel_url:
            channel_id = extract_channel_id(channel_url)
            if not channel_id:
                return NodeResult(
                    output={"error": "Invalid YouTube channel URL"},
                    type="object",
                    execution_time=datetime.now().timestamp() - start_time,
                    status="error",
                    error="Invalid YouTube channel URL",
                    node_id=node_id,
                    node_name=node_name
                )
            
            result = await get_channel_videos(channel_id, api_key, max_results)
        
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
        logger.error(f"Error in YouTube Loader node: {str(e)}", exc_info=True)
        return NodeResult(
            output={"error": str(e)},
            type="object",
            execution_time=datetime.now().timestamp() - start_time,
            status="error",
            error=str(e),
            node_id=node_id,
            node_name=node_name
        ) 