-- Kael Roblox Studio Bridge protocol v1.
-- Enable "Allow HTTP Requests" in Studio and keep the API bound to localhost.
local HttpService = game:GetService("HttpService")
local Workspace = game:GetService("Workspace")
local ServerStorage = game:GetService("ServerStorage")
local Players = game:GetService("Players")

local API = "http://127.0.0.1:8000"
local PROTOCOL_VERSION = 1
local MAX_INSTANCES = 500
local MAX_SCRIPT_COUNT = 100
local MAX_SCRIPT_CHARS = 50000
local MAX_TOTAL_SCRIPT_CHARS = 500000
local TERRAIN_SAMPLE_INTERVAL = 30
local polling = false
local busy = false
local lastStateSent = 0
local cachedTerrainSummary = nil
local lastTerrainSample = 0

local clientId = plugin:GetSetting("KaelClientId")
if type(clientId) ~= "string" or #clientId < 8 then
	clientId = HttpService:GenerateGUID(false)
	plugin:SetSetting("KaelClientId", clientId)
end

local function log(message)
	print("[Kael Bridge] " .. tostring(message))
end

local function postJson(path, payload)
	payload.protocol_version = PROTOCOL_VERSION
	payload.client_id = clientId
	local ok, response = pcall(function()
		return HttpService:RequestAsync({
			Url = API .. path,
			Method = "POST",
			Headers = { ["Content-Type"] = "application/json" },
			Body = HttpService:JSONEncode(payload),
		})
	end)
	if not ok then
		return false, tostring(response)
	end
	if not response.Success then
		return false, "HTTP " .. tostring(response.StatusCode) .. ": " .. response.Body
	end
	return true, response.Body
end

local function getJson(path)
	local ok, response = pcall(function()
		return HttpService:RequestAsync({
			Url = API .. path,
			Method = "GET",
		})
	end)
	if not ok then
		return nil, tostring(response)
	end
	if not response.Success then
		return nil, "HTTP " .. tostring(response.StatusCode) .. ": " .. response.Body
	end
	local decodedOk, decoded = pcall(function()
		return HttpService:JSONDecode(response.Body)
	end)
	if not decodedOk then
		return nil, "Resposta JSON inválida."
	end
	return decoded
end

local function backupGeneratedAssets(taskData)
	local folder = Workspace:FindFirstChild("Kael_GeneratedAssets")
	if not folder then
		return { backup_id = nil, models = 0 }
	end
	if not folder:IsA("Folder") then
		error("Kael_GeneratedAssets não é uma Folder.")
	end
	if type(taskData.task_id) ~= "string"
		or #taskData.task_id ~= 32
		or not string.match(taskData.task_id, "^[a-f0-9]+$") then
		error("Identificador da tarefa inválido.")
	end
	local backup = getBackupFolder("Kael_BackupWorld")
	local backupId = "KaelAssetsBackup_" .. string.sub(taskData.task_id, 1, 8)
	if backup:FindFirstChild(backupId) then
		error("Já existe um backup de assets com esse identificador.")
	end
	local modelCount = #folder:GetChildren()
	local ok, backupError = pcall(function()
		folder.Name = backupId
		folder.Parent = backup
	end)
	if not ok then
		folder.Name = "Kael_GeneratedAssets"
		folder.Parent = Workspace
		error("Não foi possível guardar os assets em backup: " .. tostring(backupError))
	end
	return { backup_id = backupId, models = modelCount }
end

local function restoreGeneratedAssets(taskData)
	if type(taskData.backup_id) ~= "string"
		or not string.match(taskData.backup_id, "^KaelAssetsBackup_[a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9]$") then
		error("Identificador de backup de assets inválido.")
	end
	local backupFolder = ServerStorage:FindFirstChild("Kael_BackupWorld")
	local folder = backupFolder and backupFolder:FindFirstChild(taskData.backup_id)
	if not folder or not folder:IsA("Folder") then
		error("Backup de assets não encontrado.")
	end
	if Workspace:FindFirstChild("Kael_GeneratedAssets") then
		error("Já existem assets Kael no Workspace; remova-os antes de restaurar o backup.")
	end
	local ok, restoreError = pcall(function()
		folder.Name = "Kael_GeneratedAssets"
		folder.Parent = Workspace
	end)
	if not ok then
		folder.Name = taskData.backup_id
		folder.Parent = backupFolder
		error("Não foi possível restaurar os assets: " .. tostring(restoreError))
	end
	return { backup_id = taskData.backup_id, restaurado = true }
