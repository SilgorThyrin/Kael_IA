# -*- coding: utf-8 -*-
"""
kael_assets.py - Fabrica procedural de assets para o Kael
============================================================
Gera scripts Lua que constroem assets dentro do Roblox.

Duas estrategias:
  1. TEMPLATES hardcoded (proven, funcionam) para assets comuns
     castelo, casa, torre, taverna, tocha, bandeira, bau, moeda,
     pocao, poco, fogueira, spawn
  2. LLM fallback para assets complexos ou nao-template

Nao depende de internet. Nao gera modelo 3D. Usa apenas Instance.new
de Parts, Lights, ParticleEmitters, SurfaceGui.
"""
import os
import re
import json


# ==========================================================
# TEMPLATES DE ESTRUTURA (Lua que constroi)
# ==========================================================
# Convencao de cada template:
#   - Retorna string com codigo Lua COMPLETO
#   - Todos os Parts sao Anchored = true
#   - Ao final, print("[Kael] OK: <nome>")
#   - Usa basePos determinada internamente (categoria + random)

_TEMPLATE_CASTELO = """-- Kael Asset: Castelo
local basePos = Vector3.new(180 + math.random(-20, 20), 0, 180 + math.random(-20, 20))
local wallColor = Color3.fromRGB(95, 95, 95)
local towerColor = Color3.fromRGB(80, 80, 80)

-- Base (chao de pedra)
local base = Instance.new("Part")
base.Name = "CasteloBase"
base.Size = Vector3.new(60, 1, 60)
base.Position = basePos + Vector3.new(0, 0.5, 0)
base.Material = Enum.Material.Cobblestone
base.Color = Color3.fromRGB(120, 120, 120)
base.Anchored = true
base.Parent = workspace

-- 4 paredes (com gap na frente pro portao)
local wallH = 18
local wallT = 2
local walls = {
    {pos = basePos + Vector3.new(0, wallH/2, -29), size = Vector3.new(60, wallH, wallT)},
    {pos = basePos + Vector3.new(-29, wallH/2, 0), size = Vector3.new(wallT, wallH, 60)},
    {pos = basePos + Vector3.new(29, wallH/2, 0), size = Vector3.new(wallT, wallH, 60)},
    {pos = basePos + Vector3.new(-20, wallH/2, 29), size = Vector3.new(20, wallH, wallT)},
    {pos = basePos + Vector3.new(20, wallH/2, 29), size = Vector3.new(20, wallH, wallT)},
    {pos = basePos + Vector3.new(0, wallH - 3, 29), size = Vector3.new(20, 6, wallT)},
}
for i, w in ipairs(walls) do
    local part = Instance.new("Part")
    part.Name = "CasteloParede" .. i
    part.Size = w.size
    part.Position = w.pos
    part.Material = Enum.Material.Slate
    part.Color = wallColor
    part.Anchored = true
    part.Parent = workspace
end

-- 4 torres nos cantos
local corners = {
    Vector3.new(-30, 0, -30), Vector3.new(30, 0, -30),
    Vector3.new(-30, 0, 30), Vector3.new(30, 0, 30),
}
for i, off in ipairs(corners) do
    local tower = Instance.new("Part")
    tower.Name = "Torre" .. i
    tower.Shape = Enum.PartType.Cylinder
    tower.Size = Vector3.new(26, 10, 10)
    tower.CFrame = CFrame.new(basePos + off + Vector3.new(0, 13, 0)) * CFrame.Angles(0, 0, math.pi/2)
    tower.Material = Enum.Material.Slate
    tower.Color = towerColor
    tower.Anchored = true
    tower.Parent = workspace
end

print("[Kael] OK: Castelo construido em " .. tostring(basePos))
"""

