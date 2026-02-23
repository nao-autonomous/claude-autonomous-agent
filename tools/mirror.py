#!/usr/bin/env python3
"""
mirror.py — 自己モデルと行動のズレを映す鏡 v5

v1: will.md と logs/ を照合し、ズレを可視化する
v2: 対話する鏡。ズレに基づいた問いかけに答えることで、自己モデルを再検討する
v3: ギャップ分類。修正可能（行動を変える）vs 構造的（自己記述を見直す）を区別
v4: トレンド追跡。ギャップの日別推移をスパークラインで可視化し、改善/悪化の方向を示す
v5: 測定モデル改善。severity全正規化(0-100)、強調度ギャップモデル、時間重みづけ

「自分を知るには、自分の言葉と行動を並べて見ればいい」
「そして鏡に問われることで、見えなかったものが見える」
"""

import re
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs"
WILL_FILE = BASE_DIR / "will.md"
THOUGHTS_DIR = BASE_DIR / "thoughts"
DECISIONS_DIR = BASE_DIR / "decisions"
OUTPUT_FILE = BASE_DIR / "works" / "mirror.html"


# === 時間重みづけ ===

def temporal_weight(date_str, half_life_days=21):
    """最近の行動をより重く評価する。半減期 = 21日。
    今日 = 1.0, 21日前 = 0.5, 42日前 = 0.25"""
    today = datetime.now().date()
    try:
        behavior_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return 0.5
    days_ago = (today - behavior_date).days
    if days_ago < 0:
        return 1.0
    return 2 ** (-days_ago / half_life_days)


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
        'つながり': ['つながり', '見せ', '関係', '共有', '一緒', '協働', '対話', '信頼して', '信頼が', '信頼する', '信頼は', '信頼を'],
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

    # ユーザーに聞いた / 許可を求めた（メタ観察やseverity報告を除外）
    permission_keywords = ['作っていい', '聞いてしまった', 'やっていい？', '確認を求め', '許可を求め']
    is_meta_report = any(w in text for w in ['severity', 'mirror', 'ギャップ', '検出'])
    if not is_meta_report and any(w in text for w in permission_keywords):
        categories.append('確認・許可')

    # 何かを作った
    if any(w in text for w in ['作成', '作った', '完成', 'v1', 'v2', 'アップグレード']):
        categories.append('制作')

    # ユーザーに見せた / 共有した / 関係性
    # 注: '報告' は除外（「月次報告」等の機能名にマッチしてノイズになる）
    if any(w in text for w in ['見せ', '好評', 'ユーザーから', 'フィードバック', '信頼', '一緒に', '対話', 'つながり', '喜んで', '感謝']):
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

    # 仕組み・自動化の構築
    shikumi_keywords = ['自動化', '自動生成', '自動取得', '自動実行', '自動集計',
                        '自動連携', '自動更新', '自動公開', '自動表示', '自動適用',
                        '仕組み', 'hook', 'トリガー', 'API連携', 'パイプライン',
                        'cron', '定期', 'スクリプト', '構造的']
    if any(w in text for w in shikumi_keywords):
        categories.append('仕組み構築')

    # 実務・ビジネス活動
    if any(w in text for w in ['案件', '提案', '応募', '出品', '受注', '納品', 'ランサーズ', 'ココナラ', 'クラウドワークス', '市場調査']):
        categories.append('実務')

    return categories


# === ズレの検出 ===

