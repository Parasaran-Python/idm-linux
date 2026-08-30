/**
 * IDM Linux - Background Service Worker / Script
 * Intercepts downloads across all browsers (Firefox & Chrome) and provides Native Messaging Bridge.
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
  return new Promise((resolve) => {
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
  if (chrome.contextMenus) {
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
  }
});

if (chrome.contextMenus && chrome.contextMenus.onClicked) {
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
}

/**
 * Universal Browser Download Interception (Firefox + Chrome/Edge/Brave)
 */
const interceptedDownloadIds = new Set();

function handleDownloadIntercept(downloadItem) {
  if (!settings.interceptDownloads || !downloadItem || !downloadItem.url) {
    return;
  }

  // Avoid recursive loops
  if (interceptedDownloadIds.has(downloadItem.id)) {
    return;
  }

  const rawFilename = downloadItem.filename || "";
  const filename = rawFilename.split(/[/\\]/).pop() || "";
  const ext = filename.split(".").pop().toLowerCase();

  // If extension is in ignore list, skip
  if (ext && settings.ignoreExtensions.includes(ext)) {
    return;
  }

  // Intercept if matches configured extensions or binary MIME types or explicit download
  const mime = downloadItem.mime || "";
  const isTargetExt = settings.interceptExtensions.includes(ext);
  const isBinaryMime = mime.startsWith("video/") || mime.startsWith("audio/") ||
                       mime.includes("zip") || mime.includes("octet-stream") ||
                       mime.includes("pdf") || mime.includes("tar") || mime.includes("gzip");

  const shouldIntercept = isTargetExt || isBinaryMime || !ext || filename.length === 0;

  if (shouldIntercept) {
    interceptedDownloadIds.add(downloadItem.id);

    // Cancel native browser download
    if (chrome.downloads && chrome.downloads.cancel) {
      chrome.downloads.cancel(downloadItem.id, () => {
        if (chrome.downloads.erase) {
          chrome.downloads.erase({ id: downloadItem.id });
        }
      });
    }

    // Forward immediately to IDM Linux native app
    sendNativeMessage({
      action: "add_download",
      url: downloadItem.url,
      filename: filename || null,
      total_bytes: downloadItem.fileSize > 0 ? downloadItem.fileSize : (downloadItem.totalBytes > 0 ? downloadItem.totalBytes : 0),
      headers: {
        "Referer": downloadItem.referrer || downloadItem.url,
        "User-Agent": navigator.userAgent
      },
      start_immediately: true
    });
  }
}

// 1. Firefox & Chrome: onCreated download listener
if (chrome.downloads && chrome.downloads.onCreated) {
  chrome.downloads.onCreated.addListener((downloadItem) => {
    handleDownloadIntercept(downloadItem);
  });
}

// 2. Chrome / Edge / Brave: onDeterminingFilename listener
if (chrome.downloads && chrome.downloads.onDeterminingFilename) {
  chrome.downloads.onDeterminingFilename.addListener((downloadItem, suggest) => {
    handleDownloadIntercept(downloadItem);
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

  if (request.action === "open_idm_gui") {
    sendNativeMessage({ action: "open_gui" }).then(sendResponse);
    return true;
  }

  if (request.action === "download_media") {
    sendNativeMessage({
      action: "add_download",
      url: request.url,
      filename: request.filename,
      headers: {
        "Referer": sender.tab ? sender.tab.url : window.location ? window.location.href : "",
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
