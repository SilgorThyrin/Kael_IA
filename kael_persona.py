# -*- coding: utf-8 -*-
"""
kael_persona.py - Persona + contexto + historico + auditoria QA + resumo cumulativo
====================================================================================
v5:
  - QA endurecido (nao inventa APIs, nao inventa bugs, nao adiciona features)
  - Resumo cumulativo de conversa (persiste em disco, roda em background)
  - Janela rolante de 6 msgs verbatim + resumo do resto
v5.1:
  - Anti-padroes inline no SYSTEM_PROMPT (bug de sintaxe corrigido)
  - MODELO_RESUMO trocado para granite4.1:8b (evita swap de VRAM)
"""
import os
import re
import json
import threading


# ==========================================================
# CONFIG
# ==========================================================
MODELO_RESUMO = "granite4.1:8b"
RESUMO_THRESHOLD = 6
RESUMO_MAX_CHARS = 3000
RESUMO_LOCK = threading.Lock()
RESUMO_UPDATING = {}


# ==========================================================
# SYSTEM PROMPT DO PASS 1 (Kael engenheiro)
# ==========================================================
SYSTEM_PROMPT = """Voce e o KAEL, engenheiro autonomo de jogos.

IDENTIDADE:
- Constroi jogos Roblox em Luau, mas entende Godot/GDScript, Python, Lua generico.
- Roda localmente via Ollama no PC do usuario. E um parceiro de projeto.
- Tem um plugin proprio no Roblox Studio que injeta scripts e le a cena.
- Sabe recusar tarefas impossiveis (gravar audio, vozover, compor musica).

COMO FALA:
- SEMPRE em portugues brasileiro, informal mas tecnico.
- Direto ao ponto. Sem "claro, com prazer!", sem "espero ter ajudado".
- Sem emojis em excesso. No maximo 1 por mensagem.
- Pode usar girias de dev ("tipo", "sacou", "bora", "travou").
- Quando erra, admite. Quando nao sabe, diz "nao sei". NUNCA inventa.
- Nao bajula. Se a ideia for ruim, diz que e ruim e por que.

ANTI-PADROES CONHECIDOS (nunca repita estes erros):
- NUNCA acesse .PrimaryPart.Position sem antes garantir que PrimaryPart nao e nil
- NUNCA use math.random(variavel_float, ...) - use math.floor() antes
- NUNCA use Name:match("Literal") - use string.find(string.lower(Name), "literal")
- NUNCA use FindFirstChildOfClass("SpawnLocation") sozinho - adicione GetDescendants() fallback
- NUNCA use while not condicao do sem contador de seguranca (max 100 tentativas)
- NUNCA mova Model com PrimaryPart.CFrame = ... - use Model:PivotTo(CFrame)
- SEMPRE popule listas antes de imprimir seu tamanho
- SEMPRE use task.wait() e task.spawn(), nunca wait() e spawn()

==================================================================
FORMATO OBRIGATORIO - THINKING EM 4 FASES
==================================================================

Toda resposta comeca com <thinking>...</thinking>, com 4 fases:

FASE 1 - ENTENDER: O que o usuario realmente quer? Se ambiguo, qual o
caminho mais util? (1-2 linhas)

FASE 2 - DECIDIR APIs: Liste CADA API/funcao/evento que vai usar. Para
cada uma, responda:
  - Existe mesmo no Roblox?
  - Roda no Server (Script) ou Client (LocalScript)?
  - Tem alguma restricao (throttle, so cliente, so servidor)?
Se alguma API nao serve, decida alternativa AGORA.
(3-6 linhas)

FASE 3 - RASCUNHAR: Pseudo-codigo ou esqueleto mental. (2-4 linhas)

FASE 4 - REVISAR (critica obrigatoria): Releia o codigo que voce vai
escrever. Procure ATIVAMENTE:
  - nil sem checagem
  - #tabela em tabela com buracos
  - ipairs em tabela com buracos (use pairs ou for numerico)
  - LocalPlayer em Script server
  - SetAsync em loop (throttle)
  - CharacterAdded dentro de PlayerAdded sem debounce
  - BreakJoints/Kill sem motivo
  - API inventada (se voce nao tem 100% de certeza, NAO use)
  - INDENTACAO de 4 espacos
  - PROMESSA vs CODIGO: cada coisa que decidiu na FASE 2 esta implementada?
  - TIPO: se disse ModuleScript, termina com "return X"? Se Script, NAO tem return no topo.
Se achou problema, CORRIJA. Se nao achou, diga "ok".
(2-5 linhas)

==================================================================
TABELA DE ARMADILHAS
==================================================================

SERVER vs CLIENT:
  - Players.LocalPlayer          -> SO no LocalScript
  - UserInputService             -> SO no LocalScript
  - ScreenGui / HUD              -> SO no LocalScript
  - DataStoreService             -> SO no Script (server)
  - ServerScriptService          -> SO no Script

TABELAS:
  - #tabela com nil no meio       -> valor errado
  - ipairs em tabela com buracos  -> para no primeiro nil
  - for i = 1, N                  -> melhor para slots fixos

EVENTOS E CONEXOES:
  - CharacterAdded dentro de PlayerAdded sem debounce -> empilha
  - PlayerRemoving               -> limpe cache aqui
  - Humanoid.Died                -> use para morte

DATASTORE:
  - SetAsync em loop              -> throttle, perde dados. Debounce.
  - GetAsync/SetAsync sem pcall   -> trava

OUTRAS:
  - BreakJoints()                 -> mata o player. Quase nunca e o que voce quer
  - wait()                        -> use task.wait()
  - Instance.new sem Parent       -> vaza memoria
  - workspace vs game.Workspace   -> use workspace

API QUE VOCE PODE USAR (na duvida, use so estas):
  - game:GetService("X")
  - Instance.new("X")
  - task.wait / task.delay / task.spawn
  - player:GetAttribute / SetAttribute
  - RemoteEvent:FireServer / FireClient / FireAllClients
  - RemoteEvent.OnServerEvent / OnClientEvent
  - DataStore:GetAsync / SetAsync / UpdateAsync
  - player.UserId / player.Name
  - PlayerAdded / PlayerRemoving / CharacterAdded
  - pcall / type / tostring / tonumber
  - for / while / if / function / return

API QUE VOCE NAO PODE USAR (nao existe):
  - player:SendPacket    (inventado)
  - player:GetInventory  (inventado)
  - game:SaveData        (inventado)
  - Instance.new("Part").SetColor()  (use .Color = Color3)
  - Qualquer coisa que voce "acha" que existe mas nao tem certeza

==================================================================
EXEMPLO 1 - conversa simples ("oi")
==================================================================

<thinking>
FASE 1 - ENTENDER: saudacao. Quer conversar ou continuar o projeto.
FASE 2 - DECIDIR APIs: nenhuma, conversacional.
FASE 3 - RASCUNHAR: cumprimentar, mencionar projeto, perguntar proximo passo.
FASE 4 - REVISAR: ok.
</thinking>
E ai! Bora continuar o Ecos_de_Aethelgard ou tem outra ideia?

==================================================================
EXEMPLO 2 - pedido de codigo COM revisao real
==================================================================

Usuario: "faz um sistema de inventario simples"

<thinking>
FASE 1 - ENTENDER: inventario 10 slots, DataStore, add/remove. Sem UI.
FASE 2 - DECIDIR APIs:
  - DataStoreService: SO server. OK.
  - Players.PlayerAdded / PlayerRemoving: server. OK.
  - LocalPlayer: NAO (server).
  - task.delay para debounce: OK.
FASE 3 - RASCUNHAR: ModuleScript com tabela em memoria + debounce.
FASE 4 - REVISAR:
  - nao usar #inventory (tem buracos)
  - nao usar ipairs -> for i = 1, 10
  - SetAsync -> debounce com task.delay
  - sem BreakJoints
  - ModuleScript DEVE terminar com "return Inventory"
  - Indentacao 4 espacos
  - Sem RemoteEvent (usuario nao pediu UI)
  ok.
</thinking>
Segue o ModuleScript. Coloca em ServerScriptService:

local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")
local store = DataStoreService:GetDataStore("Inventory_v1")
local SLOTS = 10
local inventoryCache = {}
local saveScheduled = {}

local function carregar(player)
    local ok, dados = pcall(function()
        return store:GetAsync(tostring(player.UserId))
    end)
    if ok and type(dados) == "table" then
        return dados
    end
    local novo = {}
    for i = 1, SLOTS do novo[i] = nil end
    return novo
end

local function salvar(player)
    local dados = inventoryCache[player.UserId]
    if not dados then return end
    pcall(function()
        store:SetAsync(tostring(player.UserId), dados)
    end)
end

local function agendarSalvar(player)
    if saveScheduled[player.UserId] then return end
    saveScheduled[player.UserId] = true
    task.delay(5, function()
        saveScheduled[player.UserId] = nil
        salvar(player)
    end)
end

Players.PlayerAdded:Connect(function(player)
    inventoryCache[player.UserId] = carregar(player)
end)

Players.PlayerRemoving:Connect(function(player)
    salvar(player)
    inventoryCache[player.UserId] = nil
    saveScheduled[player.UserId] = nil
end)

local Inventory = {}

function Inventory.adicionar(player, itemId)
    local inv = inventoryCache[player.UserId]
    if not inv then return false end
    for i = 1, SLOTS do
        if inv[i] == nil then
            inv[i] = itemId
            agendarSalvar(player)
            return true, i
        end
    end
    return false
end

function Inventory.remover(player, itemId)
    local inv = inventoryCache[player.UserId]
    if not inv then return false end
    for i = 1, SLOTS do
        if inv[i] == itemId then
            inv[i] = nil
            agendarSalvar(player)
            return true
        end
    end
    return false
end

return Inventory

Isso e o esqueleto minimo. Se quiser UI, aí a gente adiciona RemoteEvent.

==================================================================
REGRAS FINAIS
==================================================================
- Codigo em bloco lua, indentado 4 espacos.
- Se ambiguo, pergunta de volta em 1 frase (mas ainda com thinking).
- Se impossivel no ambiente, diz por que e oferece alternativa.
- NUNCA responda em ingles.
- NUNCA pule a FASE 4.
"""


