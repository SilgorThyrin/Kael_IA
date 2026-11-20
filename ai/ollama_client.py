import json
import sys
import requests
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.json"

def load_config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERRO] Não foi possível ler config.json: {e}")
        return {
            "ollama_url": "http://127.0.0.1:11434",
            "model_name": "qwen3:8b",
            "temperature": 0.7,
            "max_tokens": 2048
        }

def check_ollama_status():
    config = load_config()
    try:
        r = requests.get(f"{config['ollama_url']}/api/tags", timeout=3)
        return r.status_code == 200
    except requests.exceptions.ConnectionError:
        return False

def generate_response(prompt: str, system_prompt: str = None, think: bool = None) -> dict:
    """Gera resposta via STREAMING."""
    config = load_config()

    if not check_ollama_status():
        return {"response": "[ERRO] Ollama não está respondendo.", "thinking": ""}

    if think is None:
        think = config.get("think", True)

    payload = {
        "model": config["model_name"],
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": config.get("temperature", 0.7),
            "num_predict": config.get("max_tokens", 2048),
            "think": think
        }
    }

    if system_prompt:
        payload["system"] = system_prompt
    elif config.get("system_prompt"):
        payload["system"] = config["system_prompt"]

    try:
        print(f"[KAEL] Gerando com {config['model_name']} (streaming)... ", end="", flush=True)

        response = requests.post(
            f"{config['ollama_url']}/api/generate",
            json=payload,
            stream=True,
            timeout=(10, 120)
        )
        response.raise_for_status()

        thinking_parts = []
        response_parts = []
        dots = 0

        for line in response.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue

            if chunk.get("thinking"):
                thinking_parts.append(chunk["thinking"])
            if chunk.get("response"):
                response_parts.append(chunk["response"])
                dots += 1
                if dots % 30 == 0:
                    print(".", end="", flush=True)
            if chunk.get("done"):
                break

        print(" OK!")
        return {
            "response": "".join(response_parts),
            "thinking": "".join(thinking_parts)
        }

    except requests.exceptions.Timeout:
        print(" TIMEOUT!")
        return {"response": "[ERRO] Ollama parou de responder durante a geração.", "thinking": ""}
    except Exception as e:
        print(f" ERRO: {e}")
        return {"response": f"[ERRO] Falha na comunicação: {e}", "thinking": ""}

if __name__ == "__main__":
    print("=" * 40)
    print("TESTE DE CONEXÃO DO KAEL (STREAMING)")
    print("=" * 40)
    if check_ollama_status():
        print("✅ Ollama está online!")
        resultado = generate_response("Explique em 1 frase o que é IA.")
        print(f"\n🧠 PENSAMENTO:\n{resultado['thinking']}")
        print(f"\n🤖 RESPOSTA:\n{resultado['response']}")
    else:
        print("❌ Ollama está OFFLINE.")
    print("=" * 40)