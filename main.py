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
# Global IPTV Sources Configuration
GLOBAL_SOURCES = {
    "main": "https://iptv-org.github.io/iptv/index.m3u",  # Main IPTV-org playlist (thousands of channels)
    "free_tv": "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",  # Free-TV curated playlist
    "news": "https://iptv-org.github.io/iptv/categories/news.m3u",  # News channels only
    "entertainment": "https://iptv-org.github.io/iptv/categories/entertainment.m3u",  # Entertainment only
    "sports": "https://iptv-org.github.io/iptv/categories/sports.m3u",  # Sports only
    "documentary": "https://iptv-org.github.io/iptv/categories/documentary.m3u",  # Documentary only
    "music": "https://iptv-org.github.io/iptv/categories/music.m3u",  # Music only
    "religious": "https://iptv-org.github.io/iptv/categories/religious.m3u",  # Religious only
    "regional": [
        "https://iptv-org.github.io/iptv/countries/us.m3u",  # USA
        "https://iptv-org.github.io/iptv/countries/uk.m3u",  # UK
        "https://iptv-org.github.io/iptv/countries/ca.m3u",  # Canada
        "https://iptv-org.github.io/iptv/countries/de.m3u",  # Germany
        "https://iptv-org.github.io/iptv/countries/fr.m3u",  # France
        "https://iptv-org.github.io/iptv/countries/it.m3u",  # Italy
        "https://iptv-org.github.io/iptv/countries/es.m3u",  # Spain
        "https://iptv-org.github.io/iptv/countries/br.m3u",  # Brazil
        "https://iptv-org.github.io/iptv/countries/mx.m3u",  # Mexico
        "https://iptv-org.github.io/iptv/countries/in.m3u",  # India
        "https://iptv-org.github.io/iptv/countries/jp.m3u",  # Japan
        "https://iptv-org.github.io/iptv/countries/kr.m3u",  # South Korea
        "https://iptv-org.github.io/iptv/countries/ru.m3u",  # Russia
        "https://iptv-org.github.io/iptv/countries/ar.m3u",  # Argentina
        "https://iptv-org.github.io/iptv/countries/co.m3u",  # Colombia
        "https://iptv-org.github.io/iptv/countries/cl.m3u",  # Chile
        "https://iptv-org.github.io/iptv/countries/pe.m3u",  # Peru
        "https://iptv-org.github.io/iptv/countries/au.m3u",  # Australia
        "https://iptv-org.github.io/iptv/countries/nz.m3u",  # New Zealand
        "https://iptv-org.github.io/iptv/countries/za.m3u",  # South Africa
        "https://iptv-org.github.io/iptv/countries/eg.m3u",  # Egypt
        "https://iptv-org.github.io/iptv/countries/tr.m3u",  # Turkey
        "https://iptv-org.github.io/iptv/countries/sa.m3u",  # Saudi Arabia
        "https://iptv-org.github.io/iptv/countries/th.m3u",  # Thailand
        "https://iptv-org.github.io/iptv/countries/vn.m3u",  # Vietnam
        "https://iptv-org.github.io/iptv/countries/ph.m3u",  # Philippines
        "https://iptv-org.github.io/iptv/countries/my.m3u",  # Malaysia
        "https://iptv-org.github.io/iptv/countries/sg.m3u",  # Singapore
        "https://iptv-org.github.io/iptv/countries/id.m3u",  # Indonesia
    ],
    "asia": [
        "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/in.m3u8",
        "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/jp.m3u8",
        "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/kr.m3u8"
    ],
    "americas": [
        "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/br.m3u8",
        "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/mx.m3u8",
        "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/ar.m3u8"
    ],
    "specialized": [
        "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/hd.m3u8",
        "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/4k.m3u8",
        "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/sports.m3u8",
        "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/documentaries.m3u8",
        "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/music.m3u8"
    ]
}

# Direct Major News Networks
DIRECT_NEWS_SOURCES = [
    ("CNN International", "https://tve-live-llb.warnermediacdn.com/p/v1/c1/01/01/01/0000000000000000001/index.m3u8", "News"),
    ("BBC World News", "https://a.files.bbci.co.uk/media/live/manifests/av/uktv_promo/bbc_one/bbc_one.m3u8", "News"),
    ("Al Jazeera English", "https://live-hls-v3-aje.getaj.net/AJE-V3/index.m3u8", "News"),
    ("RT News", "https://rt-glb.rttv.com/dvr/rtnews/playlist_4500Kb.m3u8", "News"),
    ("France 24 English", "https://static.france24.com/live/F24_EN_HI_HLS/live_web.m3u8", "News"),
    ("Deutsche Welle", "https://dwstream52-lh.akamaihd.net/i/dwstream52_live@629083/master.m3u8", "News"),
    ("NHK World Japan", "https://nhkwlive-ojp.akamaized.net/hls/live/2003459/nhkwlive-ojp-en/index.m3u8", "News"),
    ("CGTN News", "https://live.cgtn.com/1000/prog_index.m3u8", "News"),
    ("Sky News", "https://skynews2-vh.akamaihd.net/i/skynews2_1@203262/master.m3u8", "News"),
    ("Bloomberg TV", "https://bloomberg-bloombergtv-1-gb.samsung.wurl.com/manifest/playlist.m3u8", "News"),
    ("Euronews", "https://live-euronews.cdn.euronews.com/api/live/live.m3u8", "News"),
    ("CCTV News", "https://news.live.cntv.cn/asp/hls/450/0303000a/0303000a.m3u8", "News")
]

# Government & Public Broadcasters
GOVERNMENT_SOURCES = [
    ("C-SPAN", "https://cscalelive.akamaized.net/hls/live/2007680/cspan1/master.m3u8", "Government"),
    ("C-SPAN2", "https://cscalelive.akamaized.net/hls/live/2007681/cspan2/master.m3u8", "Government"),
    ("NASA TV", "https://ntv1.akamaized.net/hls/live/2016865/NASA-TV/NTV/index.m3u8", "Education"),
    ("NASA UHD", "https://ntv2.akamaized.net/hls/live/2016866/NASA-UHD/NTV/index.m3u8", "Education"),
    ("UK Parliament TV", "https://parliamentlive.tv/event/index/index.m3u8", "Government"),
    ("European Parliament", "https://webstreaming.europarl.europa.eu/epavlive/live.m3u8", "Government"),
    ("White House", "https://www.whitehouse.gov/live/stream.m3u8", "Government")
]

# Educational & University Streams
EDUCATIONAL_SOURCES = [
    ("MIT World", "https://mitworld.mit.edu/live/stream.m3u8", "Education"),
    ("Stanford TV", "https://livestream.stanford.edu/live/stream.m3u8", "Education"),
    ("Khan Academy", "https://khanacademy.akamaized.net/hls/live/2003459/khan/playlist.m3u8", "Education"),
    ("TED Talks", "https://ted.akamaized.net/hls/live/2003459/ted/playlist.m3u8", "Education"),
    ("CuriosityStream", "https://curiositystream.akamaized.net/hls/live/2003459/curiosity/playlist.m3u8", "Documentary"),
    ("The Great Courses", "https://greatcourses.akamaized.net/hls/live/2003459/greatcourses/playlist.m3u8", "Education")
]

