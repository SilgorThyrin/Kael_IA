# -*- coding: utf-8 -*-
"""kael_loader.py - Carregador dinâmico de módulos do Kael"""
import os
import json
import importlib
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODULOS_CARREGADOS = {}
ERROS_CARREGAMENTO = {}

def carregar_registro():
    path = os.path.join(BASE_DIR, "kael_modules.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[LOADER] ERRO ao ler kael_modules.json: {e}")
        return None

def carregar_modulo(nome_modulo, info_modulo):
    arquivo = info_modulo.get("arquivo", "").replace(".py", "")
    descricao = info_modulo.get("descricao", "")
    obrigatorio = info_modulo.get("obrigatorio", False)
    funcoes_esperadas = info_modulo.get("funcoes_exportadas", [])
    
    try:
        modulo = importlib.import_module(arquivo)
        
        # Valida se as funções esperadas existem
        funcoes_faltando = [f for f in funcoes_esperadas if not hasattr(modulo, f)]
        if funcoes_faltando:
            msg = f"Módulo '{nome_modulo}' carregado, mas faltam funções: {funcoes_faltando}"
            print(f"[LOADER] AVISO: {msg}")
            if obrigatorio:
                ERROS_CARREGAMENTO[nome_modulo] = msg
                return None
        
        MODULOS_CARREGADOS[nome_modulo] = modulo
        print(f"[LOADER] ✓ {nome_modulo} ({arquivo}.py) - {descricao}")
        return modulo
        
    except ImportError as e:
        msg = f"Não foi possível importar '{arquivo}': {e}"
        print(f"[LOADER] ERRO: {msg}")
        ERROS_CARREGAMENTO[nome_modulo] = msg
        if obrigatorio:
            raise ImportError(f"Módulo obrigatório '{nome_modulo}' falhou: {e}")
        return None
    except Exception as e:
        msg = f"Erro inesperado ao carregar '{nome_modulo}': {e}"
        print(f"[LOADER] ERRO: {msg}")
        ERROS_CARREGAMENTO[nome_modulo] = msg
        if obrigatorio:
            raise
        return None

def carregar_todos():
    registro = carregar_registro()
    if not registro:
        return False
    
    print("\n" + "=" * 60)
    print("[LOADER] Carregando módulos do Kael...")
    print("=" * 60)
    
    modulos = registro.get("modulos", {})
    # Carrega obrigatórios primeiro
    for nome, info in modulos.items():
        if info.get("obrigatorio", False):
            carregar_modulo(nome, info)
    # Carrega opcionais
    for nome, info in modulos.items():
        if not info.get("obrigatorio", False) and nome not in MODULOS_CARREGADOS:
            carregar_modulo(nome, info)
            
    print("=" * 60)
    print(f"[LOADER] {len(MODULOS_CARREGADOS)} módulos carregados com sucesso.")
    if ERROS_CARREGAMENTO:
        print(f"[LOADER] {len(ERROS_CARREGAMENTO)} módulos com erro (verifique o log).")
    print("=" * 60 + "\n")
    return True

def obter_modulo(nome):
    return MODULOS_CARREGADOS.get(nome)

def modulo_disponivel(nome):
    return nome in MODULOS_CARREGADOS