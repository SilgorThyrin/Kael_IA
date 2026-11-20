from flask import Flask, request, jsonify, send_from_directory
import threading
import time
import os
import json
import logging
import requests

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCK_ESTADO = threading.Lock()

# Estado Global
ESTADO_KAEL = {
    "modo_auto": False,
    "modo_rpg": False,
    "ultimo_comando": "",
    "ultima_resposta": "",
    "status": "Ocioso",
    "mensagens_chat": [],
    "fila_roblox": [],
    "estado_jogo": {},
    "ultimo_erro_roblox": ""
}

print("\n" + "="*60)
print("🚨 [KAEL] VERSÃO NOVA DO API_SERVER CARREGADA COM SUCESSO! 🚨")
print("🚨 SE VOCÊ NÃO VÊ ISSO NO TERMINAL, O ARQUIVO ERRADO ESTÁ RODANDO!")
print("="*60 + "\n")

@app.route("/status", methods=["GET"])
def get_status():
    with LOCK_ESTADO:
        return jsonify({
            "status": ESTADO_KAEL["status"],
            "fila_pendente": len(ESTADO_KAEL["fila_roblox"]),
            "modo_auto": ESTADO_KAEL["modo_auto"],
            "modo_rpg": ESTADO_KAEL["modo_rpg"]
        })

@app.route("/comando", methods=["POST"])
def receber_comando():
    data = request.json
    if not data or 'mensagem' not in data:
        return jsonify({"erro": "Formato inválido"}), 400
        
    texto = data['mensagem'].strip()
    print(f"\n[API] 📩 COMANDO RECEBIDO DO CHAT: '{texto}'")
    
    with LOCK_ESTADO:
        ESTADO_KAEL["mensagens_chat"].append({
            "autor": "Você",
            "texto": texto,
            "hora": time.strftime("%H:%M:%S")
        })
        ESTADO_KAEL["status"] = "Processando"
        
        texto_lower = texto.lower()
        
        if texto_lower in ("/teste_conexao", "/test_conexao_roblox"):
            print("[API] 🎯 COMANDO INTERCEPTADO! Criando tarefa de PING para o Roblox.")
            ESTADO_KAEL["fila_roblox"].append({
                "tipo": "ping",
                "nome": "TesteConexao",
                "codigo": "print('[KAEL] 🟢 PONG! Conexão com Python estabelecida com sucesso!')"
            })
            ESTADO_KAEL["ultima_resposta"] = "📡 Comando interceptado! Tarefa de PING enviada para o Roblox Studio. Verifique o Output."
            ESTADO_KAEL["status"] = "Ocioso"
            return jsonify({"status": "sucesso"})
            
        ESTADO_KAEL["ultimo_comando"] = texto

    return jsonify({"status": "processando"})

@app.route("/ultimas_mensagens", methods=["GET"])
def ultimas_mensagens():
    with LOCK_ESTADO:
        msgs = list(ESTADO_KAEL["mensagens_chat"])
        resp = ESTADO_KAEL["ultima_resposta"]
        if resp:
            msgs.append({
                "autor": "Kael",
                "texto": resp,
                "hora": time.strftime("%H:%M:%S")
            })
            ESTADO_KAEL["mensagens_chat"].append({
                "autor": "Kael",
                "texto": resp,
                "hora": time.strftime("%H:%M:%S")
            })
            ESTADO_KAEL["ultima_resposta"] = ""
            
    return jsonify({"mensagens": msgs[-50:], "status": ESTADO_KAEL["status"]})

# ==========================================================
# ROTAS DE COMUNICAÇÃO COM O ROBLOX STUDIO
# ==========================================================
@app.route('/proxima_tarefa', methods=['GET'])
def proxima_tarefa():
    with LOCK_ESTADO:
        if ESTADO_KAEL["fila_roblox"]:
            tarefa = ESTADO_KAEL["fila_roblox"].pop(0)
            print(f"[API] 📤 ENVIANDO TAREFA PARA O ROBLOX: {tarefa.get('tipo')}")
            return jsonify({"status": "ok", "tarefa": tarefa})
        else:
            return jsonify({"status": "ok", "tarefa": None})

@app.route('/tarefa_concluida', methods=['POST'])
def tarefa_concluida():
    print("[API] ✅ Roblox confirmou que executou a tarefa.")
    return jsonify({"status": "ok"})

@app.route('/estado_jogo', methods=['POST'])
def receber_estado_jogo():
    dados = request.json or {}
    with LOCK_ESTADO:
        ESTADO_KAEL["estado_jogo"] = dados
    print(f"[API] 🗺️ Mapa da cena recebido ({dados.get('total_instancias', 0)} instâncias).")
    return jsonify({"status": "ok"})

@app.route('/reportar_erro', methods=['POST'])
def reportar_erro():
    dados = request.json or {}
    origem = dados.get("origem", "Desconhecida")
    erro = dados.get("erro", "")
    print(f"[API] ⚠️ Erro reportado pelo Roblox ({origem}): {erro}")
    with LOCK_ESTADO:
        ESTADO_KAEL["ultimo_erro_roblox"] = erro
    return jsonify({"status": "ok"})

@app.route('/confirmar_etapa', methods=['POST'])
def confirmar_etapa():
    dados = request.json or {}
    print(f"[API] ✅ Etapa confirmada no Studio: {dados.get('descricao', '')}")
    return jsonify({"status": "ok"})

def iniciar_api(porta=8000):
    def rodar():
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        app.run(host='0.0.0.0', port=porta, debug=False, use_reloader=False)
    threading.Thread(target=rodar, daemon=True).start()
    print(f"[API] 🌐 Servidor Flask iniciado em http://127.0.0.1:{porta}")

if __name__ == "__main__":
    iniciar_api(8000)
    print("[API] Sistema rodando. Aguardando comandos...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[API] Encerrando...")