# AW115MST

**AW 115 Media Scan Tool** - 115网盘秒传检测工具

自动检测文件是否支持秒传，智能分类管理，支持实时监控和定时重检。

## ✨ 主要特性

- 🚀 **智能延迟移动** - 新文件多次检测后才移动，避免误判
- 🔄 **自动重新检测** - 定时重检不可秒传的文件
- 📁 **灵活文件处理** - 支持移动或复制模式
- 👁️ **实时监控** - 自动监控 input 目录的新文件
- ⏰ **定时任务** - 可配置的扫描和重检间隔
- 🤖 **Telegram Bot** - 交互式控制和通知
- 🐳 **Docker 支持** - 开箱即用的容器化部署
- ⚙️ **智能配置** - 自动合并配置，保留注释

## 📋 目录结构

```
AW115MST/
├── input/          # 待检测文件目录
├── rapid/          # 可秒传文件目录
├── non_rapid/      # 不可秒传文件目录（移动模式）
├── logs/           # 日志文件
├── data/           # 数据文件（断点、重检记录）
├── config/         # 配置文件
│   ├── config.yaml
│   └── 115-cookies.txt
├── modules/        # 核心模块
├── docker/         # Docker 配置
└── main_cli.py     # 主程序
```

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

1. **拉取镜像**
```bash
docker pull awdress/aw115mst:latest
```

2. **创建配置文件**
```bash
mkdir -p config input rapid non_rapid logs data
```

3. **配置 Cookies**
编辑 `config/115-cookies.txt`，填入你的 115 Cookies

4. **启动容器**
```bash
docker run -d \
  --name aw115mst \
  --restart unless-stopped \
  -v $(pwd)/config:/app/config:ro \
  -v $(pwd)/input:/app/input \
  -v $(pwd)/rapid:/app/rapid \
  -v $(pwd)/non_rapid:/app/non_rapid \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  -e TZ=Asia/Shanghai \
  awdress/aw115mst:latest
```

或使用 docker-compose：
```bash
cd docker
docker-compose up -d
```

### 方式二：本地运行

1. **安装依赖**
```bash
# 需要 Python 3.13+
pip install -r requirements.txt
```

2. **配置文件**
首次运行会自动创建配置文件模板：
```bash
python main_cli.py
```

3. **配置 Cookies**
编辑 `config/115-cookies.txt`，填入你的 115 Cookies

4. **运行程序**
```bash
# 默认模式（实时监控 + 定时任务）
python main_cli.py

# 手动模式（单次运行）
python main_cli.py --manual

# Telegram Bot 模式
python main_cli.py --telegram-bot
```

## ⚙️ 配置说明

### 核心配置

**文件处理模式**
```yaml
file_processing:
  move_strategy:
    use_copy: false  # false=移动模式，true=复制模式
```

- **移动模式**：文件会被移动到目标目录，原文件删除
- **复制模式**：文件会被复制到目标目录，原文件保留

**延迟移动策略**
```yaml
recheck:
  delay_move_times: 3  # 检测 N 次后才移动不可秒传文件
```

**定时任务**
```yaml
scheduler:
  watch:
    enabled: true           # 实时监控
    debounce_seconds: 5     # 防抖时间
  cron:
    enabled: true           # 定时任务
    interval: "30m"         # 间隔（5m, 30m, 1h, 6h 等）
```

**Telegram 通知**
```yaml
telegram:
  enabled: true
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
  bot_mode: true  # 启用 Bot 交互模式
```

### 完整配置

参考 `config/config.yaml.example` 查看所有配置项。

## 🔧 使用场景

### 场景 1：自动整理媒体文件（移动模式）

```yaml
use_copy: false
delay_move_times: 3
interval: "1h"
```

- 新文件放入 `input/`
- 自动检测 3 次
- 可秒传 → 移动到 `rapid/`
- 不可秒传 → 移动到 `non_rapid/`，继续重检

### 场景 2：安全备份模式（复制模式）

```yaml
use_copy: true
delay_move_times: 3
interval: "6h"
```

- 新文件放入 `input/`
- 自动检测 3 次
- 可秒传 → 复制到 `rapid/`，原文件保留
- 不可秒传 → 保留在 `input/`，继续重检

### 场景 3：Telegram Bot 控制

```bash
python main_cli.py --telegram-bot
```

在 Telegram 中：
- `/start` - 显示控制面板
- `/status` - 查看系统状态
- `/scan` - 立即扫描
- `/recheck` - 立即重检

## 📊 工作流程

### 移动模式流程