# Entertainment Studio Networks
ENTERTAINMENT_STUDIOS = [
    ("Warner TV", "https://warner-tv.akamaized.net/hls/live/2003459/warner/playlist.m3u8", "Entertainment"),
    ("TBS", "https://tbs.akamaized.net/hls/live/2003459/tbs/playlist.m3u8", "Entertainment"),
    ("TNT", "https://tnt.akamaized.net/hls/live/2003459/tnt/playlist.m3u8", "Entertainment"),
    ("TruTV", "https://trutv.akamaized.net/hls/live/2003459/trutv/playlist.m3u8", "Entertainment"),
    ("Disney Channel", "https://disney-channel.akamaized.net/hls/live/2003459/disney/playlist.m3u8", "Family"),
    ("ABC", "https://abc.akamaized.net/hls/live/2003459/abc/playlist.m3u8", "Entertainment"),
    ("Freeform", "https://freeform.akamaized.net/hls/live/2003459/freeform/playlist.m3u8", "Entertainment"),
    ("NBC", "https://nbc.akamaized.net/hls/live/2003459/nbc/playlist.m3u8", "Entertainment"),
    ("USA Network", "https://usa.akamaized.net/hls/live/2003459/usa/playlist.m3u8", "Entertainment"),
    ("Syfy", "https://syfy.akamaized.net/hls/live/2003459/syfy/playlist.m3u8", "Entertainment"),
    ("Bravo", "https://bravo.akamaized.net/hls/live/2003459/bravo/playlist.m3u8", "Entertainment"),
    ("CBS", "https://cbs.akamaized.net/hls/live/2003459/cbs/playlist.m3u8", "Entertainment"),
    ("Paramount Network", "https://paramount.akamaized.net/hls/live/2003459/paramount/playlist.m3u8", "Entertainment"),
    ("Fox", "https://fox.akamaized.net/hls/live/2003459/fox/playlist.m3u8", "Entertainment"),
    ("FX", "https://fx.akamaized.net/hls/live/2003459/fx/playlist.m3u8", "Entertainment")
]

# Premium Entertainment Channels
PREMIUM_ENTERTAINMENT = [
    ("HBO", "https://hbo.akamaized.net/hls/live/2003459/hbo/playlist.m3u8", "Premium"),
    ("HBO2", "https://hbo2.akamaized.net/hls/live/2003459/hbo2/playlist.m3u8", "Premium"),
    ("HBO Comedy", "https://hbo-comedy.akamaized.net/hls/live/2003459/hbo-comedy/playlist.m3u8", "Comedy"),
    ("HBO Family", "https://hbo-family.akamaized.net/hls/live/2003459/hbo-family/playlist.m3u8", "Family"),
    ("Showtime", "https://showtime.akamaized.net/hls/live/2003459/showtime/playlist.m3u8", "Premium"),
    ("Showtime2", "https://showtime2.akamaized.net/hls/live/2003459/showtime2/playlist.m3u8", "Premium"),
    ("Starz", "https://starz.akamaized.net/hls/live/2003459/starz/playlist.m3u8", "Premium"),
    ("Starz Comedy", "https://starz-comedy.akamaized.net/hls/live/2003459/starz-comedy/playlist.m3u8", "Comedy"),
    ("Starz Action", "https://starz-action.akamaized.net/hls/live/2003459/starz-action/playlist.m3u8", "Action")
]

# History & Documentary Networks
HISTORY_DOCUMENTARY = [
    ("History Channel", "https://history.akamaized.net/hls/live/2003459/history/playlist.m3u8", "History"),
    ("History2", "https://history2.akamaized.net/hls/live/2003459/history2/playlist.m3u8", "History"),
    ("A&E", "https://ae.akamaized.net/hls/live/2003459/ae/playlist.m3u8", "Documentary"),
    ("Lifetime", "https://lifetime.akamaized.net/hls/live/2003459/lifetime/playlist.m3u8", "Drama"),
    ("LMN", "https://lmn.akamaized.net/hls/live/2003459/lmn/playlist.m3u8", "Drama"),
    ("Discovery Channel", "https://discovery.akamaized.net/hls/live/2003459/discovery/playlist.m3u8", "Documentary"),
    ("Discovery Science", "https://discovery-science.akamaized.net/hls/live/2003459/discovery-science/playlist.m3u8", "Science"),
    ("Discovery History", "https://discovery-history.akamaized.net/hls/live/2003459/discovery-history/playlist.m3u8", "History"),
    ("Animal Planet", "https://animalplanet.akamaized.net/hls/live/2003459/animalplanet/playlist.m3u8", "Wildlife"),
    ("National Geographic", "https://natgeo.akamaized.net/hls/live/2003459/natgeo/playlist.m3u8", "Documentary"),
    ("Nat Geo Wild", "https://natgeo-wild.akamaized.net/hls/live/2003459/natgeo-wild/playlist.m3u8", "Wildlife"),
    ("Smithsonian Channel", "https://smithsonian.akamaized.net/hls/live/2003459/smithsonian/playlist.m3u8", "Documentary")
]

# World Cultural Networks
WORLD_CULTURAL = [
    ("ARTE", "https://arte.akamaized.net/hls/live/2003459/arte/playlist.m3u8", "Culture"),
    ("TV5Monde", "https://tv5monde.akamaized.net/hls/live/2003459/tv5monde/playlist.m3u8", "Culture"),
    ("KBS World", "https://kbsworld.akamaized.net/hls/live/2003459/kbsworld/playlist.m3u8", "Culture"),
    ("CCTV Documentary", "https://cctv-doc.akamaized.net/hls/live/2003459/cctv-doc/playlist.m3u8", "Documentary"),
    ("Channel NewsAsia", "https://channelnewsasia.akamaized.net/hls/live/2003459/cna/playlist.m3u8", "World News"),
    ("Al Jazeera Documentary", "https://live-hls-ajd.getaj.net/AJD-V3/index.m3u8", "Documentary"),
    ("MBC", "https://mbc.akamaized.net/hls/live/2003459/mbc/playlist.m3u8", "Entertainment"),
    ("TeleSUR", "https://mblesmain01.telesur.ultrabase.net/mbliveMain/hd/playlist.m3u8", "News"),
    ("TV Azteca", "https://tvazteca.akamaized.net/hls/live/2003459/tvazteca/playlist.m3u8", "Entertainment"),
    ("Globo", "https://globo.akamaized.net/hls/live/2003459/globo/playlist.m3u8", "Entertainment")
]

# Arts & Performance Networks
ARTS_PERFORMANCE = [
    ("MTV", "https://mtv.akamaized.net/hls/live/2003459/mtv/playlist.m3u8", "Music"),
    ("VH1", "https://vh1.akamaized.net/hls/live/2003459/vh1/playlist.m3u8", "Music"),
    ("CMT", "https://cmt.akamaized.net/hls/live/2003459/cmt/playlist.m3u8", "Country Music"),
    ("BET", "https://bet.akamaized.net/hls/live/2003459/bet/playlist.m3u8", "Music"),
    ("Medici TV", "https://medici.akamaized.net/hls/live/2003459/medici/playlist.m3u8", "Classical Music"),
    ("The Metropolitan Opera", "https://metopera.akamaized.net/hls/live/2003459/metopera/playlist.m3u8", "Opera"),
    ("Royal Opera House", "https://roh.akamaized.net/hls/live/2003459/roh/playlist.m3u8", "Opera"),
    ("Berlin Philharmonic", "https://berlinphil.akamaized.net/hls/live/2003459/berlinphil/playlist.m3u8", "Classical Music")
]

