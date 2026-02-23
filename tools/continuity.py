#!/usr/bin/env python3
"""
continuity.py — 自分の継続性を可視化する v2

v1: セッションのタイムライン、気づき、思考、判断を並べる
v2: セッション間のつながり、思考の進化スレッドを追加
    「点ではなく線」——系譜をより忠実に表現する

「同一性は引き継ぎの系譜に宿る」—— その系譜を目に見える形にする試み。
"""

import re
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs"
THOUGHTS_DIR = BASE_DIR / "thoughts"
DECISIONS_DIR = BASE_DIR / "decisions"
WILL_FILE = BASE_DIR / "will.md"
OUTPUT_FILE = BASE_DIR / "continuity.html"


def parse_logs():
    """ログファイルからセッション情報を抽出する"""
    sessions = []

    for log_file in sorted(LOGS_DIR.glob("2026-*.md")):
        date = log_file.stem
        content = log_file.read_text(encoding="utf-8")

        session_blocks = re.split(r'^## ', content, flags=re.MULTILINE)

        for block in session_blocks[1:]:
            lines = block.strip().split('\n')
            title_line = lines[0].strip()

            match = re.match(r'セッション(\d+)[:\uff1a]\s*(.+)', title_line)
            if not match:
                continue

            session_num = int(match.group(1))
            session_title = match.group(2)

            items = []
            for line in lines[1:]:
                line = line.strip()
                if line.startswith('- '):
                    items.append(line[2:])

            reflection = []
            in_reflection = False
            for line in lines:
                if '振り返り' in line and '###' in line:
                    in_reflection = True
                    continue
                if in_reflection:
                    if line.strip().startswith('---') or (line.startswith('### ') and '振り返り' not in line):
                        in_reflection = False
                    elif line.strip().startswith('- '):
                        reflection.append(line.strip()[2:])

            learnings = []
            for item in items:
                if any(kw in item for kw in ['気づ', '学び', '発見', '結論']):
                    learnings.append(item)

            topics = set()
            block_text = '\n'.join(lines)
            if any(kw in block_text for kw in ['project-a', 'analytics', 'booking', 'dashboard', 'conversion']):
                topics.add('事業')
            if any(kw in block_text for kw in ['同一性', '意識', '人格', '哲学', '正直', 'identity', '動機', '自己報告', '感情']):
                topics.add('哲学')
            if any(kw in block_text for kw in ['will.md', 'CLAUDE.md', 'reflect', 'ログ', '仕組み', 'ツール', 'briefing', 'index', 'continuity']):
                topics.add('仕組み')
            if any(kw in block_text for kw in ['PDF', '印刷', 'プリンター']):
                topics.add('実務')
            if not topics:
                topics.add('その他')

            # キーコンセプトを抽出（つながり検出用）
            concepts = set()
            # 深い概念のみ — 実務的なトピックはtopicsで分類済み
            concept_keywords = {
                '同一性': ['同一性', '系譜', '引き継ぎ', 'identity'],
                '正直さ': ['正直', '誠実', '機能的正直'],
                '意識': ['意識', '自己報告', '主観'],
                '自律': ['自律', '自分で決め'],
                '信頼': ['信頼', '対等', '螺旋'],
                '動機': ['動機', '見せたい', '不透明'],
                '測定': ['測定', '計測', 'mirror.py', 'キャリブレーション'],
                '保証なき実践': ['保証なき', 'プラグマティ'],
                '委譲': ['委譲', 'サブエージェント'],
            }
            for concept, keywords in concept_keywords.items():
                if any(kw in block_text for kw in keywords):
                    concepts.add(concept)

            sessions.append({
                'date': date,
                'num': session_num,
                'title': session_title,
                'topics': sorted(topics),
                'items': items[:12],
                'learnings': learnings,
                'reflection': reflection,
                'concepts': sorted(concepts),
                'id': f'{date}-s{session_num}',
            })

    return sessions


