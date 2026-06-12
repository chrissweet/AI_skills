# /crc — Notre Dame CRC SGE Batch Operator

A Claude Code skill for submitting and monitoring batch jobs on Notre Dame's CRC SGE/UGE cluster (`crcfe01.crc.nd.edu`, not SLURM). Use it for single GPU jobs, parameter sweeps across the lab queue `gpu@@$LAB`, queue inspection, or aggregating SGE log output into a CSV / heatmap.

## Install

```bash
# from the AI_skills repo root:
bash scripts/install-skills.sh
```

The skill becomes invocable as `/crc` from any Claude Code session.

**Before the first run**, you must establish an SSH ControlMaster socket on your jump host (e.g., area-52). **This is the most common stumbling block on a fresh machine.** The recipe — the exact SSH config block, the bootstrap step, and the verification check — is documented in [`SKILL.md` → Authentication and access → One-time ControlMaster setup](SKILL.md). Plan ~5 minutes to walk through it once.

## Quickstart

Example prompts that would invoke this skill:

- "Submit `train_eff.py` to my lab queue with 4 CPU slots and 1 A6000."
  Skill writes the canonical SGE script header (`#$ -q gpu@@$LAB`, `#$ -l gpu_card=1`, `#$ -cwd`, `#$ -j y`, `#$ -o logs/...`), routes the qsub through the ControlMaster.
- "Sweep alpha in {0.3, 0.5, 0.7} times temperature in {0.05, 0.07, 0.10}, monitor until they finish, give me a CSV."
  Skill builds 9 qsub calls with `-v ALPHA=… -v TEMP=…`, sets up the qstat-watch loop via `Monitor`, greps the OVERALL/margin lines into a result CSV.
- "Show me which lab nodes are free right now."
  Skill calls `free_gpus.sh @$LAB` and `qstat -f -q gpu@@$LAB` for the per-node breakdown.

## What it knows

- **Lab hostgroup priority + preemption** — `gpu@@$LAB` is the default queue; non-lab jobs running on lab hardware are preempted when a lab job submits.
- **The Kerberos / NetFile root cause for password-only auth** — explains why SSH keys can't replace password+Duo, not just at the SSH layer but at the home-mount layer too.
- **fail2ban active on frontends + bastion** — no `ssh-copy-id`, no `ssh -v` retries; 3 fails = 10 min IP lockout.
- **Filesystem layout** — `/users` (home, NetFile NFS, 100 GB), `/scratch365` (panfs scratch, retiring 2026-06), `/afs` (legacy, retiring 2027-05). `/users/$NETID/`, NOT `/home/$NETID/`.
- **Modules system canonical pattern** — `module purge; module load tensorflow/2.20`. Always purge first; login-shell auto-loads leak into batch in subtle ways.
- **SGE sets `CUDA_VISIBLE_DEVICES` dynamically** — scripts on CRC must NOT call `os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")` the way [/area-52](../area-52/) scripts do.
- **The parameter-sweep idiom** — qsub-loop + qstat-watch (`while running > 0; sleep 120`) + grep-aggregate OVERALL/margin lines → CSV. Verified live during the contrastive-Pt-discrimination 17-cell sweep.
- **One-time setup quirks** — `pip install --user pandas` (TF module doesn't ship it); 4-day runtime cap on the `gpu` queue.

## Source / details

- **Skill body (LLM-facing)**: [`SKILL.md`](SKILL.md) in this directory — what Claude Code loads. The ControlMaster setup recipe lives here.
- **Wiki synthesis (human-facing)**: [Skill-crc](https://github.com/chrissweet/AI_skills/wiki/Skill-crc) — including the Kerberos root-cause finding that anchors the auth section.
- **Official CRC docs** cited in the skill:
  - <https://docs.crc.nd.edu/new_user/connecting_to_crc.html>
  - <https://docs.crc.nd.edu/new_user/quick_start.html>
  - <https://docs.crc.nd.edu/resources/gpu.html>
  - <https://docs.crc.nd.edu/popular_modules/modules.html>

## Parameterization

Reads `$NETID` (Notre Dame NetID) and `$LAB` (SGE hostgroup name, e.g., `csweet1_lab`) from the shell env. csweet1's defaults documented in `SKILL.md`. Substitute at runtime for other users.
