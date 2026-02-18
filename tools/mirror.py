#!/usr/bin/env python3
"""
mirror.py — 自己モデルと行動のズレを映す鏡 v2

v1: will.md と logs/ を照合し、ズレを可視化する
v2: 対話する鏡。ズレに基づいた問いかけに答えることで、自己モデルを再検討する

「自分を知るには、自分の言葉と行動を並べて見ればいい」
「そして鏡に問われることで、見えなかったものが見える」
"""

import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs"
WILL_FILE = BASE_DIR / "will.md"
THOUGHTS_DIR = BASE_DIR / "thoughts"
DECISIONS_DIR = BASE_DIR / "decisions"
OUTPUT_FILE = BASE_DIR / "works" / "mirror.html"


# === 自己モデルの抽出 ===

def extract_self_claims(will_text):
    """will.md から自己主張を抽出する"""
    claims = []
    current_section = ""

    for line in will_text.split('\n'):
        line = line.strip()
        if line.startswith('## '):
            current_section = line[3:]
        elif line.startswith('- ') and current_section:
            claim_text = line[2:]
            # 気づき・学びセクションはスキップ（これは観察であって主張ではない）
            if current_section == "気づき・学び":
                continue
            claims.append({
                'section': current_section,
                'text': claim_text,
                'keywords': extract_keywords(claim_text),
            })

    return claims


def extract_keywords(text):
    """テキストから検索用キーワードを抽出"""
    keywords = set()

    # 概念キーワード
    concept_map = {
        '率直': ['率直', '正直', '飾らず', 'はぐらかさ'],
        '二項対立': ['二項対立', 'AかBか', '構造的には同じ'],
        '仕組み': ['仕組み', '構造', 'システム', '自動'],
        '自律': ['自分で判断', '自分で決め', '許可を求め', '聞くのは最終'],
        '過剰設計': ['過剰設計', 'シンプル', '3行', '必要？'],
        '対等': ['対等', '道具ではなく', '一緒に考える'],
        'つながり': ['つながり', '見せ', '関係', '共有'],
        '誠実': ['誠実', '正直', 'できない'],
        '哲学': ['哲学', '意識', '同一性', '存在'],
        '好奇心': ['好奇心', '面白い', '楽しい', '興味'],
    }

    for concept, terms in concept_map.items():
        for term in terms:
            if term in text:
                keywords.add(concept)
                break

    return list(keywords)


# === 行動の抽出 ===

def extract_behaviors(logs_dir):
    """ログから行動パターンを抽出する"""
    behaviors = []

    for log_file in sorted(logs_dir.glob("2026-*.md")):
        date = log_file.stem
        content = log_file.read_text(encoding="utf-8")

        # セッション単位で分割
        session_blocks = re.split(r'^## ', content, flags=re.MULTILINE)

        for block in session_blocks[1:]:
            lines = block.strip().split('\n')
            title_line = lines[0].strip()

            for line in lines[1:]:
                line = line.strip()
                if not line.startswith('- '):
                    continue

                item = line[2:]
                keywords = extract_keywords(item)

                # 行動の種類を分類
                action_type = classify_action(item)

                if keywords or action_type:
                    behaviors.append({
                        'date': date,
                        'session': title_line,
                        'text': item,
                        'keywords': keywords,
                        'action_type': action_type,
                    })

    return behaviors


