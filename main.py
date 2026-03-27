import os
import json
import time
import re
from threading import Thread
import asyncio
import aiohttp
import requests
from flask import Flask, render_template, jsonify, request, Response, stream_with_context
from flask_cors import CORS
from features.channel_checker import check_channels
from features.stream_validator import validate_stream
import logging
import urllib.parse
from urllib.request import urlopen

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
            
            # Add playing_now info to channels
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
        logging.error(f"Error loading channels: {e}")
        return jsonify([])


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

@app.route('/proxy/stream')
def proxy_stream():
    """Proxy YouTube and Twitch streams to work with HTML5 video player."""
    try:
        stream_url = request.args.get('url')
        if not stream_url:
            return jsonify({'error': 'No URL provided'}), 400
        
        # YouTube handling
        if 'youtube.com' in stream_url or 'youtu.be' in stream_url:
            return proxy_youtube_stream(stream_url)
        
        # Twitch handling
        elif 'twitch.tv' in stream_url:
            return proxy_twitch_stream(stream_url)
        
        # Direct stream for other sources
        else:
            return proxy_direct_stream(stream_url)
            
    except Exception as e:
        logging.error(f"Error proxying stream: {e}")
        return jsonify({'error': str(e)}), 500

def proxy_youtube_stream(url):
    """Proxy YouTube stream by extracting direct video URL."""
    try:
        # Extract video ID
        video_id = None
        if 'youtube.com/watch?v=' in url:
            video_id = url.split('v=')[1].split('&')[0]
        elif 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0]
        elif 'youtube.com/embed/' in url:
            video_id = url.split('embed/')[1].split('?')[0]
        
        if not video_id:
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        # For now, create an M3U8 playlist that points to YouTube
        # In a production environment, you'd use youtube-dl or yt-dlp
        playlist_content = f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXT-X-MEDIA-SEQUENCE:0
#EXTINF:10.0,YouTube Stream
https://rr1---sn-8pxxvh5vxa-cxge.googlevideo.com/videoplayback?expire=1714400000&ei=XXXX&itag=18&source=youtube&id={video_id}
#EXTINF:10.0,YouTube Stream
https://rr1---sn-8pxxvh5vxa-cxge.googlevideo.com/videoplayback?expire=1714400000&ei=XXXX&itag=22&source=youtube&id={video_id}
#EXT-X-ENDLIST
"""
        
        return Response(playlist_content, mimetype='application/vnd.apple.mpegurl')
        
    except Exception as e:
        logging.error(f"Error proxying YouTube: {e}")
        return jsonify({'error': 'Failed to proxy YouTube stream'}), 500

def proxy_twitch_stream(url):
    """Proxy Twitch stream by extracting direct video URL."""
    try:
        # Extract channel name
        if 'twitch.tv/' in url:
            channel = url.split('twitch.tv/')[1].split('/')[0]
        else:
            return jsonify({'error': 'Invalid Twitch URL'}), 400
        
        # Create M3U8 playlist for Twitch stream
        # In production, you'd use Twitch API or stream extraction
        playlist_content = f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:6
#EXT-X-MEDIA-SEQUENCE:0
#EXTINF:6.0,Twitch Stream - {channel}
https://video-weaver.fra05.hls.ttvnw.net/v1/playlist/{channel}.m3u8
#EXTINF:6.0,Twitch Stream - {channel}
https://video-weaver.fra05.hls.ttvnw.net/v1/playlist/{channel}_720p.m3u8
#EXT-X-ENDLIST
"""
        
        return Response(playlist_content, mimetype='application/vnd.apple.mpegurl')
        
    except Exception as e:
        logging.error(f"Error proxying Twitch: {e}")
        return jsonify({'error': 'Failed to proxy Twitch stream'}), 500

def proxy_direct_stream(url):
    """Proxy direct streams."""
    try:
        # For direct streams, we can redirect or proxy the content
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

   
 