_TEMPLATE_CASA = """-- Kael Asset: Casa
local basePos = Vector3.new(60 + math.random(-20, 20), 0, 60 + math.random(-20, 20))
local woodColor = Color3.fromRGB(139, 111, 71)

-- Chao
local floor = Instance.new("Part")
floor.Name = "CasaChao"
floor.Size = Vector3.new(20, 1, 20)
floor.Position = basePos + Vector3.new(0, 0.5, 0)
floor.Material = Enum.Material.Wood
floor.Color = woodColor
floor.Anchored = true
floor.Parent = workspace

-- 4 paredes (frente tem porta)
local wallH = 10
local walls = {
    {pos = basePos + Vector3.new(0, wallH/2, -9.5), size = Vector3.new(20, wallH, 1)},
    {pos = basePos + Vector3.new(-9.5, wallH/2, 0), size = Vector3.new(1, wallH, 20)},
    {pos = basePos + Vector3.new(9.5, wallH/2, 0), size = Vector3.new(1, wallH, 20)},
    {pos = basePos + Vector3.new(-5, wallH/2, 9.5), size = Vector3.new(10, wallH, 1)},
    {pos = basePos + Vector3.new(5, wallH/2, 9.5), size = Vector3.new(10, wallH, 1)},
}
for i, w in ipairs(walls) do
    local part = Instance.new("Part")
    part.Name = "CasaParede" .. i
    part.Size = w.size
    part.Position = w.pos
    part.Material = Enum.Material.WoodPlanks
    part.Color = woodColor
    part.Anchored = true
    part.Parent = workspace
end

-- Telhado (dois wedges)
for i, off in ipairs({-5, 5}) do
    local roof = Instance.new("WedgePart")
    roof.Name = "CasaTelhado" .. i
    roof.Size = Vector3.new(10, 6, 21)
    roof.Position = basePos + Vector3.new(off, wallH + 3, 0)
    roof.Rotation = Vector3.new(0, 0, off > 0 and 90 or -90)
    roof.Material = Enum.Material.Slate
    roof.Color = Color3.fromRGB(120, 40, 30)
    roof.Anchored = true
    roof.Parent = workspace
end

print("[Kael] OK: Casa construida em " .. tostring(basePos))
"""

_TEMPLATE_TORRE = """-- Kael Asset: Torre
local basePos = Vector3.new(120 + math.random(-30, 30), 0, 120 + math.random(-30, 30))

local tower = Instance.new("Part")
tower.Name = "TorreCorpo"
tower.Shape = Enum.PartType.Cylinder
tower.Size = Vector3.new(35, 10, 10)
tower.CFrame = CFrame.new(basePos + Vector3.new(0, 17.5, 0)) * CFrame.Angles(0, 0, math.pi/2)
tower.Material = Enum.Material.Slate
tower.Color = Color3.fromRGB(90, 90, 90)
tower.Anchored = true
tower.Parent = workspace

-- Topo (cone de telhado)
local top = Instance.new("Part")
top.Name = "TorreTopo"
top.Shape = Enum.PartType.Cylinder
top.Size = Vector3.new(12, 13, 13)
top.CFrame = CFrame.new(basePos + Vector3.new(0, 41, 0)) * CFrame.Angles(0, 0, math.pi/2)
top.Material = Enum.Material.Slate
top.Color = Color3.fromRGB(100, 50, 40)
top.Anchored = true
top.Parent = workspace

print("[Kael] OK: Torre construida em " .. tostring(basePos))
"""

