"""
KAEL PLUGIN BRIDGE - Rotas HTTP para o plugin Roblox Studio.
"""
import base64
import time
from collections import deque
from flask import Blueprint, request, jsonify


class PluginBridge:
    def __init__(self):
        self.last_state = None
        self.last_state_time = 0
        self.errors = []
        self.task_queue = deque()
        self.last_completion = None
        self.last_test = None
        self.screenshots = []
        self.limpezas = []

    def enqueue(self, tarefa):
        """Adiciona tarefa na fila para o plugin do Roblox."""
        self.task_queue.append(tarefa)
        print(f"[PLUGIN] Tarefa enfileirada: {tarefa.get('tipo')}")
        return len(self.task_queue)

    def enfileirar_limpeza(self, modo="REMOVER", backup=True, max_distance=50):
        """Atalho para limpeza de flutuantes."""
        return self.enqueue({
            "tipo": "limpar_flutuantes",
            "modo": modo,
            "backup": backup,
            "max_distance": max_distance
        })

    def studio_conectado(self):
        """Verifica se o plugin mandou sinal de vida nos últimos 10s."""
        return (time.time() - self.last_state_time) < 10


def register_routes(app, ctx):
    """Registra todas as rotas do plugin no Flask app e injeta a classe no ctx."""
    # A MÁGICA ACONTECE AQUI: Cria a instância e salva no contexto
    bridge = PluginBridge()
    ctx.plugin_bridge = bridge

    studio_bp = Blueprint("studio", __name__)

    @studio_bp.route("/proxima_tarefa", methods=["GET"])
    def proxima_tarefa():
        bridge.last_state_time = time.time() # Atualiza ping
        if bridge.task_queue:
            tarefa = bridge.task_queue.popleft()
            return jsonify({"status": "ok", "tarefa": tarefa})
        return jsonify({"status": "empty"})

    @studio_bp.route("/tarefa_concluida", methods=["POST"])
    def tarefa_concluida():
        d = request.json or {}
        print(f"[PLUGIN] Tarefa concluída: {d.get('tipo')} sucesso={d.get('sucesso')}")
        if d.get('tipo') == 'teste_script':
            bridge.last_test = d
        bridge.last_completion = d
        return jsonify({"ok": True})

    @studio_bp.route("/estado_jogo", methods=["POST"])
    @studio_bp.route("/visao_jogo", methods=["POST"])
    def estado_jogo():
        bridge.last_state = request.json or {}
        bridge.last_state_time = time.time()
        print(f"[PLUGIN] Mapa atualizado: {bridge.last_state.get('total_instancias', 0)} objetos")
        return jsonify({"ok": True})

    @studio_bp.route("/reportar_erro", methods=["POST"])
    def reportar_erro():
        d = request.json or {}
        bridge.errors.append(d)
        bridge.errors = bridge.errors[-20:]
        print(f"[PLUGIN] Erro: {str(d.get('erro', ''))[:120]}")
        return jsonify({"ok": True})

    @studio_bp.route("/resultado_limpeza", methods=["POST"])
    def resultado_limpeza():
        d = request.json or {}
        bridge.limpezas.append(d)
        print(f"[PLUGIN] Limpeza: detectados={d.get('detectados')} removidos={d.get('removidos')}")
        return jsonify({"ok": True})

    @studio_bp.route("/screenshot", methods=["POST"])
    def screenshot():
        b64 = (request.json or {}).get("imagem_b64", "")
        if b64:
            nome = f"shot_{int(time.time())}.png"
            try:
                (ctx.project_path / "Screenshots").mkdir(exist_ok=True)
                (ctx.project_path / "Screenshots" / nome).write_bytes(base64.b64decode(b64))
                bridge.screenshots.append(str(ctx.project_path / "Screenshots" / nome))
            except Exception as e:
                print(f"[PLUGIN] Falha screenshot: {e}")
        return jsonify({"ok": True})
        
    @studio_bp.route("/studio_status", methods=["GET"])
    def studio_status():
        return jsonify({
            "conectado": bridge.studio_conectado(),
            "fila": len(bridge.task_queue),
            "objetos": (bridge.last_state or {}).get("total_instancias", 0),
            "erros_recentes": bridge.errors[-5:],
        })

    app.register_blueprint(studio_bp)
    print("[REG] Plugin Bridge inicializado e ativo.")