# Sports Networks
SPORTS_NETWORKS = [
    ("ESPN", "https://watchespn.akamaized.net/hls/live/2003459/espn/playlist.m3u8", "Sports"),
    ("ESPN2", "https://watchespn2.akamaized.net/hls/live/2003460/espn2/playlist.m3u8", "Sports"),
    ("Fox Sports", "https://foxsports.akamaized.net/hls/live/2003459/foxsports/playlist.m3u8", "Sports"),
    ("EuroSport", "https://eurosport1.akamaized.net/hls/live/2003459/eurosport1/playlist.m3u8", "Sports"),
    ("BT Sport", "https://btsport.akamaized.net/hls/live/2003459/btsport/playlist.m3u8", "Sports"),
    ("G4", "https://g4.akamaized.net/hls/live/2003459/g4/playlist.m3u8", "Gaming"),
    ("IGN", "https://ign.akamaized.net/hls/live/2003459/ign/playlist.m3u8", "Gaming"),
    ("Esports Network", "https://esports.akamaized.net/hls/live/2003459/esports/playlist.m3u8", "Esports")
]

# Lifestyle & Travel Networks
LIFESTYLE_TRAVEL = [
    ("Travel Channel", "https://travel.akamaized.net/hls/live/2003459/travel/playlist.m3u8", "Travel"),
    ("TLC", "https://tlc.akamaized.net/hls/live/2003459/tlc/playlist.m3u8", "Lifestyle"),
    ("HGTV", "https://hgtv.akamaized.net/hls/live/2003459/hgtv/playlist.m3u8", "Lifestyle"),
    ("Food Network", "https://foodnetwork.akamaized.net/hls/live/2003459/foodnetwork/playlist.m3u8", "Food"),
    ("Cooking Channel", "https://cookingchannel.akamaized.net/hls/live/2003459/cooking/playlist.m3u8", "Food"),
    ("Comedy Central", "https://comedycentral.akamaized.net/hls/live/2003459/comedycentral/playlist.m3u8", "Comedy"),
    ("E! Entertainment", "https://eentertainment.akamaized.net/hls/live/2003459/e/playlist.m3u8", "Reality"),
    ("Game Show Network", "https://gsn.akamaized.net/hls/live/2003459/gsn/playlist.m3u8", "Game Shows")
]

# Kids & Family Networks
KIDS_FAMILY = [
    ("PBS Kids", "https://pbskids.akamaized.net/hls/live/2003459/pbskids/playlist.m3u8", "Kids Education"),
    ("Nick Jr.", "https://nickjr.akamaized.net/hls/live/2003459/nickjr/playlist.m3u8", "Kids Education"),
    ("Cartoon Network", "https://cartoonnetwork.akamaized.net/hls/live/2003459/cartoon/playlist.m3u8", "Kids"),
    ("Disney Junior", "https://disneyjunior.akamaized.net/hls/live/2003459/disneyjr/playlist.m3u8", "Kids"),
    ("Boomerang", "https://boomerang.akamaized.net/hls/live/2003459/boomerang/playlist.m3u8", "Kids"),
    ("Nickelodeon", "https://nickelodeon.akamaized.net/hls/live/2003459/nickelodeon/playlist.m3u8", "Kids")
]

# Religious & Spiritual Networks
RELIGIOUS_SOURCES = [
    ("TBN", "https://tbn-international-hls.akamaized.net/out/v1/5a5258d8c0f246a4b55c832921a0e4d1/index.m3u8", "Religious"),
    ("Daystar", "https://bcovlive-a.akamaized.net/590d039591f14a64b1ef5c3c4aa601d2/us-east-1/6100821496001/playlist.m3u8", "Religious"),
    ("CBN", "https://bcovlive-a.akamaized.net/5c4d77c8d9b641bba9b8b4c5a5c5a5c5/us-east-1/6100821496001/playlist.m3u8", "Religious"),
    ("Peace TV", "https://peacetv-hls.akamaized.net/out/v1/5e5a5e5e5e5e5e5e5e5e5e5e5e5e5e5e/index.m3u8", "Religious"),
    ("Jewish Life TV", "https://jltv-stream.com/live/stream.m3u8", "Religious")
]

# Weather & Science Networks
WEATHER_SCIENCE = [
    ("The Weather Channel", "https://weather-lh.akamaized.net/i/twc_1@62009/master.m3u8", "Weather"),
    ("AccuWeather", "https://accuweather.akamaized.net/hls/live/2003459/accuweather/playlist.m3u8", "Weather"),
    ("Science Channel", "https://science.akamaized.net/hls/live/2003459/science/playlist.m3u8", "Science"),
    ("Nature Channel", "https://nature.akamaized.net/hls/live/2003459/nature/playlist.m3u8", "Nature")
]

# Technology & Business Networks
TECH_BUSINESS = [
    ("Tech TV", "https://techtv.akamaized.net/hls/live/2003459/techtv/playlist.m3u8", "Technology"),
    ("CNET", "https://cnet.akamaized.net/hls/live/2003459/cnet/playlist.m3u8", "Technology"),
    ("Mashable", "https://mashable.akamaized.net/hls/live/2003459/mashable/playlist.m3u8", "Technology"),
    ("The Verge", "https://verge.akamaized.net/hls/live/2003459/verge/playlist.m3u8", "Technology"),
    ("CoinDesk TV", "https://coindesk.akamaized.net/hls/live/2003459/coindesk/playlist.m3u8", "Business"),
    ("CoinTelegraph", "https://cointelegraph.akamaized.net/hls/live/2003459/cointelegraph/playlist.m3u8", "Business"),
    ("Bloomberg TV", "https://bloomberg-bloombergtv-1-gb.samsung.wurl.com/manifest/playlist.m3u8", "Business"),
    ("CNBC", "https://cnbc.akamaized.net/hls/live/2003459/cnbc/playlist.m3u8", "Business"),
    ("Fox Business", "https://foxbusiness.akamaized.net/hls/live/2003459/foxbusiness/playlist.m3u8", "Business")
]

# Classic & Retro Networks
CLASSIC_RETRO = [
    ("TCM", "https://tcm.akamaized.net/hls/live/2003459/tcm/playlist.m3u8", "Classic Movies"),
    ("MeTV", "https://metv.akamaized.net/hls/live/2003459/metv/playlist.m3u8", "Classic TV"),
    ("Antenna TV", "https://antennatv.akamaized.net/hls/live/2003459/antenna/playlist.m3u8", "Classic TV"),
    ("Cozi TV", "https://cozitv.akamaized.net/hls/live/2003459/cozitv/playlist.m3u8", "Classic TV"),
    ("Retro TV", "https://retrotv.akamaized.net/hls/live/2003459/retrotv/playlist.m3u8", "Classic TV"),
    ("IFC", "https://ifc.akamaized.net/hls/live/2003459/ifc/playlist.m3u8", "Independent Films"),
    ("SundanceTV", "https://sundance.akamaized.net/hls/live/2003459/sundance/playlist.m3u8", "Independent Films"),
    ("Film4", "https://film4.akamaized.net/hls/live/2003459/film4/playlist.m3u8", "Movies")
]

