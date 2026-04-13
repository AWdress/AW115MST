FROM python:3.13-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=Asia/Shanghai
RUN apt-get update && apt-get install -y tzdata gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY modules/ ./modules/
COPY main_cli.py .
RUN mkdir -p /app/config /app/待检测 /app/可秒传 /app/待秒传 /app/logs /app/data
CMD ["python", "main_cli.py", "--watch"]
