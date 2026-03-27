import os
import re
import json
import time
import logging
import asyncio
import aiohttp
import requests
import threading
from flask import Flask, jsonify, request, Response, stream_with_context, send_file, render_template
from flask_cors import CORS
from threading import Thread
import time
import re
from urllib.parse import quote
import urllib.parse
from urllib.request import urlopen
import subprocess
import tempfile
import yt_dlp
from pathlib import Path

# constants
M3U_URL = "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"
BATCH_SIZE = 10 # number of channels to process in each batch. 
FILES = {
        "streams": 'jsons/IPTV_STREAMS_FILE.json',
        "dead": 'jsons/DEAD_STREAMS_FILE.json',
        "invalid": 'jsons/INVALID_LINKS_FILE.json'
}
DIRECTORIES = ['webroot', 'webroot/js']

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global variable for live update tracking
last_update_count = 0

# Ensure required directories and files exist
for directory in DIRECTORIES:
    os.makedirs(directory, exist_ok=True)
for file in FILES.values():
    if not os.path.exists(file):
        with open(file, 'w') as f:
            json.dump([], f)

# Create icons directory for channel logos
os.makedirs('webroot/icons', exist_ok=True)

# Initialize Flask app
app = Flask(__name__, template_folder='webroot', static_folder='webroot')
CORS(app) 


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0"
}

def get_valid_channels():
    """Get current valid channels from file."""
    try:
        with open(FILES['streams'], 'r') as f:
            return json.load(f)
    except:
        return []

def get_update_count():
    """Get current count of valid channels."""
    global last_update_count
    channels = get_valid_channels()
    count = len(channels)
    if count != last_update_count:
        last_update_count = count
    return count

#checks if link exists
async def check_link_exists(session, url, retries=3, delay=5):
    retryable_statuses = {500, 502, 503, 504, 429, 403}  # include 403 for Cloudflare

    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, timeout=20, headers=HEADERS) as response:
                if response.status in {200, 302}:
                    return True
                if response.status in retryable_statuses:
                    logging.warning(f"Retryable error {response.status} for {url}, attempt {attempt}")
                    if attempt < retries:
                        await asyncio.sleep(delay * attempt)  # Exponential backoff
                    continue
                else:
                    logging.warning(f"Invalid link {url} (status: {response.status})")
                    return False
        except aiohttp.ClientError as e:
            logging.error(f"Network error attempt {attempt} for {url}: {e}")
            if attempt < retries:
                await asyncio.sleep(delay * attempt)
            continue
        except Exception as e:
            logging.error(f"Unexpected error attempt {attempt} for {url}: {e}")
            if attempt < retries:
                await asyncio.sleep(delay * attempt)
            continue

    return False 



# Asynchronously validate a single channel.
async def validate_channel(session, channel):
    
    try:
        logging.info(f"Validating channel: {channel['url']}")
        if await validate_stream(session, channel['url']): 
            channel['status'] = 'online'
            return channel, True
        else:
            channel['status'] = 'offline'
            return channel, False
    except Exception as e:
        logging.error(f"Error validating channel {channel['url']}: {e}")
        channel['status'] = 'error'
        return channel, False


#Process channels in batches asynchronously
async def process_channels(channels, invalid_links, delay=5):
   
    valid_channels = []
    dead_channels = []
    
    # Create session with SSL settings to handle certificate issues
    connector = aiohttp.TCPConnector(
        ssl=False,  # Disable SSL verification for problematic certificates
        limit=100,   # Increase connection pool size
        limit_per_host=20
    )
    
    async with aiohttp.ClientSession(connector=connector) as session:
        for i in range(0, len(channels), BATCH_SIZE):
            batch = channels[i:i + BATCH_SIZE]
            tasks = [validate_channel(session, channel) for channel in batch if channel['url'] not in invalid_links]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    logging.error(f"Batch processing error: {result}")
                    continue
                    
                channel, is_valid = result
                if is_valid:
                    valid_channels.append(channel)
                else:
                    dead_channels.append(channel)
            
            # Save progress after each batch
            try:
                with open(FILES['streams'], 'w') as f:
                    json.dump(valid_channels, f, indent=4) 

                with open(FILES['dead'], 'w') as f:
                    json.dump(dead_channels, f, indent=4)
                    
                logging.info(f"Batch {i//BATCH_SIZE + 1}: {len(valid_channels)} valid, {len(dead_channels)} dead")
                
            except Exception as e:
                logging.error(f"Error saving batch: {e}")

            await asyncio.sleep(delay) # play about with this to control processing speed
            
    return valid_channels, dead_channels



