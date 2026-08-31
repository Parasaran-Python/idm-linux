document.addEventListener("DOMContentLoaded", () => {
  const badge = document.getElementById("engine-badge");
  const toggleIntercept = document.getElementById("toggle-intercept");
  const toggleSniffer = document.getElementById("toggle-sniffer");
  const inputUrl = document.getElementById("input-url");
  const btnStartDownload = document.getElementById("btn-start-download");
  const btnOpenGui = document.getElementById("btn-open-gui");
  const feedback = document.getElementById("url-feedback");

  // 1. Check IDM connection status
  chrome.runtime.sendMessage({ action: "ping_idm" }, (res) => {
    if (chrome.runtime.lastError || !res || res.status !== "ok") {
      badge.textContent = "Disconnected";
      badge.className = "badge badge-disconnected";
    } else {
      badge.textContent = "Connected";
      badge.className = "badge badge-connected";
    }
  });

  // 2. Load Settings
  chrome.runtime.sendMessage({ action: "get_settings" }, (res) => {
    if (chrome.runtime.lastError) return;
    if (res && res.settings) {
      toggleIntercept.checked = !!res.settings.interceptDownloads;
      toggleSniffer.checked = !!res.settings.videoSniffer;
    }
  });

  toggleIntercept.addEventListener("change", () => {
    chrome.runtime.sendMessage({
      action: "save_settings",
      settings: { interceptDownloads: toggleIntercept.checked }
    }, () => {
      if (chrome.runtime.lastError) { /* ignore */ }
    });
  });

  toggleSniffer.addEventListener("change", () => {
    chrome.runtime.sendMessage({
      action: "save_settings",
      settings: { videoSniffer: toggleSniffer.checked }
    }, () => {
      if (chrome.runtime.lastError) { /* ignore */ }
    });
  });

  // 3. Direct URL Download
  function submitDownload() {
    const url = inputUrl.value.trim();
    if (!url) {
      feedback.textContent = "⚠️ Please paste a valid URL.";
      feedback.className = "feedback-msg error";
      return;
    }

    if (!url.startsWith("http://") && !url.startsWith("https://") && !url.startsWith("ftp://")) {
      feedback.textContent = "⚠️ URL must begin with http:// or https://";
      feedback.className = "feedback-msg error";
      return;
    }

    feedback.textContent = "⏳ Adding download to IDM...";
    feedback.className = "feedback-msg";

    chrome.runtime.sendMessage({
      action: "download_media",
      url: url
    }, (res) => {
      if (chrome.runtime.lastError) {
        feedback.textContent = `❌ ${chrome.runtime.lastError.message || "Failed to communicate with extension."}`;
        feedback.className = "feedback-msg error";
        return;
      }
      if (res && res.status === "ok") {
        feedback.textContent = "✅ Download started in IDM!";
        feedback.className = "feedback-msg success";
        inputUrl.value = "";
        setTimeout(() => {
          window.close();
        }, 1200);
      } else {
        feedback.textContent = `❌ ${res && res.error ? res.error : "Failed to add download."}`;
        feedback.className = "feedback-msg error";
      }
    });
  }

  btnStartDownload.addEventListener("click", submitDownload);
  inputUrl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      submitDownload();
    }
  });

  // 4. Detected Active Tab Media Streams
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (chrome.runtime.lastError) return;
    if (tabs && tabs[0] && tabs[0].id) {
      const activeTab = tabs[0];
      chrome.runtime.sendMessage({ action: "get_tab_media", tabId: activeTab.id }, (res) => {
        if (chrome.runtime.lastError) return;
        if (res && res.streams && res.streams.length > 0) {
          const mediaCard = document.getElementById("media-card");
          const mediaList = document.getElementById("media-list");
          if (mediaCard && mediaList) {
            mediaCard.style.display = "block";
            mediaList.innerHTML = "";
            res.streams.slice(0, 10).forEach((streamUrl) => {
              if (streamUrl.includes("videoplayback") && streamUrl.includes("range=")) {
                return;
              }
              let label = "Video Stream";
              let badge = "STREAM";
              if (streamUrl.includes(".m3u8")) { label = "HLS Video Stream"; badge = "HLS"; }
              else if (streamUrl.includes(".mpd")) { label = "DASH Video Stream"; badge = "DASH"; }
              else if (streamUrl.includes(".mp4")) { label = "Direct MP4 Video"; badge = "MP4"; }
              else if (streamUrl.includes(".webm")) { label = "Direct WebM Video"; badge = "WEBM"; }
              else if (streamUrl.includes(".mp3") || streamUrl.includes(".m4a")) { label = "Audio Stream"; badge = "MP3"; }
              else if (streamUrl.includes("youtube.com") || streamUrl.includes("youtu.be")) { label = "YouTube Video"; badge = "YOUTUBE"; }

              const item = document.createElement("div");
              item.className = "media-item";
              item.title = streamUrl;
              item.innerHTML = `<span class="media-item-title">${label}</span><span class="media-item-badge">${badge}</span>`;
              item.addEventListener("click", () => {
                const title = activeTab.title ? activeTab.title.replace(/[\\/:*?"<>|]/g, "_").trim() : "video";
                const ext = badge.toLowerCase() === "hls" || badge.toLowerCase() === "dash" || badge.toLowerCase() === "youtube" ? "mp4" : badge.toLowerCase();
                chrome.runtime.sendMessage({
                  action: "download_media",
                  url: streamUrl,
                  filename: `${title}.${ext}`,
                  quality: "best"
                }, () => {
                  if (chrome.runtime.lastError) { /* ignore */ }
                  window.close();
                });
              });
              mediaList.appendChild(item);
            });
          }
        }
      });
    }
  });

  // 5. Open Desktop Application
  btnOpenGui.addEventListener("click", () => {
    chrome.runtime.sendMessage({ action: "open_idm_gui" }, () => {
      if (chrome.runtime.lastError) { /* ignore */ }
    });
  });
});
