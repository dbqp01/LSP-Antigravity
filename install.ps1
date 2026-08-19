<#
.SYNOPSIS
    Instalador y configurador automatico del Antigravity LSP Enforcement Kit.
.DESCRIPTION
    1. Verifica e instala herramientas CLI recomendadas (Ruff, Pyright, Biome, TypeScript, Astro, PHP).
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

# 1. Verificacion de Entorno Base
Write-Host "`n[1/3] Verificando entorno base..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "[FAIL] Python no encontrado. Instala Python 3.10+ para continuar."
    exit 1
}
Write-Host "  [OK] Python detectado: $((python --version) 2>&1)" -ForegroundColor Green

if (Get-Command php -ErrorAction SilentlyContinue) {
    $phpVer = (php -v | Select-Object -First 1)
    Write-Host "  [OK] PHP detectado: $phpVer" -ForegroundColor Green
} else {
    Write-Host "  [INFO] PHP CLI no detectado. Si programas en PHP: winget install PHP.PHP" -ForegroundColor DarkGray
}

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
Write-Host "`n[3/3] Desplegando plugin de Antigravity..." -ForegroundColor Yellow

$SourceDir = $PSScriptRoot
if (-not (Test-Path (Join-Path $SourceDir "plugin.json"))) {
    $SourceDir = $WorkspacePath
}

$PluginFiles = @("plugin.json", "hooks.json", "mcp_config.json", "src", "rules", "skills")

# Workspace local (.agents/plugins/lsp-enforcement-kit)
$LocalAgentsDir = Join-Path $WorkspacePath ".agents"
$LocalPluginsDir = Join-Path $LocalAgentsDir "plugins\lsp-enforcement-kit"

New-Item -ItemType Directory -Force -Path $LocalPluginsDir | Out-Null
foreach ($item in $PluginFiles) {
    $srcPath = Join-Path $SourceDir $item
    if (Test-Path $srcPath) {
        Copy-Item -Recurse -Force $srcPath "$LocalPluginsDir\"
    }
}

# Remove legacy broken root hooks.json if present
$LegacyHooksJson = Join-Path $LocalAgentsDir "hooks.json"
if (Test-Path $LegacyHooksJson) {
    Remove-Item -Force $LegacyHooksJson
}
Write-Host "  [OK] Desplegado como Plugin en Workspace: $LocalPluginsDir" -ForegroundColor Green

# Global (~/.gemini/config/plugins/lsp-enforcement-kit)
if ($Global) {
    $GlobalPluginDir = Join-Path $env:USERPROFILE ".gemini\config\plugins\lsp-enforcement-kit"
    New-Item -ItemType Directory -Force -Path $GlobalPluginDir | Out-Null
    foreach ($item in $PluginFiles) {
        $srcPath = Join-Path $SourceDir $item
        if (Test-Path $srcPath) {
            Copy-Item -Recurse -Force $srcPath "$GlobalPluginDir\"
        }
    }
    Write-Host "  [OK] Desplegado Globalmente: $GlobalPluginDir" -ForegroundColor Green
}

# 4. Diagnostico Final
Write-Host "`n"
if (Get-Command agy -ErrorAction SilentlyContinue) {
    Write-Host "  -> Validando con Antigravity CLI (agy):" -ForegroundColor Cyan
    agy plugin validate $LocalPluginsDir
}
python "$LocalPluginsDir\src\lsp_audit.py" status

Write-Host "`n[LISTO] Antigravity LSP Enforcement Kit instalado y activado con exito." -ForegroundColor Green
