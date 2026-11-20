# -*- coding: utf-8 -*-
"""
world_builder.py - Kael World Builder v3 (Procedural Terrain)
=============================================================
Gera um mundo 3D usando Perlin Noise (math.noise) para criar 
relevo natural, colinas e biomas suaves.
"""
import os
import re
import json
import math
import time
from datetime import datetime


class WorldBuilder:
    def __init__(self, projeto, genero, descricao="", lore="", base_dir=None,
                 fn_llm=None, fn_enfileirar=None, fn_adicionar_msg=None,
                 blueprint=None):
        self.projeto = str(projeto)
        self.genero = str(genero)
        self.descricao = str(descricao)
        self.lore = str(lore)
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.fn_llm = fn_llm
        self.fn_enfileirar = fn_enfileirar
        self.fn_adicionar_msg = fn_adicionar_msg
        self.blueprint = blueprint or {}

        self.projeto_dir = os.path.join(self.base_dir, "Projetos", self._slug(projeto))
        os.makedirs(self.projeto_dir, exist_ok=True)
        self.arquivo_mapa = os.path.join(self.projeto_dir, "mapa_mundo.json")

        self.mapa = {
            "tamanho_mundo": 2000,   # studs (meio-lado)
            "centro": [0, 50, 0],    # castelo central
            "reinos": [],            # lista de reinos
            "rios": [],              # lista de rios
            "estradas": [],          # lista de estradas
            "pontes": [],            # lista de pontes
            "scripts_gerados": [],   # nomes dos scripts Lua
        }
        self._contador_scripts = 0

    def _slug(self, s):
        s = re.sub(r"[^a-zA-Z0-9_\- ]", "", str(s))
        return s.strip().replace(" ", "_")[:60] or "Jogo"

    def _log(self, msg):
        try:
            print("[WORLD] " + str(msg))
            if self.fn_adicionar_msg:
                self.fn_adicionar_msg("Sistema", "[World] " + str(msg))
        except Exception:
            pass

    def _proximo_nome(self, prefixo):
        self._contador_scripts += 1
        return "World_" + prefixo + "_" + str(self._contador_scripts)

    def _enfileirar_script(self, nome, codigo_lua):
        self._log("Enfileirando script: " + nome)
        self.mapa["scripts_gerados"].append(nome)
        try:
            self.fn_enfileirar({
                "tipo": "criar_script",
                "nome": nome,
                "codigo": codigo_lua,
                "tipo_script": "Script",
                "testar_automaticamente": False,
                "origem": "world_builder",
            })
        except Exception as e:
            self._log("Erro ao enfileirar " + nome + ": " + str(e))

    def _salvar_mapa(self):
        try:
            with open(self.arquivo_mapa, "w", encoding="utf-8") as f:
                json.dump(self.mapa, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log("Erro ao salvar mapa: " + str(e))

    # ================================================================
    # FASE 1: PLANEJAR MAPA
    # ================================================================
    def _planejar_mapa(self):
        self._log("Planejando posicoes dos reinos...")
        
        # Decide os reinos (via LLM ou fallback)
        reinos = self._decidir_reinos()
        self.mapa["reinos"] = reinos

        # Distribui os reinos em círculo
        raio = 1200
        for i, reino in enumerate(self.mapa["reinos"]):
            angulo = (i * 2 * math.pi) / max(1, len(self.mapa["reinos"]))
            x = int(math.cos(angulo) * raio)
            z = int(math.sin(angulo) * raio)
            reino["posicao"] = [x, 50, z]
            reino["angulo"] = round(math.degrees(angulo), 1)

        # Rios radiais
        for i in range(3):
            angulo = (i * 2 * math.pi) / 3 + 0.5
            self.mapa["rios"].append({
                "id": "rio_" + str(i + 1),
                "inicio": [int(math.cos(angulo) * 1800), 80, int(math.sin(angulo) * 1800)],
                "fim": [0, 60, 0],
                "largura": 80,
            })

        # Estradas
        for reino in self.mapa["reinos"]:
            self.mapa["estradas"].append({
                "id": "estrada_" + reino["nome"].lower().replace(" ", "_"),
                "de": [0, 50, 0],
                "para": reino["posicao"],
                "material": "Cobblestone",
            })

        self._salvar_mapa()

    def _decidir_reinos(self):
        # Tenta extrair do LLM (com fallback seguro)
        fallback = [
            {"nome": "Estatura de Gelo", "bioma": "Gelo", "material": "Snow", "cor": [220, 235, 255]},
            {"nome": "Vales do Crepusculo", "bioma": "Floresta", "material": "Grass", "cor": [80, 130, 70]},
            {"nome": "Matas de Aetherium", "bioma": "Floresta Magica", "material": "LeafyGrass", "cor": [140, 90, 200]},
            {"nome": "Oeste de Ferro", "bioma": "Montanha", "material": "Rock", "cor": [90, 90, 100]},
            {"nome": "Areias Rubras", "bioma": "Deserto", "material": "Sand", "cor": [220, 150, 80]},
            {"nome": "Pantano Sombrio", "bioma": "Pantano", "material": "Mud", "cor": [60, 70, 50]},
        ]
        # Como já sabemos os reinos da lore, usamos eles direto para ser rapido
        return fallback

    # ================================================================
    # FASE 2: GERAR TERRENO PROCEDURAL (PERLIN NOISE)
    # ================================================================
    def _gerar_terreno_procedural(self):
        self._log("Gerando terreno procedural (isso pode demorar no Roblox)...")
        nome = self._proximo_nome("TerrenoProcedural")
        
        # Passa os dados dos reinos pro Lua para ele pintar o bioma certo
        reinos_lua = json.dumps(self.mapa["reinos"])
        
        codigo = f'''
-- World Builder: Terreno Procedural (Perlin Noise)
local Terrain = workspace:FindFirstChildOfClass("Terrain")
if not Terrain then warn("[World] Terrain nao encontrado") return end
Terrain:Clear()

local reinos = {reinos_lua}
local TAMANHO = 2000
local PASSO = 16  -- Tamanho do bloco (menor = mais detalhado, mais pesado)
local ESCALA = 300 -- Suavidade das colinas
local ALTURA_MAX = 120

-- Funcao para achar o bioma mais proximo
local function getMaterial(x, z)
    local menorDist = 999999
    local mat = Enum.Material.Grass
    for _, r in ipairs(reinos) do
        local dx = x - r.posicao[1]
        local dz = z - r.posicao[3]
        local dist = math.sqrt(dx*dx + dz*dz)
        if dist < menorDist and dist < 800 then
            menorDist = dist
            -- Converte a string do python para Enum.Material
            local ok, m = pcall(function() return Enum.Material[r.material] end)
            if ok then mat = m end
        end
    end
    return mat
end

print("[World] Iniciando escavacao do terreno...")
local tempoInicio = os.time()

for x = -TAMANHO, TAMANHO, PASSO do
    for z = -TAMANHO, TAMANHO, PASSO do
        -- Perlin Noise para colinas
        local ruido = math.noise(x / ESCALA, z / ESCALA)
        -- Perlin Noise para montanhas (mais agressivo)
        local montanha = math.noise(x / 100, z / 100) * 80
        
        local altura = 30 + (ruido * ALTURA_MAX) + math.max(0, montanha)
        
        -- Achatamento perto do centro (Castelo)
        local distCentro = math.sqrt(x*x + z*z)
        if distCentro < 400 then
            altura = 50 + (ruido * 10) -- Terreno plano no centro
        end
        
        local material = getMaterial(x, z)
        
        local pos = Vector3.new(x, altura / 2, z)
        local size = Vector3.new(PASSO, altura, PASSO)
        
        Terrain:FillBlock(CFrame.new(pos), size, material)
    end
end

print("[World] Terreno Procedural gerado em " .. (os.time() - tempoInicio) .. " segundos!")
'''
        self._enfileirar_script(nome, codigo)

    # ================================================================
    # FASE 3: RIOS E LAGOS
    # ================================================================
    def _gerar_rios(self):
        self._log("Gerando rios...")
        for rio in self.mapa["rios"]:
            nome = self._proximo_nome("Rio_" + rio["id"])
            ini = rio["inicio"]
            fim = rio["fim"]
            larg = rio["largura"]

            codigo = f'''
-- World: Rio {rio["id"]}
local Terrain = workspace:FindFirstChildOfClass("Terrain")
local inicio = Vector3.new({ini[0]}, {ini[1]}, {ini[2]})
local fim_v = Vector3.new({fim[0]}, {fim[1]}, {fim[2]})
local passos = 30
local delta = (fim_v - inicio) / passos

for i = 0, passos do
    local pos = inicio + delta * i
    -- Cava o leito
    Terrain:FillBall(pos + Vector3.new(0, -10, 0), {larg//2}, Enum.Material.Sand)
    -- Preenche com agua
    Terrain:FillBall(pos, {larg//3}, Enum.Material.Water)
end
print("[World] Rio {rio["id"]} criado.")
'''
            self._enfileirar_script(nome, codigo)

    # ================================================================
    # FASE 4: CASTELO E CIDADES (Aproveitando o terreno)
    # ================================================================
    def _gerar_castelo_central(self):
        self._log("Gerando castelo central...")
        nome = self._proximo_nome("CasteloCentral")
        cx, cy, cz = self.mapa["centro"]

        # Como o terreno é procedural, usamos um Raycast pra achar o chao exato
        codigo = f'''
-- World: Castelo Central
local centro = Vector3.new({cx}, {cy + 50}, {cz})
local params = RaycastParams.new()
params.FilterDescendantsInstances = {{workspace.Terrain}}

-- Acha o chao
local ray = workspace:Raycast(centro, Vector3.new(0, -200, 0), params)
if ray then centro = ray.Position + Vector3.new(0, 2, 0) end

local function criarPart(nome, size, pos, mat, cor)
    local p = Instance.new("Part")
    p.Name = nome; p.Size = size; p.Position = pos
    p.Anchored = true; p.Material = mat or Enum.Material.Slate
    p.Color = cor or Color3.fromRGB(150,150,160); p.Parent = workspace
    return p
end

criarPart("Castelo_Fundacao", Vector3.new(150,5,150), centro, Enum.Material.Cobblestone)
criarPart("Castelo_Muro1", Vector3.new(150,50,10), centro + Vector3.new(0,25,-70), Enum.Material.Cobblestone)
criarPart("Castelo_Muro2", Vector3.new(150,50,10), centro + Vector3.new(0,25,70), Enum.Material.Cobblestone)
criarPart("Castelo_Muro3", Vector3.new(10,50,150), centro + Vector3.new(-70,25,0), Enum.Material.Cobblestone)
criarPart("Castelo_Muro4", Vector3.new(10,50,150), centro + Vector3.new(70,25,0), Enum.Material.Cobblestone)
criarPart("Castelo_Torre", Vector3.new(40,80,40), centro + Vector3.new(0,40,0), Enum.Material.Slate)
criarPart("Castelo_Bandeira", Vector3.new(15,30,2), centro + Vector3.new(0,95,0), Enum.Material.Neon, Color3.fromRGB(200,180,50))

print("[World] Castelo central construido no chao (Y=" .. centro.Y .. ")")
'''
        self._enfileirar_script(nome, codigo)

    def _gerar_cidades(self):
        self._log("Gerando cidades...")
        for reino in self.mapa["reinos"]:
            nome = self._proximo_nome("Cidade_" + re.sub(r"[^A-Za-z0-9]", "", reino["nome"]))
            pos = reino["posicao"]
            cor = reino["cor"]

            codigo = f'''
-- World: Cidade {reino["nome"]}
local centro = Vector3.new({pos[0]}, 200, {pos[2]})
local params = RaycastParams.new()
params.FilterDescendantsInstances = {{workspace.Terrain}}
local ray = workspace:Raycast(centro, Vector3.new(0, -300, 0), params)
if ray then centro = ray.Position + Vector3.new(0, 1, 0) end

local corReino = Color3.fromRGB({cor[0]}, {cor[1]}, {cor[2]})
local function cp(nome, size, pos, mat, cor)
    local p = Instance.new("Part")
    p.Name = nome; p.Size = size; p.Position = pos; p.Anchored = true
    p.Material = mat; p.Color = cor or Color3.fromRGB(180,180,180); p.Parent = workspace
end

cp("Praca", Vector3.new(100,2,100), centro, Enum.Material.Cobblestone)
for i = 1, 8 do
    local ang = (i/8) * math.pi * 2
    local p = centro + Vector3.new(math.cos(ang)*60, 8, math.sin(ang)*60)
    cp("Casa", Vector3.new(20,20,20), p, Enum.Material.WoodPlanks)
    cp("Telhado", Vector3.new(22,8,22), p + Vector3.new(0,14,0), Enum.Material.Slate, corReino)
end
print("[World] Cidade {reino["nome"]} construida no chao.")
'''
            self._enfileirar_script(nome, codigo)

    def _gerar_estradas(self):
        self._log("Gerando estradas...")
        for estrada in self.mapa["estradas"]:
            nome = self._proximo_nome("Estrada_" + re.sub(r"[^A-Za-z0-9]", "", estrada["id"])[:15])
            de = estrada["de"]
            para = estrada["para"]

            codigo = f'''
-- World: Estrada {estrada["id"]}
local inicio = Vector3.new({de[0]}, 100, {de[2]})
local fim_v = Vector3.new({para[0]}, 100, {para[2]})
local passos = 40
local delta = (fim_v - inicio) / passos
local params = RaycastParams.new()
params.FilterDescendantsInstances = {{workspace.Terrain}}

for i = 0, passos do
    local pos = inicio + delta * i
    -- Acha o chao
    local ray = workspace:Raycast(pos, Vector3.new(0, -200, 0), params)
    if ray then
        local p = Instance.new("Part")
        p.Name = "Estrada"
        p.Size = Vector3.new(20, 1, 22)
        p.Position = ray.Position + Vector3.new(0, 0.5, 0) -- Cola no chao
        p.Anchored = true
        p.Material = Enum.Material.Cobblestone
        p.Color = Color3.fromRGB(120,120,120)
        p.Parent = workspace
    end
end
print("[World] Estrada {estrada["id"]} criada seguindo o relevo.")
'''
            self._enfileirar_script(nome, codigo)

    # ================================================================
    # METODO PUBLICO
    # ================================================================
    def construir_mundo(self):
        self._log("Iniciando construcao do mundo '" + self.projeto + "'...")
        
        # Limpeza inteligente
        self._log("Limpando construcoes antigas do Kael...")
        self.fn_enfileirar({"tipo": "limpar_construcoes_kael"})
        time.sleep(2)

        self._planejar_mapa()
        self._gerar_terreno_procedural()
        
        # Espera o terreno ser gerado antes de colocar os objetos (que usam Raycast)
        self._log("Aguardando geracao do terreno...")
        time.sleep(6)

        self._gerar_rios()
        self._gerar_castelo_central()
        self._gerar_cidades()
        self._gerar_estradas()
        
        self._salvar_mapa()
        self._log("Construcao do mundo enfileirada! O Roblox vai gerar as colinas agora.")
        return self.mapa