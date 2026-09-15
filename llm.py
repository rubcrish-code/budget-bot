"""
Модуль для работы с LLM через Bridge API
"""
import json
import requests
from typing import Optional
import config


class BridgeLLM:
    """Клиент для работы с LLM через Bridge API"""

    def __init__(self):
        self.api_url = config.BRIDGE_API_URL
        self.api_key = config.BRIDGE_API_KEY
        self.model = config.BRIDGE_MODEL

    def _create_headers(self) -> dict:
        """Создать заголовки для API запроса"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        return headers

    def chat(self, messages: list, temperature: float = 0.7) -> Optional[str]:
        """
        Отправить запрос к LLM и получить ответ

        Args:
            messages: список сообщений в формате OpenAI
                [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            temperature: температура генерации (0.0 - 1.0)

        Returns:
            Ответ модели или None при ошибке
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }

        try:
            response = requests.post(
                self.api_url,
                headers=self._create_headers(),
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # Стандартный формат ответа (как у OpenAI)
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content.strip() if content else None

        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к LLM: {e}")
            return None
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"Ошибка при парсинге ответа LLM: {e}")
            return None

    def parse_transaction(self, text: str) -> dict:
        """
        Разобрать текст о транзакции и извлечь структурированные данные

        Returns:
            Словарь с ключами: type, amount, category, description, date
            type: "income" (доход) или "expense" (расход)
        """
        system_prompt = """Ты — ассистент для учёта финансов. 
Твоя задача — проанализировать текст пользователя и определить:
1. Тип транзакции (type) — "income" если это доход, "expense" если это расход
2. Сумму (amount) — число
3. Категорию (category):
   - Для расходов: еда, транспорт, развлечения, жилье, здоровье, образование, одежда, другие
   - Для доходов: зарплата, фриланс, подарок, продажа, возврат, другие
4. Описание (description) — краткое описание
5. Дату (date) — если указана в тексте, иначе null

Примеры доходов: "зарплата 50000", "получил от друга 1000", "продал старый телефон 8000"
Примеры расходов: "обед 500", "такси 300", "продукты 2000"

Всегда отвечай ТОЛЬКО валидным JSON в формате:
{"type": "income или expense", "amount": число, "category": "категория", "description": "описание", "date": "дата или null"}

Не добавляй ничего кроме JSON."""

        user_prompt = f"Транзакция: {text}"

        response = self.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], temperature=0.1)

        if response:
            try:
                # Извлечь JSON из ответа (может быть в markdown блоке)
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    response = response.split("```")[1].split("```")[0].strip()

                return json.loads(response)
            except json.JSONDecodeError as e:
                print(f"Ошибка парсинга JSON от LLM: {e}")
                print(f"Ответ LLM: {response}")

        # Fallback — вернуть пустой словарь
        return {"type": "expense", "amount": None, "category": None, "description": text, "date": None}

    def parse_expense(self, text: str) -> dict:
        """
        Разобрать текст о транзакции (обёртка для обратной совместимости)
        """
        result = self.parse_transaction(text)
        # Убрать type для обратной совместимости
        result.pop("type", None)
        return result

    def generate_summary(self, expenses: list, incomes: list = None, period: str = "за всё время") -> str:
        """
        Сгенерировать сводку финансов (доходы + расходы)

        Args:
            expenses: список расходов (список словарей)
            incomes: список доходов (список словарей)
            period: описание периода

        Returns:
            Текстовая сводка
        """
        if not expenses and not incomes:
            return f"За {period} записей не найдено."

        expenses_text = json.dumps(expenses, ensure_ascii=False, indent=2)
        incomes_text = json.dumps(incomes or [], ensure_ascii=False, indent=2)

        system_prompt = """Ты — финансовый ассистент. 
Твоя задача — создать красивую и информативную финансовую сводку.
Используй эмодзи, форматирование и делай ответ удобным для чтения в Telegram.
Не используй Markdown (жирный/курсив через символы), используй только эмодзи и текст.
НЕ указывай период/даты в заголовке — они будут добавлены автоматически."""

        user_prompt = f"""Создай финансовую сводку {period}:

Доходы:
{incomes_text}

Расходы:
{expenses_text}

Включи:
- Доходы: общую сумму, категории
- Расходы: общую сумму, категории
- Баланс (доходы минус расходы)
- Топ-3 крупные траты
- Краткий комментарий по финансам"""

        response = self.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], temperature=0.7)

        return response or "Не удалось сгенерировать сводку."

    def answer_question(self, question: str, expenses: list) -> str:
        """
        Ответить на вопрос пользователя о расходах

        Args:
            question: вопрос пользователя
            expenses: список расходов для контекста

        Returns:
            Ответ на вопрос
        """
        expenses_text = json.dumps(expenses, ensure_ascii=False, indent=2)

        system_prompt = """Ты — финансовый ассистент. 
У тебя есть данные о расходах пользователя. Ответь на его вопрос на основе этих данных.
Будь кратким, полезным и используй эмодзи."""

        user_prompt = f"""Мои расходы:
{expenses_text}

Вопрос: {question}"""

        response = self.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], temperature=0.7)

        return response or "Не удалось получить ответ."


# Глобальный экземпляр
llm_client = BridgeLLM()