#Perform an initial scan to check if links exist and validate them.
async def initial_scan():
    try:
        logging.info("Starting initial scan...")
        channels = check_channels(M3U_URL)

        async with aiohttp.ClientSession() as session:
            tasks = [check_link_exists(session, ch['url']) for ch in channels]
            exists_results = await asyncio.gather(*tasks)
            invalid_links = [ch['url'] for ch, exists in zip(channels, exists_results) if not exists]
            valid_channels, dead_channels = await process_channels([ch for ch, exists in zip(channels, exists_results) if exists], invalid_links)

        for file, data in zip(FILES.values(), [valid_channels, dead_channels, invalid_links]):
            with open(file, 'w') as f:
                json.dump(data, f, indent=4)

        logging.info(f"Initial scan complete: {len(valid_channels)} valid, {len(dead_channels)} dead.")
    except Exception as e:
        logging.error(f"Error during initial scan: {e}")



async def sweep_channels_async():
    logging.info("Starting channel sweep...")
    channels = check_channels(M3U_URL)
    with open(FILES['invalid'], 'r') as f:
        invalid_links = json.load(f)
        valid_channels, dead_channels = await process_channels(channels, invalid_links)
    
    for file, data in zip([FILES['streams'], FILES['dead']], [valid_channels, dead_channels]):
        with open(file, 'w') as f:
            json.dump(data, f, indent=4)

    logging.info(f"Channel sweep complete: {len(valid_channels)} valid, {len(dead_channels)} dead.")      


async def start_periodic_sweep():
    """Start periodic channel sweeps every 3 hours."""
    while True:
        await sweep_channels_async() # use asyncio.sleep() instead of time.sleep()
        await asyncio.sleep(3 * 60 * 60)  # Sleep for 3 hours



#flask routes

@app.route('/')
def index():
    """Render the main TV guide page."""
    return render_template('index.html')

@app.route('/status')
def get_status():
    """Return current scanning status and channel count."""
    try:
        channels = get_valid_channels()
        return jsonify({
            'total_channels': len(channels),
            'scanning': True,  # We could track this more precisely
            'last_update': time.time()
        })
    except Exception as e:
        return jsonify({'error': str(e)})

