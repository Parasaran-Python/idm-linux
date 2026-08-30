/**
 * IDM Linux - Universal Floating Video Grabber & Stream Sniffer
 * Works across YouTube, Vimeo, Dailymotion, Reddit, Twitter/X, Twitch, Facebook, and any HTML5 video player.
 */

(function () {
  "use strict";

  const sniffedStreams = new Set();
  let floatingPanel = null;
  let activeVideoEl = null;

  /**
   * Helper to clean video title
   */
  function getVideoTitle() {
    const ytTitle = document.querySelector("h1.ytd-watch-metadata, #title h1, h1.title");
    if (ytTitle && ytTitle.innerText.trim()) {
      return ytTitle.innerText.trim().replace(/[\\/:*?"<>|]/g, "_");
    }
    let title = document.title || "video";
    title = title.replace(/ - YouTube$/, "").replace(/ - Vimeo$/, "").trim();
    return title.replace(/[\\/:*?"<>|]/g, "_") || "video";
  }

  /**
   * Initialize or retrieve the floating IDM panel
   */
  function ensureFloatingPanel() {
    if (floatingPanel && document.contains(floatingPanel)) {
      return floatingPanel;
    }

    const panel = document.createElement("div");
    panel.id = "idm-universal-video-panel";
    panel.className = "idm-universal-video-panel";

    const btn = document.createElement("button");
    btn.className = "idm-video-grabber-btn";
    btn.innerHTML = `
      <svg class="idm-grabber-icon" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
        <path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM17 13l-5 5-5-5h3V9h4v4h3z"/>
      </svg>
      <span class="idm-grabber-text">Download this video</span>
    `;

    const dropdown = document.createElement("div");
    dropdown.className = "idm-grabber-dropdown";

    function populateQualities() {
      dropdown.innerHTML = "";
      const currentUrl = window.location.href;
      const isYouTube = window.location.hostname.includes("youtube.com");

      const options = isYouTube
        ? [
            { label: "1080p 60fps (Full HD)", format: "MP4", url: currentUrl },
            { label: "720p HD", format: "MP4", url: currentUrl },
            { label: "480p SD", format: "MP4", url: currentUrl },
            { label: "360p Medium", format: "MP4", url: currentUrl },
            { label: "Audio Only (128k MP3)", format: "MP3", url: currentUrl },
          ]
        : [
            { label: "Original Stream / Best Quality", format: "MP4", url: currentUrl },
            { label: "720p HD", format: "MP4", url: currentUrl },
            { label: "480p SD", format: "MP4", url: currentUrl },
            { label: "Audio Track (MP3)", format: "MP3", url: currentUrl },
          ];

      // Add any dynamically sniffed stream URLs
      if (sniffedStreams.size > 0) {
        sniffedStreams.forEach((streamUrl) => {
          let label = "Stream (.m3u8 / .mp4)";
          if (streamUrl.includes(".m3u8")) label = "HLS Stream (Adaptive .m3u8)";
          else if (streamUrl.includes(".mpd")) label = "DASH Stream (.mpd)";
          else if (streamUrl.includes(".mp4")) label = "Direct MP4 Video Stream";
          options.unshift({ label: label, format: "MP4", url: streamUrl });
        });
      }

      options.forEach((opt) => {
        const item = document.createElement("div");
        item.className = "idm-grabber-item";
        item.innerHTML = `
          <span class="idm-item-title">${opt.label}</span>
          <span class="idm-item-tag">${opt.format}</span>
        `;
        item.addEventListener("click", (e) => {
          e.stopPropagation();
          e.preventDefault();
          dropdown.classList.remove("idm-show");

          const title = getVideoTitle();
          const filename = `${title}.${opt.format.toLowerCase()}`;

          chrome.runtime.sendMessage({
            action: "download_media",
            url: opt.url,
            filename: filename,
            format: opt.format.toLowerCase()
          });
        });
        dropdown.appendChild(item);
      });
    }

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      populateQualities();
      dropdown.classList.toggle("idm-show");
    });

    document.addEventListener("click", (e) => {
      if (!panel.contains(e.target)) {
        dropdown.classList.remove("idm-show");
      }
    });

    panel.appendChild(btn);
    panel.appendChild(dropdown);

    // Attach to root so it can never be clipped by overflow:hidden
    (document.fullscreenElement || document.body || document.documentElement).appendChild(panel);
    floatingPanel = panel;
    return panel;
  }

  /**
   * Position panel directly above the active video player
   */
  function updatePosition() {
    const video = activeVideoEl || document.querySelector("video");
    if (!video) {
      if (window.location.hostname.includes("youtube.com")) {
        const panel = ensureFloatingPanel();
        panel.style.display = "block";
        panel.style.top = "70px";
        panel.style.right = "24px";
      } else if (floatingPanel) {
        floatingPanel.style.display = "none";
      }
      return;
    }

    const panel = ensureFloatingPanel();
    const rect = video.getBoundingClientRect();

    if (rect.width > 80 && rect.height > 50 && rect.bottom > 0 && rect.top < window.innerHeight) {
      panel.style.display = "block";
      const topPos = Math.max(12, rect.top + 12);
      const rightPos = Math.max(16, (window.innerWidth - rect.right) + 16);
      panel.style.top = `${topPos}px`;
      panel.style.right = `${rightPos}px`;
    } else {
      // Fallback fixed position if player is on screen or video is playing
      panel.style.display = "block";
      panel.style.top = "70px";
      panel.style.right = "24px";
    }
  }

  /**
   * Scan page and hook all video elements
   */
  function scanAndHookVideos() {
    const videos = document.querySelectorAll("video, audio");
    if (videos.length > 0) {
      activeVideoEl = videos[0];
      videos.forEach((v) => {
        if (!v.dataset.idmHooked) {
          v.dataset.idmHooked = "true";
          v.addEventListener("mouseenter", () => {
            activeVideoEl = v;
            updatePosition();
          });
          v.addEventListener("play", () => {
            activeVideoEl = v;
            updatePosition();
          });
        }
      });
      updatePosition();
    } else if (window.location.hostname.includes("youtube.com")) {
      updatePosition();
    }
  }

  // Network Sniffing for Media Streams
  function setupSniffing() {
    const originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url) {
      if (typeof url === "string") {
        if (
          url.includes(".m3u8") ||
          url.includes(".mpd") ||
          url.includes("videoplayback") ||
          url.includes(".mp4") ||
          url.includes(".webm")
        ) {
          sniffedStreams.add(url);
          scanAndHookVideos();
        }
      }
      return originalOpen.apply(this, arguments);
    };

    const originalFetch = window.fetch;
    window.fetch = function (input, init) {
      const url = typeof input === "string" ? input : input ? input.url : "";
      if (
        url && (
          url.includes(".m3u8") ||
          url.includes(".mpd") ||
          url.includes("videoplayback") ||
          url.includes(".mp4") ||
          url.includes(".webm")
        )
      ) {
        sniffedStreams.add(url);
        scanAndHookVideos();
      }
      return originalFetch.apply(this, arguments);
    };
  }

  // Initialize
  setupSniffing();
  scanAndHookVideos();

  // Polling & Event Listeners
  setInterval(scanAndHookVideos, 1200);
  window.addEventListener("scroll", updatePosition, { passive: true });
  window.addEventListener("resize", updatePosition, { passive: true });
  document.addEventListener("fullscreenchange", () => {
    if (floatingPanel) {
      (document.fullscreenElement || document.body).appendChild(floatingPanel);
    }
    updatePosition();
  });

  // YouTube SPA navigation
  window.addEventListener("yt-navigate-finish", () => {
    sniffedStreams.clear();
    scanAndHookVideos();
  });

  // Extract all links
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "extract_all_links") {
      const anchors = document.querySelectorAll("a[href]");
      const links = [];
      anchors.forEach((a) => {
        const href = a.href;
        if (href && (href.startsWith("http://") || href.startsWith("https://") || href.startsWith("ftp://"))) {
          links.push({ url: href, text: (a.innerText || a.title || "").trim() });
        }
      });
      sendResponse({ links: links });
      return true;
    }
  });

})();
