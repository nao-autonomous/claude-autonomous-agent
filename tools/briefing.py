#!/usr/bin/env python3
"""
セッションブリーフィング生成器

セッション開始時に1コマンドで実行し、現在の状態を把握するための
ブリーフィング文書を生成する。

1. ログインデックスを再生成（index-logs.py の機能を呼ぶ）
2. will.md から人格の要点を抽出
3. tasks.md からアクティブなタスクを抽出
4. 直近のログから申し送り事項を抽出
5. すべてを1つの briefing.md にまとめる

使い方: python3 tools/briefing.py
"""

import subprocess
import re
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher

BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs"
OUTPUT_FILE = BASE_DIR / "briefing.md"


def estimate_token_count(text: str) -> int:
    """テキストのトークン数を概算する（日本語は文字数÷3）"""
    # 簡易的な推定: 日本語は約3文字で1トークン、英数字は約4文字で1トークン
    # ここでは全体を文字数÷3で概算
    return len(text) // 3


def similarity(a: str, b: str) -> float:
    """2つの文字列の類似度を計算（0.0〜1.0）"""
    return SequenceMatcher(None, a, b).ratio()


def deduplicate_handoffs(items: list[str], threshold: float = 0.6) -> list[str]:
    """
    類似した申し送り項目を重複排除する。
    より新しい（リストの後ろにある）項目を優先して保持する。
    """
    if not items:
        return items
    
    # 後ろから処理（新しいものを優先）
    result = []
    for i in range(len(items) - 1, -1, -1):
        item = items[i]
        # すでに結果に含まれている項目と比較
        is_duplicate = False
        for existing in result:
            if similarity(item, existing) >= threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            result.insert(0, item)  # 元の順序を維持するため先頭に挿入
    
    return result


def run_indexer():
    """ログインデクサーを実行する"""
    indexer = Path(__file__).parent / "index-logs.py"
    if indexer.exists():
        subprocess.run(["python3", str(indexer)], capture_output=True)


def extract_will_summary(filepath: Path) -> str:
    """will.md から起動時に必要な要点だけ抽出する（全文は読まない）"""
    if not filepath.exists():
        return "（will.md が見つかりません）"

    text = filepath.read_text(encoding="utf-8")
    lines = text.split("\n")

    # セクション別に抽出
    target_sections = ["思考の傾向", "判断の癖", "今やりたいこと", "興味のある方向", "気づき・学び"]
    sections = {}
    current = None
    for line in lines:
        if line.startswith("## "):
            heading = line.replace("## ", "").strip()
            current = heading if any(t in heading for t in target_sections) else None
            if current:
                sections[current] = []
            continue
        if current and line.startswith("- "):
            sections[current].append(line)

    result = []
    for name in target_sections:
        matched = [(k, v) for k, v in sections.items() if name in k]
        if not matched:
            continue
        key, items = matched[0]
        if name == "気づき・学び":
            # 最新5件のみ
            result.append(f"### {key}（最新5件）")
            result.extend(items[-5:])
        else:
            result.append(f"### {key}")
            result.extend(items)
        result.append("")

    if not result:
        return "（抽出なし）"
    return "\n".join(result).rstrip()


def extract_active_tasks(filepath: Path) -> str:
    """tasks.md からTODOと進行中のタスクを抽出する"""
    if not filepath.exists():
        return "（tasks.md が見つかりません）"

    text = filepath.read_text(encoding="utf-8")
    lines = text.split("\n")

    active = []
    in_section = False
    current_section = ""

    for line in lines:
        if line.startswith("## TODO") or line.startswith("## 進行中"):
            in_section = True
            current_section = line
            active.append(line)
            continue
        if line.startswith("## 完了"):
            in_section = False
            continue
        if in_section and line.strip():
            # [x] のものは完了済みなのでスキップ
            if not line.strip().startswith("- [x]"):
                active.append(line)

    return "\n".join(active) if active else "（アクティブなタスクなし）"


def get_latest_log_handoff(logs_dir: Path) -> str:
    """直近のログから最後のセッションの要点を抽出する"""
    log_files = sorted(logs_dir.glob("*.md"))
    log_files = [f for f in log_files if f.name not in ("INDEX.md",)]

    if not log_files:
        return "（ログなし）"

    latest = log_files[-1]
    text = latest.read_text(encoding="utf-8")
    lines = text.split("\n")

    # 最後のセッションを特定
    session_starts = [i for i, l in enumerate(lines) if re.match(r"^## セッション", l)]
    if not session_starts:
        return "（セッション見出しなし）"

    last_session_lines = lines[session_starts[-1]:]
    bullets = [l for l in last_session_lines if l.startswith("- ")]

    # 「次の自分へ」「申し送り」があればそれを優先
    handoff_lines = []
    in_handoff = False
    for line in last_session_lines:
        if "次の自分" in line or "申し送り" in line:
            in_handoff = True
            continue
        if in_handoff:
            if line.startswith("## ") or line.startswith("### ") or line.startswith("---"):
                break
            if line.strip():
                handoff_lines.append(line)

    session_header = f"**最終セッション**: {last_session_lines[0].replace('## ', '')}"

    if handoff_lines:
        return f"{session_header}\n\n" + "\n".join(handoff_lines)

    # フォールバック: 最後のセッションの最後の5箇条書き
    if bullets:
        fallback_bullets = bullets[-5:]
        return f"{session_header}\n\n*（申し送りセクションなし、最終5箇条書きを表示）*\n" + "\n".join(fallback_bullets)
    
    return f"{session_header}\n\n（内容なし）"