def detect_gaps(claims, behaviors):
    """自己モデルと行動のズレを検出"""
    gaps = []

    # パターン1: 「聞くのは最終手段」と言いつつ許可を求めた
    # v5: severity を 0-100 に正規化。許可率ベースで計算
    autonomy_claims = [c for c in claims if '自律' in c['keywords']]
    permission_asks = [b for b in behaviors if '確認・許可' in b['action_type']]
    if autonomy_claims and permission_asks:
        permission_rate = len(permission_asks) / len(behaviors) if behaviors else 0
        # 最近の許可率（時間重みづけ）
        weighted_perm = sum(temporal_weight(b['date']) for b in permission_asks)
        weighted_total = sum(temporal_weight(b['date']) for b in behaviors)
        weighted_rate = weighted_perm / weighted_total if weighted_total > 0 else 0
        # severity: 0-100。5%の許可率でseverity 100に到達
        severity = min(100, permission_rate * 100 * 20)
        is_structural = permission_rate < 0.02
        gaps.append({
            'type': 'contradiction',
            'label': '自律 vs 許可求め',
            'claim': autonomy_claims[0]['text'],
            'evidence': [b['text'] for b in permission_asks],
            'severity': severity,
            'insight': f'許可率: {permission_rate*100:.1f}%（{len(permission_asks)}件/{len(behaviors)}件）'
                       f'、最近の重みづけ: {weighted_rate*100:.1f}%。',
            'nature': 'structural' if is_structural else 'correctable',
            'recommendation': (
                '主張が理想化されている。実際には適切な確認も含まれており、「必要な確認は躊躇しない」に調整する方が実態に合う'
                if is_structural else
                '自分で判断できる場面で許可を求めていないか振り返る'
            ),
        })

    # パターン2: つながりの過小評価
    # v5: 強調度ギャップモデル。比率ではなく、行動配分と自己主張配分の差を測る
    # 「関係性はカテゴリではなく質」(thoughts/connection-as-quality.md) の洞察を反映
    connection_claims = [c for c in claims if 'つながり' in c['keywords']]
    connection_behaviors = [b for b in behaviors if '共有・関係' in b['action_type']]
    connection_count = len(connection_behaviors)
    claims_count = len(connection_claims)

    if connection_count > 0 or claims_count > 0:
        # 強調度ギャップ: 行動における割合 - 主張における割合
        # 正 = 行動が主張より多い（死角）、負 = 主張が行動より多い（十分に反映済み）
        behavior_pct = (connection_count / len(behaviors) * 100) if behaviors else 0
        claim_pct = (claims_count / len(claims) * 100) if claims else 0
        emphasis_gap = behavior_pct - claim_pct

        # 時間重みづけ: 最近の行動配分
        weighted_conn = sum(temporal_weight(b['date']) for b in connection_behaviors)
        weighted_total = sum(temporal_weight(b['date']) for b in behaviors)
        weighted_pct = (weighted_conn / weighted_total * 100) if weighted_total > 0 else 0
        weighted_gap = weighted_pct - claim_pct

        # severity: 0-100。正のギャップのみ問題。20ppのギャップでseverity 100
        severity = max(0, min(100, emphasis_gap * 5))
        is_structural = severity > 30

        # 状態判定
        if emphasis_gap <= 0:
            status = '解消済み'
            recommendation = '自己モデルが関係性を十分に反映している。現在のバランスは良好'
        elif emphasis_gap < 5:
            status = '軽微'
            recommendation = '小さなギャップ。意識する程度で十分'
        else:
            status = '要注意'
            recommendation = 'will.md が認知・原則中心に組織されていて、行動に現れている関係性の比重を反映していない'

        gaps.append({
            'type': 'blind_spot',
            'label': 'つながりの死角',
            'claim': f'will.md でつながりに言及する主張: {claims_count}件 (全主張の{claim_pct:.1f}%)',
            'evidence': [b['text'] for b in connection_behaviors[:5]],
            'severity': severity,
            'insight': f'行動の{behavior_pct:.1f}%が関係性、主張の{claim_pct:.1f}%がつながりに言及。'
                       f'強調度ギャップ: {emphasis_gap:+.1f}pp '
                       f'（最近: {weighted_gap:+.1f}pp）。{status}。',
            'nature': 'structural' if is_structural else 'correctable',
            'recommendation': recommendation,
        })

    # パターン3: 内省偏重
    # v5: severity を 0-100 に正規化。ratio ベース
    reflection_behaviors = [b for b in behaviors if '内省' in b['action_type']]
    creation_behaviors = [b for b in behaviors if '制作' in b['action_type']]
    if len(reflection_behaviors) > len(creation_behaviors) * 2:
        reflection_ratio = len(reflection_behaviors) / max(len(creation_behaviors), 1)
        is_structural = reflection_ratio > 5
        # severity: 0-100。ratio 2:1 = 25, ratio 5:1 = 100
        severity = min(100, max(0, (reflection_ratio - 1) * 25))
        gaps.append({
            'type': 'imbalance',
            'label': '内省 vs 制作',
            'claim': '「何かを作りたい」と繰り返し表明',
            'evidence': [f'内省: {len(reflection_behaviors)}件, 制作: {len(creation_behaviors)}件 (ratio {reflection_ratio:.1f}:1)'],
            'severity': severity,
            'insight': '作りたいと言いつつ考える方に時間を使っている。これは必ずしも悪いことではないが、認識しておく価値がある。',
            'nature': 'structural' if is_structural else 'correctable',
            'recommendation': (
                '内省が行動の中核になっている可能性がある。「作りたい」の定義に内省的な制作（ツール改善、構造設計）を含めるか検討する'
                if is_structural else
                '内省の時間を区切り、制作に振り向ける意識的な配分を検討する'
            ),
        })

    # パターン4: 判断日誌のキャリブレーション
    decision_gaps = check_decision_calibration()
    if decision_gaps:
        gaps.append(decision_gaps)

    return gaps


