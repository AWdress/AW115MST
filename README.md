<div align="center">
  <img src="logo.png" alt="AW115MST Logo" width="600"/>
  
  <p><strong>AW 115 Media Scan Tool</strong> - 智能的 115 网盘秒传检测工具</p>
  
  <p>自动检测文件是否支持秒传，智能分类管理，支持实时监控、定时重检和 Telegram Bot 控制。</p>
  
  <p>
    <a href="https://hub.docker.com/r/awdress/aw115mst"><img src="https://img.shields.io/docker/v/awdress/aw115mst?label=Docker&logo=docker" alt="Docker Image"></a>
    <a href="[https://github.com/AWdress/AW115MST/releases](https://github.com/AWdress/AW115MST/releases/tag/v1.0.0)"><img src="https://img.shields.io/github/v/release/AWdress/AW115MST" alt="GitHub Release"></a>
    <a href="LICENSE"><img src="https://img.shields.io/github/license/AWdress/AW115MST" alt="License"></a>
  </p>
</div>

## ✨ 主要特性

- 🔍 **智能延迟移动** - 检测 N 次后才移动不可秒传文件，避免误判
- 📋 **移动/复制双模式** - 支持移动文件或保留原文件
- ⏰ **实时监控 + 定时任务** - 自动检测新文件，定期重检不可秒传文件
- 🤖 **Telegram Bot** - 远程控制和实时通知
- 🛠️ **智能配置管理** - 首次运行自动创建配置，升级时自动合并
- 🐳 **Docker 支持** - 一键部署，开箱即用

## 📋 目录结构

```
AW115MST/
├── input/          # 待检测文件目录
├── rapid/          # 可秒传文件目录
├── non_rapid/      # 不可秒传文件目录
├── logs/           # 日志文件
├── data/           # 数据文件（断点、重检记录）
└── config/         # 配置文件
    ├── config.yaml
    └── 115-cookies.txt
```

## 🚀 快速开始

### Docker 部署（推荐）

1. **克隆仓库**
```bash
git clone https://github.com/AWdress/AW115MST.git
cd AW115MST
```

2. **配置文件**
```bash
# 编辑配置文件
cp config/config.yaml.example config/config.yaml
cp config/115-cookies.txt.example config/115-cookies.txt

# 填入你的 115 Cookies
nano config/115-cookies.txt
```

3. **启动容器**
```bash
cd docker
docker-compose up -d
```

4. **查看日志**
```bash
docker-compose logs -f
```

### 本地运行

1. **安装依赖**（需要 Python 3.13+）
```bash
pip install -r requirements.txt
```

2. **首次运行**（自动创建配置文件）
```bash
python main_cli.py
```

3. **配置 Cookies**
```bash
# 编辑 config/115-cookies.txt，填入你的 115 Cookies
nano config/115-cookies.txt
```

4. **启动程序**
```bash
# 默认模式（实时监控 + 定时任务）
python main_cli.py
```

## 📝 获取 115 Cookies