def download_channel_icon(channel_name, channel_url, tvg_logo):
    """Download and cache channel icon/logo with multiple sources."""
    try:
        # Create a safe filename from channel name
        safe_name = re.sub(r'[^\w\-_\.]', '', channel_name.lower())
        icon_path = f'webroot/icons/{safe_name}.png'
        
        # If icon already exists, return URL
        if os.path.exists(icon_path):
            return f'/icons/{safe_name}.png'
        
        # Source 1: Try tvg_logo from M3U playlist
        if tvg_logo and tvg_logo != '':
            try:
                response = requests.get(tvg_logo, timeout=10, headers=HEADERS)
                if response.status_code == 200:
                    with open(icon_path, 'wb') as f:
                        f.write(response.content)
                    logging.info(f"Downloaded icon for {channel_name} from tvg_logo")
                    return f'/icons/{safe_name}.png'
            except Exception as e:
                logging.warning(f"Failed to download tvg_logo for {channel_name}: {e}")
        
        # Source 2: YouTube Channel Icons
        if 'youtube.com' in channel_url or 'youtu.be' in channel_url:
            icon_url = get_youtube_channel_icon(channel_url)
            if icon_url:
                try:
                    response = requests.get(icon_url, timeout=10, headers=HEADERS)
                    if response.status_code == 200:
                        with open(icon_path, 'wb') as f:
                            f.write(response.content)
                        logging.info(f"Downloaded YouTube icon for {channel_name}")
                        return f'/icons/{safe_name}.png'
                except Exception as e:
                    logging.warning(f"Failed to download YouTube icon for {channel_name}: {e}")
        
        # Source 3: TV Logo Sources (Similar to Excel logo systems)
        icon_sources = [
            # TV Logos database
            f"https://raw.githubusercontent.com/tv-logo/tv-logos/main/data/logos/{safe_name}.png",
            f"https://raw.githubusercontent.com/tv-logo/tv-logos/main/data/logos/{safe_name}.jpg",
            # IPTV Logos repository
            f"https://raw.githubusercontent.com/iptv-org/epg/master/logos/{safe_name}.png",
            f"https://raw.githubusercontent.com/iptv-org/epg/master/logos/{safe_name}.jpg",
            # Alternative TV logos
            f"https://raw.githubusercontent.com/fanmixco/IPTV_Logos/master/{safe_name}.png",
            f"https://raw.githubusercontent.com/fanmixco/IPTV_Logos/master/{safe_name}.jpg",
        ]
        
        for icon_url in icon_sources:
            try:
                response = requests.get(icon_url, timeout=5, headers=HEADERS)
                if response.status_code == 200 and len(response.content) > 100:
                    with open(icon_path, 'wb') as f:
                        f.write(response.content)
                    logging.info(f"Downloaded logo for {channel_name} from {icon_url}")
                    return f'/icons/{safe_name}.png'
            except:
                continue
        
        # Source 4: Domain Favicons
        domain_icon = get_domain_favicon(channel_url)
        if domain_icon:
            try:
                response = requests.get(domain_icon, timeout=5, headers=HEADERS)
                if response.status_code == 200 and len(response.content) > 100:
                    with open(icon_path, 'wb') as f:
                        f.write(response.content)
                    logging.info(f"Downloaded favicon for {channel_name}")
                    return f'/icons/{safe_name}.png'
            except Exception as e:
                logging.warning(f"Failed to download favicon for {channel_name}: {e}")
        
        # Source 5: Google Favicon API
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(channel_url)
            domain = parsed_url.netloc
            
            google_favicon = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
            response = requests.get(google_favicon, timeout=5, headers=HEADERS)
            if response.status_code == 200 and len(response.content) > 100:
                with open(icon_path, 'wb') as f:
                    f.write(response.content)
                logging.info(f"Downloaded Google favicon for {channel_name}")
                return f'/icons/{safe_name}.png'
        except Exception as e:
            logging.warning(f"Failed to download Google favicon for {channel_name}: {e}")
        
        # Source 6: DuckDuckGo Icon API
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(channel_url)
            domain = parsed_url.netloc
            
            ddg_icon = f"https://icons.duckduckgo.com/ip3/{domain}.ico"
            response = requests.get(ddg_icon, timeout=5, headers=HEADERS)
            if response.status_code == 200 and len(response.content) > 100:
                with open(icon_path, 'wb') as f:
                    f.write(response.content)
                logging.info(f"Downloaded DuckDuckGo icon for {channel_name}")
                return f'/icons/{safe_name}.png'
        except Exception as e:
            logging.warning(f"Failed to download DuckDuckGo icon for {channel_name}: {e}")
        
        # If all else fails, return None
        logging.info(f"No icon found for {channel_name}, will use text fallback")
        return None
        
    except Exception as e:
        logging.error(f"Error downloading icon for {channel_name}: {e}")
        return None

def get_youtube_channel_icon(channel_url):
    """Extract YouTube channel icon using yt-dlp."""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            if info and info.get('thumbnail'):
                return info['thumbnail']
    except Exception as e:
        logging.warning(f"Failed to get YouTube icon: {e}")
        return None

