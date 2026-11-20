# -*- coding: utf-8 -*-
"""
game_architect.py - Kael Game Architect
========================================
O "cerebro planejador" do Kael. NAO constroi codigo, apenas PLANEJA.

Recebe: genero + descricao (+ lore opcional)
Produz: blueprint.json (arvore hierarquica de tarefas com dependencias)

Filosofia:
  "MMO de 6 reinos" (impossivel de gerar direto)
      ↓ decompoe em dominios
  [world, systems, content, ui, quests]
      ↓ cada um em subsistemas
  world = [terrain, biomes, cities, roads, bridges]
      ↓ cada um em tarefas de 1 script
  terrain = ["criar ground", "adicionar montanhas", "entalhar rios", ...]

Filtros aplicados em v2:
  - Maximo 3 tarefas por subsistema (era 6)
  - Bloqueia tarefas nao-faziveis (gravar audio, vozover, etc)
  - Bloqueia duplicatas do WorldBuilder
  - Forca IDs unicos
"""
import os
import re
import json
import time
from datetime import datetime


class GameArchitect:
    def __init__(self, projeto, genero, descricao="", lore="",
                 base_dir=None, fn_llm=None, fn_adicionar_msg=None,
                 max_dominios=6):
        self.projeto = str(projeto)
        self.genero = str(genero)
        self.descricao = str(descricao)
        self.lore = str(lore)
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.fn_llm = fn_llm
        self.fn_adicionar_msg = fn_adicionar_msg
        self.max_dominios = max_dominios

        self.blueprint = None
        self.projeto_dir = os.path.join(self.base_dir, "Projetos", self._slug(projeto))
        os.makedirs(self.projeto_dir, exist_ok=True)
        self.arquivo_blueprint = os.path.join(self.projeto_dir, "blueprint.json")

    def _slug(self, s):
        s = re.sub(r"[^a-zA-Z0-9_\- ]", "", str(s))
        return s.strip().replace(" ", "_")[:60] or "Jogo"

    def _log(self, msg):
        try:
            print("[ARCHITECT] " + str(msg))
            if self.fn_adicionar_msg:
                self.fn_adicionar_msg("Sistema", "[Architect] " + str(msg))
        except Exception:
            pass

    def _extrair_json(self, resposta):
        texto = str(resposta)
        match = re.search(r'```(?:json)?\s*\n(.*?)```', texto, re.DOTALL)
        if match:
            texto = match.group(1)
        else:
            for abre, fecha in [("{", "}"), ("[", "]")]:
                i = texto.find(abre)
                j = texto.rfind(fecha)
                if i >= 0 and j > i:
                    texto = texto[i:j + 1]
                    break
        try:
            return json.loads(texto)
        except Exception as e:
            self._log("JSON invalido: " + str(e)[:100])
            return None

    def _chamar_llm_retry(self, prompt, temperatura=0.3, max_retries=3):
        for tentativa in range(max_retries):
            try:
                resposta = self.fn_llm(prompt, temperatura=temperatura)
                dados = self._extrair_json(resposta)
                if dados is not None:
                    return dados
                self._log("Tentativa " + str(tentativa + 1) + "/" + str(max_retries) + " falhou (JSON invalido).")
            except Exception as e:
                self._log("Erro LLM tentativa " + str(tentativa + 1) + ": " + str(e))
            time.sleep(1)
        return None

    # --------------------------------------------------------------
    # FASE 1: decompor em dominios
    # --------------------------------------------------------------
    def _decompor_dominios(self):
        self._log("FASE 1/3: Decompondo o jogo em dominios...")
        lore_ctx = ""
        if self.lore:
            lore_ctx = "\nLORE DO MUNDO:\n" + self.lore[:3000] + "\n"

        prompt = (
            "Voce e o ARQUITETO DE JOGOS do KAEL. Sua funcao e PLANEJAR, nao programar.\n\n"
            "JOGO A CONSTRUIR:\n"
            "  Genero: " + self.genero + "\n"
            "  Projeto: " + self.projeto + "\n"
            "  Descricao: " + self.descricao + "\n"
            + lore_ctx + "\n"
            "TAREFA: Decomponha este jogo em DOMINIOS (categorias grandes de trabalho).\n\n"
            "REGRAS:\n"
            "- Maximo de " + str(self.max_dominios) + " dominios\n"
            "- Cada dominio deve ser uma AREA grande e independente\n"
            "- Exemplos: world (terreno/cidades), systems (combate/movimento), "
            "content (inimigos/itens), ui (HUD/menus), audio, economy, quests\n"
            "- Ordem importa: dominios base vem antes (world antes de systems)\n"
            "- Cada dominio deve dizer de quais outros depende\n"
            "- NAO crie dominio 'audio' (o Kael nao consegue gerar audio)\n"
            "- NAO crie dominio 'world' se o jogo for simples (o WorldBuilder ja faz)\n\n"
            "Responda APENAS em JSON:\n"
            "{\n"
            '  "dominios": [\n'
            '    {"nome": "world", "descricao": "...", "prioridade": 1, "depende_de": []},\n'
            '    {"nome": "systems", "descricao": "...", "prioridade": 2, "depende_de": ["world"]}\n'
            "  ]\n"
            "}\n"
            "Responda em portugues."
        )

        dados = self._chamar_llm_retry(prompt, temperatura=0.4)
        if not dados or "dominios" not in dados:
            self._log("LLM falhou. Usando dominios padrao (fallback).")
            dados = {"dominios": [
                {"nome": "systems", "descricao": "Sistemas jogaveis (movimento, combate)", "prioridade": 1, "depende_de": []},
                {"nome": "content", "descricao": "Inimigos, itens, dungeons", "prioridade": 2, "depende_de": ["systems"]},
                {"nome": "ui", "descricao": "Interface, HUD, menus", "prioridade": 3, "depende_de": ["systems"]},
                {"nome": "quests", "descricao": "Missoes e objetivos", "prioridade": 4, "depende_de": ["content"]},
            ]}

        dominios = dados.get("dominios", [])[:self.max_dominios]

        # Filtra dominio 'audio' (impossivel)
        dominios = [d for d in dominios if d.get("nome", "").lower() != "audio"]

        self._log("Dominios planejados: " + ", ".join(d.get("nome", "?") for d in dominios))
        return dominios

    # --------------------------------------------------------------
    # FASE 2: cada dominio em subsistemas
    # --------------------------------------------------------------
    def _decompor_subsistemas(self, dominio):
        self._log("FASE 2/3: Dominio '" + dominio["nome"] + "' -> subsistemas...")
        prompt = (
            "Voce e o ARQUITETO DE JOGOS do KAEL. Estamos planejando:\n"
            "  Jogo: " + self.genero + " (" + self.projeto + ")\n"
            "  Dominio atual: " + dominio.get("nome", "") + " - " + dominio.get("descricao", "") + "\n\n"
            "TAREFA: Decomponha este DOMINIO em SUBSISTEMAS (2 a 4 partes).\n\n"
            "Cada subsistema deve ser uma parte coerente do dominio.\n"
            "Exemplo para 'systems': movement, combat, inventory\n"
            "Exemplo para 'content': enemies, items, dungeons\n\n"
            "Responda APENAS em JSON:\n"
            "{\n"
            '  "subsistemas": [\n'
            '    {"nome": "movement", "descricao": "..."},\n'
            '    {"nome": "combat", "descricao": "..."}\n'
            "  ]\n"
            "}"
        )
        dados = self._chamar_llm_retry(prompt, temperatura=0.4)
        if not dados or "subsistemas" not in dados:
            dados = {"subsistemas": [
                {"nome": dominio["nome"] + "_base", "descricao": "Base do " + dominio.get("nome", "")},
                {"nome": dominio["nome"] + "_extra", "descricao": "Extras do " + dominio.get("nome", "")},
            ]}
        subsistemas = dados.get("subsistemas", [])[:4]
        self._log("  -> " + str(len(subsistemas)) + " subsistemas")
        return subsistemas

    # --------------------------------------------------------------
    # FASE 3: cada subsistema em tarefas pequenas (COM FILTROS)
    # --------------------------------------------------------------
    def _decompor_tarefas(self, dominio, subsistema):
        self._log("FASE 3/3: " + dominio["nome"] + "/" + subsistema["nome"] + " -> tarefas...")

        NAO_FAZIVEL = [
            "gravar", "gravação", "gravacao", "vozover", "voice over", "voiceover",
            "compor música", "compor musica", "gravar audio", "gravar áudio",
            "editar audio", "editar áudio", "fotografar",
            "testar com jogadores", "feedback dos jogadores", "playtest",
            "localizar", "traduzir para", "dublar",
            "gravar video", "editar video", "editar vídeo",
        ]

        DUPLICADO_WORLDBUILDER = [
            "terreno base", "gerar biomas", "criar biomas",
            "criar cidades", "gerar cidades",
            "criar estradas", "gerar estradas",
            "criar pontes", "gerar pontes",
            "castelo central", "criar castelo",
            "criar rios", "gerar rios",
        ]

        prompt = (
            "Voce e o ARQUITETO DE JOGOS do KAEL. Estamos planejando:\n"
            "  Jogo: " + self.genero + "\n"
            "  Dominio: " + dominio["nome"] + "\n"
            "  Subsistema: " + subsistema["nome"] + " (" + subsistema.get("descricao", "") + ")\n\n"
            "TAREFA: Decomponha este SUBSISTEMA em TAREFAS pequenas (2 a 3 no maximo).\n\n"
            "REGRAS CRITICAS (siga TODAS):\n"
            "1. Cada tarefa gera 1 script Lua de 100-300 linhas\n"
            "2. Cada tarefa e testavel em Roblox imediatamente\n"
            "3. Cada tarefa tem criterio mensuravel (ex: 'script roda sem erro')\n"
            "4. NAO inclua: gravar audio, vozover, compor musica, editar video,\n"
            "   playtest com humanos, localizacao, traducao, marketing\n"
            "5. NAO inclua tarefas do WorldBuilder (terreno, biomas, rios,\n"
            "   cidades, estradas, pontes, castelo)\n"
            "6. IDs UNICOS no formato '<dominio>-<subsistema>-N'\n"
            "7. Descricao em UMA frase completa (nao corte no meio!)\n\n"
            "Responda APENAS em JSON:\n"
            "{\n"
            '  "tarefas": [\n'
            '    {"id": "' + dominio["nome"] + "-" + subsistema["nome"] + '-1",\n'
            '     "descricao": "frase completa explicando o que fazer",\n'
            '     "criterio_sucesso": "como verificar que funcionou",\n'
            '     "depende_de": [], "estimativa_min": 15}\n'
            "  ]\n"
            "}"
        )

        dados = self._chamar_llm_retry(prompt, temperatura=0.3)
        if not dados or "tarefas" not in dados:
            return [{
                "id": dominio["nome"] + "-" + subsistema["nome"] + "-1",
                "descricao": "Implementar " + subsistema.get("descricao", subsistema["nome"]),
                "criterio_sucesso": "Script compila e executa sem erro",
                "depende_de": [],
                "estimativa_min": 20,
            }]

        tarefas = dados.get("tarefas", [])[:3]
        filtradas = []

        for i, tar in enumerate(tarefas):
            desc_lower = str(tar.get("descricao", "")).lower()

            # Filtro 1: nao-fazivel
            if any(k in desc_lower for k in NAO_FAZIVEL):
                self._log("  [SKIP] nao-fazivel: " + desc_lower[:60])
                continue

            # Filtro 2: duplicata do WorldBuilder
            if any(k in desc_lower for k in DUPLICADO_WORLDBUILDER):
                self._log("  [SKIP] duplicado com WorldBuilder: " + desc_lower[:60])
                continue

            # Forca ID unico (ignora o que o LLM retornou)
            tar["id"] = dominio["nome"] + "-" + subsistema["nome"] + "-" + str(i + 1)
            tar["descricao"] = str(tar.get("descricao", "")).strip()
            tar["criterio_sucesso"] = str(tar.get("criterio_sucesso", "Script executa sem erro")).strip()

            # Filtra dependencias: so aceita do mesmo dominio-subsistema
            deps_validas = []
            prefixo = dominio["nome"] + "-" + subsistema["nome"]
            for d in tar.get("depende_de", []):
                if isinstance(d, str) and d.startswith(prefixo) and d != tar["id"]:
                    deps_validas.append(d)
            tar["depende_de"] = deps_validas

            filtradas.append(tar)

        self._log("  -> " + str(len(filtradas)) + " tarefas validas (de " + str(len(tarefas)) + " geradas)")
        return filtradas

    # --------------------------------------------------------------
    # PLANEJAMENTO COMPLETO
    # --------------------------------------------------------------
    def planejar(self):
        self._log("Iniciando planejamento completo de '" + self.projeto + "'...")
        dominios = self._decompor_dominios()

        for dom in dominios:
            dom["subsistemas"] = self._decompor_subsistemas(dom)
            for sub in dom["subsistemas"]:
                sub["tarefas"] = self._decompor_tarefas(dom, sub)

        total = sum(
            len(sub.get("tarefas", []))
            for dom in dominios
            for sub in dom.get("subsistemas", [])
        )

        self.blueprint = {
            "projeto": self.projeto,
            "genero": self.genero,
            "descricao": self.descricao,
            "lore": self.lore[:500] if self.lore else "",
            "dominios": dominios,
            "total_tarefas": total,
            "criado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "planejado",
        }

        self._salvar()
        self._log("Blueprint pronto! " + str(total) + " tarefas em " + str(len(dominios)) + " dominios.")
        return self.blueprint

    def _salvar(self):
        try:
            with open(self.arquivo_blueprint, "w", encoding="utf-8") as f:
                json.dump(self.blueprint, f, ensure_ascii=False, indent=2)
            self._log("Salvo em " + self.arquivo_blueprint)
        except Exception as e:
            self._log("Erro ao salvar: " + str(e))

    def resumo(self):
        if not self.blueprint:
            return "Nenhum plano feito ainda."
        linhas = ["=" * 50]
        linhas.append("BLUEPRINT: " + self.blueprint["projeto"])
        linhas.append("Genero: " + self.blueprint["genero"])
        linhas.append("Total: " + str(self.blueprint["total_tarefas"]) + " tarefas")
        linhas.append("=" * 50)
        for dom in self.blueprint["dominios"]:
            deps = ", ".join(dom.get("depende_de", [])) or "nenhuma"
            linhas.append("")
            linhas.append("[" + dom["nome"] + "] depende de: " + deps)
            for sub in dom.get("subsistemas", []):
                linhas.append("  - " + sub["nome"] + " (" + str(len(sub.get("tarefas", []))) + " tarefas)")
                for tar in sub.get("tarefas", []):
                    linhas.append("      [" + tar["id"] + "] " + tar["descricao"][:60])
        return "\n".join(linhas)


# ================================================================
# CLI standalone
# ================================================================
if __name__ == "__main__":
    import sys
    import requests

    if len(sys.argv) < 3:
        print("Uso: python game_architect.py <genero> <nome_projeto> [descricao]")
        print("Ex:  python game_architect.py rpg_mundo_aberto Ecos_Aethelgard 'MMO com 6 reinos'")
        sys.exit(1)

    genero = sys.argv[1]
    nome = sys.argv[2]
    descricao = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""

    def _llm(prompt, temperatura=0.3, modelo="qwen2.5-coder:7b"):
        try:
            r = requests.post("http://127.0.0.1:11434/api/generate", json={
                "model": modelo,
                "prompt": str(prompt),
                "stream": False,
                "options": {"temperature": float(temperatura), "num_ctx": 8192},
            }, timeout=300)
            return r.json().get("response", "")
        except Exception as e:
            return "ERRO: " + str(e)

    arquiteto = GameArchitect(
        projeto=nome,
        genero=genero,
        descricao=descricao,
        fn_llm=_llm,
        fn_adicionar_msg=lambda autor, txt, **kw: print("[" + autor + "] " + txt),
    )

    blueprint = arquiteto.planejar()
    print("\n" + arquiteto.resumo())