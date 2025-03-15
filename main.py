import os
import json
import time
from threading import Thread
import asyncio
import aiohttp
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from features.channel_checker import check_channels
from features.stream_validator import validate_stream
import logging


# constants
M3U_URL = "https://iptv-org.github.io/iptv/index.m3u"
BATCH_SIZE = 10 # number of channels to process in each batch. 
FILES = {
        "streams": 'jsons/IPTV_STREAMS_FILE.json',
        "dead": 'jsons/DEAD_STREAMS_FILE.json',
        "invalid": 'jsons/INVALID_LINKS_FILE.json'
}
DIRECTORIES = ['webroot', 'webroot/js']

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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


#checks if link exists
async def check_link_exists(session, url, retries=3, delay=5):
    retryable_statuses = {500, 502, 503, 504, 429}  # temp  failures
    headers = {"User-Agent": "Mozilla/5.0"}  # avoid bot detection

    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, timeout=15, headers=headers)as response:
                if response.status in {200, 302}:
                    return True
                if response.status in retryable_statuses:
                    logging.warning(f"retryable error {response.status} for {url}, retryinh=g")
                else:
                    logging.warning(f"invalid link {url} /9status: {response.status})")
                    return False
        except Exception as e:
            logging.error(f"attempt {attempt} failed for {url}: {e}")
            await asyncio.sleep(delay) # slow down and avoid hitting servers to quickly

    return False # if 3 retries fail 

       
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
async def process_channels(channels, invalid_links, delay=10):
   
    valid_channels = []
    dead_channels = []
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(channels), BATCH_SIZE):
            batch = channels[i:i + BATCH_SIZE]
            tasks = [validate_channel(session, channel) for channel in batch if channel['url'] not in invalid_links]
            results = await asyncio.gather(*tasks)
            for channel, is_valid in results:
                if is_valid:
                    valid_channels.append(channel)
                else:
                    dead_channels.append(channel)
            # write to file write away so file is read for user once finsihed initial scan
            with open(FILES['streams'], 'w')as f:
                json.dump(valid_channels, f, indent=4) 

            with open(FILES['dead'], 'w') as f:
                json.dump(dead_channels, f, indent=4)

            await asyncio.sleep(delay) # play about with this to control proceesing speed
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


@app.route('/channels')
def get_channels():
    """Return a list of channels (15 at a time)."""
    try:
        with open(FILES['streams'], 'r') as f:
            channels = json.load(f)
            page = int(request.args.get('page', 1))
            sort_by = request.args.get('sort_by', 'name')
            group_by = request.args.get('group_by', 'group_title')
            channels.sort(key=lambda x: x.get(sort_by, ''))

        # group channels
        grouped_channels = {}
        for ch in channels:
            grouped_channels.setdefault(ch.get(group_by, 'Unknown'), []).append(ch)

        # flattening and paginating
        flattened_channels = [ch for group in grouped_channels.values() for ch in group]
        paginated_channels = flattened_channels[(page - 1) * 15: page * 15]
        return jsonify(paginated_channels)
    
    except Exception as e:
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



def run_flask():
    app.run(host='127.0.0.1', port=40006, use_reloader=False)

"""make sure flask server runs first and then do initial scan """
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

   
 