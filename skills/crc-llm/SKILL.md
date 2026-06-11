---
name: crc-llm
description: Call the Notre Dame CRC-hosted Open WebUI LLM service (`openwebui.crc.nd.edu`) for chat completion, vision, embeddings, and RAG. OpenAI-compatible HTTP API, zero cost, large model catalog including qwen3.5:122b, qwen3-vl:30b, qwen2.5-coder:32b. Use when running LLM inference (not training), captioning images, doing RAG over documents, or generating code/text without burning external API credits. Distinct from `/crc` (batch training via qsub) — this is HTTP, not ssh.
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(curl *openwebui.crc.nd.edu*)
  - Bash(bash /tmp/*)
  - Bash(python3 *)
---

# Skill: CRC Open WebUI LLM Operator

Call Notre Dame's CRC-hosted Open WebUI service for LLM inference. The service runs Ollama under the hood with an OpenAI-compatible API in front. Free to NetID holders, no compute budget, just rate-limited.

Source of truth: <https://docs.crc.nd.edu/resources/crcowui.html>.

## Mental model

- **HTTP API, not ssh.** Unlike `/crc` (batch training via qsub) or `/area-52` (interactive ssh), this skill is plain `curl` against `https://openwebui.crc.nd.edu/api/v1/chat/completions`. No ControlMaster needed, no Duo, no SGE.
- **OpenAI-compatible.** The request body is `{model, messages, ...}` and the response is `{choices: [{message: {role, content}}], usage, ...}` — same as OpenAI's chat completions. Any OpenAI-shaped client library can hit it by setting `base_url=https://openwebui.crc.nd.edu/api/v1`.
- **Cold-load tax on first request per model.** Each model loads on demand. Empirical: first call to `granite4:micro` took 42 s wall clock (`load_duration` 36 s, `eval_duration` 6 ms). Subsequent calls while the model is still hot are ~300 tok/s. Big models (qwen3.5:122b) take much longer to cold-load. Plan accordingly.
- **Campus or VPN only.** Service is internal. Off-campus needs VPN. The `/area-52` workstation is campus-hardwired and can reach this from automated contexts.
- **Rate-limited.** 6 calls/min, 60/hr weekdays. Unlimited Sat/Sun.
- **Models are NOT guaranteed stable.** The model list shifts as the CRC admins add/remove. Always `module avail`-equivalent (`/api/models` listing) at the start of a session rather than hardcoding model names.

## Authentication

One-time setup (human step, browser required):

1. Visit <https://openwebui.crc.nd.edu/> (campus/VPN, Notre Dame Google login).
2. Settings → Account → API Keys → generate a key (`sk-...`).
3. Save in shell env, e.g.:
   ```bash
   echo 'export MY_OPEN_WEBUI_API_KEY="sk-..."' >> ~/.zshenv
   source ~/.zshenv
   ```

Every API call passes `Authorization: Bearer $MY_OPEN_WEBUI_API_KEY` as a header. Treat the key like any other secret — never paste it into chat transcripts, commit messages, or files in a tracked git repo.

If a key leaks, regenerate it in the same Settings → Account UI and revoke the old one.

## Available models (as of testing)

Pull the live list at session start; do not hardcode beyond a fallback default:

```bash
curl -sS -H "Authorization: Bearer $MY_OPEN_WEBUI_API_KEY" \
  https://openwebui.crc.nd.edu/api/models | jq -r '.data[].id'
```

(or `| python3 -c "import json,sys; [print(m['id']) for m in json.load(sys.stdin)['data']]"` if jq is absent.)

Categories observed in this account:

| Use case | Model IDs |
|---|---|
| Big-context general | `qwen3.5:122b`, `qwen3.6:35b`, `qwen3.6:27b`, `qwen3.5:35b` |
| Mid general | `qwen3:32b`, `qwen3:30b-a3b`, `qwen3.5:9b`, `gemma4:31b`, `wizardlm2:latest`, `llama4:scout` |
| Small/fast | `granite4:micro`, `granite4:tiny-h` |
| Vision | `qwen3-vl:30b`, `qwen3-vl:latest`, `qwen2.5vl:72b`, `qwen2.5vl:32b`, `qwen2.5vl:latest`, `llama3.2-vision:90b`, `glm-ocr:latest`, `richardyoung/olmocr2:7b-q8`, `granite3.2-vision:latest`, `llava:34b`, `minicpm-v:latest`, `moondream:latest` |
| Code | `qwen2.5-coder:32b`, `starcoder2:latest`, `codellama:70b` |
| Embeddings | `qwen3-embedding:8b`, `snowflake-arctic-embed:latest` |
| Structured extraction | `sciphi/triplex:latest` (knowledge-graph triples) |
| Specialty | `gpt-oss:latest`, `phi4:latest`, `mistral-small3.2:latest` |

Defaults for new tasks: `granite4:micro` for ping-style health checks; `qwen3:32b` or `qwen3.5:35b` for general chat; `qwen2.5-coder:32b` for code; `qwen3-vl:30b` for vision; `qwen3-embedding:8b` for embeddings.

## Chat completion

The canonical pattern. **Use a heredoc-built payload and a temp script** — long single-line `curl` calls get mangled by interactive shell wrapping (escaping `-d '{...}'` inline is fragile).

```bash
cat > /tmp/owui_chat.sh <<'OUTER'
#!/bin/bash
set -e
PAYLOAD=$(cat <<EOF
{
  "model": "qwen3:32b",
  "messages": [
    {"role": "system", "content": "You are concise."},
    {"role": "user", "content": "REPLACE_ME"}
  ],
  "stream": false,
  "temperature": 0.2
}
EOF
)
curl -sS -X POST https://openwebui.crc.nd.edu/api/v1/chat/completions \
  -H "Authorization: Bearer $MY_OPEN_WEBUI_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  | python3 -c "import json,sys; r=json.load(sys.stdin); print(r['choices'][0]['message']['content'])"
OUTER
bash /tmp/owui_chat.sh
```

The response includes a useful `usage` block (`input_tokens`, `output_tokens`, `total_duration`, `load_duration`, `eval_duration`, `eval_count`, `response_token/s`). When debugging slow responses, pretty-print the full response and inspect `load_duration` — if it's > 30 s, the model was cold-loaded and the next call should be fast.

## Vision (image input)

Vision models (`qwen3-vl:*`, `qwen2.5vl:*`, `llama3.2-vision:*`) accept image content via the standard OpenAI multi-content message format. Each user message becomes a list of `{type: text}` and `{type: image_url}` items. Inline-encode the image as base64:

```bash
B64=$(base64 -i /path/to/card.jpg | tr -d '\n')
cat > /tmp/owui_vision.sh <<OUTER
#!/bin/bash
set -e
PAYLOAD=$(cat <<EOF
{
  "model": "qwen3-vl:30b",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "Describe what this PAD card shows."},
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,$B64"}}
    ]
  }],
  "stream": false
}
EOF
)
curl -sS -X POST https://openwebui.crc.nd.edu/api/v1/chat/completions \
  -H "Authorization: Bearer \$MY_OPEN_WEBUI_API_KEY" \
  -H "Content-Type: application/json" \
  -d "\$PAYLOAD" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['choices'][0]['message']['content'])"
OUTER
bash /tmp/owui_vision.sh
```

Notes:
- Base64-encoded images bloat the payload; keep images under 2-3 MB pre-encoding to avoid timeouts.
- For batch image processing, prefer the file-upload endpoint (next section) over inline base64 — it's more efficient and gives you a file_id you can reference in multiple calls.

## File upload and RAG

For documents (PDF, Word, CSV) or many images, upload once and reference by `file_id`:

```bash
curl -sS -X POST https://openwebui.crc.nd.edu/api/v1/files/ \
  -H "Authorization: Bearer $MY_OPEN_WEBUI_API_KEY" \
  -F "file=@/path/to/document.pdf"
```

Response includes a `file_id`. Then attach in a chat call by adding to the message:

```json
{"role": "user", "content": "Summarize the methods section.", "files": [{"type": "file", "id": "<file_id>"}]}
```

The service handles chunking and retrieval automatically — this IS the RAG layer.

For wiki-style RAG (markdown documents), upload the relevant `.md` files at session start and reference them by `file_id` in subsequent calls. Embeddings are computed on upload.

## Python client (OpenAI-compatible)

Any OpenAI SDK can target this service by pointing `base_url` at the proxy:

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://openwebui.crc.nd.edu/api/v1",
    api_key=os.environ["MY_OPEN_WEBUI_API_KEY"],
)

resp = client.chat.completions.create(
    model="qwen3:32b",
    messages=[{"role": "user", "content": "Explain SupCon loss in one paragraph."}],
    temperature=0.2,
)
print(resp.choices[0].message.content)
```

Same client supports streaming (`stream=True`), embeddings (`client.embeddings.create(model="qwen3-embedding:8b", input=[...])`), and vision (multi-content messages).

## Rate limits and back-off

- **Weekdays (Mon-Fri)**: 6 calls/min, 60 calls/hour.
- **Weekends (Sat-Sun)**: no limit (lifted by the CRC admins).

In an agent context, throttle to ~1 call every 10 s during weekdays. If a 429 comes back, sleep 60 s and retry (don't bombard). For heavy bench work (sweeps, dataset captioning, embedding generation) schedule for weekends if possible.

## Choosing the right model for the task

| Task | Recommended start |
|---|---|
| Quick chat / smoke test | `granite4:micro` |
| General reasoning, code review, summarisation | `qwen3:32b` or `qwen3.5:35b` |
| Hardest reasoning, longest context | `qwen3.5:122b` (slow cold-load; warm-runs are tolerable) |
| Code generation | `qwen2.5-coder:32b` or `codellama:70b` |
| Vision (drug card analysis, OCR) | `qwen3-vl:30b` (default), `qwen2.5vl:72b` (heavier), `glm-ocr:latest` (OCR-specific) |
| Embeddings for RAG | `qwen3-embedding:8b` |
| Knowledge-graph triple extraction | `sciphi/triplex:latest` |

If unsure, prototype with the small/fast option, then move to the bigger sibling once the call shape is verified.

## Common gotchas

- **Shell wrapping breaks inline `-d '{json}'` curl calls.** Always use a heredoc-built payload variable, or write the JSON to a file and use `-d @/tmp/payload.json`.
- **`load_duration` ≫ `eval_duration` on first call.** Don't conclude the service is broken because the first request takes 30-60 s. Time a second call to the same model to verify warm-path latency.
- **`stream: true` returns SSE chunks, not a single JSON.** Either set `stream: false` (default for these snippets) or handle Server-Sent Events line-by-line.
- **The model catalog drifts.** Hardcoded model names that worked last month may 404 today. Re-list at session start. Build in a fallback chain (`qwen3:32b` → `qwen3.5:35b` → `granite4:micro`).
- **No GPU control.** You don't choose which GPU runs your request, and you don't see per-request hardware. This is hosted inference; for training you still want `/crc` + SGE submission.
- **The 6/min weekday rate limit applies per-account**, not per-key. Multiple agents racing on the same key compete with each other.

## Recovery

- **401 Unauthorized:** API key is wrong or revoked. Re-check `echo $MY_OPEN_WEBUI_API_KEY` shows a `sk-...` value. If yes, generate a fresh key in the web UI.
- **404 model_not_found:** model was removed or renamed. Re-list with `/api/models` and pick a substitute from the same category.
- **429 rate limit:** sleep 60 s, retry. Schedule heavy work for weekends.
- **Long delay with no response:** likely cold-load on a big model. Wait at least 60-120 s before assuming a hang. If it does hang, the request will eventually 504; retry.
- **Connection refused:** off-campus without VPN. Check `curl -I https://openwebui.crc.nd.edu/` first.

## Related

- `/crc` skill — for batch GPU training on the SGE cluster (orthogonal use case)
- `/area-52` skill — campus-hardwired host that can reach this service without VPN
- `/colab` skill — alternative cloud GPU runtimes (for training, not chat)

## Sources

- <https://docs.crc.nd.edu/resources/crcowui.html> (the official user guide)
- Empirically verified call shapes against the live service 2026-06-11