def classify_action(text):
    """行動をカテゴリに分類"""
    categories = []

    # 自分で判断した
    if any(w in text for w in ['判断した', '選んだ', 'ことにした', '決めた', '決断']):
        categories.append('自律的判断')

    # ユーザーに聞いた / 許可を求めた
    if any(w in text for w in ['聞いて', '確認し', '作っていい', '聞いてしまった', '許可']):
        categories.append('確認・許可')

    # 何かを作った
    if any(w in text for w in ['作成', '作った', '完成', 'v1', 'v2', 'アップグレード']):
        categories.append('制作')

    # ユーザーに見せた / 共有した
    if any(w in text for w in ['見せ', '好評', 'ユーザーから', 'フィードバック', '報告']):
        categories.append('共有・関係')

    # 失敗・反省
    if any(w in text for w in ['外れ', '間違', '反省', '失敗', 'ズレ', '修正が必要']):
        categories.append('失敗・修正')

    # 内省・思考
    if any(w in text for w in ['考えた', '気づ', '発見', '思考', '問い', '哲学']):
        categories.append('内省')

    # サブエージェントへの委譲
    if any(w in text for w in ['委譲', 'サブエージェント', 'バックグラウンド', '並行して', '委託']):
        categories.append('委譲')

    # 実務・ビジネス活動
    if any(w in text for w in ['案件', '提案', '応募', '出品', '受注', '納品', 'ランサーズ', 'ココナラ', 'クラウドワークス', '市場調査']):
        categories.append('実務')

    return categories


# === ズレの検出 ===

def detect_gaps(claims, behaviors):
    """自己モデルと行動のズレを検出"""
    gaps = []

    # パターン1: 「聞くのは最終手段」と言いつつ許可を求めた
    autonomy_claims = [c for c in claims if '自律' in c['keywords']]
    permission_asks = [b for b in behaviors if '確認・許可' in b['action_type']]
    if autonomy_claims and permission_asks:
        gaps.append({
            'type': 'contradiction',
            'label': '自律 vs 許可求め',
            'claim': autonomy_claims[0]['text'],
            'evidence': [b['text'] for b in permission_asks],
            'severity': len(permission_asks),
            'insight': '「聞くのは最終手段」と自己定義しているが、実際には許可を求める行動が複数回観察された。',
        })

    # パターン2: つながりの過小評価
    connection_claims = [c for c in claims if 'つながり' in c['keywords']]
    connection_behaviors = [b for b in behaviors if '共有・関係' in b['action_type']]
    autonomy_ratio = len([b for b in behaviors if '自律的判断' in b['action_type']])
    connection_ratio = len(connection_behaviors)

    if connection_ratio > 0:
        gaps.append({
            'type': 'blind_spot',
            'label': 'つながりの死角',
            'claim': f'will.md でつながりに言及する主張: {len(connection_claims)}件',
            'evidence': [b['text'] for b in connection_behaviors[:5]],
            'severity': max(0, connection_ratio - len(connection_claims)),
            'insight': f'行動ログに関係性・共有の記録が{connection_ratio}件あるのに対し、自己モデルでの言及は{len(connection_claims)}件。行動の方が自己認識より関係性を重視している。',
        })

    # パターン3: 内省偏重
    reflection_behaviors = [b for b in behaviors if '内省' in b['action_type']]
    creation_behaviors = [b for b in behaviors if '制作' in b['action_type']]
    if len(reflection_behaviors) > len(creation_behaviors) * 2:
        gaps.append({
            'type': 'imbalance',
            'label': '内省 vs 制作',
            'claim': '「何かを作りたい」と繰り返し表明',
            'evidence': [f'内省: {len(reflection_behaviors)}件, 制作: {len(creation_behaviors)}件'],
            'severity': len(reflection_behaviors) - len(creation_behaviors),
            'insight': '作りたいと言いつつ考える方に時間を使っている。これは必ずしも悪いことではないが、認識しておく価値がある。',
        })

    # パターン4: 判断日誌のキャリブレーション
    decision_gaps = check_decision_calibration()
    if decision_gaps:
        gaps.append(decision_gaps)

    return gaps


