document.addEventListener("DOMContentLoaded", () => {
  const badge = document.getElementById("engine-badge");
  const toggleIntercept = document.getElementById("toggle-intercept");
  const toggleSniffer = document.getElementById("toggle-sniffer");
  const btnAddUrl = document.getElementById("btn-add-url");
  const btnOpenGui = document.getElementById("btn-open-gui");

  // Check IDM connection status
  chrome.runtime.sendMessage({ action: "ping_idm" }, (res) => {
    if (res && res.status === "ok") {
      badge.textContent = "Connected";
      badge.className = "badge badge-connected";
    } else {
      badge.textContent = "Daemon Offline";
      badge.className = "badge badge-disconnected";
    }
  });

  // Load Settings
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

  btnAddUrl.addEventListener("click", () => {
    const url = prompt("Enter URL to download with IDM:");
    if (url) {
      chrome.runtime.sendMessage({
        action: "download_media",
        url: url
      }, () => {
        alert("Download added to IDM!");
      });
    }
  });

  btnOpenGui.addEventListener("click", () => {
    chrome.runtime.sendMessage({ action: "ping_idm" });
  });
});