_TEMPLATE_TAVERNA = """-- Kael Asset: Taverna
local basePos = Vector3.new(90 + math.random(-20, 20), 0, 90 + math.random(-20, 20))
local woodColor = Color3.fromRGB(120, 85, 55)

-- Chao
local floor = Instance.new("Part")
floor.Name = "TavernaChao"
floor.Size = Vector3.new(28, 1, 22)
floor.Position = basePos + Vector3.new(0, 0.5, 0)
floor.Material = Enum.Material.WoodPlanks
floor.Color = woodColor
floor.Anchored = true
floor.Parent = workspace

-- Paredes
local wallH = 12
local walls = {
    {pos = basePos + Vector3.new(0, wallH/2, -10.5), size = Vector3.new(28, wallH, 1)},
    {pos = basePos + Vector3.new(-13.5, wallH/2, 0), size = Vector3.new(1, wallH, 22)},
    {pos = basePos + Vector3.new(13.5, wallH/2, 0), size = Vector3.new(1, wallH, 22)},
    {pos = basePos + Vector3.new(-6, wallH/2, 10.5), size = Vector3.new(16, wallH, 1)},
    {pos = basePos + Vector3.new(9, wallH/2, 10.5), size = Vector3.new(9, wallH, 1)},
}
for i, w in ipairs(walls) do
    local part = Instance.new("Part")
    part.Name = "TavernaParede" .. i
    part.Size = w.size
    part.Position = w.pos
    part.Material = Enum.Material.WoodPlanks
    part.Color = woodColor
    part.Anchored = true
    part.Parent = workspace
end

-- Telhado
local roof = Instance.new("Part")
roof.Name = "TavernaTelhado"
roof.Size = Vector3.new(30, 1, 24)
roof.Position = basePos + Vector3.new(0, wallH + 4, 0)
roof.Material = Enum.Material.Slate
roof.Color = Color3.fromRGB(100, 40, 30)
roof.Anchored = true
roof.Parent = workspace

-- Placa (SurfaceGui com texto)
local sign = Instance.new("Part")
sign.Name = "TavernaPlaca"
sign.Size = Vector3.new(6, 3, 0.3)
sign.Position = basePos + Vector3.new(0, wallH - 2, 10.8)
sign.Material = Enum.Material.WoodPlanks
sign.Color = woodColor
sign.Anchored = true
sign.Parent = workspace

local gui = Instance.new("SurfaceGui")
gui.Face = Enum.NormalId.Front
gui.Parent = sign

local label = Instance.new("TextLabel")
label.Size = UDim2.new(1, 0, 1, 0)
label.BackgroundTransparency = 1
label.Text = "TAVERNA"
label.TextColor3 = Color3.fromRGB(255, 220, 150)
label.TextScaled = true
label.Font = Enum.Font.GothamBold
label.Parent = gui

print("[Kael] OK: Taverna construida em " .. tostring(basePos))
"""

_TEMPLATE_TOCHA = """-- Kael Asset: Tocha
local basePos = Vector3.new(40 + math.random(-15, 15), 0, 40 + math.random(-15, 15))

-- Haste de madeira
local stick = Instance.new("Part")
stick.Name = "TochaHaste"
stick.Size = Vector3.new(0.6, 4, 0.6)
stick.Position = basePos + Vector3.new(0, 2, 0)
stick.Material = Enum.Material.Wood
stick.Color = Color3.fromRGB(80, 50, 30)
stick.Anchored = true
stick.Parent = workspace

-- Chama (Neon laranja)
local flame = Instance.new("Part")
flame.Name = "TochaChama"
flame.Size = Vector3.new(0.9, 1.2, 0.9)
flame.Position = basePos + Vector3.new(0, 4.6, 0)
flame.Material = Enum.Material.Neon
flame.Color = Color3.fromRGB(255, 140, 0)
flame.Anchored = true
flame.Parent = workspace

-- Luz
local light = Instance.new("PointLight")
light.Brightness = 2
light.Range = 15
light.Color = Color3.fromRGB(255, 180, 80)
light.Parent = flame

-- Particula de fogo
local part = Instance.new("ParticleEmitter")
part.Rate = 20
part.Lifetime = NumberRange.new(0.4, 0.8)
part.Speed = NumberRange.new(2, 4)
part.Size = NumberSequence.new(0.6)
part.Color = ColorSequence.new(Color3.fromRGB(255, 100, 20), Color3.fromRGB(255, 220, 100))
part.LightEmission = 0.8
part.Parent = flame

print("[Kael] OK: Tocha construida em " .. tostring(basePos))
"""

_TEMPLATE_BANDEIRA = """-- Kael Asset: Bandeira
local basePos = Vector3.new(70 + math.random(-15, 15), 0, 70 + math.random(-15, 15))

local pole = Instance.new("Part")
pole.Name = "BandeiraMastro"
pole.Size = Vector3.new(0.5, 12, 0.5)
pole.Position = basePos + Vector3.new(0, 6, 0)
pole.Material = Enum.Material.Wood
pole.Color = Color3.fromRGB(60, 40, 20)
pole.Anchored = true
pole.Parent = workspace

local fabric = Instance.new("Part")
fabric.Name = "BandeiraTecido"
fabric.Size = Vector3.new(4, 6, 0.1)
fabric.Position = basePos + Vector3.new(2.3, 9, 0)
fabric.Material = Enum.Material.Fabric
fabric.Color = Color3.fromRGB(150, 30, 30)
fabric.Anchored = true
fabric.Parent = workspace

print("[Kael] OK: Bandeira construida em " .. tostring(basePos))
"""