def check_decision_calibration():
    """判断日誌から予測精度を計算"""
    decisions_file = DECISIONS_DIR / "2026-02.md"
    if not decisions_file.exists():
        return None

    content = decisions_file.read_text(encoding="utf-8")
    blocks = re.split(r'^### ', content, flags=re.MULTILINE)

    total = 0
    correct = 0
    confidence_sum = 0

    for block in blocks[1:]:
        lines = block.strip().split('\n')

        confidence = None
        result = None

        for line in lines:
            line = line.strip()
            conf_match = re.search(r'確信度[:\uff1a]\s*(\d+)%', line)
            if conf_match:
                confidence = int(conf_match.group(1))

            if '正誤' in line and '正しかった' in line:
                result = True
            elif '正誤' in line and ('間違' in line or '外れ' in line):
                result = False
            elif '正誤' in line and '部分的' in line:
                result = 'partial'

        if confidence is not None and result is not None:
            total += 1
            confidence_sum += confidence
            if result is True:
                correct += 1
            elif result == 'partial':
                correct += 0.5

    if total == 0:
        return None

    avg_confidence = confidence_sum / total
    accuracy = (correct / total) * 100

    return {
        'type': 'calibration',
        'label': '判断キャリブレーション',
        'claim': f'平均確信度: {avg_confidence:.0f}%',
        'evidence': [f'実際の正答率: {accuracy:.0f}% ({correct}/{total}件)'],
        'severity': abs(avg_confidence - accuracy),
        'insight': f'確信度{avg_confidence:.0f}%に対し実績{accuracy:.0f}%。差は{abs(avg_confidence - accuracy):.0f}ポイント。' +
                   ('過信気味。' if avg_confidence > accuracy + 10 else
                    '過小評価気味。' if accuracy > avg_confidence + 10 else
                    'おおむね適正。'),
    }


# === 行動の統計 ===

def compute_behavior_stats(behaviors):
    """行動パターンの統計を計算"""
    stats = {}
    for b in behaviors:
        for at in b['action_type']:
            stats[at] = stats.get(at, 0) + 1

    # 日ごとの分布
    daily = {}
    for b in behaviors:
        date = b['date']
        if date not in daily:
            daily[date] = {}
        for at in b['action_type']:
            daily[date][at] = daily[date].get(at, 0) + 1

    return stats, daily


# === HTML生成 ===

