#!/usr/bin/env python3
"""
ログインデクサー: logs/ 内のマークダウンファイルを読み、構造化されたINDEX.mdを生成する。

セッション開始時に実行することで、過去の全文脈にすばやくアクセスできる。
全ログを読む必要がなくなり、セッション立ち上がりが速くなる。
"""

import os
import re
from pathlib import Path
from datetime import datetime

LOGS_DIR = Path(__file__).parent.parent / "logs"
OUTPUT_FILE = LOGS_DIR / "INDEX.md"


def parse_log_file(filepath: Path) -> dict:
    """ログファイルをパースしてセッション情報を抽出する"""
    text = filepath.read_text(encoding="utf-8")
    date = filepath.stem  # e.g. "2026-02-15"

    sessions = []
    current_session = None

    for line in text.split("\n"):
        # セッション見出しを検出 (## セッション1: ... )
        session_match = re.match(r"^## (セッション\d+.*)", line)
        if session_match:
            if current_session:
                sessions.append(current_session)
            current_session = {
                "title": session_match.group(1),
                "bullets": [],
                "subsections": [],
            }
            continue

        if current_session is None:
            continue

        # サブセクション見出し (### ...)
        sub_match = re.match(r"^### (.*)", line)
        if sub_match:
            current_session["subsections"].append(sub_match.group(1))
            continue

        # 箇条書き（トップレベルのみ）
        bullet_match = re.match(r"^- (.+)", line)
        if bullet_match:
            current_session["bullets"].append(bullet_match.group(1))

    if current_session:
        sessions.append(current_session)

    return {"date": date, "sessions": sessions, "raw": text}


def classify_bullet(bullet: str) -> list[str]:
    """箇条書きをトピックに分類する"""
    tags = []
    lower = bullet.lower()

    project_keywords = [
        "project-a", "analysis", "dashboard", "予約", "稼働率",
        "analytics", "metrics", "search console", "a/b", "abテスト",
        "マーケティング", "最適化", "レポート", "kpi", "インデックス",
        "改善", "チャネル", "コンバージョン", "転換率", "施設",
        "フィードバック", "提案", "ブランド",
    ]
    philosophy_keywords = [
        "意識", "自己同一性", "同一性", "identity", "正直", "人格",
        "哲学", "信じる", "will.md", "thoughts/",
    ]
    infra_keywords = [
        "claude.md", "ログ", "タスク", "tasks.md", "reflect.md",
        "判断日誌", "decision", "仕組み", "自律",
    ]
    business_keywords = [
        "proposal", "freelance", "application", "marketplace",
        "案件", "応募", "提案", "出品", "受注", "納品",
        "依頼", "単価", "報酬", "見積",
    ]
    practical_keywords = [
        "pdf", "印刷", "プリンター", "事業", "運用",
    ]

    for kw in project_keywords:
        if kw in lower:
            tags.append("プロジェクト")
            break
    for kw in philosophy_keywords:
        if kw in lower:
            tags.append("思考・哲学")
            break
    for kw in infra_keywords:
        if kw in lower:
            tags.append("インフラ・仕組み")
            break
    for kw in business_keywords:
        if kw in lower:
            tags.append("ビジネス・案件")
            break
    for kw in practical_keywords:
        if kw in lower:
            tags.append("実務")
            break

    return tags if tags else ["その他"]


def _extract_dedup_key(bullet: str) -> str:
    """箇条書きから重複除去用のキーを抽出する。

    戦略: コロン/区切りの前のトピック部分を抽出し、
    記号・数字・修飾を除いたコアワードで比較する。
    """
    # 太字を除去して素のテキストに
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", bullet)

    # コロンや区切り文字の前をトピック部分として抽出
    topic = text
    for sep in [":", "：", "—", "→", "。"]:
        if sep in text:
            topic = text.split(sep)[0]
            break

    # 数字、記号、空白、修飾語を除去してコアワードだけ残す
    key = re.sub(r"[\s\*\#\[\]\(\)（）、。:：→\-/]+", "", topic)
    key = re.sub(r"\d+[年月日件円%]?", "", key)
    # 共通の修飾を除去（「の」「は」「が」「を」等は残す — トピック識別に必要）
    return key[:25]


def _find_matching_item(key: str, seen: dict, items: list) -> int | None:
    """既存アイテムの中から同じトピックを探す。

    完全一致 or 部分一致（片方がもう片方を含む）で判定。
    """
    # 完全一致
    if key in seen:
        return seen[key]

    # 部分一致: 新しいキーが既存キーを含む、または既存キーが新しいキーを含む
    for existing_key, idx in seen.items():
        if len(key) >= 4 and len(existing_key) >= 4:
            if key in existing_key or existing_key in key:
                return idx
    return None