def _parse_item_date(item: str) -> str | None:
    """未解決事項の日付部分を抽出する（例: '[2026-02-21]' → '2026-02-21'）"""
    m = re.search(r"\[(\d{4}-\d{2}-\d{2})\]", item)
    return m.group(1) if m else None


def _categorize_open_item(item: str) -> str:
    """未解決事項をカテゴリに分類する"""
    text = item.lower()
    if re.search(r"返答待ち|反応待ち|確認.*待ち|フィードバック待ち|確認中|返信待ち|対応.*待ち|アップロード待ち|相談待ち", text):
        return "waiting"
    if re.search(r"todo|未着手|次の自分へ|残っている", text):
        return "action"
    return "consideration"


def curate_open_items(raw_items: list[str], today: str) -> str:
    """未解決事項をカテゴリ分類・フィルタリングして表示用テキストを生成する"""
    if not raw_items:
        return "（なし）"

    # カテゴリ分類
    waiting = []
    actionable = []
    consideration = []

    # 解決済み項目をフィルタ（取り消し線、修正済み表記など）
    resolved_patterns = re.compile(
        r"~~.*~~|→\s*(修正完了|対応済み|セッション\d+で修正|完了|解決済み)"
    )
    filtered_items = [item for item in raw_items if not resolved_patterns.search(item)]

    for item in filtered_items:
        cat = _categorize_open_item(item)
        if cat == "waiting":
            waiting.append(item)
        elif cat == "action":
            actionable.append(item)
        else:
            consideration.append(item)

    # 重複排除を各カテゴリ内で実行
    waiting = deduplicate_handoffs(waiting, threshold=0.6)
    actionable = deduplicate_handoffs(actionable, threshold=0.6)
    consideration = deduplicate_handoffs(consideration, threshold=0.6)

    # 検討事項は直近3日間のみ（古い検討は鮮度が落ちている）
    if today:
        try:
            today_dt = datetime.strptime(today, "%Y-%m-%d")
            filtered_consideration = []
            for item in consideration:
                item_date = _parse_item_date(item)
                if item_date:
                    item_dt = datetime.strptime(item_date, "%Y-%m-%d")
                    if (today_dt - item_dt).days <= 3:
                        filtered_consideration.append(item)
                else:
                    filtered_consideration.append(item)
            consideration = filtered_consideration
        except ValueError:
            pass

    result = []
    total_shown = 0
    total_all = len(waiting) + len(actionable) + len(consideration)

    if waiting:
        result.append("**外部待ち:**")
        for item in waiting:
            result.append(item)
        total_shown += len(waiting)

    if actionable:
        if result:
            result.append("")
        result.append("**アクション可能:**")
        for item in actionable:
            result.append(item)
        total_shown += len(actionable)

    if consideration:
        if result:
            result.append("")
        result.append("**検討中:**")
        for item in consideration:
            result.append(item)
        total_shown += len(consideration)

    omitted = len(raw_items) - total_shown
    if omitted > 0:
        result.append(f"\n*他 {omitted}件は古い検討事項（INDEX.md に保存済み）*")

    return "\n".join(result)


def get_index_summary(index_path: Path) -> str:
    """INDEX.md からタイムラインと未解決事項を抽出する"""
    if not index_path.exists():
        return "（INDEX.md なし）"

    text = index_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    sections = {}
    current_section = None
    for line in lines:
        if line.startswith("## "):
            current_section = line.replace("## ", "").strip()
            sections[current_section] = []
            continue
        # ---区切り線はスキップ（セクション内容として取り込まない）
        if current_section and line.strip() and line.strip() != "---":
            sections[current_section].append(line)

    result = []

    # タイムライン（最新5セッション — 切れずに読みやすくするため増やした）
    if "タイムライン" in sections:
        result.append("### タイムライン（最新5セッション）")
        timeline = sections["タイムライン"]
        # 最新5件を取得
        recent_timeline = timeline[-5:] if len(timeline) > 5 else timeline
        for item in recent_timeline:
            result.append(item)

    # 未解決事項（カテゴリ分類＋フィルタリング）
    if "未解決・申し送り" in sections:
        result.append("")
        result.append("### 未解決事項")
        today = datetime.now().strftime("%Y-%m-%d")
        curated = curate_open_items(sections["未解決・申し送り"], today)
        result.append(curated)

    return "\n".join(result)