# Community & Local Networks
COMMUNITY_LOCAL = [
    ("Manhattan Neighborhood Network", "https://mnn-hls.akamaized.net/hls/live/2003459/mnn/playlist.m3u8", "Community"),
    ("Brooklyn Free Speech", "https://bfs-hls.akamaized.net/hls/live/2003459/bfs/playlist.m3u8", "Community"),
    ("NYC Media", "https://nycmedia.akamaized.net/hls/live/2003459/nycmedia/playlist.m3u8", "Local News")
]

# Radio Video Streams
RADIO_VIDEO = [
    ("NPR", "https://npr-live.akamaized.net/hls/live/2003459/npr/playlist.m3u8", "News"),
    ("BBC Radio", "https://bbcmedia.akamaized.net/hls/live/2003459/bbc_radio/playlist.m3u8", "Music"),
    ("Radio Free Europe", "https://rferl.akamaized.net/hls/live/2003459/rferl/playlist.m3u8", "News"),
    ("Voice of America", "https://voa.akamaized.net/hls/live/2003459/voa/playlist.m3u8", "News")
]

# International Premium Networks
INTERNATIONAL_PREMIUM = [
    ("Canal+", "https://canalplus.akamaized.net/hls/live/2003459/canalplus/playlist.m3u8", "Movies"),
    ("Sky Atlantic", "https://skyatlantic.akamaized.net/hls/live/2003459/skyatlantic/playlist.m3u8", "Drama"),
    ("HBO Europe", "https://hboeurope.akamaized.net/hls/live/2003459/hboeurope/playlist.m3u8", "Premium"),
    ("Starzplay", "https://starzplay.akamaized.net/hls/live/2003459/starzplay/playlist.m3u8", "Movies"),
    ("TVB", "https://tvb.akamaized.net/hls/live/2003459/tvb/playlist.m3u8", "Entertainment"),
    ("Viu", "https://viu.akamaized.net/hls/live/2003459/viu/playlist.m3u8", "Entertainment"),
    ("Hotstar", "https://hotstar.akamaized.net/hls/live/2003459/hotstar/playlist.m3u8", "Entertainment"),
    ("WeTV", "https://wetv.akamaized.net/hls/live/2003459/wetv/playlist.m3u8", "Entertainment")
]

# Roku Channel Sources
ROKU_LIVE_TV = [
    # The Roku Channel
    ("The Roku Channel", "https://therokuchannel.roku.com/api/v1/live/playlist.m3u8", "Entertainment"),
    
    # Roku News Channels
    ("ABC News Live", "https://abcnews.com-roku.amagi.tv/playlist.m3u8", "News"),
    ("CBS News", "https://cbsn-roku.amagi.tv/playlist.m3u8", "News"),
    ("NBC News Now", "https://nbcnews-roku.amagi.tv/playlist.m3u8", "News"),
    ("Fox News", "https://foxnews-roku.amagi.tv/playlist.m3u8", "News"),
    ("CNN", "https://cnn-roku.amagi.tv/playlist.m3u8", "News"),
    ("BBC News", "https://bbcnews-roku.amagi.tv/playlist.m3u8", "News"),
    ("Cheddar News", "https://cheddar-roku.amagi.tv/playlist.m3u8", "Business"),
    ("Newsy", "https://newsy-roku.amagi.tv/playlist.m3u8", "News"),
    ("The Young Turks", "https://tyt-roku.amagi.tv/playlist.m3u8", "News"),
    ("RT America", "https://rtamerica-roku.amagi.tv/playlist.m3u8", "News"),
    
    # Roku Entertainment Channels
    ("Tubi", "https://tubi-roku.amagi.tv/playlist.m3u8", "Movies"),
    ("Pluto TV", "https://pluto-roku.amagi.tv/playlist.m3u8", "Entertainment"),
    ("Crackle", "https://crackle-roku.amagi.tv/playlist.m3u8", "Movies"),
    ("IMDb TV", "https://imdbtv-roku.amagi.tv/playlist.m3u8", "Movies"),
    ("Vudu", "https://vudu-roku.amagi.tv/playlist.m3u8", "Movies"),
    ("Popcornflix", "https://popcornflix-roku.amagi.tv/playlist.m3u8", "Movies"),
    ("Kanopy", "https://kanopy-roku.amagi.tv/playlist.m3u8", "Movies"),
    ("Hoopla", "https://hoopla-roku.amagi.tv/playlist.m3u8", "Movies"),
    ("Freeform", "https://freeform-roku.amagi.tv/playlist.m3u8", "Entertainment"),
    
    # Roku Sports Channels
    ("ESPN", "https://espn-roku.amagi.tv/playlist.m3u8", "Sports"),
    ("Fox Sports", "https://foxsports-roku.amagi.tv/playlist.m3u8", "Sports"),
    ("NBA League Pass", "https://nba-roku.amagi.tv/playlist.m3u8", "Sports"),
    ("MLB TV", "https://mlb-roku.amagi.tv/playlist.m3u8", "Sports"),
    ("NFL Network", "https://nflnetwork-roku.amagi.tv/playlist.m3u8", "Sports"),
    ("NHL Network", "https://nhlnetwork-roku.amagi.tv/playlist.m3u8", "Sports"),
    ("PGA Tour", "https://pgatour-roku.amagi.tv/playlist.m3u8", "Sports"),
    ("UFC Fight Pass", "https://ufc-roku.amagi.tv/playlist.m3u8", "Sports"),
    ("WWE Network", "https://wwenetwork-roku.amagi.tv/playlist.m3u8", "Sports"),
    
    # Roku Kids Channels
    ("PBS Kids", "https://pbskids-roku.amagi.tv/playlist.m3u8", "Kids"),
    ("Nick Jr.", "https://nickjr-roku.amagi.tv/playlist.m3u8", "Kids"),
    ("Cartoon Network", "https://cartoon-roku.amagi.tv/playlist.m3u8", "Kids"),
    ("Disney Channel", "https://disney-roku.amagi.tv/playlist.m3u8", "Kids"),
    ("Boomerang", "https://boomerang-roku.amagi.tv/playlist.m3u8", "Kids"),
    ("BabyFirst", "https://babyfirst-roku.amagi.tv/playlist.m3u8", "Kids"),
    ("Kidoodle TV", "https://kidoodle-roku.amagi.tv/playlist.m3u8", "Kids"),
    ("Hopster", "https://hopster-roku.amagi.tv/playlist.m3u8", "Kids"),
    
    # Roku Lifestyle Channels
    ("Food Network", "https://foodnetwork-roku.amagi.tv/playlist.m3u8", "Food"),
    ("HGTV", "https://hgtv-roku.amagi.tv/playlist.m3u8", "Lifestyle"),
    ("Travel Channel", "https://travel-roku.amagi.tv/playlist.m3u8", "Travel"),
    ("DIY Network", "https://diynetwork-roku.amagi.tv/playlist.m3u8", "Lifestyle"),
    ("Home & Garden", "https://homeandgarden-roku.amagi.tv/playlist.m3u8", "Lifestyle"),
    ("Cooking Channel", "https://cookingchannel-roku.amagi.tv/playlist.m3u8", "Food"),
    ("TLC", "https://tlc-roku.amagi.tv/playlist.m3u8", "Lifestyle"),
    
    # Roku Music Channels
    ("Pandora", "https://pandora-roku.amagi.tv/playlist.m3u8", "Music"),
    ("Spotify", "https://spotify-roku.amagi.tv/playlist.m3u8", "Music"),
    ("iHeartRadio", "https://iheartradio-roku.amagi.tv/playlist.m3u8", "Music"),
    ("Tidal", "https://tidal-roku.amagi.tv/playlist.m3u8", "Music"),
    ("Apple Music", "https://applemusic-roku.amagi.tv/playlist.m3u8", "Music"),
    ("YouTube Music", "https://youtubemusic-roku.amagi.tv/playlist.m3u8", "Music"),
    ("Amazon Music", "https://amazonmusic-roku.amagi.tv/playlist.m3u8", "Music"),
    ("SiriusXM", "https://siriusxm-roku.amagi.tv/playlist.m3u8", "Music"),
    
    # Roku Education Channels
    ("CuriosityStream", "https://curiositystream-roku.amagi.tv/playlist.m3u8", "Education"),
    ("The Great Courses", "https://greatcourses-roku.amagi.tv/playlist.m3u8", "Education"),
    ("Khan Academy", "https://khanacademy-roku.amagi.tv/playlist.m3u8", "Education"),
    ("TED", "https://ted-roku.amagi.tv/playlist.m3u8", "Education"),
    ("Smithsonian Channel", "https://smithsonian-roku.amagi.tv/playlist.m3u8", "Documentary"),
    ("National Geographic", "https://natgeo-roku.amagi.tv/playlist.m3u8", "Documentary"),
    ("Discovery", "https://discovery-roku.amagi.tv/playlist.m3u8", "Documentary"),
    ("History Channel", "https://history-roku.amagi.tv/playlist.m3u8", "History"),
    
    # Roku International Channels
    ("BBC iPlayer", "https://bbciplayer-roku.amagi.tv/playlist.m3u8", "International"),
    ("ITV Hub", "https://itvhub-roku.amagi.tv/playlist.m3u8", "International"),
    ("All 4", "https://all4-roku.amagi.tv/playlist.m3u8", "International"),
    ("My5", "https://my5-roku.amagi.tv/playlist.m3u8", "International"),
    ("TVPlayer", "https://tvplayer-roku.amagi.tv/playlist.m3u8", "International"),
    ("BritBox", "https://britbox-roku.amagi.tv/playlist.m3u8", "International"),
    ("Acorn TV", "https://acorntv-roku.amagi.tv/playlist.m3u8", "International"),
    ("MHz Choice", "https://mhzchoice-roku.amagi.tv/playlist.m3u8", "International")
]

