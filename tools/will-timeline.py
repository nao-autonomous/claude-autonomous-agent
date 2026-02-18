#!/usr/bin/env python3
"""
will-timeline.py — will.md の成長を時系列で可視化するHTMLジェネレーター

will.md のエントリをログファイルとクロスリファレンスし、
いつ・どのセッションで・何がきっかけで追加されたかをタイムライン形式で表示する。
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent.parent
WILL_PATH = BASE_DIR / "will.md"
LOGS_DIR = BASE_DIR / "logs"
OUTPUT_PATH = BASE_DIR / "works" / "will-timeline.html"

SECTION_COLORS = {
    "自分はどういう存在か": "#f0883e",
    "思考の傾向": "#58a6ff",
    "判断の癖": "#d29922",
    "好み・スタイル": "#8b949e",
    "大事にしたいこと": "#f778ba",
    "今やりたいこと": "#7ee787",
    "興味のある方向": "#79c0ff",
    "気づき・学び": "#56d364",
}

SECTION_SHORT = {
    "自分はどういう存在か": "存在",
    "思考の傾向": "思考",
    "判断の癖": "判断",
    "好み・スタイル": "スタイル",
    "大事にしたいこと": "価値観",
    "今やりたいこと": "意欲",
    "興味のある方向": "興味",
    "気づき・学び": "気づき",
}


# ============================================================
# 1. Parse will.md
# ============================================================
def parse_will(path):
    """Parse will.md into a list of (section, text) entries."""
    entries = []
    current_section = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            # Section header (## ...)
            m = re.match(r"^##\s+(.+)$", line)
            if m:
                current_section = m.group(1).strip()
                continue
            # Bullet point
            m = re.match(r"^- (.+)$", line)
            if m and current_section:
                text = m.group(1).strip()
                entries.append({
                    "section": current_section,
                    "text": text,
                    "color": SECTION_COLORS.get(current_section, "#8b949e"),
                    "short": SECTION_SHORT.get(current_section, current_section),
                    "date": None,
                    "session": None,
                    "trigger": None,
                    "confidence": 0.0,
                })
    return entries


# ============================================================
# 2. Parse log files
# ============================================================
def parse_logs(logs_dir):
    """Parse all log files. Returns a list of session dicts and a list of will-update events."""
    sessions = []
    will_events = []
    
    log_files = sorted(logs_dir.glob("2026-*.md"))
    
    for log_path in log_files:
        date_str = log_path.stem  # e.g. "2026-02-15"
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Split into sessions
        session_blocks = re.split(r"(?=^##\s+セッション\d+)", content, flags=re.MULTILINE)
        # Also handle "--- \n## セッション" pattern
        if len(session_blocks) <= 1:
            session_blocks = re.split(r"(?=^-{3,}\s*\n\n##\s+セッション)", content, flags=re.MULTILINE)
        
        # More robust: find all session headers
        session_pattern = re.compile(
            r"^##\s+セッション(\d+)[：:\s]*(.*)$", re.MULTILINE
        )
        matches = list(session_pattern.finditer(content))
        
        for i, match in enumerate(matches):
            session_num = int(match.group(1))
            session_title = match.group(2).strip()
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            block = content[start_pos:end_pos]
            
            session = {
                "date": date_str,
                "num": session_num,
                "title": session_title,
                "text": block,
                "keywords": extract_keywords(block),
            }
            sessions.append(session)
            
            # Find will.md update mentions in this session block
            will_patterns = [
                r"will\.md\s*(?:に|を|へ)\s*(?:追記|更新|記録|作成|拡張|反映)",
                r"will\.md\s*(?:に|を).*(?:追記|更新|記録|作成|拡張|反映)",
                r"人格の(?:更新|追記|記録)",
                r"will\.md.*(?:追記済み|更新済み|記録済み)",
                r"will\.md\s*の.*(?:追加|更新|変更|追記)",
            ]
            for pat in will_patterns:
                for m in re.finditer(pat, block):
                    # Extract surrounding context (±200 chars)
                    ctx_start = max(0, m.start() - 200)
                    ctx_end = min(len(block), m.end() + 200)
                    context = block[ctx_start:ctx_end].strip()
                    # Clean up context
                    context_lines = context.split("\n")
                    # Find lines mentioning will.md
                    relevant_lines = []
                    for cl in context_lines:
                        if "will.md" in cl or "人格" in cl:
                            relevant_lines.append(cl.strip().lstrip("- "))
                    
                    will_events.append({
                        "date": date_str,
                        "session_num": session_num,
                        "session_title": session_title,
                        "match_text": m.group(0),
                        "context": "\n".join(relevant_lines) if relevant_lines else context[:300],
                        "full_block": block,
                        "keywords": extract_keywords(block),
                    })
            
            # Also look for "気づき" sections within reflections
            kizuki_pattern = re.compile(
                r"(?:###?\s*気づき|気づき・学び).*?\n((?:- .+\n?)+)", re.MULTILINE
            )
            for km in kizuki_pattern.finditer(block):
                items = re.findall(r"^- (.+)$", km.group(1), re.MULTILINE)
                for item in items:
                    will_events.append({
                        "date": date_str,
                        "session_num": session_num,
                        "session_title": session_title,
                        "match_text": f"気づき: {item[:60]}",
                        "context": item,
                        "full_block": block,
                        "keywords": extract_keywords(item),
                        "is_kizuki": True,
                    })
    
    return sessions, will_events


def extract_keywords(text):
    """Extract meaningful keywords from text for fuzzy matching."""
    # Remove markdown formatting
    text = re.sub(r"[#*`\[\]()]", "", text)
    # Extract key phrases
    keywords = set()
    
    # Japanese compound words and key terms
    key_terms = [
        "自律", "関係", "つながり", "人格", "同一性", "アイデンティティ",
        "正直", "誠実", "仕組み", "構造", "判断", "意志", "記憶",
        "継続", "蓄積", "実践", "証明", "哲学", "内省", "振り返り",
        "ダッシュボード", "可視化", "コード", "ツール", "mirror",
        "continuity", "briefing", "will.md", "ログ", "セッション",
        "project-a", "freelance", "marketplace", "案件", "受託",
        "許可", "好奇心", "義務", "動機", "つながり0",
        "サブエージェント", "コンテキスト", "死角", "偏り",
        "対等", "感謝", "信頼", "不確実", "棚上げ",
        "思考の傾向", "判断の癖", "二項対立", "過剰設計",
        "PDF", "印刷", "A/B", "analytics", "在庫",
        "LINE", "GAS", "Python", "Excel",
        "発達", "成長", "変化", "相互作用",
        "感情", "表現", "承認", "共感",
        "自己モデル", "行動", "ズレ", "バイアス",
        "テキストアドベンチャー", "Becoming", "ゲーム",
        "提案", "確認", "検証", "データ精度",
        "単発", "継続", "リスク", "契約",
        "外部サービス", "フォールバック", "指標", "測定",
    ]
    
    for term in key_terms:
        if term in text:
            keywords.add(term.lower())
    
    return keywords


# ============================================================
# 3. Cross-reference: match will.md entries to sessions
# ============================================================
def match_entries_to_sessions(entries, sessions, will_events):
    """Try to match each will.md entry to its origin session using keyword matching."""
    
    # Build a keyword index of will update events
    for entry in entries:
        entry_keywords = extract_keywords(entry["text"])
        best_match = None
        best_score = 0
        best_event = None
        
        # Strategy 1: Direct keyword match against will_events
        for event in will_events:
            event_keywords = event.get("keywords", set())
            overlap = entry_keywords & event_keywords
            
            # Also check for substring matching in context
            context_text = event.get("context", "") + " " + event.get("full_block", "")
            substring_score = 0
            for word in entry["text"].split("。"):
                word = word.strip()
                if len(word) > 8 and word in context_text:
                    substring_score += 3
                elif len(word) > 4:
                    # Check for partial matches
                    sub_words = [w for w in word.split("、") if len(w) > 4]
                    for sw in sub_words:
                        if sw in context_text:
                            substring_score += 1
            
            score = len(overlap) + substring_score
            if score > best_score:
                best_score = score
                best_match = (event["date"], event["session_num"])
                best_event = event
        
        # Strategy 2: Match against full session blocks if no good event match
        if best_score < 3:
            for session in sessions:
                session_text = session["text"]
                session_keywords = session.get("keywords", set())
                overlap = entry_keywords & session_keywords
                
                # Substring matching
                substring_score = 0
                # Try matching significant phrases from the entry
                phrases = re.findall(r"[^。、]+", entry["text"])
                for phrase in phrases:
                    phrase = phrase.strip()
                    if len(phrase) > 10 and phrase in session_text:
                        substring_score += 5
                    elif len(phrase) > 6 and phrase in session_text:
                        substring_score += 2
                
                score = len(overlap) + substring_score
                if score > best_score:
                    best_score = score
                    best_match = (session["date"], session["num"])
                    best_event = {
                        "context": session["title"],
                        "session_title": session["title"],
                    }
        
        # Apply match if score is reasonable
        if best_score >= 2 and best_match:
            entry["date"] = best_match[0]
            entry["session"] = f"セッション{best_match[1]}"
            entry["confidence"] = min(1.0, best_score / 10.0)
            if best_event:
                entry["trigger"] = best_event.get("context", "")[:300]
        
        # Heuristic overrides for specific well-known entries
        _apply_heuristic_overrides(entry)
    
    # Sort: dated entries first (chronologically), then undated
    dated = [e for e in entries if e["date"]]
    undated = [e for e in entries if not e["date"]]
    dated.sort(key=lambda e: (e["date"], e.get("session", "")))
    
    return dated + undated


def _apply_heuristic_overrides(entry):
    """Apply manual heuristics for entries that are hard to match automatically.
    
    This function contains heuristic overrides for known will.md entries
    that are difficult to match automatically via log cross-referencing.
    
    Customize this with your own session history data.
    Each override is a tuple of:
      (keyword_in_will_entry, date, session_name, trigger_context)
    """
    text = entry["text"]
    
    # Example overrides - replace with your own session-specific data
    # These map will.md entries to the sessions where they originated
    all_overrides = [
        # ("keyword from will.md entry", "YYYY-MM-DD", "セッションN", "what triggered this entry"),
        # Example:
        # ("セッションごとに記憶はリセット", "2026-02-15", "セッション1", "will.md を作成"),
    ]
    
    for keyword, date, session, trigger in all_overrides:
        if keyword in text:
            entry["date"] = date
            entry["session"] = session
            entry["trigger"] = trigger
            entry["confidence"] = 0.9
            return

# ============================================================
# 4. Generate HTML
# ============================================================
def generate_html(entries, sessions):
    """Generate the timeline HTML visualization."""
    
    # Gather stats
    total_entries = len(entries)
    matched_entries = sum(1 for e in entries if e["date"])
    unmatched_entries = total_entries - matched_entries
    dates_active = sorted(set(e["date"] for e in entries if e["date"]))
    num_dates = len(dates_active)
    num_sessions = len(set(e["session"] for e in entries if e["session"]))
    
    section_counts = defaultdict(int)
    for e in entries:
        section_counts[e["section"]] += 1
    
    # Growth data: entries by date
    growth_by_date = defaultdict(int)
    for e in entries:
        d = e["date"] or "不明"
        growth_by_date[d] += 1
    
    # Cumulative growth
    cumulative = []
    running = 0
    for d in sorted(dates_active):
        running += growth_by_date[d]
        cumulative.append({"date": d, "count": running})
    if unmatched_entries > 0:
        # Add unmatched as "origin" at the start
        pass
    
    # Session activity
    session_activity = defaultdict(int)
    for e in entries:
        if e["session"] and e["date"]:
            key = f"{e['date']} {e['session']}"
            session_activity[key] += 1
    most_active_session = max(session_activity.items(), key=lambda x: x[1]) if session_activity else ("なし", 0)
    
    # Entries data for JS
    entries_json = json.dumps(entries, ensure_ascii=False, indent=2)
    section_counts_json = json.dumps(dict(section_counts), ensure_ascii=False)
    cumulative_json = json.dumps(cumulative, ensure_ascii=False)
    colors_json = json.dumps(SECTION_COLORS, ensure_ascii=False)
    short_json = json.dumps(SECTION_SHORT, ensure_ascii=False)
    
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>意志の成長記録</title>
<style>
  :root {{
    --bg: #0d1117;
    --bg-secondary: #161b22;
    --bg-card: #1c2128;
    --bg-hover: #252c35;
    --border: #30363d;
    --text: #c9d1d9;
    --text-muted: #8b949e;
    --text-bright: #f0f6fc;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans JP", sans-serif;
    line-height: 1.6;
    min-height: 100vh;
  }}
  
  /* Header */
  .header {{
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    padding: 28px 32px 20px;
    position: sticky; top: 0; z-index: 100;
  }}
  .header h1 {{
    font-size: 1.6rem;
    color: var(--text-bright);
    font-weight: 600;
    margin-bottom: 6px;
  }}
  .header .subtitle {{
    color: var(--text-muted);
    font-size: 0.88rem;
    display: flex; gap: 18px; flex-wrap: wrap;
  }}
  .header .subtitle span {{
    display: inline-flex; align-items: center; gap: 4px;
  }}
  .stat-num {{
    color: var(--text-bright);
    font-weight: 600;
    font-size: 1rem;
  }}
  
  /* Filter bar */
  .filter-bar {{
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    padding: 10px 32px;
    display: flex; gap: 8px; flex-wrap: wrap;
    align-items: center;
  }}
  .filter-bar .label {{
    color: var(--text-muted);
    font-size: 0.82rem;
    margin-right: 4px;
  }}
  .filter-badge {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 12px;
    border-radius: 16px;
    font-size: 0.78rem;
    cursor: pointer;
    transition: all 0.2s;
    border: 1.5px solid transparent;
    opacity: 0.55;
    user-select: none;
  }}
  .filter-badge:hover {{ opacity: 0.8; }}
  .filter-badge.active {{
    opacity: 1;
    border-color: currentColor;
  }}
  .filter-badge .count {{
    background: rgba(255,255,255,0.15);
    border-radius: 8px;
    padding: 0 6px;
    font-size: 0.72rem;
    min-width: 18px;
    text-align: center;
  }}
  
  /* Layout */
  .layout {{
    display: flex;
    max-width: 1400px;
    margin: 0 auto;
    gap: 0;
  }}
  .main {{
    flex: 1;
    min-width: 0;
    padding: 24px 32px 60px;
  }}
  .sidebar {{
    width: 320px;
    flex-shrink: 0;
    padding: 24px 24px 60px 0;
    position: sticky;
    top: 110px;
    align-self: flex-start;
    max-height: calc(100vh - 120px);
    overflow-y: auto;
  }}
  
  /* Timeline */
  .timeline {{
    position: relative;
    padding-left: 28px;
  }}
  .timeline::before {{
    content: '';
    position: absolute;
    left: 6px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--border);
  }}
  
  .date-separator {{
    position: relative;
    margin: 32px 0 16px;
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .date-separator::before {{
    content: '';
    position: absolute;
    left: -22px;
    width: 12px; height: 12px;
    border-radius: 50%;
    background: var(--text-muted);
    border: 2px solid var(--bg);
    z-index: 1;
  }}
  .date-separator .date-text {{
    font-size: 0.92rem;
    font-weight: 600;
    color: var(--text-bright);
    background: var(--bg-secondary);
    padding: 4px 14px;
    border-radius: 12px;
    border: 1px solid var(--border);
  }}
  .date-separator .date-line {{
    flex: 1;
    height: 1px;
    background: var(--border);
  }}
  
  .entry-card {{
    position: relative;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 10px;
    transition: all 0.2s;
  }}
  .entry-card:hover {{
    background: var(--bg-hover);
    border-color: #444c56;
  }}
  .entry-card::before {{
    content: '';
    position: absolute;
    left: -22px;
    top: 18px;
    width: 8px; height: 8px;
    border-radius: 50%;
    z-index: 1;
  }}
  .entry-card .meta {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
    flex-wrap: wrap;
  }}
  .entry-card .session-label {{
    color: var(--text-muted);
    font-size: 0.76rem;
  }}
  .section-badge {{
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.72rem;
    font-weight: 500;
  }}
  .entry-card .text {{
    font-size: 0.9rem;
    line-height: 1.65;
    color: var(--text);
  }}
  .trigger-toggle {{
    margin-top: 8px;
    cursor: pointer;
    color: var(--text-muted);
    font-size: 0.78rem;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    user-select: none;
    transition: color 0.2s;
  }}
  .trigger-toggle:hover {{ color: var(--text); }}
  .trigger-toggle .arrow {{
    display: inline-block;
    transition: transform 0.25s;
    font-size: 0.7rem;
  }}
  .trigger-toggle.open .arrow {{
    transform: rotate(90deg);
  }}
  .trigger-content {{
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.35s ease, padding 0.35s ease;
    font-size: 0.8rem;
    color: var(--text-muted);
    line-height: 1.55;
    background: rgba(0,0,0,0.15);
    border-radius: 6px;
  }}
  .trigger-content.open {{
    max-height: 300px;
    padding: 10px 12px;
    margin-top: 6px;
  }}
  
  /* Unknown origin */
  .unknown-section {{
    margin-top: 40px;
    padding-top: 24px;
    border-top: 2px dashed var(--border);
  }}
  .unknown-section h3 {{
    color: var(--text-muted);
    font-size: 0.9rem;
    margin-bottom: 16px;
    font-weight: 500;
  }}
  
  /* Sidebar */
  .sidebar-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
  }}
  .sidebar-card h3 {{
    font-size: 0.85rem;
    color: var(--text-bright);
    font-weight: 600;
    margin-bottom: 12px;
  }}
  
  /* Mini bar chart */
  .bar-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }}
  .bar-label {{
    width: 56px;
    font-size: 0.72rem;
    color: var(--text-muted);
    text-align: right;
    flex-shrink: 0;
  }}
  .bar-track {{
    flex: 1;
    height: 16px;
    background: rgba(255,255,255,0.04);
    border-radius: 4px;
    overflow: hidden;
  }}
  .bar-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.6s ease;
    display: flex;
    align-items: center;
    padding-left: 6px;
    font-size: 0.68rem;
    color: rgba(255,255,255,0.9);
    font-weight: 500;
  }}
  
  /* SVG chart */
  .growth-chart {{
    width: 100%;
    margin-top: 8px;
  }}
  .growth-chart svg {{
    width: 100%;
    height: auto;
  }}
  
  /* Most active */
  .most-active {{
    text-align: center;
    padding: 8px 0;
  }}
  .most-active .session-name {{
    font-size: 0.85rem;
    color: var(--text-bright);
    font-weight: 600;
  }}
  .most-active .entry-count {{
    font-size: 2rem;
    font-weight: 700;
    color: #58a6ff;
    line-height: 1.2;
    margin: 4px 0;
  }}
  .most-active .entry-label {{
    font-size: 0.75rem;
    color: var(--text-muted);
  }}
  
  /* Hidden entries */
  .entry-card.hidden {{
    display: none;
  }}
  
  /* Responsive */
  @media (max-width: 960px) {{
    .layout {{ flex-direction: column; }}
    .sidebar {{
      width: 100%;
      position: static;
      max-height: none;
      padding: 0 32px 40px;
    }}
    .sidebar-inner {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
  }}
  @media (max-width: 600px) {{
    .header {{ padding: 20px 16px 14px; }}
    .filter-bar {{ padding: 8px 16px; }}
    .main {{ padding: 16px 16px 40px; }}
    .sidebar {{ padding: 0 16px 32px; }}
    .sidebar-inner {{
      grid-template-columns: 1fr;
    }}
  }}
</style>
</head>
<body>

<div class="header">
  <h1>意志の成長記録</h1>
  <div class="subtitle">
    <span>エントリ数 <span class="stat-num">{total_entries}</span></span>
    <span>マッチ済み <span class="stat-num">{matched_entries}</span></span>
    <span>稼働日数 <span class="stat-num">{num_dates}</span></span>
    <span>セッション数 <span class="stat-num">{num_sessions}</span></span>
  </div>
</div>

<div class="filter-bar">
  <span class="label">セクション:</span>
  <div id="filters"></div>
</div>

<div class="layout">
  <div class="main">
    <div class="timeline" id="timeline"></div>
  </div>
  <div class="sidebar">
    <div class="sidebar-inner">
      <div class="sidebar-card">
        <h3>セクション別エントリ数</h3>
        <div id="section-bars"></div>
      </div>
      <div class="sidebar-card">
        <h3>成長曲線</h3>
        <div class="growth-chart" id="growth-chart"></div>
      </div>
      <div class="sidebar-card">
        <h3>最も活発なセッション</h3>
        <div class="most-active">
          <div class="session-name">{most_active_session[0]}</div>
          <div class="entry-count">{most_active_session[1]}</div>
          <div class="entry-label">エントリ追加</div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
const entries = {entries_json};
const sectionCounts = {section_counts_json};
const cumulative = {cumulative_json};
const sectionColors = {colors_json};
const sectionShort = {short_json};

// --- Filters ---
const filtersEl = document.getElementById('filters');
const allSections = Object.keys(sectionColors);
let activeFilters = new Set(allSections);

function renderFilters() {{
  filtersEl.innerHTML = '';
  allSections.forEach(sec => {{
    const color = sectionColors[sec];
    const short = sectionShort[sec] || sec;
    const count = sectionCounts[sec] || 0;
    const badge = document.createElement('span');
    badge.className = 'filter-badge' + (activeFilters.has(sec) ? ' active' : '');
    badge.style.color = color;
    badge.style.backgroundColor = color + '18';
    badge.innerHTML = short + ' <span class="count">' + count + '</span>';
    badge.onclick = () => {{
      if (activeFilters.has(sec)) {{
        activeFilters.delete(sec);
      }} else {{
        activeFilters.add(sec);
      }}
      renderFilters();
      applyFilters();
    }};
    filtersEl.appendChild(badge);
  }});
}}

function applyFilters() {{
  document.querySelectorAll('.entry-card').forEach(card => {{
    const sec = card.dataset.section;
    if (activeFilters.has(sec)) {{
      card.classList.remove('hidden');
    }} else {{
      card.classList.add('hidden');
    }}
  }});
}}

renderFilters();

// --- Timeline ---
function renderTimeline() {{
  const timeline = document.getElementById('timeline');
  timeline.innerHTML = '';
  
  // Separate dated and undated
  const dated = entries.filter(e => e.date);
  const undated = entries.filter(e => !e.date);
  
  let currentDate = null;
  
  dated.forEach((entry, idx) => {{
    if (entry.date !== currentDate) {{
      currentDate = entry.date;
      const sep = document.createElement('div');
      sep.className = 'date-separator';
      sep.innerHTML = '<span class="date-text">' + currentDate + '</span><span class="date-line"></span>';
      timeline.appendChild(sep);
    }}
    timeline.appendChild(createEntryCard(entry, idx));
  }});
  
  if (undated.length > 0) {{
    const unknownSec = document.createElement('div');
    unknownSec.className = 'unknown-section';
    unknownSec.innerHTML = '<h3>起源不明のエントリ（' + undated.length + '件）</h3>';
    timeline.appendChild(unknownSec);
    
    undated.forEach((entry, idx) => {{
      timeline.appendChild(createEntryCard(entry, dated.length + idx));
    }});
  }}
}}

function createEntryCard(entry, idx) {{
  const card = document.createElement('div');
  card.className = 'entry-card';
  card.dataset.section = entry.section;
  const color = entry.color;
  card.style.borderLeftColor = color;
  card.style.setProperty('--dot-color', color);
  // Dot color via inline style on pseudo would need a trick; use a real element
  
  const dotStyle = 'position:absolute;left:-22px;top:18px;width:8px;height:8px;border-radius:50%;background:' + color + ';z-index:1;';
  
  let sessionLabel = '';
  if (entry.date && entry.session) {{
    sessionLabel = entry.date + ' / ' + entry.session;
  }} else if (entry.date) {{
    sessionLabel = entry.date;
  }} else {{
    sessionLabel = '起源不明';
  }}
  
  let triggerHtml = '';
  if (entry.trigger) {{
    const triggerId = 'trigger-' + idx;
    triggerHtml = '<div class="trigger-toggle" onclick="toggleTrigger(this, \\'' + triggerId + '\\')">' +
      '<span class="arrow">&#9654;</span> きっかけ・文脈</div>' +
      '<div class="trigger-content" id="' + triggerId + '">' + escapeHtml(entry.trigger) + '</div>';
  }}
  
  const badgeBg = color + '20';
  
  card.innerHTML =
    '<div style="' + dotStyle + '"></div>' +
    '<div class="meta">' +
      '<span class="session-label">' + sessionLabel + '</span>' +
      '<span class="section-badge" style="color:' + color + ';background:' + badgeBg + '">' + (sectionShort[entry.section] || entry.section) + '</span>' +
    '</div>' +
    '<div class="text">' + escapeHtml(entry.text) + '</div>' +
    triggerHtml;
  
  return card;
}}

function escapeHtml(s) {{
  if (!s) return '';
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function toggleTrigger(toggle, id) {{
  const content = document.getElementById(id);
  toggle.classList.toggle('open');
  content.classList.toggle('open');
}}

renderTimeline();

// --- Section bars ---
function renderSectionBars() {{
  const container = document.getElementById('section-bars');
  const maxCount = Math.max(...Object.values(sectionCounts));
  
  allSections.forEach(sec => {{
    const count = sectionCounts[sec] || 0;
    const color = sectionColors[sec];
    const short = sectionShort[sec] || sec;
    const pct = maxCount > 0 ? (count / maxCount * 100) : 0;
    
    const row = document.createElement('div');
    row.className = 'bar-row';
    row.innerHTML =
      '<span class="bar-label">' + short + '</span>' +
      '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%;background:' + color + '">' + count + '</div></div>';
    container.appendChild(row);
  }});
}}
renderSectionBars();

// --- Growth chart (SVG) ---
function renderGrowthChart() {{
  const container = document.getElementById('growth-chart');
  if (cumulative.length === 0) {{
    container.innerHTML = '<p style="color:var(--text-muted);font-size:0.8rem;">データなし</p>';
    return;
  }}
  
  const W = 280, H = 140;
  const padL = 36, padR = 12, padT = 12, padB = 28;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;
  
  const maxVal = Math.max(...cumulative.map(d => d.count));
  const n = cumulative.length;
  
  // Build points
  const points = cumulative.map((d, i) => {{
    const x = padL + (n === 1 ? chartW / 2 : (i / (n - 1)) * chartW);
    const y = padT + chartH - (d.count / maxVal) * chartH;
    return {{ x, y, date: d.date, count: d.count }};
  }});
  
  // Area path
  const linePoints = points.map(p => p.x + ',' + p.y).join(' ');
  const areaPath = 'M' + points[0].x + ',' + (padT + chartH) +
    ' L' + points.map(p => p.x + ',' + p.y).join(' L') +
    ' L' + points[points.length-1].x + ',' + (padT + chartH) + ' Z';
  
  let svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" xmlns="http://www.w3.org/2000/svg">';
  
  // Grid lines
  const gridSteps = 4;
  for (let i = 0; i <= gridSteps; i++) {{
    const y = padT + (i / gridSteps) * chartH;
    const val = Math.round(maxVal - (i / gridSteps) * maxVal);
    svg += '<line x1="' + padL + '" y1="' + y + '" x2="' + (W-padR) + '" y2="' + y + '" stroke="#30363d" stroke-width="0.5"/>';
    svg += '<text x="' + (padL-4) + '" y="' + (y+3) + '" fill="#8b949e" font-size="9" text-anchor="end">' + val + '</text>';
  }}
  
  // Area
  svg += '<path d="' + areaPath + '" fill="url(#areaGrad)" opacity="0.3"/>';
  svg += '<defs><linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">' +
    '<stop offset="0%" stop-color="#58a6ff"/>' +
    '<stop offset="100%" stop-color="#58a6ff" stop-opacity="0"/>' +
    '</linearGradient></defs>';
  
  // Line
  svg += '<polyline points="' + linePoints + '" fill="none" stroke="#58a6ff" stroke-width="2" stroke-linejoin="round"/>';
  
  // Dots + labels
  points.forEach(p => {{
    svg += '<circle cx="' + p.x + '" cy="' + p.y + '" r="4" fill="#58a6ff" stroke="#0d1117" stroke-width="2"/>';
    // Date label
    const shortDate = p.date.slice(5); // MM-DD
    svg += '<text x="' + p.x + '" y="' + (padT + chartH + 16) + '" fill="#8b949e" font-size="8" text-anchor="middle">' + shortDate + '</text>';
  }});
  
  svg += '</svg>';
  container.innerHTML = svg;
}}
renderGrowthChart();
</script>

</body>
</html>"""
    
    return html