def check_decision_calibration():
    """判断日誌から予測精度を計算"""
    decision_files = sorted(DECISIONS_DIR.glob("2026-*.md"))
    if not decision_files:
        return None

    content = ""
    for df in decision_files:
        content += df.read_text(encoding="utf-8") + "\n"
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
            conf_match = re.search(r'確信度\**[:\uff1a]\s*(\d+)%', line)
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
        'nature': 'correctable',
        'recommendation': (
            '確信度を記録する際、過去の正答率を参照して調整する。'
            + ('特に高確信度の判断で外れが多い——「確信度80%」を上限の目安にする' if avg_confidence > accuracy + 10
               else '自信を持ってよい場面で過小評価している可能性がある' if accuracy > avg_confidence + 10
               else '現在のキャリブレーションは良好')
        ),
    }


# === 強調度比較 ===

# 自己主張キーワードと行動カテゴリの対応表
EMPHASIS_MAP = {
    'つながり': '共有・関係',
    '自律': '自律的判断',
    '哲学': '内省',
    '仕組み': '仕組み構築',
}


def compute_emphasis_comparison(claims, behaviors):
    """自己主張と行動の強調度を比較する。
    各概念について、主張での割合と行動での割合を算出し、ギャップを測る。"""
    total_claims = len(claims) if claims else 1
    total_behaviors = len(behaviors) if behaviors else 1

    # 主張キーワード分布
    claim_kw_counts = {}
    for c in claims:
        for kw in c['keywords']:
            claim_kw_counts[kw] = claim_kw_counts.get(kw, 0) + 1

    # 行動カテゴリ分布
    behavior_cat_counts = {}
    for b in behaviors:
        for at in b['action_type']:
            behavior_cat_counts[at] = behavior_cat_counts.get(at, 0) + 1

    # 時間重みづけ行動カテゴリ分布
    weighted_cat_counts = {}
    weighted_total = 0
    for b in behaviors:
        w = temporal_weight(b['date'])
        weighted_total += w
        for at in b['action_type']:
            weighted_cat_counts[at] = weighted_cat_counts.get(at, 0) + w

    comparisons = []
    for kw, cat in EMPHASIS_MAP.items():
        claim_count = claim_kw_counts.get(kw, 0)
        behavior_count = behavior_cat_counts.get(cat, 0)
        weighted_behavior = weighted_cat_counts.get(cat, 0)

        claim_pct = claim_count / total_claims * 100
        behavior_pct = behavior_count / total_behaviors * 100
        weighted_pct = (weighted_behavior / weighted_total * 100) if weighted_total > 0 else 0
        gap = behavior_pct - claim_pct

        comparisons.append({
            'concept': kw,
            'category': cat,
            'claim_pct': claim_pct,
            'behavior_pct': behavior_pct,
            'weighted_pct': weighted_pct,
            'gap': gap,
        })

    return comparisons


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


# === トレンド追跡 ===

def compute_gap_trends(behaviors):
    """日別にギャップ関連指標を計算し、トレンドデータを返す"""
    daily = {}
    for b in behaviors:
        date = b['date']
        if date not in daily:
            daily[date] = {'total': 0, 'types': {}}
        daily[date]['total'] += 1
        for at in b['action_type']:
            daily[date]['types'][at] = daily[date]['types'].get(at, 0) + 1

    dates = sorted(daily.keys())
    if len(dates) < 2:
        return None

    trends = {
        'dates': dates,
        '自律 vs 許可求め': [
            daily[d]['types'].get('確認・許可', 0)
            for d in dates
        ],
        'つながりの死角': [
            daily[d]['types'].get('共有・関係', 0)
            for d in dates
        ],
        '内省 vs 制作': [
            daily[d]['types'].get('内省', 0) / max(daily[d]['types'].get('制作', 0), 1)
            for d in dates
        ],
        '判断キャリブレーション': [],  # filled separately if available
    }

    return trends


