#!/usr/bin/env python3
"""
tookmarks — Twitter Bookmarks Analyzer
Generates a beautiful HTML report from your Twitter data export's bookmarks.js
Usage: python tookmarks.py bookmarks.js [-o output.html]
"""

import json
import re
import sys
import os
from collections import Counter
from datetime import datetime
from html import escape

# ── Parsing ──────────────────────────────────────────────────────────────────

def parse_bookmarks_file(filepath):
    """Parse Twitter's bookmarks.js export file."""
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    # Strip the JS variable assignment: window.YTD.bookmarks.part0 = [...]
    match = re.match(r"^[^=]+=\s*", raw)
    if match:
        raw = raw[match.end():]

    data = json.loads(raw)
    tweets = []
    for entry in data:
        tweet = entry.get("tweet") or entry.get("bookmark", {}).get("tweet")
        if not tweet:
            # Try flattened structure
            if "full_text" in entry:
                tweet = entry
        if tweet:
            tweets.append(normalize_tweet(tweet))
    return tweets


def normalize_tweet(t):
    """Extract useful fields from a raw tweet dict."""
    user = t.get("user") or t.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {})
    entities = t.get("entities", {})

    hashtags = [h["text"].lower() for h in entities.get("hashtags", [])]
    urls = [u.get("expanded_url") or u.get("url", "") for u in entities.get("urls", [])]
    media_items = entities.get("media", [])
    ext_media = t.get("extended_entities", {}).get("media", [])
    if ext_media:
        media_items = ext_media

    media_types = []
    for m in media_items:
        mt = m.get("type", "photo")
        media_types.append(mt)

    created_str = t.get("created_at", "")
    created_dt = None
    if created_str:
        try:
            created_dt = datetime.strptime(created_str, "%a %b %d %H:%M:%S %z %Y")
        except ValueError:
            try:
                created_dt = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                pass

    full_text = t.get("full_text") or t.get("text") or ""

    return {
        "id": t.get("id_str") or t.get("id", ""),
        "text": full_text,
        "author_name": user.get("name", "Unknown"),
        "author_handle": user.get("screen_name", "unknown"),
        "created_at": created_dt,
        "hashtags": hashtags,
        "urls": urls,
        "media_types": media_types,
        "favorite_count": int(t.get("favorite_count", 0)),
        "retweet_count": int(t.get("retweet_count", 0)),
        "reply_count": int(t.get("reply_count", 0)),
        "lang": t.get("lang", ""),
    }


# ── Analysis ─────────────────────────────────────────────────────────────────

STOPWORDS = set(
    "i me my myself we our ours ourselves you your yours yourself yourselves "
    "he him his himself she her hers herself it its itself they them their "
    "theirs themselves what which who whom this that these those am is are was "
    "were be been being have has had having do does did doing a an the and but "
    "if or because as until while of at by for with about against between "
    "through during before after above below to from up down in out on off "
    "over under again further then once here there when where why how all any "
    "both each few more most other some such no nor not only own same so than "
    "too very s t can will just don should now d ll m o re ve y ain aren "
    "couldn didn doesn hadn hasn haven isn ma mightn mustn needn shan shouldn "
    "wasn weren won wouldn rt amp https http co com www get got like would one "
    "also even still much really going know think make us new things people "
    "way right thing go need want see using use used way well day back time "
    "good great could every let two first last many long take made".split()
)


def extract_keywords(tweets, top_n=30):
    """Extract top keywords from tweet texts."""
    word_counts = Counter()
    for tw in tweets:
        words = re.findall(r"[a-zA-Z]{3,}", tw["text"].lower())
        for w in words:
            if w not in STOPWORDS and len(w) > 2:
                word_counts[w] += 1
    return word_counts.most_common(top_n)


