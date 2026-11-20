# -*- coding: utf-8 -*-
"""
game_director.py - Kael Game Director v4.1 (Context-Aware + Fix Parte 1)
========================================================================
Correções Parte 1:
  - Removido import kael_engine dentro da funcao (evita circular import)
  - _proxima_etapa_pendente: propaga 'bloqueada' para tarefas filhas
  - Validacao pesada via helper lazy (_validar_pesada_safe)
"""
import os
import re
import json
import time
import threading
from datetime import datetime

MAX_ITERACOES = 500
MAX_TENTATIVAS_ETAPA = 3
TIMEOUT_TESTE = 120
MAX_ERROS_CONSEC = 5


class GameDirector:
    def __init__(
        self, nome_projeto, genero, engine="lua", base_dir=None,
        fn_llm=None, fn_dual=None, fn_enfileirar=None, fn_validar_lua=None,
        fn_adicionar_msg=None, fn_salvar_regra=None, fn_carregar_regras=None,
        fn_aguardar_teste=None, descricao_usuario="", blueprint_path=None,
    ):
        self.nome_projeto = str(nome_projeto)
        self.genero = str(genero)
        self.engine = str(engine)
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.descricao_usuario = str(descricao_usuario) if descricao_usuario else ""

        self.fn_llm = fn_llm
        self.fn_dual = fn_dual
        self.fn_enfileirar = fn_enfileirar
        self.fn_validar_lua = fn_validar_lua
        self.fn_adicionar_msg = fn_adicionar_msg
        self.fn_salvar_regra = fn_salvar_regra
        self.fn_carregar_regras = fn_carregar_regras
        self.fn_aguardar_teste = fn_aguardar_teste

        self.gdd = {}
        self.etapas = []
        self.referencias = []
        self.scripts_criados = []
        self._jogavel = False
        self.rodando = False
        self.pausado = False
        self.status_atual = "parado"
        self.erros_consecutivos = 0
        self.historico_erros = []
        self.thread = None
        self.iteracao = 0

        self.projeto_dir = os.path.join(self.base_dir, "Projetos", self._slug(self.nome_projeto))
        os.makedirs(self.projeto_dir, exist_ok=True)

        # Pasta para salvar o codigo gerado (memoria de contexto)
        self.scripts_dir = os.path.join(self.projeto_dir, "scripts_salvos")
        os.makedirs(self.scripts_dir, exist_ok=True)

        self.arquivo_estado = os.path.join(self.projeto_dir, "game_estado.json")
        self.arquivo_blueprint = os.path.join(self.projeto_dir, "blueprint.json")

        self.blueprint = None
        self.modo = "gdd"

        bp_path = blueprint_path or self.arquivo_blueprint
        if bp_path and os.path.exists(bp_path):
            try:
                self._carregar_blueprint(bp_path)
            except Exception as e:
                print("[DIRECTOR] Falha ao carregar blueprint: " + str(e))
                self.blueprint = None

    def _slug(self, s):
        s = re.sub(r"[^a-zA-Z0-9_\- ]", "", str(s))
        return s.strip().replace(" ", "_")[:60] or "Jogo"

    def _log(self, msg):
        try:
            print("[DIRECTOR] " + str(msg))
            if self.fn_adicionar_msg:
                self.fn_adicionar_msg("Sistema", "[Jogo] " + str(msg))
        except Exception:
            pass

    def _salvar_json(self, nome_arquivo, dados):
        try:
            caminho = os.path.join(self.projeto_dir, nome_arquivo)
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
            return caminho
        except Exception as e:
            print("[DIRECTOR] erro salvando " + nome_arquivo + ": " + str(e))
            return None

    def _salvar_estado(self):
        self._salvar_json("game_estado.json", {
            "nome_projeto": self.nome_projeto,
            "genero": self.genero,
            "modo": self.modo,
            "descricao_usuario": self.descricao_usuario,
            "gdd": self.gdd,
            "etapas": self.etapas,
            "referencias": self.referencias,
            "scripts_criados": self.scripts_criados,
            "jogavel": self._jogavel,
            "status_atual": self.status_atual,
            "iteracao": self.iteracao,
        })

    def _carregar_blueprint(self, path):
        with open(path, "r", encoding="utf-8") as f:
            bp = json.load(f)
        self.blueprint = bp
        self.modo = "blueprint"
        self.gdd = {
            "titulo": bp.get("projeto", self.nome_projeto),
            "genero": bp.get("genero", self.genero),
            "descricao": bp.get("descricao", ""),
        }
        self.etapas = []
        for dom in bp.get("dominios", []):
            for sub in dom.get("subsistemas", []):
                for tar in sub.get("tarefas", []):
                    self.etapas.append({
                        "id": tar.get("id", ""),
                        "titulo": str(tar.get("descricao", ""))[:80],
                        "descricao": tar.get("descricao", ""),
                        "dominio": dom.get("nome", ""),
                        "subsistema": sub.get("nome", ""),
                        "depende_de": tar.get("depende_de", []),
                        "criterio_conclusao": tar.get("criterio_sucesso", ""),
                        "status": tar.get("status", "pendente"),
                        "tentativas": tar.get("tentativas", 0),
                        "scripts": tar.get("scripts", []),
                        "ultimo_erro": tar.get("ultimo_erro", ""),
                    })
        self._log("Blueprint carregado: " + str(len(self.etapas)) + " tarefas.")
        self._salvar_estado()

    def _salvar_blueprint_progresso(self):
        if not self.blueprint:
            return
        status_map = {e["id"]: e for e in self.etapas}
        for dom in self.blueprint.get("dominios", []):
            for sub in dom.get("subsistemas", []):
                for tar in sub.get("tarefas", []):
                    tid = tar.get("id")
                    if tid in status_map:
                        et = status_map[tid]
                        tar["status"] = et["status"]
                        tar["tentativas"] = et["tentativas"]
                        tar["scripts"] = et.get("scripts", [])
                        tar["ultimo_erro"] = et.get("ultimo_erro", "")
        try:
            with open(self.arquivo_blueprint, "w", encoding="utf-8") as f:
                json.dump(self.blueprint, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log("erro salvando progresso do blueprint: " + str(e))

    def _proxima_etapa_pendente(self):
        """
        FIX Parte 1: propaga 'bloqueada' para dependentes.
        Antes: 'bloqueada' contava como dep OK (bug — filho executava com base quebrada).
        Agora: se qualquer dep esta 'bloqueada', este tambem vira 'bloqueada'.
        """
        if self.modo == "blueprint":
            status_por_id = {e["id"]: e["status"] for e in self.etapas}
            for et in self.etapas:
                if et["status"] != "pendente":
                    continue
                dep_ids = et.get("depende_de", [])
                dep_status = [(d, status_por_id.get(d, "pendente")) for d in dep_ids]

                dep_bloqueadas = [d for d, s in dep_status if s == "bloqueada"]
                if dep_bloqueadas:
                    et["status"] = "bloqueada"
                    et["ultimo_erro"] = "Dependencia bloqueada: " + ", ".join(dep_bloqueadas)
                    self._log("Etapa " + et["id"] + " bloqueada (dep quebrada: " + ", ".join(dep_bloqueadas) + ")")
                    continue

                if all(s == "concluida" for d, s in dep_status):
                    return et
            return None
        for et in self.etapas:
            if et.get("status") == "pendente":
                return et
        return None

    # ==========================================
    # FIX Parte 1: validacao pesada sem circular import
    # ==========================================
    def _validar_pesada_safe(self, codigo):
        """
        Chama validar_sintaxe_lua_pesada do kael_engine SE disponivel.
        Import lazy - evita circular import no load do modulo.
        Retorna (codigo_corrigido, lista_erros).
        """
        try:
            import kael_engine
            if hasattr(kael_engine, "validar_sintaxe_lua_pesada"):
                return kael_engine.validar_sintaxe_lua_pesada(codigo)
        except Exception as e:
            self._log("validador pesado indisponivel: " + str(e)[:100])
        return codigo, []

    # ==========================================
    # Contexto de scripts anteriores
    # ==========================================
    def _ler_contexto_scripts(self, dominio_atual):
        contexto = []
        if not os.path.exists(self.scripts_dir):
            return ""

        arquivos = [f for f in os.listdir(self.scripts_dir) if f.endswith(".lua")]
        relevantes = [f for f in arquivos
                      if f.startswith(dominio_atual + "_") or f"_" + dominio_atual + "_" in f]
        relevantes = sorted(
            relevantes,
            key=lambda x: os.path.getmtime(os.path.join(self.scripts_dir, x)),
            reverse=True
        )[:3]

        for arq in relevantes:
            try:
                with open(os.path.join(self.scripts_dir, arq), "r", encoding="utf-8") as f:
                    codigo = f.read()
                if len(codigo) > 1500:
                    codigo = codigo[:1500] + "\n... [cortado]"
                contexto.append("--- Script Anterior: " + arq + " ---\n" + codigo)
            except Exception:
                pass

        if contexto:
            return ("\n\n=== CODIGO JA EXISTENTE NESTE DOMINIO (MANTENHA COMPATIBILIDADE) ===\n"
                    + "\n\n".join(contexto) + "\n=================================================================\n\n")
        return ""

    def _montar_prompt_etapa(self, etapa):
        resumo_gdd = {
            "titulo": self.gdd.get("titulo", ""),
            "genero": self.gdd.get("genero", ""),
            "descricao": self.gdd.get("descricao", ""),
        }
        if self.modo == "blueprint":
            resumo_gdd["dominio"] = etapa.get("dominio", "")
            resumo_gdd["subsistema"] = etapa.get("subsistema", "")

        contexto_codigo = self._ler_contexto_scripts(etapa.get("dominio", ""))
        deps = etapa.get("depende_de", [])
        deps_txt = ", ".join(deps) if deps else "(nenhuma)"

        return (
            "Voce e o KAEL, engenheiro autonomo de jogos " + self.engine + ".\n\n"
            "CONTEXTO DO JOGO:\n" + json.dumps(resumo_gdd, ensure_ascii=False) + "\n\n"
            + contexto_codigo +
            "TAREFA ATUAL (" + str(etapa["id"]) + "):\n"
            "Titulo: " + str(etapa["titulo"]) + "\n"
            "Descricao: " + str(etapa["descricao"]) + "\n"
            "Depende de: " + deps_txt + "\n\n"
            "INSTRUCOES CRITICAS:\n"
            "- NAO crie variaveis ou funcoes com nomes que ja existem no codigo acima.\n"
            "- Se precisar interagir com um sistema anterior, use as variaveis globais "
            "ou Modulos que ja foram criados.\n"
            "- Gere o codigo " + self.engine + " COMPLETO desta tarefa.\n"
            "- Use task.wait(), nao wait().\n"
            "- Retorne CADA arquivo no formato:\n"
            "  <!-- ARQUIVO: NomeDoScript -->\n"
            "  ```lua\n(codigo)\n```\n"
        )

    def _extrair_arquivos(self, resposta):
        texto = str(resposta)
        padrao = re.compile(
            r"<!--\s*ARQUIVO:\s*([A-Za-z0-9_\-\.]+)\s*-->\s*```(?:lua|luau)?\s*\n(.*?)```",
            re.DOTALL | re.IGNORECASE
        )
        arquivos = []
        for nome, codigo in padrao.findall(texto):
            arquivos.append({"nome": nome.strip(), "codigo": codigo.strip()})
        if arquivos:
            return arquivos
        bloco = re.search(r"```(?:lua|luau)?\s*\n(.*?)```", texto, re.DOTALL)
        if bloco:
            return [{"nome": "EtapaScript", "codigo": bloco.group(1).strip()}]
        return []

    def _executar_etapa(self, etapa, erro_anterior=""):
        self.status_atual = "executando_" + str(etapa["id"])
        self._log("Etapa " + str(etapa["id"]) + ": " + str(etapa["titulo"])[:80])

        prompt = self._montar_prompt_etapa(etapa)
        if erro_anterior:
            prompt = ("ATENCAO: a tentativa anterior falhou:\n"
                      + str(erro_anterior)[:500] + "\nCORRIJA.\n\n" + prompt)

        try:
            resposta, sucesso_dual = self.fn_dual(prompt, engine=self.engine)
        except Exception as e:
            self._log("Erro no gerador: " + str(e))
            return False

        if not sucesso_dual:
            return False

        arquivos = self._extrair_arquivos(resposta)
        if not arquivos:
            return False

        scripts_desta_etapa = []
        todos_ok = True
        erro_desta_etapa = ""

        for arq in arquivos:
            nome_script = "Kael_" + str(etapa["id"]).replace("/", "_") + "_" + arq["nome"]
            codigo = arq["codigo"]

            # Salva codigo no disco para memoria futura
            try:
                caminho_salvar = os.path.join(self.scripts_dir, nome_script + ".lua")
                with open(caminho_salvar, "w", encoding="utf-8") as f:
                    f.write(codigo)
            except Exception as e:
                self._log("Aviso: nao salvou script no disco: " + str(e))

            # FIX Parte 1: validacao via injecao + helper lazy (sem circular import)
            if self.fn_validar_lua:
                try:
                    v = self.fn_validar_lua(codigo, tipo_script="Script")
                    codigo = v.get("codigo_corrigido", codigo)
                except Exception as e:
                    self._log("validar_lua falhou: " + str(e)[:100])

            codigo, erros_pesados = self._validar_pesada_safe(codigo)
            if erros_pesados:
                self._log("validador pesado corrigiu " + str(len(erros_pesados)) + " problemas")

            tipo = "criar_localscript" if re.search(
                r"\bUserInputService\b|\bContextActionService\b", codigo
            ) else "criar_script"

            self.fn_enfileirar({
                "tipo": tipo,
                "nome": nome_script,
                "codigo": codigo,
                "tipo_script": "LocalScript" if tipo == "criar_localscript" else "Script",
                "testar_automaticamente": True,
            })
            scripts_desta_etapa.append(nome_script)

            if self.fn_aguardar_teste:
                resultado = self.fn_aguardar_teste(nome_script, TIMEOUT_TESTE)
                if resultado is None:
                    todos_ok = False
                    erro_desta_etapa = "Timeout"
                    self.erros_consecutivos += 1
                else:
                    self.erros_consecutivos = 0
                    if not resultado.get("sucesso"):
                        erro_txt = str(resultado.get("erros", ""))[:300]
                        erro_desta_etapa = erro_txt
                        todos_ok = False

        if todos_ok:
            etapa["status"] = "concluida"
            etapa["scripts"] = scripts_desta_etapa
            for s in scripts_desta_etapa:
                self.scripts_criados.append({"nome": s, "etapa_id": etapa["id"]})
            return True
        etapa["ultimo_erro"] = erro_desta_etapa
        return False

    def _loop(self):
        try:
            while self.rodando and self.iteracao < MAX_ITERACOES:
                while self.pausado and self.rodando:
                    time.sleep(1)
                if not self.rodando:
                    break

                self.iteracao += 1
                self._salvar_estado()
                if self.modo == "blueprint":
                    self._salvar_blueprint_progresso()

                etapa = self._proxima_etapa_pendente()
                if etapa is None:
                    pendentes = sum(1 for e in self.etapas if e.get("status") == "pendente")
                    bloqueadas = sum(1 for e in self.etapas if e.get("status") == "bloqueada")
                    if pendentes == 0 and bloqueadas == 0:
                        self._jogavel = True
                        self._log("JOGO COMPLETO! " + str(len(self.etapas)) + " tarefas concluidas.")
                    else:
                        self._log("Loop encerrado. Pendentes: " + str(pendentes)
                                  + ", bloqueadas: " + str(bloqueadas))
                    break

                erro_anterior = etapa.get("ultimo_erro", "")
                sucesso = self._executar_etapa(etapa, erro_anterior=erro_anterior)

                if not sucesso:
                    etapa["tentativas"] += 1
                    if etapa["tentativas"] >= MAX_TENTATIVAS_ETAPA:
                        etapa["status"] = "bloqueada"
                        self._log("Etapa " + etapa["id"] + " BLOQUEADA apos "
                                  + str(etapa["tentativas"]) + " tentativas")

                if self.erros_consecutivos >= MAX_ERROS_CONSEC:
                    self.status_atual = "erro_plugin_offline"
                    break
                self._salvar_estado()

            self.status_atual = "concluido" if self._jogavel else "encerrado"
        except Exception as e:
            self._log("CRASH no loop: " + str(e))
            self.status_atual = "erro"
        finally:
            self.rodando = False
            try:
                self._salvar_estado()
                if self.modo == "blueprint":
                    self._salvar_blueprint_progresso()
            except Exception:
                pass

    def iniciar(self):
        if self.rodando:
            return False
        self.rodando = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        return True

    def parar(self):
        self.rodando = False

    def pausar(self):
        self.pausado = True

    def continuar(self):
        self.pausado = False

    def status(self):
        return {
            "ativo": self.rodando,
            "modo": self.modo,
            "status": self.status_atual,
            "total_etapas": len(self.etapas),
            "concluidas": sum(1 for e in self.etapas if e.get("status") == "concluida"),
            "bloqueadas": sum(1 for e in self.etapas if e.get("status") == "bloqueada"),
            "jogavel": self._jogavel,
            "iteracao": self.iteracao,
        }