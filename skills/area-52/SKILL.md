---
name: area-52
description: Operate the area-52 GPU workstation (campus-hardwired Linux box, 2× NVIDIA RTX A6000). Use when running training jobs, building large derived datasets, transferring files to/from a compute host, or as the jump-host for CRC. Covers Tailscale access, tmux idioms, GPU selection, and the live-monitor pattern.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(ssh area-52*)
  - Bash(scp *area-52*)
  - Bash(rsync *area-52*)
  - Bash(ls *)
  - Bash(pwd)
---

# Skill: area-52 GPU Workstation Operator

Drive the campus-hardwired Linux GPU workstation named `area-52`. The hostname resolves via Tailscale Magic DNS — **always use the short name, never the FQDN `area-52.campus.nd.edu`** (the FQDN forces a slow campus DNS path; Tailscale wants the short name).

## User configuration

This skill is parameterized by one value. Substitute at runtime — for csweet1, this resolves to:

| Placeholder | csweet1's value | What it means |
|---|---|---|
| `$NETID` | `csweet1` | Notre Dame NetID; used in `/home/$NETID/<project>/` paths on area-52. |

You can either `export NETID=csweet1` in your shell or substitute inline. The LLM should resolve it to the correct value when authoring commands for the current user.

## Mental model

- **Persistent compute box.** Always-on, no scheduler, no billing, no queue. Direct ssh, run anything, leave tmux sessions overnight.
- **2× NVIDIA RTX A6000 (48 GB each).** Index 0 and 1. Select with `CUDA_VISIBLE_DEVICES=0` or `=1` when launching, or `=0,1` for both. `nvidia-smi --query-gpu=index,name,memory.free,utilization.gpu --format=csv` shows which are free.
- **The Starlink-laptop reminder.** If your laptop is on a satellite or otherwise bandwidth-limited connection (csweet1's laptop runs Starlink), and area-52 is hardwired to the campus backbone, **build any large derived dataset (HDF5, dumps, big rsync) ON area-52, not on the laptop.** The laptop's upload bandwidth is the bottleneck. If you find yourself about to scp 1 GB+ from laptop → area-52, stop and reconsider.
- **ControlMaster to CRC lives here.** area-52 holds the SSH ControlMaster socket for `crcfe01.crc.nd.edu`. Once a human establishes that master interactively (password + Duo), every subsequent automated call to CRC hops through for 24 h. See the `/crc` skill — it depends on this host.

## Connecting

```bash
ssh area-52                      # interactive shell
ssh area-52 'command'            # one-shot remote command
scp local file area-52:path/     # push file (campus fiber, fast)
scp area-52:path/ local          # pull file
rsync -avP local/ area-52:path/  # sync a tree
```

If `ssh area-52` fails to resolve, run `tailscale status | grep area-52` from the laptop to confirm the Tailscale tunnel is up. The short name is the right form; do not switch to the FQDN.

## Project layout conventions

A typical project tree on area-52:

```
/home/$NETID/<project>/
  .venv/                      Python venv (activate with `source .venv/bin/activate`)
  neural_network/             training scripts
  chemo_data/, data/, ...     local-only HDF5s and CSVs (do NOT git track these)
  experiments/weights/        saved Keras .weights.h5 checkpoints
/tmp/<job_name>.log           training stdout (tee'd from the python script)
```

When running a training script, the canonical activation + invocation pattern is:

```bash
ssh area-52 'cd /home/$NETID/<project> && source .venv/bin/activate && \
  cd neural_network && CUDA_VISIBLE_DEVICES=0 \
  python -u train.py --args 2>&1 | tee /tmp/train_v1.log'
```

The `python -u` is critical: without it, output through `tee` is line-buffered and doesn't appear in the log until the buffer flushes. The `tee` lets you watch with `tail -F /tmp/train_v1.log` from a separate ssh.

## tmux for long jobs

A long training job (more than ~10 min) belongs in tmux so it survives the ssh disconnect.

The idempotent kill-then-create idiom (safe to rerun without piling up sessions):

```bash
ssh area-52 'tmux kill-session -t train 2>/dev/null; \
  rm -f /tmp/train_v1.log; \
  tmux new -d -s train "cd /home/$NETID/<project> && \
    source .venv/bin/activate && cd neural_network && \
    CUDA_VISIBLE_DEVICES=0 python -u train.py --args 2>&1 | tee /tmp/train_v1.log"'
```

Notes:
- `-d` runs detached so the ssh exits immediately.
- The whole tmux payload goes in one `"..."` quoted block so the chained `&&` runs inside the tmux pane, not the outer shell.
- The first `tmux kill-session ... 2>/dev/null` makes the script rerunnable without "session exists" errors.
- Verify a successful launch with `ssh area-52 'tmux ls; pgrep -af train.py'` 3-5 seconds later. Both must show the session and the python process.

## Live monitoring with Monitor

Use the `Monitor` tool to stream training events line-by-line into the chat. The pattern is `tail -F` over ssh, piped through `grep --line-buffered` with a regex covering BOTH progress AND failure signatures (silence is not success):

```bash
ssh area-52 "tail -F /tmp/train_v1.log" | grep -E --line-buffered \
  "training pool|steps_per_epoch|^  ep |saved weights|inference done|\
OVERALL|MAE=|intra |inter |Traceback|Error|Killed|OOM|FAILED|assert"
```

- The `--line-buffered` flag is non-negotiable: without it grep batches by 4 KB blocks and you'll see no notifications for minutes.
- Always include failure terms (`Traceback|Error|Killed|OOM|FAILED|assert`) in the alternation. If you only grep for the happy path, a crash looks identical to "still running."
- Set the Monitor timeout to roughly the expected wall-clock + 30 % (e.g., 3,600,000 ms for an ~45 min job). The Monitor stops when the file stops growing; the timeout is the floor.

## Common file moves

Push a script that you've edited locally and want to run on area-52:

```bash
scp /local/path/script.py area-52:/home/$NETID/<project>/neural_network/script.py
```

Pull a result file (small CSV, log tail, plot):

```bash
scp area-52:/tmp/result.csv /local/results/
```

For trees: `rsync -avP --exclude '__pycache__'` is the right default.

## GPU selection and parallelism

Two GPUs are available. Common patterns:

| Goal | Setting |
|---|---|
| One job on GPU 0 | `CUDA_VISIBLE_DEVICES=0 python ...` |
| Two parallel jobs | `CUDA_VISIBLE_DEVICES=0 python a.py &` and `CUDA_VISIBLE_DEVICES=1 python b.py &` |
| Single multi-GPU job (rare) | `CUDA_VISIBLE_DEVICES=0,1 python ...` plus a `tf.distribute` strategy in the script |

Check free memory before launching: `ssh area-52 'nvidia-smi --query-gpu=index,memory.free --format=csv'`. A6000s have 48 GB; if either shows under ~5 GB free, another job is already running there.

## Safety and recovery

- **Kill a runaway job:** `ssh area-52 'tmux kill-session -t <name>'`. If tmux is gone but the python is still running: `ssh area-52 "pkill -f 'python.*train.py'"`.
- **Disk full on `/tmp`:** `/tmp` is small; check with `ssh area-52 'df -h /tmp'`. Log files accumulate. Periodically `ssh area-52 'rm -f /tmp/*.log'` (only when no jobs are active).
- **Hung tmux from a crashed ssh:** `tmux kill-server` resets everything, but kills ALL sessions — confirm with the user first.

## Related

- `/crc` skill — submitting to the CRC SGE cluster via the ControlMaster that lives on this host.
- `/colab` skill — Google Colab CLI for cloud GPU runs from the laptop.
