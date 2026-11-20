"""
KAEL TOOL REGISTRY v5.3 - HUB unificado com /organizar_jogo
"""
import importlib
import re
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).parent.parent / "tools"


class ToolRegistry:
    def __init__(self, ctx):
        self.ctx = ctx
        self.commands = {}
        self.tools = {}
        self._register_internal_commands()
    
    def _register_internal_commands(self):
        """Registra todos os comandos internos."""
        handlers = {
            '/status': (self._cmd_status, "Status completo do sistema Kael"),
            '/teste_conexao': (self._cmd_teste_conexao, "Ping no Ollama e Studio"),
            '/help': (self._cmd_help, "Lista todos os comandos"),
            '/ajuda': (self._cmd_help, "Lista todos os comandos"),
            '/gerenciar_jogo': (self._cmd_gerenciar_jogo, "Ativa modo autônomo em um projeto"),
            '/parar_gerenciamento': (self._cmd_parar_gerenciamento, "Desativa modo autônomo"),
            '/ver_jogo': (self._cmd_ver_jogo, "Análise estática real do projeto"),
            '/integrar_jogo': (self._cmd_integrar_jogo, "IA analisa e corrige scripts reais"),
            '/refatorar': (self._cmd_refatorar, "IA refatora o maior script"),
            '/construir_jogo': (self._cmd_construir_jogo, "Cria estrutura + GDD do projeto"),
            '/pesquisar_jogos': (self._cmd_pesquisar_jogos, "Pesquisa web de referência"),
            '/limpar_flutuantes': (self._cmd_limpar_flutuantes, "Varredura + remoção em lote"),
            '/resultado_limpeza': (self._cmd_resultado_limpeza, "Resultado da última limpeza"),
            '/corrigir_automaticamente': (self._cmd_corrigir_automaticamente, "Agente autônomo corrige erros"),
            '/criar_automaticamente': (self._cmd_criar_automaticamente, "Agente autônomo CRIA o jogo do zero"),
            '/organizar_jogo': (self._cmd_organizar_jogo, "Analisa e envia limpeza direto ao Studio"),
        }
        
        for cmd, (handler, desc) in handlers.items():
            self.commands[cmd.lower()] = {
                "handler": handler,
                "desc": desc,
                "tool": "core"
            }
    
    def register_module(self, mod):
        """Registra módulo externo."""
        name = getattr(mod, "TOOL_NAME", mod.__name__)
        self.tools[name] = mod
        cmds = getattr(mod, "COMMANDS", {})
        for cmd, info in cmds.items():
            self.commands[cmd.lower()] = {
                "handler": info["handler"],
                "desc": info.get("desc", ""),
                "tool": name,
            }
        print(f"[REG] Tool carregada: {name} ({len(cmds)} comandos)")
    
    def auto_discover(self):
        """Descobre todos os tools/cmd_*.py automaticamente."""
        if not TOOLS_DIR.exists():
            return
        for path in sorted(TOOLS_DIR.glob("cmd_*.py")):
            module_name = f"tools.{path.stem}"
            try:
                mod = importlib.import_module(module_name)
                self.register_module(mod)
            except Exception as e:
                print(f"[REG] ERRO ao carregar {module_name}: {e}")
    
    @staticmethod
    def parse_flags(parts):
        """Parse de flags --engine, --ref, etc."""
        flags = {"engine": "auto", "ref": [], "lote": 50, "desc": ""}
        args = []
        i = 1
        while i < len(parts):
            t = parts[i]
            if t == '--engine' and i + 1 < len(parts):
                flags["engine"] = parts[i + 1].lower()
                i += 2
                continue
            if t == '--lote' and i + 1 < len(parts):
                try:
                    flags["lote"] = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
                continue
            if t in ('--ref', '--exemplos', '--exemplo', '--descricao'):
                is_desc = (t == '--descricao')
                i += 1
                buf = []
                while i < len(parts) and not parts[i].startswith('--'):
                    buf.append(parts[i])
                    i += 1
                raw = ' '.join(buf)
                if is_desc:
                    flags["desc"] = raw
                else:
                    flags["ref"] = [x.strip() for x in re.split(r'[;,]', raw) if x.strip()]
                continue
            args.append(t)
            i += 1
        return args, flags
    
    def dispatch(self, prompt):
        """Dispatch de comandos."""
        parts = prompt.split()
        if not parts:
            return None
        entry = self.commands.get(parts[0].lower())
        if not entry:
            return None
        args, flags = self.parse_flags(parts)
        try:
            return entry["handler"](self.ctx, args, flags)
        except Exception as e:
            return {
                "response": f"[ERRO] Falha no comando `{parts[0]}`: {e}",
                "thinking": f"Exceção no handler: {e}",
                "status": "error"
            }
    
    def help_text(self):
        """Gera texto de ajuda."""
        lines = ["📖 **Comandos disponíveis:**"]
        by_tool = {}
        for cmd, info in self.commands.items():
            by_tool.setdefault(info["tool"], []).append((cmd, info["desc"]))
        for tool, cmds in sorted(by_tool.items()):
            lines.append(f"\n**[{tool}]**")
            for cmd, desc in sorted(cmds):
                lines.append(f"`{cmd}` — {desc}")
        return "\n".join(lines)
    
    # ========== HANDLERS ==========
    
    def _cmd_status(self, ctx, args, flags):
        mem_files = list(ctx.memory_dir.glob('*')) if ctx.memory_dir.exists() else []
        return {
            "response": (
                "✅ **Status do Sistema Kael v5.3**\n"
                f"- **Servidor API:** Online (porta 8000)\n"
                f"- **Ollama:** {'🟢 Online' if ctx.ollama_online() else '🔴 Offline'}\n"
                f"- **Memória Vetorial:** {'🟢 Ativa' if ctx.memory else '🟡 Desativada'}\n"
                f"- **Compressor:** {'🟢 Ativo' if ctx.compressor else '🟡 Desativado'}\n"
                f"- **Game Bridge:** {'🟢 Ativo' if ctx.game_bridge else '🔴 Desativado'}\n"
                f"- **Web Research:** {'🟢 Ativo' if ctx.web_research else '🔴 Desativado'}\n"
                f"- **Plugin Bridge:** {'🟢 Conectado' if ctx.plugin_bridge else '🔴 Desconectado'}\n"
                f"- **Arquivos na Memória:** {len(mem_files)}\n"
                f"- **Projeto Ativo:** `{ctx.project_path.name}`\n"
                f"- **Modo Autônomo:** {'🟢 ATIVO' if ctx.autonomous['active'] else '⚪ Inativo'}"
            ),
            "thinking": "Comando /status executado.",
            "status": "success"
        }
    
    def _cmd_teste_conexao(self, ctx, args, flags):
        ok = ctx.ollama_online()
        studio_ok = ctx.plugin_bridge is not None
        return {
            "response": (
                "📡 **Teste de Conexão**\n"
                f"- Ollama (11434): {'🟢 Respondendo' if ok else '🔴 Offline'}\n"
                "- API Kael (8000): 🟢 Respondendo\n"
                f"- Roblox Studio: {'🟢 Conectado' if studio_ok else '🔴 Desconectado'}"
            ),
            "thinking": "Ping executado.",
            "status": "success" if ok else "error"
        }
    
    def _cmd_help(self, ctx, args, flags):
        return {
            "response": self.help_text(),
            "thinking": "Menu de ajuda.",
            "status": "success"
        }
    
    def _cmd_gerenciar_jogo(self, ctx, args, flags):
        project = args[0] if args else "Ecos_de_Aethelgard"
        ctx.autonomous["active"] = True
        ctx.autonomous["project"] = project
        return {
            "response": f"🤖 **Modo Autônomo ATIVADO** em `{project}`.",
            "thinking": "Estado global alterado.",
            "status": "success"
        }
    
    def _cmd_parar_gerenciamento(self, ctx, args, flags):
        ctx.autonomous["active"] = False
        return {
            "response": "⏹️ **Modo Autônomo DESATIVADO.**",
            "thinking": "Modo autônomo desligado.",
            "status": "success"
        }
    
    def _cmd_ver_jogo(self, ctx, args, flags):
        if not ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        bridge = ctx.game_bridge(str(ctx.project_path))
        report = bridge.full_report()
        if 'erro' in report:
            return {"response": f"⚠️ {report['erro']}", "thinking": "Projeto não encontrado.", "status": "error"}
        scripts_txt = "\n".join([f"- `{s['arquivo']}` ({s['linhas']} linhas)" for s in report['scripts'][:10]]) or "- (nenhum script)"
        prob_txt = "\n".join([f"- ⚠️ [{p['tipo']}] {p['arquivo']}: {p['detalhe']}" for p in report['problemas'][:10]]) if report['problemas'] else "- ✅ Nenhum problema estático detectado"
        return {
            "response": (
                f"👁️ **Análise Real do Projeto: {ctx.project_path.name}**\n"
                f"- **Motor detectado:** {report['motor']}\n"
                f"- **Scripts:** {report['total_scripts']}\n{scripts_txt}\n"
                f"- **Documentos:** {', '.join(report['documentos']) or 'nenhum'}\n"
                f"- **Cenas:** {len(report['cenas'])}\n\n"
                f"**Problemas detectados:**\n{prob_txt}"
            ),
            "thinking": "Análise estática real executada pelo GameBridge.",
            "status": "success"
        }
    
    def _cmd_integrar_jogo(self, ctx, args, flags):
        if not ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        bridge = ctx.game_bridge(str(ctx.project_path))
        scan = bridge.scan_project()
        if 'erro' in scan or not scan['scripts']:
            return {"response": "⚠️ Nenhum script encontrado.", "thinking": "Sem scripts.", "status": "error"}
        trechos = []
        for s in scan['scripts'][:3]:
            texto = (ctx.project_path / s['arquivo']).read_text(encoding='utf-8', errors='ignore')[:2000]
            trechos.append(f"=== {s['arquivo']} ===\n{texto}")
        prompt_ia = (
            f"Analise os scripts do projeto {ctx.project_path.name} (motor: {scan['motor']}). "
            f"Identifique bugs e melhore a integração. Para cada script corrigido, gere o código "
            f"completo dentro da tag: <kael_save filename='Scripts/NOME_fix.ext'>código</kael_save>\n\n"
            + "\n\n".join(trechos)
        )
        resultado = ctx.generate(prompt_ia)
        resposta = ctx.process_save_commands(resultado['response'], save_dir=ctx.project_path)
        return {
            "response": f"🔧 **Integração analisada.** Correções salvas.\n\n{resposta}",
            "thinking": resultado.get('thinking', ''),
            "status": "success"
        }
    
    def _cmd_refatorar(self, ctx, args, flags):
        if not ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        bridge = ctx.game_bridge(str(ctx.project_path))
        scan = bridge.scan_project()
        if 'erro' in scan or not scan['scripts']:
            return {"response": "⚠️ Nenhum script encontrado.", "thinking": "Sem scripts.", "status": "error"}
        maior = max(scan['scripts'], key=lambda s: s['linhas'])
        p = ctx.project_path / maior['arquivo']
        texto = p.read_text(encoding='utf-8', errors='ignore')[:6000]
        novo_nome = f"Scripts/{Path(maior['arquivo']).stem}_refatorado{Path(maior['arquivo']).suffix}"
        prompt_ia = (
            f"Refatore o script abaixo (motor {scan['motor']}) para ficar limpo e modular. "
            f"Salve com: <kael_save filename='{novo_nome}'>código</kael_save>\n\n{texto}"
        )
        resultado = ctx.generate(prompt_ia)
        resposta = ctx.process_save_commands(resultado['response'], save_dir=ctx.project_path)
        return {
            "response": f"♻️ **Refatoração concluída.** Novo arquivo: `{novo_nome}`\n\n{resposta}",
            "thinking": resultado.get('thinking', ''),
            "status": "success"
        }
    
    def _cmd_construir_jogo(self, ctx, args, flags):
        if not ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        genero = args[0] if len(args) > 0 else 'aventura'
        nome = re.sub(r'[^\w\-]', '_', args[1]) if len(args) > 1 else 'Ecos_de_Aethelgard'
        proj_dir = ctx.project_path.parent / nome
        bridge = ctx.game_bridge(str(proj_dir))
        info = bridge.create_project_structure(nome, genero, flags['engine'])
        base_pesquisa = ""
        if flags['ref'] and ctx.web_research:
            base_pesquisa = ctx.web_research().research_genre(genero, flags['ref'])
        gdd_prompt = (
            f"Crie um GDD conciso para um jogo de {genero} chamado {nome} (motor: {info['engine']}). "
            f"Inclua: visão geral, mecânicas principais, progressão, direção de arte e som. "
        )
        if base_pesquisa:
            gdd_prompt += f"\n\nBASE DE PESQUISA REAL:\n{base_pesquisa[:4000]}\n"
        gdd_prompt += f"Salve com: <kael_save filename='Docs/GDD.md'>conteúdo</kael_save>"
        resultado = ctx.generate(gdd_prompt)
        resposta_gdd = ctx.process_save_commands(resultado['response'], save_dir=proj_dir)
        msg = (
            f"🏗️ **Projeto `{nome}` criado!**\n"
            f"- **Motor:** {info['engine']}\n"
            f"- Pastas: {', '.join(info['pastas'])}\n"
            f"- Templates: {', '.join(info['templates']) or 'nenhum'}\n"
        )
        if flags['ref']:
            msg += f"- **Referências pesquisadas:** {', '.join(flags['ref'])}\n"
        msg += f"\n{resposta_gdd}"
        return {"response": msg, "thinking": resultado.get('thinking', ''), "status": "success"}
    
    def _cmd_pesquisar_jogos(self, ctx, args, flags):
        if not ctx.web_research:
            return {"response": "🔴 Web Research indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        genero = args[0] if args else 'aventura'
        exemplos = flags['ref']
        pesquisa = ctx.web_research().research_genre(genero, exemplos)
        if not pesquisa:
            return {"response": "⚠️ Nenhuma informação encontrada.", "thinking": "Pesquisa web retornou vazio.", "status": "error"}
        docs_dir = ctx.project_path / 'Docs'
        if not docs_dir.exists():
            docs_dir = ctx.memory_dir
        genero_slug = re.sub(r'[^\w\-]', '_', genero)
        fname = f"PESQUISA_{genero_slug}.md"
        try:
            (docs_dir / fname).write_text(pesquisa, encoding='utf-8')
        except Exception as e:
            print(f"[ERRO] Ao salvar pesquisa: {e}")
        return {
            "response": f"🌐 **Pesquisa concluída!** Relatório salvo em `{docs_dir.name}/{fname}`.\n\n**Descobertas principais:**\n{pesquisa[:1500]}",
            "thinking": "Pesquisa web real executada.",
            "status": "success"
        }
    
    def _cmd_limpar_flutuantes(self, ctx, args, flags):
        """Envia limpeza direto ao Roblox Studio + salva cópia local."""
        modo = 'ANALISAR' if '--analisar' in args else 'REMOVER'
        backup = '--sem-backup' not in args
        dist = 50
        for i, p in enumerate(args):
            if p == '--dist' and i + 1 < len(args):
                try:
                    dist = int(args[i + 1])
                except ValueError:
                    pass
        
        # Gera o script Lua
        if not ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        
        bridge = ctx.game_bridge(str(ctx.project_path))
        info = bridge.create_floating_cleaner_script(modo=modo, backup=backup, max_distance=dist)
        
        # Lê o script gerado
        script_path = ctx.project_path / "Scripts" / "kael_limpeza_flutuantes.lua"
        if script_path.exists():
            codigo = script_path.read_text(encoding='utf-8')
        else:
            codigo = "-- Script não encontrado"
        
        # Envia direto ao Roblox Studio
        if ctx.plugin_bridge:
            ctx.plugin_bridge.enqueue({
                "tipo": "executar",
                "codigo": codigo,
                "nome": "kael_limpeza_flutuantes",
                "descricao": f"Limpeza de flutuantes ({modo}, backup={backup})"
            })
            return {
                "response": (
                    f"🧹 **Limpeza enviada ao Roblox Studio!**\n"
                    f"- Modo: {modo} | Backup: {'sim' if backup else 'nao'} | Alcance: {dist} studs\n"
                    f"- Script salvo em: `Scripts/kael_limpeza_flutuantes.lua`\n"
                    f"- **Execução:** O plugin vai executar automaticamente no Studio.\n\n"
                    f"Use `/resultado_limpeza` para ver quantos blocos foram removidos."
                ),
                "thinking": "Script enviado ao plugin Roblox + cópia local salva.",
                "status": "success"
            }
        
        # Fallback: só salva local
        return {
            "response": (
                f"🧹 **Script de limpeza gerado:** `Scripts/kael_limpeza_flutuantes.lua`\n"
                f"- Modo: {info['modo']} | Backup: {'sim' if backup else 'nao'} | Alcance: {dist} studs\n\n"
                f"**Studio desconectado.** Cole no Command Bar do Studio para executar."
            ),
            "thinking": "Script salvo localmente (Studio não conectado).",
            "status": "success"
        }
    
    def _cmd_resultado_limpeza(self, ctx, args, flags):
        try:
            if ctx.plugin_bridge and ctx.plugin_bridge.last_completion:
                ult = ctx.plugin_bridge.last_completion
                if ult.get('tipo') == 'limpar_flutuantes':
                    return {
                        "response": (
                            f"🧹 **Última limpeza no Studio:**\n"
                            f"- Detectados: **{ult.get('detectados', 0)}** | Removidos em lote: **{ult.get('removidos', 0)}**\n"
                            f"- Modo: {ult.get('modo')} | Backup: {ult.get('backup')}"
                        ),
                        "thinking": "Resultado real vindo do plugin Roblox.",
                        "status": "success"
                    }
        except:
            pass
        return {"response": "Nenhuma limpeza executada ainda.", "thinking": "Sem resultados.", "status": "success"}
    
    def _cmd_corrigir_automaticamente(self, ctx, args, flags):
        """Ativa o agente autônomo para CORRIGIR erros."""
        if not ctx.autonomous_agent:
            return {"response": "🔴 Agente autônomo não disponível.", "thinking": "Módulo ausente.", "status": "error"}
        
        if not ctx.autonomous_agent.active:
            ctx.autonomous_agent.activate(mode="corrigir")
            try:
                if ctx.plugin_bridge:
                    ctx.plugin_bridge.enqueue({"tipo": "pedir_visao"})
            except:
                pass
            return {
                "response": (
                    "🤖 **Modo Autônomo de CORREÇÃO ATIVADO!**\n\n"
                    "O Kael agora vai:\n"
                    "1. Escanear o jogo automaticamente\n"
                    "2. Detectar blocos flutuantes, erros de script, etc.\n"
                    "3. Corrigir cada problema sozinho\n"
                    "4. Verificar se funcionou e repetir se necessário\n\n"
                    "Aguarde... o Kael está trabalhando no seu jogo."
                ),
                "thinking": "Agente autônomo de correção ativado.",
                "status": "success"
            }
        else:
            status = ctx.autonomous_agent.get_status()
            return {
                "response": (
                    f"🤖 **Agente Autônomo já está ativo!**\n"
                    f"- Modo: {status.get('modo', 'desconhecido')}\n"
                    f"- Iteração: {status['iteracao']}/{status['max_iteracoes']}\n"
                    f"- Tarefas pendentes: {status['tarefas_pendentes']}\n"
                    f"- Tarefas concluídas: {status['tarefas_concluidas']}"
                ),
                "thinking": "Status do agente autônomo.",
                "status": "success"
            }
    
    def _cmd_criar_automaticamente(self, ctx, args, flags):
        """Ativa o agente autônomo para CRIAR um jogo do zero."""
        if not ctx.autonomous_agent:
            return {"response": "🔴 Agente autônomo não disponível.", "thinking": "Módulo ausente.", "status": "error"}
        
        genero = args[0] if args else 'aventura'
        nome = re.sub(r'[^\w\-]', '_', args[1]) if len(args) > 1 else 'NovoJogo'
        engine = flags.get('engine', 'roblox')
        ref = flags.get('ref', [])
        
        if not ctx.autonomous_agent.active:
            ctx.autonomous_agent.activate(mode="criar")
            ctx.autonomous_agent.set_project(genero, nome, engine, ref)
            return {
                "response": (
                    f"🤖 **Modo Autônomo de CRIAÇÃO ATIVADO!**\n\n"
                    f"**Projeto:** `{nome}` ({genero} - {engine})\n"
                    f"**Referências:** {', '.join(ref) if ref else 'nenhuma'}\n\n"
                    f"**Fases do Kael:**\n"
                    f"1. 🔍 Pesquisa de mercado e referências\n"
                    f"2. 📄 Geração do GDD (Game Design Document)\n"
                    f"3. 🏗️ Criação da estrutura de pastas\n"
                    f"4. 💻 Geração dos scripts principais\n"
                    f"5. 🧪 Validação e correção automática\n"
                    f"6. 📦 Envio para o Roblox Studio via plugin\n\n"
                    f"Aguarde... o Kael está construindo seu jogo do zero!"
                ),
                "thinking": "Agente autônomo de criação ativado com projeto configurado.",
                "status": "success"
            }
        else:
            return {
                "response": "🤖 Agente já está ativo. Use `/parar_gerenciamento` antes de iniciar novo projeto.",
                "thinking": "Agente já ativo.",
                "status": "success"
            }
    
    def _cmd_organizar_jogo(self, ctx, args, flags):
        print(f"DEBUG 1 - Tipo do ctx.game_bridge: {type(ctx.game_bridge)}")
        print(f"DEBUG 2 - Tipo do ctx.plugin_bridge: {type(ctx.plugin_bridge)}")
        """Analisa o jogo e envia limpeza direto ao Studio + salva cópia local."""
        if not ctx.plugin_bridge:
            return {
                "response": "🔴 Plugin do Studio não conectado. Abra o Roblox Studio com o plugin ativo.",
                "thinking": "Plugin bridge ausente.",
                "status": "error"
            }
        
        # Verifica se o plugin está conectado recentemente
        if not ctx.plugin_bridge.last_state_time or (time.time() - ctx.plugin_bridge.last_state_time) > 30:
            return {
                "response": "🔴 Studio não enviou estado recente. Clique em 'Mapear Cena' no plugin.",
                "thinking": "Estado do jogo desatualizado.",
                "status": "error"
            }
        
        # Analisa quantos blocos flutuantes existem
        estado = ctx.plugin_bridge.last_state or {}
        instancias = estado.get('instancias', [])
        flutuantes = [obj for obj in instancias if obj.get('y', 0) < -100]
        
        modo = 'ANALISAR' if '--analisar' in args else 'REMOVER'
        backup = '--sem-backup' not in args
        dist = 50
        for i, p in enumerate(args):
            if p == '--dist' and i + 1 < len(args):
                try:
                    dist = int(args[i + 1])
                except ValueError:
                    pass
        
        # Gera o script Lua
        if not ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        
        bridge = ctx.game_bridge(str(ctx.project_path))
        print(f"DEBUG 3 - Tipo da bridge criada: {type(bridge)}")
        print(f"DEBUG 4 - Tipo da funcao cleaner: {type(bridge.create_floating_cleaner_script)}")
        info = bridge.create_floating_cleaner_script(modo=modo, backup=backup, max_distance=dist)
        
        # Lê o script gerado
        script_path = ctx.project_path / "Scripts" / "kael_limpeza_flutuantes.lua"
        if script_path.exists():
            codigo = script_path.read_text(encoding='utf-8')
        else:
            codigo = "-- Script não encontrado"
        
        # Envia direto ao Roblox Studio
        ctx.plugin_bridge.enqueue({
            "tipo": "executar",
            "codigo": codigo,
            "nome": "kael_limpeza_flutuantes",
            "descricao": f"Limpeza de flutuantes ({modo}, backup={backup})"
        })
        
        return {
            "response": (
                f"🗂️ **Organização iniciada!**\n\n"
                f"**Análise:** {len(flutuantes)} blocos flutuantes detectados\n"
                f"- Modo: {modo} | Backup: {'sim' if backup else 'nao'} | Alcance: {dist} studs\n\n"
                f"**Ações:**\n"
                f"1. ✅ Script salvo em `Scripts/kael_limpeza_flutuantes.lua`\n"
                f"2. ✅ Enviado ao Roblox Studio para execução\n"
                f"3. ⏳ Aguardando resultado...\n\n"
                f"Use `/resultado_limpeza` para ver quantos blocos foram removidos."
            ),
            "thinking": f"Análise: {len(flutuantes)} flutuantes. Script enviado ao plugin.",
            "status": "success"
        }