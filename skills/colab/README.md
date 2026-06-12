# /colab — Google Colab CLI Operator

A Claude Code skill for driving Google Colab runtimes from the terminal via the `colab` CLI. Provisions ephemeral CPU/GPU/TPU sessions, runs Python or shell on the VM, syncs files, captures work as notebooks. Use for one-off cloud GPU runs from the laptop (no ssh chain), notebook-style exploration shared as a `colab url` link, or quick benchmarking on specific GPU tiers (T4 / L4 / A100 / H100).

For training sweeps where parallelism matters, [/crc](../crc/) on the lab queue is usually faster (5 × A6000 in parallel vs Colab T4 sequential). This skill is for the laptop-direct one-off lane.

## Install

```bash
# from the AI_skills repo root:
bash scripts/install-skills.sh
```

The skill becomes invocable as `/colab` from any Claude Code session.

**One-time CLI install** (separate from the skill — installs the actual `colab` binary):

```bash
uv tool install google-colab-cli
# or:
pip install google-colab-cli
```

**One-time auth** (per the skill body's Authentication section):

```bash
gcloud auth application-default login \
  --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/colaboratory
```

All four scopes are required; missing the `colaboratory` scope is the most common silent failure (`colab new` unassigns the VM on a 403 keep-alive failure).

## Quickstart

Example prompts that would invoke this skill:

- "Provision a T4 and run my benchmark script on it, then stop the session."
  Skill calls `colab new -s <name> --gpu T4`, `colab exec --timeout 300 -f <script>`, `colab stop -s <name>`. The `--timeout 300` is critical because the CLI default is 10 s, which TF imports always exceed.
- "Rent an A100 for an hour and let me iterate on this notebook."
  Skill provisions, opens via `colab url --open`, and warns about 24 h keep-alive cap and billable VM.
- "Quick GPU sanity check from this laptop without the CRC ssh chain."
  Skill spins a T4, runs a benchmark, reports tokens/sec, tears down.

## What it knows

- **A session is a billable VM until `colab stop`** — idle sessions burn compute units indefinitely (24 h keep-alive cap is the only safety net). `colab run` (one-shot) self-cleans even on error.
- **Kernel state persists across `colab exec` calls** — imports, variables, and defined functions survive between invocations. Build state incrementally.
- **ADC + four scopes** — the canonical agent-friendly auth path. `colab whoami` is the one-line verifier.
- **Tier-gated accelerators** — `T4`, `L4`, `G4`, `H100`, `A100` for `--gpu`; `v5e1`, `v6e1` for `--tpu`. Availability is NOT guaranteed even on Pro. Empirically: T4 works on csweet1@nd.edu; H100/A100/L4 return 400 (entitlement-gated despite valid auth).
- **Default `exec` timeout is 10 s** — long TF imports always exceed it. Use `--timeout 300`+ for anything non-trivial.
- **Empirical T4 vs A6000 ratio** — T4 ran the EfficientNetB3 benchmark at 831 ms/step; A6000 at ~500 ms/step. T4 is ~1.7 × slower; tolerable for one-offs, not for sweeps.

## Source / details

- **Skill body (LLM-facing)**: [`SKILL.md`](SKILL.md) in this directory. **The body is the upstream Google-published skill text** from `googlecolab/google-colab-cli/COLAB_SKILL.md`, with Claude Code frontmatter added for `/colab` invocation.
- **Wiki synthesis (human-facing)**: [Skill-colab](https://github.com/chrissweet/AI_skills/wiki/Skill-colab).
- **Upstream sources**:
  - <https://github.com/googlecolab/google-colab-cli> — upstream CLI repo + canonical SKILL.md
  - <https://github.com/googlecolab/google-colab-cli/blob/main/COLAB_SKILL.md> — the file shipped here
  - <https://pypi.org/project/google-colab-cli/> — PyPI package
  - <https://developers.googleblog.com/introducing-the-google-colab-cli/> — launch announcement

## Parameterization

No NetID-style parameterization. Auth flows through Google ADC (`gcloud auth application-default login`); the user's identity is tied to their Google account, not a shell env var.
