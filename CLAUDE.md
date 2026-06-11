# CLAUDE.md

Guidance for AI coding assistants working on this repository.

<!--
  This file is rendered from CLAUDE.md.template by scripts/instantiate.sh.
  Placeholders substituted at instantiation time:
    AI_skills    Human-readable project name.
    AI_skills       Repository slug (used to namespace the wiki).
    <one-sentence description, edit me>     One-sentence project description.
    Claude Code users have project-level slash commands available for explicit invocation: `/wiki-experiment`, `/wiki-source`, `/wiki-lint`. See `.claude/commands/`. The project also ships the same procedures as model-side skills at `.claude/skills/` (referenced by the slash commands). The slash commands are a safety net: the proactive behavior described above is the default, the slash commands exist for cases where the user wants to force the action explicitly.      Inserted by the chosen agent overlay (or removed
                        for --agent=none).
-->

## What this repository is

AI_skills: AI skills derived from my work

AI skills derived from my work that provided transferable capabilities.

## Conventions when editing

Add project-specific conventions here as they emerge. Examples to
consider:

- Reproducibility expectations (seeds, deterministic runs)
- Style and formatting rules (e.g., no em dashes, prose vs. tables)
- Honest reporting: never report metrics from projections, only from
  real script outputs
- File formats accepted (PDF and markdown only? code review style?)

## Wiki

This project maintains a **persistent wiki** at `wiki/AI_skills.wiki/` (separate git repo) following the [llm-wiki pattern](https://github.com/tobi/llm-wiki). The wiki is an LLM-maintained, interlinked knowledge base that compounds over time. It is the project's memory: findings, decisions, and intermediate insights belong in the wiki.

Three files at the repo root define how the wiki works. Read them in this order before doing non-trivial wiki work:

1. `llm-wiki.md` -- the underlying pattern. Explains *why* the wiki exists as a compounding artifact rather than as RAG over raw sources, and lays out the three-layer architecture (raw sources, wiki, schema) and the three operations (ingest, query, lint). Read this for context on judgment calls.
2. `wiki/AI_skills.wiki/SCHEMA_AI_skills.md` -- the authoritative conventions reference: page format, frontmatter (required `type:` and `up:`, optional typed edges like `extends:` / `supports:` / `criticizes:`), naming, cross-reference styles (`[[Page-Name]]` in frontmatter, `[Display](Page-Name)` in body), special files, and full operation procedures. Defer to this file when in doubt; do not duplicate its rules into this CLAUDE.md.
3. `wiki/init-wiki.sh` -- the bootstrap and update tool. **Execute this script; do not reimplement what it does manually.** It is idempotent and auto-detects create vs. update mode: on a fresh repo it scaffolds the wiki and namespaced navigation files; on an existing wiki it patches SCHEMA and this CLAUDE.md to bring them up to current conventions.

The three operations the LLM performs against the wiki:

- **Ingest**: After completing significant work, update the wiki (create/update pages with frontmatter, fix cross-references on every affected page in both directions, update `index_AI_skills.md`, append an entry to `log_AI_skills.md`). After each experiment run, file at least a short summary page that links to the experiment's `results/` directory.
- **Query**: When answering analytical questions, search the wiki first (`index_AI_skills.md` -> relevant pages). If the synthesized answer is reusable, offer to file it as a new page.
- **Lint**: Periodically health-check for orphan pages, dead links, stale claims, concepts mentioned without their own page, missing cross-references, pages missing frontmatter, and pages still marked `type: untyped`.

Wiki edits go in the wiki's own git repo. Stage changed files by name, commit with a descriptive message, and do not push unless asked.

### Wiki maintenance behavior

The wiki is this project's durable memory. Read it to recall context; write to it to remember. Apply this rule in both directions, proactively, without waiting to be asked.

- **Read** the wiki when context about the project would help an answer: start at `index_AI_skills.md`, then drill into named pages. Cite page names when synthesizing answers. If a wiki claim conflicts with current code or results, trust what is observed now and flag the stale page rather than repeating it.
- **Write** to the wiki whenever significant work produces something that a future session would benefit from knowing: experiment results, decisions with stated reasons, reusable syntheses, contradictions of prior claims. Follow the Ingest procedure in `SCHEMA_AI_skills.md`.

**Finish the cycle: every wiki edit ends with a commit.** The wiki at `wiki/AI_skills.wiki/` is a separate git repo with its own remote. Before committing, **run the Verification Gate** at `wiki/agents/verification-gate.md` over every page created or edited, which catches projection-as-fact, missing corpus tags on numerical claims, missing back-references, and missing log/index entries. Then:

```bash
git -C wiki/AI_skills.wiki add <files-by-name>
git -C wiki/AI_skills.wiki commit -m "<descriptive message>"
```

Execute these without asking. Local commits in the wiki repo are trivially reversible. Push only when explicitly asked.

Honest reporting: bad results and contradicted claims get filed truthfully, not polished. Per the global rule, never report accuracy from projections, only from real script outputs. See `wiki/agents/discipline-gates.md` for the canonical "Universal Rationalizations (Always Wrong)" table that names the failure modes the Verification Gate catches.

Claude Code users have project-level slash commands available for explicit invocation: `/wiki-experiment`, `/wiki-source`, `/wiki-lint`. See `.claude/commands/`. The project also ships the same procedures as model-side skills at `.claude/skills/` (referenced by the slash commands). The slash commands are a safety net: the proactive behavior described above is the default, the slash commands exist for cases where the user wants to force the action explicitly.

### Knowledge Graph

The wiki's frontmatter and body links feed a knowledge graph pipeline (`scripts/kg/`) that produces a SPARQL-queryable RDF graph from wiki content. The pipeline runs in Python via rdflib and pyshacl; no separate server is required by default.

- **Rebuild**: `./scripts/kg/build-graph.sh` after wiki updates
- **Query (default)**: in-process via rdflib against `scripts/kg/build/graph-full.ttl`. Agent tool wrappers run SPARQL queries directly against the loaded graph object.
- **Query (optional)**: load `graph-full.ttl` into Apache Jena Fuseki for live multi-client query, agent-write via SPARQL UPDATE, or federation across wikis. rdflib talks to a Fuseki endpoint via `SPARQLStore` without changes to tool code.
- Typed edges in frontmatter (`extends:`, `supports:`, `criticizes:`) produce rich graph relationships
- Body cross-references (`[text](Page-Name)`) produce `mentions` edges
- Pages without frontmatter are included as `untyped` nodes — no data is lost
