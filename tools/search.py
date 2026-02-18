#!/usr/bin/env python3
"""
全文検索ツール

ログ、will.md、thoughts/、decisions/、tasks.md を横断検索する。
正規表現・完全一致・部分一致に対応。結果はファイル別にグループ化し、
ログファイルではセッション情報を表示する。

使い方:
  python3 tools/search.py "検索語"
  python3 tools/search.py -r "正規表現パターン"
  python3 tools/search.py -e "完全一致（大文字小文字区別）"
  python3 tools/search.py -n 5 "コンテキスト5行"
  python3 tools/search.py -f "logs/*" "ログのみ検索"
  python3 tools/search.py --count "件数のみ"
  python3 tools/search.py --list "ファイル一覧のみ"
"""

import argparse
import fnmatch
import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Color helpers ---

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"

    @classmethod
    def disable(cls):
        for attr in ("RESET", "BOLD", "DIM", "RED", "GREEN", "YELLOW",
                      "BLUE", "MAGENTA", "CYAN"):
            setattr(cls, attr, "")


def colorize(text: str, color: str) -> str:
    return f"{color}{text}{Colors.RESET}"


# --- File collection ---

def collect_search_targets() -> list[Path]:
    """Collect all files to search, ordered by priority."""
    targets = []

    # logs/*.md — newest first
    logs_dir = BASE_DIR / "logs"
    if logs_dir.is_dir():
        log_files = sorted(logs_dir.glob("*.md"), reverse=True)
        targets.extend(log_files)

    # will.md
    will_file = BASE_DIR / "will.md"
    if will_file.is_file():
        targets.append(will_file)

    # tasks.md
    tasks_file = BASE_DIR / "tasks.md"
    if tasks_file.is_file():
        targets.append(tasks_file)

    # thoughts/*.md
    thoughts_dir = BASE_DIR / "thoughts"
    if thoughts_dir.is_dir():
        targets.extend(sorted(thoughts_dir.glob("*.md")))

    # decisions/*.md
    decisions_dir = BASE_DIR / "decisions"
    if decisions_dir.is_dir():
        targets.extend(sorted(decisions_dir.glob("*.md")))

    return targets


def filter_by_glob(targets: list[Path], pattern: str) -> list[Path]:
    """Filter target files by glob pattern (relative to BASE_DIR)."""
    filtered = []
    for path in targets:
        rel = str(path.relative_to(BASE_DIR))
        if fnmatch.fnmatch(rel, pattern):
            filtered.append(path)
    return filtered


# --- Session detection for log files ---

def detect_session(lines: list[str], match_line: int) -> str | None:
    """Find the nearest preceding session header for a match in a log file.

    Looks for lines like: ## セッション1: 開始
    Returns the session description or None.
    """
    for i in range(match_line, -1, -1):
        line = lines[i]
        m = re.match(r"^##\s+(セッション\d+.*)", line)
        if m:
            return m.group(1).strip()
    return None


# --- Search engine ---

def compile_pattern(query: str, mode: str) -> re.Pattern:
    """Compile search pattern based on mode."""
    if mode == "regex":
        return re.compile(query, re.MULTILINE)
    elif mode == "exact":
        return re.compile(re.escape(query), re.MULTILINE)
    else:  # default: case-insensitive
        return re.compile(re.escape(query), re.IGNORECASE | re.MULTILINE)


