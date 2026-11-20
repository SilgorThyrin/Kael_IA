"""Comandos para interagir com o plugin do Roblox Studio."""
import time

TOOL_NAME = "studio"


def _bridge(ctx):
    return getattr(ctx, "plugin_bridge", None)


def ping_studio(ctx, args, flags):
    b = _bridge(ctx)
    if not b:
        return {"response": "🔴 Plugin Bridge não carregado.", "thinking": "Bridge ausente.", "status": "error"}
    b.enqueue({"tipo": "ping"})
    return {"response": "📡 **Ping enfileirado.** Olhe o Output do Roblox Studio: deve aparecer `🟢 PONG!`",
            "thinking": "Tarefa de ping enfileirada para o plugin.", "status": "success"}


def pedir_visao(ctx, args, flags):
    b = _bridge(ctx)
    if not b:
        return {"response": "🔴 Plugin Bridge não carregado.", "thinking": "Bridge ausente.", "status": "error"}
    b.enqueue({"tipo": "pedir_visao"})
    return {"response": "🗺️ **Varredura solicitada.** O plugin vai mapear o Workspace e enviar para `/visao_jogo`.",
            "thinking": "Tarefa de visão enfileirada.", "status": "success"}


def pedir_print(ctx, args, flags):
    b = _bridge(ctx)
    if not b:
        return {"response": "🔴 Plugin Bridge não carregado.", "thinking": "Bridge ausente.", "status": "error"}
    b.enqueue({"tipo": "pedir_screenshot"})
    return {"response": "📸 **Screenshot solicitado.** (Requer modo Play/F5 no Studio.) Será salvo em `Screenshots/`.",
            "thinking": "Tarefa de screenshot enfileirada.", "status": "success"}


def studio_status(ctx, args, flags):
    b = _bridge(ctx)
    if not b:
        return {"response": "🔴 Plugin Bridge não carregado.", "thinking": "Bridge ausente.", "status": "error"}
    if not b.last_state:
        return {"response": "⚪ **Studio nunca enviou estado.** O plugin está instalado e o Studio aberto?",
                "thinking": "Sem estado recebido.", "status": "success"}
    idade = int(time.time() - b.last_state_time)
    objetos = b.last_state.get("total_instancias", 0)
    scripts = len(b.last_state.get("scripts_servidor", []))
    ultimo_teste = "nenhum"
    if b.last_test:
        ultimo_teste = f"{b.last_test.get('nome_script')}: {'✅' if b.last_test.get('sucesso') else '❌'}"
    return {
        "response": (
            "🎛️ **Status do Roblox Studio**\n"
            f"- **Último heartbeat:** há {idade}s\n"
            f"- **Objetos no Workspace:** {objetos}\n"
            f"- **Scripts de servidor:** {scripts}\n"
            f"- **Último teste:** {ultimo_teste}\n"
            f"- **Erros reportados:** {len(b.errors)}\n"
            f"- **Tarefas na fila:** {len(b.task_queue)}"
        ),
        "thinking": "Estado do plugin consultado via Bridge.",
        "status": "success"
    }


COMMANDS = {
    "/studio_ping": {"handler": ping_studio, "desc": "Ping no plugin do Studio"},
    "/studio_visao": {"handler": pedir_visao, "desc": "Pede varredura do Workspace"},
    "/studio_print": {"handler": pedir_print, "desc": "Pede screenshot (modo Play)"},
    "/studio_status": {"handler": studio_status, "desc": "Estado do plugin/Studio"},
}