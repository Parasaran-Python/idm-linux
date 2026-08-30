/**
 * IDM Linux - Classic Floating Video Grabber & Sniffer
 * Renders the iconic Windows IDM "Download this video" button above players with dismiss & drag options.
 */

(function () {
  "use strict";

  // Prevent multiple injections
  if (window.__idm_sniffer_injected) return;
  window.__idm_sniffer_injected = true;

  const capturedStreams = new Map(); // url -> { title, format, type }
  let floatingBar = null;
  let activePlayerEl = null;
  let userDismissed = false;
  let customPosition = null; // { x, y }
  const cachedFormatsForUrl = new Map();

  function fetchFormatsForCurrentPage() {
    const currentUrl = window.location.href;
    if (cachedFormatsForUrl.has(currentUrl)) return;

    try {
      chrome.runtime.sendMessage({ action: "query_media_formats", url: currentUrl }, (response) => {
        if (response && response.formats && response.formats.length > 0) {
          cachedFormatsForUrl.set(currentUrl, response.formats);
          if (floatingBar) {
            const openMenu = floatingBar.querySelector(".idm-grabber-menu.idm-menu-open");
            if (openMenu) {
              const populateFunc = floatingBar.__idmPopulateMenu;
              if (populateFunc) populateFunc();
            }
          }
        }
      });
    } catch (e) {}
  }

  /**
   * Inject Main-World Page Hook Script
   */
  function injectPageHook() {
    try {
      const script = document.createElement("script");
      script.src = chrome.runtime.getURL("content/page_hook.js");
      script.onload = function () {
        this.remove();
      };
      (document.head || document.documentElement).appendChild(script);
    } catch (e) {}
  }

  injectPageHook();

  /**
   * Helper to extract clean page/video title
   */
  function getMediaTitle() {
    const ytTitle = document.querySelector("h1.ytd-watch-metadata, #title h1, h1.title, .video-title");
    if (ytTitle && ytTitle.innerText.trim()) {
      return ytTitle.innerText.trim().replace(/[\\/:*?"<>|]/g, "_");
    }
    let title = document.title || "video";
    title = title.replace(/ - YouTube$/, "").replace(/ - Vimeo$/, "").trim();
    return title.replace(/[\\/:*?"<>|]/g, "_") || "video";
  }

  /**
   * Create the iconic IDM Floating Download Banner with Dismiss & Drag Options
   */
  function createFloatingDownloadBar() {
    if (floatingBar && document.contains(floatingBar)) {
      return floatingBar;
    }

    const container = document.createElement("div");
    container.id = "idm-floating-grabber-root";
    container.className = "idm-floating-grabber-root";

    const wrapper = document.createElement("div");
    wrapper.className = "idm-grabber-pill-wrapper";

    const dragHandle = document.createElement("div");
    dragHandle.className = "idm-grabber-drag-handle";
    dragHandle.title = "Drag to reposition IDM bar";
    dragHandle.innerHTML = `⠿`;

    const button = document.createElement("div");
    button.className = "idm-grabber-button";
    button.innerHTML = `
      <div class="idm-grabber-icon-box">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM17 13l-5 5-5-5h3V9h4v4h3z"/>
        </svg>
      </div>
      <span class="idm-grabber-label">Download this video</span>
      <span class="idm-grabber-arrow">▼</span>
    `;

    const closeBtn = document.createElement("button");
    closeBtn.className = "idm-grabber-close-btn";
    closeBtn.title = "Dismiss IDM download panel";
    closeBtn.innerHTML = "&times;";
    closeBtn.addEventListener("pointerdown", (e) => {
      e.stopPropagation();
      e.stopImmediatePropagation();
    });
    closeBtn.addEventListener("mousedown", (e) => {
      e.stopPropagation();
      e.stopImmediatePropagation();
    });
    closeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      e.stopImmediatePropagation();
      e.preventDefault();
      userDismissed = true;
      sessionStorage.setItem("__idm_dismissed_" + window.location.pathname, "true");
      container.style.display = "none";
      if (floatingBar) {
        floatingBar.remove();
        floatingBar = null;
      }
    });

    wrapper.appendChild(dragHandle);
    wrapper.appendChild(button);
    wrapper.appendChild(closeBtn);

    const menu = document.createElement("div");
    menu.className = "idm-grabber-menu";

    function populateMenu() {
      menu.innerHTML = "";
      const currentUrl = window.location.href;
      let items = [];

      // 1. If backend dynamic formats exist for this video, use exact real formats
      if (cachedFormatsForUrl.has(currentUrl) && cachedFormatsForUrl.get(currentUrl).length > 0) {
        items = [...cachedFormatsForUrl.get(currentUrl)];
      } else {
        // Trigger background format resolution
        fetchFormatsForCurrentPage();

        // 2. Add in-page sniffed media streams (HLS, DASH, direct MP4)
        if (capturedStreams.size > 0) {
          capturedStreams.forEach((meta, streamUrl) => {
            let label = meta.format || "Media Stream";
            if (streamUrl.includes(".m3u8")) label = "HLS Master Stream (.m3u8)";
            else if (streamUrl.includes(".mpd")) label = "DASH Video Stream (.mpd)";
            else if (streamUrl.includes(".mp4")) label = "Direct MP4 Stream";
            else if (streamUrl.includes(".webm")) label = "WebM Stream";
            items.push({ label: label, format: "MP4", quality: "best", url: streamUrl });
          });
        }

        // If empty, show loading indicator while fetching
        if (items.length === 0) {
          items.push({ label: "⏳ Extracting available formats...", format: "SCAN", quality: "best", url: currentUrl, disabled: true });
        }
      }

      items.forEach((item) => {
        const row = document.createElement("div");
        row.className = "idm-grabber-menu-item" + (item.disabled ? " idm-menu-item-disabled" : "");
        row.innerHTML = `
          <span class="idm-menu-item-text">${item.label}</span>
          <span class="idm-menu-item-badge">${item.format}</span>
        `;
        if (!item.disabled) {
          row.addEventListener("click", (e) => {
            e.stopPropagation();
            e.preventDefault();
            menu.classList.remove("idm-menu-open");

            const title = getMediaTitle();
            const filename = `${title}.${item.format.toLowerCase()}`;

            chrome.runtime.sendMessage({
              action: "download_media",
              url: item.url,
              filename: filename,
              quality: item.quality,
              format: item.format.toLowerCase()
            });
          });
        }
        menu.appendChild(row);
      });
    }

    // Dragging Logic - attached strictly to drag handle
    let isDragging = false;
    let dragStartX = 0, dragStartY = 0;
    let initialLeft = 0, initialTop = 0;
    let hasMoved = false;

    function onPointerDown(e) {
      isDragging = true;
      hasMoved = false;
      dragStartX = e.clientX;
      dragStartY = e.clientY;
      const rect = container.getBoundingClientRect();
      initialLeft = rect.left;
      initialTop = rect.top;
      window.addEventListener("pointermove", onPointerMove);
      window.addEventListener("pointerup", onPointerUp);
    }

    function onPointerMove(e) {
      if (!isDragging) return;
      const dx = e.clientX - dragStartX;
      const dy = e.clientY - dragStartY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
        hasMoved = true;
        container.classList.add("idm-is-dragging");
        const newX = Math.max(10, Math.min(window.innerWidth - 120, initialLeft + dx));
        const newY = Math.max(10, Math.min(window.innerHeight - 50, initialTop + dy));
        container.style.left = `${newX}px`;
        container.style.top = `${newY}px`;
        container.style.right = "auto";
        customPosition = { x: newX, y: newY };
      }
    }

    function onPointerUp(e) {
      if (!isDragging) return;
      isDragging = false;
      container.classList.remove("idm-is-dragging");
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    }

    dragHandle.addEventListener("pointerdown", onPointerDown);

    button.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      if (hasMoved) return; // Ignore click if drag occurred
      populateMenu();
      menu.classList.toggle("idm-menu-open");
    });

    document.addEventListener("click", (e) => {
      if (!container.contains(e.target)) {
        menu.classList.remove("idm-menu-open");
      }
    });

    container.appendChild(wrapper);
    container.appendChild(menu);
    container.__idmPopulateMenu = populateMenu;

    (document.fullscreenElement || document.body || document.documentElement).appendChild(container);
    floatingBar = container;
    fetchFormatsForCurrentPage();
    return container;
  }

  /**
   * Position the floating bar over the active video element
   */
  function repositionBar() {
    if (userDismissed || sessionStorage.getItem("__idm_dismissed_" + window.location.pathname) === "true") {
      if (floatingBar) {
        floatingBar.remove();
        floatingBar = null;
      }
      return;
    }

    const video = activePlayerEl || document.querySelector("video, audio, #movie_player, .html5-video-player");
    const isVideoSite =
      window.location.hostname.includes("youtube.com") ||
      window.location.hostname.includes("vimeo.com") ||
      window.location.hostname.includes("dailymotion.com") ||
      window.location.hostname.includes("twitch.tv") ||
      window.location.hostname.includes("twitter.com") ||
      window.location.hostname.includes("x.com");

    if (!video && !isVideoSite && capturedStreams.size === 0) {
      if (floatingBar) floatingBar.style.display = "none";
      return;
    }

    const bar = createFloatingDownloadBar();
    bar.style.display = "block";

    // If user dragged to custom location, preserve it
    if (customPosition) {
      bar.style.left = `${customPosition.x}px`;
      bar.style.top = `${customPosition.y}px`;
      bar.style.right = "auto";
      return;
    }

    if (video && video.getBoundingClientRect) {
      const rect = video.getBoundingClientRect();
      if (rect.width > 60 && rect.height > 40 && rect.bottom > 0 && rect.top < window.innerHeight) {
        bar.style.top = `${Math.max(14, rect.top + 14)}px`;
        bar.style.right = `${Math.max(16, (window.innerWidth - rect.right) + 16)}px`;
        bar.style.left = "auto";
        return;
      }
    }

    // Default top-right position
    bar.style.top = "70px";
    bar.style.right = "24px";
    bar.style.left = "auto";
  }

  /**
   * Scan page and hook player elements
   */
  function scanMediaElements() {
    const mediaEls = document.querySelectorAll("video, audio");
    if (mediaEls.length > 0) {
      activePlayerEl = mediaEls[0];
      mediaEls.forEach((el) => {
        if (!el.dataset.idmHooked) {
          el.dataset.idmHooked = "true";
          el.addEventListener("mouseenter", () => {
            activePlayerEl = el;
            repositionBar();
          });
          el.addEventListener("play", () => {
            activePlayerEl = el;
            repositionBar();
          });
        }
      });
      repositionBar();
    } else if (window.location.hostname.includes("youtube.com")) {
      repositionBar();
    }
  }

  // 1. Listen to Page Hook Custom Events
  document.addEventListener("__idm_media_event", (e) => {
    if (e.detail && e.detail.url) {
      capturedStreams.set(e.detail.url, { format: e.detail.type || "Stream" });
      repositionBar();
    }
  });

  // 2. Listen to Background Network Sniffer Messages
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === "idm_media_detected" && msg.streamUrl) {
      capturedStreams.set(msg.streamUrl, { format: msg.contentType || "Stream" });
      repositionBar();
    }
  });

  // 3. Initialize & Continuous Polling
  scanMediaElements();
  setInterval(scanMediaElements, 1200);
  window.addEventListener("scroll", repositionBar, { passive: true });
  window.addEventListener("resize", repositionBar, { passive: true });
  document.addEventListener("fullscreenchange", () => {
    if (floatingBar) {
      (document.fullscreenElement || document.body).appendChild(floatingBar);
    }
    repositionBar();
  });

  window.addEventListener("yt-navigate-finish", () => {
    userDismissed = false;
    customPosition = null;
    capturedStreams.clear();
    scanMediaElements();
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
