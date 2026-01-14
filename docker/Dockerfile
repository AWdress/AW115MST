FROM python:3.13-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=Asia/Shanghai
RUN apt-get update && apt-get install -y tzdata gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir PyYAML requests tqdm colorama watchdog p115client
COPY modules/ ./modules/
COPY main_cli.py .
RUN mkdir -p /app/config /app/input /app/rapid /app/non_rapid /app/logs /app/data
CMD ["python", "main_cli.py", "--watch"]