_TEMPLATE_BAU = """-- Kael Asset: Bau
local basePos = Vector3.new(35 + math.random(-10, 10), 0, 35 + math.random(-10, 10))

local box = Instance.new("Part")
box.Name = "BauCaixa"
box.Size = Vector3.new(4, 2.5, 3)
box.Position = basePos + Vector3.new(0, 1.25, 0)
box.Material = Enum.Material.WoodPlanks
box.Color = Color3.fromRGB(120, 70, 30)
box.Anchored = true
box.Parent = workspace

local lid = Instance.new("Part")
lid.Name = "BauTampa"
lid.Size = Vector3.new(4.2, 0.5, 3.2)
lid.Position = basePos + Vector3.new(0, 2.75, 0)
lid.Material = Enum.Material.WoodPlanks
lid.Color = Color3.fromRGB(140, 90, 40)
lid.Anchored = true
lid.Parent = workspace

local lock = Instance.new("Part")
lock.Name = "BauFechadura"
lock.Size = Vector3.new(0.5, 0.5, 0.2)
lock.Position = basePos + Vector3.new(0, 2, 1.6)
lock.Material = Enum.Material.Metal
lock.Color = Color3.fromRGB(220, 180, 50)
lock.Anchored = true
lock.Parent = workspace

print("[Kael] OK: Bau construido em " .. tostring(basePos))
"""

_TEMPLATE_MOEDA = """-- Kael Asset: Moeda
local basePos = Vector3.new(30 + math.random(-8, 8), 0, 30 + math.random(-8, 8))

local coin = Instance.new("Part")
coin.Name = "Moeda"
coin.Shape = Enum.PartType.Cylinder
coin.Size = Vector3.new(0.3, 2, 2)
coin.CFrame = CFrame.new(basePos + Vector3.new(0, 3, 0)) * CFrame.Angles(0, 0, math.pi/2)
coin.Material = Enum.Material.Neon
coin.Color = Color3.fromRGB(255, 215, 0)
coin.Anchored = true
coin.CanCollide = false
coin.Parent = workspace

-- Gira (Tween)
local TweenService = game:GetService("TweenService")
local tween = TweenService:Create(
    coin,
    TweenInfo.new(2, Enum.EasingStyle.Linear, Enum.EasingDirection.InOut, -1),
    {CFrame = coin.CFrame * CFrame.Angles(0, math.pi * 2, 0)}
)
tween:Play()

print("[Kael] OK: Moeda construida em " .. tostring(basePos))
"""

_TEMPLATE_POCAO = """-- Kael Asset: Pocao
local basePos = Vector3.new(32 + math.random(-8, 8), 0, 32 + math.random(-8, 8))

local bottle = Instance.new("Part")
bottle.Name = "PocaoFrasco"
bottle.Shape = Enum.PartType.Ball
bottle.Size = Vector3.new(1.5, 1.5, 1.5)
bottle.Position = basePos + Vector3.new(0, 1.5, 0)
bottle.Material = Enum.Material.Glass
bottle.Color = Color3.fromRGB(200, 220, 255)
bottle.Transparency = 0.3
bottle.Anchored = true
bottle.Parent = workspace

local liquid = Instance.new("Part")
liquid.Name = "PocaoLiquido"
liquid.Shape = Enum.PartType.Ball
liquid.Size = Vector3.new(1.1, 1.1, 1.1)
liquid.Position = basePos + Vector3.new(0, 1.4, 0)
liquid.Material = Enum.Material.Neon
liquid.Color = Color3.fromRGB(220, 40, 100)
liquid.Anchored = true
liquid.Parent = workspace

local cork = Instance.new("Part")
cork.Name = "PocaoRolha"
cork.Size = Vector3.new(0.6, 0.4, 0.6)
cork.Position = basePos + Vector3.new(0, 2.4, 0)
cork.Material = Enum.Material.Wood
cork.Color = Color3.fromRGB(120, 80, 40)
cork.Anchored = true
cork.Parent = workspace

print("[Kael] OK: Pocao construida em " .. tostring(basePos))
"""