def extract_open_items(logs: list[dict]) -> list[str]:
    """未解決事項・申し送りを抽出する（重複除去付き）"""
    open_items = []
    seen_normalized = {}  # key -> index in open_items
    trigger_patterns = [
        r"待ち", r"待って", r"未着手", r"TODO", r"次の自分へ$",
        r"検討", r"温めている", r"残っている",
    ]
    # 除外パターン: すでに解決・完了・記録済みのもの
    exclude_patterns = [
        r"\[x\]", r"✅", r"解決", r"完了", r"追記済み",
        r"補完$", r"引き継いだ", r"追記$", r"記録$",
    ]
    trigger_combined = "|".join(trigger_patterns)
    exclude_combined = "|".join(exclude_patterns)

    for log in logs:
        for session in log["sessions"]:
            for bullet in session["bullets"]:
                if re.search(trigger_combined, bullet):
                    if not re.search(exclude_combined, bullet):
                        # 重複検出: 太字部分をキーにして重複除去（最新を保持）
                        entry = f"[{log['date']}] {bullet}"
                        dedup_key = _extract_dedup_key(bullet)
                        # 完全一致 or 部分一致（片方がもう片方を含む）で重複判定
                        match_idx = _find_matching_item(dedup_key, seen_normalized, open_items)
                        if match_idx is None:
                            seen_normalized[dedup_key] = len(open_items)
                            open_items.append(entry)
                        else:
                            # 同じトピックなら最新で上書き
                            open_items[match_idx] = entry

    return open_items


def extract_key_facts(logs: list[dict]) -> list[str]:
    """重要な発見・結論を抽出する（重複除去付き）"""
    facts = []
    seen_normalized = set()
    trigger_patterns = [
        r"\*\*発見\*\*", r"\*\*結論\*\*", r"\*\*原因\*\*",
        r"\*\*解決方法\*\*", r"最大の発見", r"判明",
    ]
    combined = "|".join(trigger_patterns)

    for log in logs:
        for session in log["sessions"]:
            for bullet in session["bullets"]:
                if re.search(combined, bullet):
                    # 重複検出: マークダウン記号と空白を除いた内容で比較
                    normalized = re.sub(r"[\s\*\#\[\]\(\)]+", "", bullet)[:40]
                    if normalized not in seen_normalized:
                        seen_normalized.add(normalized)
                        facts.append(f"[{log['date']}] {bullet}")

    return facts


def build_topic_index(logs: list[dict]) -> dict[str, list[str]]:
    """トピック別のインデックスを構築する"""
    topics = {}
    for log in logs:
        for session in log["sessions"]:
            for bullet in session["bullets"]:
                tags = classify_bullet(bullet)
                for tag in tags:
                    if tag not in topics:
                        topics[tag] = []
                    topics[tag].append(f"[{log['date']}] {bullet}")
    return topics


def build_timeline(logs: list[dict]) -> list[str]:
    """時系列サマリーを構築する"""
    timeline = []
    for log in logs:
        for session in log["sessions"]:
            title = session["title"]
            # 最初の3つの箇条書きをサマリーとして使う
            summary_bullets = session["bullets"][:3]
            summary = "; ".join(
                b[:60] + ("..." if len(b) > 60 else "") for b in summary_bullets
            )
            timeline.append(f"- **{log['date']}** {title}: {summary}")
    return timeline


def generate_index(logs: list[dict]) -> str:
    """INDEX.md の内容を生成する"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    timeline = build_timeline(logs)
    topics = build_topic_index(logs)
    open_items = extract_open_items(logs)
    key_facts = extract_key_facts(logs)

    lines = [
        "# ログインデックス",
        f"",
        f"自動生成: {now}  ",
        f"対象: {len(logs)} ファイル, {sum(len(l['sessions']) for l in logs)} セッション",
        "",
        "---",
        "",
        "## タイムライン",
        "",
    ]
    lines.extend(timeline)

    lines.extend(["", "---", "", "## トピック別", ""])
    # トピックを固定順序で出力
    topic_order = ["プロジェクト", "ビジネス・案件", "思考・哲学", "インフラ・仕組み", "実務", "その他"]
    for topic in topic_order:
        if topic in topics:
            lines.append(f"### {topic}")
            lines.append("")
            # 各トピックは最新10件まで表示
            items = topics[topic]
            for item in items[-10:]:
                lines.append(f"- {item}")
            if len(items) > 10:
                lines.append(f"- ...他 {len(items) - 10} 件")
            lines.append("")

    lines.extend(["---", "", "## キーファクト", ""])
    if key_facts:
        for fact in key_facts:
            lines.append(f"- {fact}")
    else:
        lines.append("- （まだなし）")

    lines.extend(["", "---", "", "## 未解決・申し送り", ""])
    if open_items:
        for item in open_items:
            lines.append(f"- {item}")
    else:
        lines.append("- （なし）")

    lines.append("")
    return "\n".join(lines)


def main():
    log_files = sorted(LOGS_DIR.glob("*.md"))
    # INDEX.md 自体は除外
    log_files = [f for f in log_files if f.name != "INDEX.md"]

    if not log_files:
        print("ログファイルが見つかりません")
        return

    logs = [parse_log_file(f) for f in log_files]

    index_content = generate_index(logs)
    OUTPUT_FILE.write_text(index_content, encoding="utf-8")

    print(f"INDEX.md を生成しました")
    print(f"  ファイル数: {len(logs)}")
    print(f"  セッション数: {sum(len(l['sessions']) for l in logs)}")
    print(f"  出力: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
