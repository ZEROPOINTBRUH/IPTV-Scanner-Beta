// Modern IPTV Scanner - DirecTV-style Interface
class IPTVScanner {
    constructor() {
        this.channels = [];
        this.filteredChannels = [];
        this.currentChannel = null;
        this.scrollPosition = 0;
        this.isGuideVisible = true;
        this.updateInterval = null;
        this.searchTimeout = null;
        
        // User state preservation
        this.currentSearch = '';
        this.currentGroupFilter = '';
        this.currentSortFilter = 'name';
        this.userIsInteracting = false;
        
        this.init();
    }

    downloadAllIcons() {
        this.showNotification('Starting icon download...', 'info');
        
        fetch('/download-icons')
            .then(response => response.json())
            .then(data => {
                if (data.message) {
                    this.showNotification(data.message, 'success');
                    this.showNotification(`Downloaded: ${data.downloaded}, Failed: ${data.failed}`, 'info');
                    
                    // Reload channels after a short delay to get updated icon URLs
                    setTimeout(() => {
                        this.loadChannels(false);
                    }, 2000);
                } else if (data.error) {
                    this.showNotification(`Error: ${data.error}`, 'error');
                }
            })
            .catch(error => {
                console.error('Error downloading icons:', error);
                this.showNotification('Failed to download icons', 'error');
            });
    }

    init() {
        this.setupEventListeners();
        this.startLiveUpdates();
        this.loadChannels(false); // Don't preserve filters on initial load
        this.updateStatus();
    }

    setupEventListeners() {
        // Search functionality
        const searchInput = document.getElementById('search');
        searchInput.addEventListener('input', (e) => {
            this.userIsInteracting = true;
            clearTimeout(this.searchTimeout);
            this.searchTimeout = setTimeout(() => {
                this.currentSearch = e.target.value;
                this.filterChannels(e.target.value);
            }, 300);
        });

        // Guide toggle
        const toggleGuide = document.getElementById('toggleGuide');
        toggleGuide.addEventListener('click', () => {
            this.toggleGuideVisibility();
        });

        // Filter controls
        const groupFilter = document.getElementById('groupFilter');
        const sortFilter = document.getElementById('sortFilter');
        
        groupFilter.addEventListener('change', () => {
            this.userIsInteracting = true;
            this.currentGroupFilter = groupFilter.value;
            this.applyFilters();
        });
        
        sortFilter.addEventListener('change', () => {
            this.userIsInteracting = true;
            this.currentSortFilter = sortFilter.value;
            this.applyFilters();
        });

        // Modal controls
        document.getElementById('watchNowBtn').addEventListener('click', () => {
            this.watchFromPreview();
        });

        document.getElementById('closePreviewBtn').addEventListener('click', () => {
            this.closePreview();
        });

        // Close modal on background click
        document.getElementById('previewModal').addEventListener('click', (e) => {
            if (e.target.id === 'previewModal') {
                this.closePreview();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closePreview();
            }
            if (e.key === 'ArrowLeft' && this.currentChannel) {
                this.switchChannel(-1);
            }
            if (e.key === 'ArrowRight' && this.currentChannel) {
                this.switchChannel(1);
            }
        });
    }

    async loadChannels(preserveFilters = true) {
        try {
            if (!preserveFilters) {
                this.showLoading(true);
            }
            // Request all channels without expensive info loading and WITHOUT icon preloading for speed
            const response = await fetch('/channels?group_by=none&limit=10000&include_info=false&preload_icons=false');
            const data = await response.json();
            
            console.log('API Response:', data); // Debug log
            
            // Handle both grouped and flat response formats
            if (data.channels && data.channels.length > 0) {
                // Flat format
                this.channels = data.channels;
            } else if (data.groups && data.groups.length > 0) {
                // Extract channels from groups
                this.channels = [];
                data.groups.forEach(group => {
                    if (group.channels && group.channels.length > 0) {
                        this.channels.push(...group.channels);
                    }
                });
            } else if (Array.isArray(data) && data.length > 0) {
                // Direct array format
                this.channels = data;
            } else {
                this.channels = [];
            }
            
            console.log('Loaded channels:', this.channels.length);
            
            this.populateGroupFilter();
            
            // Preserve user filters if requested
            if (preserveFilters && this.userIsInteracting) {
                this.restoreUserFilters();
            } else {
                this.filteredChannels = [...this.channels];
                this.renderChannels();
            }
            
            this.updateChannelCount();
        } catch (error) {
            console.error('Error loading channels:', error);
            this.showError('Failed to load channels');
        } finally {
            if (!preserveFilters) {
                this.showLoading(false);
            }
        }
    }

