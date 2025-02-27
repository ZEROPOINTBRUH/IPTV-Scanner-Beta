import requests
from m3u8 import M3U8
from bs4 import BeautifulSoup

def get_playing_now(url):
    """Extract 'what's playing now' from a channel's webpage (if available)."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Example: Look for a meta tag or specific HTML element
            playing_now = soup.find('meta', attrs={'name': 'description'})
            if playing_now:
                return playing_now.get('content', 'Not available')
    except:
        pass
    return 'Not available'

def check_channels(m3u_url):
    """Check channels from the M3U playlist."""
    response = requests.get(m3u_url)
    if response.status_code != 200:
        raise Exception("Failed to fetch M3U playlist.")

    channels = []
    playlist = M3U8(response.text)
    for segment in playlist.segments:
        channel = {
            'name': segment.title,
            'url': segment.uri,
            'playing_now': get_playing_now(segment.uri)  # Add "what's playing now"
        }
        channels.append(channel)
    return channels