# -*- coding: utf-8 -*-
import os
import re
import json

class RefactorAgent:
    def __init__(self, projeto, base_dir, fn_llm, fn_adicionar_msg, fn_enfileirar):
        self.projeto = projeto
        self.base_dir = base_dir
        self.fn_llm = fn_llm
        self.fn_msg = fn_adicionar_msg
        self.fn_enfileirar = fn_enfileirar
        self.projeto_dir = os.path.join(base_dir, "Projetos", self._slug(projeto))

    def _slug(self, s):
        return re.sub(r"[^a-zA-Z0-9_\- ]", "", str(s)).strip().replace(" ", "_")[:60] or "Jogo"

    def refatorar(self):
        self.fn_msg("Sistema", "[Faxineiro] Iniciando varredura de scripts...")
        pasta_scripts = os.path.join(self.projeto_dir, "scripts_salvos")
        if not os.path.exists(pasta_scripts):
            self.fn_msg("Sistema", "[Faxineiro] Nenhum script salvo encontrado.")
            return

        arquivos = [f for f in os.listdir(pasta_scripts) if f.endswith(".lua")]
        if not arquivos:
            return

        self.fn_msg("Sistema", f"[Faxineiro] Lendo {len(arquivos)} scripts. Isso pode demorar...")

        # Junta o codigo de todos os scripts para a IA ler
        codigo_bruto = ""
        for arq in arquivos[:30]: # Limite para nao estourar o contexto
            with open(os.path.join(pasta_scripts, arq), "r", encoding="utf-8") as f:
                codigo_bruto += f"\n--- {arq} ---\n{f.read()[:1000]}\n"

        prompt = (
            "Voce e o FAXINEIRO DE CODIGO do KAEL. Sua tarefa e refatorar scripts soltos.\n"
            "Abaixo estao os scripts bagunçados que criamos para o jogo:\n"
            f"{codigo_bruto}\n\n"
            "Crie UM UNICO script Lua chamado 'GameCoreModule' que consolide as variaveis "
            "globais repetidas e limpe o codigo morto. "
            "Retorne o codigo completo do Modulo no formato:\n"
            "<!-- ARQUIVO: GameCoreModule -->\n```lua\n(codigo)\n```"
        )

        resposta = self.fn_llm(prompt, temperatura=0.2)
        m = re.search(r"<!--\s*ARQUIVO:\s*([A-Za-z0-9_\-\.]+)\s*-->\s*```(?:lua|luau)?\s*\n(.*?)```", resposta, re.DOTALL | re.IGNORECASE)

        if m:
            codigo_limpo = m.group(2).strip()
            self.fn_msg("Sistema", "[Faxineiro] Codigo refatorado com sucesso! Enviando para o Roblox.")
            self.fn_enfileirar({
                "tipo": "criar_script",
                "nome": "GameCoreModule",
                "codigo": codigo_limpo,
                "tipo_script": "ModuleScript",
                "testar_automaticamente": False
            })
            # Salva o modulo novo
            with open(os.path.join(self.projeto_dir, "GameCoreModule.lua"), "w", encoding="utf-8") as f:
                f.write(codigo_limpo)
        else:
            self.fn_msg("Sistema", "[Faxineiro] A IA falhou em gerar o codigo refatorado.")