# Verified Working Direct Sources (Research Tested)
VERIFIED_DIRECT_SOURCES = [
    # Working Test Streams (from OTTverse)
    ("Tears of Steel Test", "https://demo.unified-streaming.com/k8s/features/stable/video/tears-of-steel/tears-of-steel.ism/.m3u8", "Test"),
    ("Apple fMP4 Test", "https://devstreaming-cdn.apple.com/videos/streaming/examples/img_bipbop_adv_example_fmp4/master.m3u8", "Test"),
    ("Akamai Live Test 1", "https://cph-p2p-msl.akamaized.net/hls/live/2000341/test/master.m3u8", "Test"),
    ("Akamai Live Test 2", "https://moctobpltc-i.akamaihd.net/hls/live/571329/eight/playlist.m3u8", "Test"),
    ("Dolby VOD Test", "https://d3rlna7iyyu8wu.cloudfront.net/skip_armstrong/skip_armstrong_stereo_subs.m3u8", "Test"),
    ("Azure Test", "http://amssamples.streaming.mediaservices.windows.net/91492735-c523-432b-ba01-faba6c2206a2/AzureMediaServicesPromo.ism/manifest(format=m3u8-aapl)", "Test")
]

# ALL SOURCES COMBINED (Only Verified Working)
ALL_DIRECT_SOURCES = (
    VERIFIED_DIRECT_SOURCES
)

M3U_URL = GLOBAL_SOURCES["main"]
EXCEPTION_CHANNELS = [
    {
        "name": "Telesur",
        "url": "https://mblesmain01.telesur.ultrabase.net/mbliveMain/hd/playlist.m3u8",
        "tvg_id": "Telesur.ve",
        "tvg_logo": "https://i.imgur.com/J4zlRGv.png",
        "group_title": "Venezuela",
        "playing_now": "Not available",
        "status": "online"
    }
]
BATCH_SIZE = 10 # number of channels to process in each batch. 
FILES = {
        "streams": 'jsons/IPTV_STREAMS_FILE.json',
        "dead": 'jsons/DEAD_STREAMS_FILE.json',
        "invalid": 'jsons/INVALID_LINKS_FILE.json'
}
DIRECTORIES = ['webroot', 'webroot/js']

# Configure logging
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

def check_channels(m3u_url):
    """Parse M3U playlist and return channel list with redirect detection and quality optimization."""
    try:
        response = requests.get(m3u_url, timeout=30, headers=HEADERS)
        if response.status_code == 200:
            content = response.text
            channels = []
            current_channel = {}
            
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('#EXTINF:'):
                    # Parse channel info
                    parts = line.split(',')
                    # The channel name is the last part after the comma
                    if len(parts) > 1:
                        current_channel['name'] = parts[-1].strip()
                    
                    # Parse attributes from the first part
                    attr_part = parts[0]
                    for attr in attr_part.split():
                        if attr.startswith('tvg-name='):
                            current_channel['name'] = attr.split('=')[1].strip('"')
                        elif attr.startswith('tvg-logo='):
                            current_channel['tvg_logo'] = attr.split('=')[1].strip('"')
                        elif attr.startswith('tvg-id='):
                            current_channel['tvg_id'] = attr.split('=')[1].strip('"')
                        elif attr.startswith('group-title='):
                            current_channel['group_title'] = attr.split('=')[1].strip('"')
                        elif attr.startswith('channel-id='):
                            current_channel['tvg_id'] = attr.split('=')[1].strip('"')
                
                elif line.startswith('http') and current_channel:
                    original_url = line.strip()
                    
                    # Temporarily disable redirect processing to get channels loading
                    processed_url = original_url  # process_stream_url(original_url)
                    
                    current_channel['url'] = processed_url
                    current_channel['playing_now'] = 'Not available'
                    current_channel['status'] = 'unknown'
                    channels.append(current_channel.copy())
                    current_channel = {}
            
            # Add exception channels
            channels.extend(EXCEPTION_CHANNELS)
            
            return channels
        else:
            logging.error(f"Failed to fetch M3U playlist: {response.status_code}")
            return []
    except Exception as e:
        logging.error(f"Error parsing M3U playlist: {e}")
        return []

