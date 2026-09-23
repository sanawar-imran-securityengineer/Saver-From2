// ===== ReddSave — Reddit Video Downloader App =====

const ALLOWED_OPTION_VALUES = ['1080p', '720p', '360p', 'mp3']
const OPTION_LABELS = {
  '1080p': '1080p Full HD (Sound Included)',
  '720p': '720p HD (Sound Included)',
  '360p': '360p SD (Compact)',
  'mp3': 'MP3 Audio (Music / Voice)',
}

const ICONS = {
  snoo: `<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.56 1.25 1.25a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.703zM9.25 12C8.56 12 8 12.56 8 13.25c0 .69.56 1.25 1.25 1.25.69 0 1.25-.56 1.25-1.25 0-.69-.56-1.25-1.25-1.25zm5.5 0c-.69 0-1.25.56-1.25 1.25 0 .69.56 1.25 1.25 1.25.69 0 1.25-.56 1.25-1.25 0-.69-.56-1.25-1.25-1.25zm-5.465 4.316a.434.434 0 0 0-.11.605c.35.534 1.6 1.162 2.825 1.162 1.226 0 2.476-.628 2.826-1.162a.433.433 0 0 0-.715-.488c-.2.304-1.144.75-2.111.75-.967 0-1.912-.446-2.11-.75a.433.433 0 0 0-.605-.117z"/></svg>`,
  reddit: `<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.56 1.25 1.25a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.703zM9.25 12C8.56 12 8 12.56 8 13.25c0 .69.56 1.25 1.25 1.25.69 0 1.25-.56 1.25-1.25 0-.69-.56-1.25-1.25-1.25zm5.5 0c-.69 0-1.25.56-1.25 1.25 0 .69.56 1.25 1.25 1.25.69 0 1.25-.56 1.25-1.25 0-.69-.56-1.25-1.25-1.25zm-5.465 4.316a.434.434 0 0 0-.11.605c.35.534 1.6 1.162 2.825 1.162 1.226 0 2.476-.628 2.826-1.162a.433.433 0 0 0-.715-.488c-.2.304-1.144.75-2.111.75-.967 0-1.912-.446-2.11-.75a.433.433 0 0 0-.605-.117z"/></svg>`,
  download: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" width="18" height="18"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`,
  check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" width="18" height="18"><polyline points="20 6 9 17 4 12"/></svg>`,
  alert: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="20" height="20"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
  clipboard: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="15" height="15"><rect x="9" y="2" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
  refresh: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>`,
  chevronDown: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>`,
  hamburger: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>`,
  close: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
  volume: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>`,
  upvote: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 19V5M5 12l7-7 7 7"/></svg>`,
}

const FRIENDLY_ERRORS = {
  400: 'Please enter a valid Reddit post link (e.g. reddit.com/r/.../comments/... or v.redd.it).',
  404: 'The file could not be found.',
  413: 'The file is too large to process.',
  429: 'The server is busy. Please try again later.',
  500: 'This Reddit video could not be downloaded.',
  504: 'The download took too long and was stopped.',
}

// ── Reddit URL normalization & validation ──────────────────────────────────
function normalizeUrl(raw) {
  if (!raw || typeof raw !== 'string') return ''
  let u = raw.trim()
  const match = u.match(/https?:\/\/[^\s]+/)
  if (match) return match[0]
  const lower = u.toLowerCase()
  if (
    lower.startsWith('reddit.com') ||
    lower.startsWith('www.reddit.com') ||
    lower.startsWith('old.reddit.com') ||
    lower.startsWith('sh.reddit.com') ||
    lower.startsWith('m.reddit.com') ||
    lower.startsWith('redd.it') ||
    lower.startsWith('v.redd.it') ||
    lower.startsWith('twitter.com') ||
    lower.startsWith('x.com') ||
    lower.startsWith('youtube.com') ||
    lower.startsWith('youtu.be')
  ) {
    return 'https://' + u
  }
  return u
}

