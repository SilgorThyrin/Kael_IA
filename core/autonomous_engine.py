"""
============================================================
KAEL AUTONOMOUS ENGINE - Loop de trabalho independente
============================================================
Loop: Planejar → Executar → Observar → Refletir
Integra com: Game Bridge, Memória Vetorial, Floating Detector
============================================================
"""
import json
import sqlite3
import threading
import time
from pathlib import Path
from datetime import datetime


class AutonomousEngine:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db_path = ctx.memory_dir / "autonomous_tasks.db"
        self._init_db()
        self.running = False
        self.current_task = None
        self.thread = None

    def _init_db(self):
        """Cria tabela de tarefas autônomas."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                result TEXT,
                error TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS subtasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                description TEXT,
                status TEXT DEFAULT 'pending',
                result TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        ''')
        conn.commit()
        conn.close()

    def start_task(self, description):
        """Inicia uma tarefa autônoma em thread separada."""
        if self.running:
            return {"error": "Já existe uma tarefa rodando. Use /parar_tarefa primeiro."}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (description, status) VALUES (?, 'running')",
            (description,)
        )
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.running = True
        self.current_task = task_id
        self.thread = threading.Thread(target=self._run_loop, args=(task_id, description), daemon=True)
        self.thread.start()

        return {
            "task_id": task_id,
            "message": f"🤖 Tarefa #{task_id} iniciada: '{description[:50]}...'"
        }

    def stop_task(self):
        """Para a tarefa atual."""
        if not self.running:
            return {"message": "Nenhuma tarefa rodando."}
        self.running = False
        if self.current_task:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "UPDATE tasks SET status='stopped', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (self.current_task,)
            )
            conn.commit()
            conn.close()
        return {"message": "⏹️ Tarefa parada pelo usuário."}

    def get_status(self):
        """Retorna status da tarefa atual."""
        if not self.current_task:
            return {"status": "idle"}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT description, status, result, error FROM tasks WHERE id=?",
            (self.current_task,)
        )
        row = cursor.fetchone()
        
        cursor.execute(
            "SELECT description, status, result FROM subtasks WHERE task_id=? ORDER BY id",
            (self.current_task,)
        )
        subtasks = cursor.fetchall()
        conn.close()

        if not row:
            return {"status": "not_found"}

        return {
            "task_id": self.current_task,
            "description": row[0],
            "status": row[1],
            "result": row[2],
            "error": row[3],
            "subtasks": [
                {"description": s[0], "status": s[1], "result": s[2]}
                for s in subtasks
            ]
        }

    def _run_loop(self, task_id, description):
        """Loop principal: Planejar → Executar → Observar → Refletir."""
        try:
            # FASE 1: Planejar (IA decompõe a tarefa)
            plan = self._plan_task(description)
            if not plan:
                self._finish_task(task_id, status="failed", error="Falha no planejamento")
                return

            # FASE 2: Executar cada subtarefa
            for i, subtask in enumerate(plan, 1):
                if not self.running:
                    break

                print(f"[AUTONOMO] Executando subtarefa {i}/{len(plan)}: {subtask}")
                result = self._execute_subtask(task_id, subtask)
                
                # FASE 3: Observar resultado
                observation = self._observe_result(result)
                print(f"[AUTONOMO] Observação: {observation}")

                # FASE 4: Refletir (aprende com erros)
                if "erro" in observation.lower() or "falha" in observation.lower():
                    lesson = self._reflect_on_error(subtask, result)
                    if lesson and self.ctx.memory:
                        self.ctx.memory.add_memory(lesson, "autonomous_lesson")
                    print(f"[AUTONOMO] Lição aprendida: {lesson}")

                # Pausa entre subtarefas (evita sobrecarregar GPU)
                time.sleep(2)

            # Concluiu todas as subtarefas
            final_result = self._summarize_task(task_id)
            self._finish_task(task_id, status="completed", result=final_result)

        except Exception as e:
            print(f"[AUTONOMO] Erro no loop: {e}")
            self._finish_task(task_id, status="failed", error=str(e))

    def _plan_task(self, description):
        """Usa a IA para decompor a tarefa em subtarefas."""
        prompt = (
            f"Você é o Kael em MODO AUTÔNOMO. Sua tarefa: '{description}'.\n"
            f"Projeto atual: {self.ctx.project_path.name}\n\n"
            "Decomponha esta tarefa em 3-5 subtarefas concretas e executáveis. "
            "Cada subtarefa deve ser uma ação específica (criar arquivo, testar script, corrigir bug).\n\n"
            "Responda APENAS com um JSON array de strings, sem markdown:\n"
            '[\"Subtarefa 1\", \"Subtarefa 2\", \"Subtarefa 3\"]'
        )
        resultado = self.ctx.generate(prompt)
        response = resultado['response'].strip()

        # Tenta parsear como JSON
        try:
            if response.startswith('```json'):
                response = response.replace('```json', '').replace('```', '').strip()
            plan = json.loads(response)
            if isinstance(plan, list):
                return plan
        except json.JSONDecodeError:
            print(f"[AUTONOMO] Falha ao parsear plano: {response[:200]}")
            return None

        return None

    def _execute_subtask(self, task_id, subtask):
        """Executa uma subtarefa usando as tools disponíveis."""
        # Salva no banco
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO subtasks (task_id, description, status) VALUES (?, ?, 'running')",
            (task_id, subtask)
        )
        subtask_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Roteia para a tool apropriada
        result = None
        if "criar" in subtask.lower() or "gerar" in subtask.lower():
            # Usa Game Bridge para criar estrutura
            prompt = f"{subtask}\nUse <kael_save filename='...'> para salvar o código."
            res = self.ctx.generate(prompt)
            result = self.ctx.process_save_commands(res['response'], save_dir=self.ctx.project_path)
        
        elif "testar" in subtask.lower() or "verificar" in subtask.lower():
            # Usa Floating Detector ou Game Bridge
            from tools.game_bridge import GameBridge
            bridge = GameBridge(str(self.ctx.project_path))
            report = bridge.full_report()
            result = json.dumps(report, indent=2, ensure_ascii=False)

        elif "corrigir" in subtask.lower() or "fixar" in subtask.lower():
            # Usa IA para corrigir scripts
            prompt = f"{subtask}\nAnalise os scripts e corrija problemas. Salve com <kael_save>."
            res = self.ctx.generate(prompt)
            result = self.ctx.process_save_commands(res['response'], save_dir=self.ctx.project_path)

        else:
            # Tarefa genérica: usa IA
            prompt = f"Execute esta subtarefa: {subtask}\nContexto: {self.ctx.project_path.name}"
            res = self.ctx.generate(prompt)
            result = res['response']

        # Atualiza status no banco
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE subtasks SET status='completed', result=? WHERE id=?",
            (result[:500], subtask_id)  # Trunca resultado
        )
        conn.commit()
        conn.close()

        return result

    def _observe_result(self, result):
        """Analisa o resultado de uma subtarefa."""
        if not result:
            return "Sem resultado."
        
        result_lower = result.lower()
        if "erro" in result_lower or "falha" in result_lower:
            return "Erro detectado no resultado."
        if "sucesso" in result_lower or "concluído" in result_lower:
            return "Subtarefa concluída com sucesso."
        return "Resultado processado."

    def _reflect_on_error(self, subtask, result):
        """Gera uma lição aprendida com o erro."""
        prompt = (
            f"Subtarefa falhou: '{subtask}'\nResultado: {result[:200]}\n\n"
            "Em 1 frase, qual lição aprender para não repetir este erro?"
        )
        res = self.ctx.generate(prompt)
        return res['response'].strip()[:200]

    def _summarize_task(self, task_id):
        """Gera resumo final da tarefa."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT description, status FROM subtasks WHERE task_id=?",
            (task_id,)
        )
        subtasks = cursor.fetchall()
        conn.close()

        completed = sum(1 for s in subtasks if s[1] == 'completed')
        total = len(subtasks)
        return f"Tarefa concluída: {completed}/{total} subtarefas executadas."

    def _finish_task(self, task_id, status, result=None, error=None):
        """Finaliza a tarefa no banco."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE tasks SET status=?, result=?, error=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, result, error, task_id)
        )
        conn.commit()
        conn.close()
        self.running = False
        self.current_task = None
        print(f"[AUTONOMO] Tarefa #{task_id} finalizada: {status}")