---
name: crc
description: Submit and monitor jobs on the Notre Dame CRC SGE/UGE cluster (`crcfe01.crc.nd.edu`). Use when running batch GPU jobs, lab-queue submissions to `gpu@@<labname>`, parameter sweeps with qsub loops, or aggregating SGE log output. Anchors on the ControlMaster-via-area-52 path because direct laptop→CRC ssh requires NetID password + Duo every time.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(ssh area-52*)
  - Bash(scp *area-52*)
  - Bash(ls *)
---

# Skill: CRC SGE Cluster Operator

Drive the Notre Dame CRC SGE/UGE cluster from automated contexts (claude-code, scripts, agents). Source of truth for the official docs: <https://docs.crc.nd.edu>.

## User configuration

This skill is parameterized by two values. Substitute at runtime — for csweet1, these resolve to:

| Placeholder | csweet1's value | What it means |
|---|---|---|
| `$NETID` | `csweet1` | Notre Dame NetID; used in `/users/$NETID/`, `qstat -u $NETID`, mail target, etc. |
| `$LAB` | `csweet1_lab` | SGE hostgroup name for the lab queue. Used as `gpu@@$LAB` for the queue and `@$LAB` for `qconf -shgrp`. |

You can either `export NETID=csweet1` and `export LAB=csweet1_lab` in your shell (so the templates below work as-is from interactive contexts) or substitute inline whenever a snippet is run. The LLM should resolve them to the correct values when authoring commands for the current user.

## Mental model (read this first)

- **CRC uses SGE/UGE (Sun/Univa Grid Engine), NOT SLURM.** The submission verb is `qsub`, monitor is `qstat`, cancel is `qdel`, queue topology is `qhost` / `qconf`. Anyone reaching for `sbatch` or `squeue` is in the wrong universe.
- **The frontend is `crcfe01.crc.nd.edu` (Linux) or `crcfe02.crc.nd.edu` (Mac).** Per the docs, Macs are supposed to use crcfe02; in practice crcfe01 works fine from both. The cluster has a shared filesystem so either frontend sees the same `/users/$NETID/` home and the same queue state.
- **Home is `/users/$NETID/`, NOT `/home/$NETID/`.** Hardcoded `/home/` paths will fail silently with empty `ls`. When scping, always use `/users/$NETID/...`.
- **Direct laptop → CRC is password+Duo every time.** SSH keys are not pre-installed on bastion or crcfe01 (verified empirically; the docs are silent on key pair setup). The only automation-friendly path is the ControlMaster persistent socket on area-52.
- **`area-52` is the jump host.** Per the `/area-52` skill, area-52 holds the ControlMaster socket for crcfe01. Once a human establishes that master interactively (`ssh crcfe01` from area-52 → password + Duo), every subsequent automated call hops through for 24 h. This skill assumes that master is alive.

## Authentication and access

**Before any qsub work**, verify the ControlMaster on area-52 is alive:

```bash
ssh area-52 'ssh -O check crcfe01'
```

Expected: `Master running (pid=NNNNN)`. If you get `Control socket "...": No such file or directory`, the master is dead and a human needs to re-mint it. Instruct the user:

> "The crcfe01 ControlMaster on area-52 has expired. Please run `ssh crcfe01` interactively from area-52 and complete the NetID password + Duo flow. Once the master is re-established it persists for 24 h. Then I can resume."

**Do not attempt to fix this from an automated context.** Duo is a human-in-the-loop step.

Once the master is up, route every CRC command through area-52:

```bash
ssh area-52 'ssh crcfe01 "<command on crc>"'   # one-shot
ssh area-52 'scp file crcfe01:/users/$NETID/path/'  # push file
```

For off-campus humans (not for this skill, but worth knowing):
- VPN-then-direct is the canonical path (skip bastion).
- `bastion.crc.nd.edu` is the fallback off-campus relay (password + Duo).
- The `/area-52` ControlMaster route works from any network the laptop can reach area-52 from (Tailscale).

## Modules system

CRC uses **Environment Modules** (the `module` command) for software discovery and loading. There is no system-wide venv; this is the supported path for any compiler, language runtime, or package outside the base OS. At login only `CRC_default` is loaded — everything else (TF, CUDA, Python, MPI, MATLAB, etc.) must be explicitly `module load`-ed.

### Discovery

```bash
ssh area-52 'ssh crcfe01 "module avail"'               # everything available
ssh area-52 'ssh crcfe01 "module avail tensorflow"'    # filter by pattern
ssh area-52 'ssh crcfe01 "module avail cuda"'
ssh area-52 'ssh crcfe01 "module avail python"'
```