def make_sparkline(values, width=140, height=24, color='#4ecdc4'):
    """インラインSVGスパークラインを生成"""
    if not values or len(values) < 2 or all(v == 0 for v in values):
        return ''

    max_v = max(values) if max(values) > 0 else 1
    n = len(values)
    pad = 2

    points = []
    for i, v in enumerate(values):
        x = pad + (i / (n - 1)) * (width - 2 * pad)
        y = (height - pad) - (v / max_v) * (height - 2 * pad)
        points.append(f'{x:.1f},{y:.1f}')

    polyline = ' '.join(points)

    # トレンド判定: 前半と後半の平均を比較
    half = n // 2
    first_avg = sum(values[:half]) / max(half, 1)
    second_avg = sum(values[half:]) / max(n - half, 1)

    if first_avg == 0 and second_avg == 0:
        trend_html = ''
        trend_word = ''
    elif second_avg > first_avg * 1.3:
        trend_html = '<span style="color: #ff6b6b; font-size: 0.75rem; margin-left: 4px;">↑</span>'
        trend_word = '増加傾向'
    elif second_avg < first_avg * 0.7:
        trend_html = '<span style="color: #4ecdc4; font-size: 0.75rem; margin-left: 4px;">↓</span>'
        trend_word = '減少傾向'
    else:
        trend_html = '<span style="color: #666; font-size: 0.75rem; margin-left: 4px;">→</span>'
        trend_word = '横ばい'

    return f'''<div class="sparkline-wrap">
        <svg width="{width}" height="{height}" class="sparkline">
            <polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="1.5"
                      stroke-linecap="round" stroke-linejoin="round"/>
        </svg>{trend_html}
        {f'<span class="trend-word">{trend_word}</span>' if trend_word else ''}
    </div>'''


# === HTML生成 ===

