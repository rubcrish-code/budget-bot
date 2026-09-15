FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создаём директорию для данных
RUN mkdir -p /app/data

ENV DB_PATH=/app/data/expenses.db

CMD ["python", "main.py"]
