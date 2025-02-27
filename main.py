import os
import json
import time
import threading
import queue
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from features.channel_checker import check_channels
from features.stream_validator import validate_stream

# Initialize Flask app
app = Flask(__name__, template_folder='webroot', static_folder='webroot')
CORS(app)  # Enable CORS for all routes

# Constants
M3U_URL = "https://iptv-org.github.io/iptv/index.m3u"
IPTV_STREAMS_FILE = "iptv_streams.json"
DEAD_STREAMS_FILE = "dead_streams.json"  # File to store dead streams
NUM_WORKERS = 5  # Number of worker threads for concurrent scanning

# Ensure the webroot folder exists
if not os.path.exists("webroot"):
    os.makedirs("webroot")
if not os.path.exists("webroot/css"):
    os.makedirs("webroot/css")
if not os.path.exists("webroot/js"):
    os.makedirs("webroot/js")

# Thread-safe queue for validated channels
valid_channels_queue = queue.Queue()
dead_channels_queue = queue.Queue()  # Queue for dead channels

def worker(channel_queue):
    """Worker thread to validate channels."""
    while not channel_queue.empty():
        channel = channel_queue.get()
        if validate_stream(channel['url']):
            valid_channels_queue.put(channel)
        else:
            dead_channels_queue.put(channel)  # Add dead channels to the queue
        channel_queue.task_done()

def sweep_channels():
    """Sweep through channels every 3 hours and update the JSON files."""
    while True:
        print("Starting channel sweep...")
        channels = check_channels(M3U_URL)

        # Create a thread-safe queue for channels
        channel_queue = queue.Queue()
        for channel in channels:
            channel_queue.put(channel)

        # Start worker threads
        threads = []
        for _ in range(NUM_WORKERS):
            t = threading.Thread(target=worker, args=(channel_queue,))
            t.start()
            threads.append(t)

        # Wait for all channels to be processed
        channel_queue.join()

        # Collect validated channels
        valid_channels = []
        while not valid_channels_queue.empty():
            valid_channels.append(valid_channels_queue.get())

        # Collect dead channels
        dead_channels = []
        while not dead_channels_queue.empty():
            dead_channels.append(dead_channels_queue.get())

        # Write the JSON files
        with open(IPTV_STREAMS_FILE, 'w') as f:
            json.dump(valid_channels, f, indent=4)
        with open(DEAD_STREAMS_FILE, 'w') as f:
            json.dump(dead_channels, f, indent=4)

        print(f"Channel sweep complete. {len(valid_channels)} valid channels found, {len(dead_channels)} dead channels tracked.")
        time.sleep(3 * 60 * 60)  # Sleep for 3 hours

@app.route('/')
def index():
    """Render the main TV guide page."""
    return render_template('index.html')

@app.route('/channels')
def get_channels():
    """Return a list of channels (15 at a time)."""
    with open(IPTV_STREAMS_FILE, 'r') as f:
        channels = json.load(f)
    page = int(request.args.get('page', 1))
    start = (page - 1) * 15
    end = start + 15
    return jsonify(channels[start:end])

@app.route('/search')
def search_channels():
    """Search for channels by name."""
    query = request.args.get('query', '').lower()
    with open(IPTV_STREAMS_FILE, 'r') as f:
        channels = json.load(f)
    results = [channel for channel in channels if query in channel['name'].lower()]
    return jsonify(results)

if __name__ == '__main__':
    # Start the channel sweep in a separate thread
    sweep_thread = threading.Thread(target=sweep_channels, daemon=True)
    sweep_thread.start()

    # Start the Flask web server
    app.run(host='0.0.0.0', port=40006)