function isValidRedditUrl(rawUrl) {
  const url = normalizeUrl(rawUrl)
  if (!url || typeof url !== 'string' || url.length > 2048) return false
  try {
    const u = new URL(url)
    if (!u.protocol.startsWith('http')) return false
    const host = u.hostname.replace(/^www\./, '')
    if (['reddit.com', 'old.reddit.com', 'sh.reddit.com', 'm.reddit.com'].includes(host)) {
      return /(?:r\/[^/]+\/comments\/|comments\/|user\/[^/]+\/comments\/|r\/[^/]+\/s\/)/.test(u.pathname)
    }
    if (['redd.it', 'v.redd.it'].includes(host)) {
      return !!u.pathname.replace('/', '').trim()
    }
    if (['twitter.com', 'x.com', 'youtube.com', 'youtu.be', 'snapchat.com', 'bilibili.com', 'b23.tv'].includes(host)) {
      return !!u.pathname.replace('/', '').trim()
    }
    return false
  } catch {
    return false
  }
}

export function renderApp(root) {
  root.innerHTML = buildHTML()
  initInteractions(root)
}

function buildHTML() {
  const year = new Date().getFullYear()
  return `
<header class="site-header">
  <div class="header-inner">
    <a href="#home" class="logo-link" aria-label="ReddSave home">
      <div class="logo-icon">${ICONS.snoo}</div>
      <span class="logo-text">Redd<span class="logo-accent">Save</span></span>
    </a>
    <nav class="nav-desktop" aria-label="Main navigation">
      <a href="#home">Home</a>
      <a href="#how-it-works">How it works</a>
      <a href="#features">Features</a>
      <a href="#faq">FAQ</a>
    </nav>
    <button class="hamburger" id="hamburger" aria-label="Toggle menu" aria-expanded="false" aria-controls="nav-mobile">
      ${ICONS.hamburger}
    </button>
  </div>
  <nav class="nav-mobile" id="nav-mobile" aria-label="Mobile navigation">
    <a href="#home">Home</a>
    <a href="#how-it-works">How it works</a>
    <a href="#features">Features</a>
    <a href="#faq">FAQ</a>
  </nav>
</header>

<main>
  <!-- Hero + Downloader -->
  <section id="home" class="hero">
    <div class="hero-bg">
      <div class="hero-grid"></div>
      <div class="hero-glow-1"></div>
      <div class="hero-glow-2"></div>
    </div>

    <div class="hero-content">
      <div class="hero-badge">
        ${ICONS.snoo}
        <span>#1 Free Reddit Video Downloader with Audio</span>
      </div>
      <h1>Download Reddit Videos<br/><span class="reddit-accent">With Sound &amp; Audio in HD</span></h1>

      <div class="downloader-card" id="downloader-card">
        <div class="audio-highlight-bar">
          <span class="audio-tag">${ICONS.volume} <strong>Sound Guaranteed:</strong> Audio &amp; Video Merged into MP4</span>
          <span class="speed-tag">⚡ Ultra Fast &bull; No Watermark</span>
        </div>

        <form id="download-form" novalidate>
          <div class="input-row">
            <div class="url-input-wrap">
              <div class="reddit-icon">${ICONS.snoo}</div>
              <input
                type="url"
                id="url-input"
                name="url"
                placeholder="Paste Reddit post or v.redd.it URL (e.g. reddit.com/r/.../comments/...)"
                autocomplete="off"
                spellcheck="false"
                aria-label="Reddit post URL"
              />
              <button type="button" class="paste-btn" id="paste-btn" title="Paste from clipboard">
                ${ICONS.clipboard}
                <span>Paste</span>
              </button>
            </div>

            <select id="quality-select" name="option" class="quality-select">
              <option value="1080p">1080p Full HD (Sound)</option>
              <option value="720p" selected>720p HD (Sound)</option>
              <option value="360p">360p SD (Compact)</option>
              <option value="mp3">MP3 Audio Only</option>
            </select>

            <button type="submit" class="btn-download" id="download-btn">
              ${ICONS.download}
              <span>Download</span>
            </button>
          </div>

          <div id="url-status" class="url-status" aria-live="polite"></div>
        </form>

        <!-- Loading state -->
        <div class="loading-area" id="loading-area" hidden>
          <div class="loading-spinner">
            <div class="spinner-ring"></div>
          </div>
          <div class="loading-text">
            <p id="loading-msg">Fetching Reddit video &amp; audio...</p>
            <p class="loading-sub">Merging video and audio tracks with ffmpeg for crystal clear sound.</p>
          </div>
          <div class="progress-track">
            <div class="progress-fill"></div>
          </div>
        </div>

        <!-- Reddit Post Info Preview Card -->
        <div class="reddit-preview-card" id="info-preview" hidden>
          <div class="tweet-card-header">
            <div class="reddit-avatar">${ICONS.snoo}</div>
            <div class="tweet-user-meta">
              <div class="tweet-user-row">
                <span class="subreddit-tag" id="info-subreddit">r/reddit</span>
                <span class="tweet-author-name" id="info-author">Reddit Post</span>
              </div>
              <p class="tweet-text-content" id="info-title"></p>
            </div>
          </div>
          <div class="info-thumb-wrap">
            <img id="info-thumb" src="" alt="Reddit post preview" class="info-thumb" />
            <div class="info-thumb-overlay">
              <svg viewBox="0 0 24 24" fill="white" width="44" height="44">
                <circle cx="12" cy="12" r="11" fill="rgba(255, 69, 0, 0.85)"/>
                <polygon points="10,8 17,12 10,16" fill="white"/>
              </svg>
            </div>
            <span class="info-duration" id="info-duration"></span>
          </div>
          <div class="tweet-stats-row">
            <span class="tweet-stat-item upvotes">
              ${ICONS.upvote}
              <span id="info-views">Upvoted</span>
            </span>
            <span class="tweet-stat-item audio-status">
              ${ICONS.volume} Audio Synced
            </span>
          </div>
        </div>

        <!-- Error box -->
        <div class="error-box" id="error-box" role="alert" hidden>
          ${ICONS.alert}
          <span id="error-text"></span>
        </div>

        <!-- Result Card -->
        <div class="result-card" id="result-card" hidden aria-live="polite">
          <div class="result-header">
            <div class="result-check">${ICONS.check}</div>
            <span>Your Reddit Video is Ready!</span>
          </div>
          <div class="result-video-info" id="result-title"></div>
          <div class="result-meta-grid" id="result-meta-grid"></div>
          <div class="result-actions">
            <a href="#" class="btn-result-primary" id="download-file-btn" download>
              ${ICONS.download}
              <span>Download Video</span>
            </a>
            <button type="button" class="btn-result-ghost" id="copy-link-btn">
              ${ICONS.clipboard}
              <span>Copy Link</span>
            </button>
            <button type="button" class="btn-result-ghost" id="start-another-btn">
              ${ICONS.refresh}
              <span>Download Another</span>
            </button>
          </div>
        </div>
      </div>

      <p class="hero-legal">
        For publicly accessible Reddit posts and videos. Compliant with copyright laws and platform terms.
      </p>
    </div>
  </section>

  <!-- Format Strip -->
  <section class="formats-strip">
    <div class="container">
      <div class="format-chips">
        <div class="format-chip">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20"><rect x="2" y="3" width="20" height="14" rx="2"/><polyline points="8 21 12 17 16 21"/></svg>
          <div>
            <strong>1080p Full HD</strong>
            <span>Highest Quality with Audio</span>
          </div>
        </div>
        <div class="format-chip featured">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20"><rect x="2" y="3" width="20" height="14" rx="2"/><polyline points="8 21 12 17 16 21"/></svg>
          <div>
            <strong>720p HD</strong>
            <span>Crisp &amp; Fast Download</span>
          </div>
          <span class="chip-badge">Popular</span>
        </div>
        <div class="format-chip">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20"><rect x="2" y="3" width="20" height="14" rx="2"/><polyline points="8 21 12 17 16 21"/></svg>
          <div>
            <strong>360p SD</strong>
            <span>Small Size, Fast Save</span>
          </div>
        </div>
        <div class="format-chip">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
          <div>
            <strong>MP3 Audio</strong>
            <span>Pure Extracted Audio</span>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- How It Works -->
  <section id="how-it-works" class="section">
    <div class="container">
      <div class="section-header">
        <h2>How to Download Reddit Videos</h2>
        <p>Three simple steps to save any Reddit video, clip, or GIF with audio directly to your device.</p>
      </div>
      <div class="steps-grid">
        <div class="step-card">
          <div class="step-num">01</div>
          <div class="step-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="28" height="28"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
          </div>
          <h3>Copy Reddit Link</h3>
          <p>Open Reddit on the app or browser, tap <strong>Share</strong> under any video post, and choose <strong>Copy Link</strong>.</p>
        </div>
        <div class="step-card">
          <div class="step-num">02</div>
          <div class="step-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="28" height="28"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>
          </div>
          <h3>Paste &amp; Pick Quality</h3>
          <p>Paste the Reddit link into the search box above. Select 1080p, 720p HD with merged audio or MP3.</p>
        </div>
        <div class="step-card">
          <div class="step-num">03</div>
          <div class="step-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="28" height="28"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          </div>
          <h3>Download with Sound</h3>
          <p>Click <strong>Download</strong>. Your MP4 video is ready with sound fully synced to play on any device.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Features / Safety -->
  <section id="features" class="section section-alt">
    <div class="container">
      <div class="section-header">
        <h2>Why Use ReddSave?</h2>
        <p>Engineered to solve the common issues with Reddit video downloads.</p>
      </div>
      <div class="safety-grid">
        <div class="safety-card">
          <div class="safety-icon orange">${ICONS.volume}</div>
          <div>
            <h4>Sound &amp; Audio Merged (No Mute)</h4>
            <p>Reddit separates video and audio streams. ReddSave automatically combines both into a seamless MP4 with high-quality sound.</p>
          </div>
        </div>
        <div class="safety-card">
          <div class="safety-icon orange">${ICONS.snoo}</div>
          <div>
            <h4>Supports v.redd.it &amp; redd.it</h4>
            <p>Full support for all Reddit link formats including direct v.redd.it links, shortlinks, and subreddit post URLs.</p>
          </div>
        </div>
        <div class="safety-card">
          <div class="safety-icon green">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="22" height="22"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          </div>
          <div>
            <h4>No Login or App Required</h4>
            <p>Zero accounts, passwords, or cookies needed. Everything runs directly in your web browser 100% free.</p>
          </div>
        </div>
        <div class="safety-card">
          <div class="safety-icon black">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="22" height="22"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          </div>
          <div>
            <h4>Auto-Delete in 30 Minutes</h4>
            <p>Downloaded media files are automatically purged from our servers within 30 minutes for strict privacy.</p>
          </div>
        </div>
        <div class="safety-card">
          <div class="safety-icon orange">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="22" height="22"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          </div>
          <div>
            <h4>Multi-Layer In-Memory Cache</h4>
            <p>Cached videos are processed and served within milliseconds to eliminate wait times for trending videos.</p>
          </div>
        </div>
        <div class="safety-card">
          <div class="safety-icon green">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="22" height="22"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
          </div>
          <div>
            <h4>All Devices Supported</h4>
            <p>Works flawlessly across iPhone, iPad, Android, Windows, Mac, and Linux on Chrome, Safari, and Firefox.</p>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- FAQ -->
  <section id="faq" class="section">
    <div class="container">
      <div class="section-header">
        <h2>Frequently Asked Questions</h2>
        <p>Everything you need to know about downloading Reddit videos with sound.</p>
      </div>
      <div class="faq-list">
        <details class="faq-item">
          <summary class="faq-q">
            <span>Why do Reddit videos usually download without sound on other sites?</span>
            ${ICONS.chevronDown}
          </summary>
          <p class="faq-a">Reddit delivers videos using DASH (Dynamic Adaptive Streaming over HTTP), which stores video and audio in two completely separate streams. Many downloaders only grab the video stream, resulting in a muted file. ReddSave downloads both tracks and merges them together into a standard MP4 file with full sound.</p>
        </details>
        <details class="faq-item">
          <summary class="faq-q">
            <span>How do I download videos from the Reddit mobile app?</span>
            ${ICONS.chevronDown}
          </summary>
          <p class="faq-a">In the official Reddit app, find the video post you want to save. Tap the "Share" button beneath the post, then choose "Copy link". Come to ReddSave, paste the link, and click Download.</p>
        </details>
        <details class="faq-item">
          <summary class="faq-q">
            <span>Does ReddSave support direct v.redd.it links?</span>
            ${ICONS.chevronDown}
          </summary>
          <p class="faq-a">Yes! You can paste standard subreddit links (reddit.com/r/.../comments/...), short links (redd.it/...), or direct video URLs (v.redd.it/...). ReddSave detects all of them automatically.</p>
        </details>
        <details class="faq-item">
          <summary class="faq-q">
            <span>Can I extract only the audio as an MP3?</span>
            ${ICONS.chevronDown}
          </summary>
          <p class="faq-a">Yes! Simply choose "MP3 Audio Only" in the quality dropdown before hitting Download. ReddSave will extract and convert the audio track to a high-bitrate MP3.</p>
        </details>
        <details class="faq-item">
          <summary class="faq-q">
            <span>Is ReddSave free to use?</span>
            ${ICONS.chevronDown}
          </summary>
          <p class="faq-a">Yes, ReddSave is 100% free with no hidden fees, watermarks, or account registration required.</p>
        </details>
      </div>
    </div>
  </section>
</main>

<footer class="site-footer">
  <div class="container">
    <div class="footer-top">
      <div class="footer-brand">
        <div class="logo-link">
          <div class="logo-icon">${ICONS.snoo}</div>
          <span class="logo-text">Redd<span class="logo-accent">Save</span></span>
        </div>
        <p class="footer-tagline">Free Reddit Video Downloader with Sound &bull; HD MP4 &amp; MP3</p>
      </div>
      <div class="footer-links">
        <a href="#home">Home</a>
        <a href="#how-it-works">How it works</a>
        <a href="#features">Features</a>
        <a href="#faq">FAQ</a>
      </div>
    </div>
    <div class="footer-bottom">
      <p class="copyright-notice">
        Disclaimer: ReddSave is an independent web utility and is not affiliated, endorsed, or associated with Reddit Inc. All trademarks belong to their respective owners.
      </p>
      <p class="copyright-year">&copy; ${year} ReddSave. All rights reserved.</p>
    </div>
  </div>
</footer>
`
}