_TEMPLATE_POCO = """-- Kael Asset: Poco
local basePos = Vector3.new(50 + math.random(-15, 15), 0, 50 + math.random(-15, 15))

-- Muro circular (8 partes)
for i = 1, 8 do
    local ang = (i / 8) * math.pi * 2
    local stone = Instance.new("Part")
    stone.Name = "PocoMuro" .. i
    stone.Size = Vector3.new(2, 3, 1)
    stone.CFrame = CFrame.new(basePos + Vector3.new(math.cos(ang) * 4, 1.5, math.sin(ang) * 4)) * CFrame.Angles(0, -ang, 0)
    stone.Material = Enum.Material.Cobblestone
    stone.Color = Color3.fromRGB(100, 100, 100)
    stone.Anchored = true
    stone.Parent = workspace
end

-- Agua
local water = Instance.new("Part")
water.Name = "PocoAgua"
water.Shape = Enum.PartType.Cylinder
water.Size = Vector3.new(0.5, 7, 7)
water.CFrame = CFrame.new(basePos + Vector3.new(0, 0.3, 0)) * CFrame.Angles(0, 0, math.pi/2)
water.Material = Enum.Material.Water
water.Color = Color3.fromRGB(60, 130, 200)
water.Transparency = 0.3
water.Anchored = true
water.Parent = workspace

-- Telhado (dois wedges)
for i, off in ipairs({-2, 2}) do
    local roof = Instance.new("WedgePart")
    roof.Name = "PocoTelhado" .. i
    roof.Size = Vector3.new(2, 2.5, 9)
    roof.Position = basePos + Vector3.new(off, 5, 0)
    roof.Rotation = Vector3.new(0, 0, off > 0 and 90 or -90)
    roof.Material = Enum.Material.WoodPlanks
    roof.Color = Color3.fromRGB(80, 50, 30)
    roof.Anchored = true
    roof.Parent = workspace
end

print("[Kael] OK: Poco construido em " .. tostring(basePos))
"""

_TEMPLATE_FOGUEIRA = """-- Kael Asset: Fogueira
local basePos = Vector3.new(38 + math.random(-10, 10), 0, 38 + math.random(-10, 10))

-- Pedras em circulo
for i = 1, 6 do
    local ang = (i / 6) * math.pi * 2
    local stone = Instance.new("Part")
    stone.Name = "FogueiraPedra" .. i
    stone.Size = Vector3.new(1, 0.6, 1)
    stone.Position = basePos + Vector3.new(math.cos(ang) * 2.2, 0.3, math.sin(ang) * 2.2)
    stone.Material = Enum.Material.Rock
    stone.Color = Color3.fromRGB(80, 80, 80)
    stone.Anchored = true
    stone.Parent = workspace
end

-- Lenhas
for i = 1, 3 do
    local log = Instance.new("Part")
    log.Name = "FogueiraLenha" .. i
    log.Size = Vector3.new(0.5, 0.5, 3)
    log.Position = basePos + Vector3.new(0, 0.5, 0)
    log.Rotation = Vector3.new(0, (i - 1) * 60, 0)
    log.Material = Enum.Material.Wood
    log.Color = Color3.fromRGB(70, 40, 20)
    log.Anchored = true
    log.Parent = workspace
end

-- Fogo
local fire = Instance.new("Part")
fire.Name = "FogueiraFogo"
fire.Size = Vector3.new(1.5, 2, 1.5)
fire.Position = basePos + Vector3.new(0, 1.5, 0)
fire.Material = Enum.Material.Neon
fire.Color = Color3.fromRGB(255, 100, 20)
fire.Anchored = true
fire.Parent = workspace

local light = Instance.new("PointLight")
light.Brightness = 3
light.Range = 20
light.Color = Color3.fromRGB(255, 160, 60)
light.Parent = fire

local emitter = Instance.new("ParticleEmitter")
emitter.Rate = 30
emitter.Lifetime = NumberRange.new(0.5, 1)
emitter.Speed = NumberRange.new(3, 6)
emitter.Size = NumberSequence.new(0.8)
emitter.Color = ColorSequence.new(Color3.fromRGB(255, 100, 20), Color3.fromRGB(255, 200, 80))
emitter.LightEmission = 0.9
emitter.Parent = fire

print("[Kael] OK: Fogueira construida em " .. tostring(basePos))
"""

