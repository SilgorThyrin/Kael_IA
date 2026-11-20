"""
KAEL CONTEXT - Contexto central do Kael
Carrega configuração, inicializa módulos opcionais e gerencia estado.
"""
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))


class KaelContext:
    def __init__(self):
        self.config_file = BASE_DIR / "config" / "config.json"
        self.config = {}
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f"[AVISO] Falha ao ler config.json: {e}")
        
        self.system_prompt = self.config.get("system_prompt", "")
        self.ollama_url = self.config.get("ollama_url", "http://127.0.0.1:11434")
        self.model_name = self.config.get("model_name", "qwen3:8b")
        
        # Caminhos de projeto
        projects_root = Path(self.config.get("projects_root", str(BASE_DIR.parent / "arquivos-de-inteligencia" / "Projetos")))
        self.project_path = Path(self.config.get("project_path", str(projects_root / "Ecos_de_Aethelgard")))
        
        # Memória
        self.memory_dir = BASE_DIR.parent / "arquivos-de-inteligencia" / "conhecimento"
        if not self.memory_dir.exists():
            self.memory_dir = BASE_DIR / "kael_knowledge"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Histórico
        self.historico_file = BASE_DIR / "ultimas_mensagens.json"
        
        # Modo autônomo
        self.autonomous = {"active": False, "project": None}
        
        # Módulos opcionais
        self.memory = None
        self.compressor = None
        self.game_bridge = None
        self.web_research = None
        self.plugin_bridge = None
        self.autonomous_agent = None
        self.registry = None
        
        # Tenta importar módulos
        try:
            from core.memory import KaelMemory
            self.memory = KaelMemory()
            print("[OK] Memória vetorial carregada")
        except ImportError as e:
            print(f"[AVISO] Memória vetorial indisponível: {e}")
        
        try:
            from core.context_compressor import ContextCompressor
            self.compressor = ContextCompressor(max_chars=12000)
            print("[OK] Compressor de contexto carregado")
        except ImportError as e:
            print(f"[AVISO] Compressor indisponível: {e}")
        
        try:
            from tools.game_bridge import GameBridge
            self.game_bridge = GameBridge
            print("[OK] Game Bridge carregado")
        except ImportError as e:
            print(f"[AVISO] Game Bridge indisponível: {e}")
        
        try:
            from tools.web_research import WebResearch
            self.web_research = WebResearch
            print("[OK] Web Research carregado")
        except ImportError as e:
            print(f"[AVISO] Web Research indisponível: {e}")
    
    def ollama_online(self):
        """Verifica se o Ollama está respondendo."""
        try:
            import requests
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            return r.status_code == 200
        except:
            return False
    
    def generate(self, prompt):
        """Gera resposta via ollama_client."""
        try:
            from ai.ollama_client import generate_response
            return generate_response(prompt)
        except ImportError as e:
            print(f"[ERRO] ollama_client não encontrado: {e}")
            return {"response": "[ERRO] Cliente Ollama não disponível.", "thinking": ""}
    
    def load_historico(self):
        """Carrega histórico de conversas."""
        if not self.historico_file.exists():
            return []
        try:
            with open(self.historico_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def save_historico(self, historico):
        """Salva histórico (mantém apenas as últimas 50 mensagens)."""
        try:
            with open(self.historico_file, 'w', encoding='utf-8') as f:
                json.dump(historico[-50:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERRO] Ao salvar histórico: {e}")
    
    def process_save_commands(self, response_text, save_dir=None):
        """Intercepta <kael_save> e escreve no disco."""
        import re
        target_dir = (Path(save_dir) if save_dir else self.memory_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        
        pattern = r'<kael_save\s+filename=[\'"]([^\'"]+)[\'"]>(.*?)</kael_save>'
        matches = re.findall(pattern, response_text, re.DOTALL)
        
        saved_files = []
        clean_text = response_text
        
        for filename, content in matches:
            normalized = filename.replace("\\", "/")
            parts = [p for p in normalized.split("/") if p not in ("", ".")]
            is_absolute = normalized.startswith("/") or (
                len(parts[0]) >= 2 and parts[0][1] == ":" if parts else False
            )
            if not parts or ".." in parts or is_absolute:
                clean_text = clean_text.replace(
                    f'<kael_save filename="{filename}">{content}</kael_save>',
                    f"\n[ARQUIVO BLOQUEADO: nome de arquivo inseguro '{filename}']",
                )
                clean_text = clean_text.replace(
                    f"<kael_save filename='{filename}'>{content}</kael_save>",
                    f"\n[ARQUIVO BLOQUEADO: nome de arquivo inseguro '{filename}']",
                )
                continue

            safe_name = Path(*parts)
            filepath = (target_dir / safe_name).resolve()
            if filepath != target_dir and target_dir not in filepath.parents:
                clean_text = clean_text.replace(
                    f'<kael_save filename="{filename}">{content}</kael_save>',
                    f"\n[ARQUIVO BLOQUEADO: caminho fora do diretorio permitido '{filename}']",
                )
                clean_text = clean_text.replace(
                    f"<kael_save filename='{filename}'>{content}</kael_save>",
                    f"\n[ARQUIVO BLOQUEADO: caminho fora do diretorio permitido '{filename}']",
                )
                continue
            
            try:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(content.strip(), encoding='utf-8')
                saved_files.append(str(safe_name))
                
                # Salva na memória vetorial se disponível
                if self.memory:
                    try:
                        self.memory.add_memory(content.strip(), f"arquivo:{safe_name}")
                    except:
                        pass
                
                clean_text = clean_text.replace(f'<kael_save filename="{filename}">{content}</kael_save>', '')
                clean_text = clean_text.replace(f"<kael_save filename='{filename}'>{content}</kael_save>", '')
            except Exception as e:
                clean_text += f"\n\n[ERRO AO SALVAR {safe_name}: {e}]"
        
        if saved_files:
            clean_text += f"\n\n✅ **Sistema:** Arquivos salvos: {', '.join(saved_files)}"
        return clean_text