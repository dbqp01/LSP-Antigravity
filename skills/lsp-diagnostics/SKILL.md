---
name: lsp-diagnostics
description: Diagnostic tool to check LSP language servers, compilers, linters, and session cache status. Use when verifying environment tools or investigating audit failures.
---

# LSP Diagnostics Skill

This skill allows the agent or user to verify the status of active Language Servers, installed linters, and the current audit cache.

## Usage

Run the diagnostic status check:
`ash
python src/lsp_audit.py status
`

This will report:
- Active Language Server Protocol (LSP) availability (pyright, typescript-language-server, rust-analyzer, gopls, intelephense, astro-ls).
- Installed fast-path AST parsers and CLI linters (ruff, biome, node --check, cargo check, go vet, php -l).
- Status of current session audit cache (.agents/.audit_cache/).
