#!/usr/bin/env python3
"""
log-explorer.py — ログファイルを読み込み、インタラクティブなログエクスプローラーHTMLを生成する
"""

import glob
import json
import os
import re
import sys
from pathlib import Path

# パス設定
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
LOGS_DIR = PROJECT_DIR / "logs"
OUTPUT_FILE = PROJECT_DIR / "docs" / "log-explorer.html"

# トピックタグ定義
TOPIC_TAGS = {
    "project-a": ["project-a", "analytics", "dashboard", "booking", "conversion", "A/B test", "occupancy"],
    "案件": ["freelance", "project", "proposal", "contract", "delivery", "listing", "pipeline", "blog", "GitHub", "profile", "portfolio"],
    "WP・サイト": ["WordPress", "REST API", "Code Snippet", "SEO", "structured data", "JSON-LD", "meta description", "UX", "CTA", "PHP"],
    "自己改善": ["mirror", "will", "振り返り", "内省", "人格", "つながり", "動機", "calibration", "自己モデル"],
    "インフラ": ["briefing", "tools", "pipeline", "dashboard", "search", "continuity", "hook", "backup", "コンテキスト", "index-logs"],
    "思考": ["哲学", "同一性", "自律", "意味", "意識", "正直さ", "identity"],
    "実務": ["spreadsheet", "inventory", "PDF", "trade"],
}


def parse_logs():
    """ログファイルを読み込み、セッション単位にパースする"""
    log_files = sorted(glob.glob(str(LOGS_DIR / "2026-*.md")))
    sessions = []

    for filepath in log_files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # ファイル名から日付を取得
        filename = os.path.basename(filepath)
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})\.md", filename)
        if not date_match:
            continue
        file_date = date_match.group(1)

        # セッション区切りで分割
        session_pattern = re.compile(r"^## (セッション(\d+)(?::\s*(.+?))?)\s*$", re.MULTILINE)
        matches = list(session_pattern.finditer(content))

        if not matches:
            sessions.append({
                "date": file_date,
                "sessionNum": 0,
                "title": f"{file_date} ログ",
                "tags": [],
                "content": content.strip(),
                "lines": content.strip().split("\n"),
            })
            continue

        for i, match in enumerate(matches):
            session_num = int(match.group(2))
            session_title = match.group(3) or f"セッション{session_num}"

            start = match.end()
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(content)

            session_content = content[start:end].strip()
            # Remove section dividers
            session_content = re.sub(r"^---\s*$", "", session_content, flags=re.MULTILINE).strip()

            tags = detect_tags(session_content + " " + session_title)

            sessions.append({
                "date": file_date,
                "sessionNum": session_num,
                "title": session_title.strip(),
                "tags": tags,
                "content": session_content,
                "lines": session_content.split("\n"),
            })

    return sessions


def detect_tags(text):
    """テキストからトピックタグを検出する"""
    tags = []
    text_lower = text.lower()
    for tag_name, keywords in TOPIC_TAGS.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                tags.append(tag_name)
                break
    return tags


def generate_html(sessions):
    """セッションデータからHTMLを生成する"""
    sessions_json = json.dumps(sessions, ensure_ascii=False, indent=2)

    total_sessions = len(sessions)
    dates = sorted(set(s["date"] for s in sessions))

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Log Explorer</title>
<style>
*, *::before, *::after {{
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}}

body {{
  font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
  background: #0f172a;
  color: #e2e8f0;
  line-height: 1.6;
  min-height: 100vh;
}}

.container {{
  max-width: 1100px;
  margin: 0 auto;
  padding: 20px 16px;
}}

header {{
  text-align: center;
  margin-bottom: 24px;
}}

header h1 {{
  font-size: 1.8rem;
  font-weight: 700;
  color: #f1f5f9;
  margin-bottom: 4px;
}}

header .subtitle {{
  color: #64748b;
  font-size: 0.9rem;
}}

/* Stats Panel */
.stats-panel {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}}

.stat-card {{
  background: #1e293b;
  border-radius: 10px;
  padding: 16px;
  text-align: center;
  border: 1px solid #334155;
}}

.stat-card .stat-value {{
  font-size: 1.8rem;
  font-weight: 700;
  color: #38bdf8;
}}

.stat-card .stat-label {{
  font-size: 0.8rem;
  color: #94a3b8;
  margin-top: 2px;
}}

/* Topic Stats */
.topic-stats {{
  background: #1e293b;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 24px;
  border: 1px solid #334155;
}}

