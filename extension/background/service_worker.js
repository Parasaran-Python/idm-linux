/**
 * IDM Linux - Background Service Worker (Native Messaging & Download Dispatcher)
 */

const NATIVE_HOST = "com.idm.linux.native_host";

// Default settings
let settings = {
  interceptDownloads: true,
  videoSniffer: true,
  minVideoSize: 1024 * 1024, // 1MB
  interceptExtensions: [
    "3gp", "7z", "aac", "ace", "aif", "apk", "appimage", "arj", "asf", "avi", "bin", "bz2",
    "deb", "dmg", "doc", "docx", "epub", "exe", "flac", "flv", "gz", "iso", "jar", "m4a",
    "m4v", "mkv", "mov", "mp3", "mp4", "mpa", "mpe", "mpeg", "mpg", "msi", "ogg", "opus",
    "pdf", "pkg", "ppt", "pptx", "rar", "rpm", "rtf", "sh", "tar", "tgz", "torrent", "ts",
    "txt", "wav", "webm", "wma", "wmv", "xls", "xlsx", "xz", "zip", "zst"
  ],
  ignoreExtensions: ["html", "htm", "php", "asp", "aspx", "jsp", "css", "js", "json", "xml"]
};

// Load saved settings
chrome.storage.local.get(["idmSettings"], (res) => {
  if (res.idmSettings) {
    settings = Object.assign(settings, res.idmSettings);
  }
});

/**
 * Send request to IDM Native Messaging Host
 */
function sendNativeMessage(payload) {
  return new Promise((resolve, reject) => {
    try {
      chrome.runtime.sendNativeMessage(NATIVE_HOST, payload, (response) => {
        if (chrome.runtime.lastError) {
          console.warn("[IDM Extension] Native messaging warning:", chrome.runtime.lastError.message);
          resolve({ status: "error", error: chrome.runtime.lastError.message });
        } else {
          resolve(response || { status: "ok" });
        }
      });
    } catch (e) {
      console.error("[IDM Extension] Native messaging failed:", e);
      resolve({ status: "error", error: e.toString() });
    }
  });
}

/**
 * Context Menus Setup
 */
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "idm_download_link",
    title: "Download with IDM",
    contexts: ["link", "image", "video", "audio"]
  });

  chrome.contextMenus.create({
    id: "idm_download_all",
    title: "Download all links with IDM",
    contexts: ["page", "selection"]
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "idm_download_link") {
    const targetUrl = info.linkUrl || info.srcUrl || info.pageUrl;
    if (targetUrl) {
      sendNativeMessage({
        action: "add_download",
        url: targetUrl,
        headers: {
          "Referer": tab ? tab.url : "",
          "User-Agent": navigator.userAgent
        },
        start_immediately: true
      });
    }
  } else if (info.menuItemId === "idm_download_all") {
    if (tab && tab.id) {
      chrome.tabs.sendMessage(tab.id, { action: "extract_all_links" }, (response) => {
        if (response && response.links && response.links.length > 0) {
          for (const link of response.links) {
            sendNativeMessage({
              action: "add_download",
              url: link.url,
              filename: link.text || null,
              headers: { "Referer": tab.url },
              start_immediately: false
            });
          }
        }
      });
    }
  }
});

/**
 * Intercept standard browser downloads
 */
if (chrome.downloads && chrome.downloads.onDeterminingFilename) {
  chrome.downloads.onDeterminingFilename.addListener((downloadItem, suggest) => {
    if (!settings.interceptDownloads) {
      return;
    }

    const filename = downloadItem.filename || "";
    const ext = filename.split(".").pop().toLowerCase();

    // Check if extension is in intercept list
    const shouldIntercept = settings.interceptExtensions.includes(ext) ||
      (downloadItem.mime && (
        downloadItem.mime.startsWith("video/") ||
        downloadItem.mime.startsWith("audio/") ||
        downloadItem.mime.includes("zip") ||
        downloadItem.mime.includes("octet-stream")
      ));

    if (shouldIntercept && !settings.ignoreExtensions.includes(ext)) {
      // Cancel native browser download
      chrome.downloads.cancel(downloadItem.id, () => {
        chrome.downloads.erase({ id: downloadItem.id });
      });

      // Forward to IDM Native Messaging
      sendNativeMessage({
        action: "add_download",
        url: downloadItem.url,
        filename: filename,
        total_bytes: downloadItem.fileSize > 0 ? downloadItem.fileSize : 0,
        headers: {
          "Referer": downloadItem.referrer || "",
          "User-Agent": navigator.userAgent
        },
        start_immediately: true
      });
    }
  });
}

/**
 * Message Dispatcher (from content scripts & popup)
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "ping_idm") {
    sendNativeMessage({ action: "ping" }).then(sendResponse);
    return true;
  }

  if (request.action === "download_media") {
    sendNativeMessage({
      action: "add_download",
      url: request.url,
      filename: request.filename,
      headers: {
        "Referer": sender.tab ? sender.tab.url : "",
        "User-Agent": navigator.userAgent
      },
      start_immediately: true
    }).then(sendResponse);
    return true;
  }

  if (request.action === "get_settings") {
    sendResponse({ settings: settings });
    return true;
  }

  if (request.action === "save_settings") {
    settings = Object.assign(settings, request.settings);
    chrome.storage.local.set({ idmSettings: settings }, () => {
      sendResponse({ status: "ok" });
    });
    return true;
  }
});
