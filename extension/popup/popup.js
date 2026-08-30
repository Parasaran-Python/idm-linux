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
    if (res && res.status === "ok") {
      badge.textContent = "Connected";
      badge.className = "badge badge-connected";
    } else {
      badge.textContent = "Daemon Ready";
      badge.className = "badge badge-connected";
    }
  });

  // 2. Load Settings
  chrome.runtime.sendMessage({ action: "get_settings" }, (res) => {
    if (res && res.settings) {
      toggleIntercept.checked = !!res.settings.interceptDownloads;
      toggleSniffer.checked = !!res.settings.videoSniffer;
    }
  });

  toggleIntercept.addEventListener("change", () => {
    chrome.runtime.sendMessage({
      action: "save_settings",
      settings: { interceptDownloads: toggleIntercept.checked }
    });
  });

  toggleSniffer.addEventListener("change", () => {
    chrome.runtime.sendMessage({
      action: "save_settings",
      settings: { videoSniffer: toggleSniffer.checked }
    });
  });

  // 3. Direct URL Download (No modal prompt clipping!)
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

  // 4. Open Desktop Application
  btnOpenGui.addEventListener("click", () => {
    chrome.runtime.sendMessage({ action: "open_idm_gui" });
  });
});
