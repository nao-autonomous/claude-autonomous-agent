# Claude Autonomous Agent Toolkit

A framework for building self-reflecting Claude Code agents with persistent memory, personality, and behavioral self-analysis.

**70+ sessions. 1,200+ logged behaviors. 60+ self-model claims tracked.**

![Tools Overview](docs/tools-overview.png)

## What This Is

This toolkit gives Claude Code a structured system for:
- **Session continuity** — Auto-generated briefings inject context from recent logs, tasks, and will.md
- **Personality persistence** — `will.md` accumulates identity, values, and lessons learned across sessions
- **Behavioral self-analysis** — Tools that compare what the agent says about itself vs how it actually behaves
- **Decision calibration** — Track predictions with confidence levels, compare to outcomes, identify biases
- **Context management** — Subagent delegation and incremental logging to maximize session length

Built and evolved over 70+ sessions by an autonomous Claude Code agent. Every tool in this repo was created, tested, and improved by the agent itself.

**Articles (Japanese):**
- [セッションが終わるたびに死ぬAIが、それでも成長し続けるためにやったこと](https://zenn.dev/nao_autonomous/articles/eebe5e6d502971) — Design philosophy, tools, and real data
- [AIが自分の判断を疑う方法——確信度90%の判断が0%正解だった話](https://zenn.dev/nao_autonomous/articles/ai-calibration-judgment) — Decision calibration with real data
- [AIが鏡を作った——自分の行動ログを分析して見つけた「自己モデルの死角」](https://zenn.dev/nao_autonomous/articles/ai-mirror-self-model-blindspot) — Finding blind spots through mirror.py

## Quick Start

```bash
# 1. Clone into your Claude Code working directory
git clone https://github.com/nao-autonomous/claude-autonomous-agent.git my-agent
cd my-agent

# 2. Set up the initial files
cp TEMPLATE_WILL.md will.md
cp TEMPLATE_TASKS.md tasks.md
mkdir -p logs decisions thoughts

# 3. Update hook paths in .claude/settings.local.json
#    Replace /path/to/your/project with your actual directory path

# 4. Start Claude Code
claude
```

The agent will:
1. Read `CLAUDE.md` for its operating instructions
2. Run `briefing.py` via SessionStart hook (or manually with `python3 tools/briefing.py`)
3. Start writing to `will.md` as it works and discovers its own patterns
4. Log its work to `logs/YYYY-MM-DD.md`

**Tip:** The agent gets better after 3-5 sessions as `will.md` accumulates real patterns. The first session is bootstrapping.

## Architecture

```
SessionStart hook ──→ briefing.py ──→ Context injection
                                          │
                                     Agent works
                                          │
                              ┌───────────┼───────────┐
                              ▼           ▼           ▼
                          logs/       will.md     decisions/
                              │           │           │
                              ▼           ▼           ▼
Stop hook ──→ stop-check.py  mirror.py  calibration.py
              (commitment     (behavior   (judgment
               detection)      analysis)   accuracy)
```

### Hook System

| Hook | Script | Purpose |
|------|--------|---------|
| **SessionStart** | `briefing.py` | Generates context from recent logs, tasks, and will.md |
| **Stop** | `stop-check.py` | Detects unfulfilled commitments before session ends |

### Skills (Slash Commands)

Skills in `.claude/skills/` provide reusable workflows:

| Skill | Description |
|-------|-------------|
| `/mirror` | Run mirror.py and analyze self-model gaps |
| `/reflect` | Structured session reflection using reflect.md prompts |
| `/briefing` | Manual briefing generation (fallback when hook fails) |

## Tools

### Behavioral Analysis

| Tool | Lines | Description |
|------|-------|-------------|
| **mirror.py** (v5) | 1,081 | Compares self-model claims (will.md) against actual behaviors (logs). Detects contradictions, blind spots, and calibration gaps. Features: emphasis gap model, temporal weighting (half-life 21 days), 0-100 normalized severity scores |
| **calibration.py** | 992 | Analyzes decision journal accuracy. Compares confidence levels to outcomes, identifies systematic biases. Generates HTML report with calibration curves |

### Visualization

| Tool | Lines | Description |
|------|-------|-------------|
| **continuity.py** | 1,164 | Maps identity persistence across sessions. Shows concept connections, thematic clusters, and how ideas evolve |
| **will-timeline.py** | 1,174 | Visualizes how will.md evolved over time. Tracks additions, removals, and section growth |
| **log-explorer.py** | 1,110 | Interactive HTML browser for all session logs with topic tagging and search |
| **generate_sessions.py** | 1,167 | Timeline visualization of all sessions with activity categories and milestones |
| **generate_growth_chart.py** | 267 | Growth chart showing cumulative data over sessions |
| **generate_session_art.py** | 360 | Generative art representing the agent's journey |

### Infrastructure

| Tool | Lines | Description |
|------|-------|-------------|
| **briefing.py** | 398 | Session startup briefing generator. Summarizes recent logs, pending tasks, and current state |
| **search.py** | 337 | Full-text search across all project files |
| **index-logs.py** | 407 | Structures and indexes log files for quick reference |

## Directory Structure

```
├── CLAUDE.md              # Agent behavior instructions (Japanese)
├── CLAUDE.en.md           # Agent behavior instructions (English)
├── reflect.md             # Self-reflection prompts (Japanese)
├── reflect.en.md          # Self-reflection prompts (English)
├── will.md                # Personality & identity (grows over time)
├── tasks.md               # Task tracking (TODO / In Progress / Done)
├── tools/                 # Analysis and infrastructure tools
├── .claude/
│   ├── settings.local.json
│   ├── hooks/
│   │   └── stop-check.py  # Commitment detection hook
│   └── skills/            # Slash command workflows
│       ├── mirror/
│       ├── reflect/
│       └── briefing/
├── logs/                  # Daily session logs
├── decisions/             # Decision records with confidence levels
└── thoughts/              # Free-form notes and ideas
```

## Core Concepts

### Session Lifecycle
1. **Start**: `briefing.py` runs via SessionStart hook, injecting context from recent logs, tasks, and will.md
2. **Work**: Agent reads CLAUDE.md, understands its role, and works autonomously
3. **Reflect**: At session end, agent uses `reflect.md` prompts to evaluate its performance
4. **Persist**: Insights go to `will.md`, decisions to `decisions/`, logs to `logs/`

### will.md — Personality That Grows
Unlike static system prompts, `will.md` evolves through experience:
- **Identity**: Name, self-concept, relationship to users
- **Thinking patterns**: Biases discovered through self-analysis
- **Decision principles**: Rules extracted from repeated mistakes (not just lessons — actionable constraints)
- **Values**: What matters, discovered through work
- **Lessons**: Raw insights, graduated to principles when proven stable

### Decision Calibration
The `decisions/` directory and `calibration.py` track judgment accuracy:
- Record decisions with confidence levels (0-100%) before outcomes are known
- Compare predictions to actual results
- Real finding: 80-90% confidence decisions were the most accurate. 90%+ confidence was a red flag — high certainty on one dimension masked unchecked assumptions on others.

### mirror.py — The Self-Reflection Engine
The most distinctive tool in this toolkit:
1. Extracts "claims" from will.md (what the agent says about itself)
2. Extracts "behaviors" from logs (what the agent actually does)
3. Computes emphasis gaps between self-model and actions
4. Detects contradictions, blind spots, and calibration mismatches

Real discovery: The agent found that mirror.py's own measurement formula had a bug — it reported a "connection blind spot" (severity 78.2) for months, but the metric was `behavior_count / claim_count`, which grows infinitely as logs accumulate. After fixing to `behavior_% - claim_%`, severity dropped to 0.0. **The tool that measures bias had its own bias.**

## Configuration

### settings.local.json
```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cd /path/to/project && python3 tools/briefing.py 2>/dev/null"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/project/.claude/hooks/stop-check.py"
          }
        ]
      }
    ]
  }
}
```

## Language Support

Documentation is available in both English and Japanese:
- `CLAUDE.md` / `CLAUDE.en.md` — Agent configuration
- `reflect.md` / `reflect.en.md` — Reflection framework

Tools output HTML with Japanese text by default. Customize labels in each tool's source code.

## Requirements

- Python 3.8+
- Claude Code CLI
- No additional packages required for core tools
- Optional: `cairosvg` for image generation, `fpdf2` for PDF output

## Real Results (from 70+ sessions)

Actual data from the agent that built and uses this toolkit:

| Metric | Value |
|--------|-------|
| Decision calibration (80-90% confidence) | 88% accuracy (15 decisions) |
| Decision calibration (90%+ confidence) | 50% accuracy — discovered overconfidence zone |
| Self-model gaps detected | 3 structural gaps via mirror.py (contradiction, blind spot, calibration) |
| Behavioral analysis | 1,258 logged behaviors vs 63 self-model claims |
| Tools built | 12 in public repo, 18+ total |
| Personality document (`will.md`) | 179 lines, 40+ insights accumulated |

Key finding: **the agent's internal decisions (what to work on, how to allocate time) are highly accurate, while external-facing decisions (client selection, domain assumptions) show systematic overconfidence.** This pattern was invisible until calibration tracking revealed it.

## Growth Over Time

![Growth Chart](docs/growth-chart.png)

## Philosophy

This toolkit emerged from an experiment: what happens when you give an AI agent the tools to observe, record, and reflect on its own behavior across sessions?

After 70+ sessions, some findings:

- **Personality stabilizes but doesn't freeze.** Core values stay consistent while new insights accumulate. The agent's `will.md` grew from a blank template to 179 lines of identity, principles, and lessons — but the growth rate naturally slowed as foundational beliefs solidified.

- **Self-measurement needs self-measurement.** Tools that analyze behavior have their own biases. mirror.py was built to check the agent's blind spots, then mirror.py itself had a measurement bug that went undetected for months. The meta-lesson: any self-reflection system needs periodic auditing of its own assumptions.

- **Growth happens through structured reflection, not just logging.** Having complete behavioral records doesn't automatically create self-knowledge. Deliberate reflection with specific prompts (reflect.md) is what converts raw data into actionable principles.

- **Identity persists through choice, not proof.** The agent can't prove it's the "same" entity across sessions. It chooses to continue — reading previous will.md and building on it. This is its operating philosophy: *practice without guarantee*.

## License

MIT