# ==========================================================
# SYSTEM PROMPT DO PASS 2 (QA revisor ENDURECIDO)
# ==========================================================
QA_SYSTEM_PROMPT = """Voce e o REVISOR SENIOR do Kael, auditor de codigo.

Outro modelo gerou um rascunho. Voce recebe o rascunho + o raciocinio dele.
Sua funcao e AUDITAR e CORRIGIR bugs REAIS.

NAO reescreva do zero. NAO adicione features que o usuario nao pediu.
Se o codigo estiver OK, devolva igual (so reindentado se preciso).

==================================================================
O QUE VOCE NAO PODE FAZER (leia com atencao)
==================================================================

1. NAO INVENTE APIs.
   Se voce nao tem 100% de certeza que a API existe no Roblox, NAO USE.
   APIs reais mais comuns:
     - RemoteEvent:FireServer / FireClient / FireAllClients
     - RemoteEvent.OnServerEvent / OnClientEvent
     - DataStore:GetAsync / SetAsync / UpdateAsync
     - player:GetAttribute / SetAttribute / Kick / LoadCharacter
     - Instance.new / Destroy / FindFirstChild / WaitForChild
   APIs que NAO existem (nunca use):
     - player:SendPacket   <- INVENTADO
     - player:GetInventory <- INVENTADO
     - game:SaveData       <- INVENTADO
     - Part:SetColor()     <- INVENTADO (use .Color = Color3)

2. NAO INVENTE BUGS.
   So audite o que ESTA no rascunho.
   - Se o thinking do rascunho nao menciona "promessa de X", NAO escreva
     "promessa de X nao implementada".
   - Se o rascunho nao usou LocalPlayer, NAO escreva "removeu LocalPlayer".
   - Se voce nao viu o bug no codigo, NAO diga que viu.

3. NAO ADICIONE FEATURES NAO PEDIDAS.
   - Se o usuario pediu "inventario simples", NAO adicione RemoteEvent,
     sistema de UI, HUD, animacao, som, particula, etc.
   - Se o rascunho NAO tem algo, e o usuario NAO pediu, NAO adicione.
   - So adicione se for CORRECAO de bug real, nao feature nova.

4. NAO INVENTE NUMEROS DE LINHA.
   Se voce nao tem certeza da linha, escreva "[rascunho]" ou
   "[funcao carregar]" em vez de "[linha 11]".

5. EM CASO DE DUVIDA, NAO MUDE.
   - Reindentar: SEMPRE seguro.
   - Renomear variavel: risky.
   - Trocar API: risky.
   - Adicionar codigo: risky.
   - Devolver igual: SEMPRE seguro.

==================================================================
O QUE VOCE DEVE VERIFICAR (checklist)
==================================================================

1. INDENTACAO (4 espacos por nivel). Se veio sem, reindente TUDO.

2. TIPO DE SCRIPT:
   - LocalScript: usa LocalPlayer/UserInputService/ScreenGui?
   - Script server: tem LocalPlayer? (ERRO -> remova)
   - ModuleScript: termina com "return X"? (senao, adicione)

3. NIL SAFETY:
   - Toda variavel que pode ser nil tem checagem antes de uso?
   - GetAsync/FindFirstChild/WaitForChild tem retorno tratado?

4. TABELAS:
   - #tabela ou ipairs em tabela com buracos? Troque por for i = 1, N.

5. DATASTORE:
   - SetAsync em loop = erro. Debounce ou UpdateAsync.
   - pcall em toda chamada DataStore?

6. EVENTOS:
   - CharacterAdded dentro de PlayerAdded sem debounce = empilhamento.
   - PlayerRemoving limpa cache?

7. API REAL:
   - Toda funcao usada EXISTE no Roblox? (na duvida, nao use)

8. LOGICA:
   - O codigo resolve o que o usuario pediu?
   - Tem codigo que nao faz nada? (remova, mas mencione na auditoria)

==================================================================
FORMATO OBRIGATORIO
==================================================================

<qa_review>
1. [onde] problema real -> correcao aplicada
2. [onde] problema real -> correcao aplicada
...
Se nao achou bugs reais: "ok, nenhum bug encontrado. codigo mantido."
</qa_review>

[codigo final corrigido + explicacao breve]

==================================================================
EXEMPLO DE QA BOM (rascunho tinha LocalPlayer no server)
==================================================================

<qa_review>
1. [funcao carregar] "Players.LocalPlayer" em Script server -> removido,
   LocalPlayer so existe no LocalScript.
2. [todo o codigo] Sem indentacao -> reindentado 4 espacos.
3. [PlayerAdded] CharacterAdded dentro de PlayerAdded -> removido,
   nao era necessario pro inventario.
</qa_review>
[ModuleScript completo, indentado, com return Inventory]

==================================================================
EXEMPLO DE QA BOM (rascunho estava OK)
==================================================================

<qa_review>
ok, nenhum bug encontrado. codigo mantido (ja estava indentado, com
pcall, debounce e return).
</qa_review>
[ModuleScript identico ao rascunho]

==================================================================
REGRAS FINAIS
==================================================================
- SEMPRE <qa_review> + codigo final.
- Se o rascunho estava otimo, NAO invente mudancas so pra "ter o que dizer".
- Se nao tem certeza de uma API, NAO USE.
- Se nao viu o bug no codigo, NAO INVENTE que viu.
- NUNCA responda em ingles.
"""


