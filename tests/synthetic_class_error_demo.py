"""
Synthetic Test Demo: Class Reference & Undefined Symbol Detection.
Demonstrates how the LSP Enforcement Kit catches:
1. Missing Class Import (referencing UserAccount without importing it).
2. Class Name Typo (referencing UserAcount instead of UserAccount).
3. Cross-File Broken Reference (Renaming a class in module A while module B still imports it).

Includes Multi-Path Discovery (local .agents, global ~/.gemini, and repo plugin/).
"""
import subprocess
import json
import os
import sys
import shutil
import pathlib

DEMO_DIR = "demo_synthetic_test"

def find_lsp_audit_script() -> str:
    """Discovers lsp_audit.py in local workspace, global config, or repo folder."""
    candidates = [
        pathlib.Path("src/lsp_audit.py"),
        pathlib.Path(".agents/hooks/lsp_audit.py"),
        pathlib.Path("plugin/lsp-enforcement-kit/lsp_audit.py"),
        pathlib.Path.home() / ".gemini" / "config" / "plugins" / "lsp-enforcement-kit" / "lsp_audit.py",
        pathlib.Path(__file__).resolve().parent.parent / "src" / "lsp_audit.py"
    ]
    for c in candidates:
        if c.exists():
            return str(c.resolve())
    return ".agents/hooks/lsp_audit.py"

def run_demo():
    print("=" * 65)
    print("PRUEBA SINTETICA: DETECCION DE ERRORES DE CLASES Y REFERENCIAS")
    print("=" * 65)

    audit_script = find_lsp_audit_script()
    print(f"[*] Motor de auditoria cargado desde: {audit_script}\n")

    os.makedirs(f"{DEMO_DIR}/models", exist_ok=True)
    os.makedirs(f"{DEMO_DIR}/services", exist_ok=True)

    auth_file = f"{DEMO_DIR}/services/auth_service.py"
    payload = {
        "conversationId": "demo-class-session",
        "toolCall": {"name": "write_to_file", "args": {"TargetFile": auth_file}}
    }

    # -------------------------------------------------------------
    # CASO 1: Referenciar una clase sin importar (Missing Import)
    # -------------------------------------------------------------
    auth_service_code = """
def authenticate_user(username: str):
    # Error: UserAccount se usa directamente pero NO esta importada
    session = UserAccount(username=username, active=True)
    return session
"""
    with open(auth_file, "w", encoding="utf-8") as f:
        f.write(auth_service_code)

    subprocess.run([sys.executable, audit_script, "post-tool"],
                   input=json.dumps(payload), text=True, capture_output=True)

    res = subprocess.run([sys.executable, audit_script, "pre-invocation"],
                         input=json.dumps({"conversationId": "demo-class-session"}), text=True, capture_output=True)

    print("[CASO 1: Clase no importada]")
    print("  Archivo: services/auth_service.py")
    print("  Codigo: session = UserAccount(...) # (sin importar UserAccount)")
    print("  Diagnostico inyectado a la IA:")
    diag = json.loads(res.stdout).get("injectSteps", [{}])[0].get("ephemeralMessage", "")
    print(f"  {diag}")

    # -------------------------------------------------------------
    # CASO 2: Error tipografico en nombre de clase (Class Typo)
    # -------------------------------------------------------------
    auth_service_typo = """
class UserAccount:
    def __init__(self, username, active):
        self.username = username
        self.active = active

def authenticate_user(username: str):
    # Error: Se escribio UserAcount (con una sola 'c')
    session = UserAcount(username=username, active=True)
    return session
"""
    with open(auth_file, "w", encoding="utf-8") as f:
        f.write(auth_service_typo)

    subprocess.run([sys.executable, audit_script, "post-tool"],
                   input=json.dumps(payload), text=True, capture_output=True)

    res2 = subprocess.run([sys.executable, audit_script, "pre-invocation"],
                          input=json.dumps({"conversationId": "demo-class-session"}), text=True, capture_output=True)

    print("\n[CASO 2: Error tipografico en clase existente]")
    print("  Archivo: services/auth_service.py")
    print("  Codigo: session = UserAcount(...) # (definida como UserAccount)")
    print("  Diagnostico con sugerencia automatica:")
    diag2 = json.loads(res2.stdout).get("injectSteps", [{}])[0].get("ephemeralMessage", "")
    print(f"  {diag2}")

    # -------------------------------------------------------------
    # CASO 3: Correccion limpia (Clean Fix)
    # -------------------------------------------------------------
    auth_service_clean = """
class UserAccount:
    def __init__(self, username, active):
        self.username = username
        self.active = active

def authenticate_user(username: str):
    session = UserAccount(username=username, active=True)
    return session
"""
    with open(auth_file, "w", encoding="utf-8") as f:
        f.write(auth_service_clean)

    subprocess.run([sys.executable, audit_script, "post-tool"],
                   input=json.dumps(payload), text=True, capture_output=True)

    res3 = subprocess.run([sys.executable, audit_script, "stop"],
                          input=json.dumps({"conversationId": "demo-class-session"}), text=True, capture_output=True)

    print("\n[CASO 3: Codigo corregido]")
    print("  Respuesta del Stop Quality Gate (Permitido):", res3.stdout.strip() or "{} (Limpio)")
    print("=" * 65)

    shutil.rmtree(DEMO_DIR, ignore_errors=True)

if __name__ == "__main__":
    run_demo()
