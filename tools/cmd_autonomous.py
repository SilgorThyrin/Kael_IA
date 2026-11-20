"""Comandos do Modo Autônomo do Kael."""

TOOL_NAME = "autonomous"

try:
    from core.autonomous_engine import AutonomousEngine
    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    class AutonomousEngine:
        def __init__(self, *a, **k): pass
        def start_task(self, *a, **k): return {"error": "Engine indisponível."}
        def stop_task(self): return {"message": "Engine indisponível."}
        def get_status(self): return {"status": "unavailable"}


def tarefa(ctx, args, flags):
    """Inicia uma tarefa autônoma."""
    if not AVAILABLE:
        return {"response": "🔴 AutonomousEngine indisponível.", "thinking": "Módulo ausente.", "status": "error"}
    
    if not args:
        return {"response": "⚠️ Uso: `/tarefa [descricao]`", "thinking": "Faltou descrição.", "status": "error"}
    
    description = " ".join(args)
    
    # Cria engine se não existir
    if not hasattr(ctx, 'autonomous_engine'):
        ctx.autonomous_engine = AutonomousEngine(ctx)
    
    result = ctx.autonomous_engine.start_task(description)
    
    if "error" in result:
        return {"response": f"⚠️ {result['error']}", "thinking": "Erro ao iniciar tarefa.", "status": "error"}
    
    return {
        "response": (
            f"🤖 **Modo Autônomo INICIADO!**\n"
            f"- **Tarefa:** {description}\n"
            f"- **ID:** #{result['task_id']}\n\n"
            f"O Kael vai planejar, executar e corrigir sozinho. "
            f"Use `/status_tarefa` para ver o progresso ou `/parar_tarefa` para interromper."
        ),
        "thinking": "Tarefa autônoma iniciada em thread separada.",
        "status": "success"
    }


def status_tarefa(ctx, args, flags):
    """Mostra status da tarefa autônoma atual."""
    if not AVAILABLE or not hasattr(ctx, 'autonomous_engine'):
        return {"response": "⚪ Nenhuma tarefa autônoma ativa.", "thinking": "Engine não inicializada.", "status": "success"}
    
    status = ctx.autonomous_engine.get_status()
    
    if status['status'] == 'idle':
        return {"response": "⚪ Nenhuma tarefa ativa.", "thinking": "Engine ociosa.", "status": "success"}
    
    subtasks_txt = ""
    if 'subtasks' in status and status['subtasks']:
        subtasks_txt = "\n**Subtarefas:**\n"
        for i, s in enumerate(status['subtasks'], 1):
            icon = "✅" if s['status'] == 'completed' else "🔄" if s['status'] == 'running' else "⏳"
            subtasks_txt += f"{icon} {i}. {s['description'][:60]}\n"
    
    return {
        "response": (
            f"📊 **Status da Tarefa #{status['task_id']}**\n"
            f"- **Descrição:** {status['description']}\n"
            f"- **Status:** {status['status'].upper()}\n"
            f"{subtasks_txt}\n"
            f"{'**Resultado:** ' + status['result'] if status.get('result') else ''}\n"
            f"{'**Erro:** ' + status['error'] if status.get('error') else ''}"
        ),
        "thinking": "Status da tarefa consultado.",
        "status": "success"
    }


def parar_tarefa(ctx, args, flags):
    """Para a tarefa autônoma atual."""
    if not AVAILABLE or not hasattr(ctx, 'autonomous_engine'):
        return {"response": "⚪ Nenhuma tarefa para parar.", "thinking": "Engine não inicializada.", "status": "success"}
    
    result = ctx.autonomous_engine.stop_task()
    return {"response": result['message'], "thinking": "Tarefa parada.", "status": "success"}


COMMANDS = {
    "/tarefa": {"handler": tarefa, "desc": "Inicia tarefa autônoma (ex: /tarefa Crie sistema de combate)"},
    "/status_tarefa": {"handler": status_tarefa, "desc": "Mostra progresso da tarefa autônoma"},
    "/parar_tarefa": {"handler": parar_tarefa, "desc": "Interrompe a tarefa autônoma"},
}