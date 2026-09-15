"""
Helper функции для работы с календарными периодами
"""
from datetime import datetime, timedelta
from typing import Tuple


def get_week_range(date: datetime = None) -> Tuple[str, str]:
    """
    Получить начало и конец календарной недели (Пн-Вс)
    
    Returns:
        (start_date, end_date) в формате "YYYY-MM-DD HH:MM:SS"
    """
    if date is None:
        date = datetime.now()
    
    # Начало недели (понедельник)
    start_of_week = date - timedelta(days=date.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Конец недели (воскресенье 23:59:59)
    end_of_week = start_of_week + timedelta(days=6)
    end_of_week = end_of_week.replace(hour=23, minute=59, second=59)
    
    return (
        start_of_week.strftime("%Y-%m-%d %H:%M:%S"),
        end_of_week.strftime("%Y-%m-%d %H:%M:%S")
    )


def get_previous_week_range(date: datetime = None) -> Tuple[str, str]:
    """
    Получить начало и конец предыдущей календарной недели (Пн-Вс)
    
    Returns:
        (start_date, end_date) в формате "YYYY-MM-DD HH:MM:SS"
    """
    if date is None:
        date = datetime.now()
    
    # Начало предыдущей недели
    start_of_week = date - timedelta(days=date.weekday() + 7)
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Конец предыдущей недели
    end_of_week = start_of_week + timedelta(days=6)
    end_of_week = end_of_week.replace(hour=23, minute=59, second=59)
    
    return (
        start_of_week.strftime("%Y-%m-%d %H:%M:%S"),
        end_of_week.strftime("%Y-%m-%d %H:%M:%S")
    )


def get_month_range(date: datetime = None) -> Tuple[str, str]:
    """
    Получить начало и конец календарного месяца (1 число - последний день)
    
    Returns:
        (start_date, end_date) в формате "YYYY-MM-DD HH:MM:SS"
    """
    if date is None:
        date = datetime.now()
    
    # Начало месяца
    start_of_month = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Конец месяца
    if date.month == 12:
        end_of_month = date.replace(year=date.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end_of_month = date.replace(month=date.month + 1, day=1) - timedelta(days=1)
    end_of_month = end_of_month.replace(hour=23, minute=59, second=59)
    
    return (
        start_of_month.strftime("%Y-%m-%d %H:%M:%S"),
        end_of_month.strftime("%Y-%m-%d %H:%M:%S")
    )


def get_previous_month_range(date: datetime = None) -> Tuple[str, str]:
    """
    Получить начало и конец предыдущего календарного месяца
    
    Returns:
        (start_date, end_date) в формате "YYYY-MM-DD HH:MM:SS"
    """
    if date is None:
        date = datetime.now()
    
    # Начало предыдущего месяца
    if date.month == 1:
        start_of_month = date.replace(year=date.year - 1, month=12, day=1,
                                       hour=0, minute=0, second=0, microsecond=0)
    else:
        start_of_month = date.replace(month=date.month - 1, day=1,
                                       hour=0, minute=0, second=0, microsecond=0)
    
    # Конец предыдущего месяца
    if start_of_month.month == 12:
        end_of_month = start_of_month.replace(year=start_of_month.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end_of_month = start_of_month.replace(month=start_of_month.month + 1, day=1) - timedelta(days=1)
    end_of_month = end_of_month.replace(hour=23, minute=59, second=59)
    
    return (
        start_of_month.strftime("%Y-%m-%d %H:%M:%S"),
        end_of_month.strftime("%Y-%m-%d %H:%M:%S")
    )


def get_rolling_period(days: int, date: datetime = None) -> Tuple[str, str]:
    """
    Получить скользящий период (последние N дней)
    
    Returns:
        (start_date, end_date) в формате "YYYY-MM-DD HH:MM:SS"
    """
    if date is None:
        date = datetime.now()
    
    end_date = date.replace(hour=23, minute=59, second=59)
    start_date = date - timedelta(days=days)
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    return (
        start_date.strftime("%Y-%m-%d %H:%M:%S"),
        end_date.strftime("%Y-%m-%d %H:%M:%S")
    )


def format_period(start_date: str, end_date: str) -> str:
    """
    Красиво отформатировать период для отображения
    
    Args:
        start_date: "YYYY-MM-DD HH:MM:SS"
        end_date: "YYYY-MM-DD HH:MM:SS"
    
    Returns:
        "07.09.2026 - 13.09.2026"
    """
    start = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
    
    return f"{start.day:02d}.{start.month:02d}.{start.year} - {end.day:02d}.{end.month:02d}.{end.year}"
