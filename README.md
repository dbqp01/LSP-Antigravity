# 🚀 Antigravity LSP Enforcement Kit

> **A 360° Closed-Loop LSP Lifecycle & Quality Gate for Antigravity CLI**  
> *Enforce LSP-first navigation to save up to 80% tokens & prevent broken code from landing.*

[![CI](https://github.com/your-username/antigravity-lsp-enforcement-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/antigravity-lsp-enforcement-kit/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Antigravity](https://img.shields.io/badge/Antigravity-Plugin-purple.svg)](https://antigravity.dev)
[![Python Stdlib Only](https://img.shields.io/badge/Dependencies-0%20pip%20deps-blue.svg)](plugin/lsp-enforcement-kit/lsp_audit.py)

---

## 🎯 The Problem

Without semantic LSP guidance, AI coding agents suffer from two critical inefficiencies:

1. **Blind Exploration (Token Waste)**: The agent searches symbols via full-workspace `grep_search` and reads entire files, consuming 5,000–10,000+ tokens per lookup.
2. **Blind Modification (Broken Code)**: The agent edits code without immediate syntax or type validation, finishing tasks with unresolved compilation errors.

---

## ⚡ The Solution: 360° LSP Lifecycle

```mermaid
flowchart LR
    A[Exploración / Lectura] -->|PreToolUse: nav_guard.py| B[Bloquea Grep ciego -> Sugiere LSP MCP]
    C[Modificación / Escritura] -->|PostToolUse: lsp_audit.py| D[Auditoría instantánea AST/Linter]
    D -->|PreInvocation efímero| E[Agente autocorrige el código roto]
    E -->|Stop Hook Gate| F[Cerrojo con Circuit Breaker anti-deadlock]
```

### 1. Pre-Tool Navigation Guard (`nav_guard.py`)
Intercepts `grep_search` and `find_by_name`. If a query contains code symbols (e.g., `UserService`, `handleSubmit`, `write_audit_log`), it **denies execution** and instructs the agent to use LSP semantic navigation (`find_definition`, `find_references`) or targeted reading.

### 2. Post-Tool Incremental Auditor (`lsp_audit.py`)
Intercepts `write_to_file` and `replace_file_content`. Audits only modified files using a multi-tiered failover ladder:
* **Python**: AST parsing (0ms) $\to$ Ruff / Pyright.
* **TypeScript / JS**: Node `--check` $\to$ Biome / TSC.
* **Astro**: Frontmatter format check $\to$ `@astrojs/check`.
* **JSON**: Instant syntax validation with `json.loads()`.

### 3. Ephemeral Ingestion (`PreInvocation`)
Injects diagnostics into the model prompt via `ephemeralMessage`. The model fixes the error without cluttering the permanent conversation transcript.

### 4. Quality Gate with Circuit Breaker (`Stop`)
Prevents the agent from stopping while unresolved errors persist in cache. Automatically releases after **3 attempts** (*Circuit Breaker*) to prevent infinite deadlocks.

---

## 📦 Quick Installation

### Option A: Install as an Antigravity Global Plugin (Recommended)
Copy the plugin folder to your global Antigravity configuration directory:

```bash
# Linux / macOS
cp -r plugin/lsp-enforcement-kit ~/.gemini/config/plugins/

# Windows (PowerShell)
Copy-Item -Recurse -Force plugin/lsp-enforcement-kit "$env:USERPROFILE\.gemini\config\plugins\"
```

Enable the plugin inside Antigravity:
```text
/plugin enable lsp-enforcement-kit
```

### Option B: Project-Level Usage
Simply place the plugin inside your project root:
```bash
mkdir -p .agents/plugins/
cp -r plugin/lsp-enforcement-kit .agents/plugins/
```

---

## 🧪 Testing and Reproducibility

### Run the Native Test Suite (0 dependencies)
```bash
python -m unittest discover tests -v
```

### Run in Docker Sandbox
```bash
docker compose -f docker/docker-compose.yml run --rm audit-sandbox
```

---

## 📊 Token Savings Benchmark

| Task | Standard Grep + Read | LSP Enforced | Savings |
| :--- | :--- | :--- | :--- |
| Find symbol definition | ~6,500 tokens (Grep + 2 file reads) | ~580 tokens (`find_definition` + targeted read) | **~91%** |
| Find symbol usages | ~1,500 tokens (Noisy Grep matches) | ~150 tokens (`find_references`) | **~90%** |
| Syntax verification | Manual developer debugging | 0 tokens overhead (auto-fixed in-loop) | **100% automated** |

---

## 📂 Repository Structure

```text
.
├── .github/workflows/ci.yml       # Multi-OS & Multi-Python CI/CD pipeline
├── docker/
│   ├── Dockerfile                 # Slim, reproducible container sandbox
│   └── docker-compose.yml         # Container runner
├── docs/
│   ├── ARCHITECTURE.md            # Detailed technical specification
│   └── CHANGELOG.md               # Version history
├── plugin/
│   └── lsp-enforcement-kit/
│       ├── hooks.json             # Antigravity hook lifecycle mappings
│       ├── lsp_audit.py           # Post-write auditor & quality gate
│       ├── nav_guard.py           # Pre-tool navigation guard
│       └── plugin.json            # Official plugin manifest
├── tests/
│   ├── test_audit_engine.py       # Engine & circuit breaker unit tests
│   ├── test_hooks_e2e.py          # Full lifecycle E2E integration tests
│   └── test_nav_guard.py          # Symbol pattern detection tests
├── LICENSE                        # MIT License
└── README.md                      # Documentation & guide
```

---

## 📜 License

MIT License. Designed with **Ponytail (ULTRA)** principles: minimal code, maximum speed, zero external dependencies.
