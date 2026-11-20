# -*- coding: utf-8 -*-
"""
kael_creative.py - Diretor Criativo do Kael
=============================================
Responsabilidades:
  - Base de conhecimento de generos (rpg_medieval, plataforma, fps, terror)
  - Detectar genero do projeto (do lore, do blueprint, ou da descricao)
  - Ler estado atual (o que JA existe) para nao repetir
  - Propor N features novas via LLM, respeitando o escopo do genero
  - Validar cada ideia (nao duplicada, executavel, dentro do genero)
"""
import os
import re
import json


# ==========================================================
# BASE DE CONHECIMENTO DE GENEROS
# ==========================================================
# Curada manualmente. O Kael consulta isso antes de chamar o LLM,
# para dar contexto rico e evitar alucinacao fora do genero.

KNOWLEDGE_BASE = {
    "rpg_medieval": {
        "atmosfera": "epico, magia antiga, reinos em conflito",
        "paleta_cores": ["marrom escuro", "dourado", "verde musgo", "pedra cinza"],
        "materiais_roblox": ["Slate", "Wood", "Cobblestone", "Fabric", "Rock"],
        "estruturas": [
            "castelo com torres", "vila de camponeses", "taverna",
            "torre do mago", "templo antigo", "mina abandonada",
            "portao da cidade", "muralha de pedra",
        ],
        "decoracoes": [
            "tocha na parede", "bandeira de guilda", "barril de madeira",
            "poco no centro da praca", "placa de madeira", "fogueira",
            "estatua de heroi", "carroca",
        ],
        "itens": [
            "espada longa", "escudo redondo", "pocao de vida",
            "moeda de ouro", "pergaminho magico", "chave antiga",
            "armadura de couro", "arco e flecha",
        ],
        "mecanicas": [
            "combate por turnos ou tempo real", "sistema de inventario",
            "quests com NPCs", "crafting (ferreiro, alquimista)",
            "sistema de moedas/economia", "dialogo com NPCs",
            "sistema de XP e level up",
        ],
        "inimigos": ["goblin", "lobo selvagem", "esqueleto", "dragao", "bandido"],
        "npcs": ["ferreiro", "taberneiro", "mercador", "guarda", "mago"],
        "cores_zona": {
            "vila": ["#8b6f47", "#c9a961", "#6b5033"],
            "castelo": ["#4a4a4a", "#8b6f47", "#c9a961"],
            "floresta": ["#2d4a1e", "#4a6b2a", "#8b6f47"],
        },
        "inspiracoes": [
            # THE WITCHER 3
            "Sistema de Contratos: Um quadro de avisos na taverna onde o jogador aceita caçar monstros. Inclui negociar o preço antes de aceitar e usar o 'Senso do Bruxo' (um highlight no ambiente) para rastrear pistas.",
            "Alquimia e Óleos: Preparar poções e óleos para armas antes de lutas contra chefes (precisa de ingredientes e tempo de preparo).",
            
            # SKYRIM
            "Árvore de Habilidades: Três ramos principais (Guerreiro, Mago, Ladino). O jogador ganha pontos ao upar e escolhe onde investir (ex: dano de espada, magia de fogo, furtividade).",
            "Ferraria e Crafting: Bancadas de ferreiro nas vilas para criar armas e armaduras usando minérios coletados.",
            "Palavras de Poder (Shouts): Habilidades especiais encontradas em ruínas antigas que gastam um recurso (cooldown) para usar.",
            
            # CRIMSON DESERT (Ideias gerais já que a busca falhou)
            "Montarias: Cavalos ou criaturas que aumentam a velocidade de viagem entre os reinos.",
            "Clima Dinâmico: Tempestades que reduzem a visão e nevascas que reduzem a velocidade do jogador."
        ]
    },
    "plataforma": {
        "atmosfera": "colorido, agil, desafiador",
        "paleta_cores": ["azul ceu", "verde grama", "amarelo sol", "vermelho vivo"],
        "materiais_roblox": ["Grass", "Plastic", "SmoothPlastic"],
        "estruturas": ["plataformas moveis", "tubos", "checkpoints", "portal final"],
        "decoracoes": ["nuvens", "moedas flutuantes", "estrelas", "cogumelos"],
        "itens": ["moedas", "power-ups", "vidas extras", "chaves"],
        "mecanicas": ["pulo duplo", "wall jump", "dash", "checkpoint"],
        "inimigos": ["slime", "morcego", "espinho", "robo"],
        "npcs": ["guia", "boss final"],
    },
    "fps": {
        "atmosfera": "tenso, competitivo, tatico",
        "paleta_cores": ["cinza industrial", "vermelho alerta", "azul aco"],
        "materiais_roblox": ["Concrete", "Metal", "DiamondPlate"],
        "estruturas": ["mapa de arena", "bases", "corredores", "snipers points"],
        "decoracoes": ["caixas de suprimento", "barricadas", "holofotes"],
        "itens": ["armas", "municao", "granadas", "colete"],
        "mecanicas": ["sistema de tiro", "respawn", "scoreboard", "times"],
        "inimigos": ["jogadores", "bots"],
        "npcs": ["comandante"],
    },
    "terror": {
        "atmosfera": "sombrio, tenso, claustrofobico",
        "paleta_cores": ["preto", "vermelho escuro", "cinza sujo"],
        "materiais_roblox": ["Slate", "Concrete", "Fabric", "Metal"],
        "estruturas": ["mansao abandonada", "hospital", "floresta sombria", "porao"],
        "decoracoes": ["vela", "sangue no chao", "retratos rasgados", "espelho quebrado"],
        "itens": ["lanterna", "bateria", "chave", "bilhete"],
        "mecanicas": ["sistema de folego", "esconder", "perseguicao", "susto"],
        "inimigos": ["fantasma", "monstro", "boneca", "sombra"],
        "npcs": ["sobrevivente"],
    },
    "simulador": {
        "atmosfera": "leve, progressivo, recompensador",
        "paleta_cores": ["cores vivas", "tons pastel"],
        "materiais_roblox": ["Plastic", "SmoothPlastic", "Neon"],
        "estruturas": ["area de coleta", "loja de upgrades", "spawn inicial"],
        "decoracoes": ["placas de buff", "portais de teleporte"],
        "itens": ["minerios", "moedas", "baús"],
        "mecanicas": ["clicar pra coletar", "upgrades", "prestigio", "pets"],
        "inimigos": [],
        "npcs": ["vendedor", "guia tutorial"],
    },
}