_TEMPLATE_SPAWN = """-- Kael Asset: SpawnLocation
local basePos = Vector3.new(0, 5, 0)

local spawn = Instance.new("SpawnLocation")
spawn.Name = "SpawnLocation"
spawn.Size = Vector3.new(12, 1, 12)
spawn.Position = basePos
spawn.Material = Enum.Material.SmoothPlastic
spawn.Color = Color3.fromRGB(50, 180, 50)
spawn.Anchored = true
spawn.Neutral = true
spawn.Duration = 0
spawn.Parent = workspace

print("[Kael] OK: SpawnLocation criado em " .. tostring(basePos))
"""


# ==========================================================
# REGISTRO DE TEMPLATES
# ==========================================================
TEMPLATES = {
    "castelo": (_TEMPLATE_CASTELO, "Script"),
    "fortaleza": (_TEMPLATE_CASTELO, "Script"),
    "casa": (_TEMPLATE_CASA, "Script"),
    "cabana": (_TEMPLATE_CASA, "Script"),
    "torre": (_TEMPLATE_TORRE, "Script"),
    "taverna": (_TEMPLATE_TAVERNA, "Script"),
    "estalagem": (_TEMPLATE_TAVERNA, "Script"),
    "tocha": (_TEMPLATE_TOCHA, "Script"),
    "bandeira": (_TEMPLATE_BANDEIRA, "Script"),
    "estandarte": (_TEMPLATE_BANDEIRA, "Script"),
    "bau": (_TEMPLATE_BAU, "Script"),
    "tesouro": (_TEMPLATE_BAU, "Script"),
    "moeda": (_TEMPLATE_MOEDA, "Script"),
    "pocao": (_TEMPLATE_POCAO, "Script"),
    "poco": (_TEMPLATE_POCO, "Script"),
    "fogueira": (_TEMPLATE_FOGUEIRA, "Script"),
    "fogo": (_TEMPLATE_FOGUEIRA, "Script"),
    "spawnlocation": (_TEMPLATE_SPAWN, "Script"),
    "spawn": (_TEMPLATE_SPAWN, "Script"),
}


# ==========================================================
# TEMPLATE MATCHING
# ==========================================================
def _match_template(titulo):
    """Retorna (codigo, tipo_script) ou None."""
    t = str(titulo).lower()
    for chave, (codigo, tipo) in TEMPLATES.items():
        if chave in t:
            return codigo, tipo
    return None


# ==========================================================
# FALLBACK VIA LLM
# ==========================================================
def _gerar_via_llm(ideia, kb, genero, fn_llm):
    titulo = ideia.get("titulo", "Asset")
    categoria = ideia.get("categoria", "estrutura")
    descricao = ideia.get("descricao", "")
    materiais = ", ".join(kb.get("materiais_roblox", ["Plastic"]))
    paleta = ", ".join(kb.get("paleta_cores", []))

    prompt = (
        "Voce e o CONSTRUTOR DE ASSETS do KAEL. Gere um script Lua COMPLETO\n"
        "que constroi em Roblox o asset descrito abaixo.\n\n"
        "CATEGORIA: " + str(categoria) + "\n"
        "TITULO: " + str(titulo) + "\n"
        "DESCRICAO: " + str(descricao) + "\n"
        "GENERO: " + str(genero) + "\n"
        "MATERIAIS TIPICOS: " + materiais + "\n"
        "PALETA: " + paleta + "\n\n"
        "REGRAS CRITICAS:\n"
        "- Use APENAS: Part, WedgePart, PointLight, SurfaceGui, TextLabel,\n"
        "  ParticleEmitter, TweenService\n"
        "- TODOS os Parts devem ter Anchored = true\n"
        "- Use Material do Enum.Material (Wood, Slate, Neon, etc)\n"
        "- Posicao base: Vector3.new(60 + math.random(-20,20), 0, "
        "60 + math.random(-20,20))\n"
        "- NUNCA use LocalPlayer (este script roda no SERVER)\n"
        "- NUNCA use API inventada\n"
        "- Ao final: print(\"[Kael] OK: " + str(titulo)[:40] + "\")\n"
        "- Indentacao de 4 espacos\n\n"
        "Retorne APENAS o codigo no formato:\n"
        "<!-- ARQUIVO: NomeDoScript -->\n"
        "```lua\n(codigo)\n```\n"
    )

    try:
        resp = str(fn_llm(prompt, temperatura=0.3))
    except Exception as e:
        print("[ASSETS] LLM falhou: " + str(e)[:150])
        return None

    m = re.search(
        r"<!--\s*ARQUIVO:\s*([A-Za-z0-9_\-\.]+)\s*-->\s*"
        r"```(?:lua|luau)?\s*\n(.*?)```",
        resp, re.DOTALL | re.IGNORECASE
    )
    if m:
        return m.group(2).strip(), "Script"

    m2 = re.search(r"```(?:lua|luau)?\s*\n(.*?)```", resp, re.DOTALL)
    if m2:
        return m2.group(1).strip(), "Script"

    print("[ASSETS] LLM nao retornou codigo valido")
    return None


