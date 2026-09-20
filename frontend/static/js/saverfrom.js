(function (global) {
  function isYouTube(url) {
    return /(?:youtube\.com|youtu\.be|youtube-nocookie\.com)/i.test(url || "");
  }

  function errorText(data, fallback) {
    if (!data) return fallback;
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map(function (item) { return item.msg || item; }).join(" ");
    }
    return data.message || data.error || fallback;
  }

  async function downloadToServer(sourceUrl, format) {
    const resp = await fetch("/api/v1/download-file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: sourceUrl, format: format || "best" }),
    });
    const data = await resp.json().catch(function () { return {}; });
    if (!resp.ok || data.success === false) {
      throw new Error(errorText(data, "Could not download this video."));
    }
    const fileUrl = data.file_url || data.download_url;
    if (!fileUrl) throw new Error("Download finished but no file was returned.");
    return fileUrl;
  }

  global.saverfromAttachDownload = function (dlBtn, sourceUrl, format, filename, resolved) {
    if (!dlBtn) return;
    const label = dlBtn.textContent;
    const platform = (resolved && resolved.platform) || "";
    const rawHint = (resolved && (resolved.download_url || resolved.url)) || "";
    const useServer =
      isYouTube(sourceUrl) ||
      platform === "youtube" ||
      /i\.ytimg\.com|storyboard|\.(jpg|png|webp)(\?|$)/i.test(rawHint);

    if (!useServer) {
      const raw = (resolved && (resolved.download_url || resolved.url)) || sourceUrl;
      dlBtn.href =
        "/api/v1/proxy-download?url=" +
        encodeURIComponent(raw) +
        "&filename=" +
        encodeURIComponent(filename || "video.mp4");
      dlBtn.setAttribute("download", filename || "video.mp4");
      dlBtn.setAttribute("target", "_blank");
      dlBtn.onclick = null;
      return;
    }

    dlBtn.removeAttribute("target");
    dlBtn.removeAttribute("download");
    dlBtn.href = "#download";
    dlBtn.onclick = async function (event) {
      event.preventDefault();
      if (dlBtn.dataset.busy === "1") return;
      dlBtn.dataset.busy = "1";
      dlBtn.textContent = "Preparing file...";
      try {
        const fileUrl = await downloadToServer(sourceUrl, format);
        const link = document.createElement("a");
        link.href = fileUrl;
        link.setAttribute("download", filename || "video.mp4");
        document.body.appendChild(link);
        link.click();
        link.remove();
      } catch (err) {
        const msg = err.message || "Download failed.";
        const box = document.getElementById("error-box") || document.getElementById("error-box-plat");
        const text = document.getElementById("error-msg") || document.getElementById("error-msg-plat");
        if (box && text) {
          text.textContent = msg;
          box.style.display = "flex";
        } else {
          alert(msg);
        }
      } finally {
        dlBtn.dataset.busy = "0";
        dlBtn.textContent = label;
      }
    };
  };
})(window);