    restoreUserFilters() {
        // Restore search
        const searchInput = document.getElementById('search');
        if (this.currentSearch) {
            searchInput.value = this.currentSearch;
        }
        
        // Restore group filter
        const groupFilter = document.getElementById('groupFilter');
        if (this.currentGroupFilter) {
            groupFilter.value = this.currentGroupFilter;
        }
        
        // Restore sort filter
        const sortFilter = document.getElementById('sortFilter');
        if (this.currentSortFilter) {
            sortFilter.value = this.currentSortFilter;
        }
        
        // Apply filters
        this.applyFilters();
    }

    populateGroupFilter() {
        const groupFilter = document.getElementById('groupFilter');
        const groups = [...new Set(this.channels.map(ch => ch.group_title || 'Unknown'))];
        
        groupFilter.innerHTML = '<option value="">All Groups</option>';
        groups.sort().forEach(group => {
            const option = document.createElement('option');
            option.value = group;
            option.textContent = group;
            groupFilter.appendChild(option);
        });
    }

    renderChannels() {
        const channelsList = document.getElementById('channelsList');
        channelsList.innerHTML = '';

        if (this.filteredChannels.length === 0) {
            channelsList.innerHTML = '<div class="no-channels">No channels found</div>';
            return;
        }

        // Always show channels flat (no grouping) for better performance
        this.filteredChannels.forEach(channel => {
            const channelCard = this.createChannelCard(channel);
            channelsList.appendChild(channelCard);
        });
        
        this.updateVisibleCount();
        this.restoreScrollPosition();
    }

    groupChannels(channels) {
        const groups = {};
        channels.forEach(channel => {
            const group = channel.group_title || 'Unknown';
            if (!groups[group]) {
                groups[group] = [];
            }
            groups[group].push(channel);
        });
        
        return Object.keys(groups).map(name => ({
            name,
            channels: groups[name]
        }));
    }

    createGroupHeader(groupName) {
        const header = document.createElement('div');
        header.className = 'group-header';
        header.innerHTML = `<h3>${groupName}</h3>`;
        return header;
    }