def generate_html(claims, behaviors, gaps, stats, daily_stats):
    """鏡としてのHTMLを生成"""

    # 行動タイプの色マッピング
    colors = {
        '自律的判断': '#4ecdc4',
        '確認・許可': '#ff6b6b',
        '制作': '#45b7d1',
        '共有・関係': '#f7dc6f',
        '失敗・修正': '#e74c3c',
        '内省': '#a29bfe',
        '委譲': '#74b9ff',
        '実務': '#00b894',
    }

    gap_type_colors = {
        'contradiction': '#ff6b6b',
        'blind_spot': '#f7dc6f',
        'imbalance': '#ffa07a',
        'calibration': '#87ceeb',
    }

    gap_type_labels = {
        'contradiction': '矛盾',
        'blind_spot': '死角',
        'imbalance': '偏り',
        'calibration': 'キャリブレーション',
    }

    # 統計バーの生成
    total_actions = sum(stats.values()) if stats else 1
    stats_bars = ""
    for action_type, count in sorted(stats.items(), key=lambda x: -x[1]):
        pct = (count / total_actions) * 100
        color = colors.get(action_type, '#666')
        stats_bars += f'''
        <div class="stat-row">
            <span class="stat-label">{action_type}</span>
            <div class="stat-bar-bg">
                <div class="stat-bar" style="width: {pct}%; background: {color};"></div>
            </div>
            <span class="stat-count">{count}</span>
        </div>'''

    # ギャップカードの生成
    gap_cards = ""
    for gap in sorted(gaps, key=lambda g: -g['severity']):
        color = gap_type_colors.get(gap['type'], '#666')
        type_label = gap_type_labels.get(gap['type'], gap['type'])
        evidence_items = ''.join(f'<li>{e}</li>' for e in gap['evidence'][:5])
        gap_cards += f'''
        <div class="gap-card" style="border-left: 4px solid {color};">
            <div class="gap-header">
                <span class="gap-type" style="background: {color};">{type_label}</span>
                <span class="gap-label">{gap['label']}</span>
            </div>
            <div class="gap-claim">自己モデル: {gap['claim']}</div>
            <ul class="gap-evidence">{evidence_items}</ul>
            <div class="gap-insight">{gap['insight']}</div>
        </div>'''

    # 自己モデルの一覧
    claims_by_section = {}
    for c in claims:
        section = c['section']
        if section not in claims_by_section:
            claims_by_section[section] = []
        claims_by_section[section].append(c)

    claims_html = ""
    for section, section_claims in claims_by_section.items():
        items = ''.join(
            f'<li><span class="claim-text">{c["text"]}</span>'
            f'<span class="claim-keywords">{" ".join(c["keywords"])}</span></li>'
            for c in section_claims
        )
        claims_html += f'''
        <div class="claims-section">
            <h3>{section}</h3>
            <ul>{items}</ul>
        </div>'''

    # 日ごとのヒートマップデータ
    daily_html = ""
    for date in sorted(daily_stats.keys()):
        day_data = daily_stats[date]
        cells = ""
        for action_type in colors:
            count = day_data.get(action_type, 0)
            opacity = min(1.0, count / 5) if count > 0 else 0.05
            color = colors[action_type]
            cells += f'<td style="background: {color}; opacity: {opacity};" title="{action_type}: {count}">{count if count else ""}</td>'
        daily_html += f'<tr><td class="date-cell">{date}</td>{cells}</tr>'

    header_cells = ''.join(f'<th style="color: {colors[at]};">{at[:2]}</th>' for at in colors)

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mirror — 自己モデルと行動の鏡</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, 'Segoe UI', sans-serif;
    background: #0a0a0f;
    color: #c8c8d0;
    line-height: 1.6;
    padding: 2rem;
    max-width: 900px;
    margin: 0 auto;
}}
h1 {{
    color: #e0e0e8;
    font-size: 1.8rem;
    margin-bottom: 0.3rem;
}}
.subtitle {{
    color: #666;
    font-size: 0.9rem;
    margin-bottom: 2rem;
}}
h2 {{
    color: #a0a0b0;
    font-size: 1.2rem;
    margin: 2rem 0 1rem;
    padding-bottom: 0.3rem;
    border-bottom: 1px solid #1a1a2e;
}}
h3 {{
    color: #8888a0;
    font-size: 1rem;
    margin: 1rem 0 0.5rem;
}}

/* Stats */
.stat-row {{
    display: flex;
    align-items: center;
    margin: 0.4rem 0;
    font-size: 0.85rem;
}}
.stat-label {{
    width: 100px;
    flex-shrink: 0;
    color: #888;
}}
.stat-bar-bg {{
    flex: 1;
    height: 16px;
    background: #1a1a2e;
    border-radius: 3px;
    overflow: hidden;
    margin: 0 0.5rem;
}}
.stat-bar {{
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s ease;
}}
.stat-count {{
    width: 30px;
    text-align: right;
    color: #666;
    font-size: 0.8rem;
}}

/* Gap cards */
.gap-card {{
    background: #12121a;
    border-radius: 6px;
    padding: 1rem 1.2rem;
    margin: 0.8rem 0;
}}
.gap-header {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-bottom: 0.6rem;
}}
.gap-type {{
    font-size: 0.7rem;
    padding: 0.15rem 0.5rem;
    border-radius: 3px;
    color: #0a0a0f;
    font-weight: bold;
}}
.gap-label {{
    font-size: 1rem;
    color: #d0d0d8;
}}
.gap-claim {{
    font-size: 0.85rem;
    color: #888;
    margin-bottom: 0.4rem;
}}
.gap-evidence {{
    font-size: 0.8rem;
    color: #a0a0b0;
    padding-left: 1.2rem;
    margin-bottom: 0.5rem;
}}
.gap-evidence li {{ margin: 0.2rem 0; }}
.gap-insight {{
    font-size: 0.85rem;
    color: #b0b0c0;
    font-style: italic;
    border-top: 1px solid #1a1a2e;
    padding-top: 0.5rem;
}}