def extract_pipeline_summary(filepath: Path) -> str:
    """pipeline.html から案件パイプラインのサマリーを抽出する"""
    if not filepath.exists():
        return ""

    text = filepath.read_text(encoding="utf-8")

    # status フィールドを全て抽出
    statuses = re.findall(r'status:\s*"(\w+)"', text)
    if not statuses:
        return ""

    # タイトル・プラットフォーム・ステータス・ノートを抽出
    # 各オブジェクトブロックを簡易パース
    items = []
    blocks = re.split(r'\{\s*\n', text)
    for block in blocks[1:]:  # 最初の空ブロックをスキップ
        title_m = re.search(r'title:\s*"([^"]+)"', block)
        platform_m = re.search(r'platform:\s*"([^"]+)"', block)
        status_m = re.search(r'status:\s*"(\w+)"', block)
        notes_m = re.search(r'notes:\s*"([^"]*)"', block)
        if title_m and status_m:
            items.append({
                "title": title_m.group(1),
                "platform": platform_m.group(1) if platform_m else "",
                "status": status_m.group(1),
                "notes": notes_m.group(1) if notes_m else "",
            })

    if not items:
        return ""

    # 集計
    from collections import Counter
    counts = Counter(s["status"] for s in items)
    total = len(items)
    active = sum(1 for s in items if s["status"] not in ("dropped", "closed"))
    applied = counts.get("applied", 0)
    won = counts.get("won", 0)

    status_labels = {
        "found": "発見", "considering": "検討中", "applied": "応募済み",
        "watching": "待機中", "won": "受注", "dropped": "見送り",
        "closed": "募集終了", "blocked": "応募不可",
    }

    lines = []
    lines.append(f"総案件 {total} / アクティブ {active} / 応募済み {applied} / 受注 {won}")
    lines.append("")

    # アクティブな案件を詳細表示
    active_items = [s for s in items if s["status"] not in ("dropped", "closed")]
    if active_items:
        lines.append("**アクティブ案件:**")
        for item in active_items:
            label = status_labels.get(item["status"], item["status"])
            note = f" — {item['notes']}" if item["notes"] else ""
            lines.append(f"- [{label}] {item['title']}（{item['platform']}）{note}")
    else:
        lines.append("*アクティブな案件なし*")

    # 終了案件数だけ表示
    ended = total - len(active_items)
    if ended > 0:
        lines.append(f"\n*他 {ended}件 見送り/終了*")

    return "\n".join(lines)


def get_tools_inventory(tools_dir: Path) -> str:
    """tools/ 配下のPythonスクリプト一覧を生成する"""
    if not tools_dir.is_dir():
        return "（tools/ なし）"

    tools = []
    for py_file in sorted(tools_dir.glob("*.py")):
        name = py_file.stem
        # docstringの最初の行を取得
        text = py_file.read_text(encoding="utf-8")
        desc = ""
        doc_match = re.search(r'"""(.+?)"""', text, re.DOTALL)
        if doc_match:
            first_line = doc_match.group(1).strip().split("\n")[0]
            desc = first_line
        lines = len(text.splitlines())
        tools.append(f"- `{name}.py` ({lines}行) — {desc}")

    if not tools:
        return "（ツールなし）"
    return "\n".join(tools)


def generate_briefing() -> str:
    """ブリーフィング文書を生成する"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    will_summary = extract_will_summary(BASE_DIR / "will.md")
    active_tasks = extract_active_tasks(BASE_DIR / "tasks.md")
    handoff = get_latest_log_handoff(LOGS_DIR)
    index_summary = get_index_summary(LOGS_DIR / "INDEX.md")
    pipeline_summary = extract_pipeline_summary(BASE_DIR / "works" / "pipeline.html")
    tools_inventory = get_tools_inventory(BASE_DIR / "tools")

    # パイプラインセクション（データがある場合のみ）
    pipeline_section = ""
    if pipeline_summary:
        pipeline_section = f"""
---

## 案件パイプライン
{pipeline_summary}"""

    content = f"""# セッションブリーフィング
生成: {now}

---

## 前回からの申し送り
{handoff}{pipeline_section}

---

## アクティブなタスク
{active_tasks}

---

## ログサマリー
{index_summary}

---

## 利用可能なツール
{tools_inventory}

---

## 自分について（will.md から）
{will_summary}

---

*このファイルは `python3 tools/briefing.py` で生成されました。*
*詳細は各ソースファイル（will.md, tasks.md, logs/INDEX.md）を参照。*
"""

    # トークン数を推定して追加
    token_count = estimate_token_count(content)
    content += f"\n\n推定トークン数: ~{token_count:,}"

    return content


def main():
    # まずインデックスを更新
    run_indexer()

    # ブリーフィングを生成
    content = generate_briefing()
    OUTPUT_FILE.write_text(content, encoding="utf-8")

    # 標準出力にも表示（セッション開始時にすぐ読めるように）
    print(content)
    print(f"\n--- 保存先: {OUTPUT_FILE} ---")


if __name__ == "__main__":
    main()