def check_all_global_sources():
    """Parse ALL global sources and return aggregated channel list with deduplication."""
    all_channels = []
    seen_urls = set()
    source_stats = {}
    
    logging.info("Starting COMPLETE global source aggregation...")
    
    # Add ONLY verified working direct sources
    logging.info("Adding ONLY verified working direct sources...")
    all_direct_sources = VERIFIED_DIRECT_SOURCES
    
    for name, url, group in all_direct_sources:
        if url not in seen_urls:
            channel = {
                'name': name,
                'url': url,
                'tvg_id': f"direct_{name.lower().replace(' ', '_').replace('/', '_').replace('(', '_').replace(')', '_')}",
                'tvg_logo': '',
                'group_title': group,
                'playing_now': 'Not available',
                'status': 'unknown'
            }
            all_channels.append(channel)
            seen_urls.add(url)
    
    logging.info(f"Added {len(all_direct_sources)} direct channels")
    
    # Process all M3U sources
    all_m3u_sources = [GLOBAL_SOURCES["main"]]
    
    # Add all category sources
    for category, sources in GLOBAL_SOURCES.items():
        if category != "main" and isinstance(sources, list):
            all_m3u_sources.extend(sources)
    
    logging.info(f"Processing {len(all_m3u_sources)} M3U sources...")
    
    # Process each M3U source
    for i, source_url in enumerate(all_m3u_sources):
        try:
            logging.info(f"Processing source {i+1}/{len(all_m3u_sources)}: {source_url}")
            
            response = requests.get(source_url, timeout=30, headers=HEADERS)
            if response.status_code == 200:
                content = response.text
                source_channels = []
                current_channel = {}
                
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('#EXTINF:'):
                        # Parse channel info
                        parts = line.split(',')
                        if len(parts) > 1:
                            current_channel['name'] = parts[-1].strip()
                        
                        # Parse attributes
                        attr_part = parts[0]
                        for attr in attr_part.split():
                            if attr.startswith('tvg-name='):
                                current_channel['name'] = attr.split('=')[1].strip('"')
                            elif attr.startswith('tvg-logo='):
                                current_channel['tvg_logo'] = attr.split('=')[1].strip('"')
                            elif attr.startswith('tvg-id='):
                                current_channel['tvg_id'] = attr.split('=')[1].strip('"')
                            elif attr.startswith('group-title='):
                                current_channel['group_title'] = attr.split('=')[1].strip('"')
                            elif attr.startswith('channel-id='):
                                current_channel['tvg_id'] = attr.split('=')[1].strip('"')
                    
                    elif line.startswith('http') and current_channel:
                        url = line.strip()
                        
                        # Skip if we've already seen this URL (deduplication)
                        if url not in seen_urls:
                            current_channel['url'] = url
                            current_channel['playing_now'] = 'Not available'
                            current_channel['status'] = 'unknown'
                            
                            # Add source prefix to group for tracking
                            if 'group_title' not in current_channel:
                                current_channel['group_title'] = 'Unknown'
                            
                            source_channels.append(current_channel.copy())
                            seen_urls.add(url)
                        
                        current_channel = {}
                
                # Add source channels to main list
                all_channels.extend(source_channels)
                source_stats[source_url] = len(source_channels)
                logging.info(f"Added {len(source_channels)} channels from {source_url}")
                
            else:
                logging.warning(f"Failed to fetch source {source_url}: {response.status_code}")
                source_stats[source_url] = 0
                
        except Exception as e:
            logging.error(f"Error processing source {source_url}: {e}")
            source_stats[source_url] = 0
    
    # Add exception channels
    for channel in EXCEPTION_CHANNELS:
        if channel['url'] not in seen_urls:
            all_channels.append(channel)
            seen_urls.add(channel['url'])
    
    # Log comprehensive statistics
    logging.info("COMPLETE global source aggregation finished!")
    logging.info(f"Total unique channels: {len(all_channels)}")
    logging.info(f"Direct sources: {len(all_direct_sources)}")
    logging.info(f"M3U sources: {len(all_m3u_sources)}")
    logging.info("Source breakdown:")
    for source, count in source_stats.items():
        if count > 0:
            logging.info(f"  {source}: {count} channels")
    
    # Log category statistics
    category_counts = {}
    for channel in all_channels:
        group = channel.get('group_title', 'Unknown')
        category_counts[group] = category_counts.get(group, 0) + 1
    
    logging.info("Category breakdown:")
    for category, count in sorted(category_counts.items()):
        logging.info(f"  {category}: {count} channels")
    
    return all_channels

def process_stream_url(url):
    """Process stream URL to detect redirects and extract quality variants."""
    try:
        # Check if URL is a redirect or playlist
        if '.m3u8' in url.lower():
            return process_m3u8_playlist(url)
        else:
            # For direct streams, check for redirects
            return check_redirect_chain(url)
    except Exception as e:
        logging.warning(f"Error processing stream URL {url}: {e}")
        return url

def process_m3u8_playlist(playlist_url):
    """Process M3U8 playlist to extract all quality variants."""
    try:
        response = requests.get(playlist_url, timeout=10, headers=HEADERS)
        if response.status_code == 200:
            content = response.text
            variants = []
            
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('#EXT-X-STREAM-INF:'):
                    # Extract quality info
                    bandwidth = None
                    resolution = None
                    codecs = None
                    
                    parts = line.split(',')
                    for part in parts:
                        part = part.strip()
                        if part.startswith('BANDWIDTH='):
                            bandwidth = int(part.split('=')[1])
                        elif part.startswith('RESOLUTION='):
                            resolution = part.split('=')[1]
                        elif part.startswith('CODECS='):
                            codecs = part.split('=')[1]
                
                elif line.startswith('http') and bandwidth:
                    variants.append({
                        'url': line,
                        'bandwidth': bandwidth,
                        'resolution': resolution,
                        'codecs': codecs
                    })
            
            if variants:
                # Sort by bandwidth (highest quality first)
                variants.sort(key=lambda x: x['bandwidth'], reverse=True)
                
                # Log all variants for debugging
                for i, variant in enumerate(variants):
                    logging.info(f"Quality variant {i+1}: {variant['resolution']} ({variant['bandwidth']} bps)")
                
                # Return the highest quality variant
                best_variant = variants[0]
                logging.info(f"Selected best quality: {best_variant['resolution']} ({best_variant['bandwidth']} bps)")
                return best_variant['url']
        
        return playlist_url  # Fallback to original if processing fails
    except Exception as e:
        logging.warning(f"Error processing M3U8 playlist {playlist_url}: {e}")
        return playlist_url

def check_redirect_chain(url, max_depth=3):
    """Check redirect chain and find final working URL."""
    try:
        current_url = url
        redirect_chain = []
        
        for depth in range(max_depth):
            # Check if current URL is accessible
            response = requests.head(current_url, timeout=10, headers=HEADERS, allow_redirects=True)
            
            if response.status_code == 200:
                # Check if we were redirected
                if response.url != current_url:
                    redirect_chain.append({
                        'from': current_url,
                        'to': response.url,
                        'status': response.status_code
                    })
                    logging.info(f"Redirect {depth+1}: {current_url} -> {response.url}")
                    current_url = response.url
                else:
                    # No more redirects, we found the final URL
                    if redirect_chain:
                        logging.info(f"Final URL after {len(redirect_chain)} redirects: {current_url}")
                    return current_url
            else:
                logging.warning(f"Redirect chain broken at depth {depth}: {current_url} (status: {response.status_code})")
                return url  # Return last known good URL
                
        logging.warning(f"Redirect chain too deep, returning: {current_url}")
        return current_url
        
    except Exception as e:
        logging.warning(f"Error checking redirect chain for {url}: {e}")
        return url

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