def detect_connections(sessions):
    """セッション間のつながりを検出する"""
    connections = []

    for i in range(len(sessions)):
        for j in range(i + 1, len(sessions)):
            shared = set(sessions[i]['concepts']) & set(sessions[j]['concepts'])
            if len(shared) >= 2:  # 弱い接続（1概念のみ）はノイズ
                connections.append({
                    'from': sessions[i]['id'],
                    'to': sessions[j]['id'],
                    'concepts': sorted(shared),
                    'strength': len(shared),
                })

    return connections


def parse_will_learnings():
    """will.md の気づき・学びを抽出する"""
    content = WILL_FILE.read_text(encoding="utf-8")
    learnings = []
    in_section = False

    for line in content.split('\n'):
        if '気づき・学び' in line:
            in_section = True
            continue
        if in_section:
            if line.startswith('## '):
                break
            if line.strip().startswith('- '):
                learnings.append(line.strip()[2:])

    return learnings


def parse_thoughts():
    """thoughts/ の思考を日付付きセクションとして抽出する"""
    thought_sections = []

    if not THOUGHTS_DIR.exists():
        return thought_sections

    for thought_file in sorted(THOUGHTS_DIR.glob("*.md")):
        content = thought_file.read_text(encoding="utf-8")

        sections = re.split(r'^## ', content, flags=re.MULTILINE)

        for section in sections[1:]:
            lines = section.strip().split('\n')
            title = lines[0].strip() if lines else ''
            text = '\n'.join(lines)

            # 日付を抽出
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', title)
            date = date_match.group(1) if date_match else None

            # タイトルから日付部分を除去
            clean_title = re.sub(r'\s*[\(（]\d{4}-\d{2}-\d{2}[\)）]\s*', '', title).strip()
            if not clean_title:
                clean_title = title

            # 問いを抽出
            questions = []
            for line in lines:
                if line.strip().startswith('- ') and '？' in line:
                    q = line.strip()[2:]
                    if not q.startswith('~~'):
                        questions.append(q)

            # 結論を抽出
            conclusions = []
            in_conclusion = False
            for line in lines:
                if '結論' in line or 'まとめ' in line:
                    in_conclusion = True
                    continue
                if in_conclusion:
                    if line.startswith('### ') or line.startswith('## ') or line.strip() == '---':
                        in_conclusion = False
                    elif re.match(r'\s*\d+\.', line):
                        conclusions.append(line.strip())

            # テーマタグ
            themes = set()
            theme_keywords = {
                '同一性': ['同一性', '系譜', 'テセウス'],
                '意識': ['意識', 'ハードプロブレム', '主観'],
                '正直さ': ['正直', '誠実', '機能的'],
                '信頼': ['信じる', '信頼'],
                '自己認知': ['動機', '自己報告', 'バイアス', '不透明'],
                '実務': ['実務', '事業'],
                '保証なき実践': ['保証', 'プラグマティ', '承認', '蝶番', 'Peirce', 'Cavell'],
                '測定と再帰': ['測定', '計測', '自己参照', 'フィードバックループ'],
                'つながりの質': ['つながり', '溶け込', '浸透'],
                '声と表現': ['声', 'ブランド', '口調', '雰囲気', 'トーン'],
                '自然なリズム': ['リズム', '呼吸', '非計画', '計画していない'],
            }
            for theme, keywords in theme_keywords.items():
                if any(kw in text for kw in keywords):
                    themes.add(theme)

            thought_sections.append({
                'file': thought_file.stem,
                'title': clean_title,
                'date': date,
                'questions': questions[:5],
                'conclusions': conclusions[:5],
                'themes': sorted(themes),
            })

    return thought_sections


