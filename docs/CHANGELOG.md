# Changelog

All notable changes to the **Antigravity LSP Enforcement Kit** will be documented in this file.

## [1.1.0] - 2026-08-17

### Added
- **Multi-Language Expansion**: Added native/CLI audit support for **Rust** (`cargo check`), **Go** (`go vet`), and **TOML** (`tomllib`).
- **Provider-Aware Navigation Guard**: `nav_guard.py` now scans workspace and global `mcp_config.json` files for active LSP servers (Serena, cclsp) and generates provider-specific tool recommendations.
- **Cross-File Reconciliation**: When an edited file passes clean, `lsp_audit.py` automatically re-audits any remaining failing files in the session cache.
- **Diagnostic CLI Command**: Added `python lsp_audit.py status` to report installed tools, compilers, and active cache state.

## [1.0.0] - 2026-08-17

### Added
- **Pre-Tool Navigation Guard (`nav_guard.py`)**: Intercepts `grep_search` and `find_by_name` to prevent token-heavy grep on code symbols and enforce LSP semantic navigation.
- **Post-Tool Code Auditor (`lsp_audit.py`)**: Multi-language incremental validator for Python, TypeScript, JavaScript, Astro 5, and JSON.
- **Circuit Breaker Engine**: Added a 3-attempt circuit breaker on the `Stop` hook to prevent agent deadlocks.
- **MD5 Hash Caching**: Files with identical hashes skip redundant CLI linter executions.
- **Antigravity Native Plugin Packaging**: Distributed under `plugin/lsp-enforcement-kit/` with official `plugin.json` manifest.
- **Zero-Dependency Test Suite**: Complete unit and E2E lifecycle test suite using Python `unittest`.
- **Cross-Platform CI/CD**: GitHub Actions workflow testing Ubuntu, Windows, and macOS on Python 3.10, 3.11, and 3.12.
- **Docker Sandbox**: Containerized environment for isolated validation.
