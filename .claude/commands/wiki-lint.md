---
description: Health-check the wiki for orphans, dead links, stale claims, missing frontmatter.
---

You are running a health check on the wiki at `wiki/AI_skills.wiki/`. Defer to `SCHEMA_AI_skills.md` for the precise conventions.

Full procedure: see `.claude/skills/wiki-lint.md`. Summary:

1. Read `index_AI_skills.md` to get the canonical list of pages.
2. List all `.md` files in the wiki directory.
3. Scan systematically for each check below and collect findings:
   - **Orphan pages** (no inbound links from other pages or index)
   - **Dead links** (`[Display](Page)` or `[[Page]]` pointing to non-existent files)
   - **Stale claims** (superseded by newer pages or current code/results)
   - **Missing frontmatter** (no block at top, or missing `type:` / `up:`)
   - **`type: untyped`** pages whose proper type is now obvious
   - **Missing concept pages** (concepts mentioned in multiple bodies without their own page)
   - **Missing cross-references** in either direction (if A → B, B should → A)
   - **Index gaps** (pages in wiki but not listed in `index_…md`)
   - **Naming convention** deviations (should be `Title-Case-Hyphenated.md`)
   - **Special-file integrity** (`Home_…`, `index_…`, `log_…`, `SCHEMA_…`, `Home.md` redirect)
4. Report findings to the user grouped by check type, with one or two example pages per finding.
5. Ask which findings to fix in this pass. Lint is incremental.
6. For accepted fixes, apply them with cross-reference repair in both directions, update `index_AI_skills.md` as needed, and append a `## [YYYY-MM-DD] lint | Subject` entry to `log_AI_skills.md`. The first bullet of that entry is the attribution line `- by: <name> via claude-code`, where `<name>` is the output of `git config user.name` in the wiki repo (read it, do not invent it). See "Log Entry Attribution" in `SCHEMA_AI_skills.md`.
7. Optionally rebuild the knowledge graph: `./scripts/kg/build-graph.sh`.
8. **Finish the cycle.** Commit in the wiki's own git repo in two steps, without asking. One commit per log entry keeps `git blame` on the log a faithful per-entry record (see "Log Entry Attribution" in SCHEMA):
    ```
    git -C wiki/AI_skills.wiki add <lint-fix-and-index-files-by-name>
    git -C wiki/AI_skills.wiki commit -m "lint: <summary>"
    git -C wiki/AI_skills.wiki add log_AI_skills.md
    git -C wiki/AI_skills.wiki commit -m "log: lint <summary>"
    ```
    Local commits are reversible. Push only if the user requests.

Honest reporting: do not paper over contradictions. If two pages disagree and current code/results decide between them, update the loser and link to the winner.