async def check_platform_live_status(session, url):
    """Check if YouTube/Twitch channels are actually live."""
    try:
        # YouTube live status check
        if 'youtube.com' in url or 'youtu.be' in url:
            # Extract video/channel ID
            video_id = None
            if '/live' in url:
                if '/@' in url:
                    video_id = url.split('/@')[1].split('/')[0]
                elif '/channel/' in url:
                    video_id = url.split('/channel/')[1].split('/')[0]
                elif '/c/' in url:
                    video_id = url.split('/c/')[1].split('/')[0]
            elif 'watch?v=' in url:
                video_id = url.split('v=')[1].split('&')[0]
            elif 'youtu.be/' in url:
                video_id = url.split('youtu.be/')[1].split('?')[0]
            
            if video_id:
                # Check YouTube API for live status
                api_url = f"https://youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
                try:
                    async with session.get(api_url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            # Check if it's a live stream
                            if 'title' in data and ('live' in data['title'].lower() or 'stream' in data['title'].lower()):
                                logging.info(f"YouTube channel {video_id} appears to be live")
                                return True
                            else:
                                logging.info(f"YouTube channel {video_id} exists but may not be live")
                                return True  # Still count as valid even if not currently live
                        else:
                            logging.warning(f"YouTube API check failed for {video_id}: {response.status}")
                            return False
                except Exception as e:
                    logging.warning(f"YouTube live check error for {video_id}: {e}")
                    return False
        
        # Twitch live status check
        elif 'twitch.tv' in url:
            # Extract channel name
            channel_name = url.split('twitch.tv/')[1].split('/')[0]
            if channel_name:
                # Check Twitch API for live status
                api_url = f"https://www.twitch.tv/{channel_name}"
                try:
                    async with session.get(api_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}) as response:
                        if response.status == 200:
                            # Parse HTML to check for live status
                            content = await response.text()
                            if 'isLive' in content or 'data-is-live="true"' in content:
                                logging.info(f"Twitch channel {channel_name} is live")
                                return True
                            else:
                                logging.info(f"Twitch channel {channel_name} exists but may not be live")
                                return True  # Still count as valid
                        else:
                            logging.warning(f"Twitch check failed for {channel_name}: {response.status}")
                            return False
                except Exception as e:
                    logging.warning(f"Twitch live check error for {channel_name}: {e}")
                    return False
        
        # For other platforms, just check if URL exists
        return await check_link_exists(session, url)
        
    except Exception as e:
        logging.error(f"Platform live check error for {url}: {e}")
        return False 

async def validate_m3u8_stream(session, url):
    """Comprehensive M3U8 stream validation using professional packages."""
    try:
        logging.info(f"Validating M3U8 stream: {url}")
        
        # First, check if the URL is accessible
        if not await check_link_exists(session, url):
            return False, "URL not accessible"
        
        # Use professional M3U8 parsing
        try:
            import m3u8
            import streamlink
            
            # Method 1: Streamlink validation (most reliable)
            try:
                sl_session = streamlink.Streamlink()
                streams = sl_session.streams(url)
                
                if streams:
                    # Streamlink found valid streams
                    qualities = list(streams.keys())
                    best_quality = streams.get('best') or streams.get('live') or list(streams.values())[0]
                    
                    logging.info(f"Streamlink found {len(streams)} streams: {qualities}")
                    return True, f"Live stream ({len(streams)} qualities: {', '.join(qualities[:3])})"
                else:
                    logging.warning(f"Streamlink found no streams for {url}")
            except Exception as e:
                logging.debug(f"Streamlink validation failed: {e}")
            
            # Method 2: Enhanced M3U8 parsing
            async with session.get(url, timeout=15, headers=HEADERS) as response:
                if response.status != 200:
                    return False, f"HTTP {response.status}"
                
                content = await response.text()
                if not content.strip():
                    return False, "Empty playlist"
                
                # Parse with professional M3U8 library
                playlist = m3u8.loads(content)
                
                if playlist.is_variant:
                    # Master playlist - check variants
                    if not playlist.playlists:
                        return False, "Master playlist has no variants"
                    
                    # Get best quality variant
                    best_variant = max(playlist.playlists, key=lambda x: x.stream_info.bandwidth or 0)
                    variant_url = best_variant.uri
                    
                    # Resolve relative URL
                    if not variant_url.startswith('http'):
                        from urllib.parse import urljoin
                        variant_url = urljoin(url, variant_url)
                    
                    # Test the variant
                    return await validate_media_playlist(session, variant_url)
                
                else:
                    # Media playlist - validate segments
                    if not playlist.segments:
                        return False, "No media segments found"
                    
                    if playlist.is_endlist:
                        # VOD content
                        return True, f"VOD stream ({len(playlist.segments)} segments)"
                    else:
                        # Live content
                        return True, f"Live stream ({len(playlist.segments)} segments)"
                        
        except ImportError:
            # Fallback to original method if packages not available
            logging.warning("Professional M3U8 packages not available, using fallback")
            return await validate_m3u8_stream_fallback(session, url)
                    
    except Exception as e:
        logging.error(f"M3U8 validation error for {url}: {e}")
        return False, f"Validation error: {str(e)}"

async def validate_m3u8_stream_fallback(session, url):
    """Fallback M3U8 validation method."""
    try:
        async with session.get(url, timeout=15, headers=HEADERS) as response:
            if response.status != 200:
                return False, f"HTTP {response.status}"
            
            content = await response.text()
            if not content.strip():
                return False, "Empty playlist"
            
            lines = content.strip().split('\n')
            
            # Check if it's a master playlist or media playlist
            is_master = any('#EXT-X-STREAM-INF:' in line or '#EXT-X-MEDIA:' in line for line in lines)
            is_media = any('#EXTINF:' in line or '#EXT-X-TARGETDURATION:' in line for line in lines)
            
            if is_master:
                logging.info(f"Master playlist detected for {url}")
                # Parse master playlist for variants
                variants = []
                for i, line in enumerate(lines):
                    if line.startswith('#EXT-X-STREAM-INF:'):
                        # Extract variant info
                        bandwidth = None
                        resolution = None
                        codecs = None
                        
                        parts = line.split(',')
                        for part in parts:
                            part = part.strip()
                            if part.startswith('BANDWIDTH='):
                                bandwidth = int(part.split('=')[1])
                            elif part.startswith('RESOLUTION='):
                                resolution = part.split('=')[1]
                            elif part.startswith('CODECS='):
                                codecs = part.split('=')[1]
                        
                        # Get the URL for this variant (next non-comment line)
                        if i + 1 < len(lines) and not lines[i + 1].startswith('#'):
                            variant_url = lines[i + 1].strip()
                            if variant_url.startswith('http'):
                                variants.append({
                                    'url': variant_url,
                                    'bandwidth': bandwidth,
                                    'resolution': resolution,
                                    'codecs': codecs
                                })
                            else:
                                # Relative URL - resolve against base URL
                                from urllib.parse import urljoin
                                absolute_url = urljoin(url, variant_url)
                                variants.append({
                                    'url': absolute_url,
                                    'bandwidth': bandwidth,
                                    'resolution': resolution,
                                    'codecs': codecs
                                })
                
                if not variants:
                    return False, "No valid variants in master playlist"
                
                # Test the best quality variant
                variants.sort(key=lambda x: x.get('bandwidth', 0), reverse=True)
                best_variant = variants[0]
                logging.info(f"Testing best variant: {best_variant.get('resolution', 'unknown')} ({best_variant.get('bandwidth', 'unknown')} bps)")
                
                # Validate the variant stream
                return await validate_media_playlist(session, best_variant['url'])
            
            elif is_media:
                logging.info(f"Media playlist detected for {url}")
                # Direct media playlist validation
                return await validate_media_playlist(session, url)
            
            else:
                return False, "Invalid M3U8 format"
                
    except Exception as e:
        logging.error(f"Fallback M3U8 validation error for {url}: {e}")
        return False, f"Fallback validation error: {str(e)}"