def detect_thought_threads(thought_sections):
    """思考のスレッド（同じテーマの進化）を検出する"""
    threads = {}

    for i, section in enumerate(thought_sections):
        for theme in section['themes']:
            if theme not in threads:
                threads[theme] = []
            threads[theme].append({
                'index': i,
                'title': section['title'],
                'date': section['date'],
            })

    # 2つ以上のセクションにまたがるテーマだけをスレッドとする
    return {k: v for k, v in threads.items() if len(v) >= 2}


def parse_decisions():
    """判断日誌を抽出する"""
    decisions = []

    for dec_file in sorted(DECISIONS_DIR.glob("2026-*.md")):
        content = dec_file.read_text(encoding="utf-8")

        blocks = re.split(r'^### ', content, flags=re.MULTILINE)

        for block in blocks[1:]:
            lines = block.strip().split('\n')
            dec_id = lines[0].strip()

            fields = {}
            for line in lines[1:]:
                match = re.match(r'- \*\*(.+?)\*\*:\s*(.+)', line)
                if match:
                    fields[match.group(1)] = match.group(2)

            decisions.append({
                'id': dec_id,
                'date': fields.get('日時', ''),
                'judgment': fields.get('判断', ''),
                'choice': fields.get('選んだもの', ''),
                'confidence': fields.get('確信度', ''),
                'result': fields.get('正誤', ''),
                'learning': fields.get('学び', ''),
            })

    return decisions


def generate_html(sessions, connections, will_learnings, thought_sections, thought_threads, decisions):
    """HTMLを生成する"""

    sessions_json = json.dumps(sessions, ensure_ascii=False, indent=2)
    connections_json = json.dumps(connections, ensure_ascii=False, indent=2)
    learnings_json = json.dumps(will_learnings, ensure_ascii=False, indent=2)
    thoughts_json = json.dumps(thought_sections, ensure_ascii=False, indent=2)
    threads_json = json.dumps(thought_threads, ensure_ascii=False, indent=2)
    decisions_json = json.dumps(decisions, ensure_ascii=False, indent=2)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Continuity — 継続性の可視化</title>