def get_domain_favicon(channel_url):
    """Get favicon from channel domain."""
    try:
        from urllib.parse import urlparse
        parsed_url = urlparse(channel_url)
        domain = parsed_url.netloc
        
        # Try common favicon locations
        favicon_urls = [
            f"https://{domain}/favicon.ico",
            f"https://{domain}/favicon.png",
            f"https://{domain}/apple-touch-icon.png",
            f"https://{domain}/android-chrome-192x192.png",
        ]
        
        for favicon_url in favicon_urls:
            try:
                response = requests.head(favicon_url, timeout=3, headers=HEADERS)
                if response.status_code == 200:
                    return favicon_url
            except:
                continue
    except Exception as e:
        logging.warning(f"Failed to get domain favicon: {e}")
        return None

@app.route('/icons/<filename>')
def serve_icon(filename):
    """Serve cached channel icons."""
    try:
        icon_path = f'webroot/icons/{filename}'
        if os.path.exists(icon_path):
            return send_file(icon_path, mimetype='image/png')
        else:
            return "Icon not found", 404
    except Exception as e:
        logging.error(f"Error serving icon {filename}: {e}")
        return "Error serving icon", 500

def get_channel_info(channel_name, channel_url):
    """Get current program information for a channel."""
    try:
        # For YouTube channels, try to get video title
        if 'youtube.com' in channel_url or 'youtu.be' in channel_url:
            try:
                # Extract channel ID or video ID
                if '/live' in channel_url:
                    # For live streams, return "LIVE"
                    return f" LIVE - {channel_name}"
                else:
                    return " Live Stream"
            except:
                return " Live Stream"
        
        # For Twitch channels
        elif 'twitch.tv' in channel_url:
            return " Live Stream"
        
        # For other M3U8 streams
        elif '.m3u8' in channel_url:
            try:
                # Try to fetch the playlist to get title info
                response = requests.get(channel_url, timeout=5, headers=HEADERS)
                if response.status_code == 200:
                    content = response.text
                    # Look for title metadata
                    title_match = re.search(r'#EXT-X-STREAM-TITLE:(.+)', content, re.IGNORECASE)
                    if title_match:
                        return title_match.group(1).strip()
            except:
                pass
        
        # Default fallback
        return f" {channel_name}"
        
    except Exception as e:
        logging.debug(f"Error getting channel info for {channel_name}: {e}")
        return f" {channel_name}"