Output is grouped by category — pay attention to which header a module sits under:

| Category | What lives here | Example |
|---|---|---|
| `general_software` | App-level scientific software | `tensorflow/2.20`, `matlab/R2024a` |
| `development_tools_and_libraries` | Compilers, languages, libs | `python/3.12.13(default)`, `cuda/12.1(default)`, `gcc/...` |
| `deprecated_software` | Old versions kept available | `tensorflow/2.13` |
| `restricted_software` | License-gated | (group-membership required) |
| `system_modules` | OS-level | typically auto-loaded |

The `(default)` annotation on a version means `module load python` (no version) picks it. Always pin the version explicitly in batch scripts — defaults shift over time.

### Loading and inspecting

```bash
ssh area-52 'ssh crcfe01 "module load tensorflow/2.20"'      # load specific version
ssh area-52 'ssh crcfe01 "module list"'                       # show what's loaded
ssh area-52 'ssh crcfe01 "module whatis tensorflow/2.20"'    # one-line description
ssh area-52 'ssh crcfe01 "module help tensorflow/2.20"'      # full info
ssh area-52 'ssh crcfe01 "module show tensorflow/2.20"'      # show env vars it sets (PATH, LD_LIBRARY_PATH, etc.)
ssh area-52 'ssh crcfe01 "module purge"'                      # unload everything
ssh area-52 'ssh crcfe01 "module unload tensorflow"'         # unload just one
```

`module show` is especially useful for debugging — it prints exactly which paths and env vars the module modifies. When a job fails with "command not found" or "library not found" after a `module load`, run `module show <name>` to see what it actually did.

### In batch scripts

**Always `module purge` before `module load`.** Login-shell auto-loads can leak into the batch environment in subtle ways. The canonical pattern:

```bash
module purge
module load tensorflow/2.20
```

That guarantees a clean slate.

### Private modules (rarely needed, but documented)

If you need a custom module (e.g., a self-built library):

```bash
mkdir -p ~/privatemodules/<software>
# write ~/privatemodules/<software>/<version> (the modulefile)
module use -a ~/privatemodules
# add 'module use -a ~/privatemodules' to ~/.bashrc for permanence
```

In practice, for ML work this is almost never needed — `tensorflow/2.20` plus `module load python/3.12.13` plus `pip install --user <extra>` covers most cases. If `pip install --user` is the answer, do it once interactively, then your batch jobs see the user-site packages automatically.

## Single-job submission

