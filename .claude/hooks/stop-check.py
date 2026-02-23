#!/usr/bin/env python3
"""
Claude Code Stop Hook: データ形式調査 & 言行不一致パターン検出

- stdin から JSON を読み取り、構造をログに保存（最新10件）
- レスポンス末尾にコミットメント表現があるのにツールコールがない場合を検出
- 検出時: stderr に警告を出し exit 2（ブロック＝続行を強制）
- それ以外: exit 0
"""

import json
import re
import sys
import os
from datetime import datetime

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stop-debug.log")
MAX_LOG_ENTRIES = 10
TAIL_CHARS = 200

# 前向きなコミットメント表現パターン
COMMITMENT_PATTERNS = [
    r"続ける",
    r"続けて",
    r"やっていく",
    r"着手する",
    r"着手します",
    r"次は.{0,20}する",
    r"次は.{0,20}します",
    r"に取り掛かる",
    r"に取り掛かります",
    r"していきます",
    r"していこう",
    r"始めます",
    r"始めましょう",
    r"進めます",
    r"進めていき",
    r"取り組みます",
    r"取り組んでいき",
    r"実行します",
    r"実装します",
    r"作成します",
    r"対応します",
]


def load_existing_log() -> list:
    """既存のログエントリを読み込む。"""
    if not os.path.exists(LOG_PATH):
        return []
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_log(entries: list) -> None:
    """ログエントリを保存する（最新 MAX_LOG_ENTRIES 件）。"""
    trimmed = entries[-MAX_LOG_ENTRIES:]
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)


def extract_text(data, depth=0) -> str:
    """
    JSON 構造から応答テキストを再帰的に探索して結合する。
    "response", "content", "text", "message" などのキーを探す。
    """
    if depth > 10:
        return ""

    if isinstance(data, str):
        return data

    if isinstance(data, list):
        parts = []
        for item in data:
            parts.append(extract_text(item, depth + 1))
        return "\n".join(p for p in parts if p)

    if isinstance(data, dict):
        # 優先的に探すキー
        priority_keys = ["response", "content", "text", "message", "body", "output"]
        parts = []
        for key in priority_keys:
            if key in data:
                result = extract_text(data[key], depth + 1)
                if result:
                    parts.append(result)
        if parts:
            return "\n".join(parts)

        # 優先キーになければ全値を探索
        for key, value in data.items():
            if key in priority_keys:
                continue
            result = extract_text(value, depth + 1)
            if result:
                parts.append(result)
        return "\n".join(parts)

    return ""


def has_tool_use(data, depth=0) -> bool:
    """JSON 構造内に tool_use / tool_call の痕跡があるか再帰的に調べる。"""
    if depth > 10:
        return False

    if isinstance(data, str):
        return False

    if isinstance(data, list):
        return any(has_tool_use(item, depth + 1) for item in data)

    if isinstance(data, dict):
        # type が tool_use / tool_call / tool_result のブロックがあるか
        t = data.get("type", "")
        if t in ("tool_use", "tool_call", "tool_result"):
            return True
        # "tool_calls" キーが存在するか
        if "tool_calls" in data:
            return True
        # 再帰
        return any(has_tool_use(v, depth + 1) for v in data.values())

    return False


def check_commitment(text: str) -> str | None:
    """末尾 TAIL_CHARS 文字にコミットメント表現が含まれていれば、該当表現を返す。"""
    tail = text[-TAIL_CHARS:] if len(text) > TAIL_CHARS else text
    for pattern in COMMITMENT_PATTERNS:
        match = re.search(pattern, tail)
        if match:
            return match.group(0)
    return None


def main():
    # stdin から読み取り
    try:
        raw = sys.stdin.read()
    except Exception:
        sys.exit(0)

    # JSON パース
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        # パース失敗 → ログに生データを保存して安全に終了
        entries = load_existing_log()
        entries.append({
            "timestamp": datetime.now().isoformat(),
            "parse_error": True,
            "raw_preview": raw[:2000] if raw else "(empty)",
        })
        save_log(entries)
        sys.exit(0)

    # ログに保存
    entries = load_existing_log()
    entries.append({
        "timestamp": datetime.now().isoformat(),
        "data": data,
    })
    save_log(entries)

    # テキスト抽出
    response_text = extract_text(data)
    if not response_text:
        sys.exit(0)

    # ツールコールの有無
    tool_used = has_tool_use(data)

    # コミットメント表現チェック
    matched = check_commitment(response_text)

    if matched and not tool_used:
        print(
            f"⚠ 行動を伴わないコミットメントを検出しました。実際に着手してください。（検出: 「{matched}」）",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
