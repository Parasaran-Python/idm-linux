/**
 * IDM Linux - Video Grabber & Sniffer Content Script
 * Supports YouTube, Vimeo, Dailymotion, HTML5 players, HLS (.m3u8), DASH (.mpd), and Blob streams.
 */

(function () {
  "use strict";

  const detectedStreams = new Set();
  let panelAttached = false;

  /**
   * Helper: Get current clean video title
   */
  function getMediaTitle() {
    // YouTube title selector
    const ytTitle = document.querySelector("h1.ytd-watch-metadata, #title h1, h1.title");
    if (ytTitle && ytTitle.innerText.trim()) {
      return ytTitle.innerText.trim();
    }
    // Generic page title
    let title = document.title || "Video";
    title = title.replace(/ - YouTube$/, "").replace(/ - Vimeo$/, "").trim();
    return title.replace(/[\\/:*?"<>|]/g, "_");
  }

  /**
   * Create and attach the iconic floating IDM "Download this video" button
   */
  function attachFloatingDownloadBar(targetElement) {
    if (document.getElementById("idm-floating-panel")) {
      return;
    }

    const panel = document.createElement("div");
    panel.id = "idm-floating-panel";
    panel.className = "idm-floating-panel";

    const btn = document.createElement("button");
    btn.className = "idm-floating-btn";
    btn.innerHTML = `
      <svg class="idm-svg-icon" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
        <path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM17 13l-5 5-5-5h3V9h4v4h3z"/>
      </svg>
      <span class="idm-btn-text">Download this video</span>
    `;

    const dropdown = document.createElement("div");
    dropdown.className = "idm-dropdown-menu";

    function populateDropdown() {
      dropdown.innerHTML = "";
      const isYouTube = window.location.hostname.includes("youtube.com");
      const currentUrl = window.location.href;

      const qualities = isYouTube
        ? [
            { label: "1080p 60fps (Full HD)", format: "MP4", url: currentUrl },
            { label: "720p HD", format: "MP4", url: currentUrl },
            { label: "480p SD", format: "MP4", url: currentUrl },
            { label: "360p Medium", format: "MP4", url: currentUrl },
            { label: "Audio Only (128k MP3)", format: "MP3", url: currentUrl },
          ]
        : [
            { label: "Original / Best Quality", format: "MP4", url: currentUrl },
            { label: "720p HD", format: "MP4", url: currentUrl },
            { label: "480p SD", format: "MP4", url: currentUrl },
            { label: "Audio Track (MP3)", format: "MP3", url: currentUrl },
          ];

      // If specific sniffed stream URLs were detected, list them
      if (detectedStreams.size > 0) {
        detectedStreams.forEach((streamUrl) => {
          let label = "Stream (.m3u8 / .mp4)";
          if (streamUrl.includes(".m3u8")) label = "HLS Stream (Adaptive .m3u8)";
          else if (streamUrl.includes(".mpd")) label = "DASH Stream (.mpd)";
          else if (streamUrl.includes(".mp4")) label = "Direct MP4 Stream";
          qualities.unshift({ label: label, format: "MP4", url: streamUrl });
        });
      }

      qualities.forEach((q) => {
        const item = document.createElement("div");
        item.className = "idm-dropdown-item";
        item.innerHTML = `
          <span class="idm-item-label">${q.label}</span>
          <span class="idm-item-badge">${q.format}</span>
        `;
        item.addEventListener("click", (e) => {
          e.stopPropagation();
          e.preventDefault();
          dropdown.classList.remove("idm-show");

          const title = getMediaTitle();
          const filename = `${title}.${q.format.toLowerCase()}`;

          chrome.runtime.sendMessage({
            action: "download_media",
            url: q.url,
            filename: filename,
            format: q.format.toLowerCase()
          });
        });
        dropdown.appendChild(item);
      });
    }

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      populateDropdown();
      dropdown.classList.toggle("idm-show");
    });

    // Close dropdown on outside click
    document.addEventListener("click", (e) => {
      if (!panel.contains(e.target)) {
        dropdown.classList.remove("idm-show");
      }
    });

    panel.appendChild(btn);
    panel.appendChild(dropdown);

    // Attach to video parent or player container
    const playerContainer =
      document.querySelector("#movie_player, .html5-video-player, .player-container, .video-container") ||
      (targetElement && targetElement.parentElement) ||
      document.body;

    if (playerContainer && playerContainer !== document.body) {
      const pos = window.getComputedStyle(playerContainer).position;
      if (pos === "static") {
        playerContainer.style.position = "relative";
      }
      playerContainer.appendChild(panel);
    } else {
      document.body.appendChild(panel);
    }

    panelAttached = true;
  }

  /**
   * Continuous scanner for video elements and streaming players
   */
  function scanForPlayers() {
    const video = document.querySelector("video, audio");
    const isVideoSite =
      window.location.hostname.includes("youtube.com") ||
      window.location.hostname.includes("vimeo.com") ||
      window.location.hostname.includes("dailymotion.com") ||
      window.location.hostname.includes("twitch.tv") ||
      window.location.hostname.includes("twitter.com") ||
      window.location.hostname.includes("x.com");

    if (video || isVideoSite) {
      attachFloatingDownloadBar(video);
    }
  }

  // Intercept XHR and fetch for media stream URLs (.m3u8, .mpd, videoplayback)
  function setupNetworkSniffing() {
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
          detectedStreams.add(url);
          scanForPlayers();
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
        detectedStreams.add(url);
        scanForPlayers();
      }
      return originalFetch.apply(this, arguments);
    };
  }

  // Initialize
  setupNetworkSniffing();
  scanForPlayers();

  // Polling fallback to ensure player detection across all SPAs
  setInterval(scanForPlayers, 1500);
  document.addEventListener("play", scanForPlayers, true);
  document.addEventListener("playing", scanForPlayers, true);
  document.addEventListener("loadedmetadata", scanForPlayers, true);

  // Watch DOM mutations and YouTube page transitions
  const observer = new MutationObserver(() => {
    scanForPlayers();
  });
  observer.observe(document.documentElement || document.body, { childList: true, subtree: true });

  // YouTube navigation event
  window.addEventListener("yt-navigate-finish", () => {
    panelAttached = false;
    const existing = document.getElementById("idm-floating-panel");
    if (existing) existing.remove();
    setTimeout(scanForPlayers, 300);
  });

  // Extract all links command
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