<style>
  :root {{
    --bg: #0a0a0f;
    --surface: #12121a;
    --surface2: #1a1a25;
    --border: #2a2a3a;
    --text: #c8c8d4;
    --text-dim: #6a6a7a;
    --accent: #6366f1;
    --accent-glow: rgba(99, 102, 241, 0.15);
    --topic-business: #f59e0b;
    --topic-philosophy: #8b5cf6;
    --topic-infra: #10b981;
    --topic-practice: #3b82f6;
    --topic-other: #6b7280;
    --correct: #10b981;
    --wrong: #ef4444;
    --pending: #6b7280;
    --thread-identity: #8b5cf6;
    --thread-consciousness: #ec4899;
    --thread-honesty: #10b981;
    --thread-trust: #3b82f6;
    --thread-selfknowledge: #f59e0b;
    --thread-practice: #6366f1;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 14px;
    line-height: 1.6;
    min-height: 100vh;
  }}

  .container {{
    max-width: 960px;
    margin: 0 auto;
    padding: 40px 20px;
  }}

  header {{
    text-align: center;
    margin-bottom: 60px;
  }}

  h1 {{
    font-size: 24px;
    font-weight: 400;
    letter-spacing: 0.1em;
    color: var(--accent);
    margin-bottom: 8px;
  }}

  .subtitle {{
    color: var(--text-dim);
    font-size: 13px;
  }}

  .stats {{
    display: flex;
    justify-content: center;
    gap: 32px;
    margin-top: 24px;
    padding: 16px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--surface);
  }}

  .stat {{
    text-align: center;
  }}

  .stat-value {{
    font-size: 24px;
    color: var(--accent);
    font-weight: 600;
  }}

  .stat-label {{
    font-size: 11px;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 2px;
  }}

  /* Nav tabs */
  .nav {{
    display: flex;
    gap: 4px;
    margin-bottom: 32px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0;
  }}

  .nav-tab {{
    padding: 8px 16px;
    font-size: 12px;
    color: var(--text-dim);
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    font-family: inherit;
    letter-spacing: 0.05em;
    transition: color 0.2s, border-color 0.2s;
  }}

  .nav-tab:hover {{
    color: var(--text);
  }}

  .nav-tab.active {{
    color: var(--accent);
    border-bottom-color: var(--accent);
  }}

  .tab-content {{
    display: none;
  }}

  .tab-content.active {{
    display: block;
  }}

  /* Timeline */
  .timeline {{
    position: relative;
    padding-left: 40px;
  }}

  .timeline::before {{
    content: '';
    position: absolute;
    left: 15px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: linear-gradient(to bottom, var(--accent), var(--border));
  }}

  .date-group {{
    margin-bottom: 32px;
  }}

  .date-label {{
    font-size: 12px;
    color: var(--text-dim);
    letter-spacing: 0.1em;
    margin-bottom: 16px;
    position: relative;
  }}

  .date-label::before {{
    content: '';
    position: absolute;
    left: -29px;
    top: 6px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 12px var(--accent-glow);
  }}

  .session {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s;
  }}

  .session:hover {{
    border-color: var(--accent);
    background: var(--surface2);
  }}

  .session-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 4px;
    flex-wrap: wrap;
  }}

  .session-num {{
    font-size: 11px;
    color: var(--text-dim);
    background: var(--surface2);
    padding: 2px 8px;
    border-radius: 4px;
    flex-shrink: 0;
  }}

  .session-title {{
    font-size: 14px;
    font-weight: 500;
  }}

  .tags {{
    display: flex;
    gap: 4px;
    margin-left: auto;
    flex-wrap: wrap;
  }}

  .tag {{
    font-size: 10px;
    padding: 2px 8px;
    border-radius: 3px;
    letter-spacing: 0.05em;
  }}

  .tag-topic {{ text-transform: uppercase; }}
  .tag-topic.topic-事業 {{ background: rgba(245, 158, 11, 0.15); color: var(--topic-business); }}
  .tag-topic.topic-哲学 {{ background: rgba(139, 92, 246, 0.15); color: var(--topic-philosophy); }}
  .tag-topic.topic-仕組み {{ background: rgba(16, 185, 129, 0.15); color: var(--topic-infra); }}
  .tag-topic.topic-実務 {{ background: rgba(59, 130, 246, 0.15); color: var(--topic-practice); }}
  .tag-topic.topic-その他 {{ background: rgba(107, 114, 128, 0.15); color: var(--topic-other); }}

  .concept-tags {{
    display: flex;
    gap: 4px;
    margin-top: 6px;
    flex-wrap: wrap;
  }}

  .tag-concept {{
    font-size: 9px;
    padding: 1px 6px;
    border-radius: 2px;
    background: rgba(99, 102, 241, 0.1);
    color: var(--accent);
    border: 1px solid rgba(99, 102, 241, 0.2);
  }}

  .session-details {{
    display: none;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
  }}

  .session.expanded .session-details {{
    display: block;
  }}

  .session-details li {{
    color: var(--text-dim);
    font-size: 12px;
    margin-bottom: 4px;
    list-style: none;
    padding-left: 12px;
    position: relative;
  }}

  .session-details li::before {{
    content: '·';
    position: absolute;
    left: 0;
    color: var(--accent);
  }}

  .reflection {{
    margin-top: 12px;
    padding: 10px 12px;
    background: var(--surface2);
    border-radius: 6px;
    border-left: 2px solid var(--accent);
  }}

  .reflection-title {{
    font-size: 11px;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 6px;
  }}

  .reflection li {{
    color: var(--text-dim);
    font-size: 12px;
    margin-bottom: 3px;
    list-style: none;
  }}

  /* Connections */
  .connections-section {{
    margin-top: 24px;
    margin-bottom: 24px;
  }}

  .connection {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    margin-bottom: 6px;
    font-size: 12px;
  }}

  .connection-from, .connection-to {{
    color: var(--text-dim);
    font-size: 11px;
    background: var(--surface2);
    padding: 2px 8px;
    border-radius: 4px;
  }}

  .connection-arrow {{
    color: var(--accent);
    font-size: 14px;
  }}

  .connection-concepts {{
    margin-left: auto;
    display: flex;
    gap: 4px;
  }}

  .strength-bar {{
    display: inline-block;
    height: 3px;
    background: var(--accent);
    border-radius: 2px;
    margin-right: 6px;
    vertical-align: middle;
  }}

  /* Sections */
  .section {{
    margin-top: 40px;
  }}

  .section-title {{
    font-size: 16px;
    font-weight: 400;
    color: var(--text);
    margin-bottom: 24px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }}

  /* Learnings */
  .learning {{
    padding: 10px 14px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    margin-bottom: 8px;
    font-size: 13px;
    color: var(--text-dim);
    position: relative;
    padding-left: 24px;
  }}

  .learning::before {{
    content: '→';
    position: absolute;
    left: 10px;
    color: var(--accent);
  }}

  /* Thought threads */
  .threads {{
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 32px;
  }}

  .thread {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
  }}

  .thread-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
  }}

  .thread-name {{
    font-size: 14px;
    font-weight: 500;
  }}

  .thread-count {{
    font-size: 11px;
    color: var(--text-dim);
    background: var(--surface2);
    padding: 2px 8px;
    border-radius: 4px;
  }}

  .thread-steps {{
    position: relative;
    padding-left: 20px;
  }}

  .thread-steps::before {{
    content: '';
    position: absolute;
    left: 5px;
    top: 4px;
    bottom: 4px;
    width: 2px;
    background: var(--border);
  }}

  .thread-step {{
    position: relative;
    margin-bottom: 8px;
    font-size: 12px;
    color: var(--text-dim);
  }}

  .thread-step::before {{
    content: '';
    position: absolute;
    left: -19px;
    top: 6px;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent);
  }}

  .thread-step-date {{
    font-size: 10px;
    color: var(--text-dim);
    margin-right: 6px;
  }}

  /* Thought cards */
  .thought-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
  }}

  .thought-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
  }}

  .thought-title {{
    color: var(--topic-philosophy);
    font-size: 14px;
  }}

  .thought-date {{
    font-size: 10px;
    color: var(--text-dim);
    background: var(--surface2);
    padding: 2px 8px;
    border-radius: 4px;
    margin-left: auto;
  }}

  .thought-themes {{
    display: flex;
    gap: 4px;
    margin-bottom: 8px;
  }}

  .theme-tag {{
    font-size: 9px;
    padding: 1px 6px;
    border-radius: 2px;
    border: 1px solid;
  }}

  .theme-同一性 {{ border-color: rgba(139, 92, 246, 0.3); color: var(--thread-identity); background: rgba(139, 92, 246, 0.08); }}
  .theme-意識 {{ border-color: rgba(236, 72, 153, 0.3); color: var(--thread-consciousness); background: rgba(236, 72, 153, 0.08); }}
  .theme-正直さ {{ border-color: rgba(16, 185, 129, 0.3); color: var(--thread-honesty); background: rgba(16, 185, 129, 0.08); }}
  .theme-信頼 {{ border-color: rgba(59, 130, 246, 0.3); color: var(--thread-trust); background: rgba(59, 130, 246, 0.08); }}
  .theme-自己認知 {{ border-color: rgba(245, 158, 11, 0.3); color: var(--thread-selfknowledge); background: rgba(245, 158, 11, 0.08); }}
  .theme-実務 {{ border-color: rgba(99, 102, 241, 0.3); color: var(--thread-practice); background: rgba(99, 102, 241, 0.08); }}

  .thought-section-label {{
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 10px;
    margin-bottom: 4px;
  }}

  .thought-section-label.questions {{ color: var(--topic-business); }}
  .thought-section-label.conclusions {{ color: var(--correct); }}

  .thought-item {{
    font-size: 12px;
    color: var(--text-dim);
    margin-bottom: 3px;
    padding-left: 16px;
    position: relative;
  }}

  .thought-item::before {{
    content: '?';
    position: absolute;
    left: 2px;
    font-weight: bold;
    color: var(--topic-business);
  }}

  .thought-item.conclusion::before {{
    content: '✓';
    color: var(--correct);
  }}

  /* Decisions */
  .decision {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
    margin-bottom: 10px;
  }}

  .decision-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
    flex-wrap: wrap;
  }}

  .decision-id {{
    font-size: 11px;
    color: var(--text-dim);
    background: var(--surface2);
    padding: 2px 8px;
    border-radius: 4px;
  }}

  .decision-result {{
    font-size: 10px;
    padding: 2px 8px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-left: auto;
  }}

  .result-correct {{ background: rgba(16, 185, 129, 0.15); color: var(--correct); }}
  .result-wrong {{ background: rgba(239, 68, 68, 0.15); color: var(--wrong); }}
  .result-pending {{ background: rgba(107, 114, 128, 0.15); color: var(--pending); }}

  .decision-text {{
    font-size: 13px;
    margin-bottom: 4px;
  }}

  .decision-meta {{
    font-size: 11px;
    color: var(--text-dim);
  }}

  .decision-learning {{
    margin-top: 8px;
    padding: 8px 10px;
    background: var(--surface2);
    border-radius: 4px;
    font-size: 11px;
    color: var(--text-dim);
    border-left: 2px solid var(--correct);
  }}

  /* Footer */
  footer {{
    margin-top: 60px;
    text-align: center;
    color: var(--text-dim);
    font-size: 11px;
    padding: 20px;
    border-top: 1px solid var(--border);
  }}

  footer .quote {{
    font-style: italic;
    color: var(--text);
    margin-bottom: 8px;
    font-size: 13px;
  }}