    createChannelCard(channel) {
        const card = document.createElement('div');
        card.className = 'channel-card';
        if (this.currentChannel && this.currentChannel.url === channel.url) {
            card.classList.add('active');
        }

        // Check if icon exists and create logo element
        let logoElement;
        if (channel.icon_url && channel.icon_url !== null) {
            // Use cached icon URL from backend
            logoElement = `<img src="${channel.icon_url}" alt="${channel.name}" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" loading="lazy"><span>${channel.name.charAt(0).toUpperCase()}</span>`;
        } else if (channel.tvg_logo && channel.tvg_logo !== '') {
            // Show text initially, then check for icon and replace when available
            const channelId = channel.name.replace(/[^a-zA-Z0-9]/g, '');
            logoElement = `<span class="channel-text-logo" data-channel-id="${channelId}" data-tvg-logo="${channel.tvg_logo}">${channel.name.charAt(0).toUpperCase()}</span>`;
        } else {
            // Fallback to first letter
            logoElement = channel.name.charAt(0).toUpperCase();
        }
        
        const status = channel.status || 'unknown';
        const playingNow = channel.playing_now || 'Loading...';

        card.innerHTML = `
            <div class="channel-header">
                <div class="channel-logo">${logoElement}</div>
                <div class="channel-name">${channel.name}</div>
                <div class="channel-status ${status}"></div>
            </div>
            <div class="channel-info">${playingNow}</div>
            <div class="channel-actions">
                <button class="channel-btn primary" onclick="iptvScanner.playChannel('${channel.url}', '${channel.name}')">
                    <i class="fas fa-play"></i> Play Here
                </button>
                <button class="channel-btn" onclick="iptvScanner.openInVLC('${channel.url}', '${channel.name}')">
                    <i class="fas fa-external-link-alt"></i> VLC
                </button>
                <button class="channel-btn" onclick="iptvScanner.openInBrowser('${channel.url}', '${channel.name}')">
                    <i class="fas fa-globe"></i> Browser
                </button>
                <button class="channel-btn" onclick="iptvScanner.copyStream('${channel.url}', '${channel.name}')">
                    <i class="fas fa-copy"></i> Copy
                </button>
            </div>
        `;

        // Add click handler for channel selection
        card.addEventListener('click', (e) => {
            // Only handle clicks on card itself, not buttons
            if (e.target === card || e.target.closest('.channel-header') || e.target.closest('.channel-info')) {
                this.selectChannel(channel);
            }
        });

        return card;
    }

    selectChannel(channel) {
        this.currentChannel = { url: channel.url, name: channel.name };
        this.renderChannels(); // Update active state
        this.showNotification(`Selected: ${channel.name}`, 'success');
        
        // Update player info to show selected channel
        const currentChannelName = document.getElementById('currentChannelName');
        const currentChannelInfo = document.getElementById('currentChannelInfo');
        currentChannelName.textContent = channel.name;
        currentChannelInfo.textContent = `${channel.playing_now || 'Click Play to start streaming'} • ${channel.group_title || 'Unknown Group'}`;
    }

    async playChannel(url, name) {
        try {
            this.currentChannel = { url, name };
            this.updatePlayer(url, name);
            this.renderChannels(); // Update active state
            this.showNotification(`Now playing: ${name}`, 'success');
        } catch (error) {
            console.error('Error playing channel:', error);
            this.showNotification('Failed to play channel', 'error');
        }
    }

    async previewChannel(url, name, playingNow) {
        const modal = document.getElementById('previewModal');
        const previewName = document.getElementById('previewChannelName');
        const previewInfo = document.getElementById('previewChannelInfo');
        
        previewName.textContent = name;
        previewInfo.textContent = playingNow;
        
        // Load preview video/iframe
        const previewPlayer = document.getElementById('previewPlayer');
        
        // Check if it's YouTube or Twitch and use iframe
        if (url.includes('youtube.com') || url.includes('youtu.be')) {
            const videoId = this.extractYouTubeId(url);
            if (videoId) {
                previewPlayer.innerHTML = `
                    <iframe 
                        width="100%" 
                        height="100%" 
                        src="https://www.youtube.com/embed/${videoId}?rel=0" 
                        frameborder="0" 
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                        allowfullscreen>
                    </iframe>
                `;
                modal.style.display = 'block';
                this.currentPreviewChannel = { url, name };
                return;
            }
        }
        
        if (url.includes('twitch.tv')) {
            const channelName = this.extractTwitchChannel(url);
            if (channelName) {
                previewPlayer.innerHTML = `
                    <iframe 
                        width="100%" 
                        height="100%" 
                        src="https://player.twitch.tv/?channel=${channelName}&parent=localhost&parent=127.0.0.1" 
                        frameborder="0" 
                        allow="autoplay; fullscreen" 
                        allowfullscreen>
                    </iframe>
                `;
                modal.style.display = 'block';
                this.currentPreviewChannel = { url, name };
                return;
            }
        }
        
        // Default video player for other streams
        previewPlayer.innerHTML = `
            <video controls>
                <source src="${url}" type="application/x-mpegURL">
                <source src="${url}" type="video/mp4">
                Your browser does not support video tag.
            </video>
        `;
        
        modal.style.display = 'block';
        this.currentPreviewChannel = { url, name };
    }