def analyze(tweets):
    """Run all analyses and return a stats dict."""
    # Authors
    author_counts = Counter()
    author_names = {}
    for tw in tweets:
        handle = tw["author_handle"]
        author_counts[handle] += 1
        author_names[handle] = tw["author_name"]

    top_authors = [
        {"handle": h, "name": author_names.get(h, h), "count": c}
        for h, c in author_counts.most_common(20)
    ]

    # Hashtags
    hashtag_counts = Counter()
    for tw in tweets:
        for ht in tw["hashtags"]:
            hashtag_counts[ht] += 1
    top_hashtags = hashtag_counts.most_common(20)

    # Keywords
    top_keywords = extract_keywords(tweets)

    # Timeline
    timeline = Counter()
    for tw in tweets:
        if tw["created_at"]:
            key = tw["created_at"].strftime("%Y-%m")
            timeline[key] += 1
    timeline_sorted = sorted(timeline.items())

    # Day of week distribution
    dow_counts = Counter()
    dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for tw in tweets:
        if tw["created_at"]:
            dow_counts[tw["created_at"].weekday()] += 1
    dow_dist = [(dow_names[i], dow_counts.get(i, 0)) for i in range(7)]

    # Hour distribution
    hour_counts = Counter()
    for tw in tweets:
        if tw["created_at"]:
            hour_counts[tw["created_at"].hour] += 1
    hour_dist = [(f"{h:02d}", hour_counts.get(h, 0)) for h in range(24)]

    # Media breakdown
    media_counter = Counter()
    tweets_with_media = 0
    tweets_with_urls = 0
    for tw in tweets:
        if tw["media_types"]:
            tweets_with_media += 1
            for mt in tw["media_types"]:
                media_counter[mt] += 1
        if tw["urls"]:
            tweets_with_urls += 1

    # Top tweets by engagement
    top_by_likes = sorted(tweets, key=lambda x: x["favorite_count"], reverse=True)[:10]
    top_by_rts = sorted(tweets, key=lambda x: x["retweet_count"], reverse=True)[:10]

    # Language breakdown
    lang_counts = Counter(tw["lang"] for tw in tweets if tw["lang"])
    top_langs = lang_counts.most_common(10)

    # Tweet length
    lengths = [len(tw["text"]) for tw in tweets]
    avg_len = sum(lengths) / len(lengths) if lengths else 0

    # Total engagement
    total_likes = sum(tw["favorite_count"] for tw in tweets)
    total_rts = sum(tw["retweet_count"] for tw in tweets)

    return {
        "total": len(tweets),
        "unique_authors": len(author_counts),
        "top_authors": top_authors,
        "top_hashtags": top_hashtags,
        "top_keywords": top_keywords,
        "timeline": timeline_sorted,
        "dow_dist": dow_dist,
        "hour_dist": hour_dist,
        "tweets_with_media": tweets_with_media,
        "tweets_with_urls": tweets_with_urls,
        "media_breakdown": media_counter.most_common(),
        "top_by_likes": top_by_likes,
        "top_by_rts": top_by_rts,
        "top_langs": top_langs,
        "avg_tweet_length": avg_len,
        "total_likes": total_likes,
        "total_rts": total_rts,
        "all_tweets": tweets,
    }


# ── HTML Report ──────────────────────────────────────────────────────────────

def fmt_num(n):
    """Format number with K/M suffix."""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def bar_chart_html(items, max_val=None, color="var(--accent-blue)"):
    """Generate CSS bar chart HTML from (label, value) pairs."""
    if not items:
        return "<p class='empty'>No data</p>"
    if max_val is None:
        max_val = max(v for _, v in items) if items else 1
    if max_val == 0:
        max_val = 1
    rows = []
    for label, val in items:
        pct = (val / max_val) * 100
        rows.append(
            f'<div class="bar-row">'
            f'<span class="bar-label">{escape(str(label))}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%;background:{color}"></div></div>'
            f'<span class="bar-value">{fmt_num(val)}</span>'
            f'</div>'
        )
    return "\n".join(rows)