end

local function getSpawnPosition()
	for _, item in ipairs(Workspace:GetDescendants()) do
		if item:IsA("SpawnLocation") then
			return item.Position
		end
	end
	return Vector3.zero
end

local function collectTerrainSummary()
	if cachedTerrainSummary and os.clock() - lastTerrainSample < TERRAIN_SAMPLE_INTERVAL then
		return cachedTerrainSummary
	end
	local center = getSpawnPosition()
	local region = Region3.new(
		center - Vector3.new(32, 32, 32),
		center + Vector3.new(32, 32, 32)
	):ExpandToGrid(4)
	local ok, summary = pcall(function()
		local materials, occupancies = Workspace.Terrain:ReadVoxels(region, 4)
		local dimensions = materials.Size
		local minY = region.CFrame.Position.Y - region.Size.Y / 2
		local heightmap = {}
		local minHeight = nil
		local maxHeight = nil
		local emptyColumns = 0
		for xIndex = 1, dimensions.X, 2 do
			local row = {}
			for zIndex = 1, dimensions.Z, 2 do
				local height = false
				for yIndex = dimensions.Y, 1, -1 do
					if occupancies[xIndex][yIndex][zIndex] > 0.1
						and materials[xIndex][yIndex][zIndex] ~= Enum.Material.Air then
						height = minY + (yIndex - 1) * 4
						break
					end
				end
				if height == false then
					emptyColumns += 1
				else
					minHeight = minHeight and math.min(minHeight, height) or height
					maxHeight = maxHeight and math.max(maxHeight, height) or height
				end
				table.insert(row, height)
			end
			table.insert(heightmap, row)
		end
		return {
			range = 64,
			sample_step = 8,
			heightmap = heightmap,
			has_terrain = minHeight ~= nil,
			min_height = minHeight or 0,
			max_height = maxHeight or 0,
			empty_columns = emptyColumns,
		}
	end)
	if not ok then
		cachedTerrainSummary = { error = string.sub(tostring(summary), 1, 160) }
	else
		cachedTerrainSummary = summary
	end
	lastTerrainSample = os.clock()
	return cachedTerrainSummary
end

local function collectState(includeScriptContent)
	local instances = {}
	for _, item in ipairs(Workspace:GetDescendants()) do
		if #instances >= MAX_INSTANCES then
			break
		end
		if item:IsA("BasePart") then
			local position = item.Position
			table.insert(instances, {
				nome = item.Name,
				classe = item.ClassName,
				y = position.Y,
				posicao = string.format("%.1f, %.1f, %.1f", position.X, position.Y, position.Z),
			})
		end
	end

	local scriptNames = {}
	local scriptsWithContent = {}
	local totalScriptChars = 0
	local scriptContentLimited = false
	for _, item in ipairs(game:GetDescendants()) do
		if item:IsA("Script") or item:IsA("LocalScript") or item:IsA("ModuleScript") then
			local fullName = item:GetFullName()
			if item:IsA("Script") and #scriptNames < MAX_INSTANCES then
				if #fullName <= 256 then
					table.insert(scriptNames, fullName)
				end
			end
			if includeScriptContent and #scriptsWithContent >= MAX_SCRIPT_COUNT then
				scriptContentLimited = true
				break
			elseif includeScriptContent then
				local sourceOk, source = pcall(function()
					return item.Source
				end)
				if sourceOk and type(source) == "string" then
					local available = math.max(0, MAX_TOTAL_SCRIPT_CHARS - totalScriptChars)
					if available == 0 then
						scriptContentLimited = true
						break
					end
					local bounded = string.sub(source, 1, math.min(MAX_SCRIPT_CHARS, available))
					if #fullName <= 256 then
						totalScriptChars += #bounded
						table.insert(scriptsWithContent, {
							nome = fullName,
							tipo = item.ClassName,
							codigo = bounded,
							truncado = #bounded < #source,
						})
					else
						scriptContentLimited = true
					end
					if #bounded < #source then
						scriptContentLimited = true
					end
				else
					scriptContentLimited = true
				end
			end
		end
	end

	return {
		motor = "RobloxStudio",
		total_instancias = #instances,
		instancias = instances,
		scripts_servidor = scriptNames,
		scripts_com_conteudo = scriptsWithContent,
		scripts_com_conteudo_limitado = scriptContentLimited,
		pedir_analise = includeScriptContent,
		terreno = collectTerrainSummary(),
	}
