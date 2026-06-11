---
type: entity
up: "[[index_annotated_chemopad]]"
related:
  - "[[Pt-Collapse-Classifier]]"
  - "[[Neural-Network-Drug-Classification]]"
  - "[[Neural-Network-Concentration-Prediction]]"
tags: [infrastructure, gpu, cluster, area-52, crc, ssh, sge]
---

# Compute Infrastructure: area-52 and the CRC cluster

Two compute homes for this project. **area-52** is a single GPU workstation on Notre Dame campus that owns the long-running development sessions, holds the canonical scripts and HDF5s, and is the only machine the laptop SSHes into directly. **crcfe01.crc.nd.edu** is the CRC cluster's submit node; lab GPU jobs go through `gpu@@csweet1_lab`, an SGE queue of A6000 nodes that runs the same TensorFlow stack as area-52. The cluster is reached by a second SSH hop from area-52.

The first production cluster training job was the [Pt-Collapse-Classifier](Pt-Collapse-Classifier) run on 2026-06-09; the rest of this page is the validated recipe distilled from that session.

## area-52

- **Hostname**: `area-52` resolves via Tailscale; the FQDN is `area-52.campus.nd.edu`. Prefer the short form unless DNS misbehaves (the Tailscale DNS occasionally fails to resolve the short form when the macOS DNS cache is stale; falling back to the FQDN works).
- **Auth**: SSH key (id_rsa) installed on the laptop. macOS keychain can fail to unlock the key with "User interaction is not allowed" if the Mac was just rebooted; recovery is `ssh-add --apple-load-keychain`.
- **GPUs**: two NVIDIA RTX A6000s. **GPU 0 by default for Claude sessions; GPU 1 is reserved for the other Claude session the user runs in parallel.** Set this at the top of any training script:
  ```python
  os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")  # or "1" if the user says so
  ```
  The user calls out which GPU to use explicitly when it matters; check before launching long-running training if there's any ambiguity.
- **Project root**: `~/annotated_chemopad/`. Same layout as the local checkout (see the main repo `CLAUDE.md`). HDF5 datasets at `chemo_data/`, training scripts at `neural_network/`, saved weights at `experiments/weights/`, run-time scratch at `tmp/`.
- **TensorFlow env**: project-managed venv at `~/annotated_chemopad/.venv/`; `uv` for dependency management. Activate with `source .venv/bin/activate` for ad-hoc scripts or just call `python` directly if working inside the project root with the venv hook.
- **Long-running training**: launch under `tmux` so the session survives laptop sleep / SSH drops. Convention: tmux session name = experiment name (e.g., `tmux new -s cat_effnetb3_mild_aug`). Logs to `/tmp/<experiment>.log`.

## crcfe01.crc.nd.edu (CRC submit node)