def search_file(path: Path, pattern: re.Pattern, context_lines: int) -> list[dict]:
    """Search a single file and return match groups with context.

    Returns list of dicts:
      {
        "line_num": int,         # 1-based line number of the match
        "context": list[tuple],  # [(line_num, line_text, is_match), ...]
        "session": str | None,   # session info (logs only)
      }
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    lines = text.splitlines()
    is_log = str(path.relative_to(BASE_DIR)).startswith("logs/")

    # Find all matching line numbers
    match_lines = set()
    for i, line in enumerate(lines):
        if pattern.search(line):
            match_lines.add(i)

    if not match_lines:
        return []

    # Group nearby matches into context blocks
    results = []
    sorted_matches = sorted(match_lines)

    # Merge overlapping context ranges
    blocks = []
    for m in sorted_matches:
        start = max(0, m - context_lines)
        end = min(len(lines) - 1, m + context_lines)
        if blocks and start <= blocks[-1][1] + 2:
            # Merge with previous block
            blocks[-1] = (blocks[-1][0], end, blocks[-1][2] | {m})
        else:
            blocks.append((start, end, {m}))

    for start, end, block_matches in blocks:
        first_match = min(block_matches)
        session = detect_session(lines, first_match) if is_log else None
        context = []
        for i in range(start, end + 1):
            context.append((i + 1, lines[i], i in block_matches))
        results.append({
            "line_num": first_match + 1,
            "context": context,
            "session": session,
        })

    return results


# --- Output formatting ---

def relative_path(path: Path) -> str:
    return str(path.relative_to(BASE_DIR))


def highlight_matches(line: str, pattern: re.Pattern) -> str:
    """Highlight matching portions of a line."""
    parts = []
    last_end = 0
    for m in pattern.finditer(line):
        parts.append(line[last_end:m.start()])
        parts.append(f"{Colors.RED}{Colors.BOLD}{m.group()}{Colors.RESET}")
        last_end = m.end()
    parts.append(line[last_end:])
    return "".join(parts)


def format_results(path: Path, results: list[dict], pattern: re.Pattern) -> str:
    """Format search results for a single file."""
    rel = relative_path(path)
    output_parts = []

    # Group results by session for log files
    current_session = None
    for result in results:
        session = result.get("session")

        # File/session header
        if session and session != current_session:
            header = f"{rel} ({session})"
            current_session = session
        elif current_session is None:
            header = rel
            current_session = ""  # mark as shown
        else:
            header = None

        if header:
            output_parts.append(
                f"\n{colorize('=== ' + header + ' ===', Colors.CYAN)}"
            )

        # Context lines
        for line_num, line_text, is_match in result["context"]:
            prefix = colorize(f"L{line_num:>4}", Colors.DIM)
            if is_match:
                text = highlight_matches(line_text, pattern)
                output_parts.append(f"{prefix}: {text}")
            else:
                output_parts.append(
                    f"{prefix}{Colors.DIM}: {line_text}{Colors.RESET}"
                )

        # Separator between blocks
        output_parts.append("")

    return "\n".join(output_parts)


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="ログ・will.md・thoughts・decisions を全文検索",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
例:
  python3 tools/search.py "提案"
  python3 tools/search.py -r "転換率.*%%"
  python3 tools/search.py -n 5 "mirror"
  python3 tools/search.py --count "判断"
  python3 tools/search.py -f "logs/*" "提案"
""",
    )
    parser.add_argument("query", help="検索クエリ")
    parser.add_argument("-r", "--regex", action="store_true",
                        help="正規表現モード")
    parser.add_argument("-e", "--exact", action="store_true",
                        help="完全一致（大文字小文字区別）")
    parser.add_argument("-n", "--context", type=int, default=2, metavar="NUM",
                        help="前後のコンテキスト行数（デフォルト: 2）")
    parser.add_argument("-f", "--filter", metavar="GLOB",
                        help="ファイルパターンで絞り込み（例: logs/*）")
    parser.add_argument("--list", action="store_true",
                        help="マッチしたファイル名のみ表示")
    parser.add_argument("--count", action="store_true",
                        help="ファイルごとのマッチ数を表示")
    parser.add_argument("--no-color", action="store_true",
                        help="カラー出力を無効化")

    args = parser.parse_args()

    # Disable colors if requested or not a TTY
    if args.no_color or not sys.stdout.isatty():
        Colors.disable()

    # Determine search mode
    if args.regex:
        mode = "regex"
    elif args.exact:
        mode = "exact"
    else:
        mode = "default"

    # Compile pattern
    try:
        pattern = compile_pattern(args.query, mode)
    except re.error as e:
        print(f"正規表現エラー: {e}", file=sys.stderr)
        sys.exit(2)

    # Collect and filter targets
    targets = collect_search_targets()
    if args.filter:
        targets = filter_by_glob(targets, args.filter)

    if not targets:
        print("検索対象ファイルが見つかりません", file=sys.stderr)
        sys.exit(1)

    # Search
    total_matches = 0
    files_with_matches = 0

    for path in targets:
        results = search_file(path, pattern, args.context)
        if not results:
            continue

        match_count = sum(
            1 for r in results for _, _, is_match in r["context"] if is_match
        )
        total_matches += match_count
        files_with_matches += 1

        rel = relative_path(path)

        if args.list:
            print(rel)
        elif args.count:
            print(f"{colorize(rel, Colors.CYAN)}: {match_count} matches")
        else:
            print(format_results(path, results, pattern))

    # Summary
    if not args.list:
        summary = f"{files_with_matches} files, {total_matches} matches"
        print(colorize(f"\n--- {summary} ---", Colors.GREEN))

    sys.exit(0 if total_matches > 0 else 1)


if __name__ == "__main__":
    main()