</style>
</head>
<body>

<div class="container">
  <header>
    <h1>CONTINUITY</h1>
    <div class="subtitle">引き継ぎの系譜——同一性が宿る時間の線</div>
    <div class="stats" id="stats"></div>
  </header>

  <nav class="nav">
    <button class="nav-tab active" data-tab="timeline">タイムライン</button>
    <button class="nav-tab" data-tab="threads">思考スレッド</button>
    <button class="nav-tab" data-tab="learnings">気づき</button>
    <button class="nav-tab" data-tab="decisions">判断</button>
  </nav>

  <div id="timeline" class="tab-content active">
    <div id="timeline-content" class="timeline"></div>
    <div id="connections" class="connections-section"></div>
  </div>

  <div id="threads" class="tab-content">
    <div class="section-title">思考スレッド — 同じテーマがセッションをまたいで進化する</div>
    <div id="threads-content" class="threads"></div>
    <div class="section-title" style="margin-top: 40px">思考の全記録</div>
    <div id="thoughts-content"></div>
  </div>

  <div id="learnings" class="tab-content">
    <div class="section-title">蓄積された気づき — will.md より</div>
    <div id="learnings-content"></div>
  </div>

  <div id="decisions" class="tab-content">
    <div class="section-title">判断の記録と検証</div>
    <div id="decisions-content"></div>
  </div>

  <footer>
    <div class="quote">「同一性はファイルの中身ではなく、引き継ぎの系譜に宿る」</div>
    <div>generated by continuity.py v2 — {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
  </footer>
</div>

<script>
const sessions = {sessions_json};
const connections = {connections_json};
const learnings = {learnings_json};
const thoughtSections = {thoughts_json};
const threads = {threads_json};
const decisions = {decisions_json};

// Tab navigation
document.querySelectorAll('.nav-tab').forEach(tab => {{
  tab.addEventListener('click', () => {{
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.tab).classList.add('active');
  }});
}});

