# MathLens

**Verify, then visualize. Learn math you can trust.**

MathLens is a terminal-first tool that takes a mathematical question, verifies it
formally with Lean 4 and Mathlib, and renders an animated explanation using Manim.
Every visualization carries a verification badge so you always know what has been
proved and what has not.

---

## Quick Start

```bash
pip install mathlens                           # install
mathlens doctor                                # check dependencies
mathlens doctor --install                      # auto-install missing deps
mathlens config profile personal               # use Claude subscription (no API billing)
mathlens explore "why does the harmonic series diverge"
```

`mathlens doctor` detects your platform (macOS / Linux / Windows) and provides
the exact install commands for anything that is missing. `--install` attempts to
run them automatically.

---

## Commands

| Command | Description |
|---|---|
| `mathlens explore <query>` | Plan, verify, visualize, and summarize (medium quality). |
| `mathlens deep <query>` | Same pipeline at production quality. |
| `mathlens prove <statement>` | Verify a single mathematical statement with Lean 4. |
| `mathlens viz <description>` | Visualize without verification. |
| `mathlens vis <description>` | Alias for `viz` (AU/UK spelling). |
| `mathlens history` | List past explorations. |
| `mathlens search <query>` | Full-text search across past explorations. |
| `mathlens show <topic>` | View details and artifacts for a past exploration. |
| `mathlens config show` | Print current configuration. |
| `mathlens config set <key> <value>` | Change a setting. |
| `mathlens config profile <name>` | Apply a named profile. |
| `mathlens config diff` | Show what differs from defaults. |
| `mathlens doctor` | Check dependencies. |
| `mathlens doctor --install` | Auto-install missing dependencies. |
| `mathlens doctor --fix` | Repair workspace issues (stale locks, tmp files). |

### Flags

Every config value is overridable per-run. The config file sets defaults; flags
override for a single invocation.

```
--provider     LLM provider: api, cli, or local
--model        Model name override
--local        Shorthand for --provider local
--format       Output format: video, frames, or diagram
--quality      Render quality: low, medium, high, production
--no-verify    Skip formal verification
--verify-timeout  Override Lean timeout (seconds)
--no-open      Do not open the output file when done
--quiet        Minimal output
--json         Output result as JSON (explore only)
--retry        Resume from last checkpoint
--force        Ignore cache, start fresh
```

---

## How It Works

```
question
   |
   v
 plan       LLM decomposes the question into theorem statements
   |        and visualization scenes.
   v
verify      Lean 4 + Mathlib attempts a formal proof of each
   |        statement. The result sets the verification badge.
   v
visualize   Manim renders the scenes to video, frames, or a diagram.
   |
   v
summarize   LLM writes key insights and further-reading suggestions.
   |
   v
 index      The workspace is indexed for full-text search.
```

---

## Verification Badges

Every output is tagged with one of four badges.

| Badge | Meaning |
|---|---|
| `✓ Verified` | All theorem statements were accepted by Lean 4. |
| `⚠ Unverified` | Lean could not construct a proof but found no counter-example. |
| `✗ Refuted` | Lean found a counter-example or a logical error. **Visualization halted.** |
| `○ Not checked` | Verification was skipped (`--no-verify` or `viz` command). |

When a result is **Refuted** the visualization is suppressed and the failure
reason is printed. This is the core safety invariant — MathLens never shows
wrong math as a visualization.

---

## Configuration

Config lives at `~/.config/mathlens/config.toml`, created with defaults on first use.

```bash
mathlens config show                            # print all settings
mathlens config set provider.default cli        # change a value
mathlens config diff                            # show what differs from defaults
mathlens config profile personal                # apply a named profile
mathlens config edit                            # open in $EDITOR
mathlens config reset                           # restore defaults
```

### Settings Reference

| Key | Default | Description |
|---|---|---|
| `provider.default` | `api` | Active LLM provider. |
| `provider.fallback_chain` | `["api", "cli", "local"]` | Ordered fallback list. |
| `provider.cli.backend` | `claude-code` | Backend for the `cli` provider. |
| `provider.api.model` | `claude-sonnet-4-6` | Model for the `api` provider. |
| `provider.local.model` | `qwen3:32b` | Model for the `local` provider. |
| `provider.local.endpoint` | `http://localhost:11434` | Ollama endpoint. |
| `render.default_quality` | `medium` | Quality for `explore`. |
| `render.deep_quality` | `production` | Quality for `deep`. |
| `render.default_format` | `video` | Output format when none is specified. |
| `verification.explore_timeout` | `60` | Lean timeout in seconds for `explore`. |
| `verification.deep_timeout` | `300` | Lean timeout in seconds for `deep`. |
| `workspace.path` | `~/.local/share/mathlens/explorations` | Exploration storage. |

### Profiles

| Profile | What it sets | Use case |
|---|---|---|
| `personal` | `provider.default = cli`, fallback starts with `cli` | Use Claude Code subscription -- no API key needed. |
| `publish` | `provider.default = api`, fallback starts with `api` | Stable API access for sharing or publication. |

---

## LLM Providers

| Provider | Cost | Quality | Setup |
|---|---|---|---|
| `cli` | Subscription | High | Claude Code CLI installed (`npm i -g @anthropic-ai/claude-code`) |
| `api` | Per-token | High | `ANTHROPIC_API_KEY` environment variable |
| `local` | Free | Medium | Ollama running locally with a model pulled |

---

## Dependencies

### Required

| Dependency | Version | Install |
|---|---|---|
| Python | 3.11+ | System package manager or pyenv |
| Manim CE | 0.18+ | `pip install manim` |
| ffmpeg | any | macOS: `brew install ffmpeg` / Linux: `apt install ffmpeg` / Windows: `winget install ffmpeg` |

### For Formal Verification (optional, recommended)

| Dependency | Install |
|---|---|
| Lean 4 (via elan) | macOS/Linux: `curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \| sh` / Windows: `winget install leanprover.elan` |
| Mathlib | Fetched automatically by the Lean project. |

Without Lean, verification is skipped and all outputs receive the `○ Not checked` badge.

### For Math Typesetting (optional)

| Dependency | Install |
|---|---|
| LaTeX | macOS: `brew install --cask basictex` / Linux: `apt install texlive-base` / Windows: `winget install MiKTeX.MiKTeX` |

### For LLM Access (at least one required)

| Provider | Install |
|---|---|
| Claude Code CLI | `npm install -g @anthropic-ai/claude-code` |
| Anthropic API | Set `ANTHROPIC_API_KEY` in your shell profile |
| Ollama | macOS: `brew install ollama` / Linux: `curl -fsSL https://ollama.com/install.sh \| sh` / Windows: `winget install Ollama.Ollama` |

Run `mathlens doctor` at any time to check the status of all dependencies.
Run `mathlens doctor --install` to attempt automatic installation of anything missing.

---

## License

MIT
