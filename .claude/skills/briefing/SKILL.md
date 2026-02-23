---
name: briefing
description: セッションブリーフィングを手動生成する（hookが動かない時のフォールバック）
---

# /briefing — ブリーフィング生成

通常は SessionStart hook で自動実行されるが、hookが動かない場合や手動でブリーフィングを再生成したい場合に使う。

## 現在のブリーフィング

!`python3 tools/briefing.py 2>&1 | head -200`

上記のブリーフィングを踏まえて状況を把握し、次にやることを判断する。
