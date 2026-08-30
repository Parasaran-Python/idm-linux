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

  // 4. In-page Player Format & Quality Discovery
  function extractVideoPlayerFormats() {
    try {
      const currentUrl = window.location.href;

      // 4a. YouTube Player Quality Levels & StreamingData
      const ytPlayer = document.querySelector("#movie_player");
      const ytResp = window.ytInitialPlayerResponse;

      if (ytResp && ytResp.streamingData) {
        const formats = [];
        const adaptive = (ytResp.streamingData.adaptiveFormats || []).concat(ytResp.streamingData.formats || []);
        const seen = new Set();
        for (const f of adaptive) {
          if (f.height && !seen.has(f.height)) {
            seen.add(f.height);
            let label = f.qualityLabel || `${f.height}p`;
            if (f.height >= 2160) label += " (4K Ultra HD)";
            else if (f.height >= 1440) label += " (2K Quad HD)";
            else if (f.height >= 1080) label += " (Full HD)";
            else if (f.height >= 720) label += " (HD)";
            else label += " (SD)";
            formats.push({
              label: label,
              height: f.height,
              quality: String(f.height),
              format: "MP4",
              filesize: parseInt(f.contentLength || 0, 10),
              url: currentUrl
            });
          }
        }
        formats.sort((a, b) => b.height - a.height);
        if (formats.length > 0) {
          formats.push({
            label: "Audio Only (MP3)",
            height: 0,
            quality: "audio",
            format: "MP3",
            filesize: 0,
            url: currentUrl
          });
          document.dispatchEvent(new CustomEvent("__idm_discovered_formats", {
            detail: { url: currentUrl, formats: formats }
          }));
          return;
        }
      }

      // 4b. YouTube Player API Fallback (getAvailableQualityLevels)
      if (ytPlayer && typeof ytPlayer.getAvailableQualityLevels === "function") {
        const levels = ytPlayer.getAvailableQualityLevels();
        if (Array.isArray(levels) && levels.length > 0) {
          const levelMap = {
            "highres": { label: "4K+ Original (Highest Quality)", quality: "2160", height: 2160 },
            "hd2880": { label: "5K 2880p (Ultra HD)", quality: "2880", height: 2880 },
            "hd2160": { label: "4K 2160p (Ultra HD)", quality: "2160", height: 2160 },
            "hd1440": { label: "2K 1440p (Quad HD)", quality: "1440", height: 1440 },
            "hd1080": { label: "1080p (Full HD)", quality: "1080", height: 1080 },
            "hd720": { label: "720p (HD)", quality: "720", height: 720 },
            "large": { label: "480p (SD)", quality: "480", height: 480 },
            "medium": { label: "360p (SD)", quality: "360", height: 360 },
            "small": { label: "240p (SD)", quality: "240", height: 240 },
            "tiny": { label: "144p (SD)", quality: "144", height: 144 }
          };
          const formats = [];
          for (const lvl of levels) {
            if (levelMap[lvl]) {
              formats.push({
                label: levelMap[lvl].label,
                quality: levelMap[lvl].quality,
                height: levelMap[lvl].height,
                format: "MP4",
                filesize: 0,
                url: currentUrl
              });
            }
          }
          if (formats.length > 0) {
            formats.push({
              label: "Audio Only (MP3)",
              quality: "audio",
              height: 0,
              format: "MP3",
              filesize: 0,
              url: currentUrl
            });
            document.dispatchEvent(new CustomEvent("__idm_discovered_formats", {
              detail: { url: currentUrl, formats: formats }
            }));
          }
        }
      }
    } catch (e) {}
  }

  setInterval(extractVideoPlayerFormats, 1000);

})();
