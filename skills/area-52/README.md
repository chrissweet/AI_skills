# /area-52 — Campus GPU Workstation Operator

A Claude Code skill that wraps the conventions for driving a campus-hardwired Linux GPU workstation named `area-52` (csweet1's host: 2 × NVIDIA RTX A6000, 48 GB each, reached via Tailscale). Use it when running training jobs, building large derived datasets, transferring files to/from a compute host, or as the jump-host hub for the `/crc` skill.

## Install

```bash
# from the AI_skills repo root:
bash scripts/install-skills.sh
```

The skill becomes invocable as `/area-52` from any Claude Code session.

## Quickstart

Example prompts that would invoke this skill:

- "Launch the training script on area-52 in a tmux session and stream the log."
  Skill handles `python -u` + `tee`, kill-then-create tmux idiom, Monitor regex covering progress + failure signatures.
- "Build the merged HDF5 on area-52 then pull just the first 100 rows back."
  Skill enforces the "build derived data on the campus host, not on the Starlink laptop" convention.
- "Check what's running on the GPUs."
  Skill knows about `nvidia-smi --query-gpu=…` and the GPU 0 / GPU 1 concurrent-session convention.

## What it knows

- **Tailscale Magic DNS short-name preference** — use `area-52`, with FQDN `area-52.campus.nd.edu` as documented fallback when DNS misbehaves.
- **macOS keychain recovery** — after Mac reboot, `ssh-add --apple-load-keychain` re-primes the agent.
- **GPU 0 / GPU 1 convention** — csweet1 runs two parallel Claude sessions; GPU 0 is the default for the current session, GPU 1 is reserved for the other.
- **`python -u` + `tee` for live logs** — without `-u`, output is line-buffered through `tee` and the log stays empty for minutes.
- **Kill-then-create tmux idiom** — every long-running launch starts with `tmux kill-session -t <name> 2>/dev/null` so re-running the script doesn't pile up sessions.
- **Monitor `grep --line-buffered` pattern** — required for live log watching; the regex must cover failure signatures, not just progress, because silence is not success.
- **ControlMaster to crcfe01 lives here** — this host is the dependency root for the `/crc` skill.
- **Starlink-laptop reminder** — large derived datasets (HDF5, dumps, big rsync) belong on the compute host, not on the bandwidth-limited laptop.

## Source / details

- **Skill body (LLM-facing)**: [`SKILL.md`](SKILL.md) in this directory — what Claude Code loads.
- **Wiki synthesis (human-facing)**: [Skill-area-52](https://github.com/chrissweet/AI_skills/wiki/Skill-area-52) — why each pattern is there + verification notes.

## Parameterization

Reads `$NETID` from the shell env for paths like `/home/$NETID/<project>/`. csweet1's defaults documented in `SKILL.md`. For other users, substitute their own NetID.
