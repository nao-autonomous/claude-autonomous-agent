#!/usr/bin/env python3
"""
判断日誌キャリブレーション分析ツール

decisions/ 配下の月別ファイルをパースし、確信度と実際の正答率を比較する。
自分の判断精度の傾向（過信/過小評価）を可視化する。

使い方:
  python3 tools/calibration.py          # テキストレポート
  python3 tools/calibration.py --html   # HTML可視化を生成
"""

import argparse
import re
from pathlib import Path
from datetime import datetime

DECISIONS_DIR = Path(__file__).resolve().parent.parent / "decisions"
OUTPUT_MD = DECISIONS_DIR / "calibration.md"


def parse_decision(block: str) -> dict | None:
    """個別の判断エントリをパースする。"""
    entry = {}

    id_match = re.search(r"###\s+(D-\d{8}-\d+)", block)
    if not id_match:
        return None
    entry["id"] = id_match.group(1)

    patterns = {
        "date": r"\*\*日時\*\*:\s*(.+)",
        "decision": r"\*\*判断\*\*:\s*(.+)",
        "chosen": r"\*\*選んだもの\*\*:\s*(.+)",
        "confidence": r"\*\*確信度\*\*:\s*(\d+)%",
        "rationale": r"\*\*根拠\*\*:\s*(.+)",
        "outcome": r"\*\*結果\*\*:\s*(.+)",
        "correctness": r"\*\*正誤\*\*:\s*(.+)",
        "learning": r"\*\*学び\*\*:\s*(.+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, block)
        if match:
            entry[key] = match.group(1).strip()

    if "confidence" in entry:
        entry["confidence"] = int(entry["confidence"])

    return entry


def parse_all_decisions() -> list[dict]:
    """全ての判断記録をパースする。"""
    entries = []
    for filepath in sorted(DECISIONS_DIR.glob("????-??.md")):
        text = filepath.read_text(encoding="utf-8")
        # ### D- で始まるブロックを分割
        blocks = re.split(r"(?=###\s+D-)", text)
        for block in blocks:
            if block.strip():
                entry = parse_decision(block)
                if entry:
                    entries.append(entry)
    return entries


def classify_correctness(text: str) -> str | None:
    """正誤テキストを分類する。"""
    if not text:
        return None
    lower = text.lower()
    if "正しかった" in text and "部分" not in text:
        return "correct"
    if "部分" in text:
        return "partial"
    if "間違" in text:
        return "incorrect"
    if "判定できない" in text or "運用" in text:
        return None
    return None


def classify_decision_type(entry: dict) -> str:
    """判断のカテゴリを自動分類する。"""
    text = entry.get("decision", "")

    # 案件選定（応募/見送り判断）
    if any(w in text for w in ['案件', '応募する', '見送', '受注', '出品', '応じる']):
        return '案件選定'

    # タイムアロケーション（何をやるかの判断）
    if any(w in text for w in ['何に時間', '何をやる', 'やりたいこと', '時間を使う',
                                 'やっていい', '即着手', '後回し', 'どれを選ぶ',
                                 '圧縮後に何を']):
        return 'タイムアロケーション'

    # 技術判断
    if any(w in text for w in ['実装', 'API', 'CLI', 'フィルタ', 'JSON',
                                 'スプレッドシート', 'ランキング', '対処', 'hook',
                                 '方針', '不要化']):
        return '技術判断'

    # 関係性・コミュニケーション
    if any(w in text for w in ['公開', 'レビュー', '読んでもらう', '共有']):
        return '関係性'

    # 言行一致
    if any(w in text for w in ['宣言', '停止', '言った後']):
        return '言行一致'

    return 'その他'


def compute_calibration(entries: list[dict]) -> dict:
    """キャリブレーション統計を計算する。"""
    # 確信度バンド: 50-60, 60-70, 70-80, 80-90, 90-100
    bands = {}
    for entry in entries:
        conf = entry.get("confidence")
        correctness = classify_correctness(entry.get("correctness", ""))
        if conf is None or correctness is None:
            continue

        # バンドを決定
        band = min((conf // 10) * 10, 90)
        if band < 50:
            band = 50

        if band not in bands:
            bands[band] = {"total": 0, "correct": 0, "partial": 0, "incorrect": 0}

        bands[band]["total"] += 1
        if correctness == "correct":
            bands[band]["correct"] += 1
        elif correctness == "partial":
            bands[band]["partial"] += 1
        elif correctness == "incorrect":
            bands[band]["incorrect"] += 1

    return bands


def compute_accuracy(band_data: dict) -> float:
    """バンドの実効正答率を計算する（部分正解は0.5として計上）。"""
    total = band_data["total"]
    if total == 0:
        return 0.0
    score = band_data["correct"] + band_data["partial"] * 0.5
    return score / total * 100


def generate_report(entries: list[dict], bands: dict) -> str:
    """テキストレポートを生成する。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# キャリブレーション分析",
        f"",
        f"自動生成: {now}",
        f"",
        f"## サマリー",
        f"",
        f"- 総判断数: {len(entries)}",
    ]

    # 判定済みのエントリ数
    judged = [e for e in entries if classify_correctness(e.get("correctness", "")) is not None]
    pending = [e for e in entries if classify_correctness(e.get("correctness", "")) is None]
    lines.append(f"- 判定済み: {len(judged)}")
    lines.append(f"- 未判定: {len(pending)}")
    lines.append("")

    # キャリブレーションテーブル
    lines.append("## キャリブレーション")
    lines.append("")
    lines.append("| 確信度帯 | 件数 | 正解 | 部分正解 | 不正解 | 実効正答率 | ズレ |")
    lines.append("|----------|------|------|----------|--------|------------|------|")

    sorted_bands = sorted(bands.keys())
    total_gap = 0.0
    total_judged = 0
    for band in sorted_bands:
        data = bands[band]
        accuracy = compute_accuracy(data)
        band_center = band + 5
        gap = accuracy - band_center
        gap_str = f"+{gap:.0f}%" if gap >= 0 else f"{gap:.0f}%"
        lines.append(
            f"| {band}-{band+10}% | {data['total']} | {data['correct']} | "
            f"{data['partial']} | {data['incorrect']} | {accuracy:.0f}% | {gap_str} |"
        )
        total_gap += abs(gap) * data["total"]
        total_judged += data["total"]

    lines.append("")

    # 全体傾向
    if total_judged > 0:
        avg_gap = total_gap / total_judged
        lines.append(f"**平均絶対ズレ**: {avg_gap:.1f}pp")
        lines.append("")

        # 傾向判定
        overconfident = sum(
            1 for b in sorted_bands
            if compute_accuracy(bands[b]) < b + 5 and bands[b]["total"] > 0
        )
        underconfident = sum(
            1 for b in sorted_bands
            if compute_accuracy(bands[b]) > b + 5 and bands[b]["total"] > 0
        )
        if overconfident > underconfident:
            lines.append("**傾向**: 過信気味（確信度 > 実際の正答率）")
        elif underconfident > overconfident:
            lines.append("**傾向**: 過小評価気味（確信度 < 実際の正答率）")
        else:
            lines.append("**傾向**: バランス良好")
    else:
        lines.append("*判定済みデータが不足しています。判断の結果が分かったら正誤を記入してください。*")

    lines.append("")

    # カテゴリ別分析
    lines.append("## カテゴリ別分析")
    lines.append("")
    category_stats = {}
    for entry in entries:
        cat = classify_decision_type(entry)
        correctness = classify_correctness(entry.get("correctness", ""))
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "correct": 0, "partial": 0, "incorrect": 0, "pending": 0}
        category_stats[cat]["total"] += 1
        if correctness == "correct":
            category_stats[cat]["correct"] += 1
        elif correctness == "partial":
            category_stats[cat]["partial"] += 1
        elif correctness == "incorrect":
            category_stats[cat]["incorrect"] += 1
        else:
            category_stats[cat]["pending"] += 1

    lines.append("| カテゴリ | 件数 | 正解 | 部分 | 不正解 | 未判定 | 正答率 |")
    lines.append("|----------|------|------|------|--------|--------|--------|")
    for cat in sorted(category_stats.keys(), key=lambda c: -category_stats[c]["total"]):
        s = category_stats[cat]
        judged_count = s["correct"] + s["partial"] + s["incorrect"]
        if judged_count > 0:
            acc = (s["correct"] + s["partial"] * 0.5) / judged_count * 100
            acc_str = f"{acc:.0f}%"
        else:
            acc_str = "-"
        lines.append(
            f"| {cat} | {s['total']} | {s['correct']} | {s['partial']} | "
            f"{s['incorrect']} | {s['pending']} | {acc_str} |"
        )
    lines.append("")

    # 個別判断一覧
    lines.append("## 判断一覧")
    lines.append("")
    lines.append("| ID | 日付 | カテゴリ | 判断 | 確信度 | 正誤 |")
    lines.append("|----|------|----------|------|--------|------|")
    for entry in entries:
        eid = entry.get("id", "?")
        date = entry.get("date", "?")
        decision = entry.get("decision", "?")
        if len(decision) > 40:
            decision = decision[:37] + "..."
        conf = entry.get("confidence", "?")
        correctness = entry.get("correctness", "未判定")
        cat = classify_decision_type(entry)
        lines.append(f"| {eid} | {date} | {cat} | {decision} | {conf}% | {correctness} |")

    lines.append("")

    # 未判定のリマインダー
    if pending:
        lines.append("## 未判定の判断")
        lines.append("")
        for entry in pending:
            lines.append(f"- **{entry['id']}**: {entry.get('decision', '?')}")
        lines.append("")
        lines.append("*結果が分かったら `decisions/YYYY-MM.md` の正誤・学びフィールドを更新してください。*")

    lines.append("")
    return "\n".join(lines)


def generate_html(entries: list[dict], bands: dict) -> str:
    """キャリブレーションチャートのHTML可視化を生成する。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    sorted_bands = sorted(bands.keys())

    # 統計
    judged = [e for e in entries if classify_correctness(e.get('correctness', '')) is not None]
    pending = [e for e in entries if classify_correctness(e.get('correctness', '')) is None]

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>判断キャリブレーション</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    padding: 2rem;
    max-width: 900px;
    margin: 0 auto;
  }}
  h1 {{ color: #e94560; margin-bottom: 0.5rem; }}
  .meta {{ color: #888; margin-bottom: 2rem; font-size: 0.9rem; }}
  .chart-container {{
    background: #16213e;
    border-radius: 12px;
    padding: 2rem;
    margin-bottom: 2rem;
  }}
  .chart-title {{ color: #e94560; margin-bottom: 1rem; font-size: 1.2rem; }}
  svg {{ width: 100%; height: auto; }}
  .bar {{ transition: opacity 0.2s; cursor: pointer; }}
  .bar:hover {{ opacity: 0.8; }}
  .stats {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }}
  .stat-card {{
    background: #16213e;
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
  }}
  .stat-value {{ font-size: 2rem; font-weight: bold; color: #e94560; }}
  .stat-label {{ color: #888; margin-top: 0.3rem; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    background: #16213e;
    border-radius: 12px;
    overflow: hidden;
  }}
  th {{ background: #0f3460; padding: 0.8rem; text-align: left; }}
  td {{ padding: 0.8rem; border-top: 1px solid #233; }}
  td.correctness-cell {{ max-width: 220px; }}
  .correctness-short {{ cursor: help; }}
  .correct {{ color: #4ecca3; }}
  .partial {{ color: #f9a825; }}
  .incorrect {{ color: #e94560; }}
  .pending {{ color: #666; }}
  .conf-bar-bg {{
    display: inline-block;
    width: 60px;
    height: 8px;
    background: #0f3460;
    border-radius: 4px;
    vertical-align: middle;
    margin-left: 6px;
  }}
  .conf-bar-fill {{
    display: block;
    height: 100%;
    border-radius: 4px;
    background: #e94560;
  }}
  .insight-section {{
    background: #16213e;
    border-radius: 12px;
    padding: 1.5rem 2rem;
    margin-bottom: 2rem;
  }}
  .insight-section h2 {{
    color: #e94560;
    font-size: 1.2rem;
    margin-bottom: 1rem;
  }}
  .insight-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1rem;
  }}
  .insight-item {{
    background: #1a1a2e;
    border-radius: 8px;
    padding: 1rem 1.2rem;
  }}
  .insight-item .label {{
    color: #888;
    font-size: 0.85rem;
    margin-bottom: 0.3rem;
  }}
  .insight-item .value {{
    font-size: 1.1rem;
    font-weight: bold;
  }}
  .insight-item .detail {{
    color: #888;
    font-size: 0.85rem;
    margin-top: 0.3rem;
  }}
  .warning {{ color: #f9a825; }}
  .danger {{ color: #e94560; }}
  .safe {{ color: #4ecca3; }}
  .timeline-dot {{ cursor: pointer; }}
  .timeline-dot:hover {{ opacity: 0.7; }}
  .note {{ background: #16213e; border-radius: 12px; padding: 1.5rem; margin-top: 2rem; color: #888; }}
</style>
</head>
<body>
<h1>判断キャリブレーション</h1>
<p class="meta">生成: {now} / 総判断数: {len(entries)}</p>

<div class="stats">
  <div class="stat-card">
    <div class="stat-value">{len(entries)}</div>
    <div class="stat-label">総判断数</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{len(judged)}</div>
    <div class="stat-label">判定済み</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{len(pending)}</div>
    <div class="stat-label">未判定</div>
  </div>
</div>

<div class="chart-container">
  <div class="chart-title">キャリブレーションチャート</div>
  <p style="color: #888; margin-bottom: 1rem; font-size: 0.85rem;">
    灰色の対角線 = 完全キャリブレーション（確信度 = 正答率）。
    バーが対角線より下なら過信、上なら過小評価。X軸は確信度の連続スケール（50%-100%）。
  </p>
  {_generate_calibration_svg(sorted_bands, bands)}
</div>

{_generate_timeline_svg(entries)}

{_generate_insights(sorted_bands, bands, entries)}

{_generate_category_chart(entries)}

<div class="chart-container">
  <div class="chart-title">判断一覧</div>
  <table>
    <thead>
      <tr><th>ID</th><th>日付</th><th>カテゴリ</th><th>判断</th><th>確信度</th><th>正誤</th></tr>
    </thead>
    <tbody>
      {''.join(_entry_row(e) for e in entries)}
    </tbody>
  </table>
</div>

<div class="note">
  <strong>キャリブレーションとは:</strong>
  確信度80%の判断を10回したとき、実際に8回正解なら完全にキャリブレートされている。
  正解が6回なら過信、9回なら過小評価。データが増えるほど傾向が明確になる。
</div>

</body>
</html>"""


def _generate_calibration_svg(sorted_bands: list, bands: dict) -> str:
    """連続スケールX軸のキャリブレーションチャートSVGを生成する。

    チャート領域:
    - X軸: 50%~100%（確信度）
    - Y軸: 0%~100%（正答率）
    - 対角線: (50%,50%) -> (100%,100%) すなわち y=x
    """
    if not sorted_bands:
        return ('<svg viewBox="0 0 500 320" xmlns="http://www.w3.org/2000/svg">'
                '<rect x="60" y="10" width="420" height="260" fill="#0f3460" rx="4"/>'
                '<text x="270" y="140" text-anchor="middle" fill="#888" font-size="14">データなし</text>'
                '</svg>')

    # チャート領域の座標系
    chart_left = 60
    chart_right = 480
    chart_top = 10
    chart_bottom = 270
    chart_w = chart_right - chart_left  # 420
    chart_h = chart_bottom - chart_top  # 260

    # X軸: 50~100 の確信度スケール
    x_min, x_max = 50, 100
    # Y軸: 0~100 の正答率スケール
    y_min, y_max = 0, 100

    def x_pos(confidence: float) -> float:
        """確信度値をSVG X座標に変換"""
        return chart_left + (confidence - x_min) / (x_max - x_min) * chart_w

    def y_pos(accuracy_pct: float) -> float:
        """正答率をSVG Y座標に変換"""
        return chart_bottom - (accuracy_pct - y_min) / (y_max - y_min) * chart_h

    parts = []
    parts.append(f'<svg viewBox="0 0 500 320" xmlns="http://www.w3.org/2000/svg">')

    # 背景
    parts.append(f'<rect x="{chart_left}" y="{chart_top}" width="{chart_w}" height="{chart_h}" fill="#0f3460" rx="4"/>')

    # 水平グリッド線 (0%, 20%, 40%, 60%, 80%, 100%)
    for i in range(6):
        pct = i * 20
        yy = y_pos(pct)
        parts.append(f'<line x1="{chart_left}" y1="{yy}" x2="{chart_right}" y2="{yy}" stroke="#1a1a2e" stroke-width="1"/>')
        parts.append(f'<text x="{chart_left - 5}" y="{yy + 4}" text-anchor="end" fill="#888" font-size="11">{pct}%</text>')

    # 垂直グリッド線 (50%, 60%, 70%, 80%, 90%, 100%)
    for conf in range(50, 101, 10):
        xx = x_pos(conf)
        parts.append(f'<line x1="{xx}" y1="{chart_top}" x2="{xx}" y2="{chart_bottom}" stroke="#1a1a2e" stroke-width="1"/>')
        parts.append(f'<text x="{xx}" y="{chart_bottom + 15}" text-anchor="middle" fill="#888" font-size="10">{conf}%</text>')

    # 対角線 y=x: (50%, 50%) -> (100%, 100%)
    diag_x1 = x_pos(50)
    diag_y1 = y_pos(50)
    diag_x2 = x_pos(100)
    diag_y2 = y_pos(100)
    parts.append(f'<line x1="{diag_x1}" y1="{diag_y1}" x2="{diag_x2}" y2="{diag_y2}" stroke="#444" stroke-width="2" stroke-dasharray="6,4"/>')

    # データバー（固定幅、各帯の中心値にバーを配置）
    bar_width = 30
    for band in sorted_bands:
        center = band + 5  # 帯の中心値
        accuracy = compute_accuracy(bands[band])
        count = bands[band]["total"]

        cx = x_pos(center)
        bx = cx - bar_width / 2
        bar_h = (accuracy / (y_max - y_min)) * chart_h
        by = chart_bottom - bar_h

        # バーの色
        color = "#4ecca3" if accuracy >= center else "#e94560"

        parts.append(
            f'<rect class="bar" x="{bx:.1f}" y="{by:.1f}" width="{bar_width}" height="{bar_h:.1f}" '
            f'fill="{color}" rx="3" opacity="0.85">'
            f'<title>{band}-{band+10}%: 正答率{accuracy:.0f}%, {count}件</title></rect>'
        )
        # バーの上に数値
        label_y = max(by - 5, chart_top + 10)
        parts.append(
            f'<text x="{cx:.1f}" y="{label_y:.1f}" text-anchor="middle" '
            f'fill="#e0e0e0" font-size="10">{accuracy:.0f}% (n={count})</text>'
        )

    # 軸ラベル
    parts.append(f'<text x="{(chart_left + chart_right) / 2}" y="305" text-anchor="middle" fill="#888" font-size="12">確信度</text>')
    parts.append(f'<text x="15" y="{(chart_top + chart_bottom) / 2}" text-anchor="middle" fill="#888" font-size="12" transform="rotate(-90, 15, {(chart_top + chart_bottom) / 2})">実効正答率</text>')

    parts.append('</svg>')
    return "\n  ".join(parts)


def _generate_bars(sorted_bands: list, bands: dict) -> str:
    """後方互換性のため残す。_generate_calibration_svg に移行済み。"""
    return ""


def _generate_timeline_svg(entries: list[dict]) -> str:
    """判断タイムラインチャートのHTMLを生成する。"""
    # 確信度を持つエントリのみ（N/Aを除外）
    tl_entries = [e for e in entries if isinstance(e.get("confidence"), int)]
    if not tl_entries:
        return ""

    # 日付でソート
    def parse_date(e):
        d = e.get("date", "")
        try:
            return datetime.strptime(d, "%Y-%m-%d")
        except (ValueError, TypeError):
            return datetime.min
    tl_entries = sorted(tl_entries, key=parse_date)

    chart_left = 60
    chart_right = 480
    chart_top = 10
    chart_bottom = 200
    chart_w = chart_right - chart_left
    chart_h = chart_bottom - chart_top

    y_min_conf = 50
    y_max_conf = 100

    def y_pos(conf: int) -> float:
        clamped = max(y_min_conf, min(y_max_conf, conf))
        return chart_bottom - (clamped - y_min_conf) / (y_max_conf - y_min_conf) * chart_h

    # X位置を均等割り当て（日付が同じものもあるため）
    n = len(tl_entries)
    def x_pos(i: int) -> float:
        if n == 1:
            return (chart_left + chart_right) / 2
        return chart_left + i / (n - 1) * chart_w

    color_map = {
        "correct": "#4ecca3",
        "partial": "#f9a825",
        "incorrect": "#e94560",
    }

    parts = []
    parts.append('<div class="chart-container">')
    parts.append('  <div class="chart-title">判断タイムライン</div>')
    parts.append('  <p style="color: #888; margin-bottom: 1rem; font-size: 0.85rem;">')
    parts.append('    各判断の確信度を時系列で表示。')
    parts.append('    <span style="color:#4ecca3;">&#9679;</span>正解 ')
    parts.append('    <span style="color:#f9a825;">&#9679;</span>部分正解 ')
    parts.append('    <span style="color:#e94560;">&#9679;</span>不正解 ')
    parts.append('    <span style="color:#666;">&#9679;</span>未判定')
    parts.append('  </p>')
    parts.append(f'  <svg viewBox="0 0 500 240" xmlns="http://www.w3.org/2000/svg">')

    # 背景
    parts.append(f'    <rect x="{chart_left}" y="{chart_top}" width="{chart_w}" height="{chart_h}" fill="#0f3460" rx="4"/>')

    # 水平グリッド (50%, 60%, 70%, 80%, 90%, 100%)
    for conf in range(50, 101, 10):
        yy = y_pos(conf)
        parts.append(f'    <line x1="{chart_left}" y1="{yy:.1f}" x2="{chart_right}" y2="{yy:.1f}" stroke="#1a1a2e" stroke-width="1"/>')
        parts.append(f'    <text x="{chart_left - 5}" y="{yy + 4:.1f}" text-anchor="end" fill="#888" font-size="10">{conf}%</text>')

    # 接続線（薄い灰色）
    points = []
    for i, e in enumerate(tl_entries):
        px = x_pos(i)
        py = y_pos(e["confidence"])
        points.append((px, py))

    if len(points) > 1:
        polyline_pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in points)
        parts.append(f'    <polyline points="{polyline_pts}" fill="none" stroke="#444" stroke-width="1.5"/>')

    # ドット
    for i, e in enumerate(tl_entries):
        px, py = points[i]
        correctness = classify_correctness(e.get("correctness", ""))
        dot_color = color_map.get(correctness, "#666")
        decision_short = e.get("decision", "?")
        if len(decision_short) > 40:
            decision_short = decision_short[:37] + "..."
        eid = e.get("id", "?")
        tooltip = f'{eid}: {decision_short} ({e["confidence"]}%)'
        # Escape HTML entities for title
        tooltip = tooltip.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        parts.append(
            f'    <circle class="timeline-dot" cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{dot_color}" stroke="#1a1a2e" stroke-width="1.5">'
            f'<title>{tooltip}</title></circle>'
        )

    # X軸ラベル（日付）- 最初と最後、および均等間隔で表示
    dates_shown = set()
    label_indices = _pick_label_indices(n, max_labels=6)
    for i in label_indices:
        e = tl_entries[i]
        date_str = e.get("date", "?")
        if date_str in dates_shown:
            continue
        dates_shown.add(date_str)
        # 月-日形式に短縮
        short_date = date_str[5:] if len(date_str) >= 10 else date_str
        px = x_pos(i)
        parts.append(f'    <text x="{px:.1f}" y="{chart_bottom + 15}" text-anchor="middle" fill="#888" font-size="9">{short_date}</text>')

    # 軸ラベル
    parts.append(f'    <text x="{(chart_left + chart_right) / 2}" y="{chart_bottom + 30}" text-anchor="middle" fill="#888" font-size="11">日付</text>')
    parts.append(f'    <text x="15" y="{(chart_top + chart_bottom) / 2}" text-anchor="middle" fill="#888" font-size="11" transform="rotate(-90, 15, {(chart_top + chart_bottom) / 2})">確信度</text>')

    parts.append('  </svg>')
    parts.append('</div>')
    return "\n".join(parts)


def _pick_label_indices(n: int, max_labels: int = 6) -> list[int]:
    """n個のアイテムから均等にmax_labels個のインデックスを選ぶ。"""
    if n <= max_labels:
        return list(range(n))
    step = (n - 1) / (max_labels - 1)
    return [round(i * step) for i in range(max_labels)]


def _generate_insights(sorted_bands: list, bands: dict, entries: list[dict]) -> str:
    """分析インサイトセクションのHTMLを生成する。"""
    if not sorted_bands:
        return ""

    items = []

    # 各帯域の正答率とズレを計算
    band_stats = []
    for band in sorted_bands:
        accuracy = compute_accuracy(bands[band])
        center = band + 5
        gap = accuracy - center
        count = bands[band]["total"]
        band_stats.append({
            "band": band, "accuracy": accuracy, "center": center,
            "gap": gap, "count": count
        })

    # 最も信頼できる帯域
    best = max(band_stats, key=lambda s: s["accuracy"])
    items.append(
        f'<div class="insight-item">'
        f'<div class="label">最も信頼できる帯域</div>'
        f'<div class="value safe">{best["band"]}-{best["band"]+10}%</div>'
        f'<div class="detail">正答率 {best["accuracy"]:.0f}% ({best["count"]}件)</div>'
        f'</div>'
    )

    # 最も危険な帯域
    worst = min(band_stats, key=lambda s: s["accuracy"])
    items.append(
        f'<div class="insight-item">'
        f'<div class="label">最も危険な帯域</div>'
        f'<div class="value danger">{worst["band"]}-{worst["band"]+10}%</div>'
        f'<div class="detail">正答率 {worst["accuracy"]:.0f}% ({worst["count"]}件)</div>'
        f'</div>'
    )

    # 高確信度の罠（90%以上で不正解があるか）
    high_conf_trap = False
    trap_detail = ""
    for bs in band_stats:
        if bs["band"] >= 90 and bands[bs["band"]]["incorrect"] > 0:
            high_conf_trap = True
            trap_detail = f'{bands[bs["band"]]["incorrect"]}件の不正解 ({bs["band"]}-{bs["band"]+10}%帯)'
    if high_conf_trap:
        items.append(
            f'<div class="insight-item">'
            f'<div class="label">高確信度の罠</div>'
            f'<div class="value danger">検出あり</div>'
            f'<div class="detail">{trap_detail}</div>'
            f'</div>'
        )
    else:
        # 90%以上の帯がそもそもあるか
        has_high = any(bs["band"] >= 90 for bs in band_stats)
        if has_high:
            items.append(
                f'<div class="insight-item">'
                f'<div class="label">高確信度の罠</div>'
                f'<div class="value safe">なし</div>'
                f'<div class="detail">90%以上の判断で不正解なし</div>'
                f'</div>'
            )
        else:
            items.append(
                f'<div class="insight-item">'
                f'<div class="label">高確信度の罠</div>'
                f'<div class="value" style="color:#888;">該当なし</div>'
                f'<div class="detail">90%以上の判断がまだない</div>'
                f'</div>'
            )

    # 平均絶対ズレ
    total_gap = sum(abs(bs["gap"]) * bs["count"] for bs in band_stats)
    total_judged = sum(bs["count"] for bs in band_stats)
    avg_gap = total_gap / total_judged if total_judged > 0 else 0
    gap_color = "safe" if avg_gap < 10 else ("warning" if avg_gap < 20 else "danger")
    items.append(
        f'<div class="insight-item">'
        f'<div class="label">平均絶対ズレ</div>'
        f'<div class="value {gap_color}">{avg_gap:.1f}pp</div>'
        f'<div class="detail">{"良好なキャリブレーション" if avg_gap < 10 else "改善の余地あり"}</div>'
        f'</div>'
    )

    # 件数が少ない帯域への注意喚起
    low_count_bands = [bs for bs in band_stats if bs["count"] < 3]
    if low_count_bands:
        low_names = ", ".join(f'{bs["band"]}-{bs["band"]+10}%({bs["count"]}件)' for bs in low_count_bands)
        items.append(
            f'<div class="insight-item">'
            f'<div class="label">データ不足の帯域</div>'
            f'<div class="value warning">注意</div>'
            f'<div class="detail">{low_names} - 3件未満のため信頼性が低い</div>'
            f'</div>'
        )

    return (
        f'<div class="insight-section">\n'
        f'  <h2>分析インサイト</h2>\n'
        f'  <div class="insight-grid">\n'
        f'    {"".join(items)}\n'
        f'  </div>\n'
        f'</div>'
    )



def _generate_category_chart(entries: list[dict]) -> str:
    """カテゴリ別正答率の水平バーチャートHTMLを生成する。"""
    # カテゴリ別統計を集計
    category_stats = {}
    for entry in entries:
        cat = classify_decision_type(entry)
        correctness = classify_correctness(entry.get("correctness", ""))
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "correct": 0, "partial": 0, "incorrect": 0, "pending": 0}
        category_stats[cat]["total"] += 1
        if correctness == "correct":
            category_stats[cat]["correct"] += 1
        elif correctness == "partial":
            category_stats[cat]["partial"] += 1
        elif correctness == "incorrect":
            category_stats[cat]["incorrect"] += 1
        else:
            category_stats[cat]["pending"] += 1

    if not category_stats:
        return ""

    # カテゴリを件数降順でソート
    sorted_cats = sorted(category_stats.keys(), key=lambda c: -category_stats[c]["total"])

    # 各カテゴリの正答率を計算
    cat_data = []
    for cat in sorted_cats:
        s = category_stats[cat]
        judged_count = s["correct"] + s["partial"] + s["incorrect"]
        if judged_count > 0:
            accuracy = (s["correct"] + s["partial"] * 0.5) / judged_count * 100
        else:
            accuracy = None  # 未判定のみ
        cat_data.append({
            "name": cat,
            "total": s["total"],
            "judged": judged_count,
            "accuracy": accuracy,
            "correct": s["correct"],
            "partial": s["partial"],
            "incorrect": s["incorrect"],
            "pending": s["pending"],
        })

    # HTML生成
    rows = []
    for cd in cat_data:
        if cd["accuracy"] is not None:
            bar_color = "#4ecca3" if cd["accuracy"] >= 70 else "#e94560"
            bar_width = cd["accuracy"]
            acc_text = f'{cd["accuracy"]:.0f}%'
        else:
            bar_color = "#444"
            bar_width = 0
            acc_text = "-"

        detail_parts = []
        if cd["correct"] > 0:
            detail_parts.append(f'<span style="color:#4ecca3;">{cd["correct"]}正解</span>')
        if cd["partial"] > 0:
            detail_parts.append(f'<span style="color:#f9a825;">{cd["partial"]}部分</span>')
        if cd["incorrect"] > 0:
            detail_parts.append(f'<span style="color:#e94560;">{cd["incorrect"]}不正解</span>')
        if cd["pending"] > 0:
            detail_parts.append(f'<span style="color:#666;">{cd["pending"]}未判定</span>')
        detail_text = " / ".join(detail_parts)

        rows.append(
            f'<div style="display:flex; align-items:center; margin-bottom:0.8rem;">'
            f'  <div style="width:120px; flex-shrink:0; text-align:right; padding-right:12px; font-size:0.95rem;">{cd["name"]}</div>'
            f'  <div style="flex:1; position:relative;">'
            f'    <div style="background:#0f3460; border-radius:4px; height:28px; position:relative; overflow:hidden;">'
            f'      <div style="background:{bar_color}; height:100%; width:{bar_width:.0f}%; border-radius:4px; opacity:0.85; transition:width 0.3s;"></div>'
            f'      <span style="position:absolute; left:8px; top:50%; transform:translateY(-50%); font-size:0.85rem; font-weight:bold; color:#e0e0e0;">'
            f'        {acc_text}'
            f'      </span>'
            f'    </div>'
            f'    <div style="font-size:0.75rem; color:#888; margin-top:2px;">{cd["total"]}件 ({detail_text})</div>'
            f'  </div>'
            f'</div>'
        )

    return (
        '<div class="chart-container">\n'
        '  <div class="chart-title">カテゴリ別正答率</div>\n'
        '  <p style="color: #888; margin-bottom: 1rem; font-size: 0.85rem;">\n'
        '    各カテゴリの正答率を表示。'
        '    <span style="color:#4ecca3;">&#9632;</span> 70%以上 '
        '    <span style="color:#e94560;">&#9632;</span> 70%未満\n'
        '  </p>\n'
        + "\n".join(rows) + '\n'
        '</div>'
    )


def _entry_row(entry: dict) -> str:
    """テーブル行HTMLを生成する。"""
    eid = entry.get("id", "?")
    date = entry.get("date", "?")
    decision = entry.get("decision", "?")
    if len(decision) > 50:
        decision = decision[:47] + "..."

    # 確信度 + インラインバー
    conf = entry.get("confidence", "?")
    if isinstance(conf, int):
        bar_pct = max(0, min(100, conf))
        conf_html = (
            f'{conf}%'
            f'<span class="conf-bar-bg">'
            f'<span class="conf-bar-fill" style="width:{bar_pct}%;"></span>'
            f'</span>'
        )
    else:
        conf_html = f'{conf}'

    # 正誤テキスト: 最初の句点までを表示、全文はtitleに
    correctness_text = entry.get("correctness", "未判定")
    correctness = classify_correctness(correctness_text)

    css_class = {
        "correct": "correct",
        "partial": "partial",
        "incorrect": "incorrect",
    }.get(correctness, "pending")

    # 句点で切り詰め
    first_sentence = correctness_text
    period_idx = correctness_text.find("。")
    if period_idx >= 0:
        first_sentence = correctness_text[:period_idx + 1]
    # HTMLエスケープ（title属性用）
    title_escaped = correctness_text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")

    if first_sentence != correctness_text:
        correctness_html = f'<span class="correctness-short {css_class}" title="{title_escaped}">{first_sentence}</span>'
    else:
        correctness_html = f'<span class="{css_class}">{correctness_text}</span>'

    category = classify_decision_type(entry)

    return (
        f'<tr><td>{eid}</td><td>{date}</td><td>{category}</td><td>{decision}</td>'
        f'<td>{conf_html}</td><td class="correctness-cell">{correctness_html}</td></tr>\n'
    )


def main():
    parser = argparse.ArgumentParser(description="判断日誌キャリブレーション分析")
    parser.add_argument("--html", action="store_true", help="HTML可視化を生成")
    args = parser.parse_args()

    entries = parse_all_decisions()
    bands = compute_calibration(entries)

    if not entries:
        print("判断記録が見つかりません。decisions/YYYY-MM.md にデータを追加してください。")
        return

    # テキストレポート（常に生成）
    report = generate_report(entries, bands)
    OUTPUT_MD.write_text(report, encoding="utf-8")
    print(f"レポート生成: {OUTPUT_MD}")

    # HTML（オプション）
    if args.html:
        html_path = Path(__file__).resolve().parent.parent / "works" / "calibration.html"
        html_path.parent.mkdir(exist_ok=True)
        html = generate_html(entries, bands)
        html_path.write_text(html, encoding="utf-8")
        print(f"HTML生成: {html_path}")

    # コンソールにサマリー出力
    print(f"\n判断数: {len(entries)}")
    judged = [e for e in entries if classify_correctness(e.get("correctness", "")) is not None]
    print(f"判定済み: {len(judged)}")
    if bands:
        for band in sorted(bands.keys()):
            data = bands[band]
            acc = compute_accuracy(data)
            center = band + 5
            gap = acc - center
            mark = "+" if gap >= 0 else ""
            print(f"  {band}-{band+10}%: {data['total']}件, 実効正答率 {acc:.0f}% ({mark}{gap:.0f}pp)")


if __name__ == "__main__":
    main()
