# Guia de Publicacion e Instalacion en el Marketplace de Antigravity (AGY)

Este documento detalla el procedimiento oficial y estandarizado para distribuir, instalar y publicar el **Antigravity LSP Enforcement Kit** en el ecosistema de **Google Antigravity CLI (gy)**.

---

## 1. Arquitectura de Distribucion de Plugins en Antigravity

Antigravity CLI gestiona sus plugins a traves de tres mecanismos complementarios:

1. **Instalacion Directa por Repositorio Git (Recomendado / Inmediato)**:
   Cualquier usuario con Antigravity CLI puede instalar este plugin apuntando al repositorio de GitHub:
   `ash
   agy plugin install https://github.com/dbqp01/LSP-Antigravity
   `
   El CLI clona el repositorio en ~/.gemini/antigravity-cli/plugins/lsp-enforcement-kit, registra las herramientas MCP y activa los hooks de ciclo de vida automaticamente.

2. **Instalacion Local / Desarrollo**:
   Para probar o instalar cambios locales en cualquier entorno:
   `ash
   agy plugin install .
   `

3. **Catalogo / Marketplace de Antigravity (plugin@marketplace)**:
   Para registrar el plugin en el catalogo centralizado de extensiones de Google Antigravity.

---

## 2. Requisitos de Estructura para el Marketplace de AGY

Para que un plugin sea valido y procesado correctamente por gy plugin validate y el Marketplace, la raiz del repositorio debe contener los siguientes archivos:

`	ext
├── plugin.json                 # [REQUERIDO] Manifiesto del plugin con nombre, version y descripcion
├── hooks.json                  # [OPCIONAL] Hooks de ciclo de vida del agente
├── mcp_config.json             # [OPCIONAL] Definicion de servidores de herramientas MCP
├── rules/                      # [OPCIONAL] Reglas contextuales del agente (AGENTS.md)
│   └── AGENTS.md
├── skills/                     # [OPCIONAL] Habilidades invocables bajo demanda
│   └── lsp-diagnostics/
│       └── SKILL.md
└── src/                        # [CODIGO] Codigo ejecutable del plugin (Python stdlib)
`

---

## 3. Validacion Pre-Publicacion (Pre-flight Check)

Antes de publicar o taggear una nueva version, ejecuta siempre el validador oficial de Antigravity:

`ash
# Validar el plugin en el directorio actual
agy plugin validate .
`

**Salida esperada:**
`	ext
  [ok]    .
          ✔ skills      : 1 processed
          - agents      : skipped (not found)
          - commands    : skipped (not found)
          ✔ mcpServers  : 1 processed
          ✔ hooks       : 1 processed
`

---

## 4. Proceso de Publicacion en GitHub y Versionado Semantico

1. **Actualizar la version en plugin.json**:
   `json
   {
     name: lsp-enforcement-kit,
     version: 1.2.0,
     description: 360-degree LSP Lifecycle, Navigation Guard & Quality Gate for Antigravity CLI,
     author: dbqp01,
     license: MIT,
     repository: https://github.com/dbqp01/LSP-Antigravity
   }
   `

2. **Crear el Tag y Release en Git**:
   `ash
   git add .
   git commit -m release: v1.2.0 standardized marketplace structure
   git tag -a v1.2.0 -m Release v1.2.0 for Antigravity Plugin Marketplace
   git push origin main --tags
   `

3. **Generar un GitHub Release**:
   - Ir a https://github.com/dbqp01/LSP-Antigravity/releases/new.
   - Seleccionar el tag 1.2.0.
   - Publicar el release con las notas de version de docs/CHANGELOG.md.

---

## 5. Publicacion en el Registro de Antigravity / Gemini Extensions

Para registrar el plugin en los catalogos publicos oficiales:

1. **Registro en el Catalogo de Antigravity**:
   - Enviar una PR o registro al repositorio central del catalogo de Antigravity o mediante la consola de Vertex AI / Google Cloud Developer Console.
   - Proporcionar la URL del repositorio Git (https://github.com/dbqp01/LSP-Antigravity), la descripcion, tags (lsp, quality-gate, developer-tools, python, 	ypescript) y licencia MIT.

2. **Comandos de Gestion para Usuarios Finales**:
   `ash
   # Listar plugins instalados
   agy plugin list

   # Habilitar o deshabilitar
   agy plugin enable lsp-enforcement-kit
   agy plugin disable lsp-enforcement-kit

   # Desinstalar
   agy plugin uninstall lsp-enforcement-kit
   `
