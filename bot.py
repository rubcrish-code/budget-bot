"""
Telegram бот для учёта расходов
"""
import logging
import json
import re
import html
from datetime import datetime, timedelta
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    ContextTypes, filters, CallbackQueryHandler
)
import config
from database import ExpenseDatabase
from llm import llm_client
from periods import get_previous_week_range, get_previous_month_range, format_period

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = ExpenseDatabase()

# Пользователи в режиме чата
chat_mode_users = set()


def clean_llm_text(text: str) -> str:
    """Очистить ответ LLM от Markdown и HTML разметки"""
    if not text:
        return ""
    
    # Сначала декодировать HTML сущности (если LLM вернул &lt;b&gt; вместо <b>)
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    text = text.replace('&quot;', '"').replace('&apos;', "'").replace('&#39;', "'")
    
    # Удалить HTML теги (<b>, </b>, <i>, <code>, <u> и т.д.)
    text = re.sub(r'<[^>]*>', '', text)
    
    # Удалить Markdown: **жирный**, __жирный__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    
    # Удалить Markdown: *курсив*, _курсив_
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)
    
    # Удалить `код` и ```код``` 
    text = re.sub(r'```(.+?)```', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'`(.+?)`', r'\1', text)
    
    # Удалить Markdown ссылки [текст](url)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # Удалить оставшиеся HTML сущности (&nbsp;, &mdash; и т.д.)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)
    
    # Удалить лишние пробелы и пустые строки
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def escape_html(text: str) -> str:
    """Экранировать HTML спецсимволы в пользовательском тексте"""
    return html.escape(text or '')


def back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка «Назад» к главному меню"""
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню с кнопками"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Сводка за неделю", callback_data="summary_week"),
            InlineKeyboardButton("📈 Сводка за месяц", callback_data="summary_month")
        ],
        [
            InlineKeyboardButton("💰 Все расходы", callback_data="all_expenses"),
            InlineKeyboardButton("💬 Чат", callback_data="chat_mode")
        ],
        [
            InlineKeyboardButton("❓ Помощь", callback_data="help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user_id = update.effective_user.id

    welcome_text = (
        "👋 Привет! Я твой финансовый ассистент!\n\n"
        "📝 Просто напиши мне о доходе или расходе в свободной форме:\n\n"
        "💰 <b>Расходы:</b>\n"
        "• Обед в кафе 450 рублей\n"
        "• Такси домой 350\n"
        "• Кино с друзьями 1200\n\n"
        "💵 <b>Доходы:</b>\n"
        "• Зарплата 50000\n"
        "• Получил от друга 1000\n"
        "• Фриланс проект 25000\n\n"
        "Я автоматически определю тип, сумму и категорию.\n\n"
        "📊 Доступные команды:"
    )
    
    reply_markup = main_menu_keyboard()

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = (
        "📖 <b>Как пользоваться ботом</b>\n\n"
        "💬 <b>Записать транзакцию</b>\n"
        "Просто напиши сообщение в свободной форме:\n\n"
        "🔴 <b>Расходы:</b>\n"
        "• \"Кофе 200\"\n"
        "• \"Продукты в пятерочке 1500 рублей\"\n"
        "• \"Метро 80\"\n\n"
        "🟢 <b>Доходы:</b>\n"
        "• \"Зарплата 50000\"\n"
        "• \"Получил от друга 1000\"\n"
        "• \"Продажу старый телефон 8000\"\n\n"
        "📊 <b>Сводки</b>\n"
        "• /week — сводка за прошлую неделю\n"
        "• /month — сводка за прошлый месяц\n"
        "• /all — все расходы\n\n"
        "🗑️ <b>Очистка записей</b>\n"
        "• /clear_week — удалить записи за прошлую неделю\n"
        "• /clear_month — удалить записи за прошлый месяц\n"
        "• /clear_all — удалить ВСЕ записи (с подтверждением)\n\n"
        "�️ <b>Удаление аккаунта</b>\n"
        "• /delete_data — удалить все ваши данные и выйти из бота\n\n"
        "�💬 <b>Чат-режим</b>\n"
        "Нажми кнопку \"💬 Чат\" в главном меню для свободного общения\n\n"
        "❓ <b>Вопросы</b>\n"
        "Задай вопрос о финансах за любой период:\n"
        "• \"Сколько я потратил на еду в сентябре?\"\n"
        "• \"Какой был баланс в августе?\"\n"
        "• \"Какая самая большая трата?\""
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


async def week_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сводка за прошлую неделю"""
    user_id = update.effective_user.id
    start_date, end_date = get_previous_week_range()
    period_label = format_period(start_date, end_date)

    expenses = db.get_all_expenses_for_llm(
        user_id, 
        start_date,
        end_date
    )
    incomes = db.get_all_incomes_for_llm(
        user_id,
        start_date,
        end_date
    )

    summary = llm_client.generate_summary(expenses, incomes, period_label)
    if summary.startswith("За ") and "не найдено" in summary:
        await update.message.reply_text(summary)
    else:
        await update.message.reply_text(f"📊 {period_label}\n\n{clean_llm_text(summary)}")


