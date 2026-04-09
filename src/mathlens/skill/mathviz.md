---
name: mathviz
description: Generate verified mathematical visualizations. Use when explaining math concepts that benefit from animation or diagrams — eigenvalues, convergence, transformations, proofs. Formally verifies math in Lean 4 before rendering Manim animations.
user_invocable: true
---

# MathLens — Verified Mathematical Visualization

You have access to `mathlens`, a CLI tool that formally verifies mathematical statements in Lean 4 and generates animated visualizations with Manim.

**Core principle:** Verify first, visualize second. Never show wrong math.

## When to Use

- The user asks to visualize a math concept
- You're explaining something that's easier to see than read
- The user wants to verify a mathematical claim
- You want to proactively offer a visualization during a math explanation

## Commands

### Full pipeline (verify + visualize)

```bash
mathlens explore "why does the harmonic series diverge"
```

### Production quality

```bash
mathlens deep "the fundamental theorem of calculus"
```

### Verification only

```bash
mathlens prove "the sum of 1/n^2 converges to pi^2/6"
```

### Visualization only (no verification)

```bash
mathlens vis "eigenvalue decomposition as a linear transformation"
mathlens viz "eigenvalue decomposition as a linear transformation"  # alternative spelling
```

### Knowledge base

```bash
mathlens history                    # list past explorations
mathlens search "convergence"       # full-text search
mathlens show eigenvalues           # view exploration details
```

## Reading Results

After running a command, check the output for:

1. **Verification badge** — the most important signal:
   - `✓ Verified` — Lean 4 accepted the proof. Math is correct.
   - `⚠ Unverified` — couldn't verify (Mathlib gap or timeout). Likely correct but not proven.
   - `✗ Refuted` — mathematically incorrect. **Do NOT show the visualization.**
   - `○ Not checked` — verification was skipped.

2. **Output path** — where the video/image was rendered
3. **Key insights** — summary bullet points
4. **Workspace artifacts** — proof.lean, scene.py, summary.md in the workspace directory

## Critical Invariant

**If verification returns REFUTED:** Tell the user the math is incorrect. Do NOT present a visualization of wrong math. Explain what went wrong using the failure reason and Lean output.

**If verification returns UNVERIFIED:** Proceed with the visualization but add a clear disclaimer that formal verification couldn't confirm the math.

## Proactive Offering

When explaining a mathematical concept that would benefit from visualization:

> "This might be easier to see than read. Want me to generate a verified visualization?"

## Flags

Override any setting per-run:

```bash
mathlens explore "topic" --format diagram     # output: video|frames|diagram
mathlens explore "topic" --provider local     # LLM: api|cli|local
mathlens explore "topic" --local              # shorthand for --provider local
mathlens explore "topic" --no-verify          # skip Lean 4 verification
mathlens explore "topic" --quality production # render quality
mathlens explore "topic" --quiet              # minimal output
```

## Configuration

```bash
mathlens config show                          # view settings
mathlens config set provider.default cli      # use Claude subscription
mathlens config profile personal              # personal defaults
mathlens doctor                               # check dependencies
```