@app.route('/channel-info/<channel_name>')
def get_channel_info_endpoint(channel_name):
    """API endpoint to get channel information."""
    try:
        with open(FILES['streams'], 'r') as f:
            channels = json.load(f)
        
        # Find channel by name
        channel = None
        for ch in channels:
            if ch['name'] == channel_name:
                channel = ch
                break
        
        if channel:
            info = get_channel_info(channel['name'], channel['url'])
            return jsonify({
                'name': channel['name'],
                'playing_now': info,
                'status': channel.get('status', 'unknown')
            })
        else:
            return jsonify({'error': 'Channel not found'}), 404
            
    except Exception as e:
        logging.error(f"Error getting channel info: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/channels')
def get_channels():
    """Return a list of channels with configurable limit and improved sorting and grouping."""
    try:
        with open(FILES['streams'], 'r') as f:
            channels = json.load(f)
            
            if not channels:
                return jsonify([])
            
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 15))  # Default to 15, but allow override
            sort_by = request.args.get('sort_by', 'name')
            group_by = request.args.get('group_by', 'group_title')
            status_filter = request.args.get('status', '')  # Optional status filter
            
            # Apply status filter if provided
            if status_filter and status_filter in ['online', 'offline', 'error']:
                channels = [ch for ch in channels if ch.get('status') == status_filter]
            
            # Pre-cache all channel logos in background (non-blocking)
            if request.args.get('preload_icons') != 'false':
                threading.Thread(target=preload_all_channel_icons, args=(channels,), daemon=True).start()
            
            # Add cached icon URLs to channels
            for channel in channels:
                icon_url = get_cached_icon_url(channel['name'], channel['url'], channel.get('tvg_logo', ''))
                if icon_url:
                    channel['icon_url'] = icon_url
                else:
                    channel['icon_url'] = None
            
            # Skip expensive operations for fast loading
            # Only add playing_now info if explicitly requested
            if request.args.get('include_info') == 'true':
                for channel in channels:
                    if not channel.get('playing_now') or channel['playing_now'] == 'Not available':
                        channel['playing_now'] = get_channel_info(channel['name'], channel['url'])
            
            # Safe sorting with fallback
            def sort_key(channel):
                value = channel.get(sort_by, '')
                if isinstance(value, str):
                    return value.lower()
                return str(value).lower()
            
            try:
                channels.sort(key=sort_key)
            except Exception as e:
                logging.warning(f"Sorting failed: {e}, using default order")
                channels.sort(key=lambda x: x.get('name', '').lower())

            # If limit is very high, return all channels without pagination
            if limit >= 1000:
                # Group channels if requested
                if group_by != 'none':
                    grouped_channels = {}
                    for ch in channels:
                        group_key = ch.get(group_by, 'Unknown')
                        if group_key not in grouped_channels:
                            grouped_channels[group_key] = []
                        grouped_channels[group_key].append(ch)
                    
                    # Return all groups
                    result = {
                        'groups': [],
                        'total_groups': len(grouped_channels),
                        'current_page': 1,
                        'has_more': False
                    }
                    
                    for group_name in grouped_channels:
                        result['groups'].append({
                            'group_name': group_name,
                            'channels': grouped_channels[group_name]
                        })
                    
                    return jsonify(result)
                else:
                    # Return all channels flat
                    return jsonify({
                        'channels': channels,
                        'total_channels': len(channels),
                        'current_page': 1,
                        'has_more': False,
                        'total_pages': 1
                    })
            
            # Group channels if requested (with pagination)
            if group_by != 'none':
                grouped_channels = {}
                for ch in channels:
                    group_key = ch.get(group_by, 'Unknown')
                    if group_key not in grouped_channels:
                        grouped_channels[group_key] = []
                    grouped_channels[group_key].append(ch)
                
                # Return grouped format with pagination
                start_idx = (page - 1) * limit
                end_idx = start_idx + limit
                group_names = list(grouped_channels.keys())[start_idx:end_idx]
                
                result = {
                    'groups': [],
                    'total_groups': len(grouped_channels),
                    'current_page': page,
                    'has_more': end_idx < len(grouped_channels)
                }
                
                for group_name in group_names:
                    result['groups'].append({
                        'group_name': group_name,
                        'channels': grouped_channels[group_name]
                    })
                
                return jsonify(result)
            else:
                # Return flat pagination
                start_idx = (page - 1) * limit
                end_idx = start_idx + limit
                paginated_channels = channels[start_idx:end_idx]
                
                has_more = end_idx < len(channels)
                total_pages = (len(channels) + limit - 1) // limit  # ceiling division
                
                return jsonify({
                    'channels': paginated_channels,
                    'total_channels': len(channels),
                    'current_page': page,
                    'has_more': has_more,
                    'total_pages': total_pages
                })
    
    except FileNotFoundError:
        logging.warning("Streams file not found, returning empty list")
        return jsonify([])
    except json.JSONDecodeError:
        logging.error("Invalid JSON in streams file")
        return jsonify([])
    except Exception as e:
        logging.error(f"Error loading channels: {e}")
        return jsonify([])

def get_cached_icon_url(channel_name, channel_url, tvg_logo):
    """Get cached icon URL for a channel."""
