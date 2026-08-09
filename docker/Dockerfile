FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=Asia/Shanghai LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONUTF8=1
RUN apt-get update && apt-get install -y tzdata gcc libffi-dev libssl-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt p115-constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip check \
    && python -c "from asynctools import to_list; from p115client import P115Client"
COPY modules/ ./modules/
COPY main_cli.py .
RUN mkdir -p /app/config /app/待检测 /app/可秒传 /app/待秒传 /app/logs /app/data
CMD ["python", "main_cli.py", "--watch"]
