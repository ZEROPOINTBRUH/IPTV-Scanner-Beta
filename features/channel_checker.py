import requests
import logging

def parse_m3u_playlist(content):
    """
    Parse the M3U playlist content and extract channel information.
    Enhanced parsing with better error handling.
    """
    channels = []
    lines = content.splitlines()
    
    for i in range(len(lines)):
        if lines[i].startswith("#EXTINF:"):
            try:
                # Extract metadata from the #EXTINF line
                metadata = lines[i].strip()
                logging.debug(f"Parsing metadata: {metadata}")
                
                # More robust parsing with fallbacks
                channel_name = "Unknown"
                if 'tvg-name="' in metadata:
                    try:
                        channel_name = metadata.split('tvg-name="')[1].split('"')[0]
                    except IndexError:
                        pass
                elif ',' in metadata:
                    # Fallback to comma-separated name
                    channel_name = metadata.split(',')[-1].strip()
                
                tvg_id = ""
                if 'tvg-id="' in metadata:
                    try:
                        tvg_id = metadata.split('tvg-id="')[1].split('"')[0]
                    except IndexError:
                        pass
                
                tvg_logo = ""
                if 'tvg-logo="' in metadata:
                    try:
                        tvg_logo = metadata.split('tvg-logo="')[1].split('"')[0]
                    except IndexError:
                        pass
                
                group_title = "Ungrouped"
                if 'group-title="' in metadata:
                    try:
                        group_title = metadata.split('group-title="')[1].split('"')[0]
                    except IndexError:
                        pass

                # Extract the stream URL (next line after #EXTINF)
                if i + 1 < len(lines) and not lines[i + 1].startswith("#"):
                    stream_url = lines[i + 1].strip()
                    if stream_url:  # Only add if URL is not empty
                        channel = {
                            "name": channel_name or "Unknown",
                            "url": stream_url,
                            "tvg_id": tvg_id,
                            "tvg_logo": tvg_logo,
                            "group_title": group_title or "Ungrouped",
                            "playing_now": "Not available",
                            "status": "unknown"
                        }
                        channels.append(channel)
            except Exception as e:
                logging.error(f"Error parsing channel metadata at line {i}: {e}")
                continue
                
    logging.info(f"Parsed {len(channels)} channels from M3U playlist")
    return channels

def check_channels(m3u_url):
    """
    Fetch and parse the M3U playlist from the given URL.
    Enhanced with better headers and error handling.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/vnd.apple.mpegurl, application/x-mpegURL, application/vnd.apple.mpegurl.audio, application/octet-stream, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        logging.info(f"Fetching M3U playlist from: {m3u_url}")
        response = requests.get(m3u_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        content = response.text
        if not content.strip():
            logging.error("Received empty M3U playlist")
            return []
            
        logging.info(f"Successfully fetched M3U playlist ({len(content)} bytes)")
        return parse_m3u_playlist(content)
        
    except requests.exceptions.Timeout:
        logging.error(f"Timeout fetching M3U playlist from {m3u_url}")
        return []
    except requests.exceptions.ConnectionError:
        logging.error(f"Connection error fetching M3U playlist from {m3u_url}")
        return []
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error fetching M3U playlist: {e}")
        return []
    except Exception as e:
        logging.error(f"Error fetching M3U playlist: {e}")
        return []