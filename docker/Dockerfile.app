FROM python:3.11-slim

WORKDIR /app

# 1. apt-get update отдельно
RUN apt-get update

# 2. Установка build-essential отдельно
RUN apt-get install -y build-essential

# 3. Очистка кэша apt
RUN rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY ./src/ /app

CMD ["python", "test_format.py"]