# ==========================================================
# PRIORIDADES DE EXPANSAO (ordem de construcao)
# ==========================================================
# Fase 1: estrutura do mundo (o jogador tem pra onde ir?)
# Fase 2: interacao (o jogador pode fazer algo?)
# Fase 3: progressao (o jogador tem motivo pra continuar?)
# Fase 4: polish (o jogo fica bonito?)

ORDEM_EXPANSAO = [
    "estrutura_principal",   # castelo, vila, mapa
    "decoracao_ambiente",    # tochas, arvores
    "item_coletavel",        # moedas, pocoes
    "npc",                   # ferreiro, mercador
    "mecanica",              # inventario, quest
    "inimigo",               # goblin, lobo
    "polish",                # particulas, som
]


class DiretorCriativo:
    def __init__(self, projeto, base_dir, fn_llm, fn_msg=None,
                 genero_hint="", descricao_usuario=""):
        self.projeto = str(projeto)
        self.base_dir = base_dir
        self.fn_llm = fn_llm
        self.fn_msg = fn_msg
        self.genero_hint = (genero_hint or "").strip().lower()
        self.descricao_usuario = (descricao_usuario or "").strip()

        self.dir = os.path.join(base_dir, "Projetos", self._slug(projeto))
        os.makedirs(self.dir, exist_ok=True)

        self.arquivo_ideias = os.path.join(self.dir, "ideias_criativas.json")

        self.genero = None
        self.kb = None

    def _slug(self, s):
        s = re.sub(r"[^a-zA-Z0-9_\- ]", "", str(s))
        return s.strip().replace(" ", "_")[:60] or "Jogo"

    def _log(self, m):
        print("[CREATIVE] " + str(m))
        if self.fn_msg:
            try:
                self.fn_msg("Sistema", "[Criativo] " + str(m))
            except Exception:
                pass

    # ==========================================================
    # 1. DETECCAO DE GENERO
    # ==========================================================
    def _detectar_genero(self):
        if self.genero_hint in KNOWLEDGE_BASE:
            return self.genero_hint

        # Tenta achar no lore / descricao / blueprint
        textos = [
            self.descricao_usuario,
            self._ler_lore(),
        ]
        bp_path = os.path.join(self.dir, "blueprint.json")
        if os.path.exists(bp_path):
            try:
                with open(bp_path, "r", encoding="utf-8") as f:
                    bp = json.load(f)
                textos.append(str(bp.get("genero", "")))
                textos.append(str(bp.get("descricao", "")))
            except Exception:
                pass

        combo = " ".join(textos).lower()

        # Palavras-chave por genero (ordem importa: especifico antes de generico)
        sinais = {
            "rpg_medieval": ["rpg", "medieval", "castelo", "dragao", "espada",
                              "reino", "mago", "guilda", "taverna", "knight"],
            "terror": ["terror", "horror", "assustador", "fantasma",
                        "mansao", "sobrevivencia", "monstro"],
            "fps": ["fps", "shooter", "tiro", "arma", "combate tatico",
                    "first person shooter"],
            "simulador": ["simulador", "simulator", "clicker", "idle",
                          "progressao infinita", "prestigio"],
            "plataforma": ["plataforma", "platformer", "pulo", "obstaculo",
                           "corrida", "runner"],
        }
        for gen, kws in sinais.items():
            for kw in kws:
                if kw in combo:
                    return gen

        # Fallback generico
        return "rpg_medieval"

    def _ler_lore(self):
        path = os.path.join(self.dir, "1_LORE.md")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()[:2000]
        except Exception:
            pass
        return ""

    # ==========================================================
    # 2. ESTADO ATUAL (o que JA existe)
    # ==========================================================
    def _ler_estado_atual(self):
        """Coleta o que ja foi construido, para nao repetir ideias."""
        existentes = {
            "estruturas": [],
            "decoracoes": [],
            "itens": [],
            "mecanicas": [],
            "inimigos": [],
            "npcs": [],
            "nomes_objetos": [],
            "scripts_criados": [],
            "ideias_anteriores": [],
        }

        # game_estado.json: scripts que ja rodaram
        est_path = os.path.join(self.dir, "game_estado.json")
        if os.path.exists(est_path):
            try:
                with open(est_path, "r", encoding="utf-8") as f:
                    ge = json.load(f)
                for et in ge.get("etapas", []):
                    titulo = str(et.get("titulo", "")).lower()
                    if et.get("status") == "concluida":
                        existentes["scripts_criados"].append(titulo[:80])
                        # Classifica pelo nome
                        for cat in ["estruturas", "decoracoes", "itens",
                                    "mecanicas", "inimigos", "npcs"]:
                            if any(p in titulo for p in self._palavras_cat(cat)):
                                existentes[cat].append(titulo)
            except Exception:
                pass

        # blueprint.json: dominios e subsistemas que ja existem
        bp_path = os.path.join(self.dir, "blueprint.json")
        if os.path.exists(bp_path):
            try:
                with open(bp_path, "r", encoding="utf-8") as f:
                    bp = json.load(f)
                for dom in bp.get("dominios", []):
                    for sub in dom.get("subsistemas", []):
                        existentes["scripts_criados"].append(
                            str(sub.get("nome", ""))[:60]
                        )
            except Exception:
                pass

        # estado_jogo do plugin: nomes de objetos no mundo
        # (nao temos acesso direto aqui, mas o Critic ja le. Vamos ler o cache)
        critic_path = os.path.join(self.dir, "critic_ultima_avaliacao.json")
        if os.path.exists(critic_path):
            try:
                with open(critic_path, "r", encoding="utf-8") as f:
                    c = json.load(f)
                sinais = c.get("sinais", {})
                if sinais.get("tem_terreno"):
                    existentes["estruturas"].append("terreno base")
                if sinais.get("tem_spawn"):
                    existentes["estruturas"].append("spawn location")
                if sinais.get("tem_hud"):
                    existentes["mecanicas"].append("hud")
            except Exception:
                pass

        # ideias anteriores (para nao repetir)
        if os.path.exists(self.arquivo_ideias):
            try:
                with open(self.arquivo_ideias, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                for ideia in dados.get("propostas", []):
                    existentes["ideias_anteriores"].append(
                        str(ideia.get("titulo", ""))[:80]
                    )
            except Exception:
                pass

        return existentes

    def _palavras_cat(self, cat):
        mapa = {
            "estruturas": ["castelo", "vila", "casa", "torre", "templo",
                           "portao", "muralha", "mina", "taverna", "praca"],
            "decoracoes": ["tocha", "bandeira", "barril", "poco", "placa",
                           "fogueira", "estatua", "arvore", "flor"],
            "itens": ["espada", "escudo", "pocao", "moeda", "bau", "chave",
                      "armadura", "arco", "pergaminho"],
            "mecanicas": ["inventario", "combate", "quest", "crafting",
                          "economia", "dialogo", "level", "xp", "hud",
                          "movimento", "pulo"],
            "inimigos": ["goblin", "lobo", "esqueleto", "dragao", "bandido",
                         "inimigo", "monstro"],
            "npcs": ["ferreiro", "taberneiro", "mercador", "guarda", "mago",
                     "npc", "vendedor", "guia"],
        }
        return mapa.get(cat, [])

    # ==========================================================
    # 3. PROPOSTA DE IDEIAS (LLM)
    # ==========================================================
    def _montar_prompt_ideias(self, existentes, n=3):
        kb = self.kb
        resumo_existente = self._resumir_existentes(existentes)

        # Lista o que o genero sugere mas ainda NAO existe
        sugestoes = []
        for cat in ["estruturas", "decoracoes", "itens", "mecanicas",
                    "inimigos", "npcs"]:
            for item in kb.get(cat, []):
                if not self._ja_existe(item, existentes[cat]):
                    sugestoes.append(cat + ": " + item)

        sugestoes_txt = "\n".join(sugestoes[:25]) if sugestoes else "(tudo ja feito)"

        # Puxa as inspirações
        inspiracoes = kb.get("inspiracoes", [])
        inspiracoes_txt = "\n".join("- " + i for i in inspiracoes) if inspiracoes else "(nenhuma)"

        return (
            "Voce e o DIRETOR CRIATIVO do KAEL. Sua funcao e OLHAR o jogo atual\n"
            "e propor as PROXIMAS features mais uteis e interessantes.\n\n"
            "PROJETO: " + self.projeto + "\n"
            "GENERO: " + self.genero + "\n"
            "ATMOSFERA: " + kb.get("atmosfera", "") + "\n\n"
            "O QUE JA EXISTE NO JOGO:\n" + resumo_existente + "\n\n"
            "ELEMENTOS TIPICOS DO GENERO QUE AINDA NAO EXISTEM:\n"
            + sugestoes_txt + "\n\n"
            "INSPIRACOES DE JOGOS DE SUCESSO (Witcher, Skyrim, etc):\n"
            + inspiracoes_txt + "\n\n"
            "TAREFA:\n"
            "Proponha " + str(n) + " features NOVAS para adicionar ao jogo.\n"
            "Use as INSPIRACOES acima como base, mas adapte para a realidade\n"
            "de um jogo Roblox feito de Parts e Scripts (ex: 'Senso do Bruxo'\n"
            "pode ser um script que pinta as pistas de amarelo por 5 segundos).\n"
            "Cada feature deve ser:\n"
            "  - Uma coisa concreta e construivel (nao 'deixar mais divertido')\n"
            "  - Dentro do genero " + self.genero + "\n"
            "  - Executavel via script Lua\n"
            "  - Diferente do que ja existe\n"
            "  - Ordenada por impacto (o que mais melhora o jogo primeiro)\n\n"
            "Responda APENAS em JSON:\n"
            "{\n"
            '  "ideias": [\n'
            '    {"titulo": "Taverna com Quadro de Contratos",\n'
            '     "categoria": "estrutura",\n'
            '     "descricao": "Construir uma taverna de madeira com um quadro onde o jogador pode aceitar missoes",\n'
            '     "impacto": "alto",\n'
            '     "complexidade": "media"}\n'
            "  ],\n"
            '  "raciocinio": "por que essas ideias e nessa ordem"\n'
            "}\n"
            "Categorias validas: estrutura, decoracao, item, mecanica, "
            "inimigo, npc, polish.\n"
            "Responda em portugues."
        )

    def _ja_existe(self, item, lista_existentes):
        """Verifica fuzzy se o item ja esta na lista."""
        item_lower = item.lower()
        for ex in lista_existentes:
            ex_lower = ex.lower()
            # Match por palavra-chave principal
            palavras = [p for p in item_lower.split() if len(p) > 3]
            if palavras and all(p in ex_lower for p in palavras[:2]):
                return True
        return False

    def _resumir_existentes(self, existentes):
        linhas = []
        for cat, items in existentes.items():
            if cat in ("nomes_objetos", "scripts_criados", "ideias_anteriores"):
                continue
            if items:
                linhas.append(cat + ": " + ", ".join(items[:5]))
        if existentes["scripts_criados"]:
            linhas.append("scripts: " + ", ".join(existentes["scripts_criados"][:5]))
        if existentes["ideias_anteriores"]:
            linhas.append("ideias ja propostas: "
                          + ", ".join(existentes["ideias_anteriores"][:5]))
        return "\n".join(linhas) if linhas else "(projeto vazio, so terreno e spawn)"

    # ==========================================================
    # 4. VALIDACAO DE IDEIAS
    # ==========================================================
    def _validar_ideia(self, ideia, existentes):
        titulo = str(ideia.get("titulo", "")).strip()
        descricao = str(ideia.get("descricao", "")).strip()
        categoria = str(ideia.get("categoria", "")).strip().lower()

        cats_validas = {
            "estrutura", "decoracao", "item", "mecanica",
            "inimigo", "npc", "polish",
        }
        if categoria not in cats_validas:
            return False, "categoria invalida"
        if not titulo or not descricao:
            return False, "titulo/descricao vazios"
        if len(titulo) < 3 or len(titulo) > 100:
            return False, "titulo fora do tamanho"
        if len(descricao) < 10 or len(descricao) > 500:
            return False, "descricao fora do tamanho"

        # Anti-duplicata (por titulo)
        if titulo.lower() in [i.lower() for i in existentes["ideias_anteriores"]]:
            return False, "duplicata de ideia anterior"

        # Anti-fora-do-genero: verificar se tem alguma palavra do genero
        kb = self.kb
        palavras_genero = set()
        for cat in ["estruturas", "decoracoes", "itens", "mecanicas",
                    "inimigos", "npcs"]:
            for item in kb.get(cat, []):
                palavras_genero.update(item.lower().split())

        texto_ideia = (titulo + " " + descricao).lower()
        if palavras_genero and not any(p in texto_ideia for p in palavras_genero):
            return False, "parece fora do genero " + self.genero

        return True, "ok"

    # ==========================================================
    # 5. API PUBLICA
    # ==========================================================
    def inicializar(self):
        self.genero = self._detectar_genero()
        self.kb = KNOWLEDGE_BASE.get(self.genero, KNOWLEDGE_BASE["rpg_medieval"])
        self._log("Genero detectado: " + self.genero)
        return self.genero

    def propor_ideias(self, n=3):
        if not self.genero or not self.kb:
            self.inicializar()

        existentes = self._ler_estado_atual()
        self._log("Estado atual: " + self._resumir_existentes(existentes).replace("\n", " | ")[:200])

        prompt = self._montar_prompt_ideias(existentes, n=n)

        try:
            resp = str(self.fn_llm(prompt, temperatura=0.7))
        except Exception as e:
            self._log("LLM falhou: " + str(e)[:150])
            return []

        m = re.search(r"\{[\s\S]*\}", resp)
        if not m:
            self._log("resposta sem JSON")
            return []

        try:
            dados = json.loads(m.group(0))
        except Exception as e:
            self._log("JSON invalido: " + str(e)[:100])
            return []

        ideias_raw = dados.get("ideias", [])
        if not isinstance(ideias_raw, list):
            return []

        # Valida
        ideias_validas = []
        rejeitadas = []
        for ideia in ideias_raw[:n + 2]:
            if not isinstance(ideia, dict):
                continue
            ok, motivo = self._validar_ideia(ideia, existentes)
            if ok:
                ideias_validas.append({
                    "titulo": str(ideia.get("titulo", ""))[:100],
                    "categoria": str(ideia.get("categoria", "")).lower(),
                    "descricao": str(ideia.get("descricao", ""))[:500],
                    "impacto": str(ideia.get("impacto", "medio"))[:20],
                    "complexidade": str(ideia.get("complexidade", "media"))[:20],
                })
            else:
                rejeitadas.append(str(ideia.get("titulo", "?"))[:60] + " (" + motivo + ")")

        if rejeitadas:
            for r in rejeitadas:
                self._log("REJEITADA: " + r)

        # Salva ideias propostas (para nao repetir depois)
        if ideias_validas:
            self._salvar_ideias(ideias_validas)

        self._log("Propostas: " + str(len(ideias_validas)) + " validas de "
                  + str(len(ideias_raw)) + " geradas")
        for i in ideias_validas:
            self._log("  [" + i["categoria"] + "/" + i["impacto"] + "] " + i["titulo"])

        return ideias_validas[:n]

    def _salvar_ideias(self, novas):
        try:
            dados = {"propostas": []}
            if os.path.exists(self.arquivo_ideias):
                with open(self.arquivo_ideias, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    if not isinstance(dados.get("propostas"), list):
                        dados["propostas"] = []
            dados["propostas"].extend(novas)
            dados["propostas"] = dados["propostas"][-50:]
            with open(self.arquivo_ideias, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log("erro salvando ideias: " + str(e)[:100])