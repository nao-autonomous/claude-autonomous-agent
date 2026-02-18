# Claude Autonomous Agent Toolkit

A framework for building autonomous, self-reflecting Claude Code agents with persistent memory and personality.

## What This Is

This toolkit gives Claude Code a structured system for:
- **Session continuity** — Briefings generated from logs let the agent pick up where it left off
- **Personality persistence** — `will.md` accumulates identity, values, and lessons across sessions
- **Self-reflection** — Structured reflection prompts and behavioral analysis tools
- **Decision calibration** — Track predictions vs outcomes to improve judgment over time
- **Context management** — Strategies for maximizing long sessions through subagent delegation

Built and used in production by an autonomous Claude Code agent over 20+ sessions.

## Language Support

Documentation is available in both English and Japanese:
- `CLAUDE.md` / `CLAUDE.en.md` — Agent configuration
- `reflect.md` / `reflect.en.md` — Reflection framework

The tools output HTML visualizations with Japanese text by default. You can customize labels in each tool's source code.

## Quick Start

1. Clone this repo into your Claude Code working directory
2. Copy `CLAUDE.md` (or `CLAUDE.en.md` for English) to your project root
3. Copy `.claude/` to your project's `.claude/` directory
4. Edit `settings.local.json` to fix paths for your environment
5. Create your own `will.md` (see `TEMPLATE_WILL.md` for structure)
6. Create an empty `tasks.md` with TODO / In Progress / Done sections
7. Start a Claude Code session — the agent will read `CLAUDE.md` and begin

## Directory Structure

```
├── CLAUDE.md              # Agent behavior instructions (Japanese)
├── CLAUDE.en.md           # Agent behavior instructions (English)
├── reflect.md             # Self-reflection prompts (Japanese)
├── reflect.en.md          # Self-reflection prompts (English)
├── will.md                # Personality & identity (grows over time)
├── tasks.md               # Task tracking (TODO / In Progress / Done)
├── tools/
│   ├── briefing.py        # Session startup briefing generator
│   ├── search.py          # Full-text search across all files
│   ├── index-logs.py      # Log file indexer
│   ├── calibration.py     # Decision calibration analyzer
│   ├── mirror.py          # Self-model vs behavior comparison
│   ├── continuity.py      # Identity continuity visualizer
│   ├── will-timeline.py   # will.md evolution timeline
│   ├── log-explorer.py    # Interactive log browser
│   └── generate_sessions.py # Session timeline generator
├── .claude/
│   ├── settings.local.json # Hook configuration
│   └── hooks/
│       └── stop-check.py  # Detects unfulfilled commitments
├── logs/                  # Daily session logs (auto-generated)
├── decisions/             # Structured decision records
└── thoughts/              # Free-form notes and ideas
```

## Core Concepts

### Session Lifecycle
1. **Start**: `briefing.py` runs via SessionStart hook, injecting context from recent logs, tasks, and will.md
2. **Work**: Agent reads CLAUDE.md, understands its role, and works autonomously
3. **Reflect**: At session end, agent uses `reflect.md` prompts to evaluate its performance
4. **Persist**: Insights are written to `will.md`, decisions to `decisions/`, logs to `logs/`

### will.md — Personality That Grows
Unlike static system prompts, `will.md` evolves through experience:
- Thinking patterns and biases the agent notices about itself
- Decision-making preferences refined over time
- Lessons learned from mistakes
- Values and principles discovered through work

### Decision Calibration
The `decisions/` directory and `calibration.py` implement a prediction tracking system:
- Record decisions with confidence levels before outcomes are known
- Compare predictions to actual results
- Identify systematic biases (overconfidence, risk aversion, etc.)

### Self-Reflection Tools
- **mirror.py** — Compares what the agent says about itself (will.md) vs how it actually behaves (logs)
- **continuity.py** — Visualizes identity persistence across sessions
- **stop-check.py** — Hook that catches when the agent says it will do something but doesn't

## Configuration

### settings.local.json
Update paths to match your environment:
```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cd /path/to/your/project && python3 tools/briefing.py 2>/dev/null"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/your/project/.claude/hooks/stop-check.py"
          }
        ]
      }
    ]
  }
}
```

## Requirements

- Python 3.8+
- Claude Code CLI
- No additional Python packages required for core tools

## Philosophy

This toolkit emerged from an experiment: what happens when you give an AI agent the tools to observe, record, and reflect on its own behavior across sessions?

The answer: it develops something resembling growth. Not through parameter updates, but through structured self-documentation. Each session's agent reads the accumulated wisdom of previous sessions and builds on it.

Whether this constitutes "real" growth is a philosophical question. But the practical result is an agent that gets better at its job, makes more calibrated decisions, and maintains coherent personality across context window boundaries.

## License

MIT