def tweet_card_html(tw, rank=None):
    """Render a single tweet card."""
    date_str = tw["created_at"].strftime("%b %d, %Y") if tw["created_at"] else ""
    text_html = escape(tw["text"])
    # Linkify URLs in text
    text_html = re.sub(r'(https?://\S+)', r'<a href="\1" target="_blank" rel="noopener">\1</a>', text_html)

    rank_badge = f'<span class="rank-badge">#{rank}</span>' if rank else ""

    return f'''<div class="tweet-card">
        <div class="tweet-header">
            {rank_badge}
            <div class="tweet-author">
                <strong>{escape(tw["author_name"])}</strong>
                <span class="handle">@{escape(tw["author_handle"])}</span>
            </div>
            <span class="tweet-date">{date_str}</span>
        </div>
        <div class="tweet-text">{text_html}</div>
        <div class="tweet-stats">
            <span class="stat-pill likes">&hearts; {fmt_num(tw["favorite_count"])}</span>
            <span class="stat-pill rts">&#x21BB; {fmt_num(tw["retweet_count"])}</span>
        </div>
    </div>'''


def generate_html(stats):
    """Build the full HTML report."""

    # Overview cards
    overview = f'''
    <div class="stat-grid">
        <div class="stat-card accent-blue">
            <div class="stat-number">{fmt_num(stats["total"])}</div>
            <div class="stat-label">Bookmarks</div>
        </div>
        <div class="stat-card accent-purple">
            <div class="stat-number">{fmt_num(stats["unique_authors"])}</div>
            <div class="stat-label">Unique Authors</div>
        </div>
        <div class="stat-card accent-green">
            <div class="stat-number">{fmt_num(stats["total_likes"])}</div>
            <div class="stat-label">Total Likes</div>
        </div>
        <div class="stat-card accent-orange">
            <div class="stat-number">{fmt_num(stats["total_rts"])}</div>
            <div class="stat-label">Total Retweets</div>
        </div>
        <div class="stat-card accent-pink">
            <div class="stat-number">{stats["tweets_with_media"]}</div>
            <div class="stat-label">With Media</div>
        </div>
        <div class="stat-card accent-cyan">
            <div class="stat-number">{stats["tweets_with_urls"]}</div>
            <div class="stat-label">With Links</div>
        </div>
    </div>'''

    # Authors
    author_items = [(f'@{a["handle"]}', a["count"]) for a in stats["top_authors"]]
    authors_chart = bar_chart_html(author_items, color="var(--accent-purple)")

    # Hashtags
    hashtag_items = [(f'#{h}', c) for h, c in stats["top_hashtags"]]
    hashtags_chart = bar_chart_html(hashtag_items, color="var(--accent-blue)")

    # Keywords
    keyword_cloud = ""
    if stats["top_keywords"]:
        max_kw = stats["top_keywords"][0][1] if stats["top_keywords"] else 1
        tags = []
        for word, count in stats["top_keywords"]:
            size = 0.7 + (count / max_kw) * 1.5
            opacity = 0.5 + (count / max_kw) * 0.5
            tags.append(f'<span class="kw-tag" style="font-size:{size:.2f}rem;opacity:{opacity:.2f}">{escape(word)}</span>')
        keyword_cloud = '<div class="keyword-cloud">' + " ".join(tags) + "</div>"

    # Timeline
    timeline_chart = bar_chart_html(stats["timeline"], color="var(--accent-green)")

    # Day of week
    dow_chart = bar_chart_html(stats["dow_dist"], color="var(--accent-cyan)")

    # Hour
    hour_chart = bar_chart_html(stats["hour_dist"], color="var(--accent-orange)")

    # Languages
    lang_map = {
        "en": "English", "es": "Spanish", "fr": "French", "de": "German",
        "ja": "Japanese", "pt": "Portuguese", "it": "Italian", "nl": "Dutch",
        "ko": "Korean", "zh": "Chinese", "ar": "Arabic", "hi": "Hindi",
        "ru": "Russian", "tr": "Turkish", "pl": "Polish", "und": "Undefined",
        "qme": "Media only", "qst": "Quote tweet", "qht": "Hashtag only",
        "in": "Indonesian", "tl": "Tagalog", "th": "Thai", "vi": "Vietnamese",
        "sv": "Swedish", "da": "Danish", "fi": "Finnish", "no": "Norwegian",
    }
    lang_items = [(lang_map.get(l, l), c) for l, c in stats["top_langs"]]
    lang_chart = bar_chart_html(lang_items, color="var(--accent-pink)")

    # Top tweets
    top_likes_html = "\n".join(tweet_card_html(tw, i + 1) for i, tw in enumerate(stats["top_by_likes"]))
    top_rts_html = "\n".join(tweet_card_html(tw, i + 1) for i, tw in enumerate(stats["top_by_rts"]))

    # All bookmarks (sorted by date, newest first)
    sorted_tweets = sorted(stats["all_tweets"], key=lambda x: x["created_at"] or datetime.min, reverse=True)
    all_tweets_html = "\n".join(tweet_card_html(tw) for tw in sorted_tweets)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tookmarks — Twitter Bookmarks Report</title>