@app.route('/proxy/image')
def proxy_image():
    """Proxy image requests with caching and rate limiting."""
    global image_cache, last_cache_clear
    try:
        image_url = request.args.get('url')
        if not image_url:
            return "No URL provided", 400
        
        # Check cache first
        if image_url in image_cache:
            cached_data = image_cache[image_url]
            if time.time() - cached_data['timestamp'] < 3600:  # Cache for 1 hour
                return Response(
                    cached_data['content'],
                    mimetype=cached_data['mimetype'],
                    headers={
                        'Cache-Control': 'public, max-age=3600',
                        'Access-Control-Allow-Origin': '*'
                    }
                )
        
        # Rate limiting - clear old cache entries periodically
        if time.time() - last_cache_clear > 300:  # Clear cache every 5 minutes
            # Keep only recent entries
            current_time = time.time()
            image_cache = {k: v for k, v in image_cache.items() 
                          if current_time - v['timestamp'] < 1800}  # Keep entries < 30 minutes
            last_cache_clear = current_time
        
        # Fetch the image with proper headers
        response = requests.get(image_url, timeout=5, headers=HEADERS)
        
        if response.status_code == 200:
            # Cache the response
            image_cache[image_url] = {
                'content': response.content,
                'mimetype': response.headers.get('content-type', 'image/png'),
                'timestamp': time.time()
            }
            
            # Return the image with proper headers
            return Response(
                response.content,
                mimetype=response.headers.get('content-type', 'image/png'),
                headers={
                    'Cache-Control': 'public, max-age=3600',  # Cache for 1 hour
                    'Access-Control-Allow-Origin': '*'
                }
            )
        else:
            return f"Failed to fetch image: {response.status_code}", response.status_code
            
    except Exception as e:
        logging.error(f"Error proxying image {image_url}: {e}")
        return f"Error: {str(e)}", 500

