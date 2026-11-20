import sqlite3
import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

class KaelMemory:
    def __init__(self, db_path: str = "kael_memory.db"):
        self.db_path = Path(__file__).parent.parent / db_path
        self.model = SentenceTransformer('all-MiniLM-L6-v2')  # Modelo leve de embedding
        self._init_db()
    
    def _init_db(self):
        """Inicializa o banco de dados com tabela de memórias"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela para memórias (texto + embedding)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                embedding BLOB NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Índice para busca rápida por categoria
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON memories(category)')
        
        conn.commit()
        conn.close()
    
    def _get_embedding(self, text: str) -> bytes:
        """Converte texto em vetor de embedding"""
        embedding = self.model.encode(text)
        return embedding.tobytes()
    
    def add_memory(self, content: str, category: str):
        """Adiciona uma nova memória ao banco"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        embedding = self._get_embedding(content)
        
        cursor.execute(
            'INSERT INTO memories (content, category, embedding) VALUES (?, ?, ?)',
            (content, category, embedding)
        )
        
        conn.commit()
        conn.close()
        print(f"[MEMÓRIA] Adicionada: {category} - {content[:50]}...")
    
    def search_similar(self, query: str, category: str = None, limit: int = 3) -> list:
        """Busca memórias semanticamente similares"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query_embedding = self._get_embedding(query)
        query_array = np.frombuffer(query_embedding, dtype=np.float32)
        
        # Busca todas as memórias da categoria (ou todas se não especificada)
        if category:
            cursor.execute('SELECT id, content, category, embedding FROM memories WHERE category = ?', (category,))
        else:
            cursor.execute('SELECT id, content, category, embedding FROM memories')
        
        memories = cursor.fetchall()
        conn.close()
        
        # Calcula similaridade com cada memória
        results = []
        for mem_id, content, cat, emb_bytes in memories:
            mem_array = np.frombuffer(emb_bytes, dtype=np.float32)
            # Similaridade cosseno
            similarity = np.dot(query_array, mem_array) / (
                np.linalg.norm(query_array) * np.linalg.norm(mem_array)
            )
            results.append({
                'id': mem_id,
                'content': content,
                'category': cat,
                'similarity': float(similarity)
            })
        
        # Ordena por similaridade (maior primeiro) e retorna top N
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:limit]
    
    def get_all_memories(self, category: str = None) -> list:
        """Retorna todas as memórias (opcionalmente filtradas por categoria)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if category:
            cursor.execute('SELECT content, category FROM memories WHERE category = ?', (category,))
        else:
            cursor.execute('SELECT content, category FROM memories')
        
        memories = cursor.fetchall()
        conn.close()
        
        return [{'content': m[0], 'category': m[1]} for m in memories]

# Teste rápido
if __name__ == "__main__":
    memory = KaelMemory()
    memory.add_memory("Cronograma de 3 dias para Ecos de Aethelgard", "cronograma")
    memory.add_memory("Sistema de combate baseado em turnos", "mecanica")
    
    results = memory.search_similar("planejamento do jogo", limit=2)
    print("\n🔍 Busca por 'planejamento do jogo':")
    for r in results:
        print(f"  [{r['similarity']:.2f}] {r['content']}")