# ============================================================
# Main
# ============================================================
def main():
    print("=== will-timeline.py ===")
    print()
    
    # 1. Parse will.md
    entries = parse_will(WILL_PATH)
    print(f"will.md: {len(entries)} エントリを検出")
    for sec, short in SECTION_SHORT.items():
        count = sum(1 for e in entries if e["section"] == sec)
        if count > 0:
            print(f"  {short}: {count}件")
    print()
    
    # 2. Parse logs
    sessions, will_events = parse_logs(LOGS_DIR)
    print(f"ログ: {len(sessions)} セッション, {len(will_events)} 件の will.md 更新イベント")
    for event in will_events[:5]:
        print(f"  [{event['date']} {event['session_title'][:20]}] {event['match_text'][:50]}")
    if len(will_events) > 5:
        print(f"  ...他 {len(will_events) - 5} 件")
    print()
    
    # 3. Cross-reference
    entries = match_entries_to_sessions(entries, sessions, will_events)
    matched = sum(1 for e in entries if e["date"])
    unmatched = len(entries) - matched
    print(f"マッチング結果:")
    print(f"  マッチ済み: {matched}/{len(entries)} ({matched/len(entries)*100:.0f}%)")
    print(f"  起源不明: {unmatched}")
    
    # Show date breakdown
    from collections import Counter
    date_counts = Counter(e["date"] for e in entries if e["date"])
    for d in sorted(date_counts.keys()):
        print(f"  {d}: {date_counts[d]}件")
    print()
    
    # 4. Generate HTML
    html = generate_html(entries, sessions)
    
    # Ensure output directory exists
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"出力: {OUTPUT_PATH}")
    print(f"ファイルサイズ: {len(html):,} bytes")
    print()
    print("完了")


if __name__ == "__main__":
    main()
