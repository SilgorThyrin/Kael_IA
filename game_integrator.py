# -*- coding: utf-8 -*-
"""
game_integrator.py - Kael Game Integrator (v3.1)
=================================================
Correcao Parte 1:
  - Removido import kael_core dentro de _corrigir_gap (circular import)
  - Validacao pesada via helper lazy
"""
import os
import re
import json
from datetime import datetime


class GameIntegrator:
    def __init__(self, projeto, base_dir=None, fn_llm=None,
                 fn_enfileirar=None, fn_adicionar_msg=None,
                 fn_validar_lua=None, fn_aguardar_teste=None,
                 fn_estado_jogo=None, descricao_usuario=""):
        self.projeto = str(projeto)
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.fn_llm = fn_llm
        self.fn_enfileirar = fn_enfileirar
        self.fn_adicionar_msg = fn_adicionar_msg
        self.fn_validar_lua = fn_validar_lua
        self.fn_aguardar_teste = fn_aguardar_teste
        self.fn_estado_jogo = fn_estado_jogo
        self.descricao_usuario = descricao_usuario

        self.projeto_dir = os.path.join(self.base_dir, "Projetos", self._slug(projeto))
        self.arquivo_blueprint = os.path.join(self.projeto_dir, "blueprint.json")
        self.arquivo_estado = os.path.join(self.projeto_dir, "game_estado.json")
        self.arquivo_analise = os.path.join(self.projeto_dir, "integracao_analise.json")

    def _slug(self, s):
        s = re.sub(r"[^a-zA-Z0-9_\- ]", "", str(s))
        return s.strip().replace(" ", "_")[:60] or "Jogo"

    def _log(self, msg):
        try:
            print("[INTEGRATOR] " + str(msg))
            if self.fn_adicionar_msg:
                self.fn_adicionar_msg("Sistema", "[Integrator] " + str(msg))
        except Exception:
            pass

    def _validar_pesada_safe(self, codigo):
        """FIX Parte 1: validacao pesada via lazy import (evita circular)."""
        try:
            import kael_engine
            if hasattr(kael_engine, "validar_sintaxe_lua_pesada"):
                return kael_engine.validar_sintaxe_lua_pesada(codigo)
        except Exception as e:
            self._log("validador pesado indisponivel: " + str(e)[:100])
        return codigo, []

    def _coletar_estado_atual(self):
        self._log("Coletando estado atual do jogo...")
        estado = {
            "blueprint": None,
            "game_estado": None,
            "estado_jogo_plugin": None,
            "scripts_existentes": [],
            "objetos_no_mundo": [],
        }

        if os.path.exists(self.arquivo_blueprint):
            try:
                with open(self.arquivo_blueprint, "r", encoding="utf-8") as f:
                    estado["blueprint"] = json.load(f)
            except Exception as e:
                self._log("Erro ao ler blueprint: " + str(e))

        if os.path.exists(self.arquivo_estado):
            try:
                with open(self.arquivo_estado, "r", encoding="utf-8") as f:
                    estado["game_estado"] = json.load(f)
                for etapa in estado["game_estado"].get("etapas", []):
                    for sc in etapa.get("scripts", []):
                        estado["scripts_existentes"].append({
                            "id_tarefa": etapa["id"],
                            "nome": sc,
                            "dominio": etapa.get("dominio", ""),
                            "status": etapa.get("status", ""),
                        })
            except Exception as e:
                self._log("Erro ao ler game_estado: " + str(e))

        if self.fn_estado_jogo:
            try:
                ej = self.fn_estado_jogo()
                if ej:
                    estado["estado_jogo_plugin"] = ej
                    if isinstance(ej, dict):
                        for chave in ["instancias", "partes", "objetos", "instances", "children"]:
                            if chave in ej and isinstance(ej[chave], list):
                                estado["objetos_no_mundo"] = ej[chave][:200]
                                self._log("Lidos " + str(len(estado["objetos_no_mundo"]))
                                          + " objetos (campo: " + chave + ")")
                                break
            except Exception as e:
                self._log("Erro ao ler estado_jogo: " + str(e))

        self._log("Estado coletado: " + str(len(estado["scripts_existentes"]))
                  + " scripts, " + str(len(estado["objetos_no_mundo"]))
                  + " objetos no mundo.")
        return estado

    def _analisar_gaps(self, estado):
        self._log("Analisando gaps (o que falta ou esta quebrado)...")

        resumo_scripts = []
        for sc in estado["scripts_existentes"][:50]:
            resumo_scripts.append("- [" + sc["id_tarefa"] + "] " + sc["nome"])

        objetos_ordenados = sorted(
            estado["objetos_no_mundo"],
            key=lambda o: o.get("y", 0) if isinstance(o, dict) else 0,
            reverse=True
        )

        resumo_objetos = []
        for ob in objetos_ordenados[:60]:
            if isinstance(ob, dict):
                nome = ob.get("nome") or ob.get("name", "?")
                classe = ob.get("classe") or ob.get("class", "?")
                pos = ob.get("posicao") or ob.get("position", "?")
                y = ob.get("y", 0)
                alerta = ""
                if y and isinstance(y, (int, float)) and y > 60:
                    alerta = " [FLUTUANDO]"
                resumo_objetos.append("- " + nome + " (" + classe + ") em " + str(pos) + alerta)
            else:
                resumo_objetos.append("- " + str(ob))

        total_blueprint = 0
        if estado["blueprint"]:
            total_blueprint = estado["blueprint"].get("total_tarefas", 0)

        prompt = (
            "Voce e o INTEGRADOR DO KAEL. Sua funcao e OLHAR o jogo atual\n"
            "e identificar o que falta ou esta quebrado para torna-lo jogavel.\n\n"
            "DESCRICAO DO JOGO (objetivo original):\n"
            + (self.descricao_usuario or "(nao informada)") + "\n\n"
            "BLUEPRINT ORIGINAL: " + str(total_blueprint) + " tarefas planejadas\n\n"
            "SCRIPTS CRIADOS NO JOGO (" + str(len(estado["scripts_existentes"])) + "):\n"
            + "\n".join(resumo_scripts) + "\n\n"
            "OBJETOS NO MUNDO (marcados [FLUTUANDO] estao acima de Y=60):\n"
            + ("\n".join(resumo_objetos) if resumo_objetos else "(nao reportado pelo plugin)") + "\n\n"
            "SUA TAREFA:\n"
            "Analise o que existe e identifique de 3 a 6 GAPS (problemas) que impedem o jogo\n"
            "de ser jogavel de verdade. Priorize:\n"
            "- Objetos marcados [FLUTUANDO] (precisam ser removidos ou movidos pro chao)\n"
            "- SpawnLocation faltando ou player preso\n"
            "- Sistemas desconectados (combate, HUD, spawner)\n"
            "- Scripts com erro de runtime\n\n"
            "Para cada gap, de uma TAREFA DE CORRECAO concreta:\n"
            "- O que fazer\n"
            "- Onde colocar (qual servico do Roblox)\n"
            "- Como testar\n\n"
            "Responda APENAS em JSON:\n"
            "{\n"
            '  "gaps": [\n'
            '    {"id": "gap-1", "problema": "...", "correcao": "...",\n'
            '     "onde": "ServerScriptService", "como_testar": "..."},\n'
            '    {"id": "gap-2", ...}\n'
            "  ]\n"
            "}\n"
            "Responda em portugues."
        )

        try:
            resposta = str(self.fn_llm(prompt, temperatura=0.4))
        except Exception as e:
            self._log("Erro LLM na analise: " + str(e))
            return []

        m = re.search(r"\{[\s\S]*\}", resposta)
        if not m:
            self._log("Nao consegui extrair JSON da resposta.")
            return []

        try:
            dados = json.loads(m.group(0))
        except Exception as e:
            self._log("JSON invalido: " + str(e))
            return []

        gaps = dados.get("gaps", [])
        self._log("Gaps identificados: " + str(len(gaps)))
        for g in gaps:
            self._log("  - " + str(g.get("problema", "?"))[:80])

        try:
            with open(self.arquivo_analise, "w", encoding="utf-8") as f:
                json.dump({
                    "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "gaps": gaps,
                    "total_scripts": len(estado["scripts_existentes"]),
                    "total_objetos": len(estado["objetos_no_mundo"]),
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return gaps

    def _corrigir_gap(self, gap):
        gap_id = gap.get("id", "gap-?")
        problema = gap.get("problema", "")
        correcao = gap.get("correcao", "")
        onde = gap.get("onde", "ServerScriptService")
        como_testar = gap.get("como_testar", "")

        self._log("Corrigindo " + gap_id + ": " + problema[:60])

        prompt = (
            "Voce e o KAEL, engenheiro de jogos Roblox/Luau.\n\n"
            "PROBLEMA IDENTIFICADO:\n" + problema + "\n\n"
            "CORRECAO SOLICITADA:\n" + correcao + "\n\n"
            "ONDE COLOCAR: " + onde + "\n\n"
            "COMO TESTAR:\n" + como_testar + "\n\n"
            "INSTRUCOES:\n"
            "- Gere um script Lua COMPLETO e FUNCIONAL\n"
            "- Use task.wait(), nao wait()\n"
            "- NAO deixe ',]' nem ',}' em tabelas\n"
            "- Certifique-se de que o script e auto-contido\n"
            "- Faca o script printar algo ao iniciar (ex: print('[Fix] OK'))\n"
            "- Retorne APENAS o codigo no formato:\n"
            "<!-- ARQUIVO: NomeDoScript -->\n"
            "```lua\n(codigo)\n```\n"
        )

        try:
            resposta = str(self.fn_llm(prompt, temperatura=0.2))
        except Exception as e:
            self._log("Erro LLM: " + str(e))
            return False

        m = re.search(
            r"<!--\s*ARQUIVO:\s*([A-Za-z0-9_\-\.]+)\s*-->\s*```(?:lua|luau)?\s*\n(.*?)```",
            resposta, re.DOTALL | re.IGNORECASE
        )

        if not m:
            m2 = re.search(r"```(?:lua|luau)?\s*\n(.*?)```", resposta, re.DOTALL)
            if not m2:
                self._log("Nenhum codigo extraido.")
                return False
            nome = "Integrator_" + gap_id + "_Fix"
            codigo = m2.group(1).strip()
        else:
            nome = m.group(1).strip()
            codigo = m.group(2).strip()

        if self.fn_validar_lua:
            try:
                v = self.fn_validar_lua(codigo, tipo_script="Script")
                codigo = v.get("codigo_corrigido", codigo)
            except Exception as e:
                self._log("validar_lua falhou: " + str(e)[:100])

        # FIX Parte 1: validacao pesada via helper lazy (sem circular)
        codigo, erros = self._validar_pesada_safe(codigo)
        if erros:
            self._log("Validador pesado corrigiu: " + str(len(erros)) + " problemas")

        nome_final = "Integrator_" + gap_id + "_" + nome
        try:
            self.fn_enfileirar({
                "tipo": "criar_script",
                "nome": nome_final,
                "codigo": codigo,
                "tipo_script": "Script",
                "testar_automaticamente": True,
                "origem": "integrator",
            })
        except Exception as e:
            self._log("Erro ao enfileirar: " + str(e))
            return False

        if self.fn_aguardar_teste:
            resultado = self.fn_aguardar_teste(nome_final, 60)
            if resultado is None:
                self._log("Timeout no teste de " + nome_final)
                return False
            if not resultado.get("sucesso"):
                self._log("Falhou: " + str(resultado.get("erros", ""))[:150])
                return False

        self._log("OK: " + gap_id + " corrigido")
        return True

    def analisar_e_corrigir(self, max_gaps=6):
        self._log("=== INTEGRACAO INICIADA ===")
        self._log("Projeto: " + self.projeto)

        estado = self._coletar_estado_atual()
        if not estado["scripts_existentes"]:
            self._log("Nenhum script encontrado. Rode /construir_jogo primeiro.")
            return {"status": "sem_scripts", "gaps": []}

        gaps = self._analisar_gaps(estado)
        if not gaps:
            self._log("Nenhum gap identificado. Jogo parece OK.")
            return {"status": "sem_gaps", "gaps": []}

        gaps = gaps[:max_gaps]

        corrigidos = 0
        falharam = 0
        for gap in gaps:
            ok = self._corrigir_gap(gap)
            if ok:
                corrigidos += 1
            else:
                falharam += 1

        self._log("=== INTEGRACAO FINALIZADA ===")
        self._log("Corrigidos: " + str(corrigidos) + "/" + str(len(gaps)))
        self._log("Falharam: " + str(falharam))

        return {
            "status": "concluido",
            "gaps": gaps,
            "corrigidos": corrigidos,
            "falharam": falharam,
        }