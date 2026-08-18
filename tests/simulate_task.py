"""
Simulates an Antigravity agent executing a coding task under the LSP Harness.
Traces:
1. PreToolUse Navigation Guard (blocking grep on symbols)
2. PostToolUse Code Audit (catching broken Python syntax)
3. PreInvocation Ephemeral Diagnostics Injection
4. Stop Hook Gating (blocking premature stop)
5. Repair & Clean Stop
"""
import json
import subprocess
import os
import sys

def main():
    print("=" * 65)
    print("🚀 EJECUTANDO TAREA DE AGENTE EN HARNESS DOCKER ANTIGRAVITY")
    print("=" * 65)

    conv_id = "docker-task-01"

    # Paso 1: Agente intenta buscar símbolo 'calculateTotalAmount' con grep_search
    grep_payload = {
        "conversationId": conv_id,
        "toolCall": {"name": "grep_search", "args": {"Query": "calculateTotalAmount"}}
    }
    p1 = subprocess.run(["python3", "plugin/lsp-enforcement-kit/nav_guard.py", "pre-tool"],
                        input=json.dumps(grep_payload), text=True, capture_output=True)
    print("\n[Paso 1 - PreToolUse Navigation Guard]:")
    print("  Acción agente: grep_search('calculateTotalAmount')")
    print("  Respuesta del Harness:", p1.stdout.strip())

    # Paso 2: Agente escribe archivo con error de sintaxis en src/service.py
    os.makedirs("src", exist_ok=True)
    with open("src/service.py", "w", encoding="utf-8") as f:
        f.write("def calculate_total(a, b:\n    return a + b\n")

    write_payload = {
        "conversationId": conv_id,
        "toolCall": {"name": "write_to_file", "args": {"TargetFile": "src/service.py"}}
    }
    p2 = subprocess.run(["python3", "plugin/lsp-enforcement-kit/lsp_audit.py", "post-tool"],
                        input=json.dumps(write_payload), text=True, capture_output=True)
    print("\n[Paso 2 - PostToolUse Code Audit]:")
    print("  Acción agente: write_to_file('src/service.py') con sintaxis rota")
    print("  Respuesta del Harness (vacía, contract OK):", p2.stdout.strip() or "{}")

    # Paso 3: Siguiente ciclo, PreInvocation inyecta diagnóstico efímero
    p3 = subprocess.run(["python3", "plugin/lsp-enforcement-kit/lsp_audit.py", "pre-invocation"],
                        input=json.dumps({"conversationId": conv_id}), text=True, capture_output=True)
    print("\n[Paso 3 - PreInvocation Ephemeral Injection]:")
    print("  Diagnóstico inyectado al contexto del modelo:")
    print(" ", p3.stdout.strip())

    # Paso 4: Agente intenta parar prematuramente
    p4 = subprocess.run(["python3", "plugin/lsp-enforcement-kit/lsp_audit.py", "stop"],
                        input=json.dumps({"conversationId": conv_id}), text=True, capture_output=True)
    print("\n[Paso 4 - Stop Quality Gate]:")
    print("  Intento de parada bloqueado por el Harness:")
    print(" ", p4.stdout.strip())

    # Paso 5: Agente corrige el error
    with open("src/service.py", "w", encoding="utf-8") as f:
        f.write("def calculate_total(a, b):\n    return a + b\n")
    subprocess.run(["python3", "plugin/lsp-enforcement-kit/lsp_audit.py", "post-tool"],
                   input=json.dumps(write_payload), text=True, capture_output=True)

    # Paso 6: Agente para exitosamente
    p6 = subprocess.run(["python3", "plugin/lsp-enforcement-kit/lsp_audit.py", "stop"],
                        input=json.dumps({"conversationId": conv_id}), text=True, capture_output=True)
    print("\n[Paso 6 - Stop Gate tras corrección]:")
    print("  Parada permitida limpiamente (Caché vacía):", p6.stdout.strip() or "{}")
    print("=" * 65)

if __name__ == "__main__":
    main()