- **Hostname**: `crcfe01` (also `crcfe02`, `crcfe03` — they round-robin). FQDN `crcfe01.crc.nd.edu`. **Accessible only from on-campus / VPN networks** (and from area-52, which is on-campus). Not reachable directly from the laptop without VPN.
- **Auth is password-only by user constraint.** SSH key auth is technically possible but breaks the AFS / NetFile home directory mount: the CRC's NetFile home requires a Kerberos ticket that is only minted on password authentication. With key auth, the SSH login succeeds but the home directory comes up empty / unwritable. **Always use password authentication; do not attempt ssh-copy-id (it triggers fail2ban after a few `ssh -v` retries).**
- **SSH ControlMaster cache for crcfe01**: maintained from area-52, not from the laptop. The setup script `/tmp/setup_crcfe01_socket.sh` (idempotent, regenerable from the wiki history of this page) writes a managed block to `~/.ssh/config` on area-52 that pins password auth, no pubkey, no GSSAPI, plus `ControlMaster auto` and `ControlPersist 24h`. The user runs `ssh crcfe01` once interactively, types the password (Duo MFA may or may not prompt depending on CRC's current policy), and the resulting socket persists 24 h for any automated `ssh crcfe01 …` from area-52. **The socket survives laptop sleep and VPN drops** because it lives on area-52, which stays on campus network.
- **Socket health checks**:
  ```bash
  ssh -O check crcfe01     # "Master running" if alive
  ls ~/.ssh/cm-*           # presence of socket file
  ssh -O exit crcfe01      # explicit teardown
  ```
- **Project root on crcfe01**: `~/annotated_chemopad/`. This is **NetFile NFS** (`superior-data.crc.nd.edu:/primary_users` → `/users/csweet1/`), 100 GB quota, ~272 MB used baseline. Plenty of room for HDF5s + weights. Persistent across job runs.
- **TensorFlow on the cluster**: load via the module system, do not maintain a venv. The training scripts call CPython directly under the module's environment:
  ```bash
  module load tensorflow/2.20
  which python    # /software/t/tensorflow/2.20/bin/python — Python 3.12.12, TF 2.20.0
  ```
  The module bundles numpy 2.4.1, h5py 3.15.1. **Pandas is NOT in the module** and must be installed once into `~/.local/lib/python3.12/site-packages/` via `pip install --user pandas` (3.0.3 as of 2026-06-09).
- **Filesystem layout**:
  - `/users/csweet1/` (home, NetFile NFS) — project files, scripts, weights
  - `/scratch365` (panfs scratch) — fast read-only scratch, useful for high-throughput temp output
  - `/afs/crc.nd.edu/user/c/csweet1` (AFS) — still mounted; legacy, mostly unused
  - `/software/t/tensorflow/2.20/` — TF module install (read-only)

## The lab GPU queue: `gpu@@csweet1_lab`

- **Three A6000 nodes**: `ta-a6k-004`, `ta-a6k-005`, `ta-a6k-006`. Each node has 4 GPU cards and 24 CPU slots. Slots ≠ GPUs; an interactive `QLOGIN` session uses 1 slot but no GPU until requested.
- **Capacity check**:
  ```bash
  ssh crcfe01 'qstat -f -q gpu@@csweet1_lab'
  ```
  Output lists per-node `resv/used/tot.` slot counts. A node with 0 used is fully free. Two of three nodes (`004`, `005`) typically carry low-slot QLOGIN sessions from other lab members; node `006` is often fully free.
- **Submitting a GPU job**: SGE headers at the top of a shell script. The minimal pattern that worked for the Pt-collapse runs:
  ```bash
  #!/bin/bash
  #$ -M csweet1@nd.edu          # email on completion
  #$ -m e                       # 'e' = on end (not on abort/begin)
  #$ -pe smp 1                  # 1 CPU slot
  #$ -q gpu@@csweet1_lab        # the lab queue
  #$ -l gpu_card=1              # request 1 GPU card from this node
  #$ -N <job_name>              # qstat-visible job name
  #$ -cwd                       # run from the submission directory
  #$ -j y                       # merge stderr into stdout
  #$ -o <job_name>.log          # log file path relative to -cwd
  
  set +e                        # do NOT exit on first non-zero — we want the whole log
  
  hostname                      # always log node + identity at the top
  whoami
  date
  echo "JOB_ID=$JOB_ID"
  echo "CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"   # SGE manages this; do NOT override in the Python
  
  module purge
  module load tensorflow/2.20
  which python                  # verify the right Python
  
  python -u neural_network/<training_script>.py    # -u for unbuffered output
  python -u neural_network/<test_eval_script>.py
  ```
  Submit with `qsub <script>.sh`; SGE prints the job ID. SGE sets `CUDA_VISIBLE_DEVICES` to the allocated GPU; the Python should **not** call `os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")` like area-52 scripts do, because the cluster's allocation is dynamic.
- **Multiple jobs in parallel** land on the same physical node when it has free GPU cards. Two cards on one A6000 node showed no PCIe contention in the Pt-collapse pair (both jobs finished in 34 min, indistinguishable from solo). Three parallel jobs should be fine; four would saturate one node's PCIe bus.
- **Monitoring**:
  ```bash
  ssh crcfe01 'qstat -u csweet1'                              # all your jobs
  ssh crcfe01 'tail -50 ~/annotated_chemopad/<job>.log'       # log file
  ssh crcfe01 'qdel <job_id>'                                 # abort
  ```

## End-to-end pipeline (laptop → area-52 → crcfe01)

The validated 2026-06-09 workflow:

1. **One-time per crcfe01 home dir**: `pip install --user pandas` (TF module lacks it).
2. **Sync project**: from laptop, the indirect rsync via area-52 is the cleanest path (laptop is not on campus VPN; area-52 is):
   ```bash
   ssh area-52 'rsync -avz --info=progress2 \
       ~/annotated_chemopad/chemo_data/pad_dataset_chemo_categorical_v3.h5 \
       ~/annotated_chemopad/neural_network \
       ~/annotated_chemopad/scripts \
       crcfe01:annotated_chemopad/'
   ```
   At campus LAN speeds: ~25 MB/s, the 790 MB HDF5 + script tree completes in ~30 s. **Specifying a file as an rsync source flattens it to the destination root**; if the HDF5 is given by full path, it ends up as `annotated_chemopad/pad_dataset_chemo_categorical_v3.h5` on the remote, not in `chemo_data/`. After the rsync, move it into place: `ssh area-52 'ssh crcfe01 "mkdir -p annotated_chemopad/{chemo_data,data/models,experiments/weights,tmp} && mv annotated_chemopad/pad_dataset_chemo_categorical_v3.h5 annotated_chemopad/chemo_data/"'`.
3. **Write the job script** (template above), training script, test eval script, all in `neural_network/`. Stage on the laptop, then `scp` via area-52:
   ```bash
   scp /tmp/<script>.py area-52:/tmp/
   ssh area-52 'scp /tmp/<script>.py crcfe01:annotated_chemopad/neural_network/'
   ```
4. **Submit**: `ssh area-52 'ssh crcfe01 "cd annotated_chemopad && qsub <job>.sh"'`. Note the job ID.
5. **Monitor in background**: a polling watcher from the laptop that fires a completion notification:
   ```bash
   while true; do
     remaining=$(ssh area-52 "ssh crcfe01 'qstat -u csweet1 2>/dev/null'" | grep -c <job_name_prefix>)
     [ "$remaining" -eq 0 ] && break
     sleep 90
   done
   echo BOTH_JOBS_DONE
   ```
6. **Pull results**: read logs and weight files directly via the SSH chain; for one-shot reports, grep `=== Overall test accuracy` and `=== Headline comparison` from the log.

## Common gotchas

- **macOS SSH agent failure**: `Permission denied (publickey)` on area-52 after a Mac reboot — fix with `ssh-add --apple-load-keychain` to unlock the keychain-stored passphrase.
- **Tailscale DNS occasionally drops `area-52` short-form**: fall back to `area-52.campus.nd.edu` until DNS reconverges (typically resolves itself within a few minutes).
- **fail2ban on crcfe01**: ssh-copy-id and verbose-mode (`ssh -v`) attempts trigger fail2ban after ~3 attempts and lock out the source IP for 10 minutes. **Never run ssh-copy-id at crcfe01.** Password ControlMaster is the documented path.
- **Duo prompts** may or may not appear on the interactive `ssh crcfe01` socket startup, depending on CRC's policy that day. If a Duo prompt appears, tap "Approve" on the phone; the password+Duo combination feeds the Kerberos ticket the AFS/NetFile mount needs.
- **`CUDA_VISIBLE_DEVICES=`** in SGE job logs is **not a bug**. SGE sets it to the allocated GPU index after the shell environment is established; TensorFlow picks it up on import. Do not override.
- **`val_accuracy` in the chemo_cat_effnetb3 family**: see [Pt-Collapse-Classifier § val_accuracy / ModelCheckpoint bug](Pt-Collapse-Classifier#val_accuracy-modelcheckpoint-bug). Pre-fix scripts silently save last-epoch weights; the Pt-collapse + canonical mild-aug scripts now carry the explicit metric tracker fix.

## See also

- [Pt-Collapse-Classifier](Pt-Collapse-Classifier) — first production cluster training using this pipeline.
- [Neural-Network-Drug-Classification](Neural-Network-Drug-Classification) — pre-cluster baseline that ran on area-52 alone.
- [Neural-Network-Concentration-Prediction](Neural-Network-Concentration-Prediction) — ResNet50 concentration runs, area-52 GPU 0.
