# 🐳 Docker 部署指南

## 快速开始

### 1. 拉取镜像

```bash
# 从 Docker Hub 拉取镜像
docker pull awdress/aw115mst:latest
```

或者自己构建：

```bash
# 在项目根目录构建镜像
docker build -f docker/Dockerfile -t awdress/aw115mst:latest .
```

### 2. 准备配置

```bash
# 配置 115 cookies
nano config/115-cookies.txt

# 创建数据目录（用于存放断点续传和重新检测记录）
mkdir -p docker/data
touch docker/data/checkpoint.json docker/data/recheck.json
```

### 3. 使用方式

#### 方式 1：单次运行（推荐）

手动触发检测：

```bash
# 进入 docker 目录
cd docker

# 检测 input 目录并自动分类
docker-compose run --rm aw115mst python main_cli.py

# 仅检查不移动
docker-compose run --rm aw115mst python main_cli.py --check-only

# 重新检测 non_rapid 目录
docker-compose run --rm aw115mst python main_cli.py --recheck
```

#### 方式 2：监控模式

持续运行，自动处理新文件：

```bash
# 启动监控（前台运行）
docker-compose run --rm aw115mst python main_cli.py --watch

# 或后台运行
docker-compose run -d --name aw115mst-watch aw115mst python main_cli.py --watch

# 查看日志
docker logs -f aw115mst-watch

# 停止监控
docker stop aw115mst-watch
docker rm aw115mst-watch
```

#### 方式 3：定时任务（Cron）

使用系统 cron 定时运行：

```bash
# 编辑 crontab
crontab -e

# 每天凌晨 2 点检测新文件
0 2 * * * cd /path/to/AW115MST/docker && docker-compose run --rm aw115mst python main_cli.py >> ../logs/cron.log 2>&1

# 每天凌晨 3 点重新检测
0 3 * * * cd /path/to/AW115MST/docker && docker-compose run --rm aw115mst python main_cli.py --recheck >> ../logs/cron-recheck.log 2>&1
```

## 目录映射

| 容器路径 | 主机路径 | 说明 |
|---------|---------|------|
| `/app/config` | `../config` | 配置文件（只读） |
| `/app/input` | `../input` | 待检测文件 |
| `/app/rapid` | `../rapid` | 可秒传文件输出 |
| `/app/non_rapid` | `../non_rapid` | 不可秒传文件输出 |
| `/app/logs` | `../logs` | 日志文件 |
| `/app/data/checkpoint.json` | `./data/checkpoint.json` | 断点续传记录 |
| `/app/data/recheck.json` | `./data/recheck.json` | 重新检测记录 |

## 使用示例

### 示例 1：批量检测文件

```bash
# 1. 放入文件
cp /path/to/files/* ../input/

# 2. 运行检测
docker-compose run --rm aw115mst python main_cli.py

# 3. 查看结果
ls ../rapid/
ls ../non_rapid/
```

### 示例 2：定时任务（Cron）

```bash
# 编辑 crontab
crontab -e

# 每天凌晨 2 点检测新文件
0 2 * * * cd /path/to/AW115MST/docker && docker-compose run --rm aw115mst python main_cli.py

# 每天凌晨 3 点重新检测
0 3 * * * cd /path/to/AW115MST/docker && docker-compose run --rm aw115mst python main_cli.py --recheck
```

### 示例 3：自定义命令

```bash
# 不递归子目录
docker-compose run --rm aw115mst python main_cli.py --no-recursive

# 查看版本
docker-compose run --rm aw115mst python main_cli.py --version
```

## 环境变量

可以在 `docker-compose.yml` 中自定义环境变量：

```yaml
environment:
  - TZ=Asia/Shanghai          # 时区
  - PYTHONUNBUFFERED=1        # Python 输出不缓冲
```

## 故障排查

### 1. 权限问题

```bash
# 修改目录权限
chmod -R 755 ../input ../rapid ../non_rapid ../logs
chmod -R 755 data/
```

### 2. Cookies 无效

```bash
# 检查 cookies 文件
cat ../config/115-cookies.txt

# 重新获取并更新
```

### 3. 进入容器调试

```bash
# 进入容器
docker-compose run --rm aw115mst bash

# 在容器内运行命令
python main_cli.py --help
ls -la /app/
```

## 清理

```bash
# 停止并删除容器
docker-compose down

# 删除镜像
docker rmi awdress/aw115mst:latest
```

## 性能优化

### 调整资源限制

编辑 `docker-compose.yml`：

```yaml
services:
  aw115mst:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### 调整并发数

编辑 `../config/config.yaml`：

```yaml
performance:
  max_workers: 8  # 增加并发数
```

## 注意事项

1. **Cookies 安全**：不要将 `config/115-cookies.txt` 提交到 Git
2. **数据备份**：移动文件前建议先备份
3. **磁盘空间**：确保有足够的磁盘空间
4. **网络连接**：需要稳定的网络连接到 115 服务器
5. **镜像获取**：可以从 Docker Hub 拉取或自己构建
6. **数据文件**：`docker/data/` 目录用于存放断点续传和重新检测记录

## 更新

```bash
# 拉取最新代码
cd ..
git pull

# 拉取最新镜像
docker pull awdress/aw115mst:latest

# 或重新构建镜像
docker build -f docker/Dockerfile -t awdress/aw115mst:latest .

# 重启服务（如果有运行中的容器）
cd docker
docker-compose restart
```
