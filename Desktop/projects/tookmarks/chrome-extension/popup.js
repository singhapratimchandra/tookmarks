const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const statusDiv = document.getElementById('status');
const countEl = document.getElementById('count');
const progressEl = document.getElementById('progress');
const errorEl = document.getElementById('error');

let pollInterval = null;

startBtn.addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab.url.includes('x.com/i/bookmarks') && !tab.url.includes('twitter.com/i/bookmarks')) {
    errorEl.textContent = 'Please navigate to x.com/i/bookmarks first!';
    errorEl.style.display = 'block';
    return;
  }

  errorEl.style.display = 'none';
  startBtn.disabled = true;
  startBtn.textContent = 'Scraping...';
  stopBtn.style.display = 'block';
  statusDiv.style.display = 'block';

  // Inject the scraper script
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: startScraping
  });

  // Poll for progress
  pollInterval = setInterval(async () => {
    try {
      const [result] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          return {
            count: window.__tookmarks_count || 0,
            done: window.__tookmarks_done || false
          };
        }
      });

      const { count, done } = result.result;
      countEl.textContent = count;

      // Animate progress bar (pulse when scraping)
      if (!done) {
        const pct = Math.min(95, (count / Math.max(count + 20, 50)) * 100);
        progressEl.style.width = pct + '%';
      }

      if (done) {
        clearInterval(pollInterval);
        progressEl.style.width = '100%';
        await downloadBookmarks(tab.id);
      }
    } catch (e) {
      // Tab may have navigated away
    }
  }, 1000);
});

stopBtn.addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => { window.__tookmarks_stop = true; }
  });

  clearInterval(pollInterval);
  await downloadBookmarks(tab.id);
});

async function downloadBookmarks(tabId) {
  const [result] = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const bookmarks = Array.from((window.__tookmarks_data || new Map()).values());
      return JSON.stringify(bookmarks, null, 2);
    }
  });

  const json = result.result;
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = `twitter_bookmarks_${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);

  const parsed = JSON.parse(json);
  countEl.textContent = parsed.length;
  progressEl.style.width = '100%';
  startBtn.textContent = `Done! (${parsed.length})`;
  stopBtn.style.display = 'none';
}

// This function runs in the context of the Twitter page
function startScraping() {
  window.__tookmarks_data = new Map();
  window.__tookmarks_count = 0;
  window.__tookmarks_done = false;
  window.__tookmarks_stop = false;

  function scrape() {
    const articles = document.querySelectorAll('article[data-testid="tweet"]');
    articles.forEach(article => {
      try {
        const userNameEl = article.querySelector('div[data-testid="User-Name"]');
        const tweetTextEl = article.querySelector('div[data-testid="tweetText"]');
        const timeEl = article.querySelector('time');
        const linkEls = article.querySelectorAll('a[href*="/status/"]');

        let authorName = '', authorHandle = '';
        if (userNameEl) {
          const spans = userNameEl.querySelectorAll('span');
          if (spans.length > 0) authorName = spans[0]?.textContent || '';
          const handleLink = userNameEl.querySelector('a[href^="/"]');
          if (handleLink) authorHandle = handleLink.getAttribute('href').replace('/', '');
        }

        const tweetText = tweetTextEl ? tweetTextEl.textContent : '';
        const timestamp = timeEl ? timeEl.getAttribute('datetime') : '';

        let tweetUrl = '';
        linkEls.forEach(link => {
          const href = link.getAttribute('href');
          if (href && href.includes('/status/')) {
            tweetUrl = 'https://x.com' + href;
          }
        });
        tweetUrl = tweetUrl.replace(/\/analytics$/, '');

        let tweetId = '';
        if (tweetUrl) {
          const match = tweetUrl.match(/\/status\/(\d+)/);
          if (match) tweetId = match[1];
        }

        if ((tweetText || tweetUrl) && tweetId) {
          window.__tookmarks_data.set(tweetId, {
            id: tweetId,
            text: tweetText,
            author_name: authorName,
            author_handle: authorHandle,
            created_at: timestamp,
            url: tweetUrl
          });
        }
      } catch (e) { /* skip */ }
    });
    window.__tookmarks_count = window.__tookmarks_data.size;
  }

  async function autoScroll() {
    let noNewCount = 0;
    let lastCount = 0;

    for (let i = 0; i < 500; i++) {
      if (window.__tookmarks_stop) break;

      scrape();
      window.scrollBy(0, 1500);
      await new Promise(r => setTimeout(r, 1500));
      scrape();

      if (window.__tookmarks_data.size === lastCount) {
        noNewCount++;
        if (noNewCount >= 5) break;
      } else {
        noNewCount = 0;
        lastCount = window.__tookmarks_data.size;
      }
    }

    scrape();
    window.__tookmarks_done = true;
  }

  autoScroll();
}
