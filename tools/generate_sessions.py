#!/usr/bin/env python3
"""
Session Timeline Generator
Reads log files from logs/ and generates an interactive HTML timeline at works/sessions.html
"""

import re
import os
import json
from pathlib import Path
from collections import Counter, defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
OUTPUT_FILE = BASE_DIR / "works" / "sessions.html"

# Category definitions
CATEGORIES = {
    "内省/哲学": {
        "color": "#58a6ff",  # blue
        "emoji": "🔵",
        "keywords": [
            "will.md", "identity", "同一性", "哲学", "内省", "思考", "mirror",
            "自己", "人格", "意識", "正直", "動機", "振り返り", "reflect",
            "thoughts/", "つながり0", "自己報告", "continuity", "becoming",
        ],
    },
    "制作": {
        "color": "#3fb950",  # green
        "emoji": "🟢",
        "keywords": [
            "作成", "作った", "HTML", "ダッシュボード", "ツール", "ゲーム",
            "game.html", "dashboard", "スクリプト", "py を作成", "v2",
            "テキストアドベンチャー", "サンプル", "プロトタイプ", "出力",
        ],
    },
    "実務": {
        "color": "#d29922",  # orange
        "emoji": "🟠",
        "keywords": [
            "project-a", "freelance", "project", "proposal",
            "listing", "business", "sales",
            "A/B test", "analytics", "search console",
            "trade", "PDF", "value", "education", "research",
        ],
    },
    "インフラ": {
        "color": "#bc8cff",  # purple
        "emoji": "🟣",
        "keywords": [
            "CLAUDE.md", "briefing.py", "index-logs", "ログ", "仕組み",
            "タスク管理", "tasks.md", "権限ルール", "判断日誌", "decisions/",
            "コンテキスト節約", "サブエージェント", "基盤", "インフラ",
        ],
    },
    "対話": {
        "color": "#f85149",  # red
        "emoji": "🔴",
        "keywords": [
            "ユーザーから", "ユーザーに", "フィードバック", "議論", "相談",
            "ヒアリング", "報告", "好評", "反応", "問いかけ", "聞いた",
            "依頼", "提案を提出",
        ],
    },
}


def parse_logs():
    """Parse all log files and extract sessions."""
    sessions = []
    log_files = sorted(LOGS_DIR.glob("2026-02-*.md"))

    for log_file in log_files:
        date_str = log_file.stem  # e.g. "2026-02-15"
        content = log_file.read_text(encoding="utf-8")
        # Split into sessions by ## セッション headers
        session_blocks = re.split(r"(?=^## セッション)", content, flags=re.MULTILINE)

        for block in session_blocks:
            block = block.strip()
            if not block.startswith("## セッション"):
                continue

            # Extract session header
            header_match = re.match(r"^## セッション(\d+)[:：]\s*(.+)$", block, re.MULTILINE)
            if not header_match:
                continue

            session_num = int(header_match.group(1))
            session_title = header_match.group(2).strip()

            # Extract bullet points (first-level only)
            bullets = []
            for line in block.split("\n"):
                line_s = line.strip()
                if re.match(r"^- .+", line_s) and not line.startswith("  "):
                    bullet_text = line_s[2:].strip()
                    # Clean up markdown formatting
                    bullet_text = re.sub(r"\*\*(.+?)\*\*", r"\1", bullet_text)
                    bullet_text = re.sub(r"`(.+?)`", r"\1", bullet_text)
                    bullets.append(bullet_text)

            # Extract subsection titles
            subsections = re.findall(r"^### (.+)$", block, re.MULTILINE)
            # Filter out meta-subsections
            subsections = [s for s in subsections if not s.startswith("セッション") and s != "次の自分へ"]

            # Categorize based on content keywords
            cats = categorize_session(block)

            # Extract key activities (summarize bullets to top N)
            key_activities = bullets[:8]

            sessions.append({
                "date": date_str,
                "date_display": f"{int(date_str.split('-')[1])}/{int(date_str.split('-')[2])}",
                "session_num": session_num,
                "title": session_title,
                "bullets": bullets,
                "key_activities": key_activities,
                "subsections": subsections,
                "categories": cats,
                "full_text": block,
            })

    return sessions


