# Antigravity LSP Enforcement & Semantic-First Rule

When working on code in this repository or with this plugin active:

1. **Semantic Navigation First**:
   - Always prefer LSP MCP tools (ind_definition, ind_references, search_workspace_symbols, get_document_outline) over whole-file full-text regex searches (grep_search) or reading entire 500+ line files.
   - Do not search for symbols, classes, or function names with blind grep_search -- use search_workspace_symbols or ind_definition.

2. **Quality Gate Compliance**:
   - Every file edit via write_to_file or eplace_file_content triggers immediate AST and linter audits.
   - If PreInvocation provides ephemeral diagnostic errors, fix them immediately in the next step.
   - Do not attempt to finalize or stop the task while compilation, syntax, or unresolved name errors persist.
