"""
База данных для хранения расходов
"""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
import config


class ExpenseDatabase:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Создать таблицы если они не существуют"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                raw_text TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT,
                description TEXT,
                date TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                raw_text TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT,
                description TEXT,
                date TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def add_expense(self, user_id: int, raw_text: str, amount: float,
                    category: str = None, description: str = None,
                    date: str = None) -> int:
        """Добавить расход в базу"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO expenses (user_id, raw_text, amount, category, description, date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, raw_text, amount, category, description, date, created_at))
        conn.commit()
        expense_id = cursor.lastrowid
        conn.close()
        return expense_id

    def get_expenses(self, user_id: int, start_date: str = None,
                     end_date: str = None, limit: int = 50) -> List[Dict]:
        """Получить расходы пользователя за период"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM expenses WHERE user_id = ?"
        params = [user_id]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        conn.close()
        return result

    def get_total_expenses(self, user_id: int, start_date: str = None,
                           end_date: str = None) -> float:
        """Получить общую сумму расходов за период"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE user_id = ?"
        params = [user_id]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        cursor.execute(query, params)
        total = cursor.fetchone()["total"]
        conn.close()
        return total

    def get_expenses_by_category(self, user_id: int, start_date: str = None,
                                 end_date: str = None) -> Dict[str, float]:
        """Получить расходы по категориям"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
            SELECT category, COALESCE(SUM(amount), 0) as total, COUNT(*) as count
            FROM expenses WHERE user_id = ?
        """
        params = [user_id]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " GROUP BY category ORDER BY total DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        result = {row["category"] or "Без категории": row["total"] for row in rows}
        conn.close()
        return result

    def get_all_expenses_for_llm(self, user_id: int, start_date: str = None,
                                  end_date: str = None) -> List[Dict]:
        """Получить все расходы для передачи в LLM"""
        return self.get_expenses(user_id, start_date, end_date, limit=1000)

    def delete_expenses_by_period(self, user_id: int, start_date: str,
                                   end_date: str) -> int:
        """Удалить расходы за период, вернуть количество удалённых"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM expenses WHERE user_id = ? AND date >= ? AND date <= ?
        """, (user_id, start_date, end_date))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def delete_all_expenses(self, user_id: int) -> int:
        """Удалить все расходы пользователя, вернуть количество удалённых"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM expenses WHERE user_id = ?
        """, (user_id,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def save_llm_response(self, user_id: int, query: str, response: str):
        """Сохранить ответ LLM (для истории)"""
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO llm_responses (user_id, query, response, created_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, query, response, created_at))
        conn.commit()
        conn.close()

    # ==================== Методы для доходов ====================

    def add_income(self, user_id: int, raw_text: str, amount: float,
                   category: str = None, description: str = None,
                   date: str = None) -> int:
        """Добавить доход в базу"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO incomes (user_id, raw_text, amount, category, description, date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, raw_text, amount, category, description, date, created_at))
        conn.commit()
        income_id = cursor.lastrowid
        conn.close()
        return income_id

    def get_incomes(self, user_id: int, start_date: str = None,
                    end_date: str = None, limit: int = 50) -> List[Dict]:
        """Получить доходы пользователя за период"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM incomes WHERE user_id = ?"
        params = [user_id]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        conn.close()
        return result

    def get_total_incomes(self, user_id: int, start_date: str = None,
                          end_date: str = None) -> float:
        """Получить общую сумму доходов за период"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT COALESCE(SUM(amount), 0) as total FROM incomes WHERE user_id = ?"
        params = [user_id]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        cursor.execute(query, params)
        total = cursor.fetchone()["total"]
        conn.close()
        return total

    def get_all_incomes_for_llm(self, user_id: int, start_date: str = None,
                                 end_date: str = None) -> List[Dict]:
        """Получить все доходы для передачи в LLM"""
        return self.get_incomes(user_id, start_date, end_date, limit=1000)

    def delete_incomes_by_period(self, user_id: int, start_date: str,
                                  end_date: str) -> int:
        """Удалить доходы за период, вернуть количество удалённых"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM incomes WHERE user_id = ? AND date >= ? AND date <= ?
        """, (user_id, start_date, end_date))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def delete_all_incomes(self, user_id: int) -> int:
        """Удалить все доходы пользователя, вернуть количество удалённых"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM incomes WHERE user_id = ?
        """, (user_id,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def delete_all_user_data(self, user_id: int) -> dict:
        """Удалить ВСЕ данные пользователя (доходы, расходы, история LLM)
        
        Returns:
            Словарь с количеством удалённых записей по каждой таблице
        """
        expenses_deleted = self.delete_all_expenses(user_id)
        incomes_deleted = self.delete_all_incomes(user_id)
        
        # Удалить историю LLM
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM llm_responses WHERE user_id = ?
        """, (user_id,))
        llm_deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        return {
            "expenses": expenses_deleted,
            "incomes": incomes_deleted,
            "llm_responses": llm_deleted
        }
