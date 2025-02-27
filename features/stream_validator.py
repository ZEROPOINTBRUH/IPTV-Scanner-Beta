import requests
from m3u8 import M3U8
import time

def validate_stream(url, timeout=15):
    """
    Validate if a stream is active, accessible, and stable.
    Returns True if the stream is stable, False otherwise.
    """
    try:
        # Check if the URL is accessible
        response = requests.get(url, timeout=timeout)
        if response.status_code != 200:
            return False

        # Parse the M3U8 playlist (if it's an HLS stream)
        if url.endswith('.m3u8'):
            try:
                playlist = M3U8(response.text)
                if not playlist.segments:
                    return False  # No segments found, stream is invalid

                # Check the bitrate of the first segment
                first_segment = playlist.segments[0]
                if not first_segment.bitrate:
                    return False  # No bitrate information, stream may be unstable

                # Check if the stream is playable by fetching the first segment
                segment_url = first_segment.absolute_uri
                segment_response = requests.get(segment_url, timeout=timeout)
                if segment_response.status_code != 200:
                    return False  # First segment is not accessible

                # Optional: Check for buffering by timing the download of a segment
                start_time = time.time()
                segment_response = requests.get(segment_url, timeout=timeout, stream=True)
                for _ in segment_response.iter_content(chunk_size=1024):
                    break  # Download a small chunk to measure speed
                download_time = time.time() - start_time
                if download_time > 5:  # If it takes more than 5 seconds to download a chunk, the stream may be unstable
                    return False

                return True  # Stream is stable
            except:
                return False  # Failed to parse the playlist or fetch segments

        # For non-HLS streams, assume they are stable if accessible
        return True
    except:
        return False  # Stream is not accessible