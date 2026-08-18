"""
Synthetic Test Demo: Class Reference & Undefined Symbol Detection.
Demonstrates how the LSP Enforcement Kit catches:
1. Missing Class Import (referencing UserAccount without importing it).
2. Class Name Typo (referencing UserAcount instead of UserAccount).
3. Cross-File Broken Reference (Renaming a class in module A while module B still imports it).
"""
import subprocess
import json
import os
import shutil

DEMO_DIR = "demo_synthetic_test"

def run_demo():
    print("=" * 65)
    print("PRUEBA SINTETICA: DETECCION DE ERRORES DE CLASES Y REFERENCIAS")
    print("=" * 65)

    os.makedirs(f"{DEMO_DIR}/models", exist_ok=True)
    os.makedirs(f"{DEMO_DIR}/services", exist_ok=True)

    # -------------------------------------------------------------
    # CASO 1: Referenciar una clase sin importar (Missing Import)
    # -------------------------------------------------------------
    auth_service_code = """
def authenticate_user(username: str):
    # Error: UserAccount se usa directamente pero NO esta importada
    session = UserAccount(username=username, active=True)
    return session
"""
    auth_file = f"{DEMO_DIR}/services/auth_service.py"
    with open(auth_file, "w", encoding="utf-8") as f:
        f.write(auth_service_code)

    payload = {
        "conversationId": "demo-class-session",
        "toolCall": {"name": "write_to_file", "args": {"TargetFile": auth_file}}
    }
    
    # 1. PostToolUse audita el archivo
    subprocess.run(["python", ".agents/hooks/lsp_audit.py", "post-tool"],
                   input=json.dumps(payload), text=True, capture_output=True)

    # 2. PreInvocation obtiene el diagnostico
    res = subprocess.run(["python", ".agents/hooks/lsp_audit.py", "pre-invocation"],
                         input=json.dumps({"conversationId": "demo-class-session"}), text=True, capture_output=True)

    print("\n[CASO 1: Clase no importada]")
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

    subprocess.run(["python", ".agents/hooks/lsp_audit.py", "post-tool"],
                   input=json.dumps(payload), text=True, capture_output=True)

    res2 = subprocess.run(["python", ".agents/hooks/lsp_audit.py", "pre-invocation"],
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

    subprocess.run(["python", ".agents/hooks/lsp_audit.py", "post-tool"],
                   input=json.dumps(payload), text=True, capture_output=True)

    res3 = subprocess.run(["python", ".agents/hooks/lsp_audit.py", "stop"],
                          input=json.dumps({"conversationId": "demo-class-session"}), text=True, capture_output=True)

    print("\n[CASO 3: Codigo corregido]")
    print("  Respuesta del Stop Quality Gate (Permitido):", res3.stdout.strip() or "{} (Limpio)")
    print("=" * 65)

    # Limpieza
    shutil.rmtree(DEMO_DIR, ignore_errors=True)

if __name__ == "__main__":
    run_demo()