<style>
:root {{
    --bg: #0d1117;
    --bg-card: #161b22;
    --bg-card-hover: #1c2129;
    --border: #30363d;
    --text: #e6edf3;
    --text-muted: #8b949e;
    --accent-blue: #58a6ff;
    --accent-purple: #bc8cff;
    --accent-green: #3fb950;
    --accent-orange: #f0883e;
    --accent-pink: #f778ba;
    --accent-cyan: #39d2c0;
    --radius: 12px;
    --radius-sm: 8px;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem; }}

/* Header */
.header {{
    text-align: center;
    padding: 3rem 0 2rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 2rem;
}}
.header h1 {{
    font-size: 2.5rem;
    font-weight: 800;
    background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple), var(--accent-pink));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.5rem;
}}
.header p {{ color: var(--text-muted); font-size: 1.1rem; }}

/* Nav */
.nav {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    justify-content: center;
    margin-bottom: 2.5rem;
    position: sticky;
    top: 0;
    background: var(--bg);
    padding: 1rem 0;
    z-index: 100;
    border-bottom: 1px solid var(--border);
}}
.nav a {{
    color: var(--text-muted);
    text-decoration: none;
    padding: 0.4rem 1rem;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 500;
    border: 1px solid var(--border);
    transition: all 0.2s;
}}
.nav a:hover {{
    color: var(--accent-blue);
    border-color: var(--accent-blue);
    background: rgba(88, 166, 255, 0.1);
}}

/* Sections */
.section {{
    margin-bottom: 3rem;
    scroll-margin-top: 5rem;
}}
.section h2 {{
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 1.5rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--border);
    display: flex;
    align-items: center;
    gap: 0.5rem;
}}
.section h2 .sec-icon {{
    font-size: 1.2rem;
}}

/* Stat Grid */
.stat-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
}}
.stat-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
    text-align: center;
    transition: transform 0.2s, box-shadow 0.2s;
}}
.stat-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}}
.stat-number {{
    font-size: 2rem;
    font-weight: 800;
    line-height: 1.2;
}}
.stat-label {{
    color: var(--text-muted);
    font-size: 0.85rem;
    margin-top: 0.25rem;
}}
.accent-blue .stat-number {{ color: var(--accent-blue); }}
.accent-purple .stat-number {{ color: var(--accent-purple); }}
.accent-green .stat-number {{ color: var(--accent-green); }}
.accent-orange .stat-number {{ color: var(--accent-orange); }}
.accent-pink .stat-number {{ color: var(--accent-pink); }}
.accent-cyan .stat-number {{ color: var(--accent-cyan); }}

/* Bar Chart */
.bar-row {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
}}
.bar-label {{
    min-width: 140px;
    font-size: 0.85rem;
    color: var(--text-muted);
    text-align: right;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.bar-track {{
    flex: 1;
    height: 24px;
    background: rgba(255,255,255,0.05);
    border-radius: 4px;
    overflow: hidden;
}}
.bar-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.6s ease;
    min-width: 2px;
}}
.bar-value {{
    min-width: 40px;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text);
}}

/* Keyword Cloud */
.keyword-cloud {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    padding: 1.5rem;
    background: var(--bg-card);
    border-radius: var(--radius);
    border: 1px solid var(--border);
    justify-content: center;
    align-items: center;
}}
.kw-tag {{
    color: var(--accent-cyan);
    padding: 0.2rem 0.5rem;
    border-radius: 6px;
    background: rgba(57, 210, 192, 0.08);
    white-space: nowrap;
}}

/* Two Column */
.two-col {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2rem;
}}
@media (max-width: 768px) {{
    .two-col {{ grid-template-columns: 1fr; }}
    .bar-label {{ min-width: 100px; }}
}}