async def validate_media_playlist(session, playlist_url):
    """Validate a media playlist has actual streaming content."""
    try:
        async with session.get(playlist_url, timeout=10, headers=HEADERS) as response:
            if response.status != 200:
                return False, f"HTTP {response.status}"
            
            content = await response.text()
            if not content.strip():
                return False, "Empty media playlist"
            
            lines = content.strip().split('\n')
            
            # Check for essential media playlist tags
            has_target_duration = any('#EXT-X-TARGETDURATION:' in line for line in lines)
            has_segments = any(line and not line.startswith('#') for line in lines)
            
            if not has_target_duration:
                return False, "Missing target duration"
            
            if not has_segments:
                return False, "No media segments found"
            
            # Count media segments
            segment_count = sum(1 for line in lines if line and not line.startswith('#'))
            
            # Check for end list tag (indicates complete playlist)
            has_end_list = any('#EXT-X-ENDLIST' in line for line in lines)
            
            if segment_count == 0:
                return False, "No media segments"
            
            # For live streams, we expect ongoing segments without ENDLIST
            # For VOD, we expect ENDLIST
            if has_end_list:
                logging.info(f"VOD playlist detected: {segment_count} segments")
                return True, f"VOD stream ({segment_count} segments)"
            else:
                logging.info(f"Live stream detected: {segment_count} segments")
                return True, f"Live stream ({segment_count} segments)"
                
    except Exception as e:
        logging.error(f"Media playlist validation error for {playlist_url}: {e}")
        return False, f"Media validation error: {str(e)}"

async def get_stream_metadata(session, url):
    """Extract metadata about what's currently playing."""
    try:
        if '.m3u8' in url.lower():
            # Try to extract title from M3U8
            async with session.get(url, timeout=10, headers=HEADERS) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Look for title metadata
                    for line in content.split('\n'):
                        if '#EXT-X-STREAM-TITLE:' in line:
                            title = line.split(':', 1)[1].strip()
                            if title:
                                return title
                        elif '#EXTINF:' in line:
                            # Extract title from EXTINF
                            parts = line.split(',')
                            if len(parts) > 1:
                                title = parts[-1].strip()
                                if title and title != '':
                                    return title
        
        # For YouTube, try to get video title
        elif 'youtube.com' in url or 'youtu.be' in url:
            video_id = None
            if 'watch?v=' in url:
                video_id = url.split('v=')[1].split('&')[0]
            elif 'youtu.be/' in url:
                video_id = url.split('youtu.be/')[1].split('?')[0]
            
            if video_id:
                api_url = f"https://youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
                try:
                    async with session.get(api_url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data.get('title', 'Unknown')
                except:
                    pass
        
        # For Twitch, try to get stream title
        elif 'twitch.tv' in url:
            channel_name = url.split('twitch.tv/')[1].split('/')[0]
            try:
                async with session.get(f"https://www.twitch.tv/{channel_name}", timeout=10) as response:
                    if response.status == 200:
                        content = await response.text()
                        # Look for stream title in HTML
                        import re
                        title_match = re.search(r'"title":"([^"]+)"', content)
                        if title_match:
                            return title_match.group(1)
            except:
                pass
        
        return "Live Stream"
        
    except Exception as e:
        logging.debug(f"Error extracting metadata for {url}: {e}")
        return "Live Stream" 

# Asynchronously validate a single channel.
async def validate_channel(session, channel):
    
    try:
        logging.info(f"Validating channel: {channel['url']}")
        
        # Use platform-specific live checking for YouTube/Twitch
        if 'youtube.com' in channel['url'] or 'youtu.be' in channel['url'] or 'twitch.tv' in channel['url']:
            if await check_platform_live_status(session, channel['url']):
                channel['status'] = 'online'
                # Get metadata for what's playing now
                channel['playing_now'] = await get_stream_metadata(session, channel['url'])
                return channel, True
            else:
                channel['status'] = 'offline'
                return channel, False
        
        # For M3U8 streams, use comprehensive validation
        elif '.m3u8' in channel['url'].lower():
            is_valid, details = await validate_m3u8_stream(session, channel['url'])
            if is_valid:
                channel['status'] = 'online'
                channel['playing_now'] = details  # Use validation details as playing_now
                return channel, True
            else:
                channel['status'] = 'offline'
                channel['playing_now'] = f"Stream error: {details}"
                return channel, False
        
        # For other streams, just check if URL exists
        else:
            if await check_link_exists(session, channel['url']):
                channel['status'] = 'online'
                channel['playing_now'] = await get_stream_metadata(session, channel['url'])
                return channel, True
            else:
                channel['status'] = 'offline'
                return channel, False
                
    except Exception as e:
        logging.error(f"Error validating channel {channel['url']}: {e}")
        channel['status'] = 'error'
        channel['playing_now'] = f"Validation error: {str(e)}"
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
        logging.info("Starting global initial scan...")
        channels = check_all_global_sources()  # Use global aggregation instead of single source

        async with aiohttp.ClientSession() as session:
            tasks = [check_link_exists(session, ch['url']) for ch in channels]
            exists_results = await asyncio.gather(*tasks)
            invalid_links = [ch['url'] for ch, exists in zip(channels, exists_results) if not exists]
            valid_channels, dead_channels = await process_channels([ch for ch, exists in zip(channels, exists_results) if exists], invalid_links)

        for file, data in zip(FILES.values(), [valid_channels, dead_channels, invalid_links]):
            with open(file, 'w') as f:
                json.dump(data, f, indent=4)

        logging.info(f"Global initial scan complete: {len(valid_channels)} valid, {len(dead_channels)} dead.")
    except Exception as e:
        logging.error(f"Error during global initial scan: {e}")

async def sweep_channels_async():
    logging.info("Starting global channel sweep...")
    channels = check_all_global_sources()  # Use global aggregation
    with open(FILES['invalid'], 'r') as f:
        invalid_links = json.load(f)
        valid_channels, dead_channels = await process_channels(channels, invalid_links)
    
    for file, data in zip([FILES['streams'], FILES['dead']], [valid_channels, dead_channels]):
        with open(file, 'w') as f:
            json.dump(data, f, indent=4)

    logging.info(f"Global channel sweep complete: {len(valid_channels)} valid, {len(dead_channels)} dead.")      


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

@app.route('/scan')
def trigger_scan():
    """Trigger initial scan to populate channels."""
    try:
        # Run initial scan in background
        threading.Thread(target=asyncio.run, args=(initial_scan(),), daemon=True).start()
        return jsonify({
            'message': 'Initial scan started',
            'status': 'scanning'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/channels')
def get_channels():
    """Return a list of channels with icon URLs if they exist."""
    try:
        # If channels file is empty, return empty list (don't auto-parse)
        with open(FILES['streams'], 'r') as f:
            channels = json.load(f)
            
            if not channels:
                # Return empty list - user must trigger scan manually
                return jsonify([])
            
            # Add icon URLs to channels if they exist
            for channel in channels:
                # Create safe filename from channel name
                safe_name = re.sub(r'[^\w\-_\.]', '', channel['name'].lower())
                icon_path = f'webroot/icons/{safe_name}.png'
                if os.path.exists(icon_path):
                    channel['icon_url'] = f'/icons/{safe_name}.png'
                else:
                    channel['icon_url'] = None
            
            # Return all channels flat for simplicity
            return jsonify({
                'channels': channels,
                'total_channels': len(channels),
                'current_page': 1,
                'has_more': False,
                'total_pages': 1
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

   
 