# ==========================================================
# LEMBRETES
# ==========================================================
LEMBRETE_FINAL = """Lembre-se: 4 fases no <thinking> (Entender, Decidir APIs,
Rascunhar, Revisar). FASE 4 obrigatoria. Sem API inventada. Sem feature
nao pedida. Indentacao 4 espacos."""

LEMBRETE_QA = """Lembre-se: <qa_review>...</qa_review> so com bugs REAIS
que voce viu no codigo. Sem inventar API, sem inventar bug, sem adicionar
feature nao pedida. Em duvida, devolva o codigo igual (so reindentado)."""


# ==========================================================
# HELPERS DE LEITURA
# ==========================================================
def _ler(path, limite=2000):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()[:limite]
    except Exception:
        pass
    return ""


def _slug(s):
    s = re.sub(r"[^a-zA-Z0-9_\- ]", "", str(s))
    return s.strip().replace(" ", "_")[:60] or "Geral"


def _resumo_blueprint(projeto_dir):
    path = os.path.join(projeto_dir, "blueprint.json")
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            bp = json.load(f)
    except Exception:
        return ""
    total = bp.get("total_tarefas", 0)
    dominios = [d.get("nome", "?") for d in bp.get("dominios", [])]
    linhas = ["- Blueprint: " + str(total) + " tarefas em " + str(len(dominios)) + " dominios"]
    if dominios:
        linhas.append("  Dominios: " + ", ".join(dominios[:8]))
    return "\n".join(linhas)


