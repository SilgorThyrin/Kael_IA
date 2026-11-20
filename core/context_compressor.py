"""
Compressor de Contexto Nativo do Kael
Estratégia: Truncamento inteligente + priorização de memórias
Não depende de bibliotecas externas.
"""

class ContextCompressor:
    def __init__(self, max_chars: int = 12000):
        """
        max_chars: limite aproximado de caracteres (~3000 tokens, já que 1 token ≈ 4 chars)
        """
        self.max_chars = max_chars
    
    def estimate_tokens(self, text: str) -> int:
        """Estima quantidade de tokens (1 token ≈ 4 caracteres em português/inglês)"""
        return len(text) // 4
    
    def truncate_history(self, history: list, max_messages: int = 5) -> list:
        """Mantém apenas as últimas N mensagens do histórico"""
        return history[-max_messages:] if len(history) > max_messages else history
    
    def truncate_memories(self, memories: list, max_memories: int = 3) -> list:
        """Mantém apenas as top N memórias mais relevantes"""
        return memories[:max_memories] if len(memories) > max_memories else memories
    
    def build_context(self, user_message: str, history: list, memories: list, 
                     system_prompt: str = "") -> str:
        """
        Constrói o contexto final respeitando o limite de caracteres.
        Prioridade: System Prompt > Memórias > Histórico > Mensagem Atual
        """
        parts = []
        
        # 1. System Prompt (sempre incluído)
        if system_prompt:
            parts.append(f"=== SISTEMA ===\n{system_prompt}")
        
        # 2. Memórias relevantes
        if memories:
            mem_text = "\n".join([
                f"[{m.get('category', 'geral')}] {m['content']}" 
                for m in memories
            ])
            parts.append(f"=== MEMÓRIAS RELEVANTES ===\n{mem_text}")
        
        # 3. Histórico recente
        if history:
            hist_lines = []
            for msg in history:
                role = "Usuário" if msg.get('role') == 'user' else "Kael"
                hist_lines.append(f"{role}: {msg.get('content', '')}")
            parts.append(f"=== HISTÓRICO RECENTE ===\n" + "\n".join(hist_lines))
        
        # 4. Mensagem atual (sempre incluída)
        parts.append(f"=== MENSAGEM ATUAL ===\nUsuário: {user_message}")
        
        full_context = "\n\n".join(parts)
        
        # 5. Truncamento final se exceder o limite
        if len(full_context) > self.max_chars:
            print(f"[COMPRESSOR] Contexto excede limite ({len(full_context)} chars). Truncando...")
            # Mantém system prompt + mensagem atual intactos, trunca o meio
            header = parts[0] if parts else ""
            footer = parts[-1] if parts else ""
            middle = "\n\n".join(parts[1:-1])
            
            available = self.max_chars - len(header) - len(footer) - 20
            if available > 0:
                middle = middle[:available] + "\n...[contexto truncado para economizar VRAM]..."
            full_context = f"{header}\n\n{middle}\n\n{footer}"
        
        tokens_estimados = self.estimate_tokens(full_context)
        print(f"[COMPRESSOR] Contexto final: ~{tokens_estimados} tokens ({len(full_context)} chars)")
        
        return full_context
    
    def compress(self, text: str) -> str:
        """Compressão simples por truncamento (fallback)"""
        if len(text) <= self.max_chars:
            return text
        return text[:self.max_chars] + "\n...[truncado]..."


# Teste rápido
if __name__ == "__main__":
    compressor = ContextCompressor(max_chars=12000)
    
    historico = [
        {"role": "user", "content": "Olá"},
        {"role": "assistant", "content": "Oi! Como posso ajudar?"},
    ]
    memorias = [
        {"category": "cronograma", "content": "Cronograma de 3 dias para Ecos de Aethelgard"},
    ]
    
    contexto = compressor.build_context(
        user_message="Crie um novo cronograma",
        history=historico,
        memories=memorias,
        system_prompt="Você é o Kael, agente de desenvolvimento de jogos."
    )
    
    print("\n=== CONTEXTO GERADO ===")
    print(contexto)
    print(f"\nTokens estimados: {compressor.estimate_tokens(contexto)}")