end

local function sendState(includeScriptContent)
	local ok, err = postJson("/estado_jogo", collectState(includeScriptContent == true))
	if not ok then
		log("Falha ao enviar estado: " .. err)
		return false
	end
	lastStateSent = os.clock()
	log("Estado enviado ao Kael.")
	return true
end

local function getBackupFolder(folderName)
	local folder = ServerStorage:FindFirstChild(folderName)
	if folder and not folder:IsA("Folder") then
		error("Já existe um objeto incompatível chamado " .. folderName .. ".")
	end
	if not folder then
		folder = Instance.new("Folder")
		folder.Name = folderName
		folder.Parent = ServerStorage
	end
	return folder
end

local function isCharacterPart(part)
	local ancestor = part.Parent
	while ancestor and ancestor ~= Workspace do
		if ancestor:IsA("Model") and Players:GetPlayerFromCharacter(ancestor) then
			return true
		end
		ancestor = ancestor.Parent
	end
	return false
end

local function cleanFloatingParts(taskData)
	local mode = taskData.modo
	local maxDistance = taskData.max_distance
	local raycastParams = RaycastParams.new()
	raycastParams.FilterType = Enum.RaycastFilterType.Exclude
	local candidates = {}

	for _, item in ipairs(Workspace:GetDescendants()) do
		if item:IsA("BasePart") and item.Anchored and not isCharacterPart(item) then
			local exclude = { item }
			if item.Parent and item.Parent:IsA("Model") then
				table.insert(exclude, item.Parent)
			end
			raycastParams.FilterDescendantsInstances = exclude
			local hit = Workspace:Raycast(
				item.Position + Vector3.new(0, 0.1, 0),
				Vector3.new(0, -maxDistance, 0),
				raycastParams
			)
			if not hit then
				table.insert(candidates, item)
			end
		end
	end

	local names = {}
	for index = 1, math.min(#candidates, 30) do
		table.insert(names, candidates[index]:GetFullName())
	end
	local removed = 0
	if mode == "REMOVER" then
		local backupFolder
		if taskData.backup then
			backupFolder = getBackupFolder("Kael_Removidos")
		end
		for _, item in ipairs(candidates) do
			if item.Parent then
				if backupFolder then
					item.Parent = backupFolder
				else
					item:Destroy()
				end
				removed += 1
			end
		end
	end
	return {
		detectados = #candidates,
		removidos = removed,
		modo = mode,
		backup = taskData.backup,
		nomes = names,
	}
end

local function cleanKaelBuild()
	local backup = getBackupFolder("Kael_BackupWorld")
	local moved = 0
	for _, item in ipairs(Workspace:GetDescendants()) do
		if item.Parent and item:IsDescendantOf(Workspace)
			and (string.sub(item.Name, 1, 6) == "World_" or string.sub(item.Name, 1, 5) == "Kael_") then
			item.Parent = backup
			moved += 1
		end
	end
	return { backup = true, moved = moved }
end

local function generateTerrain(taskData)
	if type(taskData.task_id) ~= "string"
		or #taskData.task_id ~= 32
		or not string.match(taskData.task_id, "^[a-f0-9]+$") then
		error("Identificador da tarefa inválido.")
	end
	local presets = {
		planicies = { amplitude = 5, scale = 150 },
		colinas = { amplitude = 22, scale = 90 },
		montanhas = { amplitude = 48, scale = 110 },
		ilha = { amplitude = 16, scale = 75 },
	}
	local preset = presets[taskData.preset]
	if not preset then
		error("Preset de terreno não suportado.")
	end
	if type(taskData.size) ~= "number"
		or taskData.size % 1 ~= 0
		or (taskData.size ~= 256 and taskData.size ~= 384 and taskData.size ~= 512)
		or type(taskData.seed) ~= "number"
		or taskData.seed % 1 ~= 0
		or taskData.seed < 0
		or taskData.seed > 2147483647 then
		error("Parâmetros de terreno inválidos.")
	end
	local terrain = Workspace.Terrain
	local center = getSpawnPosition()
	local size = taskData.size
	local worldBounds = {
		center.X - size / 2,
		center.X + size / 2,
		center.Y - 64,
		center.Y + 64,
		center.Z - size / 2,
		center.Z + size / 2,
	}
	for _, coordinate in ipairs(worldBounds) do
		if math.abs(coordinate / 4) >= 32760 then
			error("O terreno solicitado excede os limites de coordenadas do Studio.")
		end
	end
	local minCell = Vector3int16.new(
		math.floor((center.X - size / 2) / 4),
		math.floor((center.Y - 64) / 4),
		math.floor((center.Z - size / 2) / 4)
	)
	local maxCell = Vector3int16.new(
		math.ceil((center.X + size / 2) / 4),
		math.ceil((center.Y + 64) / 4),
		math.ceil((center.Z + size / 2) / 4)
	)
	local corner = minCell
	local backupId = "KaelTerrainBackup_" .. string.sub(taskData.task_id, 1, 8)
	if ServerStorage:FindFirstChild(backupId) then
		error("Já existe um backup com esse identificador.")
	end

	local backup = terrain:CopyRegion(Region3int16.new(minCell, maxCell))
	backup.Name = backupId
	backup:SetAttribute("CornerX", corner.X)
	backup:SetAttribute("CornerY", corner.Y)
	backup:SetAttribute("CornerZ", corner.Z)
	backup.Parent = ServerStorage

	local minY = minCell.Y * 4
	local maxY = maxCell.Y * 4
	local baseY = center.Y - 4
	local columns = 0
	local ok, generationError = pcall(function()
		terrain:FillBlock(
			CFrame.new(center.X, (minY + maxY) / 2, center.Z),
			Vector3.new(size, maxY - minY, size),
			Enum.Material.Air
		)
		for xOffset = 8, size - 8, 16 do
			for zOffset = 8, size - 8, 16 do
				local x = center.X - size / 2 + xOffset
				local z = center.Z - size / 2 + zOffset
				local noise = math.noise(
					(x + taskData.seed) / preset.scale,
					(z - taskData.seed) / preset.scale,
					taskData.seed / 1000
				)
				local distance = math.sqrt((x - center.X) ^ 2 + (z - center.Z) ^ 2)
				local surface = baseY + noise * preset.amplitude
				local material = Enum.Material.Grass

				if distance < 48 then
					surface = baseY
				elseif taskData.preset == "ilha" and distance > size * 0.34 then
					surface = baseY + 4
					material = Enum.Material.Water
				elseif taskData.preset == "montanhas" and surface > baseY + 24 then
					material = surface > baseY + 38 and Enum.Material.Snow or Enum.Material.Rock
				elseif taskData.preset == "colinas" and surface > baseY + 14 then
					material = Enum.Material.Ground
				end

				surface = math.clamp(surface, minY + 8, center.Y + 48)
				terrain:FillBlock(
					CFrame.new(x, (minY + surface) / 2, z),
					Vector3.new(16, surface - minY, 16),
					material
				)
				columns += 1
			end
		end
	end)

	if not ok then
		local restored, restoreError = pcall(function()
			terrain:PasteRegion(backup, corner, true)
		end)
		cachedTerrainSummary = nil
		lastTerrainSample = 0
		if not restored then
			error(
				"Falha ao gerar terreno (" .. tostring(generationError)
					.. ") e também ao restaurar; mantenha o backup " .. backupId
					.. ". Erro ao restaurar: " .. tostring(restoreError)
			)
		end
		error("Geração falhou; terreno anterior restaurado. " .. tostring(generationError))
	end
	cachedTerrainSummary = nil
	lastTerrainSample = 0

	return {
		backup_id = backupId,
		preset = taskData.preset,
		size = size,
		seed = taskData.seed,
		columns = columns,
	}
end

local function restoreTerrain(taskData)
	if type(taskData.backup_id) ~= "string"
		or not string.match(taskData.backup_id, "^KaelTerrainBackup_[a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9][a-f0-9]$") then
		error("Identificador de backup de terreno inválido.")
	end
	local backup = ServerStorage:FindFirstChild(taskData.backup_id)
	if not backup or not backup:IsA("TerrainRegion") then
		error("Backup de terreno não encontrado.")
	end
	local x = backup:GetAttribute("CornerX")
	local y = backup:GetAttribute("CornerY")
	local z = backup:GetAttribute("CornerZ")
	if type(x) ~= "number" or type(y) ~= "number" or type(z) ~= "number" then
		error("O backup não contém coordenadas válidas.")
	end
	Workspace.Terrain:PasteRegion(
		backup,
		Vector3int16.new(x, y, z),
		true
	)
	cachedTerrainSummary = nil
	lastTerrainSample = 0
	return { backup_id = taskData.backup_id, restaurado = true }
end

local function createAssetPart(model, name, size, position, material, color, shape)
	local part = Instance.new(shape == "Wedge" and "WedgePart" or "Part")
	part.Name = name
	part.Size = size
	part.Position = position
	part.Anchored = true
	part.Material = material
	part.Color = color
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	if shape and shape ~= "Wedge" then
		part.Shape = shape
	end
	part.Parent = model
	return part
end

local function createAssets(taskData)
	local assetTypes = {
		casa = true,
		torre = true,
		arvore = true,
		rocha = true,
		cristal = true,
		acampamento = true,
		bau = true,
		ponte = true,
	}
	if not assetTypes[taskData.asset_type]
		or type(taskData.quantity) ~= "number"
		or taskData.quantity % 1 ~= 0
		or taskData.quantity < 1
		or taskData.quantity > 20
		or type(taskData.seed) ~= "number"
		or taskData.seed % 1 ~= 0
		or taskData.seed < 0
		or taskData.seed > 2147483647
		or type(taskData.task_id) ~= "string"
		or #taskData.task_id ~= 32
		or not string.match(taskData.task_id, "^[a-f0-9]+$") then
		error("Parâmetros de criação de assets inválidos.")
	end
	local folder = Workspace:FindFirstChild("Kael_GeneratedAssets")
	if folder and not folder:IsA("Folder") then
		error("Já existe um objeto incompatível chamado Kael_GeneratedAssets.")
	end
	if not folder then
		folder = Instance.new("Folder")
		folder.Name = "Kael_GeneratedAssets"
		folder.Parent = Workspace
	end
	local staged = Instance.new("Folder")
	staged.Name = "Kael_AssetStaging"

	local center = getSpawnPosition()
	local random = Random.new(taskData.seed)
	local generated = {}
	local placedPositions = {}
	local ok, creationError = pcall(function()
		for index = 1, taskData.quantity do
			local raycastParams = RaycastParams.new()
			raycastParams.FilterType = Enum.RaycastFilterType.Exclude
			local excluded = { folder }
			for _, player in ipairs(Players:GetPlayers()) do
				if player.Character then
					table.insert(excluded, player.Character)
				end
			end
			raycastParams.FilterDescendantsInstances = excluded
			local origin
			local spacing = taskData.asset_type == "ponte" and 48 or 28
			for _ = 1, 25 do
				local angle = random:NextNumber(0, math.pi * 2)
				local radius = random:NextNumber(56, 120)
				local candidate = Vector3.new(
					center.X + math.cos(angle) * radius,
					center.Y + 2,
					center.Z + math.sin(angle) * radius
				)
				local ground = Workspace:Raycast(
					candidate + Vector3.new(0, 256, 0),
					Vector3.new(0, -512, 0),
					raycastParams
				)
				local separated = ground ~= nil
				if ground then
					candidate = Vector3.new(candidate.X, ground.Position.Y, candidate.Z)
					for _, existing in ipairs(placedPositions) do
						local dx = candidate.X - existing.X
						local dz = candidate.Z - existing.Z
						if dx * dx + dz * dz < spacing * spacing then
							separated = false
							break
						end
					end
				end
				if separated then
					origin = candidate
					break
				end
			end
			if not origin then
				error("Não foi possível encontrar posições no chão sem sobreposição.")
			end
			table.insert(placedPositions, origin)

			local model = Instance.new("Model")
			model.Name = "Kael_" .. taskData.asset_type .. "_" .. string.sub(taskData.task_id, 1, 8) .. "_" .. index
			local primary
			local function add(name, size, offset, material, color, shape)
				local part = createAssetPart(
					model,
					name,
					size,
					origin + offset,
					material,
					color,
					shape
				)
				primary = primary or part
				return part
			end

			if taskData.asset_type == "casa" then
				add("Base", Vector3.new(20, 2, 20), Vector3.new(0, 1, 0), Enum.Material.WoodPlanks, Color3.fromRGB(105, 74, 52))
				add("Walls", Vector3.new(16, 12, 16), Vector3.new(0, 8, 0), Enum.Material.Wood, Color3.fromRGB(184, 142, 91))
				add("Roof", Vector3.new(22, 4, 22), Vector3.new(0, 16, 0), Enum.Material.Slate, Color3.fromRGB(86, 45, 42))
			elseif taskData.asset_type == "torre" then
				add("Base", Vector3.new(14, 2, 14), Vector3.new(0, 1, 0), Enum.Material.Slate, Color3.fromRGB(95, 98, 105))
				add("Tower", Vector3.new(10, 28, 10), Vector3.new(0, 16, 0), Enum.Material.Rock, Color3.fromRGB(126, 128, 132))
				add("Top", Vector3.new(16, 3, 16), Vector3.new(0, 31, 0), Enum.Material.Slate, Color3.fromRGB(75, 78, 85))
			elseif taskData.asset_type == "arvore" then
				add("Trunk", Vector3.new(4, 14, 4), Vector3.new(0, 7, 0), Enum.Material.Wood, Color3.fromRGB(105, 70, 42))
				add("Leaves", Vector3.new(14, 12, 14), Vector3.new(0, 17, 0), Enum.Material.Grass, Color3.fromRGB(48, 117, 61), Enum.PartType.Ball)
				add("UpperLeaves", Vector3.new(9, 9, 9), Vector3.new(0, 24, 0), Enum.Material.Grass, Color3.fromRGB(57, 137, 68), Enum.PartType.Ball)
			elseif taskData.asset_type == "rocha" then
				add("Rock", Vector3.new(12, 8, 10), Vector3.new(0, 4, 0), Enum.Material.Rock, Color3.fromRGB(104, 106, 108), Enum.PartType.Ball)
			elseif taskData.asset_type == "cristal" then
				add("Crystal", Vector3.new(5, 16, 5), Vector3.new(0, 8, 0), Enum.Material.Neon, Color3.fromRGB(70, 202, 220), "Wedge")
				add("Shard", Vector3.new(3, 10, 3), Vector3.new(5, 5, 2), Enum.Material.Neon, Color3.fromRGB(113, 231, 240), "Wedge")
			elseif taskData.asset_type == "acampamento" then
				add("LogA", Vector3.new(12, 2, 2), Vector3.new(0, 1, 0), Enum.Material.Wood, Color3.fromRGB(106, 71, 44))
				add("LogB", Vector3.new(2, 2, 12), Vector3.new(0, 1, 0), Enum.Material.Wood, Color3.fromRGB(106, 71, 44))
				add("Ember", Vector3.new(4, 5, 4), Vector3.new(0, 4, 0), Enum.Material.Neon, Color3.fromRGB(255, 116, 35))
			elseif taskData.asset_type == "bau" then
				add("ChestBase", Vector3.new(8, 5, 6), Vector3.new(0, 3, 0), Enum.Material.WoodPlanks, Color3.fromRGB(118, 75, 40))
				add("ChestLid", Vector3.new(8, 2, 6), Vector3.new(0, 6.5, 0), Enum.Material.Metal, Color3.fromRGB(195, 154, 61))
			elseif taskData.asset_type == "ponte" then
				for segment = -2, 2 do
					add(
						"Deck_" .. segment,
						Vector3.new(8, 1, 10),
						Vector3.new(segment * 8, 2, 0),
						Enum.Material.WoodPlanks,
						Color3.fromRGB(127, 88, 52)
					)
				end
			end

			model.PrimaryPart = primary
			model.Parent = staged
			table.insert(generated, model.Name)
		end
	end)
	if not ok then
		staged:Destroy()
		error("Falha ao criar assets; nenhum modelo foi aplicado. " .. tostring(creationError))
	end
	local committed = {}
	local commitOk, commitError = pcall(function()
		for _, model in ipairs(staged:GetChildren()) do
			model.Parent = folder
			table.insert(committed, model)
		end
	end)
	if not commitOk then
		for _, model in ipairs(committed) do
			model:Destroy()
		end
		staged:Destroy()
		error("Falha ao aplicar assets; modelos parciais removidos. " .. tostring(commitError))
	end
	staged:Destroy()
	return { asset_type = taskData.asset_type, quantity = #generated, names = generated }
end

local function executeTask(taskData)
	if taskData.tipo == "ping" then
		log("PONG!")
		return { mensagem = "PONG" }
	elseif taskData.tipo == "pedir_visao" then
		if not sendState(false) then
			error("Não foi possível enviar o estado ao Kael.")
		end
		return { estado_enviado = true }
	elseif taskData.tipo == "pedir_screenshot" then
		error("Captura de screenshot ainda não é suportada pelo plugin.")
	elseif taskData.tipo == "enviar_todos_scripts" then
		local includeContent = taskData.incluir_conteudo == true
		if not sendState(includeContent) then
			error("Não foi possível enviar os scripts ao Kael.")
		end
		return { scripts_enviados = true, conteudo_incluido = includeContent }
	elseif taskData.tipo == "limpar_flutuantes" then
		return cleanFloatingParts(taskData)
	elseif taskData.tipo == "limpar_construcoes_kael" then
		return cleanKaelBuild()
	elseif taskData.tipo == "gerar_terreno" then
		return generateTerrain(taskData)
	elseif taskData.tipo == "criar_assets" then
		return createAssets(taskData)
	elseif taskData.tipo == "restaurar_terreno" then
		return restoreTerrain(taskData)
	elseif taskData.tipo == "backup_assets_kael" then
		return backupGeneratedAssets(taskData)
	elseif taskData.tipo == "restaurar_assets_kael" then
		return restoreGeneratedAssets(taskData)
	elseif taskData.tipo == "criar_script" then
		error("Criação de scripts bloqueada: não há runner de testes Luau disponível.")
	end
	error("Tipo de tarefa não suportado.")
end

local function processTask(taskData)
	local success, result = pcall(executeTask, taskData)
	local completion = {
		task_id = taskData.task_id,
		tipo = taskData.tipo,
		sucesso = success,
		resultado = success and result or {},
		erro = success and "" or tostring(result),
	}
	local posted, postError = postJson("/tarefa_concluida", completion)
	if not posted then
		log("Falha ao confirmar tarefa " .. taskData.task_id .. ": " .. postError)
		return
	end
	if success then
		log("Tarefa concluída: " .. taskData.tipo .. " (" .. taskData.task_id .. ")")
	else
		log("Tarefa falhou: " .. tostring(result))
	end
end

local toolbar = plugin:CreateToolbar("Kael")
local mapButton = toolbar:CreateButton("KaelMap", "Enviar mapa da cena", "")
local pingButton = toolbar:CreateButton("KaelPing", "Testar conexão com Kael", "")
local pollingButton = toolbar:CreateButton("KaelPolling", "Iniciar/parar tarefas do Kael", "")

mapButton.Click:Connect(function()
	sendState(false)
end)

pingButton.Click:Connect(function()
	local response, err = getJson("/studio_status")
	if err then
		log("Falha de conexão: " .. err)
	else
		log("Conexão com Kael ativa (protocolo " .. tostring(response.protocol_version) .. ").")
	end
end)

pollingButton.Click:Connect(function()
	polling = not polling
	log(polling and "Polling iniciado." or "Polling pausado.")
	if polling then
		task.spawn(function()
			while polling do
				if not busy then
					busy = true
					local url = "/proxima_tarefa?protocol_version=1&client_id="
						.. HttpService:UrlEncode(clientId)
					local response, err = getJson(url)
					if err then
						log("Falha de polling: " .. err)
						postJson("/reportar_erro", {
							origem = "polling",
							erro = string.sub(err, 1, 2000),
						})
					elseif response.status == "ok" and response.tarefa then
						processTask(response.tarefa)
					elseif response.status == "incompatible" then
						log("A versão do protocolo do Kael não é compatível.")
					end
					if os.clock() - lastStateSent >= 15 then
						sendState(false)
					end
					busy = false
				end
				task.wait(2)
			end
		end)
	end
end)

log("Plugin carregado. Use o botão de polling para conectar ao Kael.")