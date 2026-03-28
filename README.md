# IPTV Scanner

**Advanced IPTV channel scanner with Jellyfin-compatible sources and research-verified streams.**

IPTV Scanner is a powerful tool designed to scan, validate, and organize live TV channels from multiple sources including [iptv-org](https://github.com/iptv-org/iptv) and [Free-TV](https://github.com/Free-TV/IPTV). It features automatic channel validation, categorization, and a modern web interface for easy access to working streams.

![](https://i.imgur.com/JvOMb3P.gif)
![](https://i.imgur.com/FDq9fwM.gif)

## 🌟 Key Features

- **📺 Massive Channel Library**: Access 5000+ channels from IPTV-org and 500+ curated channels from Free-TV
- **🔍 Research-Verified Sources**: Only includes publicly accessible, working streams
- **🎯 Jellyfin Compatible**: Uses the same sources as Jellyfin media servers
- **🌍 Global Coverage**: Channels from 30+ countries across all continents
- **📂 Category Organization**: News, Entertainment, Sports, Documentary, Music, Religious, and more
- **🔄 Automatic Validation**: Checks stream availability every 3 hours
- **🎨 Modern Web Interface**: Clean, responsive GUI with search and filtering
- **⚡ Real-time Updates**: Live channel status monitoring
- **📱 Mobile Friendly**: Works on all devices and screen sizes

## 🚀 Installation

### Prerequisites
- Python 3.6 or higher
- pip package manager

### Quick Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/ZEROPOINTBRUH/iptv-scanner.git
   cd iptv-scanner
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the scanner:**
   ```bash
   python main.py
   ```

4. **Access the web interface:**
   ```
   http://127.0.0.1:40006
   ```

## 📋 Requirements

The application requires the following Python packages (automatically installed via requirements.txt):

- `requests` - HTTP library for API calls
- `flask` - Web framework for the GUI
- `flask-cors` - Cross-origin resource sharing
- `m3u8` - M3U playlist parsing
- `beautifulsoup4` - HTML parsing
- `aiohttp` - Async HTTP client
- `yt-dlp` - YouTube stream extraction
- `pathlib` - Modern file path handling
- `asyncio` - Async programming support

## 🌐 Source Integration

### Primary Sources
- **[IPTV-org](https://github.com/iptv-org/iptv)**: Main playlist with 5000+ channels
- **[Free-TV](https://github.com/Free-TV/IPTV)**: Curated quality playlist (500+ channels)

### Categories Available
- 📰 **News**: CNN, BBC, Al Jazeera, Fox News, etc.
- 🎬 **Entertainment**: Movies, TV shows, series
- ⚽ **Sports**: ESPN, Fox Sports, EuroSport, etc.
- 📚 **Documentary**: Discovery, National Geographic, History
- 🎵 **Music**: MTV, music channels worldwide
- ⛪ **Religious**: Various religious and spiritual channels

### Regional Coverage
- **Americas**: USA, Canada, Mexico, Brazil, Argentina, Colombia, Chile, Peru
- **Europe**: UK, Germany, France, Italy, Spain
- **Asia**: India, Japan, South Korea, Thailand, Vietnam, Philippines, Malaysia, Singapore, Indonesia
- **Middle East & Africa**: Egypt, Turkey, Saudi Arabia, South Africa
- **Oceania**: Australia, New Zealand

## 🎯 Usage

### Web Interface
1. **Browse Channels**: View all available channels with status indicators
2. **Search & Filter**: Find channels by name, country, or category
3. **Live Preview**: Click any channel to preview in the built-in player
4. **Copy Links**: Right-click to copy stream URLs for external players
5. **Status Monitoring**: See real-time channel availability

### Channel Status
- 🟢 **Online**: Stream is working and accessible
- 🔴 **Offline**: Stream is down or unreachable
- 🟡 **Unknown**: Status not yet determined

### Data Files
- `jsons/IPTV_STREAMS_FILE.json` - Active working channels
- `jsons/DEAD_STREAMS_FILE.json` - Offline/broken channels
- `jsons/INVALID_LINKS_FILE.json` - Invalid or unreachable URLs

## ⚙️ Configuration

### Default Settings
- **Port**: 40006 (configurable in main.py)
- **Update Interval**: Every 3 hours
- **Timeout**: 30 seconds per channel
- **Batch Size**: 10 channels processed simultaneously

### Customization
Edit `main.py` to modify:
- Source URLs and playlists
- Update intervals
- Port settings
- Channel categories
- Validation parameters

## 🔧 Troubleshooting

### Common Issues
1. **Port Already in Use**: Change port in main.py or kill conflicting processes
2. **Missing Dependencies**: Run `pip install -r requirements.txt`
3. **Connection Issues**: Check internet connection and firewall settings
4. **Slow Loading**: Initial scan may take time to validate all channels

### Performance Tips
- Use SSD storage for faster JSON file operations
- Ensure stable internet connection for best results
- Consider increasing timeout values for slow connections

## 🌟 Branches
- **main**: Stable, production-ready version
- **path-two**: Beta testing and experimental features

## ⚠️ Disclaimer

> **Important**: Using IPTV services may be illegal in some countries. It is **your responsibility** to ensure compliance with local laws and regulations. Use this tool at your own risk. The developers are not liable for any misuse or legal consequences.

The developers are not responsible for actions taken with this software, the purpose for which this software is used, what happens on your machine, modifications made to the software, or any consequences of usage. This tool is provided as-is without any warranties or guarantees. All streams are from publicly available sources.

## 🤝 Contributing

We welcome contributions! Feel free to:
- Submit feature requests or bug reports via issues
- Open pull requests for improvements or fixes
- Add new verified sources and playlists
- Improve documentation and examples
- Give the project a ⭐ **star** on GitHub to show your support!

**Note**: The main project owner is **[ZEROPOINTBRUH](https://github.com/ZEROPOINTBRUH)**.

## 📄 License

This project is open-source under the [MIT License](LICENSE).

## 🙏 Credits

- **Channel lists**: [iptv-org](https://github.com/iptv-org/iptv) and [Free-TV](https://github.com/Free-TV/IPTV)
- **Stream validation**: Custom validation system with yt-dlp integration
- **Web interface**: Modern Flask-based GUI with responsive design
- **Community**: Built with ❤️ by the IPTV community

## ☕ Support the Project

Enjoying the IPTV Scanner? Consider supporting its development:

**[☕ Buy me a coffee](https://ko-fi.com/zeropointbruh)**

Your support helps maintain and improve the project:
- 🔄 Keep sources updated and verified
- 🚀 Add new features and improvements
- 🌐 Support infrastructure and hosting
- ⚡ Performance optimizations
- 📱 Mobile app development (future)

Every contribution, no matter how small, makes a difference! Thank you for your support! 🙏

## 📞 Support

For issues, feature requests, or questions:
- Create an issue on this repository
- Email: wegj1@hotmail.com
- Check existing issues for solutions
- Join discussions for community support

---

**🎯 Enjoy your IPTV Scanner experience with verified, working channels from around the world!**
