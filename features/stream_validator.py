import aiohttp
from m3u8 import M3U8
import time
import logging
import re
import ssl

async def validate_stream(session, url, timeout=15):
    """
    Enhanced stream validation with better error handling and retry logic.
    Returns True if the stream is likely accessible, False otherwise.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive"
    }
    
    try:
        # Skip problematic protocols
        if url.startswith('rtmp://') or url.startswith('rtsp://'):
            logging.debug(f"Skipping unsupported protocol: {url}")
            return False
            
        # First attempt: Basic HEAD request to check accessibility
        try:
            async with session.head(url, timeout=8, headers=headers, ssl=False) as head_response:
                if head_response.status in {200, 302, 206}:
                    logging.debug(f"Stream accessible via HEAD: {url}")
                elif head_response.status in {403, 429}:
                    logging.debug(f"Access denied for {url}, will try full GET")
                else:
                    logging.debug(f"HEAD request failed for {url}: {head_response.status}")
        except Exception as e:
            logging.debug(f"HEAD request failed for {url}: {e}")
        
        # Main validation with GET request - shorter timeout to avoid hanging
        async with session.get(url, timeout=10, headers=headers, ssl=False) as response:
            if response.status not in {200, 206, 302}:
                logging.debug(f"Stream not accessible: {url} (status: {response.status})")
                return False

            content_type = response.headers.get('content-type', '').lower()
            
            # Handle different stream types
            if '.m3u8' in url or 'application/vnd.apple.mpegurl' in content_type:
                return await validate_hls_stream(session, response, url, timeout)
            elif any(ct in content_type for ct in ['video/mp4', 'video/mpeg', 'video/quicktime']):
                logging.info(f"Direct video stream detected: {url}")
                return True
            elif 'application/octet-stream' in content_type or 'binary' in content_type:
                logging.info(f"Binary stream detected: {url}")
                return True
            else:
                # For unknown content types, try to read a small chunk
                try:
                    chunk = await response.content.read(512)
                    if chunk and len(chunk) > 0:
                        # Check if it looks like stream data
                        if any(pattern in chunk[:100].lower() for pattern in [b'#extm3u', b'#ext-x', b'ftyp']):
                            logging.info(f"Stream data detected in chunk: {url}")
                            return True
                        logging.debug(f"Data received for {url}, assuming stream is valid")
                        return True
                    else:
                        logging.debug(f"No data received for {url}")
                        return False
                except Exception as e:
                    logging.debug(f"Error reading stream chunk for {url}: {e}")
                    return False

    except aiohttp.TimeoutError:
        logging.debug(f"Timeout accessing stream: {url}")
        return False
    except aiohttp.ClientError as e:
        logging.debug(f"Client error accessing stream {url}: {e}")
        return False
    except Exception as e:
        logging.debug(f"Unexpected error validating stream {url}: {e}")
        return False

async def validate_hls_stream(session, response, url, timeout):
    """
    Specialized HLS stream validation with more lenient checks.
    """
    try:
        text = await response.text()
        
        # Basic M3U validation
        if not text.strip().startswith('#EXTM3U'):
            logging.debug(f"Invalid M3U format: {url}")
            return False
            
        playlist = M3U8(text)
        
        # Check if we have segments or variant playlists
        if playlist.segments:
            # Just check if we have segments, don't validate each one (too slow)
            if len(playlist.segments) > 0:
                logging.info(f"HLS stream has {len(playlist.segments)} segments: {url}")
                return True
            else:
                logging.debug(f"No segments found in playlist: {url}")
                return False
                
        elif playlist.playlists:
            # Variant playlist - just check if we have variants
            if len(playlist.playlists) > 0:
                logging.info(f"HLS variant playlist with {len(playlist.playlists)} variants: {url}")
                return True
            else:
                logging.debug(f"No variants found in playlist: {url}")
                return False
        else:
            logging.debug(f"No segments or variants found in playlist: {url}")
            return False
            
    except Exception as e:
        logging.debug(f"Failed to parse HLS playlist {url}: {e}")
        return False