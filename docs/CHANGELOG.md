# Changelog

All notable changes to the Antigravity LSP Enforcement Kit will be documented in this file.

## [1.3.0] - 2026-08-18

### Added
- **PHP Audit Support**: Added native execution-free AST linting via `php -l`.
- **PowerShell Audit Support**: Added native AST parsing via .NET `System.Management.Automation.Language.Parser`.
- **Bash / Shell Audit Support**: Added static syntax validation via `bash -n` / `sh -n`.
- **1-Click Cross-Platform Installers**:
  - `install.ps1` (PowerShell for Windows)
  - `install.cmd` (Double-clickable CMD launcher)
  - `install.sh` (POSIX Bash installer for Linux & macOS)
- **Built-in Scope & NameError Resolution**: Native `symtable` + `difflib` static analysis engine to catch typos (`taag` vs `tag`) and missing class imports in 0ms without external pip packages.
- **100% Pure ASCII Output Compliance**: Removed all emojis and special characters for bulletproof legacy terminal and CI pipeline compatibility.

---

## [1.2.0] - 2026-08-17

### Added
- **Nearest-Root Discovery**: Automatically traverses parent directories to discover package boundaries (`tsconfig.json`, `package.json`, `Cargo.toml`, `go.mod`, `pyproject.toml`) for monorepo scalability.
- **Cross-Platform Path Normalization**: Unified Windows and POSIX path handling with `os.path.normcase`.
- **Docker Compose Sandbox**: Containerized test and execution environment.

---

## [1.1.0] - 2026-08-17

### Added
- Multi-language auditing for Rust (`cargo check`), Go (`go vet`), JSON (`json.load`), and TOML (`tomllib.load`).
- Cross-file reconciliation: Automatically clears resolved dependencies in session cache.
- Diagnostic status mode: `python lsp_audit.py status`.

---

## [1.0.0] - 2026-08-17

### Added
- Initial release of Antigravity LSP Enforcement Kit (360-degree closed loop lifecycle).
- Pre-Tool Navigation Guard (`nav_guard.py`) for blocking full-workspace grep on code symbols.
- Post-Tool Incremental Auditor (`lsp_audit.py`) with AST fast path.
- Anti-deadlock Circuit Breaker on `Stop` hook (max 3 retries).