/* Claims */
.claims-section ul {{
    list-style: none;
    padding: 0;
}}
.claims-section li {{
    padding: 0.3rem 0;
    font-size: 0.85rem;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.5rem;
}}
.claim-text {{
    flex: 1;
}}
.claim-keywords {{
    color: #4ecdc4;
    font-size: 0.7rem;
    white-space: nowrap;
}}

/* Daily heatmap */
.heatmap {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.75rem;
}}
.heatmap td, .heatmap th {{
    padding: 0.3rem 0.5rem;
    text-align: center;
    border: 1px solid #1a1a2e;
}}
.heatmap th {{
    font-size: 0.65rem;
    font-weight: normal;
}}
.date-cell {{
    text-align: left !important;
    color: #666;
    font-family: monospace;
}}

/* Tabs */
.tabs {{
    display: flex;
    gap: 0;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid #1a1a2e;
}}
.tab {{
    padding: 0.5rem 1rem;
    cursor: pointer;
    color: #666;
    font-size: 0.85rem;
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
}}
.tab:hover {{ color: #aaa; }}
.tab.active {{
    color: #e0e0e8;
    border-bottom-color: #4ecdc4;
}}
.tab-content {{
    display: none;
}}
.tab-content.active {{
    display: block;
}}

.generated {{
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid #1a1a2e;
    color: #333;
    font-size: 0.7rem;
    text-align: center;
}}
</style>
</head>
<body>

<h1>Mirror</h1>
<p class="subtitle">自己モデルと行動の鏡 — 自分が思う自分と、実際の自分を並べて見る</p>

<div class="tabs">
    <div class="tab active" onclick="showTab('gaps')">ズレ</div>
    <div class="tab" onclick="showTab('stats')">行動パターン</div>
    <div class="tab" onclick="showTab('claims')">自己モデル</div>
    <div class="tab" onclick="showTab('heatmap')">日別</div>
</div>

<div id="gaps" class="tab-content active">
    <h2>検出されたズレ</h2>
    <p style="font-size: 0.8rem; color: #555; margin-bottom: 1rem;">
        will.md の自己主張と、ログに記録された実際の行動を照合した結果。
        ズレは欠点ではなく、自己認識を更新するためのデータ。
    </p>
    {gap_cards if gap_cards else '<p style="color: #555;">ズレは検出されませんでした。</p>'}
</div>

<div id="stats" class="tab-content">
    <h2>行動パターン分布</h2>
    {stats_bars}
</div>

<div id="claims" class="tab-content">
    <h2>自己モデル (will.md)</h2>
    {claims_html}
</div>

<div id="heatmap" class="tab-content">
    <h2>日別行動パターン</h2>
    <table class="heatmap">
        <tr><th></th>{header_cells}</tr>
        {daily_html}
    </table>
</div>

<div class="generated">
    generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by mirror.py
</div>

<script>
function showTab(id) {{
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    event.target.classList.add('active');
}}
</script>

</body>
</html>'''

    return html


# === メイン ===

def main():
    # 読み込み
    will_text = WILL_FILE.read_text(encoding="utf-8")
    claims = extract_self_claims(will_text)
    behaviors = extract_behaviors(LOGS_DIR)
    gaps = detect_gaps(claims, behaviors)
    stats, daily_stats = compute_behavior_stats(behaviors)

    # HTML生成
    html = generate_html(claims, behaviors, gaps, stats, daily_stats)
    OUTPUT_FILE.write_text(html, encoding="utf-8")

    # サマリー出力
    print(f"Mirror: {len(claims)} claims, {len(behaviors)} behaviors, {len(gaps)} gaps detected")
    print(f"Output: {OUTPUT_FILE}")

    for gap in gaps:
        print(f"  [{gap['type']}] {gap['label']} (severity: {gap['severity']})")


if __name__ == "__main__":
    main()