    watchFromPreview() {
        if (this.currentPreviewChannel) {
            this.playChannel(this.currentPreviewChannel.url, this.currentPreviewChannel.name);
            this.closePreview();
        }
    }

    closePreview() {
        const modal = document.getElementById('previewModal');
        modal.style.display = 'none';
        
        // Stop preview video
        const previewPlayer = document.getElementById('previewPlayer');
        const video = previewPlayer.querySelector('video');
        if (video) {
            video.pause();
            video.src = '';
        }
        this.currentPreviewChannel = null;
    }

    updatePlayer(url, name) {
        const videoPlayer = document.getElementById('videoPlayer');
        const currentChannelName = document.getElementById('currentChannelName');
        const currentChannelInfo = document.getElementById('currentChannelInfo');
        
        currentChannelName.textContent = name;
        currentChannelInfo.textContent = `Streaming from ${new URL(url).hostname}`;
        
        // Use proxy for YouTube and Twitch to get proper embed URLs
        if (url.includes('youtube.com') || url.includes('youtu.be') || url.includes('twitch.tv')) {
            const proxyUrl = `/proxy/stream?url=${encodeURIComponent(url)}`;
            videoPlayer.innerHTML = `
                <iframe 
                    width="100%" 
                    height="100%" 
                    src="${proxyUrl}" 
                    frameborder="0" 
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen" 
                    allowfullscreen>
                </iframe>
            `;
        } else {
            // Default video player for other streams
            videoPlayer.innerHTML = `
                <video controls autoplay>
                    <source src="${url}" type="application/x-mpegURL">
                    <source src="${url}" type="video/mp4">
                    Your browser does not support video tag.
                </video>
            `;
        }
    }