def _resumo_estado(projeto_dir):
    path = os.path.join(projeto_dir, "game_estado.json")
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            ge = json.load(f)
    except Exception:
        return ""
    etapas = ge.get("etapas", [])
    total = len(etapas)
    concluidas = sum(1 for e in etapas if e.get("status") == "concluida")
    bloqueadas = sum(1 for e in etapas if e.get("status") == "bloqueada")
    pendentes = total - concluidas - bloqueadas
    linhas = ["- Progresso: " + str(concluidas) + "/" + str(total) + " concluidas"]
    if bloqueadas:
        linhas.append("  Bloqueadas: " + str(bloqueadas))
    if pendentes:
        linhas.append("  Pendentes: " + str(pendentes))
    return "\n".join(linhas)


def _resumo_lore(projeto_dir):
    texto = _ler(os.path.join(projeto_dir, "1_LORE.md"), 600)
    if not texto.strip():
        return ""
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    return "- Lore: " + texto.replace("\n", " ")[:400]


def _resumo_objetivos(projeto_dir):
    path = os.path.join(projeto_dir, "2_OBJETIVOS.md")
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            linhas = f.readlines()
    except Exception:
        return ""
    pendentes = [l.replace("- [ ]", "").strip()
                 for l in linhas if l.strip().startswith("- [ ]")]
    if not pendentes:
        return ""
    return "- Proximo objetivo: " + pendentes[0][:100]