function initInteractions(root) {
  const form = root.querySelector('#download-form')
  const urlInput = root.querySelector('#url-input')
  const qualitySelect = root.querySelector('#quality-select')
  const downloadBtn = root.querySelector('#download-btn')
  const pasteBtn = root.querySelector('#paste-btn')
  const urlStatus = root.querySelector('#url-status')
  const loadingArea = root.querySelector('#loading-area')
  const infoPreview = root.querySelector('#info-preview')
  const errorBox = root.querySelector('#error-box')
  const errorText = root.querySelector('#error-text')
  const resultCard = root.querySelector('#result-card')
  const resultTitle = root.querySelector('#result-title')
  const resultMetaGrid = root.querySelector('#result-meta-grid')
  const downloadFileBtn = root.querySelector('#download-file-btn')
  const copyLinkBtn = root.querySelector('#copy-link-btn')
  const startAnotherBtn = root.querySelector('#start-another-btn')
  const hamburger = root.querySelector('#hamburger')
  const navMobile = root.querySelector('#nav-mobile')

  let infoDebounce = null

  // Mobile menu
  if (hamburger && navMobile) {
    hamburger.addEventListener('click', () => {
      const open = navMobile.classList.toggle('open')
      hamburger.setAttribute('aria-expanded', String(open))
    })
    navMobile.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => {
        navMobile.classList.remove('open')
        hamburger.setAttribute('aria-expanded', 'false')
      })
    })
  }

  // Paste button
  if (pasteBtn && urlInput) {
    pasteBtn.addEventListener('click', async () => {
      try {
        const text = await navigator.clipboard.readText()
        urlInput.value = text.trim()
        urlInput.dispatchEvent(new Event('input'))
      } catch {
        // clipboard access denied
      }
    })
  }

  // Input validation & info prefetch
  if (urlInput) {
    urlInput.addEventListener('input', () => {
      const val = normalizeUrl(urlInput.value)
      clearTimeout(infoDebounce)

      if (!val) {
        urlStatus.textContent = ''
        urlStatus.className = 'url-status'
        infoPreview.hidden = true
        return
      }

      if (isValidRedditUrl(val)) {
        urlStatus.textContent = '✓ Valid Reddit video link'
        urlStatus.className = 'url-status valid'

        infoDebounce = setTimeout(async () => {
          try {
            const res = await fetch(`/api/reddit/info?url=${encodeURIComponent(val)}`)
            if (!res.ok) return
            const data = await res.json()
            if (data && (data.title || data.thumbnail)) {
              root.querySelector('#info-title').textContent = data.title || 'Reddit Video'
              if (data.channel) {
                root.querySelector('#info-subreddit').textContent = data.channel.startsWith('r/') ? data.channel : `r/${data.channel}`
              }
              const thumb = root.querySelector('#info-thumb')
              if (data.thumbnail) {
                thumb.src = data.thumbnail
                thumb.hidden = false
              } else {
                thumb.hidden = true
              }
              const durEl = root.querySelector('#info-duration')
              if (data.duration) {
                const mins = Math.floor(data.duration / 60)
                const secs = String(data.duration % 60).padStart(2, '0')
                durEl.textContent = `${mins}:${secs}`
                durEl.hidden = false
              } else {
                durEl.hidden = true
              }
              infoPreview.hidden = false
            }
          } catch {
            // silent ignore
          }
        }, 500)
      } else {
        urlStatus.textContent = 'Please enter a valid Reddit post or video URL.'
        urlStatus.className = 'url-status invalid'
        infoPreview.hidden = true
      }
    })
  }

  // Form submit
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault()
      const rawUrl = urlInput.value.trim()
      const url = normalizeUrl(rawUrl)
      const option = qualitySelect.value

      errorBox.hidden = true
      resultCard.hidden = true

      if (!url) {
        errorText.textContent = 'Please enter a Reddit video URL.'
        errorBox.hidden = false
        return
      }

      if (!isValidRedditUrl(url)) {
        errorText.textContent = 'Please enter a valid Reddit post URL (e.g. reddit.com/r/.../comments/... or v.redd.it).'
        errorBox.hidden = false
        return
      }

      // Start download
      loadingArea.hidden = false
      downloadBtn.disabled = true
      downloadBtn.setAttribute('aria-busy', 'true')

      try {
        const res = await fetch('/api/reddit/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url, option }),
        })

        loadingArea.hidden = true
        downloadBtn.disabled = false
        downloadBtn.removeAttribute('aria-busy')

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}))
          const msg = errData.message || FRIENDLY_ERRORS[res.status] || 'This Reddit video could not be downloaded.'
          errorText.textContent = msg
          errorBox.hidden = false
          return
        }

        const data = await res.json()
        if (data.success && data.download_url) {
          resultTitle.textContent = data.title || 'Reddit Video'
          downloadFileBtn.href = data.download_url
          downloadFileBtn.setAttribute('download', data.filename || 'reddit-video.mp4')

          // Meta grid
          const sizeMB = data.file_size ? (data.file_size / (1024 * 1024)).toFixed(1) + ' MB' : 'Ready'
          resultMetaGrid.innerHTML = `
            <div class="meta-box"><div class="meta-label">Format</div><div class="meta-value">${data.quality_selected || option}</div></div>
            <div class="meta-box"><div class="meta-label">Audio</div><div class="meta-value" style="color: var(--color-green);">Merged &amp; Synced</div></div>
            <div class="meta-box"><div class="meta-label">File Size</div><div class="meta-value">${sizeMB}</div></div>
          `

          resultCard.hidden = false
          infoPreview.hidden = true
          resultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
        } else {
          errorText.textContent = 'Failed to prepare video file.'
          errorBox.hidden = false
        }
      } catch {
        loadingArea.hidden = true
        downloadBtn.disabled = false
        downloadBtn.removeAttribute('aria-busy')
        errorText.textContent = 'A connection error occurred. Please check your network and try again.'
        errorBox.hidden = false
      }
    })
  }

  // Copy link button
  if (copyLinkBtn && downloadFileBtn) {
    copyLinkBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(downloadFileBtn.href)
        copyLinkBtn.querySelector('span').textContent = 'Copied!'
        setTimeout(() => {
          copyLinkBtn.querySelector('span').textContent = 'Copy Link'
        }, 2000)
      } catch {
        // fallback
      }
    })
  }

  // Start another button
  if (startAnotherBtn && urlInput) {
    startAnotherBtn.addEventListener('click', () => {
      urlInput.value = ''
      urlStatus.textContent = ''
      urlStatus.className = 'url-status'
      resultCard.hidden = true
      errorBox.hidden = true
      infoPreview.hidden = true
      urlInput.focus()
    })
  }
}