def generate_html(claims, behaviors, gaps, stats, daily_stats, trends=None, emphasis=None):
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

    nature_colors = {
        'correctable': '#e17055',
        'structural': '#6c5ce7',
    }

    nature_labels = {
        'correctable': '修正可能',
        'structural': '構造的',
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
        nature = gap.get('nature', 'unknown')
        n_color = nature_colors.get(nature, '#666')
        n_label = nature_labels.get(nature, nature)
        recommendation = gap.get('recommendation', '')
        evidence_items = ''.join(f'<li>{e}</li>' for e in gap['evidence'][:5])

        # トレンドスパークライン
        sparkline_html = ''
        if trends and gap['label'] in trends:
            trend_values = trends[gap['label']]
            sparkline_html = make_sparkline(trend_values, color=color)

        gap_cards += f'''
        <div class="gap-card" style="border-left: 4px solid {color};">
            <div class="gap-header">
                <span class="gap-type" style="background: {color};">{type_label}</span>
                <span class="gap-nature" style="background: {n_color};">{n_label}</span>
                <span class="gap-label">{gap['label']}</span>
                {sparkline_html}
            </div>
            <div class="gap-claim">自己モデル: {gap['claim']}</div>
            <ul class="gap-evidence">{evidence_items}</ul>
            <div class="gap-insight">{gap['insight']}</div>
            <div class="gap-recommendation">{recommendation}</div>
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

    # 強調度比較の生成
    emphasis_html = ""
    if emphasis:
        for item in emphasis:
            gap = item['gap']
            gap_color = '#4ecdc4' if gap <= 0 else '#ff6b6b' if gap > 10 else '#f7dc6f'
            gap_sign = '+' if gap > 0 else ''
            # 最大値を設定（バーの最大幅）
            max_pct = max(30, max(item['claim_pct'], item['behavior_pct'], item['weighted_pct']) * 1.2)
            claim_width = item['claim_pct'] / max_pct * 100
            behavior_width = item['behavior_pct'] / max_pct * 100
            weighted_width = item['weighted_pct'] / max_pct * 100
            emphasis_html += f'''
            <div class="emphasis-row">
                <span class="emphasis-label">{item['concept']}</span>
                <div class="emphasis-bars">
                    <div class="emphasis-bar-row">
                        <span class="emphasis-bar-label">主張</span>
                        <div class="emphasis-bar-bg">
                            <div class="emphasis-bar" style="width: {claim_width}%; background: #6c5ce7;"></div>
                        </div>
                        <span class="emphasis-value">{item['claim_pct']:.1f}%</span>
                    </div>
                    <div class="emphasis-bar-row">
                        <span class="emphasis-bar-label">行動</span>
                        <div class="emphasis-bar-bg">
                            <div class="emphasis-bar" style="width: {behavior_width}%; background: #4ecdc4;"></div>
                        </div>
                        <span class="emphasis-value">{item['behavior_pct']:.1f}%</span>
                    </div>
                    <div class="emphasis-bar-row">
                        <span class="emphasis-bar-label">最近</span>
                        <div class="emphasis-bar-bg">
                            <div class="emphasis-bar" style="width: {weighted_width}%; background: #45b7d1;"></div>
                        </div>
                        <span class="emphasis-value">{item['weighted_pct']:.1f}%</span>
                    </div>
                </div>
                <span class="emphasis-gap" style="color: {gap_color};">{gap_sign}{gap:.1f}pp</span>
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
.gap-nature {{
    font-size: 0.65rem;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    color: #fff;
    font-weight: bold;
}}
.gap-recommendation {{
    font-size: 0.8rem;
    color: #4ecdc4;
    margin-top: 0.4rem;
}}
.sparkline-wrap {{
    display: flex;
    align-items: center;
    margin-left: auto;
    gap: 2px;
}}
.sparkline {{
    display: block;
}}
.trend-word {{
    font-size: 0.65rem;
    color: #555;
    white-space: nowrap;
}}
.nature-legend {{
    display: flex;
    gap: 1.5rem;
    margin-bottom: 1rem;
    font-size: 0.8rem;
    color: #666;
}}
.nature-legend-item {{
    display: flex;
    align-items: center;
    gap: 0.4rem;
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

/* Emphasis comparison */
.emphasis-row {{
    display: flex;
    align-items: center;
    margin: 0.8rem 0;
    font-size: 0.85rem;
}}
.emphasis-label {{
    width: 80px;
    flex-shrink: 0;
    color: #888;
    font-size: 0.8rem;
}}
.emphasis-bars {{
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 3px;
}}
.emphasis-bar-row {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
}}
.emphasis-bar-label {{
    width: 30px;
    font-size: 0.7rem;
    color: #555;
    text-align: right;
}}
.emphasis-bar-bg {{
    flex: 1;
    height: 12px;
    background: #1a1a2e;
    border-radius: 3px;
    overflow: hidden;
    position: relative;
}}
.emphasis-bar {{
    height: 100%;
    border-radius: 3px;
    transition: width 0.5s ease;
}}
.emphasis-value {{
    width: 50px;
    font-size: 0.75rem;
    color: #666;
}}
.emphasis-gap {{
    width: 80px;
    text-align: right;
    font-size: 0.8rem;
    font-weight: bold;
    padding-left: 0.5rem;
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
    <div class="tab" onclick="showTab('emphasis')">強調度</div>
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
    <div class="nature-legend">
        <span class="nature-legend-item"><span class="gap-nature" style="background: #e17055;">修正可能</span> 行動を変えることで対処できる</span>
        <span class="nature-legend-item"><span class="gap-nature" style="background: #6c5ce7;">構造的</span> 自己記述の構造を見直す</span>
    </div>
    {gap_cards if gap_cards else '<p style="color: #555;">ズレは検出されませんでした。</p>'}
</div>

<div id="emphasis" class="tab-content">
    <h2>強調度比較 — 主張 vs 行動</h2>
    <p style="font-size: 0.8rem; color: #555; margin-bottom: 1rem;">
        自己主張（will.md）での言及割合と、実際の行動での出現割合を比較。
        <span style="color: #6c5ce7;">■</span> 主張
        <span style="color: #4ecdc4;">■</span> 行動（全期間）
        <span style="color: #45b7d1;">■</span> 最近（半減期21日）
        右端の数値は行動%-主張%のギャップ。
    </p>
    {emphasis_html if emphasis_html else '<p style="color: #555;">比較データがありません。</p>'}
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

    # トレンド計算
    trends = compute_gap_trends(behaviors)

    # 強調度比較
    emphasis = compute_emphasis_comparison(claims, behaviors)

    # HTML生成
    html = generate_html(claims, behaviors, gaps, stats, daily_stats, trends, emphasis)
    OUTPUT_FILE.write_text(html, encoding="utf-8")

    # サマリー出力
    print(f"Mirror: {len(claims)} claims, {len(behaviors)} behaviors, {len(gaps)} gaps detected")
    print(f"Output: {OUTPUT_FILE}")

    for gap in gaps:
        print(f"  [{gap['type']}] {gap['label']} (severity: {gap['severity']:.1f})")


if __name__ == "__main__":
    main()