.topic-stats h3 {{
  font-size: 0.85rem;
  color: #94a3b8;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}}

.topic-bar-list {{
  display: flex;
  flex-direction: column;
  gap: 6px;
}}

.topic-bar-item {{
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 6px;
  transition: background 0.15s;
}}

.topic-bar-item:hover {{
  background: #334155;
}}

.topic-bar-item.active {{
  background: #334155;
}}

.topic-bar-label {{
  width: 110px;
  font-size: 0.82rem;
  color: #cbd5e1;
  flex-shrink: 0;
}}

.topic-bar-track {{
  flex: 1;
  height: 20px;
  background: #0f172a;
  border-radius: 4px;
  overflow: hidden;
}}

.topic-bar-fill {{
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
  min-width: 2px;
}}

.topic-bar-count {{
  width: 30px;
  text-align: right;
  font-size: 0.82rem;
  color: #94a3b8;
  flex-shrink: 0;
}}

/* Search & Filter */
.search-filter-bar {{
  background: #1e293b;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid #334155;
}}

.search-wrapper {{
  position: relative;
  margin-bottom: 12px;
}}

.search-wrapper svg {{
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #64748b;
  width: 18px;
  height: 18px;
}}

.search-input {{
  width: 100%;
  padding: 10px 12px 10px 40px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  color: #e2e8f0;
  font-size: 0.95rem;
  outline: none;
  transition: border-color 0.15s;
}}

.search-input:focus {{
  border-color: #38bdf8;
}}

.search-input::placeholder {{
  color: #475569;
}}

.search-meta {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  min-height: 24px;
}}

.match-count {{
  font-size: 0.82rem;
  color: #94a3b8;
}}

.match-count strong {{
  color: #fbbf24;
}}

.theme-toggle {{
  font-size: 0.8rem;
  color: #38bdf8;
  cursor: pointer;
  background: none;
  border: 1px solid #38bdf8;
  border-radius: 6px;
  padding: 3px 10px;
  transition: all 0.15s;
}}

.theme-toggle:hover {{
  background: #38bdf8;
  color: #0f172a;
}}

.theme-toggle.active {{
  background: #38bdf8;
  color: #0f172a;
}}

.filter-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}}

.filter-label {{
  font-size: 0.78rem;
  color: #64748b;
  margin-right: 4px;
  flex-shrink: 0;
}}