    extractYouTubeId(url) {
        const patterns = [
            /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)/,
            /youtube\.com\/watch\?.*v=([^&\n?#]+)/
        ];
        
        for (const pattern of patterns) {
            const match = url.match(pattern);
            if (match) return match[1];
        }
        return null;
    }

    extractTwitchChannel(url) {
        if (url.includes('twitch.tv/')) {
            const parts = url.split('twitch.tv/');
            if (parts.length > 1) {
                const channelPart = parts[1].split('/')[0];
                return channelPart.replace('/', '');
            }
        }
        return null;
    }

    switchChannel(direction) {
        if (!this.currentChannel) return;
        
        const currentIndex = this.filteredChannels.findIndex(ch => ch.url === this.currentChannel.url);
        if (currentIndex === -1) return;
        
        let newIndex = currentIndex + direction;
        if (newIndex < 0) newIndex = this.filteredChannels.length - 1;
        if (newIndex >= this.filteredChannels.length) newIndex = 0;
        
        const newChannel = this.filteredChannels[newIndex];
        this.playChannel(newChannel.url, newChannel.name);
    }

    filterChannels(searchTerm) {
        this.saveScrollPosition();
        
        if (!searchTerm) {
            this.filteredChannels = [...this.channels];
        } else {
            const term = searchTerm.toLowerCase();
            this.filteredChannels = this.channels.filter(channel => 
                channel.name.toLowerCase().includes(term) ||
                (channel.group_title && channel.group_title.toLowerCase().includes(term))
            );
        }
        
        this.applyFilters();
    }

    applyFilters() {
        this.saveScrollPosition();
        
        // Start with all channels
        let filtered = [...this.channels];
        
        // Apply search filter first
        const searchInput = document.getElementById('search').value;
        if (searchInput) {
            const term = searchInput.toLowerCase();
            filtered = filtered.filter(channel => 
                channel.name.toLowerCase().includes(term) ||
                (channel.group_title && channel.group_title.toLowerCase().includes(term))
            );
        }
        
        // Apply group filter
        const groupFilter = document.getElementById('groupFilter').value;
        if (groupFilter) {
            filtered = filtered.filter(ch => (ch.group_title || 'Unknown') === groupFilter);
        }
        
        // Apply sort
        const sortFilter = document.getElementById('sortFilter').value;
        filtered.sort((a, b) => {
            const aVal = a[sortFilter] || '';
            const bVal = b[sortFilter] || '';
            return aVal.localeCompare(bVal);
        });
        
        this.filteredChannels = filtered;
        this.renderChannels();
    }

    toggleGuideVisibility() {
        const guideSection = document.getElementById('channelGuide');
        const toggleBtn = document.getElementById('toggleGuide');
        
        this.isGuideVisible = !this.isGuideVisible;
        
        if (this.isGuideVisible) {
            guideSection.style.display = 'flex';
            toggleBtn.innerHTML = '<i class="fas fa-list"></i> Guide';
        } else {
            guideSection.style.display = 'none';
            toggleBtn.innerHTML = '<i class="fas fa-list"></i> Show Guide';
        }
    }

    startLiveUpdates() {
        this.updateInterval = setInterval(async () => {
            try {
                const response = await fetch('/status');
                const data = await response.json();
                
                this.updateChannelCount();
                
                // Check if new channels were added, but preserve user filters
                if (data.total_channels > this.channels.length) {
                    this.loadChannels(true); // Preserve filters during live updates
                }
                
            } catch (error) {
                console.error('Error checking status:', error);
            }
        }, 5000);
    }

    updateChannelCount() {
        const channelCount = document.getElementById('channelCount');
        channelCount.textContent = this.channels.length;
    }

    updateStatus() {
        const scanStatus = document.getElementById('scanStatus');
        // This could be enhanced to show actual scanning status
        scanStatus.textContent = 'Live';
    }

    updateVisibleCount() {
        const visibleChannels = document.getElementById('visibleChannels');
        visibleChannels.textContent = this.filteredChannels.length;
    }

    saveScrollPosition() {
        const channelsList = document.getElementById('channelsList');
        this.scrollPosition = channelsList.scrollTop;
    }

    restoreScrollPosition() {
        const channelsList = document.getElementById('channelsList');
        channelsList.scrollTop = this.scrollPosition;
    }

    copyStream(url, name) {
        navigator.clipboard.writeText(url).then(() => {
            this.showNotification('Stream URL copied to clipboard!', 'success');
        }).catch(err => {
            console.error('Failed to copy:', err);
            this.showNotification('Failed to copy URL', 'error');
        });
    }

    openInVLC(url, name) {
        try {
            window.open(`vlc://${url}`, '_blank');
            this.showNotification(`Opening ${name} in VLC...`, 'success');
        } catch (error) {
            console.error('Error opening VLC:', error);
            this.showNotification('Failed to open in VLC', 'error');
        }
    }

    openInBrowser(url, name) {
        try {
            window.open(url, '_blank');
            this.showNotification(`Opening ${name} in browser...`, 'success');
        } catch (error) {
            console.error('Error opening browser:', error);
            this.showNotification('Failed to open in browser', 'error');
        }
    }

    showLoading(show) {
        const loadingIndicator = document.getElementById('loadingIndicator');
        loadingIndicator.style.display = show ? 'flex' : 'none';
    }

    showError(message) {
        const channelsList = document.getElementById('channelsList');
        channelsList.innerHTML = `<div class="error">${message}</div>`;
    }

    showNotification(message, type = 'success') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            background-color: ${type === 'success' ? '#4CAF50' : '#f44336'};
            color: white;
            border-radius: 8px;
            z-index: 10000;
            animation: slideIn 0.3s ease-out;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'fadeOut 0.3s ease-out';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }
}

// Initialize the scanner when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.iptvScanner = new IPTVScanner();
});
