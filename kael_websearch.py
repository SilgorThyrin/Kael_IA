# -*- coding: utf-8 -*-
import time
from ddgs import DDGS

def pesquisar_web(termo: str, max_resultados: int = 4) -> str:
    """
    Pesquisa no DuckDuckGo com retry. Se falhar de verdade, retorna uma string
    começando com 'ERRO_WEB:' para o Kael saber que NÃO deve inventar.
    """
    tentativas = 2
    for tentativa in range(tentativas):
        try:
            # Aumentamos o timeout para 15s
            with DDGS(timeout=15) as ddgs:
                resultados = list(ddgs.text(termo, max_results=max_resultados))
            
            if not resultados:
                return "Nenhum resultado encontrado na web para: " + termo

            linhas = [f"Resultados reais da web para: '{termo}'\n"]
            for i, r in enumerate(resultados, 1):
                titulo = r.get("title", "Sem titulo")
                link = r.get("href", "")
                corpo = r.get("body", "")
                linhas.append(f"[{i}] {titulo}")
                linhas.append(f"URL: {link}")
                linhas.append(f"Resumo: {corpo}\n")
                
            return "\n".join(linhas)
        except Exception as e:
            if tentativa == tentativas - 1:
                return f"ERRO_WEB: A busca falhou apos {tentativas} tentativas. Detalhe: {e}"
            time.sleep(2)