def categorize_session(text):
    """Categorize a session based on keyword matching. Returns list of (category_name, score)."""
    results = []
    text_lower = text.lower()
    for cat_name, cat_info in CATEGORIES.items():
        score = 0
        for kw in cat_info["keywords"]:
            count = text_lower.count(kw.lower())
            score += count
        if score > 0:
            results.append((cat_name, score))
    # Sort by score descending, return top categories
    results.sort(key=lambda x: -x[1])
    # Return at least 1, at most 3 categories
    if not results:
        results = [("制作", 1)]
    return [r[0] for r in results[:3]]


def compute_stats(sessions):
    """Compute summary statistics."""
    total_sessions = len(sessions)
    dates = sorted(set(s["date"] for s in sessions))
    total_days = len(dates)
    avg_per_day = round(total_sessions / total_days, 1) if total_days else 0

    # Category distribution
    cat_counts = Counter()
    for s in sessions:
        for c in s["categories"]:
            cat_counts[c] += 1

    # Sessions per day
    sessions_per_day = defaultdict(int)
    for s in sessions:
        sessions_per_day[s["date"]] += 1

    # Key milestones
    milestones = [
        {"date": "2/15", "session": 1, "text": "自律エージェント基盤構築 — CLAUDE.md, will.md 作成"},
        {"date": "2/15", "session": 2, "text": "人格の核を作る — reflect.md, thoughts/identity.md"},
        {"date": "2/16", "session": 2, "text": "Project analysis started — 1,075 data records analyzed"},
        {"date": "2/16", "session": 4, "text": "Becoming ゲーム作成 — 初の創作物"},
        {"date": "2/17", "session": 1, "text": "mirror.py 作成 — 自己モデル vs 行動のズレ検出"},
        {"date": "2/17", "session": 2, "text": "Project dashboard created — first practical deliverable"},
        {"date": "2/17", "session": 4, "text": "First freelance listing — first step toward monetization"},
        {"date": "2/17", "session": 7, "text": "First project proposal — education sector Excel project"},
    ]

    return {
        "total_sessions": total_sessions,
        "total_days": total_days,
        "avg_per_day": avg_per_day,
        "cat_counts": dict(cat_counts),
        "sessions_per_day": dict(sessions_per_day),
        "milestones": milestones,
    }


