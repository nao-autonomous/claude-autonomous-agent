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

    project_a_keywords = [
        "project-a", "dashboard", "analytics", "booking", "occupancy",
        "listing", "conversion", "channel",
    ]
    philosophy_keywords = [
        "意識", "自己同一性", "同一性", "identity", "正直", "人格",
        "哲学", "信じる", "will.md", "thoughts/", "内省", "自己モデル",
        "振り返り", "気づき",
    ]
    infra_keywords = [
        "claude.md", "ログ", "タスク", "tasks.md", "reflect.md",
        "判断日誌", "decision", "仕組み", "自律",
        "mirror", "calibration", "briefing", "search.py", "explorer",
        "continuity", "hook", "backup", "コンテキスト",
        "index-logs", "log-explorer", "generate_sessions",
    ]
    business_keywords = [
        "freelance", "project", "proposal", "listing", "contract",
        "delivery", "request", "budget", "estimate", "profile",
        "blog", "github", "article", "portfolio",
    ]
    wp_site_keywords = [
        "wordpress", "rest api", "code snippet",
        "seo", "structured data", "json-ld", "schema", "meta description",
        "ssl", "domain", "php",
        "ux", "cta", "responsive",
    ]
    practical_keywords = [
        "pdf", "印刷", "プリンター", "事業", "トレード",
        "在庫管理", "gas", "スプレッドシート",
    ]

    for kw in project_a_keywords:
        if kw in lower:
            tags.append("project-a")
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
    for kw in wp_site_keywords:
        if kw in lower:
            tags.append("WordPress・サイト運用")
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


def _is_observation(bullet: str) -> bool:
    """箇条書きが観察/振り返りであり、アクション項目ではないかを判定する。

    トリガーワード（待ち、検討等）を含んでいても、実質的には
    過去の判断の振り返りや学びの記録である場合をフィルタリングする。
    """
    observation_patterns = [
        # 過去形の振り返り・評価
        r"正しかった", r"良い判断", r"判断は.*正し",
        r"効いた", r"固められた",
        # 学び・気づきの記録
        r"原則.*通り", r"原則に従って", r"パターン.*再現",
        r"戦略が再現", r"組み合わせ戦略",
        # 過去の行動の記述
        r"使えた$", r"選んだ$",
        # 過去の対話の記録
        r"正直に答えた", r"と問われ",
        # 見送り決定済み
        r"見送り$", r"→見送り", r"見送り判断",
        # 状況の観察（アクションではない）
        r"待ちタスクが多い", r"変化なし\）$", r"前回と変化なし",
        # 知見・比較（アクションではなく学び）
        r"比較:", r"は.*強み$",
        # 過去の方向性決定（もう定着済み）
        r"新しい方向性",
    ]
    return bool(re.search("|".join(observation_patterns), bullet))


def _get_topic_cluster(bullet: str) -> str | None:
    """箇条書きが属するトピッククラスタを特定する。

    同じ進行中トピックに関する複数エントリ（状態更新）を
    一つにまとめるために使う。クラスタ内では最新のエントリのみ保持する。
    """
    # トピッククラスタ定義: (パターン, クラスタ名)
    # 順序重要 — 全体ステータスを個別案件より先に（リスト内の個別名に引っかからないように）
    topic_clusters = [
        (r"応募.*待ち|応募.*件|応募ステータス", "応募状況"),
        (r"listing.*live|listing.*status|listing.*pending", "listing-status"),
        (r"education.*project|education.*proposal", "education-project"),
        (r"在庫管理", "在庫管理"),
        (r"project.*title", "project-title"),
        (r"イラストマップ", "イラストマップ"),
        (r"analytics.*API", "analytics-API"),
        (r"promo.*image", "promo-image"),
        (r"スニペット.*残っている|テストスニペット", "テストスニペット"),
        (r"site-a.*CTA", "site-a-CTA"),
        (r"site-b.*WAF", "site-b-WAF"),
        (r"keyword.*research", "keyword-research"),
        (r"QRコード", "QRコード案件"),
        (r"ChatGPT案件", "ChatGPT案件"),
    ]
    for pattern, cluster in topic_clusters:
        if re.search(pattern, bullet):
            return cluster
    return None


def extract_open_items(logs: list[dict]) -> list[str]:
    """未解決事項・申し送りを抽出する（3層の重複除去）

    重複除去の優先順位:
    1. トピッククラスタ — 既知の進行中トピックは最新エントリのみ保持
    2. エンティティ（太字テキスト）— 同一エンティティの最新を保持
    3. キーベース — テキスト先頭の類似度で判定
    """
    open_items = []
    seen_clusters = {}  # cluster_name -> index in open_items
    seen_normalized = {}  # key -> index in open_items
    trigger_patterns = [
        r"待ち", r"待って", r"未着手", r"TODO", r"次の自分へ$",
        r"検討", r"温めている", r"残っている",
    ]
    exclude_patterns = [
        r"\[x\]", r"✅", r"解決", r"完了", r"追記済み",
        r"補完$", r"引き継いだ", r"追記$", r"記録$",
    ]
    trigger_combined = "|".join(trigger_patterns)
    exclude_combined = "|".join(exclude_patterns)

    for log in logs:
        for session in log["sessions"]:
            for bullet in session["bullets"]:
                if not re.search(trigger_combined, bullet):
                    continue
                if re.search(exclude_combined, bullet):
                    continue
                if _is_observation(bullet):
                    continue

                entry = f"[{log['date']}] {bullet}"

                # 1. トピッククラスタベースの重複排除（最優先）
                cluster = _get_topic_cluster(bullet)
                if cluster:
                    if cluster in seen_clusters:
                        open_items[seen_clusters[cluster]] = entry
                    else:
                        seen_clusters[cluster] = len(open_items)
                        open_items.append(entry)
                    continue

                # 2. キーベースの重複排除（フォールバック）
                dedup_key = _extract_dedup_key(bullet)
                match_idx = _find_matching_item(dedup_key, seen_normalized, open_items)
                if match_idx is None:
                    seen_normalized[dedup_key] = len(open_items)
                    open_items.append(entry)
                else:
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
    topic_order = ["project-a", "ビジネス・案件", "WordPress・サイト運用", "思考・哲学", "インフラ・仕組み", "実務", "その他"]
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