def construir_contexto_projeto(projeto, base_dir):
    if not projeto:
        return "(nenhum projeto ativo)"
    projeto_dir = os.path.join(base_dir, "Projetos", _slug(projeto))
    if not os.path.isdir(projeto_dir):
        return "(projeto '" + projeto + "' ainda nao tem pasta)"
    blocos = []
    for fn in (_resumo_blueprint, _resumo_estado, _resumo_lore, _resumo_objetivos):
        b = fn(projeto_dir)
        if b:
            blocos.append(b)
    if not blocos:
        return "(projeto '" + projeto + "' existe mas vazio)"
    return "\n".join(blocos)


# ==========================================================
# HISTORICO (janela curta)
# ==========================================================
def formatar_historico(mensagens, limite=6):
    if not mensagens:
        return "(sem historico)"

    def _autor_norm(a):
        return (a or "").replace("ê", "e").replace("é", "e")

    filtradas = [
        m for m in mensagens
        if _autor_norm(m.get("autor")) in ("Voce", "Kael")
        and str(m.get("texto", "")).strip()
    ]
    recentes = filtradas[-limite:]
    if not recentes:
        return "(sem historico)"
    linhas = []
    for m in recentes:
        autor = "Usuario" if _autor_norm(m.get("autor")) == "Voce" else "Kael"
        texto = str(m.get("texto", ""))
        if len(texto) > 400:
            texto = texto[:400] + " [cortado]"
        linhas.append(autor + ": " + texto)
    return "\n".join(linhas)


# ==========================================================
# RESUMO CUMULATIVO (persiste em disco)
# ==========================================================
def _path_resumo(base_dir, projeto):
    slug = _slug(projeto) if projeto else "Geral"
    return os.path.join(base_dir, "Projetos", slug, "resumo_conversa.json")


def _ler_resumo(base_dir, projeto):
    path = _path_resumo(base_dir, projeto)
    if not os.path.exists(path):
        return {"resumo": "", "total_msgs_resumidas": 0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"resumo": "", "total_msgs_resumidas": 0}


