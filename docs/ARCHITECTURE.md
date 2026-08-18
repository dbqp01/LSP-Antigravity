# Architecture: 360° LSP Lifecycle for Antigravity CLI

## 1. Executive Summary

Antigravity CLI agents without semantic tools default to two costly anti-patterns:
1. **Blind Exploration**: Searching code via whole-workspace Grep/Glob, burning 70–90% of prompt tokens on irrelevant text output.
2. **Blind Modification**: Generating code without immediate syntax or type validation, creating subtle compilation bugs that persist until manual review.

The **LSP Enforcement Kit for Antigravity** creates a complete closed-loop lifecycle around the agent:

```mermaid
flowchart TD
    subgraph 1. Exploration Phase (PreToolUse)
        A[Agent calls grep_search / find_by_name] --> B(nav_guard.py)
        B --> C{Contains code symbol?}
        C -- Yes --> D[DENY: Suggest active MCP tool (Serena/cclsp)]
        C -- No --> E[ALLOW: Run standard search]
    end

    subgraph 2. Modification & Audit Phase (PostToolUse)
        F[Agent writes file via write_to_file / replace_file_content] --> G(lsp_audit.py post-tool)
        G --> H{Audit File}
        H -->|Errors found| I[Store in .audit_cache/<conv_id>.json]
        H -->|Clean| J[Purge file from cache & Reconcile cross-file errors]
    end

    subgraph 3. Context Injection Phase (PreInvocation)
        K(PreInvocation Hook) --> L{Pending errors in cache?}
        L -- Yes --> M[Inject ephemeralMessage with LSP diagnostics]
        L -- No --> N[Silent pass]
        M --> O[Agent auto-corrects broken code]
    end

    subgraph 4. Quality Gate Phase (Stop)
        P(Stop Hook) --> Q{Pending errors in cache?}
        Q -- Yes --> R{Stop Attempts <= 3?}
        R -- Yes --> S[DENY STOP: decision: continue]
        R -- No (Circuit Breaker) --> T[ALLOW STOP: log warning to stderr]
        Q -- No --> U[ALLOW STOP: task succeeded]
    end
```

---

## 2. Component Breakdown

### A. Pre-Tool Navigation Guard (`nav_guard.py`)
* **Hook Trigger**: `PreToolUse` on `grep_search` and `find_by_name`.
* **Provider Awareness**: Inspects workspace and global Antigravity `mcp_config.json` to dynamically detect active LSP servers (`serena`, `cclsp`, etc.).
* **Heuristics**:
  * Detects PascalCase (`UserService`), camelCase (`getUserById`), snake_case (`write_audit_log`), and property access (`auth.login`).
  * Passes comments/keywords (`TODO`, `FIXME`), file globs (`*.ts`, `*.py`), CLI flags (`--verbose`), and multi-word conceptual queries.
* **Result**: Blocks blind whole-repo greps and instructs the agent with concrete copy-pasteable MCP calls.

### B. Post-Tool Incremental Auditor (`lsp_audit.py post-tool`)
* **Hook Trigger**: `PostToolUse` on `write_to_file` and `replace_file_content`.
* **Language Support Matrix**:
  * **Python**: AST parsing (0ms) $\to$ Ruff (`--select=E,F`) $\to$ Pyright.
  * **TypeScript / JS**: Node `--check` $\to$ Biome $\to$ TSC (`--noEmit`).
  * **Astro**: Frontmatter structural check $\to$ `@astrojs/check`.
  * **Rust**: `cargo check --message-format=json` (if `Cargo.toml` exists).
  * **Go**: `go vet`.
  * **JSON / TOML**: Native stdlib parsers (`json.loads`, `tomllib`).
* **Hash-based Caching**: Uses MD5 hashes to skip redundant CLI calls when file contents do not change.
* **Cross-File Reconciliation**: When an edited file passes clean, the engine automatically re-checks remaining broken files in the session cache to clear resolved dependency errors.

### C. Context Injection (`lsp_audit.py pre-invocation`)
* Injects errors as an `ephemeralMessage`.
* **Zero Context Bloat**: Diagnostics disappear on subsequent steps and do not pollute the permanent transcript history.

### D. Quality Gate & Circuit Breaker (`lsp_audit.py stop`)
* Blocks `Stop` if syntax or critical type errors exist in cache.
* **Circuit Breaker**: After 3 consecutive stop blocks, the gate releases (*fail-open*) to prevent infinite deadlocks and token depletion.

### E. Diagnostic Status CLI (`lsp_audit.py status`)
* Standalone inspection mode to verify installed linters, compilers, and active session caches.