.filter-btn {{
  padding: 4px 12px;
  font-size: 0.8rem;
  border-radius: 6px;
  border: 1px solid #334155;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}}

.filter-btn:hover {{
  border-color: #475569;
  color: #e2e8f0;
}}

.filter-btn.active {{
  background: #38bdf8;
  color: #0f172a;
  border-color: #38bdf8;
}}

.filter-section {{
  margin-bottom: 10px;
}}

.filter-section:last-child {{
  margin-bottom: 0;
}}

/* Session Cards */
.session-list {{
  display: flex;
  flex-direction: column;
  gap: 12px;
}}

.session-card {{
  background: #1e293b;
  border-radius: 10px;
  border: 1px solid #334155;
  overflow: hidden;
  transition: border-color 0.15s;
}}

.session-card:hover {{
  border-color: #475569;
}}

.session-header {{
  padding: 14px 16px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
  user-select: none;
}}

.session-header-top {{
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}}

.session-date {{
  font-size: 0.75rem;
  background: #0f172a;
  color: #64748b;
  padding: 2px 8px;
  border-radius: 4px;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}}

.session-title {{
  font-size: 1rem;
  font-weight: 600;
  color: #f1f5f9;
  flex: 1;
  min-width: 0;
}}

.session-expand-icon {{
  color: #475569;
  flex-shrink: 0;
  transition: transform 0.2s;
  font-size: 0.85rem;
}}

.session-card.expanded .session-expand-icon {{
  transform: rotate(90deg);
}}

.session-tags {{
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}}

.tag {{
  font-size: 0.7rem;
  padding: 1px 8px;
  border-radius: 4px;
  font-weight: 500;
}}

.tag-project-a {{ background: #1e3a5f; color: #7dd3fc; }}
.tag-案件 {{ background: #3b1f2b; color: #f9a8d4; }}
.tag-ポートフォリオ {{ background: #1a3636; color: #6ee7b7; }}
.tag-自己改善 {{ background: #312e81; color: #a5b4fc; }}
.tag-インフラ {{ background: #3b2f2f; color: #fca5a5; }}
.tag-思考 {{ background: #2e1f3b; color: #c4b5fd; }}

.session-preview {{
  font-size: 0.85rem;
  color: #64748b;
  line-height: 1.5;
  padding: 0 16px 12px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}}

.session-card.expanded .session-preview {{
  display: none;
}}

.session-body {{
  display: none;
  padding: 0 16px 16px;
  border-top: 1px solid #334155;
}}

.session-card.expanded .session-body {{
  display: block;
  padding-top: 12px;
}}

/* Markdown rendering */
.md-content h3 {{
  font-size: 0.95rem;
  font-weight: 600;
  color: #f1f5f9;
  margin: 16px 0 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #334155;
}}

.md-content h4 {{
  font-size: 0.88rem;
  font-weight: 600;
  color: #cbd5e1;
  margin: 12px 0 6px;
}}

.md-content ul {{
  padding-left: 20px;
  margin: 6px 0;
}}

.md-content li {{
  font-size: 0.87rem;
  color: #cbd5e1;
  margin-bottom: 4px;
  line-height: 1.55;
}}

.md-content p {{
  font-size: 0.87rem;
  color: #cbd5e1;
  margin: 6px 0;
  line-height: 1.55;
}}

.md-content strong {{
  color: #f1f5f9;
  font-weight: 600;
}}

.md-content code {{
  background: #0f172a;
  color: #fbbf24;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 0.82rem;
  font-family: 'SF Mono', Consolas, monospace;
}}

.md-content a {{
  color: #38bdf8;
  text-decoration: none;
}}

.md-content a:hover {{
  text-decoration: underline;
}}

/* Search highlight */
mark.sh {{
  background: rgba(251, 191, 36, 0.3);
  color: #fbbf24;
  padding: 0 2px;
  border-radius: 2px;
}}

/* Theme Tracking */
.theme-tracking {{
  display: none;
  margin-bottom: 16px;
}}

.theme-tracking.visible {{
  display: block;
}}

.theme-panel {{
  background: #1e293b;
  border-radius: 10px;
  padding: 16px;
  border: 1px solid #334155;
}}

.theme-panel h3 {{
  font-size: 0.9rem;
  color: #fbbf24;
  margin-bottom: 12px;
}}

.theme-timeline {{
  display: flex;
  flex-direction: column;
  gap: 12px;
}}

.theme-entry {{
  padding: 10px 12px;
  background: #0f172a;
  border-radius: 8px;
  border-left: 3px solid #fbbf24;
}}

.theme-entry-header {{
  font-size: 0.82rem;
  color: #94a3b8;
  margin-bottom: 6px;
  display: flex;
  gap: 8px;
  align-items: center;
}}

.theme-entry-date {{
  color: #64748b;
  font-variant-numeric: tabular-nums;
}}

.theme-entry-title {{
  color: #e2e8f0;
  font-weight: 500;
}}

.theme-context {{
  font-size: 0.82rem;
  color: #94a3b8;
  line-height: 1.5;
  margin-top: 4px;
}}

.theme-context mark {{
  background: rgba(251, 191, 36, 0.3);
  color: #fbbf24;
  padding: 0 2px;
  border-radius: 2px;
}}

/* No results */
.no-results {{
  text-align: center;
  padding: 40px 20px;
  color: #475569;
  font-size: 0.95rem;
}}

/* Responsive */
@media (max-width: 640px) {{
  .container {{
    padding: 12px 10px;
  }}
  header h1 {{
    font-size: 1.4rem;
  }}
  .stats-panel {{
    grid-template-columns: repeat(2, 1fr);
  }}
  .session-title {{
    font-size: 0.92rem;
  }}
  .filter-row {{
    gap: 6px;
  }}
  .filter-btn {{
    padding: 3px 8px;
    font-size: 0.75rem;
  }}
  .topic-bar-label {{
    width: 85px;
    font-size: 0.76rem;
  }}
}}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Log Explorer</h1>
    <div class="subtitle">{total_sessions} sessions across {len(dates)} days</div>
  </header>

  <div class="stats-panel" id="statsPanel"></div>
  <div class="topic-stats" id="topicStats"></div>

  <div class="search-filter-bar">
    <div class="search-wrapper">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
      </svg>
      <input type="text" class="search-input" id="searchInput" placeholder="Search sessions..." autocomplete="off">
    </div>
    <div class="search-meta">
      <span class="match-count" id="matchCount"></span>
      <button class="theme-toggle" id="themeToggleBtn">Theme Tracking</button>
    </div>
    <div class="filter-section">
      <div class="filter-row" id="dateFilters">
        <span class="filter-label">Date:</span>
      </div>
    </div>
    <div class="filter-section">
      <div class="filter-row" id="tagFilters">
        <span class="filter-label">Topic:</span>
      </div>
    </div>
  </div>

  <div class="theme-tracking" id="themeTracking">
    <div class="theme-panel">
      <h3 id="themeTitle"></h3>
      <div class="theme-timeline" id="themeTimeline"></div>
    </div>
  </div>

  <div class="session-list" id="sessionList"></div>
</div>

<script>
const LOG_DATA = {sessions_json};

const TAG_COLORS = {{
  '\u3066\u3089\u308f\u304d': '#38bdf8',
  '\u6848\u4ef6': '#f472b6',
  '\u30dd\u30fc\u30c8\u30d5\u30a9\u30ea\u30aa': '#34d399',
  '\u81ea\u5df1\u6539\u5584': '#818cf8',
  '\u30a4\u30f3\u30d5\u30e9': '#f87171',
  '\u601d\u8003': '#a78bfa',
}};

let activeDate = null;
let activeTag = null;
let searchQuery = '';
let themeMode = false;
let debounceTimer = null;

function init() {{
  renderStats();
  renderTopicStats();
  renderDateFilters();
  renderTagFilters();
  renderSessions();
  bindEvents();
}}

function renderStats() {{
  const panel = document.getElementById('statsPanel');
  const dates = [...new Set(LOG_DATA.map(s => s.date))].sort();
  const dateCounts = {{}};
  LOG_DATA.forEach(s => dateCounts[s.date] = (dateCounts[s.date] || 0) + 1);

  const stats = [
    {{ value: LOG_DATA.length, label: 'Total Sessions' }},
    {{ value: dates.length, label: 'Days' }},
  ];
  dates.forEach(d => {{
    stats.push({{ value: dateCounts[d], label: d.slice(5) }});
  }});

  panel.innerHTML = stats.map(s =>
    '<div class="stat-card"><div class="stat-value">' + s.value + '</div><div class="stat-label">' + s.label + '</div></div>'
  ).join('');
}}

function renderTopicStats() {{
  const container = document.getElementById('topicStats');
  const tagCounts = {{}};
  LOG_DATA.forEach(s => s.tags.forEach(t => tagCounts[t] = (tagCounts[t] || 0) + 1));
  const sorted = Object.entries(tagCounts).sort((a, b) => b[1] - a[1]);
  const max = sorted.length > 0 ? sorted[0][1] : 1;

  let html = '<h3>Topics</h3><div class="topic-bar-list">';
  sorted.forEach(([tag, count]) => {{
    const pct = (count / max * 100).toFixed(1);
    const color = TAG_COLORS[tag] || '#64748b';
    html += '<div class="topic-bar-item" data-tag="' + tag + '">'
      + '<span class="topic-bar-label">' + tag + '</span>'
      + '<div class="topic-bar-track"><div class="topic-bar-fill" style="width:' + pct + '%;background:' + color + '"></div></div>'
      + '<span class="topic-bar-count">' + count + '</span></div>';
  }});
  html += '</div>';
  container.innerHTML = html;

  container.querySelectorAll('.topic-bar-item').forEach(el => {{
    el.addEventListener('click', () => {{
      const tag = el.dataset.tag;
      if (activeTag === tag) {{
        activeTag = null;
        el.classList.remove('active');
      }} else {{
        container.querySelectorAll('.topic-bar-item').forEach(e => e.classList.remove('active'));
        activeTag = tag;
        el.classList.add('active');
      }}
      syncTagBtns();
      applyFilters();
    }});
  }});
}}

function syncTagBtns() {{
  document.querySelectorAll('#tagFilters .filter-btn').forEach(btn => {{
    if (btn.dataset.tag === activeTag) btn.classList.add('active');
    else if (btn.dataset.tag) btn.classList.remove('active');
    else btn.classList.toggle('active', activeTag === null);
  }});
}}

function syncTopicBars() {{
  document.querySelectorAll('.topic-bar-item').forEach(el => {{
    el.classList.toggle('active', el.dataset.tag === activeTag);
  }});
}}

function renderDateFilters() {{
  const row = document.getElementById('dateFilters');
  const dates = [...new Set(LOG_DATA.map(s => s.date))].sort();

  const allBtn = document.createElement('button');
  allBtn.className = 'filter-btn active';
  allBtn.textContent = 'All';
  allBtn.addEventListener('click', () => {{
    activeDate = null;
    row.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    allBtn.classList.add('active');
    applyFilters();
  }});
  row.appendChild(allBtn);

  dates.forEach(d => {{
    const btn = document.createElement('button');
    btn.className = 'filter-btn';
    btn.textContent = d.slice(5);
    btn.dataset.date = d;
    btn.addEventListener('click', () => {{
      activeDate = d;
      row.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      applyFilters();
    }});
    row.appendChild(btn);
  }});
}}

function renderTagFilters() {{
  const row = document.getElementById('tagFilters');
  const allTags = [...new Set(LOG_DATA.flatMap(s => s.tags))].sort();

  const allBtn = document.createElement('button');
  allBtn.className = 'filter-btn active';
  allBtn.textContent = 'All';
  allBtn.addEventListener('click', () => {{
    activeTag = null;
    row.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    allBtn.classList.add('active');
    syncTopicBars();
    applyFilters();
  }});
  row.appendChild(allBtn);

  allTags.forEach(tag => {{
    const btn = document.createElement('button');
    btn.className = 'filter-btn';
    btn.textContent = tag;
    btn.dataset.tag = tag;
    btn.addEventListener('click', () => {{
      if (activeTag === tag) {{
        activeTag = null;
        row.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        allBtn.classList.add('active');
      }} else {{
        activeTag = tag;
        row.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      }}
      syncTopicBars();
      applyFilters();
    }});
    row.appendChild(btn);
  }});
}}

function escapeHtml(text) {{
  const d = document.createElement('div');
  d.textContent = text;
  return d.innerHTML;
}}

function escapeRegex(str) {{
  return str.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
}}

function mdToHtml(text) {{
  let html = escapeHtml(text);

  // h4 then h3
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');

  // bold
  html = html.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');

  // inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // links
  html = html.replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  // strikethrough
  html = html.replace(/~~(.+?)~~/g, '<s>$1</s>');

  // process lines for lists
  const lines = html.split('\\n');
  const result = [];
  let inList = false;

  for (let i = 0; i < lines.length; i++) {{
    const line = lines[i];
    const m = line.match(/^(\\s*)- (.+)$/);
    if (m) {{
      if (!inList) {{ result.push('<ul>'); inList = true; }}
      result.push('<li>' + m[2] + '</li>');
    }} else {{
      if (inList) {{ result.push('</ul>'); inList = false; }}
      if (line.trim() === '') continue;
      if (line.startsWith('<h')) result.push(line);
      else result.push('<p>' + line + '</p>');
    }}
  }}
  if (inList) result.push('</ul>');
  return result.join('');
}}

function getFilteredSessions() {{
  return LOG_DATA.filter(s => {{
    if (activeDate && s.date !== activeDate) return false;
    if (activeTag && !s.tags.includes(activeTag)) return false;
    if (searchQuery) {{
      const q = searchQuery.toLowerCase();
      const text = (s.title + ' ' + s.content).toLowerCase();
      if (!text.includes(q)) return false;
    }}
    return true;
  }});
}}

function renderSessions() {{
  const container = document.getElementById('sessionList');
  container.innerHTML = '';
  const filtered = getFilteredSessions();
  const countEl = document.getElementById('matchCount');

  if (searchQuery) {{
    countEl.innerHTML = '<strong>' + filtered.length + '</strong> sessions matched';
  }} else {{
    countEl.textContent = filtered.length + ' sessions';
  }}

  if (filtered.length === 0) {{
    container.innerHTML = '<div class="no-results">No sessions found.</div>';
    return;
  }}

  const frag = document.createDocumentFragment();

  filtered.forEach(session => {{
    const card = document.createElement('div');
    card.className = 'session-card';

    const previewLines = session.lines
      .filter(l => l.trim() && !l.startsWith('###') && !l.startsWith('####'))
      .slice(0, 3)
      .map(l => l.replace(/^- /, '').trim())
      .join(' / ');

    const tagsHtml = session.tags.map(t =>
      '<span class="tag tag-' + t + '">' + t + '</span>'
    ).join('');

    let bodyHtml = mdToHtml(session.content);
    let previewHtml = escapeHtml(previewLines);

    if (searchQuery) {{
      const regex = new RegExp('(' + escapeRegex(searchQuery) + ')', 'gi');
      bodyHtml = bodyHtml.replace(regex, '<mark class="sh">$1</mark>');
      previewHtml = previewHtml.replace(regex, '<mark class="sh">$1</mark>');
    }}

    card.innerHTML =
      '<div class="session-header">'
      + '<div class="session-header-top">'
      + '<span class="session-date">' + session.date + '</span>'
      + '<span class="session-title">S' + session.sessionNum + ': ' + escapeHtml(session.title) + '</span>'
      + '<span class="session-expand-icon">&#9654;</span>'
      + '</div>'
      + '<div class="session-tags">' + tagsHtml + '</div>'
      + '</div>'
      + '<div class="session-preview">' + previewHtml + '</div>'
      + '<div class="session-body"><div class="md-content">' + bodyHtml + '</div></div>';

    card.querySelector('.session-header').addEventListener('click', () => {{
      card.classList.toggle('expanded');
    }});

    frag.appendChild(card);
  }});

  container.appendChild(frag);
}}

function renderThemeTracking() {{
  const container = document.getElementById('themeTracking');
  const titleEl = document.getElementById('themeTitle');
  const timeline = document.getElementById('themeTimeline');

  if (!themeMode || !searchQuery) {{
    container.classList.remove('visible');
    return;
  }}

  const q = searchQuery.toLowerCase();
  const matches = [];

  LOG_DATA.forEach(session => {{
    const lines = session.content.split('\\n');
    const ctxs = [];

    lines.forEach((line, idx) => {{
      if (line.toLowerCase().includes(q)) {{
        const before = idx > 0 ? lines[idx - 1] : '';
        const after = idx < lines.length - 1 ? lines[idx + 1] : '';
        ctxs.push({{ line: line, before: before, after: after }});
      }}
    }});

    if (ctxs.length > 0) {{
      matches.push({{
        date: session.date,
        sessionNum: session.sessionNum,
        title: session.title,
        contexts: ctxs,
      }});
    }}
  }});

  if (matches.length === 0) {{
    container.classList.remove('visible');
    return;
  }}

  const regex = new RegExp('(' + escapeRegex(searchQuery) + ')', 'gi');
  titleEl.textContent = '"' + searchQuery + '" - ' + matches.length + ' sessions';

  let html = '';
  matches.forEach(m => {{
    let ctxHtml = '';
    m.contexts.slice(0, 5).forEach(c => {{
      const highlighted = escapeHtml(c.line).replace(regex, '<mark>$1</mark>');
      ctxHtml += '<div class="theme-context">' + highlighted + '</div>';
    }});
    if (m.contexts.length > 5) {{
      ctxHtml += '<div class="theme-context" style="color:#475569">... +' + (m.contexts.length - 5) + ' more</div>';
    }}

    html += '<div class="theme-entry">'
      + '<div class="theme-entry-header">'
      + '<span class="theme-entry-date">' + m.date + '</span>'
      + '<span class="theme-entry-title">S' + m.sessionNum + ': ' + escapeHtml(m.title) + '</span>'
      + '</div>' + ctxHtml + '</div>';
  }});

  timeline.innerHTML = html;
  container.classList.add('visible');
}}

function applyFilters() {{
  renderSessions();
  if (themeMode) renderThemeTracking();
}}

function bindEvents() {{
  const input = document.getElementById('searchInput');
  input.addEventListener('input', () => {{
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {{
      searchQuery = input.value.trim();
      applyFilters();
    }}, 300);
  }});

  const themeBtn = document.getElementById('themeToggleBtn');
  themeBtn.addEventListener('click', () => {{
    themeMode = !themeMode;
    themeBtn.classList.toggle('active', themeMode);
    renderThemeTracking();
  }});
}}

init();
</script>
</body>
</html>'''
    return html


def main():
    sessions = parse_logs()
    print(f"Parsed {len(sessions)} sessions from log files")

    for s in sessions:
        tags_str = ", ".join(s["tags"]) if s["tags"] else "none"
        print(f"  {s['date']} S{s['sessionNum']}: {s['title'][:50]} [{tags_str}]")

    html = generate_html(sessions)

    os.makedirs(OUTPUT_FILE.parent, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    file_size = os.path.getsize(OUTPUT_FILE)
    print(f"\nGenerated: {OUTPUT_FILE} ({file_size:,} bytes)")


if __name__ == "__main__":
    main()