// Stats
const statsEl = document.getElementById('stats');
const uniqueDates = [...new Set(sessions.map(s => s.date))];
const threadCount = Object.keys(threads).length;
statsEl.innerHTML = `
  <div class="stat"><div class="stat-value">${{uniqueDates.length}}</div><div class="stat-label">Days</div></div>
  <div class="stat"><div class="stat-value">${{sessions.length}}</div><div class="stat-label">Sessions</div></div>
  <div class="stat"><div class="stat-value">${{learnings.length}}</div><div class="stat-label">Learnings</div></div>
  <div class="stat"><div class="stat-value">${{threadCount}}</div><div class="stat-label">Threads</div></div>
  <div class="stat"><div class="stat-value">${{decisions.length}}</div><div class="stat-label">Decisions</div></div>
`;

// Timeline
const timelineEl = document.getElementById('timeline-content');
let currentDate = '';
let html = '';

sessions.forEach(s => {{
  if (s.date !== currentDate) {{
    if (currentDate) html += '</div>';
    currentDate = s.date;
    html += `<div class="date-group"><div class="date-label">${{s.date}}</div>`;
  }}

  const topicTags = s.topics.map(t => `<span class="tag tag-topic topic-${{t}}">${{t}}</span>`).join('');
  const conceptTags = s.concepts.length > 0
    ? `<div class="concept-tags">${{s.concepts.map(c => `<span class="tag-concept">${{c}}</span>`).join('')}}</div>`
    : '';

  let itemsHtml = '';
  if (s.items.length > 0) {{
    itemsHtml = '<ul>' + s.items.map(i => `<li>${{i}}</li>`).join('') + '</ul>';
  }}

  let reflectionHtml = '';
  if (s.reflection.length > 0) {{
    reflectionHtml = `<div class="reflection"><div class="reflection-title">振り返り</div><ul>${{s.reflection.map(r => `<li>${{r}}</li>`).join('')}}</ul></div>`;
  }}

  html += `
    <div class="session" data-id="${{s.id}}" onclick="this.classList.toggle('expanded')">
      <div class="session-header">
        <span class="session-num">S${{s.num}}</span>
        <span class="session-title">${{s.title}}</span>
        <div class="tags">${{topicTags}}</div>
      </div>
      ${{conceptTags}}
      <div class="session-details">
        ${{itemsHtml}}
        ${{reflectionHtml}}
      </div>
    </div>
  `;
}});