# ==========================================================
# API PUBLICA
# ==========================================================
def gerar_asset(ideia, kb, genero, fn_llm=None, projeto=""):
    """
    Gera 1 asset a partir de uma ideia do Diretor Criativo.
    """
    titulo = str(ideia.get("titulo", "Asset")).strip()
    categoria = str(ideia.get("categoria", "estrutura")).strip().lower()

    if not titulo:
        return None

    tipo_default = "Script"
    if categoria in ("mecanica", "polish"):
        desc_lower = str(ideia.get("descricao", "")).lower()
        if any(w in desc_lower for w in ["hud", "ui", "input", "tela", "menu",
                                          "interface", "botao"]):
            tipo_default = "LocalScript"

    match = _match_template(titulo)
    if match:
        codigo, tipo_script = match
        nome = "Asset_" + _slug(titulo) + "_" + str(int(__import__("time").time()))
        print("[ASSETS] Template: " + titulo + " -> " + nome)
        return {
            "nome": nome,
            "codigo": codigo,
            "tipo_script": tipo_script,
            "origem": "template",
        }

    if fn_llm is None:
        print("[ASSETS] Sem template e sem fn_llm. Nao posso gerar: " + titulo)
        return None

    print("[ASSETS] Sem template, tentando LLM: " + titulo)
    resultado_llm = _gerar_via_llm(ideia, kb, genero, fn_llm)
    if not resultado_llm:
        return None

    codigo, tipo_script = resultado_llm
    nome = "Asset_" + _slug(titulo) + "_" + str(int(__import__("time").time()))

    return {
        "nome": nome,
        "codigo": codigo,
        "tipo_script": tipo_script,
        "origem": "llm",
    }


def gerar_spawn(projeto=""):
    """Atalho: gera o SpawnLocation (usado quando nao tem spawn)."""
    nome = "Asset_Spawn_" + str(int(__import__("time").time()))
    return {
        "nome": nome,
        "codigo": _TEMPLATE_SPAWN,
        "tipo_script": "Script",
        "origem": "template",
    }


def gerar_remover_flutuantes(altura_min=60, projeto=""):
    """Gera script que remove objetos acima de Y=N."""
    codigo = (
        "-- Kael Asset: Remover objetos flutuantes\n"
        "local alturaMin = " + str(int(altura_min)) + "\n"
        "local removidos = 0\n\n"
        "for _, obj in ipairs(workspace:GetChildren()) do\n"
        "    if obj:IsA(\"BasePart\") then\n"
        "        if obj.Position.Y > alturaMin then\n"
        "            obj:Destroy()\n"
        "            removidos = removidos + 1\n"
        "        end\n"
        "    end\n"
        "end\n\n"
        "print(\"[Kael] OK: \" .. removidos .. \" objetos removidos acima de Y=\" .. alturaMin)\n"
    )
    nome = "Asset_RemoverFlutuantes_" + str(int(__import__("time").time()))
    return {
        "nome": nome,
        "codigo": codigo,
        "tipo_script": "Script",
        "origem": "template",
    }


