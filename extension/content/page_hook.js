/**
 * IDM Linux - Main World Page Hook Script
 * Injected into the webpage context to capture HTML5 media element sources, fetch, and XHR media streams.
 */

(function () {
  "use strict";

  function reportMedia(url, type) {
    if (!url || typeof url !== "string") return;
    if (url.startsWith("data:") || url.startsWith("blob:null")) return;

    // Check media signatures
    const isMedia =
      url.includes(".m3u8") ||
      url.includes(".mpd") ||
      url.includes("videoplayback") ||
      url.includes(".mp4") ||
      url.includes(".webm") ||
      url.includes(".ts") ||
      url.includes(".m4s") ||
      url.includes(".m4a") ||
      url.includes(".mp3") ||
      url.includes(".flv") ||
      url.includes(".ogg") ||
      url.includes("mime=video") ||
      url.includes("mime=audio");

    if (isMedia || type === "video" || type === "audio") {
      try {
        const event = new CustomEvent("__idm_media_event", {
          detail: { url: url, type: type || "video" }
        });
        document.dispatchEvent(event);
      } catch (e) {}
    }
  }

  // 1. Hook HTMLMediaElement (video / audio)
  const origPlay = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    const src = this.currentSrc || this.src;
    if (src) {
      reportMedia(src, this.tagName.toLowerCase());
    }
    return origPlay.apply(this, arguments);
  };

  // 2. Hook XHR
  const origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    if (typeof url === "string") {
      reportMedia(url, "stream");
    }
    return origOpen.apply(this, arguments);
  };

  // 3. Hook fetch
  const origFetch = window.fetch;
  window.fetch = function (input, init) {
    const url = typeof input === "string" ? input : input ? input.url : "";
    if (url) {
      reportMedia(url, "stream");
    }
    return origFetch.apply(this, arguments);
  };

})();
