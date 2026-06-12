# /crc-llm — CRC Open WebUI LLM API Operator

A Claude Code skill for calling Notre Dame's CRC-hosted Open WebUI LLM service via the OpenAI-compatible HTTP API at `https://openwebui.crc.nd.edu`. Free to NetID holders, ~25 models including `qwen3.5:122b`, `qwen3-vl:30b` (vision), `qwen2.5-coder:32b`, embedding models, and a structured-extraction model. Use for chat, code review, image captioning, RAG over documents, or embeddings — anywhere you'd otherwise burn paid API credits.

This is NOT for training. For training, see [/crc](../crc/) (batch SGE) or [/area-52](../area-52/) (interactive).

## Install

```bash
# from the AI_skills repo root:
bash scripts/install-skills.sh
```

The skill becomes invocable as `/crc-llm` from any Claude Code session.

**One-time API key setup** (browser required):

1. Visit <https://openwebui.crc.nd.edu/> (campus or VPN, NetID Google login).
2. Settings → Account → API Keys → generate a key (`sk-...`).
3. Save to your shell env:

```bash
echo 'export MY_OPEN_WEBUI_API_KEY="sk-..."' >> ~/.zshenv
source ~/.zshenv
```

Never paste the key into chat transcripts or commit it to a git repo.

## Quickstart

Example prompts that would invoke this skill:

- "Summarize this 5-page wiki page through the CRC LLM, using a free local model."
  Skill routes to `qwen3:32b` or `qwen3.5:35b`, returns the summary.
- "Caption these PAD card images with the CRC vision model."
  Skill batches over `qwen3-vl:30b` or `qwen2.5vl:72b` via the multi-content message format.
- "Generate embeddings for the wiki markdown files so I can do RAG locally."
  Skill calls `qwen3-embedding:8b`, returns a numpy-shaped array.
- "Upload this PDF and then have the CRC LLM answer questions about it."
  Skill `POST`s to `/api/v1/files/`, gets a `file_id`, attaches it to chat messages.

## Canonical curl recipe

The most common pitfall is shell-wrapping breaking inline `-d '{json}'` calls. Use a heredoc-built payload and a temp script:

```bash
cat > /tmp/owui_chat.sh <<'OUTER'
#!/bin/bash
set -e
PAYLOAD=$(cat <<EOF
{
  "model": "qwen3:32b",
  "messages": [{"role": "user", "content": "Explain SupCon loss in one paragraph."}],
  "stream": false
}
EOF
)
curl -sS -X POST https://openwebui.crc.nd.edu/api/v1/chat/completions \
  -H "Authorization: Bearer $MY_OPEN_WEBUI_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'])"
OUTER
bash /tmp/owui_chat.sh
```

## What it knows

- **OpenAI-compatible schema** — any OpenAI SDK targets the service by pointing `base_url=https://openwebui.crc.nd.edu/api/v1`. Verified empirically.
- **Cold-load tax on first request per model** — `granite4:micro` cold-load: 36 s. Warm eval: 6 ms. Big models like `qwen3.5:122b` take far longer to cold-load. Don't conclude the service is broken because the first call takes 30-60 s.
- **Rate limits** — 6/min and 60/hr weekdays per account; uncapped on weekends. Schedule heavy bench work for weekends.
- **Live model catalog drifts** — re-list with `GET /api/models` at session start; don't hardcode model names beyond a fallback chain.
- **File upload + RAG** — `POST /api/v1/files/` returns a `file_id`; subsequent chat calls reference via `files: [{type: file, id: ...}]`. Embeddings are computed on upload.
- **Network access** — campus or VPN only. [/area-52](../area-52/) is campus-hardwired and can hit it from automated contexts; the laptop needs VPN off-campus.

## Source / details

- **Skill body (LLM-facing)**: [`SKILL.md`](SKILL.md) in this directory — what Claude Code loads.
- **Wiki synthesis (human-facing)**: [Skill-crc-llm](https://github.com/chrissweet/AI_skills/wiki/Skill-crc-llm).
- **Official CRC docs**: <https://docs.crc.nd.edu/resources/crcowui.html>.

## Parameterization

Reads `$MY_OPEN_WEBUI_API_KEY` from the shell env. No other parameters.