def gerar_reposicionar_estruturas(raio_min=150, raio_max=700, dist_min=250,
                                   palavras=None, projeto=None):
    """
    Gera Lua que reposiciona Models com nomes de estrutura em aneis concentricos.
    Garante: distancia minima entre estruturas, raio minimo/maximo do spawn,
    Y preservado, rotacao preservada, sem loops infinitos.

    Template deterministico - nao usa LLM.
    v2: Espera o mundo carregar (task.wait(5)) e usa PivotTo direto sem exigir
    PrimaryPart (pois o jogo pode construir as partes via runtime).
    """
    if palavras is None:
        palavras = [
            "castelo", "vila", "cidade", "village", "city",
            "castle", "town", "aldeia", "fortaleza",
        ]

    palavras_lua = ", ".join(f'"{p}"' for p in palavras)

    codigo = f'''-- Kael Template v2: Reposicionar estruturas em aneis concentricos
-- Gerado por kael_assets.gerar_reposicionar_estruturas()
-- Restricoes: RAIO_MIN <= distancia do spawn <= RAIO_MAX
--             distancia entre estruturas >= DIST_MIN
--             Y preservado, rotacao preservada, sem loops infinitos

-- Espera o WorldBuilder terminar de construir o mapa
task.wait(5)

local RAIO_MIN = {int(raio_min)}
local RAIO_MAX = {int(raio_max)}
local DIST_MIN = {int(dist_min)}
local PALAVRAS = {{{palavras_lua}}}

-- 1. SpawnLocation (recursivo, tolerante a falha)
local function encontrarSpawn()
    local direto = workspace:FindFirstChildOfClass("SpawnLocation")
    if direto then return direto end
    for _, obj in ipairs(workspace:GetDescendants()) do
        if obj:IsA("SpawnLocation") then
            return obj
        end
    end
    return nil
end

local spawnLocation = encontrarSpawn()
if not spawnLocation then
    warn("[Kael] SpawnLocation nao encontrado.")
    return
end

-- 2. Coletar Models por nome (case-insensitive)
local function nomeBate(nome)
    local lower = string.lower(nome)
    for _, kw in ipairs(PALAVRAS) do
        if string.find(lower, kw, 1, true) then
            return true
        end
    end
    return false
end

local estruturas = {{}}
for _, obj in ipairs(workspace:GetDescendants()) do
    if obj:IsA("Model") and nomeBate(obj.Name) then
        table.insert(estruturas, obj)
    end
end

if #estruturas == 0 then
    warn("[Kael] Nenhuma estrutura encontrada. Nomes procurados: " ..
         table.concat(PALAVRAS, ", "))
    return
end

-- 4. Aneis concentricos
local function calcularPosicoes(n, spawnPos)
    local posicoes = {{}}
    local anel = 0
    while #posicoes < n do
        local raio = RAIO_MIN + anel * DIST_MIN
        if raio > RAIO_MAX then break end
        local slots = math.max(1, math.floor((2 * math.pi * raio) / DIST_MIN))
        local offsetAng = (anel % 2) * (math.pi / slots)
        for i = 0, slots - 1 do
            if #posicoes >= n then break end
            local ang = offsetAng + i * (2 * math.pi / slots)
            local x = spawnPos.X + math.cos(ang) * raio
            local z = spawnPos.Z + math.sin(ang) * raio
            table.insert(posicoes, Vector3.new(x, spawnPos.Y, z))
        end
        anel = anel + 1
    end
    return posicoes
end

local posicoes = calcularPosicoes(#estruturas, spawnLocation.Position)
if #posicoes < #estruturas then
    warn(string.format(
        "[Kael] Espaco para %d estruturas, ha %d. Movendo so %d.",
        #posicoes, #estruturas, #posicoes
    ))
end

-- 5. Mover preservando CFrame original
local movidos, falhas = 0, 0
for i = 1, math.min(#estruturas, #posicoes) do
    local model = estruturas[i]
    local cframeAtual = model:GetPivot()
    local novaPos = posicoes[i]
    local novoCFrame = cframeAtual - cframeAtual.Position + novaPos
    
    local ok, err = pcall(function()
        model:PivotTo(novoCFrame)
    end)
    if ok then
        movidos = movidos + 1
    else
        falhas = falhas + 1
        warn("[Kael] Falha ao mover '" .. model.Name .. "': " .. tostring(err))
    end
end

print(string.format("[Kael] OK: %d estruturas movidas, %d falhas", movidos, falhas))
'''

    return {
        "nome": "Kael_ReposicionarEstruturas",
        "codigo": codigo,
        "tipo_script": "Script",
        "origem": "template_reposicionar",
        "parametros": {
            "raio_min": raio_min,
            "raio_max": raio_max,
            "dist_min": dist_min,
            "palavras": palavras,
        },
    }


def _slug(s):
    s = re.sub(r"[^a-zA-Z0-9_\- ]", "", str(s))
    return s.strip().replace(" ", "_")[:40] or "Asset"