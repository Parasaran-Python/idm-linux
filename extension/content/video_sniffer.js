/**
 * IDM Linux - Video Sniffer & Floating Download Panel Content Script
 */

(function () {
  "use strict";

  const detectedMedia = new Map(); // video element -> list of media streams

  /**
   * Create or update floating download button for a video element
   */
  function attachDownloadPanel(videoEl, mediaInfo) {
    if (videoEl.dataset.idmAttached) {
      return;
    }
    videoEl.dataset.idmAttached = "true";

    const container = document.createElement("div");
    container.className = "idm-video-panel-container";

    const btn = document.createElement("button");
    btn.className = "idm-video-btn";
    btn.innerHTML = `
      <span class="idm-icon">📥</span>
      <span class="idm-btn-text">Download this video</span>
    `;

    const dropdown = document.createElement("div");
    dropdown.className = "idm-dropdown-menu";

    // Populate dropdown with quality / stream options
    const options = [
      { label: "Full HD (1080p / Direct)", url: mediaInfo.url, format: "MP4" },
      { label: "HD (720p)", url: mediaInfo.url, format: "MP4" },
      { label: "Audio Only (MP3)", url: mediaInfo.url, format: "MP3" }
    ];

    options.forEach((opt) => {
      const item = document.createElement("div");
      item.className = "idm-dropdown-item";
      item.innerHTML = `
        <span class="idm-item-label">${opt.label}</span>
        <span class="idm-item-badge">${opt.format}</span>
      `;
      item.addEventListener("click", (e) => {
        e.stopPropagation();
        e.preventDefault();
        dropdown.classList.remove("idm-show");

        const pageTitle = document.title.replace(/[\\/:*?"<>|]/g, "_").trim() || "video";
        const filename = `${pageTitle}.${opt.format.toLowerCase()}`;

        chrome.runtime.sendMessage({
          action: "download_media",
          url: opt.url,
          filename: filename
        });
      });
      dropdown.appendChild(item);
    });

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      dropdown.classList.toggle("idm-show");
    });

    // Close dropdown on outside click
    document.addEventListener("click", (e) => {
      if (!container.contains(e.target)) {
        dropdown.classList.remove("idm-show");
      }
    });

    container.appendChild(btn);
    container.appendChild(dropdown);

    // Position container relative to video player
    const parent = videoEl.parentElement;
    if (parent && parent !== document.body) {
      const computedPos = window.getComputedStyle(parent).position;
      if (computedPos === "static") {
        parent.style.position = "relative";
      }
      parent.appendChild(container);
    } else {
      document.body.appendChild(container);
    }
  }

  /**
   * Scan page for HTML5 media elements
   */
  function scanMediaElements() {
    const videos = document.querySelectorAll("video, audio");
    videos.forEach((el) => {
      let src = el.currentSrc || el.src;
      if (!src) {
        const source = el.querySelector("source");
        if (source) {
          src = source.src;
        }
      }

      if (src && !src.startsWith("blob:") && !src.startsWith("data:")) {
        attachDownloadPanel(el, { url: src });
      }
    });
  }

  // Initial scan
  scanMediaElements();

  // Watch for dynamic video injection (e.g. YouTube, Netflix, Twitter, Vimeo)
  const observer = new MutationObserver(() => {
    scanMediaElements();
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true
  });

  // Extract all links on page for "Download all with IDM"
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "extract_all_links") {
      const anchors = document.querySelectorAll("a[href]");
      const links = [];
      anchors.forEach((a) => {
        const href = a.href;
        if (href && (href.startsWith("http://") || href.startsWith("https://") || href.startsWith("ftp://"))) {
          links.push({
            url: href,
            text: (a.innerText || a.title || "").trim()
          });
        }
      });
      sendResponse({ links: links });
      return true;
    }
  });

})();