@app.route('/download-icons')
def download_all_icons():
    """Download icons for all channels."""
    try:
        with open(FILES['streams'], 'r') as f:
            channels = json.load(f)
        
        downloaded = 0
        failed = 0
        
        for channel in channels:
            try:
                icon_url = download_channel_icon(channel['name'], channel['url'], channel.get('tvg_logo', ''))
                if icon_url:
                    downloaded += 1
                    logging.info(f"✅ Downloaded icon for {channel['name']}")
                else:
                    failed += 1
                    logging.info(f"❌ No icon found for {channel['name']}")
            except Exception as e:
                failed += 1
                logging.error(f"Error downloading icon for {channel['name']}: {e}")
        
        return jsonify({
            'message': f'Icon download complete',
            'downloaded': downloaded,
            'failed': failed,
            'total': len(channels)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/search')
def search_channels():
    """Search for channels by name."""
    try:
        query = request.args.get('query', '').lower()
        with open(FILES['streams'], 'r') as f:
            channels = json.load(f)
        return jsonify([ch for ch in channels if query in ch['name'].lower()])
    except Exception as e:
        logging.error(f"Error searching channels: {e}")
        return jsonify([])

def get_youtube_stream_url(url):
    """Extract actual stream URL from YouTube using yt-dlp for reliable extraction."""
    try:
        logging.info(f"Attempting to extract YouTube stream from URL: {url}")
        
        # Use yt-dlp for reliable YouTube stream extraction
        import yt_dlp
        
        # Configure yt-dlp options
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'format': 'best[height<=720]',  # Limit to 720p for performance
            'noplaylist': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract video info
                info = ydl.extract_info(url, download=False)
                
                if info:
                    # For live streams, get the best format
                    if info.get('is_live'):
                        logging.info(f"Detected live stream: {info.get('title', 'Unknown')}")
                        # Get the best format URL for live streams
                        formats = info.get('formats', [])
                        if formats:
                            # Find the best format for streaming
                            best_format = None
                            for fmt in formats:
                                if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
                                    if not best_format or fmt.get('height', 0) > best_format.get('height', 0):
                                        best_format = fmt
                            
                            if best_format and best_format.get('url'):
                                stream_url = best_format['url']
                                logging.info(f"Extracted live stream URL: {stream_url}")
                                return stream_url
                    else:
                        # For regular videos, get the best format
                        formats = info.get('formats', [])
                        if formats:
                            best_format = None
                            for fmt in formats:
                                if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
                                    if not best_format or fmt.get('height', 0) > best_format.get('height', 0):
                                        best_format = fmt
                            
                            if best_format and best_format.get('url'):
                                stream_url = best_format['url']
                                logging.info(f"Extracted video stream URL: {stream_url}")
                                return stream_url
                    
                    # Fallback to embed URL if no direct stream found
                    video_id = info.get('id')
                    if video_id:
                        embed_url = f"https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0"
                        logging.info(f"Falling back to embed URL: {embed_url}")
                        return embed_url
                
        except Exception as e:
            logging.warning(f"yt-dlp extraction failed: {e}")
            # Fallback to basic extraction
            return extract_youtube_url_basic(url)
        
    except ImportError:
        logging.error("yt-dlp not installed, falling back to basic extraction")
        return extract_youtube_url_basic(url)
    except Exception as e:
        logging.error(f"Error extracting YouTube URL: {e}")
        logging.error(f"Exception details: {type(e).__name__}: {str(e)}")
        return None

def extract_youtube_url_basic(url):
    """Basic YouTube URL extraction as fallback."""
    try:
        logging.info(f"Using basic YouTube extraction for: {url}")
        
        # Extract video ID with better regex patterns
        video_id = None
        
        # Pattern 1: youtube.com/watch?v=
        if 'youtube.com/watch?v=' in url:
            video_id = url.split('v=')[1].split('&')[0]
            logging.info(f"Extracted video ID using pattern 1: {video_id}")
        # Pattern 2: youtu.be/
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0]
            logging.info(f"Extracted video ID using pattern 2: {video_id}")
        # Pattern 3: youtube.com/embed/
        elif 'youtube.com/embed/' in url:
            video_id = url.split('embed/')[1].split('?')[0]
            logging.info(f"Extracted video ID using pattern 3: {video_id}")
        # Pattern 4: YouTube channel live streams
        elif '/live' in url:
            logging.info(f"Detected YouTube live stream URL: {url}")
            # For live streams, we need to extract channel handle and convert to embed
            if '/@' in url:
                # Handle format: https://www.youtube.com/@EuronewsAlbania/live
                channel_handle = url.split('/@')[1].split('/')[0]
                logging.info(f"Extracted channel handle: {channel_handle}")
                # For live channels, use channel URL in iframe
                return f"https://www.youtube.com/embed/live_stream?channel={channel_handle}"
            elif '/channel/' in url:
                # Handle format: https://www.youtube.com/channel/UCU1i6qBMjY9El6q5L2OK8hA/live
                channel_id = url.split('/channel/')[1].split('/')[0]
                logging.info(f"Extracted channel ID: {channel_id}")
                # For live channels, use channel URL in iframe
                return f"https://www.youtube.com/embed/live_stream?channel={channel_id}"
            elif '/c/' in url:
                # Handle format: https://www.youtube.com/c/channelname/live
                channel_name = url.split('/c/')[1].split('/')[0]
                logging.info(f"Extracted channel name: {channel_name}")
                # For live channels, use channel URL in iframe
                return f"https://www.youtube.com/embed/live_stream?channel={channel_name}"
            elif '/user/' in url:
                # Handle format: https://www.youtube.com/user/username/live
                username = url.split('/user/')[1].split('/')[0]
                logging.info(f"Extracted username: {username}")
                # For live channels, use channel URL in iframe
                return f"https://www.youtube.com/embed/live_stream?channel={username}"
            else:
                logging.warning(f"Unknown live stream format: {url}")
                return None
        # Pattern 5: Handle various YouTube URL formats
        else:
            import re
            # Try to extract video ID using regex
            patterns = [
                r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
                r'youtube\.com.*[?&]v=([a-zA-Z0-9_-]{11})'
            ]
            for i, pattern in enumerate(patterns):
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    logging.info(f"Extracted video ID using regex pattern {i+1}: {video_id}")
                    break
        
        if video_id:
            # Validate video ID format (should be 11 characters)
            if len(video_id) != 11:
                logging.warning(f"Invalid video ID format: {video_id} (length: {len(video_id)})")
                return None
            
            logging.info(f"Valid video ID extracted: {video_id}")
            
            # Return embed URL directly - this is most reliable approach
            embed_url = f"https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0"
            logging.info(f"Generated embed URL: {embed_url}")
            return embed_url
        else:
            logging.warning(f"Could not extract video ID from URL: {url}")
            logging.warning(f"URL patterns checked: youtube.com/watch?v=, youtu.be/, youtube.com/embed/, /live, regex patterns")
            return None
        
    except Exception as e:
        logging.error(f"Error in basic YouTube extraction: {e}")
        return None

def get_twitch_stream_url(url):
    """Extract actual stream URL from Twitch using direct API approach."""
    try:
        # Extract channel name
        if 'twitch.tv/' in url:
            channel = url.split('twitch.tv/')[1].split('/')[0]
        else:
            return None
        
        if not channel:
            return None
        
        # Return Twitch embed URL for iframe
        # This will work with the frontend iframe approach
        return f"https://player.twitch.tv/?channel={channel}&parent=localhost&parent=127.0.0.1&autoplay=true"
        
    except Exception as e:
        logging.error(f"Error extracting Twitch URL: {e}")
        return None

@app.route('/proxy/stream')
def proxy_stream():
    """Proxy YouTube and Twitch streams to work with HTML5 video player."""
    try:
        stream_url = request.args.get('url')
        if not stream_url:
            logging.error("No URL provided to proxy/stream endpoint")
            return jsonify({'error': 'No URL provided'}), 400
        
        logging.info(f"Proxy stream request for URL: {stream_url}")
        logging.info(f"URL type check - YouTube: {'youtube.com' in stream_url or 'youtu.be' in stream_url}, Twitch: {'twitch.tv' in stream_url}")
        
        # YouTube handling
        if 'youtube.com' in stream_url or 'youtu.be' in stream_url:
            logging.info(f"Processing YouTube URL: {stream_url}")
            direct_url = get_youtube_stream_url(stream_url)
            if direct_url:
                logging.info(f"YouTube extraction successful, redirecting to: {direct_url}")
                return redirect(direct_url, code=302)
            else:
                logging.error(f"YouTube extraction failed for URL: {stream_url}")
                return jsonify({'error': 'Failed to extract YouTube stream'}), 500
        
        # Twitch handling
        elif 'twitch.tv' in stream_url:
            logging.info(f"Processing Twitch URL: {stream_url}")
            direct_url = get_twitch_stream_url(stream_url)
            if direct_url:
                logging.info(f"Twitch extraction successful, redirecting to: {direct_url}")
                return redirect(direct_url, code=302)
            else:
                logging.error(f"Twitch extraction failed for URL: {stream_url}")
                return jsonify({'error': 'Failed to extract Twitch stream'}), 500
        
        # Direct stream for other sources
        else:
            logging.info(f"Processing direct stream URL: {stream_url}")
            return proxy_direct_stream(stream_url)
            
    except Exception as e:
        logging.error(f"Error proxying stream: {e}")
        logging.error(f"Exception details: {type(e).__name__}: {str(e)}")
        return jsonify({'error': str(e)}), 500

def proxy_direct_stream(url):
    """Proxy direct streams."""
    try:
        # For direct streams, we can redirect or proxy content
        response = requests.get(url, headers=HEADERS, stream=True, timeout=10)
        
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                yield chunk
        
        return Response(stream_with_context(generate()),
                       content_type=response.headers.get('Content-Type', 'application/octet-stream'),
                       headers={'Access-Control-Allow-Origin': '*'})
        
    except Exception as e:
        logging.error(f"Error proxying direct stream: {e}")
        return jsonify({'error': 'Failed to proxy stream'}), 500

from flask import redirect

def run_flask():
    app.run(host='127.0.0.1', port=40006, use_reloader=False)

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # start flask in seperate thread so it doesnt block the loop
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    # start async tasks
    loop.create_task(initial_scan())
    loop.create_task(start_periodic_sweep())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logging.info('shutting down :3')
    finally:
        loop.close()

   
 