```
input/movie.mkv
  ↓ 实时监控检测
  ↓ 定时任务重检（第1次）
  ↓ 定时任务重检（第2次）
  ↓ 定时任务重检（第3次）
  ├─ ✅ 可秒传 → rapid/movie.mkv
  └─ ⚠️ 不可秒传 → non_rapid/movie.mkv
       ↓ 继续定时重检
       └─ ✅ 变为可秒传 → rapid/movie.mkv
```

### 复制模式流程

```
input/movie.mkv
  ↓ 实时监控检测
  ↓ 定时任务重检（第1次）
  ↓ 定时任务重检（第2次）
  ↓ 定时任务重检（第3次）
  ├─ ✅ 可秒传 → 复制到 rapid/movie.mkv
  │              原文件保留在 input/
  │              标记已处理，不再重复检测
  └─ ⚠️ 不可秒传 → 保留在 input/movie.mkv
       ↓ 重置计数，继续定时重检
       └─ ✅ 变为可秒传 → 复制到 rapid/movie.mkv
```

## 🛠️ 命令行选项

```bash
# 查看帮助
python main_cli.py --help

# 默认模式（实时监控 + 定时任务）
python main_cli.py

# 手动模式（单次运行）
python main_cli.py --manual

# 指定输入目录
python main_cli.py --manual --input /path/to/files

# 仅检查不移动
python main_cli.py --manual --check-only

# 重新检测 non_rapid 目录
python main_cli.py --recheck

# 清理已处理文件记录（复制模式）
python main_cli.py --clean-processed

# 测试 Telegram 通知
python main_cli.py --test-telegram

# 启动 Telegram Bot
python main_cli.py --telegram-bot
```

## 📦 依赖项

- Python 3.13+
- p115client >= 0.0.9
- PyYAML >= 6.0
- requests >= 2.31.0
- tqdm >= 4.66.0
- colorama >= 0.4.6
- watchdog >= 3.0.0
- ruamel.yaml >= 0.17.0
- python-telegram-bot >= 20.0
- psutil >= 5.9.0

## 🐳 Docker 镜像

- **镜像地址**: `awdress/aw115mst:latest`
- **架构支持**: amd64
- **自动构建**: GitHub Actions

## 📝 获取 115 Cookies

1. 在浏览器中登录 [115.com](https://115.com)
2. 打开开发者工具（F12）
3. 切换到 Network 标签
4. 刷新页面，找到任意请求
5. 在请求头中找到 Cookie 字段
6. 复制完整的 Cookie 值到 `config/115-cookies.txt`

Cookie 格式示例：
```
UID=12345678_A1_1234567890; CID=abcdefghijklmnopqrstuvwxyz; SEID=xyz123...
```

## 🤖 Telegram Bot 功能

### 主要功能

- 📊 查看状态 - 文件分布、系统状态
- 🔍 立即检测 - 手动触发扫描
- 🔄 重新检测 - 手动触发重检
- 📈 查看统计 - 文件统计、秒传率
- 📁 文件列表 - 最近检测的文件
- ⚙️ 系统信息 - CPU、内存、磁盘
- 🔔 通知设置 - 配置通知选项

### 设置 Bot

1. 与 [@BotFather](https://t.me/BotFather) 对话创建 Bot
2. 获取 Bot Token
3. 获取你的 Chat ID（可以用 [@userinfobot](https://t.me/userinfobot)）
4. 配置 `config.yaml`：
```yaml
telegram:
  enabled: true
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
  bot_mode: true
```
5. 启动 Bot：`python main_cli.py --telegram-bot`

## 🔍 故障排查

### 问题：配置文件缺少新配置项

**解决方案**：程序会自动合并配置，保留注释。如果需要手动更新，参考 `config/config.yaml.example`。

### 问题：Docker 容器无法访问文件

**解决方案**：检查目录挂载权限，确保容器有读写权限。

### 问题：Telegram 通知不工作

**解决方案**：
1. 测试连接：`python main_cli.py --test-telegram`
2. 检查 bot_token 和 chat_id 是否正确
3. 确保 Bot 已启动对话

### 问题：文件重复检测

**解决方案**：
- 移动模式：文件会被移动，不会重复检测
- 复制模式：可秒传文件会被标记，不会重复检测
- 如需清理记录：`python main_cli.py --clean-processed`

## 📄 许可证

MIT License

## 🔗 相关链接

- GitHub: https://github.com/AWdress/AW115MST
- Docker Hub: https://hub.docker.com/r/awdress/aw115mst
- 115网盘: https://115.com

## 🙏 致谢

- [p115client](https://github.com/ChenyangGao/p115client) - 115网盘 Python 客户端
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API

## 📮 反馈与贡献

欢迎提交 Issue 和 Pull Request！

---

**注意**：本工具仅供学习交流使用，请遵守相关法律法规。