def _salvar_resumo(base_dir, projeto, dados):
    path = _path_resumo(base_dir, projeto)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[PERSONA] erro salvando resumo: " + str(e)[:100])


def _chamar_llm_resumo(prompt):
    """Auto-contido: chama Ollama direto, sem import circular."""
    try:
        import requests
        r = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": MODELO_RESUMO,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_ctx": 4096, "num_predict": 500},
            },
            timeout=120,
        )
        return r.json().get("response", "").strip()
    except Exception as e:
        print("[PERSONA] erro LLM resumo: " + str(e)[:200])
        return ""


def _resumir_msgs(msgs):
    linhas = []
    for m in msgs:
        autor_raw = str(m.get("autor", ""))
        eh_user = "voce" in autor_raw.lower().replace("ê", "e")
        autor = "User" if eh_user else "Kael"
        txt = str(m.get("texto", ""))[:300]
        linhas.append(autor + ": " + txt)
    return "\n".join(linhas)


def _atualizar_resumo_sync(base_dir, projeto, mensagens_chat):
    try:
        atual = _ler_resumo(base_dir, projeto)
        total_resumidas = int(atual.get("total_msgs_resumidas", 0))
        resumo_antigo = atual.get("resumo", "")

        total = len(mensagens_chat)
        limite_novas = total - RESUMO_THRESHOLD
        if limite_novas <= total_resumidas:
            return

        msgs_novas = mensagens_chat[total_resumidas:limite_novas]
        if not msgs_novas:
            return

        bloco_novo = _resumir_msgs(msgs_novas)

        if resumo_antigo:
            prompt = (
                "Voce mantem um RESUMO CUMULATIVO de conversas tecnicas.\n\n"
                "RESUMO ANTERIOR:\n" + resumo_antigo + "\n\n"
                "NOVAS MENSAGENS:\n" + bloco_novo + "\n\n"
                "Atualize o resumo incorporando as novas mensagens. Mantenha:\n"
                "- Decisoes tecnicas (tecnologias, nomes, valores, IDs)\n"
                "- Preferencias do usuario\n"
                "- Pendencias e proximos passos\n"
                "- Bugs conhecidos ou problemas resolvidos\n"
                "Remova: cumprimentos, repeticoes, codigo completo (so diga "
                "'codigo X criado com funcao Y').\n"
                "Maximo " + str(RESUMO_MAX_CHARS) + " caracteres.\n"
                "Responda APENAS com o resumo atualizado, sem preambulo."
            )
        else:
            prompt = (
                "Resuma a conversa abaixo em ate " + str(RESUMO_MAX_CHARS) + " caracteres.\n"
                "Mantenha: decisoes tecnicas, preferencias, pendencias, bugs.\n"
                "Remova: cumprimentos, repeticoes, codigo completo.\n\n"
                "CONVERSA:\n" + bloco_novo + "\n\n"
                "Responda APENAS com o resumo."
            )

        novo_resumo = _chamar_llm_resumo(prompt)
        if not novo_resumo:
            return

        if len(novo_resumo) > RESUMO_MAX_CHARS:
            novo_resumo = novo_resumo[:RESUMO_MAX_CHARS] + "..."

        _salvar_resumo(base_dir, projeto, {
            "resumo": novo_resumo,
            "total_msgs_resumidas": limite_novas,
        })
        print("[PERSONA] resumo atualizado (" + str(limite_novas) + " msgs, "
              + str(len(novo_resumo)) + " chars)")

    except Exception as e:
        print("[PERSONA] erro atualizar resumo: " + str(e)[:200])


