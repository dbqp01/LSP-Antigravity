<#
.SYNOPSIS
    Instalador y configurador automatico del Antigravity LSP Enforcement Kit.
.DESCRIPTION
    1. Verifica e instala herramientas CLI recomendadas (Ruff, Pyright, Biome, TypeScript, Astro).
    2. Copia y registra los hooks en el workspace (.agents/) y globalmente (~/.gemini/config/plugins/).
    3. Valida el estado final en puro formato ASCII.
#>
param(
    [string]$WorkspacePath = (Get-Location).Path,
    [switch]$Global = $true,
    [switch]$SkipTools = $false
)

$ErrorActionPreference = "Continue"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Antigravity LSP Enforcement Kit - Instalador Automatico" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Verificacion de Python
Write-Host "`n[1/3] Verificando entorno base..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "[FAIL] Python no encontrado. Instala Python 3.10+ para continuar."
    exit 1
}
Write-Host "  [OK] Python detectado: $((python --version) 2>&1)" -ForegroundColor Green

# 2. Instalacion de Linters y Herramientas si no se omiten
if (-not $SkipTools) {
    Write-Host "`n[2/3] Instalando herramientas de analisis recomendadas..." -ForegroundColor Yellow

    # Python linters (Ruff, Pyright)
    Write-Host "  -> Instalando linters de Python (ruff, pyright)..."
    python -m pip install --quiet --upgrade ruff pyright 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "     [OK] Ruff y Pyright instalados correctamente." -ForegroundColor Green
    } else {
        Write-Host "     [WARN] No se pudo instalar via pip. Se usara motor AST/Symtable nativo." -ForegroundColor DarkYellow
    }

    # Node / JS / TS / Astro linters
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Write-Host "  -> Instalando herramientas JS/TS/Astro (biome, typescript, @astrojs/check)..."
        npm install -g --silent @biomejs/biome typescript @astrojs/check astro 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "     [OK] Biome, TypeScript y Astro CLI instalados globalmente." -ForegroundColor Green
        } else {
            Write-Host "     [WARN] Fallo la instalacion npm global. Se usara Node --check para JS." -ForegroundColor DarkYellow
        }
    } else {
        Write-Host "  -> [INFO] Node/npm no encontrado. Soporte TS/Biome omitido." -ForegroundColor DarkGray
    }
} else {
    Write-Host "`n[2/3] Instalacion de herramientas omitida (-SkipTools)." -ForegroundColor DarkGray
}

# 3. Despliegue de Hooks y Configuracion
Write-Host "`n[3/3] Desplegando hooks del plugin..." -ForegroundColor Yellow

$SourceDir = Join-Path $PSScriptRoot "plugin\lsp-enforcement-kit"
if (-not (Test-Path $SourceDir)) {
    $SourceDir = Join-Path $WorkspacePath "plugin\lsp-enforcement-kit"
}

# Workspace local (.agents/)
$LocalAgentsDir = Join-Path $WorkspacePath ".agents"
$LocalHooksDir = Join-Path $LocalAgentsDir "hooks"
$LocalPluginsDir = Join-Path $LocalAgentsDir "plugins\lsp-enforcement-kit"

New-Item -ItemType Directory -Force -Path $LocalHooksDir, $LocalPluginsDir | Out-Null
Copy-Item -Force "$SourceDir\nav_guard.py" "$LocalHooksDir\nav_guard.py"
Copy-Item -Force "$SourceDir\lsp_audit.py" "$LocalHooksDir\lsp_audit.py"
Copy-Item -Force "$SourceDir\hooks.json" "$LocalAgentsDir\hooks.json"
Copy-Item -Recurse -Force "$SourceDir\*" "$LocalPluginsDir\"
Write-Host "  [OK] Desplegado en Workspace: $LocalAgentsDir" -ForegroundColor Green

# Global (~/.gemini/config/plugins/lsp-enforcement-kit)
if ($Global) {
    $GlobalPluginDir = Join-Path $env:USERPROFILE ".gemini\config\plugins\lsp-enforcement-kit"
    New-Item -ItemType Directory -Force -Path $GlobalPluginDir | Out-Null
    Copy-Item -Recurse -Force "$SourceDir\*" "$GlobalPluginDir\"
    Write-Host "  [OK] Desplegado Globalmente: $GlobalPluginDir" -ForegroundColor Green
}

# 4. Diagnostico Final
Write-Host "`n"
python "$LocalHooksDir\lsp_audit.py" status

Write-Host "`n[LISTO] Antigravity LSP Enforcement Kit instalado y activado con exito." -ForegroundColor Green
