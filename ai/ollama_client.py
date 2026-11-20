import json
import requests
from core.configuration import (
    DEFAULT_CONFIG_PATH,
    load_config as load_runtime_config,
    validate_generation_settings,
)

CONFIG_PATH = DEFAULT_CONFIG_PATH

def load_config():
    return load_runtime_config()

def check_ollama_status():
    config = load_config()
    try:
        r = requests.get(f"{config['ollama_url']}/api/tags", timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False

def generate_response(
    prompt: str,
    system_prompt: str = None,
    think: bool = None,
    settings: dict = None,
) -> dict:
    """Gera resposta via STREAMING."""
    config = load_config()
    if settings is not None:
        generation = validate_generation_settings(settings)
        config.update({
            "model_name": generation["model"],
            "temperature": generation["temperature"],
            "max_tokens": generation["max_tokens"],
            "think": generation["think"],
        })

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
        message = "Ollama parou de responder durante a geração."
        return {"response": f"[ERRO] {message}", "thinking": "", "error": message}
    except requests.RequestException as e:
        print(f" ERRO: {e}")
        message = f"Ollama não está respondendo: {e}"
        return {"response": f"[ERRO] {message}", "thinking": "", "error": message}
    except Exception as e:
        print(f" ERRO: {e}")
        message = f"Falha na comunicação com Ollama: {e}"
        return {"response": f"[ERRO] {message}", "thinking": "", "error": message}

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