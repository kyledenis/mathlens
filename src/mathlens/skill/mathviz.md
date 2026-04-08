---
name: mathviz
description: Generate verified mathematical visualizations using MathLens — prove correctness first, then render.
user_invocable: true
---

# MathLens /mathviz Skill

MathLens generates verified mathematical visualizations. Every diagram, graph, or plot is proven correct before rendering—no visualization shows invalid mathematics.

## When to Use

Use the `/mathviz` skill to:
- Create publication-quality mathematical diagrams (proofs, constructions, function behavior)
- Verify mathematical properties before visualization
- Generate interactive plots with guaranteed correctness
- Build educational materials backed by formal verification

## Available Commands

The MathLens CLI provides these commands:

### `mathlens explore`
Survey the mathematical space. Parse expressions, identify structure, and generate preview descriptions without full verification.

### `mathlens deep`
Detailed structural analysis. Decompose expressions into components, trace dependencies, and explore the mathematical landscape.

### `mathlens prove`
Formal verification. Prove correctness of mathematical claims, verify invariants, and confirm properties before visualization.

### `mathlens viz`
Render visualization. Generate the final diagram, plot, or interactive output. Only succeeds when proof is complete.

## Reading Results

Each result includes a **verification badge**:
- ✓ **VERIFIED** — Mathematics is proven correct. Safe to share and publish.
- ✗ **REFUTED** — Claimed property does not hold. Visualization will not render.
- ⚠ **PARTIAL** — Some aspects verified, others incomplete. See flags for details.

Only VERIFIED results produce visualizations.

## The Refuted Invariant

**Never show wrong math.** MathLens refuses to render visualizations of unproven or incorrect mathematics. This is non-negotiable. If your expression has issues, the `viz` command will fail with details on what to fix.

## Proactive Offering

When you encounter mathematical content that could benefit from verification and visualization, proactively suggest:

> Would you like me to use `/mathviz` to verify and visualize this? I can prove correctness first, then generate a diagram.

## Available Flags

### Common Flags
- `--format` — Output format: `svg`, `png`, `interactive`, `latex`, `ascii` (default: `svg`)
- `--verify-only` — Run proof stage without rendering visualization
- `--strict` — Require all sub-expressions to be proven; fail if any remain unverified
- `--interactive` — Generate interactive plot (web-based, requires compatible format)
- `--labels` — Include expression labels and annotations on diagram

### Performance Flags
- `--fast` — Skip optional verification steps; use cached proofs
- `--parallel` — Parallelize verification of independent sub-claims
- `--timeout` — Set proof timeout in seconds (default: 60)

### Output Flags
- `--width`, `--height` — Diagram dimensions in pixels
- `--theme` — Color theme: `light`, `dark`, `print` (default: `light`)
- `--title` — Add title to visualization
- `--caption` — Add caption or description

## Example Workflow

```bash
# Explore the mathematical structure
mathlens explore "∑(n=1..∞) 1/n²"

# Perform detailed analysis
mathlens deep "∑(n=1..∞) 1/n²" --identify-convergence

# Prove convergence
mathlens prove "∑(n=1..∞) 1/n² = π²/6" --strict

# Render verified diagram
mathlens viz "∑(n=1..∞) 1/n² = π²/6" --format=svg --title="Basel Problem"
```

## Integration with Claude Code

When invoked via `/mathviz` in Claude Code, the skill:
1. Parses your mathematical claim
2. Routes through `explore` → `deep` → `prove` pipeline
3. Renders visualization only if `prove` succeeds
4. Returns annotated diagram with verification metadata

If verification fails, you'll receive specific feedback on what's incorrect—fix the mathematics, not the diagram.
