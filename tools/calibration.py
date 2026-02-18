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

    # 個別判断一覧
    lines.append("## 判断一覧")
    lines.append("")
    lines.append("| ID | 日付 | 判断 | 確信度 | 正誤 |")
    lines.append("|----|------|------|--------|------|")
    for entry in entries:
        eid = entry.get("id", "?")
        date = entry.get("date", "?")
        decision = entry.get("decision", "?")
        if len(decision) > 40:
            decision = decision[:37] + "..."
        conf = entry.get("confidence", "?")
        correctness = entry.get("correctness", "未判定")
        lines.append(f"| {eid} | {date} | {decision} | {conf}% | {correctness} |")

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

    # データ準備
    labels = [f"{b}-{b+10}%" for b in sorted_bands]
    expected = [b + 5 for b in sorted_bands]
    actual = [compute_accuracy(bands[b]) for b in sorted_bands]
    counts = [bands[b]["total"] for b in sorted_bands]

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
  .correct {{ color: #4ecca3; }}
  .partial {{ color: #f9a825; }}
  .incorrect {{ color: #e94560; }}
  .pending {{ color: #666; }}
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
    <div class="stat-value">{len([e for e in entries if classify_correctness(e.get('correctness','')) is not None])}</div>
    <div class="stat-label">判定済み</div>
  </div>
  <div class="stat-card">
    <div class="stat-value">{len([e for e in entries if classify_correctness(e.get('correctness','')) is None])}</div>
    <div class="stat-label">未判定</div>
  </div>
</div>

<div class="chart-container">
  <div class="chart-title">キャリブレーションチャート</div>
  <p style="color: #888; margin-bottom: 1rem; font-size: 0.85rem;">
    灰色の対角線 = 完全キャリブレーション（確信度 = 正答率）。
    赤いバーが対角線より下なら過信、上なら過小評価。
  </p>
  <svg viewBox="0 0 500 320" xmlns="http://www.w3.org/2000/svg">
    <!-- 背景グリッド -->
    <rect x="60" y="10" width="420" height="260" fill="#0f3460" rx="4"/>
    {''.join(f'<line x1="60" y1="{10 + i*52}" x2="480" y2="{10 + i*52}" stroke="#1a1a2e" stroke-width="1"/>' for i in range(6))}

    <!-- Y軸ラベル -->
    {''.join(f'<text x="55" y="{270 - i*52 + 4}" text-anchor="end" fill="#888" font-size="11">{i*20}%</text>' for i in range(6))}

    <!-- 対角線（完全キャリブレーション） -->
    <line x1="60" y1="270" x2="480" y2="10" stroke="#444" stroke-width="2" stroke-dasharray="6,4"/>

    <!-- データバー -->
    {_generate_bars(sorted_bands, bands)}

    <!-- X軸ラベル -->
    <text x="270" y="310" text-anchor="middle" fill="#888" font-size="12">確信度帯</text>
    <text x="15" y="140" text-anchor="middle" fill="#888" font-size="12" transform="rotate(-90, 15, 140)">実効正答率</text>
  </svg>
</div>

<div class="chart-container">
  <div class="chart-title">判断一覧</div>
  <table>
    <thead>
      <tr><th>ID</th><th>日付</th><th>判断</th><th>確信度</th><th>正誤</th></tr>
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


def _generate_bars(sorted_bands: list, bands: dict) -> str:
    """SVGバーを生成する。"""
    if not sorted_bands:
        return '<text x="270" y="140" text-anchor="middle" fill="#888" font-size="14">データなし</text>'

    parts = []
    n = len(sorted_bands)
    bar_width = min(60, 380 // max(n, 1))
    gap = (420 - bar_width * n) // (n + 1)

    for i, band in enumerate(sorted_bands):
        x = 60 + gap + i * (bar_width + gap)
        accuracy = compute_accuracy(bands[band])
        height = accuracy / 100 * 260
        y = 270 - height
        count = bands[band]["total"]

        # バーの色: 正答率が確信度帯の中心より高ければ緑、低ければ赤
        center = band + 5
        color = "#4ecca3" if accuracy >= center else "#e94560"

        parts.append(
            f'<rect class="bar" x="{x}" y="{y}" width="{bar_width}" height="{height}" '
            f'fill="{color}" rx="3" opacity="0.85"/>'
        )
        # バーの上に数値
        parts.append(
            f'<text x="{x + bar_width//2}" y="{y - 5}" text-anchor="middle" '
            f'fill="#e0e0e0" font-size="10">{accuracy:.0f}% (n={count})</text>'
        )
        # X軸ラベル
        parts.append(
            f'<text x="{x + bar_width//2}" y="{290}" text-anchor="middle" '
            f'fill="#888" font-size="10">{band}-{band+10}%</text>'
        )

    return "\n    ".join(parts)


def _entry_row(entry: dict) -> str:
    """テーブル行HTMLを生成する。"""
    eid = entry.get("id", "?")
    date = entry.get("date", "?")
    decision = entry.get("decision", "?")
    if len(decision) > 50:
        decision = decision[:47] + "..."
    conf = entry.get("confidence", "?")
    correctness_text = entry.get("correctness", "未判定")
    correctness = classify_correctness(correctness_text)

    css_class = {
        "correct": "correct",
        "partial": "partial",
        "incorrect": "incorrect",
    }.get(correctness, "pending")

    return (
        f'<tr><td>{eid}</td><td>{date}</td><td>{decision}</td>'
        f'<td>{conf}%</td><td class="{css_class}">{correctness_text}</td></tr>\n'
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
