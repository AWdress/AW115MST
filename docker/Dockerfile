# 使用 Python 3.13 官方镜像
FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 复制项目代码
COPY modules/ ./modules/
COPY gui/ ./gui/
COPY main_cli.py .
COPY main_gui.py .

# 创建数据目录（将被 volume 覆盖）
RUN mkdir -p /app/config /app/input /app/rapid /app/non_rapid /app/logs

# 设置执行权限
RUN chmod +x main_cli.py main_gui.py

# 默认命令：监控模式
CMD ["python", "main_cli.py", "--watch"]
