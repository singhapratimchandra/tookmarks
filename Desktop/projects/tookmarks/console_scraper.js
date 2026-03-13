// =============================================================
// Tookmarks — Twitter/X Bookmarks Scraper (Console Version)
// =============================================================
// HOW TO USE:
// 1. Go to https://x.com/i/bookmarks in Chrome
// 2. Open DevTools (Cmd+Option+J on Mac, Ctrl+Shift+J on Windows)
// 3. Paste this entire script into the Console tab and press Enter
// 4. Wait for it to scroll through all your bookmarks
// 5. A JSON file will automatically download when done
// =============================================================

(async function tookmarksScraper() {
    console.log('%c[Tookmarks] Starting bookmark scraper...', 'color: #58a6ff; font-weight: bold; font-size: 14px');

    if (!window.location.href.includes('x.com/i/bookmarks')) {
        console.error('[Tookmarks] Please navigate to https://x.com/i/bookmarks first!');
        return;
    }

    const allBookmarks = new Map();

    function scrapeTweetsFromDOM() {
        const articles = document.querySelectorAll('article[data-testid="tweet"]');
        let newCount = 0;

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

                // Clean /analytics suffix
                tweetUrl = tweetUrl.replace(/\/analytics$/, '');

                let tweetId = '';
                if (tweetUrl) {
                    const match = tweetUrl.match(/\/status\/(\d+)/);
                    if (match) tweetId = match[1];
                }

                if ((tweetText || tweetUrl) && tweetId && !allBookmarks.has(tweetId)) {
                    allBookmarks.set(tweetId, {
                        id: tweetId,
                        text: tweetText,
                        author_name: authorName,
                        author_handle: authorHandle,
                        created_at: timestamp,
                        url: tweetUrl
                    });
                    newCount++;
                }
            } catch (e) { /* skip malformed tweet */ }
        });

        return newCount;
    }

    // Scroll and collect
    let noNewCount = 0;
    let scrollCount = 0;
    const maxScrolls = 500; // Safety limit

    console.log('[Tookmarks] Scrolling through bookmarks...');

    while (scrollCount < maxScrolls) {
        scrapeTweetsFromDOM();
        window.scrollBy(0, 1500);
        await new Promise(r => setTimeout(r, 1500));

        const prevSize = allBookmarks.size;
        scrapeTweetsFromDOM();

        if (allBookmarks.size === prevSize) {
            noNewCount++;
            if (noNewCount >= 5) {
                console.log('[Tookmarks] Reached end of bookmarks.');
                break;
            }
        } else {
            noNewCount = 0;
        }

        scrollCount++;
        if (scrollCount % 10 === 0) {
            console.log(`[Tookmarks] Collected ${allBookmarks.size} bookmarks so far...`);
        }
    }

    // Final scrape
    scrapeTweetsFromDOM();

    const bookmarks = Array.from(allBookmarks.values());
    console.log(`%c[Tookmarks] Done! Collected ${bookmarks.length} bookmarks.`, 'color: #3fb950; font-weight: bold; font-size: 14px');

    // Download as JSON
    const json = JSON.stringify(bookmarks, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `twitter_bookmarks_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    console.log(`[Tookmarks] File downloaded: ${a.download}`);
    console.log('[Tookmarks] You can now use this file with: python tookmarks.py <filename>');

    return bookmarks;
})();