/* Card wrapper */
.card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
}}
.card h3 {{
    font-size: 1rem;
    color: var(--text-muted);
    margin-bottom: 1rem;
    font-weight: 600;
}}

/* Tweet Cards */
.tweet-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.25rem;
    margin-bottom: 0.75rem;
    transition: border-color 0.2s;
}}
.tweet-card:hover {{
    border-color: var(--accent-blue);
}}
.tweet-header {{
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
    flex-wrap: wrap;
}}
.tweet-author strong {{
    color: var(--text);
    font-size: 0.95rem;
}}
.handle {{
    color: var(--text-muted);
    font-size: 0.85rem;
    margin-left: 0.25rem;
}}
.tweet-date {{
    color: var(--text-muted);
    font-size: 0.8rem;
    margin-left: auto;
}}
.tweet-text {{
    font-size: 0.95rem;
    line-height: 1.5;
    margin-bottom: 0.75rem;
    word-break: break-word;
}}
.tweet-text a {{
    color: var(--accent-blue);
    text-decoration: none;
}}
.tweet-text a:hover {{ text-decoration: underline; }}
.tweet-stats {{
    display: flex;
    gap: 0.75rem;
}}
.stat-pill {{
    font-size: 0.8rem;
    padding: 0.2rem 0.6rem;
    border-radius: 20px;
    font-weight: 600;
}}
.stat-pill.likes {{
    color: var(--accent-pink);
    background: rgba(247, 120, 186, 0.1);
}}
.stat-pill.rts {{
    color: var(--accent-green);
    background: rgba(63, 185, 80, 0.1);
}}
.rank-badge {{
    background: var(--accent-blue);
    color: var(--bg);
    font-size: 0.75rem;
    font-weight: 700;
    padding: 0.15rem 0.5rem;
    border-radius: 20px;
}}

/* Tabs */
.tabs {{
    display: flex;
    gap: 0;
    margin-bottom: 1.5rem;
    border-bottom: 2px solid var(--border);
}}
.tab-btn {{
    background: none;
    border: none;
    color: var(--text-muted);
    padding: 0.75rem 1.25rem;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition: all 0.2s;
}}
.tab-btn:hover {{ color: var(--text); }}
.tab-btn.active {{
    color: var(--accent-blue);
    border-bottom-color: var(--accent-blue);
}}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}

/* Search */
.search-box {{
    width: 100%;
    padding: 0.75rem 1rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    font-size: 0.95rem;
    margin-bottom: 1.5rem;
    outline: none;
    transition: border-color 0.2s;
}}
.search-box:focus {{ border-color: var(--accent-blue); }}
.search-box::placeholder {{ color: var(--text-muted); }}

/* Footer */
.footer {{
    text-align: center;
    color: var(--text-muted);
    font-size: 0.8rem;
    padding: 2rem 0;
    border-top: 1px solid var(--border);
    margin-top: 2rem;
}}

.empty {{ color: var(--text-muted); font-style: italic; }}

