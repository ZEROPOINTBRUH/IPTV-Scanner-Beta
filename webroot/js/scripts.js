// IPTV Scanner — separate desktop / mobile layouts, smooth list updates, live revision stream

const FAVORITES_STORAGE_KEY = 'iptv_scanner_favorites_v1';

function streamUrlKey(url) {
    try {
        return btoa(unescape(encodeURIComponent(url)));
    } catch {
        return String(url).slice(0, 64);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

class IPTVScanner {
    constructor() {
        this.channels = [];
        this.filteredChannels = [];
        this.currentChannel = null;
        this.currentSearch = '';
        this.currentGroupFilter = '';
        this.currentCountryFilter = '';
        this.currentSortFilter = 'name';
        this.currentSortDir = 'asc';
        this.userIsInteracting = false;
        this.lastRevision = -1;
        this._reloadTimer = null;
        this._scrollAnchorKey = null;
        this._hlsInstance = null;
        this.favorites = this.loadFavorites();
        this.isGuideVisible = true;
        this.init();
    }

    loadFavorites() {
        try {
            const raw = localStorage.getItem(FAVORITES_STORAGE_KEY);
            const arr = raw ? JSON.parse(raw) : [];
            return new Set(Array.isArray(arr) ? arr : []);
        } catch {
            return new Set();
        }
    }

    persistFavorites() {
        localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify([...this.favorites]));
    }

    isMobileLayout() {
        return window.matchMedia('(max-width: 767px)').matches;
    }

    activeChannelsListEl() {
        return this.isMobileLayout()
            ? document.getElementById('channelsListMob')
            : document.getElementById('channelsListDesk');
    }

    saveScrollAnchor() {
        const el = this.activeChannelsListEl();
        if (!el) return;
        const listTop = el.getBoundingClientRect().top;
        this._scrollAnchorKey = null;
        for (const card of el.querySelectorAll('.channel-card[data-stream-key]')) {
            const r = card.getBoundingClientRect();
            if (r.bottom > listTop + 4 && r.top < listTop + 120) {
                this._scrollAnchorKey = card.getAttribute('data-stream-key');
                break;
            }
        }
    }

    restoreScrollAnchor() {
        const el = this.activeChannelsListEl();
        if (!el || !this._scrollAnchorKey) return;
        const target = [...el.querySelectorAll('.channel-card')].find(
            (c) => c.getAttribute('data-stream-key') === this._scrollAnchorKey
        );
        target?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }

    mirrorCheckbox(deskId, mobId) {
        const d = document.getElementById(deskId);
        const m = document.getElementById(mobId);
        if (!d || !m) return;
        const sync = (src, dst) => {
            dst.checked = src.checked;
            this.userIsInteracting = true;
            this.applyFilters();
        };
        d.addEventListener('change', () => sync(d, m));
        m.addEventListener('change', () => sync(m, d));
    }

    mirrorSelect(deskId, mobId) {
        const d = document.getElementById(deskId);
        const m = document.getElementById(mobId);
        if (!d || !m) return;
        d.addEventListener('change', () => {
            m.value = d.value;
            this.userIsInteracting = true;
            this.applyFilters();
        });
        m.addEventListener('change', () => {
            d.value = m.value;
            this.userIsInteracting = true;
            this.applyFilters();
        });
    }

    toggleFavorite(url, evt) {
        evt.preventDefault();
        evt.stopPropagation();
        if (this.favorites.has(url)) {
            this.favorites.delete(url);
        } else {
            this.favorites.add(url);
        }
        this.persistFavorites();
        this.renderChannels({ preserveScroll: true });
    }

    init() {
        this.setupIntegrationUrls();
        this.setupMobileTabs();
        this.setupEventListeners();
        this.connectEventStream();
        this.loadChannels(false, {});
        this.updateStatusPolling();
        window.addEventListener(
            'resize',
            debounce(() => {
                this.renderChannels({ preserveScroll: true });
            }, 250)
        );
    }

    setupIntegrationUrls() {
        const origin = `${window.location.protocol}//${window.location.host}`;
        const m3u = `${origin}/jellyfin/live.m3u`;
        const wire = (bareId, codeId, btnId) => {
            const bare = document.getElementById(bareId);
            const code = document.getElementById(codeId);
            const btn = document.getElementById(btnId);
            if (bare) bare.textContent = origin;
            if (code) code.textContent = m3u;
            if (btn) {
                btn.addEventListener('click', () => {
                    const run = () => this.showNotification('M3U link copied', 'success');
                    if (navigator.clipboard?.writeText) {
                        navigator.clipboard.writeText(m3u).then(run).catch(() => {});
                    }
                });
            }
        };
        wire('bareOriginDesk', 'jellyfinM3uDesk', 'copyM3uDesk');
        wire('bareOriginMob', 'jellyfinM3uMob', 'copyM3uMob');
    }

    setupMobileTabs() {
        document.querySelectorAll('.mobile-tab').forEach((btn) => {
            btn.addEventListener('click', () => {
                const tab = btn.getAttribute('data-mobile-tab');
                document.querySelectorAll('.mobile-tab').forEach((b) => {
                    const on = b === btn;
                    b.classList.toggle('active', on);
                    b.setAttribute('aria-selected', on ? 'true' : 'false');
                });
                document.querySelectorAll('.mobile-panel').forEach((p) => {
                    const panel = p.getAttribute('data-panel');
                    p.classList.toggle('hidden', panel !== tab);
                });
            });
        });
    }

    setupEventListeners() {
        const wireSearch = (id) => {
            const inp = document.getElementById(id);
            if (!inp) return;
            inp.addEventListener('input', (e) => {
                this.userIsInteracting = true;
                clearTimeout(this.searchTimeout);
                this.searchTimeout = setTimeout(() => {
                    this.currentSearch = e.target.value;
                    this.filterChannels(e.target.value);
                }, 300);
            });
        };
        wireSearch('searchDesk');
        wireSearch('searchMob');

        const toggleDesk = document.getElementById('toggleGuideDesk');
        if (toggleDesk) {
            toggleDesk.addEventListener('click', () => this.toggleGuideVisibility());
        }

        this.mirrorSelect('groupFilterDesk', 'groupFilterMob');
        this.mirrorSelect('countryFilterDesk', 'countryFilterMob');
        this.mirrorSelect('sortDirDesk', 'sortDirMob');

        ['sortFilterDesk', 'sortFilterMob'].forEach((id) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('change', () => {
                this.userIsInteracting = true;
                const v = el.value;
                document.getElementById('sortFilterDesk').value = v;
                document.getElementById('sortFilterMob').value = v;
                this.currentSortFilter = v;
                this.applyFilters();
            });
        });
        ['sortDirDesk', 'sortDirMob'].forEach((id) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('change', () => {
                this.userIsInteracting = true;
                const v = el.value;
                document.getElementById('sortDirDesk').value = v;
                document.getElementById('sortDirMob').value = v;
                this.currentSortDir = v;
                this.applyFilters();
            });
        });

        this.mirrorCheckbox('onlineOnlyDesk', 'onlineOnlyMob');
        this.mirrorCheckbox('favoritesOnlyDesk', 'favoritesOnlyMob');

        document.getElementById('watchNowBtn').addEventListener('click', () => this.watchFromPreview());
        document.getElementById('closePreviewBtn').addEventListener('click', () => this.closePreview());
        const px = document.getElementById('closePreviewX');
        if (px) px.addEventListener('click', () => this.closePreview());

        document.getElementById('previewModal').addEventListener('click', (e) => {
            if (e.target.id === 'previewModal') {
                this.closePreview();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closePreview();
            }
            if (!this.isMobileLayout()) {
                if (e.key === 'ArrowLeft' && this.currentChannel) {
                    this.switchChannel(-1);
                }
                if (e.key === 'ArrowRight' && this.currentChannel) {
                    this.switchChannel(1);
                }
            }
        });
    }

    connectEventStream() {
        if (!('EventSource' in window)) {
            this.startPollingFallback();
            return;
        }
        try {
            const es = new EventSource('/api/events');
            es.onmessage = (ev) => {
                try {
                    const d = JSON.parse(ev.data);
                    if (d.error) {
                        return;
                    }
                    this.applyStatusPayload(d);
                    if (typeof d.revision === 'number' && d.revision !== this.lastRevision) {
                        this.scheduleQuietReload();
                    }
                } catch {
                    /* ignore */
                }
            };
            es.onerror = () => {
                es.close();
                this.startPollingFallback();
            };
        } catch {
            this.startPollingFallback();
        }
    }

    startPollingFallback() {
        if (this._pollId) {
            return;
        }
        this._pollId = setInterval(async () => {
            try {
                const r = await fetch('/status');
                const d = await r.json();
                this.applyStatusPayload(d);
                if (typeof d.revision === 'number' && d.revision !== this.lastRevision) {
                    this.scheduleQuietReload();
                }
            } catch {
                /* ignore */
            }
        }, 8000);
    }

    scheduleQuietReload() {
        clearTimeout(this._reloadTimer);
        this._reloadTimer = setTimeout(() => {
            this.loadChannels(true, { quiet: true });
        }, 1200);
    }

    hasActiveFilters() {
        const sq = (document.getElementById('searchDesk')?.value || '').trim();
        const mq = (document.getElementById('searchMob')?.value || '').trim();
        const g = document.getElementById('groupFilterDesk')?.value || document.getElementById('groupFilterMob')?.value;
        const c = document.getElementById('countryFilterDesk')?.value || document.getElementById('countryFilterMob')?.value;
        const on =
            document.getElementById('onlineOnlyDesk')?.checked || document.getElementById('onlineOnlyMob')?.checked;
        const fav =
            document.getElementById('favoritesOnlyDesk')?.checked ||
            document.getElementById('favoritesOnlyMob')?.checked;
        return !!(sq || mq || g || c || on || fav);
    }

    applyStatusPayload(d) {
        if (typeof d.total_channels === 'number') {
            const elD = document.getElementById('channelCountDesk');
            const elM = document.getElementById('channelCountMob');
            if (elD) {
                elD.textContent = d.total_channels;
            }
            if (elM) {
                elM.textContent = d.total_channels;
            }
        }
        if (typeof d.online_channels === 'number') {
            const oD = document.getElementById('onlineCountDesk');
            const oM = document.getElementById('onlineCountMob');
            if (oD) {
                oD.textContent = d.online_channels;
            }
            if (oM) {
                oM.textContent = d.online_channels;
            }
            const dotD = document.getElementById('onlineDotDesk');
            const dotM = document.getElementById('onlineDotMob');
            [dotD, dotM].forEach((dot) => {
                if (dot) {
                    dot.classList.toggle('online', d.online_channels > 0);
                }
            });
        }
        const scanD = document.getElementById('scanStatusDesk');
        const scanM = document.getElementById('scanStatusMob');
        const label = d.scanning ? 'Scanning' : 'Live';
        if (scanD) {
            scanD.textContent = label;
        }
        if (scanM) {
            scanM.textContent = label;
        }
    }

    updateStatusPolling() {
        setInterval(async () => {
            try {
                const r = await fetch('/status');
                const d = await r.json();
                this.applyStatusPayload(d);
            } catch {
                /* ignore */
            }
        }, 15000);
    }

    async loadChannels(preserveFilters = true, opts = {}) {
        const quiet = opts.quiet === true;
        try {
            if (!preserveFilters && !quiet) {
                this.showLoading(true);
            }
            const response = await fetch('/channels');
            const data = await response.json();

            let next = [];
            if (data.channels && data.channels.length > 0) {
                next = data.channels;
            } else if (data.groups && data.groups.length > 0) {
                data.groups.forEach((group) => {
                    if (group.channels) {
                        next.push(...group.channels);
                    }
                });
            } else if (Array.isArray(data) && data.length > 0) {
                next = data;
            }

            if (typeof data.revision === 'number') {
                this.lastRevision = data.revision;
            }

            this.channels = next;

            this.populateGroupFilter();
            this.populateCountryFilter();

            if (preserveFilters && (this.userIsInteracting || this.hasActiveFilters())) {
                this.restoreUserFilters();
            } else {
                this.filteredChannels = [...this.channels];
                this.renderChannels({ preserveScroll: quiet });
            }

            this.updateChannelCount();
            this.updateVisibleCount();
        } catch (error) {
            console.error('Error loading channels:', error);
            this.showError('Failed to load channels');
        } finally {
            if (!preserveFilters && !quiet) {
                this.showLoading(false);
            }
        }
    }

    restoreUserFilters() {
        const dSearch = document.getElementById('searchDesk');
        const mSearch = document.getElementById('searchMob');
        if (this.currentSearch) {
            if (dSearch) {
                dSearch.value = this.currentSearch;
            }
            if (mSearch) {
                mSearch.value = this.currentSearch;
            }
        }

        if (this.currentGroupFilter) {
            document.getElementById('groupFilterDesk').value = this.currentGroupFilter;
            document.getElementById('groupFilterMob').value = this.currentGroupFilter;
        }
        if (this.currentCountryFilter) {
            document.getElementById('countryFilterDesk').value = this.currentCountryFilter;
            document.getElementById('countryFilterMob').value = this.currentCountryFilter;
        }
        if (this.currentSortFilter) {
            document.getElementById('sortFilterDesk').value = this.currentSortFilter;
            document.getElementById('sortFilterMob').value = this.currentSortFilter;
        }
        if (this.currentSortDir) {
            document.getElementById('sortDirDesk').value = this.currentSortDir;
            document.getElementById('sortDirMob').value = this.currentSortDir;
        }

        this.applyFilters();
    }

    populateGroupFilter() {
        const groups = [...new Set(this.channels.map((ch) => ch.group_title || 'Unknown'))].sort();
        ['groupFilterDesk', 'groupFilterMob'].forEach((id) => {
            const sel = document.getElementById(id);
            if (!sel) {
                return;
            }
            const cur = sel.value;
            sel.innerHTML = id.endsWith('Mob')
                ? '<option value="">Group</option>'
                : '<option value="">All groups</option>';
            groups.forEach((group) => {
                const o = document.createElement('option');
                o.value = group;
                o.textContent = group;
                sel.appendChild(o);
            });
            if (groups.includes(cur)) {
                sel.value = cur;
            }
        });
    }

    populateCountryFilter() {
        const countries = [...new Set(this.channels.map((ch) => ch.country || 'GLOBAL'))].sort();
        ['countryFilterDesk', 'countryFilterMob'].forEach((id) => {
            const sel = document.getElementById(id);
            if (!sel) {
                return;
            }
            const cur = sel.value;
            sel.innerHTML = id.endsWith('Mob')
                ? '<option value="">Country</option>'
                : '<option value="">All countries</option>';
            countries.forEach((c) => {
                const o = document.createElement('option');
                o.value = c;
                o.textContent = c;
                sel.appendChild(o);
            });
            if (countries.includes(cur)) {
                sel.value = cur;
            }
        });
    }

    renderChannels(opts = {}) {
        const preserve = opts.preserveScroll !== false;
        if (preserve) {
            this.saveScrollAnchor();
        }

        const desk = document.getElementById('channelsListDesk');
        const mob = document.getElementById('channelsListMob');
        [desk, mob].forEach((list) => {
            if (!list) {
                return;
            }
            list.innerHTML = '';
        });

        if (this.filteredChannels.length === 0) {
            const empty = '<div class="no-channels">No channels found</div>';
            if (desk) {
                desk.innerHTML = empty;
            }
            if (mob) {
                mob.innerHTML = empty;
            }
            this.updateVisibleCount();
            return;
        }

        const fragD = document.createDocumentFragment();
        const fragM = document.createDocumentFragment();
        this.filteredChannels.forEach((ch) => {
            fragD.appendChild(this.createChannelCard(ch));
            fragM.appendChild(this.createChannelCard(ch));
        });
        if (desk) {
            desk.appendChild(fragD);
        }
        if (mob) {
            mob.appendChild(fragM);
        }

        this.updateVisibleCount();
        if (preserve) {
            requestAnimationFrame(() => {
                this.restoreScrollAnchor();
                requestAnimationFrame(() => this.restoreScrollAnchor());
            });
        }
    }

    createChannelCard(channel) {
        const card = document.createElement('div');
        card.className = 'channel-card';
        const key = streamUrlKey(channel.url);
        card.setAttribute('data-stream-key', key);
        if (this.currentChannel && this.currentChannel.url === channel.url) {
            card.classList.add('active');
        }
        if (this.favorites.has(channel.url)) {
            card.classList.add('is-favorite');
        }

        const logoHtml =
            channel.icon_url && channel.icon_url !== null
                ? `<img src="${escapeHtml(channel.icon_url)}" alt="" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"><span class="channel-text-logo" style="display:none">${escapeHtml(channel.name.charAt(0).toUpperCase())}</span>`
                : escapeHtml(channel.name.charAt(0).toUpperCase());

        const status = channel.status || 'unknown';
        const playingNow = escapeHtml(channel.playing_now || 'Loading...');
        const name = escapeHtml(channel.name);
        const favLabel = this.favorites.has(channel.url) ? '★' : '☆';
        const quality = escapeHtml(channel.variant_quality || 'auto');
        const language = escapeHtml(channel.audio_language || 'N/A');
        const bandwidth = Number(channel.variant_bandwidth || 0);
        const bwKbps = bandwidth > 0 ? `${Math.round(bandwidth / 1000)} kbps` : 'N/A';

        card.innerHTML = `
            <div class="channel-header">
                <div class="channel-logo">${logoHtml}</div>
                <div class="channel-name">${name}</div>
                <button type="button" class="btn-fav" aria-label="Favorite">${favLabel}</button>
                <div class="channel-status ${escapeHtml(status)}"></div>
            </div>
            <div class="channel-meta">${quality} • ${language} • ${bwKbps}</div>
            <div class="channel-info">${playingNow}</div>
            <div class="channel-actions">
                <button type="button" class="channel-btn primary ch-play" data-action="play"><i class="fas fa-play"></i> Play</button>
                <button type="button" class="channel-btn ch-vlc" data-action="vlc"><i class="fas fa-external-link-alt"></i> VLC</button>
                <button type="button" class="channel-btn ch-browser" data-action="browser"><i class="fas fa-globe"></i> Web</button>
                <button type="button" class="channel-btn ch-copy" data-action="copy"><i class="fas fa-copy"></i> Copy</button>
            </div>
        `;

        const favBtn = card.querySelector('.btn-fav');
        favBtn.addEventListener('click', (e) => this.toggleFavorite(channel.url, e));

        card.querySelector('.ch-play').addEventListener('click', (e) => {
            e.stopPropagation();
            this.playChannel(channel.url, channel.name);
        });
        card.querySelector('.ch-vlc').addEventListener('click', (e) => {
            e.stopPropagation();
            this.openInVLC(channel.url, channel.name);
        });
        card.querySelector('.ch-browser').addEventListener('click', (e) => {
            e.stopPropagation();
            this.openInBrowser(channel.url, channel.name);
        });
        card.querySelector('.ch-copy').addEventListener('click', (e) => {
            e.stopPropagation();
            this.copyStream(channel.url, channel.name);
        });

        card.addEventListener('click', (e) => {
            if (e.target.closest('button')) {
                return;
            }
            if (e.target === card || e.target.closest('.channel-header') || e.target.closest('.channel-info')) {
                this.selectChannel(channel);
            }
        });

        return card;
    }

    selectChannel(channel) {
        this.currentChannel = { url: channel.url, name: channel.name };
        this.renderChannels({ preserveScroll: true });
        this.showNotification(`Selected: ${channel.name}`, 'success');
        this.setCurrentChannelMeta(channel);
    }

    setCurrentChannelMeta(channel) {
        const line = `${channel.playing_now || 'Click Play to start'} • ${channel.group_title || '—'} • ${channel.country || 'GLOBAL'}`;
        document.getElementById('currentChannelNameDesk').textContent = channel.name;
        document.getElementById('currentChannelInfoDesk').textContent = line;
        const nm = document.getElementById('currentChannelNameMob');
        const inf = document.getElementById('currentChannelInfoMob');
        if (nm) {
            nm.textContent = channel.name;
        }
        if (inf) {
            inf.textContent = line;
        }
    }

    async playChannel(url, name) {
        try {
            this.currentChannel = { url, name };
            this.updatePlayer(url, name);
            this.renderChannels({ preserveScroll: true });
            this.showNotification(`Now playing: ${name}`, 'success');
            if (this.isMobileLayout()) {
                document.querySelector('.mobile-tab[data-mobile-tab="watch"]')?.click();
            }
        } catch (error) {
            console.error('Error playing channel:', error);
            this.showNotification('Failed to play channel', 'error');
        }
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
        const previewPlayer = document.getElementById('previewPlayer');
        const video = previewPlayer.querySelector('video');
        if (video) {
            video.pause();
            video.removeAttribute('src');
            video.load();
        }
        this.currentPreviewChannel = null;
    }

    _teardownHls() {
        if (this._hlsInstance) {
            try {
                this._hlsInstance.destroy();
            } catch {
                /* ignore */
            }
            this._hlsInstance = null;
        }
    }

    /**
     * Same-origin /proxy/stream + hls.js for browsers without native HLS (e.g. Firefox).
     */
    _attachStreamPlayer(video, playUrl, originalUrl) {
        this._teardownHls();
        if (!video || !playUrl) {
            return;
        }
        video.removeAttribute('src');
        video.querySelectorAll('source').forEach((s) => s.remove());

        const path = (originalUrl || '').split(/[?#]/)[0].toLowerCase();
        const looksProgressive = /\.(mp4|webm|ogv)$/i.test(path);

        if (looksProgressive) {
            video.src = playUrl;
            return;
        }

        const canNative =
            video.canPlayType('application/vnd.apple.mpegurl') ||
            video.canPlayType('application/x-mpegURL');

        if (canNative) {
            video.src = playUrl;
            return;
        }

        if (typeof Hls !== 'undefined' && Hls.isSupported()) {
            const hls = new Hls({
                enableWorker: true,
                lowLatencyMode: false,
                maxBufferLength: 30,
                backBufferLength: 30,
            });
            this._hlsInstance = hls;
            hls.loadSource(playUrl);
            hls.attachMedia(video);
            hls.on(Hls.Events.ERROR, (_, data) => {
                if (!data.fatal) {
                    return;
                }
                if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
                    hls.startLoad();
                } else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
                    hls.recoverMediaError();
                } else {
                    console.error('HLS fatal error', data);
                    this.showNotification('Stream playback failed (try another channel)', 'error');
                }
            });
            return;
        }

        video.src = playUrl;
    }

    updatePlayer(url, name) {
        this._teardownHls();
        const htmlDesk = this.buildPlayerInner(url, name);
        const desk = document.getElementById('videoPlayerDesk');
        const mob = document.getElementById('videoPlayerMob');
        if (desk) {
            desk.innerHTML = htmlDesk;
        }
        if (mob) {
            mob.innerHTML = htmlDesk;
        }
        document.getElementById('currentChannelNameDesk').textContent = name;
        let host = url;
        try {
            host = new URL(url).hostname;
        } catch {
            /* keep */
        }
        document.getElementById('currentChannelInfoDesk').textContent = `Streaming from ${host}`;
        const nm = document.getElementById('currentChannelNameMob');
        const inf = document.getElementById('currentChannelInfoMob');
        if (nm) {
            nm.textContent = name;
        }
        if (inf) {
            inf.textContent = `Streaming from ${host}`;
        }

        if (url.includes('youtube.com') || url.includes('youtu.be') || url.includes('twitch.tv')) {
            return;
        }
        const playUrl = `/proxy/stream?url=${encodeURIComponent(url)}`;
        const mount = this.isMobileLayout() ? mob : desk;
        const v = mount?.querySelector('video');
        if (v) {
            this._attachStreamPlayer(v, playUrl, url);
            v.addEventListener(
                'canplay',
                () => {
                    v.muted = false;
                    v.play().catch(() => {});
                },
                { once: true }
            );
        }
    }

    buildPlayerInner(url, name) {
        if (url.includes('youtube.com') || url.includes('youtu.be') || url.includes('twitch.tv')) {
            const proxyUrl = `/proxy/stream?url=${encodeURIComponent(url)}`;
            return `
                <iframe
                    width="100%" height="100%"
                    src="${proxyUrl}&autoplay=1"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen"
                    allowfullscreen></iframe>`;
        }
        return `<video class="main-stream-video" controls autoplay muted playsinline></video>`;
    }

    switchChannel(direction) {
        if (!this.currentChannel) {
            return;
        }
        const currentIndex = this.filteredChannels.findIndex((ch) => ch.url === this.currentChannel.url);
        if (currentIndex === -1) {
            return;
        }
        let newIndex = currentIndex + direction;
        if (newIndex < 0) {
            newIndex = this.filteredChannels.length - 1;
        }
        if (newIndex >= this.filteredChannels.length) {
            newIndex = 0;
        }
        const newChannel = this.filteredChannels[newIndex];
        this.playChannel(newChannel.url, newChannel.name);
    }

    filterChannels(searchTerm) {
        this.saveScrollAnchor();
        if (!searchTerm) {
            this.filteredChannels = [...this.channels];
        } else {
            const term = searchTerm.toLowerCase();
            this.filteredChannels = this.channels.filter(
                (channel) =>
                    channel.name.toLowerCase().includes(term) ||
                    (channel.group_title && channel.group_title.toLowerCase().includes(term)) ||
                    (channel.country && String(channel.country).toLowerCase().includes(term))
            );
        }
        this.applyFilters();
    }

    applyFilters() {
        this.saveScrollAnchor();

        let filtered = [...this.channels];

        const qDesk = document.getElementById('searchDesk');
        const qMob = document.getElementById('searchMob');
        const searchInput = ((qDesk && qDesk.value) || (qMob && qMob.value) || '').trim();
        if (searchInput) {
            const term = searchInput.toLowerCase();
            filtered = filtered.filter(
                (channel) =>
                    channel.name.toLowerCase().includes(term) ||
                    (channel.group_title && channel.group_title.toLowerCase().includes(term)) ||
                    (channel.country && String(channel.country).toLowerCase().includes(term))
            );
        }

        const groupFilter =
            document.getElementById('groupFilterDesk')?.value || document.getElementById('groupFilterMob')?.value || '';
        if (groupFilter) {
            filtered = filtered.filter((ch) => (ch.group_title || 'Unknown') === groupFilter);
        }

        const countryFilter =
            document.getElementById('countryFilterDesk')?.value ||
            document.getElementById('countryFilterMob')?.value ||
            '';
        if (countryFilter) {
            filtered = filtered.filter((ch) => (ch.country || 'GLOBAL') === countryFilter);
        }

        const od =
            document.getElementById('onlineOnlyDesk')?.checked ||
            document.getElementById('onlineOnlyMob')?.checked;
        if (od) {
            filtered = filtered.filter((ch) => (ch.status || '').toLowerCase() === 'online');
        }

        const favOnly =
            document.getElementById('favoritesOnlyDesk')?.checked ||
            document.getElementById('favoritesOnlyMob')?.checked;
        if (favOnly) {
            filtered = filtered.filter((ch) => this.favorites.has(ch.url));
        }

        const sortFilter =
            document.getElementById('sortFilterDesk')?.value ||
            document.getElementById('sortFilterMob')?.value ||
            'name';
        const sortDir =
            document.getElementById('sortDirDesk')?.value ||
            document.getElementById('sortDirMob')?.value ||
            'asc';
        const dirMult = sortDir === 'desc' ? -1 : 1;
        const statusRank = { online: 0, unknown: 1, error: 2, offline: 3 };
        const qualityScore = (q) => {
            if (!q) return 0;
            const n = String(q).match(/(\d{3,4})/);
            return n ? Number(n[1]) : 0;
        };
        filtered.sort((a, b) => {
            if (sortFilter === 'status') {
                const av = statusRank[(a.status || 'unknown').toLowerCase()] ?? 9;
                const bv = statusRank[(b.status || 'unknown').toLowerCase()] ?? 9;
                return (av - bv) * dirMult;
            }
            if (sortFilter === 'variant_bandwidth') {
                const av = Number(a.variant_bandwidth || 0);
                const bv = Number(b.variant_bandwidth || 0);
                return (av - bv) * dirMult;
            }
            if (sortFilter === 'variant_quality') {
                const av = qualityScore(a.variant_quality);
                const bv = qualityScore(b.variant_quality);
                if (av !== bv) return (av - bv) * dirMult;
            }
            const aVal = String(a[sortFilter] || '').toLowerCase();
            const bVal = String(b[sortFilter] || '').toLowerCase();
            return aVal.localeCompare(bVal) * dirMult;
        });

        this.filteredChannels = filtered;
        this.renderChannels({ preserveScroll: true });
    }

    toggleGuideVisibility() {
        const guideSection = document.getElementById('channelGuideDesk');
        const toggleBtn = document.getElementById('toggleGuideDesk');
        if (!guideSection || !toggleBtn) {
            return;
        }
        this.isGuideVisible = !this.isGuideVisible;
        guideSection.style.display = this.isGuideVisible ? 'flex' : 'none';
        toggleBtn.innerHTML = this.isGuideVisible
            ? '<i class="fas fa-th-list"></i> Guide'
            : '<i class="fas fa-columns"></i> Show guide';
    }

    updateChannelCount() {
        const n = this.channels.length;
        const d = document.getElementById('channelCountDesk');
        const m = document.getElementById('channelCountMob');
        if (d) {
            d.textContent = n;
        }
        if (m) {
            m.textContent = n;
        }
    }

    updateVisibleCount() {
        const v = this.filteredChannels.length;
        const d = document.getElementById('visibleChannelsDesk');
        const m = document.getElementById('visibleChannelsMob');
        if (d) {
            d.textContent = v;
        }
        if (m) {
            m.textContent = v;
        }
    }

    copyStream(url, name) {
        navigator.clipboard.writeText(url).then(
            () => this.showNotification('URL copied', 'success'),
            () => this.showNotification('Copy failed', 'error')
        );
    }

    openInVLC(url, name) {
        try {
            window.open(`vlc://${url}`, '_blank');
            this.showNotification(`Opening ${name} in VLC…`, 'success');
        } catch {
            this.showNotification('VLC open failed', 'error');
        }
    }

    openInBrowser(url, name) {
        window.open(url, '_blank');
    }

    showLoading(show) {
        ['loadingIndicatorDesk', 'loadingIndicatorMob'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) {
                el.classList.toggle('hidden', !show);
                el.style.display = show ? 'flex' : 'none';
            }
        });
    }

    showError(message) {
        const msg = `<div class="error">${escapeHtml(message)}</div>`;
        const desk = document.getElementById('channelsListDesk');
        const mob = document.getElementById('channelsListMob');
        if (desk) {
            desk.innerHTML = msg;
        }
        if (mob) {
            mob.innerHTML = msg;
        }
    }

    showNotification(message, type = 'success') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: max(16px, env(safe-area-inset-top));
            right: max(16px, env(safe-area-inset-right));
            padding: 12px 18px;
            background: ${type === 'success' ? 'linear-gradient(180deg, #3aaf7a, #2a9868)' : 'linear-gradient(180deg, #e84d6f, #c73e52)'};
            color: white;
            border-radius: 12px;
            z-index: 10000;
            box-shadow: 0 12px 32px rgba(0,0,0,0.45);
            border: 1px solid rgba(255,255,255,0.12);
            font-weight: 600;
            font-size: 13px;
        `;
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 2800);
    }
}

function debounce(fn, ms) {
    let t;
    return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn.apply(null, args), ms);
    };
}

document.addEventListener('DOMContentLoaded', () => {
    window.iptvScanner = new IPTVScanner();
});
