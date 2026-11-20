"""
KAEL API SERVER v5.2 - Com Agente Autônomo de Criação
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import time
import threading
from pathlib import Path

BASE_DIR = Path(__file__).parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from core.kael_context import KaelContext
from core.tool_registry import ToolRegistry
from core.autonomous_agent import AutonomousAgent

# Boot
ctx = KaelContext()
registry = ToolRegistry(ctx)
ctx.registry = registry
registry.auto_discover()

# Agente Autônomo
ctx.autonomous_agent = AutonomousAgent(ctx)

app = Flask(__name__)
CORS(app)

# Plugin Bridge
try:
    from core.plugin_bridge import register_routes
    register_routes(app, ctx)
    print("[OK] Plugin Bridge registrado.")
except Exception as e:
    print(f"[AVISO] Plugin Bridge desativado: {e}")

print("\n" + "=" * 60)
print("🚨 [KAEL] API SERVER v5.2 RODANDO NA PORTA 8000 🚨")
print(f"🎮 Projeto: {ctx.project_path}")
print(f"🔧 Registry: {len(registry.tools)} tools | {len(registry.commands)} comandos")
print(f"🤖 Agente Autônomo: {'✅ ATIVO' if ctx.autonomous_agent.active else '⚪ Inativo'}")
print("=" * 60 + "\n")

# Loop do agente autônomo
def autonomous_loop():
    while True:
        if ctx.autonomous_agent.active:
            ctx.autonomous_agent.run_cycle()
        time.sleep(3)

threading.Thread(target=autonomous_loop, daemon=True).start()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "online" if ctx.ollama_online() else "ollama_offline",
        "tools": sorted(registry.tools.keys()),
        "commands": sorted(registry.commands.keys()),
        "autonomous_mode": ctx.autonomous["active"],
        "autonomous_agent": ctx.autonomous_agent.get_status()
    })

@app.route('/historico', methods=['GET'])
def get_historico():
    return jsonify(ctx.load_historico())

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    prompt = data.get('prompt', '').strip()
    if not prompt:
        return jsonify({"error": "Prompt vazio"}), 400
    
    print(f"\n[API] Recebido: {prompt[:80]}...")
    
    if prompt.startswith('/'):
        resultado = registry.dispatch(prompt)
        if resultado:
            hist = ctx.load_historico()
            hist.append({"role": "user", "content": prompt})
            hist.append({"role": "assistant", "content": resultado.get("response", ""),
                         "thinking": resultado.get("thinking", "")})
            ctx.save_historico(hist)
            return jsonify(resultado)
    
    # Conversa normal
    memorias = []
    if ctx.memory is not None:
        try:
            memorias = ctx.memory.search_similar(prompt, limit=3)
        except Exception:
            pass
    
    hist = ctx.load_historico()
    if ctx.compressor is not None:
        contexto = ctx.compressor.build_context(prompt, hist, memorias, ctx.system_prompt)
    else:
        contexto = prompt
    
    resultado = ctx.generate(contexto)
    resposta_final = ctx.process_save_commands(resultado['response'])
    
    hist.append({"role": "user", "content": prompt})
    hist.append({"role": "assistant", "content": resposta_final, "thinking": resultado['thinking']})
    ctx.save_historico(hist)
    
    return jsonify({"response": resposta_final, "thinking": resultado['thinking'], "status": "success"})

@app.route('/stream', methods=['GET', 'POST'])
def stream():
    if request.method == 'GET':
        prompt = request.args.get('prompt', '')
    else:
        prompt = (request.json or {}).get('prompt', '')
    if not prompt:
        return jsonify({"error": "Prompt vazio."}), 400
    resultado = ctx.generate(prompt)
    return jsonify({"response": resultado['response'], "thinking": resultado['thinking'], "status": "success"})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=False)