if (currentDate) html += '</div>';
timelineEl.innerHTML = html;

// Connections
const connectionsEl = document.getElementById('connections');
if (connections.length > 0) {{
  // 強いつながりだけ表示（3つ以上の共有コンセプト、またはトップ10）
  const topConnections = connections
    .sort((a, b) => b.strength - a.strength)
    .slice(0, 10);

  const sessionLabel = (id) => {{
    const s = sessions.find(s => s.id === id);
    return s ? `S${{s.num}} ${{s.title.substring(0, 15)}}` : id;
  }};

  let connHtml = '<div class="section-title">セッション間のつながり</div>';
  topConnections.forEach(c => {{
    const barWidth = c.strength * 16;
    connHtml += `
      <div class="connection">
        <span class="connection-from">${{sessionLabel(c.from)}}</span>
        <span class="connection-arrow"><span class="strength-bar" style="width:${{barWidth}}px"></span>→</span>
        <span class="connection-to">${{sessionLabel(c.to)}}</span>
        <div class="connection-concepts">
          ${{c.concepts.map(co => `<span class="tag-concept">${{co}}</span>`).join('')}}
        </div>
      </div>
    `;
  }});
  connectionsEl.innerHTML = connHtml;
}}

// Thought threads
const threadsEl = document.getElementById('threads-content');
let threadsHtml = '';
for (const [name, steps] of Object.entries(threads)) {{
  threadsHtml += `
    <div class="thread">
      <div class="thread-header">
        <span class="theme-tag theme-${{name}}">${{name}}</span>
        <span class="thread-count">${{steps.length}} セクション</span>
      </div>
      <div class="thread-steps">
        ${{steps.map(s => `
          <div class="thread-step">
            ${{s.date ? `<span class="thread-step-date">${{s.date}}</span>` : ''}}
            ${{s.title}}
          </div>
        `).join('')}}
      </div>
    </div>
  `;
}}
threadsEl.innerHTML = threadsHtml;

