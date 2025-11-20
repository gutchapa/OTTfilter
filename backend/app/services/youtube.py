from googleapiclient.discovery import build
import logging
from app.core.config import get_settings
from app.models.movie import YouTubeVideo
from typing import List

settings = get_settings()
logger = logging.getLogger(__name__)

youtube_service = build('youtube', 'v3', developerKey=settings.YOUTUBE_API_KEY) if settings.YOUTUBE_API_KEY else None

def search_youtube_videos(query: str, max_results: int = 5) -> List[YouTubeVideo]:
    """Search YouTube for videos"""
    if not youtube_service:
        return []
    
    try:
        request = youtube_service.search().list(
            part='snippet',
            q=query,
            type='video',
            maxResults=max_results,
            regionCode='IN'
        )
        response = request.execute()
        
        videos = []
        for item in response.get('items', []):
            video = YouTubeVideo(
                video_id=item['id']['videoId'],
                title=item['snippet']['title'],
                thumbnail_url=item['snippet']['thumbnails']['medium']['url'],
                channel_title=item['snippet']['channelTitle'],
                url=f"https://www.youtube.com/watch?v={item['id']['videoId']}"
            )
            videos.append(video)
        
        return videos
    except Exception as e:
        logger.error(f"Error searching YouTube: {str(e)}")
        return []