**Default to the lab hostgroup queue (`gpu@@$LAB`), not the general `gpu` queue.** Lab hostgroups give priority access and will preempt non-lab jobs on shared hardware — for csweet1 this is 5× A6000 across `ta-a6k-{004,005,006}` (your lab's quota will differ). The general `gpu` queue is shared with the rest of campus and contended. Only fall back to general `-q gpu` if the lab queue is full AND the wait is going to exceed your wall-clock budget.

The canonical SGE script template (adapted from `docs.crc.nd.edu/new_user/quick_start.html`, defaulted to the lab queue):

```bash
#!/bin/bash
#$ -M $NETID@nd.edu
#$ -m e                       # email on END (use abe for all)
#$ -pe smp 4                  # parallel environment + slots
#$ -q gpu@@$LAB        # lab queue (priority + preemption); use gpu@@<labname> for other users
#$ -l gpu_card=1              # GPU resource — without this you get no GPU
#$ -N <job_name>              # show name in qstat
#$ -cwd                       # run in the directory you qsub'd from
#$ -j y                       # merge stderr into stdout
#$ -o logs/job.log            # output file (relative to -cwd)

set +e

module purge
module load tensorflow/2.20   # or python/3.12, cuda/12.1, etc.

python -u train.py --args
echo "exit=$?"
```

Submit:

```bash
ssh area-52 'ssh crcfe01 "cd /users/$NETID/<project> && qsub job.sh"'
```

Expected output: `Your job <NNNNNNN> ("<job_name>") has been submitted`. Capture the job ID for later monitoring.

**Critical knobs:**

- **`-pe smp N`** sets CPU slot count. Without `-pe` you get 1 slot (default). 4 is a reasonable default for a single-GPU TF job (data loading needs a few cores).
- **`-l gpu_card=N`** is what actually allocates GPUs. Omit it and your job lands on a CPU node even if you set `-q gpu`. This is a common silent failure.
- **`-q gpu@@$LAB` is the default.** Lab hostgroups give priority access and preempt non-lab jobs running on the same hardware — your job either starts immediately on an idle slot or knocks an interloper off. `-q gpu` is the general campus queue and is contended; only use it as a fallback when the lab queue is full and the wait exceeds your time budget.
- **`-cwd` + `-o logs/path`** — `-cwd` makes the relative `-o` resolve correctly. Otherwise the log goes to `~/<jobname>.o<jobid>` which is annoying.
- **`module load tensorflow/2.20`** is the canonical TF on CRC. The package is at `/software/t/tensorflow/2.20/`. There is no venv on CRC for ML work — use modules.

## Lab hostgroup access

To enumerate which nodes are in a lab hostgroup:

```bash
ssh area-52 'ssh crcfe01 "qconf -shgrp @<labname>"'           # e.g., @$LAB
ssh area-52 'ssh crcfe01 "qhost -F gpu -h @<labname>"'       # GPU complex per node
```

A lab queue is often a meta-hostgroup containing one or more hardware-specific sub-groups. **Example for csweet1's lab** (`$LAB=csweet1_lab`): the meta-group `@csweet1_lab` contains `@csweet1_a6k`, which holds `ta-a6k-{004,005,006}.crc.nd.edu` — 3 nodes with 1+2+2 = 5 A6000 GPUs total. Use `qconf -shgrp @$LAB` to see whatever your lab's structure actually is.

Fast availability check (per the official docs):

```bash
ssh area-52 'ssh crcfe01 "free_gpus.sh @<labname>"'
```

Returns GPU slots available right now. Use this before submitting a sweep to estimate wave parallelism.

## Parameter sweep pattern

A multi-cell hyperparameter sweep is N independent jobs, each parameterized via `qsub -v VAR=val`. Template script reads env vars:

```bash
# crc_sweep_template.sh
#!/bin/bash
#$ -M $NETID@nd.edu
#$ -m e
#$ -pe smp 4
#$ -q gpu@@<labname>
#$ -l gpu_card=1
#$ -j y
#$ -cwd

# Required env vars passed via -v: ALPHA, TEMP, TAG (or whatever your script needs)
# Output log set on submission via -o

echo "node=$(hostname) job=$JOB_ID tag=$TAG params=alpha=$ALPHA temp=$TEMP"

module purge
module load tensorflow/2.20

python -u train.py --alpha "$ALPHA" --temperature "$TEMP" --tag "$TAG"
```

Submission loop (run from the project directory on crcfe01):

```bash
ssh area-52 'ssh crcfe01 "cd /users/$NETID/<project> && \
  mkdir -p sweep_logs && \
  for A in 0.3 0.5 0.7; do for T in 0.05 0.07 0.10; do \
    AS=\$(echo \$A | tr -d .); TS=\$(echo \$T | tr -d .); \
    TAG=sweep_a\${AS}_t\${TS}; \
    qsub -v ALPHA=\$A,TEMP=\$T,TAG=\$TAG -N \$TAG -o sweep_logs/\${TAG}.log crc_sweep_template.sh; \
  done; done"'
```

(Note the shell escaping: anything that should be evaluated on CRC is `\$`, anything evaluated on the laptop or area-52 is `$`.)

The user's lab queue (csweet1 example: 5 A6000s) will pick up the first 5 jobs immediately and queue the rest. Total wall-clock = (num_jobs / num_gpus) × per_job_wall_clock.

## Monitoring

The standard live-watch pattern uses `Monitor` to stream qstat + log progress every 60-120 s until all jobs finish:

```bash
ssh area-52 'ssh crcfe01 "while true; do echo \"--- \$(date +%H:%M) ---\"; \
  for f in /users/$NETID/<project>/sweep_logs/sweep_*.log; do \
    [ -f \"\$f\" ] || continue; \
    tag=\$(basename \$f .log); \
    last=\$(grep -E \"ep +[0-9]+/[0-9]+|OVERALL|margin|Traceback|Error\" \$f 2>/dev/null | tail -1); \
    [ -n \"\$last\" ] && echo \"\$tag: \$last\"; \
  done; \
  running=\$(qstat -u $NETID 2>/dev/null | grep -c \" r \"); \
  queued=\$(qstat -u $NETID 2>/dev/null | grep -c \" qw \"); \
  echo \"running=\$running queued=\$queued\"; \
  if [ \"\$running\" -eq 0 ] && [ \"\$queued\" -eq 0 ]; then \
    echo \"=== ALL JOBS DONE ===\"; break; fi; \
  sleep 120; done"'
```

Run that inside `Monitor`. Set the timeout to `(num_waves × per_job_minutes × 60 + buffer) × 1000` ms.

Other useful queries:

```bash
ssh area-52 'ssh crcfe01 "qstat -u $NETID"'                # my jobs
ssh area-52 'ssh crcfe01 "qstat -j <job_id>"'               # job detail incl. resource map (which GPU)
ssh area-52 'ssh crcfe01 "qstat -g c -q gpu@@<labname>"'    # queue load
ssh area-52 'ssh crcfe01 "qhost -h @<labname>"'             # node states
ssh area-52 'ssh crcfe01 "free_gpus.sh @<labname>"'         # available GPUs right now
```

To cancel a job: `qdel <job_id>` (singular) or `qdel -u <netid>` (everything that user owns).

## Aggregating sweep results

After all jobs finish, pull the metric lines into a CSV:

```bash
ssh area-52 'ssh crcfe01 "cd /users/$NETID/<project>/sweep_logs && \
  echo \"tag,metric1,metric2,margin\"; \
  for f in sweep_*.log; do \
    tag=\$(basename \$f .log); \
    m1=\$(grep \"metric1\" \$f | grep -oE \"[0-9]+\\.[0-9]+%\" | head -1); \
    m2=\$(grep \"metric2\" \$f | grep -oE \"[0-9]+\\.[0-9]+%\" | head -1); \
    mg=\$(grep \"margin\" \$f | grep -oE \"= [0-9-]+\\.[0-9]+\" | head -1 | tr -d \"= \"); \
    echo \"\$tag,\$m1,\$m2,\$mg\"; \
  done"' > sweep_results.csv
```

Then locally plot a heatmap with matplotlib's `imshow` to visualize the grid.

## Common gotchas

- **4-day runtime cap on the `gpu` queue.** Per the official docs. A multi-day training run risks getting killed mid-flight. Either split into checkpoints or move to a long queue (no GPUs there).
- **`-l gpu_card=N` is mandatory for GPU.** Omitting it gives you a CPU node even with `-q gpu`. Always include it.
- **No venv on CRC for ML.** Use `module load tensorflow/2.20`. Custom pip-installs go fast then break in cluster restarts; modules are the supported path.
- **`/users/$NETID` not `/home/$NETID`.** Frequent silent failure mode — empty `ls`, mysterious `No such file` later.
- **Shell quoting nesting is brutal.** When chaining `ssh area-52 'ssh crcfe01 "..."'`, escape carefully: `\$` for CRC-side eval, `\\\$` if there's a third level. Test with `echo` before running anything destructive.
- **`qsub` reports the job ID to stdout; capture it.** Otherwise you have to scrape it back from `qstat -u` which is racy.
- **The first 60-90 s of any job is TF init.** Don't panic if there's no epoch output for 2 min after the job enters `r` state.
- **Mac users supposed to use crcfe02 per docs.** In practice crcfe01 works from Mac; ignore the official guidance unless you hit a problem.

## Recovery

- **"Master running" check fails:** ControlMaster expired. Human must re-mint via interactive `ssh crcfe01` from area-52 (password + Duo). See Authentication section.
- **`Your job is rejected. ... no requestable resource available`:** the hostgroup is full. Either wait (queue), drop to general `-q gpu`, or pick a different lab hostgroup.
- **Job stuck in `qw` for hours with the queue empty:** check `qstat -j <jobid>` for `error reason`. Sometimes it's a resource impossibility (asked for `gpu_card=8` when nodes have 4). `qdel` and resubmit with valid resources.
- **Job died at epoch 0 with `module: command not found`:** the SGE script must use `#!/bin/bash` (not `sh`) AND must source the modules system; on CRC that's automatic on login shell but NOT in batch. The `module purge; module load ...` lines in the template are required, not optional.
- **Log file empty when job is clearly running:** likely `python` without `-u`; output is line-buffered and not flushing through `tee`. Re-launch with `python -u`.

## Related

- `/area-52` skill — the ControlMaster lives there; cross-system file moves go through that host.
- `/colab` skill — alternative cloud GPU when you don't need the cluster.

## Sources

- <https://docs.crc.nd.edu/new_user/connecting_to_crc.html> (login)
- <https://docs.crc.nd.edu/new_user/quick_start.html> (job script template)
- <https://docs.crc.nd.edu/resources/gpu.html> (GPU directive `-l gpu_card=N`)
- <https://docs.crc.nd.edu/infrastructure/crc_uge_env.html> (queue / parallel-env / hostgroup conventions)
- <https://docs.crc.nd.edu/popular_modules/modules.html> (Environment Modules: avail / load / list / private modules)