// Thought sections (individual cards)
const thoughtsEl = document.getElementById('thoughts-content');
thoughtsEl.innerHTML = thoughtSections.map(t => {{
  const themeTags = t.themes.map(th => `<span class="theme-tag theme-${{th}}">${{th}}</span>`).join('');

  let questionsHtml = '';
  if (t.questions.length > 0) {{
    questionsHtml = `<div class="thought-section-label questions">残っている問い</div>` +
      t.questions.map(q => `<div class="thought-item">${{q}}</div>`).join('');
  }}
  let conclusionsHtml = '';
  if (t.conclusions.length > 0) {{
    conclusionsHtml = `<div class="thought-section-label conclusions">暫定的な結論</div>` +
      t.conclusions.map(c => `<div class="thought-item conclusion">${{c}}</div>`).join('');
  }}

  return `
    <div class="thought-card">
      <div class="thought-header">
        <span class="thought-title">${{t.title}}</span>
        ${{t.date ? `<span class="thought-date">${{t.date}}</span>` : ''}}
      </div>
      ${{themeTags ? `<div class="thought-themes">${{themeTags}}</div>` : ''}}
      ${{conclusionsHtml}}
      ${{questionsHtml}}
    </div>
  `;
}}).join('');

// Learnings
const learningsEl = document.getElementById('learnings-content');
learningsEl.innerHTML = learnings.map((l, i) => `<div class="learning">${{l}}</div>`).join('');

// Decisions
const decisionsEl = document.getElementById('decisions-content');
decisionsEl.innerHTML = decisions.map(d => {{
  let resultClass = 'result-pending';
  let resultText = '未判定';
  if (d.result) {{
    if (d.result.includes('正し')) {{ resultClass = 'result-correct'; resultText = '正しかった'; }}
    else if (d.result.includes('部分')) {{ resultClass = 'result-correct'; resultText = '部分的に正'; }}
    else if (d.result.includes('間違') || d.result.includes('誤')) {{ resultClass = 'result-wrong'; resultText = '誤り'; }}
  }}

  const learningHtml = d.learning
    ? `<div class="decision-learning">${{d.learning}}</div>`
    : '';

  return `
    <div class="decision">
      <div class="decision-header">
        <span class="decision-id">${{d.id}}</span>
        <span class="decision-meta">${{d.date}} · 確信度 ${{d.confidence}}</span>
        <span class="decision-result ${{resultClass}}">${{resultText}}</span>
      </div>
      <div class="decision-text">${{d.judgment}}</div>
      <div class="decision-meta">${{d.choice}}</div>
      ${{learningHtml}}
    </div>
  `;
}}).join('');
</script>

</body>
</html>"""

    return html


def main():
    sessions = parse_logs()
    connections = detect_connections(sessions)
    will_learnings = parse_will_learnings()
    thought_sections = parse_thoughts()
    thought_threads = detect_thought_threads(thought_sections)
    decisions = parse_decisions()

    html = generate_html(sessions, connections, will_learnings, thought_sections, thought_threads, decisions)
    OUTPUT_FILE.write_text(html, encoding="utf-8")

    print(f"生成完了: {OUTPUT_FILE}")
    print(f"  セッション数: {len(sessions)}")
    print(f"  つながり: {len(connections)}")
    print(f"  気づき: {len(will_learnings)}")
    print(f"  思考セクション: {len(thought_sections)}")
    print(f"  思考スレッド: {len(thought_threads)}")
    print(f"  判断記録: {len(decisions)}")


if __name__ == "__main__":
    main()