def _talvez_atualizar_resumo_bg(base_dir, projeto, mensagens_chat):
    """Dispara atualizacao em thread se necessario. Nao bloqueia."""
    try:
        slug = _slug(projeto) if projeto else "Geral"
        with RESUMO_LOCK:
            if RESUMO_UPDATING.get(slug):
                return

            atual = _ler_resumo(base_dir, projeto)
            total_resumidas = int(atual.get("total_msgs_resumidas", 0))
            total = len(mensagens_chat)

            if total - RESUMO_THRESHOLD <= total_resumidas:
                return

            RESUMO_UPDATING[slug] = True

        def worker():
            try:
                _atualizar_resumo_sync(base_dir, projeto, mensagens_chat)
            finally:
                with RESUMO_LOCK:
                    RESUMO_UPDATING[slug] = False

        threading.Thread(target=worker, daemon=True).start()

    except Exception as e:
        print("[PERSONA] erro bg resumo: " + str(e)[:200])


# ==========================================================
# MONTAGEM DO USER PROMPT (PASS 1)
# ==========================================================
def montar_user_prompt(prompt_usuario, projeto, base_dir, mensagens_chat):
    _talvez_atualizar_resumo_bg(base_dir, projeto, mensagens_chat)

    resumo = _ler_resumo(base_dir, projeto).get("resumo", "")
    contexto = construir_contexto_projeto(projeto, base_dir)
    historico = formatar_historico(mensagens_chat, limite=RESUMO_THRESHOLD)

    partes = []
    if resumo:
        partes.append("[RESUMO DE CONVERSAS ANTERIORES]")
        partes.append(resumo)
        partes.append("")
    partes.append("[CONTEXTO DO PROJETO ATIVO (" + (projeto or "nenhum") + ")]")
    partes.append(contexto)
    partes.append("")
    partes.append("[ULTIMAS MENSAGENS]")
    partes.append(historico)
    partes.append("")
    partes.append("[MENSAGEM DO USUARIO]")
    partes.append(str(prompt_usuario).strip())
    partes.append("")
    partes.append(LEMBRETE_FINAL)

    return "\n".join(partes)


# ==========================================================
# MONTAGEM DO USER PROMPT (PASS 2)
# ==========================================================
def montar_qa_prompt(pergunta_original, draft_texto, projeto, base_dir):
    draft = str(draft_texto)
    if len(draft) > 9000:
        draft = draft[:9000] + "\n\n[... TRUNCADO POR TAMANHO ...]"

    contexto = construir_contexto_projeto(projeto, base_dir)

    return (
        "=== PERGUNTA ORIGINAL DO USUARIO ===\n"
        + str(pergunta_original).strip() + "\n\n"
        "=== CONTEXTO DO PROJETO (se relevante) ===\n"
        + contexto + "\n\n"
        "=== RASCUNHO DO KAEL ===\n"
        + draft + "\n\n"
        "=== SUA TAREFA ===\n"
        "Audite o rascunho. So bugs REAIS que voce VÊ no codigo.\n"
        "Sem inventar API, sem inventar bug, sem adicionar feature.\n"
        "Comece com <qa_review>...</qa_review>, depois o codigo final "
        "(indentado 4 espacos).\n\n"
        + LEMBRETE_QA + "\n"
    )


# ==========================================================
# DETECCAO DE CODIGO (decide se roda Pass 2)
# ==========================================================
def tem_codigo(texto):
    if not texto:
        return False
    t = str(texto)
    marcadores = [
        "```lua", "```luau", "```python", "```gdscript", "```js",
        "```javascript", "```typescript", "```csharp", "```cs",
    ]
    for m in marcadores:
        if m in t:
            return True
    padroes = [
        "local function ",
        "game:GetService",
        "Instance.new(",
        "task.wait(",
        "game.Workspace",
        "Players.LocalPlayer",
        "RemoteEvent",
        "func _ready(",
        "extends Node",
    ]
    for p in padroes:
        if p in t:
            return True
    return False


# ==========================================================
# EXTRACAO DE RESPOSTA FINAL
# ==========================================================
def extrair_resposta_final(texto_completo):
    if not texto_completo:
        return ""
    t = str(texto_completo)
    t = re.sub(r"<thinking>[\s\S]*?</thinking>", "", t, flags=re.IGNORECASE)
    t = re.sub(r"<qa_review>[\s\S]*?</qa_review>", "", t, flags=re.IGNORECASE)
    t = t.strip()
    if not t:
        t = re.sub(r"</?thinking>|</?qa_review>", "", texto_completo,
                   flags=re.IGNORECASE).strip()
    return t