1. 浏览器登录 [115.com](https://115.com)
2. 打开开发者工具（F12）→ Network 标签
3. 刷新页面，找到任意请求
4. 复制请求头中的 Cookie 值到 `config/115-cookies.txt`

Cookie 格式示例：
```
UID=12345678_A1_1234567890; CID=abcdefghijklmnopqrstuvwxyz; SEID=xyz123...
```

## ⚙️ 配置说明

### 文件处理模式

```yaml
file_processing:
  move_strategy:
    use_copy: false  # false=移动模式，true=复制模式
```

**移动模式**（默认）
- 可秒传文件：移动到 `rapid/`
- 不可秒传文件：检测 N 次后移动到 `non_rapid/`，继续重检

**复制模式**
- 可秒传文件：复制到 `rapid/`，原文件保留
- 不可秒传文件：保留在 `input/`，继续重检

### 延迟移动策略

```yaml
recheck:
  delay_move_times: 3  # 检测 N 次后才移动不可秒传文件
  max_recheck_times: 10  # 最大重新检测次数
```

### 调度配置

```yaml
scheduler:
  watch:
    enabled: true           # 实时监控
    debounce_seconds: 5     # 防抖时间（秒）
  cron:
    enabled: true           # 定时任务
    interval: "30m"         # 间隔（5m, 30m, 1h, 6h 等）
```

### Telegram 通知与 Bot

```yaml
telegram:
  enabled: true
  bot_token: "YOUR_BOT_TOKEN"      # 从 @BotFather 获取
  chat_id: "YOUR_CHAT_ID"          # 你的用户 ID
  notify_on_complete: true         # 处理完成时通知
  notify_on_error: true            # 发生错误时通知
  notify_on_rapid: false           # 每个可秒传文件都通知
```

**功能说明**：
- `enabled: true` + 配置了 `bot_token` 和 `chat_id`：
  - ✅ 自动发送通知消息
  - ✅ 自动启动 Bot 交互控制（可通过 Telegram 远程控制）
- `enabled: false`：所有 Telegram 功能禁用

完整配置参考：[config.yaml.example](config/config.yaml.example)

## 🛠️ 命令行使用

### 本地运行

```bash
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

# 仅启动 Telegram Bot（不运行调度器）
python main_cli.py --telegram-bot

# 查看帮助
python main_cli.py --help
```

### Docker 容器

```bash
# 容器默认运行：实时监控 + 定时任务 + Telegram 通知（如果配置）

# 查看日志
docker-compose logs -f

# 重启容器
docker-compose restart

# 停止容器
docker-compose down

# 进入容器执行命令
docker exec -it aw115mst python main_cli.py --recheck
docker exec -it aw115mst python main_cli.py --clean-processed
```

## 🤖 Telegram Bot 交互控制

Telegram Bot 会在配置后**自动启动**，无需额外操作。

### 设置 Bot

1. 与 [@BotFather](https://t.me/BotFather) 对话创建 Bot，获取 Token
2. 与 [@userinfobot](https://t.me/userinfobot) 对话获取你的 Chat ID
3. 配置 `config.yaml`：
```yaml
telegram:
  enabled: true
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
```
4. 启动程序（Bot 会自动启动）：
   - **Docker**: `docker-compose up -d`
   - **本地**: `python main_cli.py`

### Bot 命令

- `/start` - 显示控制面板
- `/status` - 查看系统状态
- `/scan` - 立即扫描 input 目录
- `/recheck` - 立即重检 non_rapid 目录

### Bot 菜单功能

- 📊 **查看状态** - 文件分布、系统运行状态
- 🔍 **立即检测** - 手动扫描 input 目录（等同 `--manual`）
- 🔄 **重新检测** - 手动重检 non_rapid 目录（等同 `--recheck`）
- 🧹 **清理记录** - 清理已处理文件标记（等同 `--clean-processed`）
- 📈 **查看统计** - 文件统计、秒传率
- 📁 **文件列表** - 最近检测的文件
- ⚙️ **系统信息** - CPU、内存、磁盘使用情况
- 🔔 **通知设置** - 配置通知选项
- ❓ **帮助** - 查看帮助信息

## 📊 工作流程

### 移动模式（默认）

```
input/movie.mkv
  ↓ 实时监控检测
  ↓ 定时任务重检（第1次）
  ↓ 定时任务重检（第2次）
  ↓ 定时任务重检（第3次）
  ├─ ✅ 可秒传 → 移动到 rapid/movie.mkv
  └─ ⚠️ 不可秒传 → 移动到 non_rapid/movie.mkv
       ↓ 继续定时重检
       └─ ✅ 变为可秒传 → 移动到 rapid/movie.mkv
```

### 复制模式

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

## 🔍 故障排查

### 配置文件缺少新配置项

程序会自动合并配置，保留注释。如需手动更新，参考 `config/config.yaml.example`。

### Docker 容器无法访问文件

检查目录挂载权限，确保容器有读写权限：
```bash
chmod -R 755 input rapid non_rapid logs data
```

### Telegram 通知不工作

1. 测试连接：`python main_cli.py --test-telegram`
2. 检查 `bot_token` 和 `chat_id` 是否正确
3. 确保已与 Bot 启动对话（发送 `/start`）

### 文件重复检测

- **移动模式**：文件会被移动，不会重复检测
- **复制模式**：可秒传文件会被标记，不会重复检测
- 如需清理记录：`python main_cli.py --clean-processed`

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
- **版本标签**: `awdress/aw115mst:v1.0.0`
- **架构支持**: linux/amd64
- **自动构建**: GitHub Actions

## 📄 许可证

MIT License

## 🙏 致谢

- [p115client](https://github.com/ChenyangGao/p115client) - 115 网盘 Python 客户端
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API

## 🔗 相关链接

- **GitHub**: https://github.com/AWdress/AW115MST
- **Docker Hub**: https://hub.docker.com/r/awdress/aw115mst
- **问题反馈**: https://github.com/AWdress/AW115MST/issues
- **115 网盘**: https://115.com

## 📮 反馈与贡献

欢迎提交 Issue 和 Pull Request！

---

**注意**：本工具仅供学习交流使用，请遵守相关法律法规。
