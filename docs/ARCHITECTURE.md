# Architecture & Technical Deep Dive: 360-degree LSP Lifecycle for Antigravity CLI

## 1. Executive Summary

Antigravity CLI agents without semantic tools default to two costly anti-patterns:
1. Blind Exploration: Searching code via whole-workspace Grep/Glob, burning 70-90% of prompt tokens on irrelevant text output.
2. Blind Modification: Generating code without immediate syntax or type validation, creating subtle compilation bugs that persist until manual review.

The LSP Enforcement Kit for Antigravity creates a complete closed-loop lifecycle around the agent:

```mermaid
flowchart TD
    subgraph 1. Exploration Phase (PreToolUse)
        A[Agent calls grep_search / find_by_name] --> B(nav_guard.py)
        C{Contains code symbol?}
        B --> C
        C -- Yes --> D[DENY: Suggest active MCP tool]
        C -- No --> E[ALLOW: Run standard search]
    end

    subgraph 2. Modification & Audit Phase (PostToolUse)
        F[Agent writes file via write_to_file / replace_file_content] --> G(lsp_audit.py post-tool)
        G --> H{Multi-Language Audit with Nearest-Root}
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

## 2. Multi-Language Audit Engine Matrix

| Language | Extensions | Primary Engine | Fallback / Deep Check | Typical Latency |
| :--- | :--- | :--- | :--- | :---: |
| **Python** | `.py` | `ast.parse()` + Native `symtable` (catches `NameError` & typos) | `ruff` / `pyright` | < 2 ms |
| **TypeScript / JS** | `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs` | `node --check` (for pure JS) | `biome` / `tsc --noEmit` (nearest root) | ~5 ms |
| **Astro** | `.astro` | Strict Frontmatter delimiter parsing (`---`) | `@astrojs/check` (in Astro projects) | < 3 ms |
| **PHP** | `.php` | Execution-free AST linting via `php -l` | Scoped project validation | < 5 ms |
| **PowerShell** | `.ps1`, `.psm1`, `.psd1` | .NET `System.Management.Automation.Language.Parser` | Native AST error collection | ~15 ms |
| **Bash / Shell** | `.sh`, `.bash`, `.zsh` | Static syntax checking via `bash -n` / `sh -n` | POSIX execution-free validation | < 5 ms |
| **Rust** | `.rs` | `cargo check --message-format=json` | Scoped nearest `Cargo.toml` root | Scoped |
| **Go** | `.go` | `go vet` | Scoped nearest `go.mod` root | Scoped |
| **JSON / TOML** | `.json`, `.toml` | Standard library parsers (`json`, `tomllib`) | Instant strict format validation | < 1 ms |

---

## 3. The 4 Engineering Pillars

### Pillar I: Syntax Analysis & Error-Tolerant Parsing
* Fast-Path AST (0ms): Direct parser invocation using standard library (ast.parse(), json.loads(), tomllib.load(), symtable).
* Noise Reduction Cap: Compilers like tsc or ruff can return 100+ lines of cascading errors. The engine caps output to the top 5 distinct diagnostics per file to prevent prompt token bloat.

### Pillar II: Cross-Platform Compatibility (Windows / Linux / macOS)
* Path Normalization: Windows mixed path separators (/ vs \) and case insensitivity are unified via os.path.normcase(os.path.abspath(path)) to prevent duplicate or missing cache entries.
* Pure ASCII Output: Replaced emojis with standard ASCII brackets ([OK], [FAIL], [LSP-FIRST GUARD]) preventing UnicodeEncodeError on legacy terminals and strict CI pipes.
* Cross-Platform Subprocess Escaping: Commands execute with shell=True on Windows and direct execution on Unix without external shell dependencies.

### Pillar III: Scalability in Monorepos (Nearest-Root Discovery)
* The Monorepo Bottleneck: In monorepos (e.g. 50+ packages, >200k lines), running tsc or cargo check at the project root causes 10-30s freezes and massive memory spikes.
* Nearest-Root Discovery:
  * Walks upward from the target file to locate the closest boundary marker (tsconfig.json, package.json, Cargo.toml, go.mod, pyproject.toml).
  * Runs the validator scoped strictly to that package boundary.

### Pillar IV: Robustness & Circuit Breaker Engine
* Anti-Deadlock Circuit Breaker: If the agent attempts to stop while errors persist, it blocks up to 3 consecutive attempts (decision: continue). On the 4th attempt, the gate opens (fail-open) to prevent infinite API billing loops.
* Cross-File Reconciliation: When a shared file (e.g., types.ts) is fixed, the engine automatically re-checks all remaining failing files in the session cache to clear resolved downstream errors.
* Dead File Purging: If a broken file is deleted by the agent, it is immediately removed from the audit cache.