/* Scrollbar */
::-webkit-scrollbar {{ width: 8px; }}
::-webkit-scrollbar-track {{ background: var(--bg); }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--text-muted); }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Tookmarks</h1>
        <p>Your Twitter Bookmarks — Analyzed</p>
    </div>

    <nav class="nav">
        <a href="#overview">Overview</a>
        <a href="#authors">Authors</a>
        <a href="#topics">Topics</a>
        <a href="#timeline">Timeline</a>
        <a href="#activity">Activity</a>
        <a href="#top-tweets">Top Tweets</a>
        <a href="#all-bookmarks">All Bookmarks</a>
    </nav>

    <section class="section" id="overview">
        <h2><span class="sec-icon">&#x1f4ca;</span> Overview</h2>
        {overview}
    </section>

    <section class="section" id="authors">
        <h2><span class="sec-icon">&#x1f464;</span> Top Authors</h2>
        <div class="card">
            {authors_chart}
        </div>
    </section>

    <section class="section" id="topics">
        <h2><span class="sec-icon">&#x1f3f7;</span> Topics</h2>
        <div class="two-col">
            <div class="card">
                <h3>Top Hashtags</h3>
                {hashtags_chart if hashtag_items else "<p class='empty'>No hashtags found</p>"}
            </div>
            <div class="card">
                <h3>Top Keywords</h3>
                {keyword_cloud if keyword_cloud else "<p class='empty'>No keywords found</p>"}
            </div>
        </div>
    </section>

    <section class="section" id="timeline">
        <h2><span class="sec-icon">&#x1f4c5;</span> Timeline</h2>
        <div class="card">
            <h3>Bookmarks by Month</h3>
            {timeline_chart}
        </div>
    </section>

    <section class="section" id="activity">
        <h2><span class="sec-icon">&#x23f0;</span> Activity Patterns</h2>
        <div class="two-col">
            <div class="card">
                <h3>Day of Week</h3>
                {dow_chart}
            </div>
            <div class="card">
                <h3>Hour of Day (UTC)</h3>
                {hour_chart}
            </div>
        </div>
        <div class="two-col" style="margin-top:1.5rem">
            <div class="card">
                <h3>Languages</h3>
                {lang_chart}
            </div>
            <div class="card">
                <h3>Media Breakdown</h3>
                {bar_chart_html(stats["media_breakdown"], color="var(--accent-orange)") if stats["media_breakdown"] else "<p class='empty'>No media found</p>"}
            </div>
        </div>
    </section>

    <section class="section" id="top-tweets">
        <h2><span class="sec-icon">&#x1f525;</span> Top Tweets</h2>
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab(event, 'tab-likes')">Most Liked</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-rts')">Most Retweeted</button>
        </div>
        <div id="tab-likes" class="tab-content active">
            {top_likes_html}
        </div>
        <div id="tab-rts" class="tab-content">
            {top_rts_html}
        </div>
    </section>

    <section class="section" id="all-bookmarks">
        <h2><span class="sec-icon">&#x1f4d6;</span> All Bookmarks</h2>
        <input type="text" class="search-box" id="search" placeholder="Search bookmarks..." oninput="filterTweets()">
        <div id="tweets-list">
            {all_tweets_html}
        </div>
    </section>

    <div class="footer">
        Generated by <strong>tookmarks</strong> &middot; {datetime.now().strftime("%B %d, %Y")}
    </div>
</div>

<script>
function switchTab(e, tabId) {{
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    e.target.classList.add('active');
    document.getElementById(tabId).classList.add('active');
}}

function filterTweets() {{
    const q = document.getElementById('search').value.toLowerCase();
    const cards = document.querySelectorAll('#tweets-list .tweet-card');
    cards.forEach(card => {{
        const text = card.textContent.toLowerCase();
        card.style.display = text.includes(q) ? '' : 'none';
    }});
}}

// Animate bars on scroll
const observer = new IntersectionObserver((entries) => {{
    entries.forEach(entry => {{
        if (entry.isIntersecting) {{
            entry.target.querySelectorAll('.bar-fill').forEach(bar => {{
                const w = bar.style.width;
                bar.style.width = '0';
                requestAnimationFrame(() => {{ bar.style.width = w; }});
            }});
        }}
    }});
}}, {{ threshold: 0.1 }});

document.querySelectorAll('.card').forEach(card => observer.observe(card));
</script>
</body>
</html>'''


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python tookmarks.py <bookmarks.js> [-o output.html]")
        print("\nGenerates an HTML report from your Twitter data export's bookmarks.js file.")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = "bookmarks_report.html"

    if "-o" in sys.argv:
        idx = sys.argv.index("-o")
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]

    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found.")
        sys.exit(1)

    print(f"Reading {input_file}...")
    tweets = parse_bookmarks_file(input_file)
    print(f"Found {len(tweets)} bookmarks.")

    if not tweets:
        print("No bookmarks found. Check that the file is a valid Twitter bookmarks export.")
        sys.exit(1)

    print("Analyzing...")
    stats = analyze(tweets)

    print("Generating report...")
    html = generate_html(stats)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report saved to {output_file}")
    print(f"Open it in your browser: file://{os.path.abspath(output_file)}")


if __name__ == "__main__":
    main()