async def month_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сводка за прошлый месяц"""
    user_id = update.effective_user.id
    start_date, end_date = get_previous_month_range()
    period_label = format_period(start_date, end_date)

    expenses = db.get_all_expenses_for_llm(
        user_id,
        start_date,
        end_date
    )
    incomes = db.get_all_incomes_for_llm(
        user_id,
        start_date,
        end_date
    )

    summary = llm_client.generate_summary(expenses, incomes, period_label)
    if summary.startswith("За ") and "не найдено" in summary:
        await update.message.reply_text(summary)
    else:
        await update.message.reply_text(f"📊 {period_label}\n\n{clean_llm_text(summary)}")


async def clear_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить расходы за прошлую неделю"""
    user_id = update.effective_user.id
    start_date, end_date = get_previous_week_range()

    period_label = format_period(start_date, end_date)

    # Проверка: есть ли расходы за период
    expenses = db.get_all_expenses_for_llm(
        user_id,
        start_date,
        end_date
    )

    if not expenses:
        await update.message.reply_text(
            f"📭 За {period_label} расходов не найдено.\nНечего очищать."
        )
        return

    total = sum(exp["amount"] for exp in expenses)
    count = len(expenses)

    # Подтверждение с кнопками
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data="confirm_clear_week"),
            InlineKeyboardButton("❌ Отмена", callback_data="help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🗑️ <b>Очистка расходов</b>\n\n"
        f"Период: {period_label}\n"
        f"Расходов: {count}\n"
        f"Сумма: {total:.0f} ₽\n\n"
        f"Вы уверены, что хотите удалить все расходы за этот период?",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def clear_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить расходы за прошлый месяц"""
    user_id = update.effective_user.id
    start_date, end_date = get_previous_month_range()

    period_label = format_period(start_date, end_date)

    # Проверка: есть ли расходы за период
    expenses = db.get_all_expenses_for_llm(
        user_id,
        start_date,
        end_date
    )

    if not expenses:
        await update.message.reply_text(
            f"📭 За {period_label} расходов не найдено.\nНечего очищать."
        )
        return

    total = sum(exp["amount"] for exp in expenses)
    count = len(expenses)

    # Подтверждение с кнопками
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить", callback_data="confirm_clear_month"),
            InlineKeyboardButton("❌ Отмена", callback_data="help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🗑️ <b>Очистка расходов</b>\n\n"
        f"Период: {period_label}\n"
        f"Расходов: {count}\n"
        f"Сумма: {total:.0f} ₽\n\n"
        f"Вы уверены, что хотите удалить все расходы за этот период?",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def clear_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить все доходы и расходы — с подтверждением"""
    user_id = update.effective_user.id

    # Проверка: есть ли записи
    expenses = db.get_all_expenses_for_llm(user_id)
    incomes = db.get_all_incomes_for_llm(user_id)

    if not expenses and not incomes:
        await update.message.reply_text(
            "📭 У вас пока нет записей.\nНечего удалять.",
            reply_markup=back_keyboard()
        )
        return

    expense_total = sum(exp["amount"] for exp in expenses)
    expense_count = len(expenses)
    income_total = sum(inc["amount"] for inc in (incomes or []))
    income_count = len(incomes or [])

    # Подтверждение с кнопками
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, удалить всё", callback_data="confirm_clear_all"),
            InlineKeyboardButton("❌ Отмена", callback_data="back")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"⚠️ <b>ВНИМАНИЕ: удаление ВСЕХ записей</b>\n\n"
        f"Доходов: {income_count} ({income_total:.0f} ₽)\n"
        f"Расходов: {expense_count} ({expense_total:.0f} ₽)\n\n"
        f"Это действие нельзя отменить!\n"
        f"Вы уверены, что хотите удалить все записи?",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def all_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все расходы"""
    user_id = update.effective_user.id
    expenses = db.get_expenses(user_id, limit=20)

    if not expenses:
        await update.message.reply_text("📭 У вас пока нет расходов.")
        return

    total = db.get_total_expenses(user_id)
    
    text = f"📋 <b>Последние расходы</b> (всего: {total:.0f} ₽)\n\n"
    
    for exp in expenses[:10]:
        date = exp["date"][:10]
        category = f' [{exp["category"]}]' if exp["category"] else ""
        text += f"🔹 {date}{category}\n"
        text += f"   {exp['amount']:.0f} ₽ — {escape_html(exp['description'] or exp['raw_text'])}\n\n"

    await update.message.reply_text(text, parse_mode="HTML")

async def delete_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить все данные пользователя"""
    user_id = update.effective_user.id

    # Подтверждение с кнопками
    keyboard = [
        [
            InlineKeyboardButton("🗑️ Да, удалить всё", callback_data="confirm_delete_data"),
            InlineKeyboardButton("❌ Отмена", callback_data="back")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "⚠️ <b>УДАЛЕНИЕ АККАУНТА</b>\n\n"
        "Это действие удалит:\n"
        "• Все ваши доходы\n"
        "• Все ваши расходы\n"
        "• Историю вопросов\n\n"
        "Это действие нельзя отменить!",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def delete_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить все данные пользователя"""
    user_id = update.effective_user.id
    
    # Подтверждение с кнопками
    keyboard = [
        [
            InlineKeyboardButton("🗑️ Да, удалить всё", callback_data="confirm_delete_data"),
            InlineKeyboardButton("❌ Отмена", callback_data="back")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "⚠️ <b>УДАЛЕНИЕ АККАУНТА</b>\n\n"
        "Это действие удалит:\n"
        "• Все ваши доходы\n"
        "• Все ваши расходы\n"
        "• Историю вопросов\n\n"
        "Это действие нельзя отменить!",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def handle_expense_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщения — определение: это расход или вопрос"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Проверка: пользователь в режиме чата?
    if user_id in chat_mode_users:
        # Режим чата — свободное общение с LLM
        try:
            await update.message.chat.send_action(action='typing')
            expenses = db.get_all_expenses_for_llm(user_id)
            incomes = db.get_all_incomes_for_llm(user_id)
            
            system_prompt = """Ты — дружелюбный финансовый ассистент. 
У тебя есть данные о доходах и расходах пользователя. Ты можешь:
- Отвечать на вопросы о финансах
- Давать советы по бюджету
- Просто общаться на любые темы
Будь кратким, полезным и используй эмодзи."""
            
            all_transactions = []
            for inc in (incomes or [])[:25]:
                t = dict(inc)
                t["type"] = "income"
                all_transactions.append(t)
            for exp in (expenses or [])[:25]:
                t = dict(exp)
                t["type"] = "expense"
                all_transactions.append(t)
            
            user_prompt = f"""Мои финансы:
{json.dumps(all_transactions, ensure_ascii=False)}

Сообщение: {text}"""
            
            answer = llm_client.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ], temperature=0.7)

            if answer:
                await update.message.reply_text(clean_llm_text(answer), reply_markup=back_keyboard())
            else:
                await update.message.reply_text(
                    "❌ Не удалось получить ответ. Попробуйте позже.",
                    reply_markup=back_keyboard()
                )
        except Exception as e:
            logger.error(f"Ошибка в чат-режиме: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте позже.",
                reply_markup=back_keyboard()
            )
        return

    # Показать "печатает..."
    await update.message.chat.send_action(action='typing')

    # Проверка: это вопрос?
    question_indicators = ['?', 'сколько', 'потратил', 'потратила', 'средний', 'какая', 'какой', 'какие', 'какую', 'максималь', 'минималь', 'сравн', 'анализ']
    is_question = '?' in text or any(indicator in text.lower() for indicator in question_indicators)

    if is_question:
        # Это вопрос — обрабатываем через LLM
        try:
            expenses = db.get_all_expenses_for_llm(user_id)
            incomes = db.get_all_incomes_for_llm(user_id)
            
            # Объединяем в один список с типами
            all_transactions = []
            for inc in (incomes or []):
                t = dict(inc)
                t["type"] = "income"
                all_transactions.append(t)
            for exp in (expenses or []):
                t = dict(exp)
                t["type"] = "expense"
                all_transactions.append(t)
            
            answer = llm_client.answer_question(text, all_transactions)

            if answer:
                db.save_llm_response(user_id, text, answer)
                await update.message.reply_text(clean_llm_text(answer))
            else:
                await update.message.reply_text("❌ Не удалось получить ответ. Попробуйте позже.")
        except Exception as e:
            logger.error(f"Ошибка при обработке вопроса: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке вопроса.")
        return

    # Это транзакция — парсим и сохраняем
    try:
        parsed = llm_client.parse_transaction(text)

        amount = parsed.get("amount")
        if amount is None:
            await update.message.reply_text(
                "❌ Не удалось распознать сумму.\n"
                "Попробуйте указать сумму явно, например:\n"
                "\"Обед 500 рублей\" или \"Зарплата 50000\""
            )
            return

        transaction_type = parsed.get("type", "expense")
        category = parsed.get("category", "Без категории")
        description = parsed.get("description", text)
        date_str = parsed.get("date")

        if transaction_type == "income":
            # Это доход
            db.add_income(
                user_id=user_id,
                raw_text=text,
                amount=amount,
                category=category,
                description=description,
                date=date_str
            )

            category_emoji = {
                "зарплата": "💼",
                "фриланс": "💻",
                "подарок": "🎁",
                "продажа": "🏷️",
                "возврат": "↩️",
                "другие": "📦"
            }
            emoji = category_emoji.get(category.lower(), "💰")

            response_text = (
                f"{emoji} Доход записан!\n\n"
                f"💵 Сумма: +{amount:.0f} ₽\n"
                f"📂 Категория: {category}\n"
                f"📝 {escape_html(description)}"
            )

        else:
            # Это расход
            db.add_expense(
                user_id=user_id,
                raw_text=text,
                amount=amount,
                category=category,
                description=description,
                date=date_str
            )

            category_emoji = {
                "еда": "🍕",
                "транспорт": "🚕",
                "развлечения": "🎬",
                "жилье": "🏠",
                "здоровье": "💊",
                "образование": "📚",
                "одежда": "👕",
                "другие": "📦"
            }
            emoji = category_emoji.get(category.lower(), "💰")

            response_text = (
                f"{emoji} Расход записан!\n\n"
                f"💵 Сумма: {amount:.0f} ₽\n"
                f"📂 Категория: {category}\n"
                f"📝 {escape_html(description)}"
            )

        # Кнопки для быстрых действий
        keyboard = [
            [
                InlineKeyboardButton("📊 Сводка за неделю", callback_data="summary_week"),
                InlineKeyboardButton("📈 Сводка за месяц", callback_data="summary_month")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(response_text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка при обработке транзакции: {e}")
        await update.message.reply_text("❌ Произошла ошибка при записи.")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    try:
        # --- Возврат в главное меню ---
        if data == "back":
            # Если пользователь был в режиме чата — выйти из него
            chat_mode_users.discard(user_id)
            await query.edit_message_text("📊 Выберите действие:", reply_markup=main_menu_keyboard())
            return

        # --- Режим чата ---
        if data == "chat_mode":
            chat_mode_users.add(user_id)
            await query.edit_message_text(
                "💬 <b>Режим чата активирован</b>\n\n"
                "Теперь вы можете свободно общаться со мной!\n"
                "Я знаю ваши расходы и могу ответить на любые вопросы.\n\n"
                "Напишите мне что-нибудь 👇",
                parse_mode="HTML",
                reply_markup=back_keyboard()
            )
            return

        # --- Сводка за прошлую неделю ---
        if data == "summary_week":
            await query.edit_message_text("⏳ Формирую сводку за неделю...")
            start_date, end_date = get_previous_week_range()
            expenses = db.get_all_expenses_for_llm(user_id, start_date, end_date)
            incomes = db.get_all_incomes_for_llm(user_id, start_date, end_date)
            period_label = format_period(start_date, end_date)

            if not expenses and not incomes:
                await query.edit_message_text(
                    f"📭 За {period_label} записей не найдено.",
                    reply_markup=back_keyboard()
                )
                return

            summary = llm_client.generate_summary(expenses, incomes, period_label)
            if summary:
                await query.edit_message_text(
                    f"📊 {period_label}\n\n{clean_llm_text(summary)}",
                    reply_markup=back_keyboard()
                )
            else:
                await query.edit_message_text(
                    "❌ Не удалось сгенерировать сводку.",
                    reply_markup=back_keyboard()
                )

        # --- Сводка за прошлый месяц ---
        elif data == "summary_month":
            await query.edit_message_text("⏳ Формирую сводку за месяц...")
            start_date, end_date = get_previous_month_range()
            expenses = db.get_all_expenses_for_llm(user_id, start_date, end_date)
            incomes = db.get_all_incomes_for_llm(user_id, start_date, end_date)
            period_label = format_period(start_date, end_date)

            if not expenses and not incomes:
                await query.edit_message_text(
                    f"📭 За {period_label} записей не найдено.",
                    reply_markup=back_keyboard()
                )
                return

            summary = llm_client.generate_summary(expenses, incomes, period_label)
            if summary:
                await query.edit_message_text(
                    f"📊 {period_label}\n\n{clean_llm_text(summary)}",
                    reply_markup=back_keyboard()
                )
            else:
                await query.edit_message_text(
                    "❌ Не удалось сгенерировать сводку.",
                    reply_markup=back_keyboard()
                )

        # --- Подтверждение очистки ---
        elif data == "confirm_clear_week":
            await query.edit_message_text("⏳ Удаляю расходы...")
            start_date, end_date = get_previous_week_range()
            deleted = db.delete_expenses_by_period(user_id, start_date, end_date)
            period_label = format_period(start_date, end_date)
            await query.edit_message_text(
                f"✅ Удалено расходов: {deleted}\nПериод: {period_label}",
                reply_markup=back_keyboard()
            )

        elif data == "confirm_clear_month":
            await query.edit_message_text("⏳ Удаляю расходы...")
            start_date, end_date = get_previous_month_range()
            deleted = db.delete_expenses_by_period(user_id, start_date, end_date)
            period_label = format_period(start_date, end_date)
            await query.edit_message_text(
                f"✅ Удалено расходов: {deleted}\nПериод: {period_label}",
                reply_markup=back_keyboard()
            )

        # --- Подтверждение удаления всех записей ---
        elif data == "confirm_clear_all":
            await query.edit_message_text("⏳ Удаляю все записи...")
            deleted_expenses = db.delete_all_expenses(user_id)
            deleted_incomes = db.delete_all_incomes(user_id)
            total_deleted = deleted_expenses + deleted_incomes
            await query.edit_message_text(
                f"✅ Удалено записей: {total_deleted}\n"
                f"Доходов: {deleted_incomes}\n"
                f"Расходов: {deleted_expenses}\n\n"
                f"Все ваши записи были удалены.",
                reply_markup=back_keyboard()
            )

        # --- Подтверждение удаления аккаунта ---
        elif data == "confirm_delete_data":
            await query.edit_message_text("⏳ Удаляю все ваши данные...")
            deleted = db.delete_all_user_data(user_id)
            # Выход из чат-режима
            chat_mode_users.discard(user_id)
            await query.edit_message_text(
                f"✅ Данные удалены:\n"
                f"• Расходов: {deleted['expenses']}\n"
                f"• Доходов: {deleted['incomes']}\n"
                f"• Записей истории: {deleted['llm_responses']}\n\n"
                "Все ваши данные полностью удалены.",
                reply_markup=main_menu_keyboard()
            )

        # --- Все расходы ---
        elif data == "all_expenses":
            expenses = db.get_expenses(user_id, limit=20)
            if not expenses:
                await query.edit_message_text(
                    "📭 У вас пока нет расходов.",
                    reply_markup=back_keyboard()
                )
                return

            total = db.get_total_expenses(user_id)
            text = f"📋 <b>Последние расходы</b> (всего: {total:.0f} ₽)\n\n"

            for exp in expenses[:10]:
                date = exp["date"][:10]
                category = f' [{exp["category"]}]' if exp["category"] else ""
                text += f"🔹 {date}{category}\n"
                text += f"   {exp['amount']:.0f} ₽ — {exp['description'] or exp['raw_text']}\n\n"

            await query.edit_message_text(
                text, parse_mode="HTML", reply_markup=back_keyboard()
            )

        elif data == "help":
            help_text = (
                "📖 <b>Как пользоваться ботом</b>\n\n"
                "💬 <b>Записать транзакцию</b>\n"
                "Просто напиши сообщение в свободной форме:\n\n"
                "🔴 <b>Расходы:</b>\n"
                "• \"Кофе 200\"\n"
                "• \"Продукты 1500 рублей\"\n"
                "• \"Метро 80\"\n\n"
                "🟢 <b>Доходы:</b>\n"
                "• \"Зарплата 50000\"\n"
                "• \"Получил от друга 1000\"\n"
                "• \"Продажу телефон 8000\"\n\n"
                "📊 <b>Сводки</b>\n"
                "• /week — сводка за прошлую неделю\n"
                "• /month — сводка за прошлый месяц\n"
                "• /all — все расходы\n\n"
                "🗑️ <b>Очистка</b>\n"
                "• /clear_week — удалить записи за прошлую неделю\n"
                "• /clear_month — удалить записи за прошлый месяц\n"
                "• /clear_all — удалить ВСЕ записи (с подтверждением)\n\n"
                "�️ <b>Удаление аккаунта</b>\n"
                "• /delete_data — удалить все ваши данные\n\n"
                "�💬 <b>Чат-режим</b>\n"
                "Нажми кнопку \"💬 Чат\" для свободного общения\n\n"
                "❓ <b>Вопросы</b>\n"
                "Задай вопрос о финансах:\n"
                "• \"Сколько я потратил на еду?\"\n"
                "• \"Какой баланс за месяц?\""
            )
            await query.edit_message_text(help_text, parse_mode="HTML", reply_markup=back_keyboard())

    except Exception as e:
        logger.error(f"Ошибка в handle_callback: {e}")
        try:
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте позже.")
        except Exception:
            await query.answer("Произошла ошибка", show_alert=True)


def create_application() -> ApplicationBuilder:
    """Создать и настроить приложение бота"""
    logger.info("Создание приложения бота...")

    application = ApplicationBuilder().token(config.BOT_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("week", week_summary))
    application.add_handler(CommandHandler("month", month_summary))
    application.add_handler(CommandHandler("all", all_expenses))
    application.add_handler(CommandHandler("clear_week", clear_week))
    application.add_handler(CommandHandler("clear_month", clear_month))
    application.add_handler(CommandHandler("clear_all", clear_all))
    application.add_handler(CommandHandler("delete_data", delete_data))

    # Кнопки
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Сообщения (расходы и вопросы)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_expense_message
    ))

    logger.info("Бот настроен!")
    return application


async def post_init(application):
    """Вызывается после инициализации бота"""
    bot_info = await application.bot.get_me()
    logger.info(f"Бот запущен: @{bot_info.username}")
