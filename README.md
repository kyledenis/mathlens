# MathLens

**Verify, then visualize. Learn math you can trust.**

MathLens is a terminal-first tool that takes a mathematical question, verifies it
formally with Lean 4 and Mathlib, and renders an animated explanation using Manim.
Every visualization carries a verification badge so you always know what has been
proved and what has not.

---

## Quick start

```bash
pip install mathlens
mathlens doctor                                 # check dependencies
mathlens explore "Pythagorean theorem"          # verify and visualize
```

---

## Commands

| Command | Description |
|---|---|
| `explore <query>` | Plan, verify, visualize, and summarize a math topic (medium quality). |
| `deep <query>` | Same pipeline at production quality with a longer verification timeout. |
| `prove <statement>` | Verify a single mathematical statement with Lean 4. |
| `viz <description>` | Visualize a math description without running verification. |
| `vis <description>` | Alias for `viz` (British/Australian spelling). |
| `history` | List past explorations stored in the workspace. |
| `search <query>` | Full-text search across past explorations. |
| `show <topic>` | Display details and artifacts for a past exploration. |
| `config show` | Print current configuration as a table. |
| `doctor` | Check that required and optional dependencies are present. |

### Common flags

```
--provider, -p     LLM provider: api, cli, or local
--model, -m        Model name override
--local            Shorthand for --provider local
--format, -f       Output format: video, frames, or diagram
--quality, -q      Render quality: low, medium, high, production
--no-verify        Skip formal verification
--no-open          Do not open the output file when done
--quiet            Suppress non-essential output
--json             Output result as JSON (explore only)
```

---

## How it works

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

## Verification badges

Every output is tagged with one of four badges.

| Badge | Meaning |
|---|---|
| `✓ Verified` | All theorem statements were accepted by Lean 4. |
| `⚠ Unverified` | Lean could not construct a proof but found no counter-example. |
| `✗ Refuted` | Lean found a counter-example or a logical error. The pipeline halts. |
| `○ Not checked` | Verification was skipped (e.g. `--no-verify` or `viz` command). |

When a result is **Refuted** the visualization is suppressed and the failure reason
is printed. You can still produce a visualization without verification using `viz`.

---

## Configuration

The config file lives at `~/.config/mathlens/config.toml` and is created with
defaults on first use.

```bash
mathlens config show                            # print all settings
mathlens config set provider.default api        # change a value
mathlens config diff                            # show what differs from defaults
mathlens config profile personal                # apply a named profile
mathlens config edit                            # open in $EDITOR
```

### Settings reference

| Key | Default | Description |
|---|---|---|
| `provider.default` | `api` | Active LLM provider. |
| `provider.fallback_chain` | `["api", "cli", "local"]` | Ordered fallback list. |
| `provider.cli.backend` | `claude-code` | Backend used by the `cli` provider. |
| `provider.api.model` | `claude-sonnet-4-6` | Model used by the `api` provider. |
| `provider.local.model` | `qwen3:32b` | Model used by the `local` provider. |
| `provider.local.endpoint` | `http://localhost:11434` | Ollama endpoint. |
| `render.default_quality` | `medium` | Quality for `explore`. |
| `render.deep_quality` | `production` | Quality for `deep`. |
| `render.default_format` | `video` | Output format when none is specified. |
| `verification.always_attempt` | `true` | Attempt verification even without Lean. |
| `verification.allow_unverified_viz` | `true` | Render even if unverified. |
| `verification.explore_timeout` | `60` | Lean timeout in seconds for `explore`. |
| `verification.deep_timeout` | `300` | Lean timeout in seconds for `deep`. |
| `workspace.path` | `~/.local/share/mathlens/explorations` | Exploration storage. |
| `ui.theme` | `auto` | Terminal color theme. |
| `ui.open_video_on_complete` | `true` | Open video after render. |

### Profiles

Profiles apply a preset group of settings in one command.

| Profile | What it sets | Use case |
|---|---|---|
| `personal` | `provider.default = cli`, fallback chain starts with `cli` | Local development with Claude Code CLI subscription — no API key needed. |
| `publish` | `provider.default = api`, fallback chain starts with `api` | Reproducible output for sharing or publication. |

```bash
mathlens config profile personal
mathlens config profile publish
```

---

## LLM providers

| Provider key | Requires | Notes |
|---|---|---|
| `cli` | Claude Code CLI installed and authenticated | Uses a Claude Code CLI subprocess. Free under a subscription, no separate API key. |
| `api` | `ANTHROPIC_API_KEY` environment variable | Direct Anthropic API access. Default model: `claude-sonnet-4-6`. |
| `local` | Ollama running locally | Talks to Ollama at the configured endpoint. Default model: `qwen3:32b`. |

Set `ANTHROPIC_API_KEY` in your shell profile when using the `api` provider:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Dependencies

### Required

| Dependency | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Runtime. |
| Manim CE | 0.18+ | Animation rendering. |
| ffmpeg | any | Video encoding used by Manim. |

### For formal verification (optional but recommended)

| Dependency | Notes |
|---|---|
| Lean 4 | Install via `elan`: `curl https://elan.lean-lang.org/elan-init.sh -sSf \| sh` |
| Mathlib | Fetched automatically by the Lean project inside the workspace. |

Without Lean, verification is skipped and all outputs receive the `○ Not checked`
badge.

### For LLM access (at least one required)

| Option | Notes |
|---|---|
| Claude Code CLI | `npm install -g @anthropic-ai/claude-code` |
| Anthropic API key | Set `ANTHROPIC_API_KEY`. |
| Ollama | `brew install ollama` or https://ollama.com |

Run `mathlens doctor` at any time to see the status of all dependencies.

---

## License

MIT
