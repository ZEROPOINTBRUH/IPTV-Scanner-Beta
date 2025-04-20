## 📌 Depreciation Notice

**This project is no longer being maintained.**

Due to a lack of interest and available time, I’ve decided to stop development on this project in favor of smaller, less time-consuming efforts.

For a more active and up-to-date alternative, I highly recommend checking out the following project by [dillionhuston](https://github.com/dillionhuston):

🔗 [IPTV-Scanner-Beta](https://github.com/dillionhuston/IPTV-Scanner-Beta)

Thanks for your understanding!


# IPTV Scanner

IPTV Scanner is a tool designed to scan, sort, and filter live channels from [iptv-org](https://github.com/iptv-org/iptv). It checks channel availability every three hours, listing active channels in `iptv_streams.json` and inactive or invalid streams (e.g., 404, 401 errors) in `dead_streams.json`. The included web GUI lets you view active channels and access them with a single click. Copy links to your preferred media player or run the service via supported external applications.

## Branches
- **main**: Stable, bug-free version of the app.
- **path-two**: Used for testing new features in beta. Expect experimental changes here.

## Disclaimer
> **Important**: Using IPTV services may be illegal in some countries. It is **your responsibility** to ensure compliance with local laws and regulations. Use this tool at your own risk. The developers are not liable for any misuse or legal consequences.

This tool is for informational and educational purposes only. IPTV Scanner does not host, distribute, or provide access to copyrighted or illegal content.

## Features
- Scans and verifies IPTV channel availability
- Organizes live channels and filters out offline/invalid ones
- Outputs clean, structured JSON files
- Lightweight and efficient
- Web-based GUI for easy channel access

## How to Use
1. Clone the repository: `git clone https://github.com/ZEROPOINTBRUH/iptv-scanner.git`
2. Install dependencies (see `requirements.txt` or setup guide).
3. Run the scanner: `python scanner.py`
4. Access the web GUI at `http://localhost:port` (port specified in config).
5. Copy channel links to your media player or use supported apps.

## Contributing
We welcome contributions! Feel free to:
- Submit feature requests or bug reports via issues.
- Open pull requests for improvements or fixes.
- Give the project a ⭐ **star** on GitHub to show your support!

**Note**The main project owner is **[ZEROPOINTBRUH](https://github.com/ZEROPOINTBRUH)**.

## License
This project is open-source under the [MIT License](LICENSE).

## Credits
- Channel list provided by [iptv-org](https://github.com/iptv-org/iptv).
- Built with ❤️ by the community.

## Support
For issues or feature requests, create an issue on this repository. We’re always open to new ideas!