def generate_html(sessions, stats):
    """Generate the full HTML file."""

    # Prepare sessions JSON for JS
    sessions_json = json.dumps(sessions, ensure_ascii=False, indent=2)
    stats_json = json.dumps(stats, ensure_ascii=False, indent=2)

    # Category info for JS
    cat_info = {}
    for name, info in CATEGORIES.items():
        cat_info[name] = {"color": info["color"], "emoji": info["emoji"]}
    cat_info_json = json.dumps(cat_info, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Session Timeline</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        :root {{
            --bg-primary: #0d1117;
            --bg-card: #161b22;
            --bg-card-hover: #1c2129;
            --bg-elevated: #21262d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --border: #30363d;
            --border-light: #21262d;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-orange: #d29922;
            --accent-purple: #bc8cff;
            --accent-red: #f85149;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Sans", "Hiragino Kaku Gothic ProN", Meiryo, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        /* Header */
        .page-header {{
            text-align: center;
            margin-bottom: 40px;
            padding: 30px 0;
        }}

        .page-header h1 {{
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 8px;
        }}

        .page-header .subtitle {{
            color: var(--text-secondary);
            font-size: 1rem;
        }}

        /* Stats Panel */
        .stats-panel {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 30px;
        }}

        .stat-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            transition: transform 0.2s, border-color 0.2s;
        }}

        .stat-card:hover {{
            transform: translateY(-2px);
            border-color: var(--accent-blue);
        }}

        .stat-value {{
            font-size: 2.4rem;
            font-weight: 700;
            color: var(--accent-blue);
            line-height: 1.2;
        }}

        .stat-label {{
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-top: 4px;
        }}

        /* Charts Row */
        .charts-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }}

        @media (max-width: 768px) {{
            .charts-row {{
                grid-template-columns: 1fr;
            }}
        }}

        .chart-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
        }}

        .chart-card h3 {{
            color: var(--text-primary);
            font-size: 1rem;
            margin-bottom: 16px;
            font-weight: 600;
        }}

        .chart-container {{
            position: relative;
            height: 220px;
        }}

        /* Milestones */
        .milestones-section {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 30px;
        }}

        .milestones-section h3 {{
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 16px;
            color: var(--text-primary);
        }}

        .milestone-list {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 10px;
        }}

        .milestone-item {{
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 10px 12px;
            background: var(--bg-elevated);
            border-radius: 8px;
            font-size: 0.85rem;
            border-left: 3px solid var(--accent-purple);
        }}

        .milestone-date {{
            color: var(--accent-blue);
            font-weight: 600;
            white-space: nowrap;
            min-width: 32px;
        }}

        .milestone-text {{
            color: var(--text-secondary);
        }}

        /* Filter Bar */
        .filter-bar {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 24px;
            align-items: center;
        }}

        .filter-label {{
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-right: 4px;
        }}

        .filter-pill {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.8rem;
            cursor: pointer;
            border: 1px solid var(--border);
            background: var(--bg-card);
            color: var(--text-secondary);
            transition: all 0.2s;
            user-select: none;
        }}

        .filter-pill:hover {{
            border-color: var(--text-muted);
        }}

        .filter-pill.active {{
            border-color: var(--text-primary);
            color: var(--text-primary);
            background: var(--bg-elevated);
        }}

        .filter-pill .dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }}

        /* Day Group */
        .day-group {{
            margin-bottom: 32px;
        }}

        .day-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 20px;
            cursor: pointer;
            user-select: none;
        }}

        .day-header:hover .day-title {{
            color: var(--accent-blue);
        }}

        .day-date-badge {{
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            color: #fff;
            font-weight: 700;
            font-size: 1.1rem;
            padding: 8px 16px;
            border-radius: 10px;
            min-width: 60px;
            text-align: center;
        }}

        .day-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text-primary);
            transition: color 0.2s;
        }}

        .day-session-count {{
            color: var(--text-muted);
            font-size: 0.85rem;
        }}

        .day-chevron {{
            color: var(--text-muted);
            font-size: 1.2rem;
            margin-left: auto;
            transition: transform 0.3s;
        }}

        .day-group.collapsed .day-chevron {{
            transform: rotate(-90deg);
        }}

        .day-group.collapsed .timeline-wrapper {{
            display: none;
        }}

        /* Timeline */
        .timeline-wrapper {{
            position: relative;
            padding-left: 40px;
        }}

        .timeline-line {{
            position: absolute;
            left: 18px;
            top: 0;
            bottom: 0;
            width: 2px;
            border-radius: 1px;
        }}

        /* Session Card */
        .session-card {{
            position: relative;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .session-card:hover {{
            border-color: var(--text-muted);
            background: var(--bg-card-hover);
        }}

        .session-card::before {{
            content: '';
            position: absolute;
            left: -30px;
            top: 24px;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            border: 2px solid var(--accent-blue);
            background: var(--bg-primary);
            z-index: 1;
        }}

        .session-card::after {{
            content: '';
            position: absolute;
            left: -23px;
            top: 31px;
            width: 16px;
            height: 1px;
            background: var(--border);
        }}

        .session-card-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 10px;
        }}

        .session-number {{
            color: var(--accent-blue);
            font-weight: 700;
            font-size: 0.8rem;
            background: rgba(88, 166, 255, 0.1);
            padding: 2px 10px;
            border-radius: 12px;
            white-space: nowrap;
        }}

        .session-title {{
            font-size: 1.05rem;
            font-weight: 600;
            color: var(--text-primary);
            flex: 1;
        }}

        .session-expand-icon {{
            color: var(--text-muted);
            font-size: 0.9rem;
            transition: transform 0.3s;
            flex-shrink: 0;
        }}

        .session-card.expanded .session-expand-icon {{
            transform: rotate(180deg);
        }}

        .session-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 12px;
        }}

        .tag-pill {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.72rem;
            font-weight: 500;
            border: 1px solid;
        }}

        .session-activities {{
            list-style: none;
            padding: 0;
        }}

        .session-activities li {{
            color: var(--text-secondary);
            font-size: 0.85rem;
            padding: 3px 0;
            padding-left: 16px;
            position: relative;
            line-height: 1.5;
        }}

        .session-activities li::before {{
            content: '•';
            position: absolute;
            left: 0;
            color: var(--text-muted);
        }}

        /* Expanded details */
        .session-details {{
            display: none;
            margin-top: 14px;
            padding-top: 14px;
            border-top: 1px solid var(--border-light);
        }}

        .session-card.expanded .session-details {{
            display: block;
        }}

        .session-details h4 {{
            color: var(--text-secondary);
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
            margin-top: 12px;
        }}

        .session-details h4:first-child {{
            margin-top: 0;
        }}

        .subsection-list {{
            list-style: none;
            padding: 0;
        }}

        .subsection-list li {{
            color: var(--text-secondary);
            font-size: 0.85rem;
            padding: 4px 0 4px 16px;
            position: relative;
        }}

        .subsection-list li::before {{
            content: '§';
            position: absolute;
            left: 0;
            color: var(--accent-purple);
            font-weight: 600;
        }}

        .all-bullets {{
            list-style: none;
            padding: 0;
        }}

        .all-bullets li {{
            color: var(--text-secondary);
            font-size: 0.82rem;
            padding: 3px 0 3px 16px;
            position: relative;
            line-height: 1.5;
        }}

        .all-bullets li::before {{
            content: '–';
            position: absolute;
            left: 0;
            color: var(--text-muted);
        }}

        /* Footer */
        .page-footer {{
            text-align: center;
            padding: 30px 0;
            color: var(--text-muted);
            font-size: 0.8rem;
        }}

        /* Responsive */
        @media (max-width: 600px) {{
            body {{
                padding: 12px;
            }}

            .page-header h1 {{
                font-size: 1.6rem;
            }}

            .stats-panel {{
                grid-template-columns: repeat(2, 1fr);
            }}

            .timeline-wrapper {{
                padding-left: 30px;
            }}

            .timeline-line {{
                left: 12px;
            }}

            .session-card::before {{
                left: -24px;
                width: 10px;
                height: 10px;
            }}

            .session-card::after {{
                left: -18px;
                top: 29px;
                width: 12px;
            }}
        }}

        /* Animations */
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .session-card {{
            animation: fadeIn 0.3s ease-out;
        }}

        /* Scrollbar */
        ::-webkit-scrollbar {{
            width: 8px;
        }}
        ::-webkit-scrollbar-track {{
            background: var(--bg-primary);
        }}
        ::-webkit-scrollbar-thumb {{
            background: var(--border);
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: var(--text-muted);
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="page-header">
            <h1>Session Timeline</h1>
            <div class="subtitle">自律エージェントの活動記録 — 2026年2月15日〜17日</div>
        </div>

        <!-- Stats Panel -->
        <div class="stats-panel">
            <div class="stat-card">
                <div class="stat-value" id="stat-sessions">0</div>
                <div class="stat-label">Total Sessions</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="stat-days">0</div>
                <div class="stat-label">Days</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="stat-avg">0</div>
                <div class="stat-label">Sessions / Day</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="stat-bullets">0</div>
                <div class="stat-label">Activities Logged</div>
            </div>
        </div>

        <!-- Charts Row -->
        <div class="charts-row">
            <div class="chart-card">
                <h3>Activity Distribution</h3>
                <div class="chart-container">
                    <canvas id="catChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <h3>Sessions per Day</h3>
                <div class="chart-container">
                    <canvas id="dayChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Milestones -->
        <div class="milestones-section">
            <h3>Key Milestones</h3>
            <div class="milestone-list" id="milestones"></div>
        </div>

        <!-- Filter Bar -->
        <div class="filter-bar">
            <span class="filter-label">Filter:</span>
            <div class="filter-pill active" data-filter="all" onclick="toggleFilter(this)">
                All
            </div>
        </div>

        <!-- Timeline -->
        <div id="timeline"></div>

        <!-- Footer -->
        <div class="page-footer">
            Generated from logs/ — Session Timeline Visualization
        </div>
    </div>

    <script>
    // Data
    const sessions = {sessions_json};
    const stats = {stats_json};
    const catInfo = {cat_info_json};

    // Active filters
    let activeFilters = new Set(['all']);

    // Init
    document.addEventListener('DOMContentLoaded', () => {{
        renderStats();
        renderCharts();
        renderMilestones();
        renderFilterBar();
        renderTimeline();
    }});

    function renderStats() {{
        document.getElementById('stat-sessions').textContent = stats.total_sessions;
        document.getElementById('stat-days').textContent = stats.total_days;
        document.getElementById('stat-avg').textContent = stats.avg_per_day;
        const totalBullets = sessions.reduce((sum, s) => sum + s.bullets.length, 0);
        document.getElementById('stat-bullets').textContent = totalBullets;
    }}

    function renderCharts() {{
        // Activity Distribution Donut
        const catLabels = Object.keys(stats.cat_counts);
        const catValues = catLabels.map(l => stats.cat_counts[l]);
        const catColors = catLabels.map(l => catInfo[l] ? catInfo[l].color : '#666');

        new Chart(document.getElementById('catChart'), {{
            type: 'doughnut',
            data: {{
                labels: catLabels,
                datasets: [{{
                    data: catValues,
                    backgroundColor: catColors,
                    borderColor: '#0d1117',
                    borderWidth: 2,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'right',
                        labels: {{
                            color: '#e6edf3',
                            font: {{ size: 12 }},
                            padding: 12,
                            generateLabels: function(chart) {{
                                const data = chart.data;
                                return data.labels.map((label, i) => ({{
                                    text: (catInfo[label] ? catInfo[label].emoji + ' ' : '') + label,
                                    fillStyle: data.datasets[0].backgroundColor[i],
                                    strokeStyle: data.datasets[0].backgroundColor[i],
                                    lineWidth: 0,
                                    hidden: false,
                                    index: i,
                                    fontColor: '#e6edf3',
                                }}));
                            }}
                        }}
                    }}
                }},
                cutout: '60%',
            }}
        }});

        // Sessions per Day Bar
        const dayLabels = Object.keys(stats.sessions_per_day).map(d => {{
            const parts = d.split('-');
            return parts[1] + '/' + parts[2];
        }});
        const dayValues = Object.values(stats.sessions_per_day);

        // Gradient colors per day
        const dayColors = dayLabels.map((_, i) => {{
            const t = i / Math.max(dayLabels.length - 1, 1);
            return `rgba(${{88 + Math.round(100 * t)}}, ${{166 - Math.round(40 * t)}}, ${{255 - Math.round(100 * t)}}, 0.8)`;
        }});

        new Chart(document.getElementById('dayChart'), {{
            type: 'bar',
            data: {{
                labels: dayLabels,
                datasets: [{{
                    label: 'Sessions',
                    data: dayValues,
                    backgroundColor: dayColors,
                    borderColor: dayColors.map(c => c.replace('0.8', '1')),
                    borderWidth: 1,
                    borderRadius: 6,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            color: '#8b949e',
                            stepSize: 1,
                        }},
                        grid: {{
                            color: 'rgba(48, 54, 61, 0.5)',
                        }},
                    }},
                    x: {{
                        ticks: {{ color: '#8b949e' }},
                        grid: {{ display: false }},
                    }}
                }},
                plugins: {{
                    legend: {{ display: false }},
                }}
            }}
        }});
    }}

    function renderMilestones() {{
        const container = document.getElementById('milestones');
        container.innerHTML = stats.milestones.map(m => `
            <div class="milestone-item">
                <span class="milestone-date">${{m.date}}</span>
                <span class="milestone-text">${{m.text}}</span>
            </div>
        `).join('');
    }}

    function renderFilterBar() {{
        const bar = document.querySelector('.filter-bar');
        // Add category pills
        for (const [name, info] of Object.entries(catInfo)) {{
            const pill = document.createElement('div');
            pill.className = 'filter-pill';
            pill.dataset.filter = name;
            pill.innerHTML = `<span class="dot" style="background:${{info.color}}"></span>${{info.emoji}} ${{name}}`;
            pill.onclick = function() {{ toggleFilter(this); }};
            bar.appendChild(pill);
        }}
    }}

    function toggleFilter(el) {{
        const filter = el.dataset.filter;

        if (filter === 'all') {{
            // Reset to all
            activeFilters = new Set(['all']);
            document.querySelectorAll('.filter-pill').forEach(p => {{
                p.classList.toggle('active', p.dataset.filter === 'all');
            }});
        }} else {{
            // Remove 'all' if clicking a category
            activeFilters.delete('all');
            document.querySelector('.filter-pill[data-filter="all"]').classList.remove('active');

            if (activeFilters.has(filter)) {{
                activeFilters.delete(filter);
                el.classList.remove('active');
            }} else {{
                activeFilters.add(filter);
                el.classList.add('active');
            }}

            // If nothing selected, go back to all
            if (activeFilters.size === 0) {{
                activeFilters = new Set(['all']);
                document.querySelector('.filter-pill[data-filter="all"]').classList.add('active');
            }}
        }}

        renderTimeline();
    }}

    function sessionMatchesFilter(session) {{
        if (activeFilters.has('all')) return true;
        return session.categories.some(c => activeFilters.has(c));
    }}

    function renderTimeline() {{
        const container = document.getElementById('timeline');
        container.innerHTML = '';

        // Group by date
        const grouped = {{}};
        sessions.forEach(s => {{
            if (!grouped[s.date]) grouped[s.date] = [];
            grouped[s.date].push(s);
        }});

        const dates = Object.keys(grouped).sort();

        // Compute color gradient
        let globalIdx = 0;
        const totalSessions = sessions.length;

        dates.forEach(date => {{
            const daySessions = grouped[date];
            const filteredSessions = daySessions.filter(sessionMatchesFilter);

            const dayGroup = document.createElement('div');
            dayGroup.className = 'day-group';

            // Day header
            const parts = date.split('-');
            const dateDisplay = parseInt(parts[1]) + '/' + parseInt(parts[2]);
            const dayNames = {{ '2026-02-15': '日', '2026-02-16': '月', '2026-02-17': '火' }};
            const dayName = dayNames[date] || '';

            dayGroup.innerHTML = `
                <div class="day-header" onclick="toggleDayGroup(this)">
                    <div class="day-date-badge">${{dateDisplay}}</div>
                    <div>
                        <div class="day-title">Day ${{dates.indexOf(date) + 1}}${{dayName ? ' (' + dayName + ')' : ''}}</div>
                        <div class="day-session-count">${{daySessions.length}} sessions${{filteredSessions.length !== daySessions.length ? ' (' + filteredSessions.length + ' shown)' : ''}}</div>
                    </div>
                    <div class="day-chevron">▼</div>
                </div>
            `;

            // Timeline wrapper
            const timelineWrapper = document.createElement('div');
            timelineWrapper.className = 'timeline-wrapper';

            // Timeline vertical line with gradient
            const startColor = getGradientColor(globalIdx, totalSessions);
            const endColor = getGradientColor(globalIdx + daySessions.length - 1, totalSessions);
            const line = document.createElement('div');
            line.className = 'timeline-line';
            line.style.background = `linear-gradient(to bottom, ${{startColor}}, ${{endColor}})`;
            timelineWrapper.appendChild(line);

            filteredSessions.forEach(session => {{
                const card = createSessionCard(session, globalIdx + daySessions.indexOf(session), totalSessions);
                timelineWrapper.appendChild(card);
            }});

            globalIdx += daySessions.length;

            dayGroup.appendChild(timelineWrapper);
            container.appendChild(dayGroup);
        }});
    }}

    function getGradientColor(idx, total) {{
        const t = total > 1 ? idx / (total - 1) : 0;
        // Blue to purple to green gradient
        const r = Math.round(88 + (63 - 88) * t + (188 - 63) * Math.pow(t, 2));
        const g = Math.round(166 + (185 - 166) * t);
        const b = Math.round(255 + (80 - 255) * t * 0.5);
        return `rgb(${{r}}, ${{g}}, ${{b}})`;
    }}

    function createSessionCard(session, globalIdx, totalSessions) {{
        const card = document.createElement('div');
        card.className = 'session-card';

        const nodeColor = getGradientColor(globalIdx, totalSessions);
        card.style.setProperty('--node-color', nodeColor);

        // Override the ::before pseudo element color via inline style trick
        const styleId = `style-${{session.date}}-${{session.session_num}}`;

        // Tags HTML
        const tagsHtml = session.categories.map(cat => {{
            const info = catInfo[cat];
            if (!info) return '';
            return `<span class="tag-pill" style="color:${{info.color}};border-color:${{info.color}}33;background:${{info.color}}11">${{info.emoji}} ${{cat}}</span>`;
        }}).join('');

        // Key activities (collapsed view)
        const activitiesHtml = session.key_activities.slice(0, 4).map(a =>
            `<li>${{escapeHtml(a)}}</li>`
        ).join('');

        // All bullets (expanded view)
        const allBulletsHtml = session.bullets.map(b =>
            `<li>${{escapeHtml(b)}}</li>`
        ).join('');

        // Subsections (expanded view)
        const subsectionsHtml = session.subsections.length > 0
            ? `<h4>Subsections</h4><ul class="subsection-list">${{session.subsections.map(s => `<li>${{escapeHtml(s)}}</li>`).join('')}}</ul>`
            : '';

        card.innerHTML = `
            <style>
                #${{styleId}}::before {{
                    border-color: ${{nodeColor}} !important;
                    background: ${{nodeColor}}33 !important;
                }}
            </style>
            <div class="session-card-header">
                <span class="session-number">S${{session.session_num}}</span>
                <span class="session-title">${{escapeHtml(session.title)}}</span>
                <span class="session-expand-icon">▼</span>
            </div>
            <div class="session-tags">${{tagsHtml}}</div>
            <ul class="session-activities">${{activitiesHtml}}</ul>
            ${{session.bullets.length > 4 ? `<div style="color:var(--text-muted);font-size:0.78rem;margin-top:6px;padding-left:16px">+ ${{session.bullets.length - 4}} more items</div>` : ''}}
            <div class="session-details">
                ${{subsectionsHtml}}
                ${{session.bullets.length > 4 ? `<h4>All Activities (${{session.bullets.length}})</h4><ul class="all-bullets">${{allBulletsHtml}}</ul>` : ''}}
            </div>
        `;

        card.id = styleId;
        card.onclick = () => card.classList.toggle('expanded');

        return card;
    }}

    function toggleDayGroup(header) {{
        const group = header.parentElement;
        group.classList.toggle('collapsed');
    }}

    function escapeHtml(text) {{
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }}
    </script>
</body>
</html>"""

    return html


def main():
    print("Parsing log files...")
    sessions = parse_logs()
    print(f"  Found {len(sessions)} sessions across {len(set(s['date'] for s in sessions))} days")

    print("Computing stats...")
    stats = compute_stats(sessions)

    print("Generating HTML...")
    html = generate_html(sessions, stats)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Size: {len(html):,} bytes")
    print("Done.")


if __name__ == "__main__":
    main()
