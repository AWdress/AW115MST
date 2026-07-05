<div align="center">
  <img src="logo.png" alt="AW115MST Logo" width="600"/>
  
  <p><strong>AW 115 Media Scan Tool</strong> - 智能的 115 网盘秒传检测工具</p>
  
  <p>自动检测文件是否支持秒传，智能分类管理，支持实时监控、定时重检和 Telegram Bot 控制。</p>
  
  <p>
    <a href="https://hub.docker.com/r/awdress/aw115mst"><img src="https://img.shields.io/docker/v/awdress/aw115mst?label=Docker&logo=docker" alt="Docker Image"></a>
    <a href="https://github.com/AWdress/AW115MST/releases/tag/v1.0.0"><img src="https://img.shields.io/github/v/release/AWdress/AW115MST" alt="GitHub Release"></a>
    <a href="LICENSE"><img src="https://img.shields.io/github/license/AWdress/AW115MST" alt="License"></a>
  </p>
</div>

## ✨ 主要特性

- 🔍 **实时检测即处理** - 实时监控到新文件立即完整检测并秒传移动，定时任务补全漏检文件
- 📋 **移动/复制双模式** - 支持移动文件或保留原文件做种
- ⏰ **实时监控 + 定时任务** - 新文件到达立即处理，定期补全扫描 + 重检不可秒传文件
- 🤖 **Telegram Bot** - 远程控制和实时通知
- 🛠️ **智能配置管理** - 首次运行自动创建配置，升级时自动合并
- 🐳 **Docker 支持** - 一键部署，开箱即用

## 📋 目录结构

```
AW115MST/
├── 待检测/         # 待检测文件目录
├── 可秒传/         # 可秒传文件目录
├── 待秒传/         # 不可秒传文件目录
├── logs/           # 日志文件
├── data/           # 数据文件
│   └── aw115mst.db # SQLite 数据库（检测记录/断点）
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

1. **安装依赖**（需要 Python 3.12+）
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

> **推荐用内置的扫码登录**（`--login`）取 cookie，而不是从浏览器 / 油猴脚本手动复制。
> 扫码登录拿到的是 115 官方一等会话，对上传/建目录等操作有效；而油猴等旁路方式签发的
> cookie 常出现「登录能通过、但操作全部报 `990001 登录超时`」的问题。

### 方式一：扫码登录（推荐）

```bash
# 本地
python main_cli.py --login              # 默认登录到 115android(F3) 槽位

# Docker（config 需为可写挂载 :rw）
docker exec -it AW115MST python main_cli.py --login
```

终端会打印二维码，用手机 115 App 扫码确认后，cookie 自动写入 `config/115-cookies.txt`。

**各端登录命令**（给工具用一个你平时不碰的槽位，避免和手机/网页互相踢下线）：

| 命令 | 槽位 | 说明 |
|------|------|------|
| `--login web` | A1 | 115生活_网页端 |
| `--login desktop` | A1 | 115浏览器 |
| `--login android` | F1 | 115生活_安卓端 |
| `--login 115android` | F3 | 115_安卓端（默认） |
| `--login qandroid` | M1 | 115管理_安卓端 |
| `--login ios` | D1 | 115生活_苹果端 |
| `--login 115ios` | D3 | 115_苹果端 |
| `--login qios` | N1 | 115管理_苹果端 |
| `--login ipad` | H1 | 115生活_苹果平板端 |
| `--login 115ipad` | H3 | 115_苹果平板端 |
| `--login qipad` | O1 | 115管理_苹果平板端 |
| `--login tv` | I1 | 115生活_安卓电视端 |
| `--login harmony` | S1 | 115_鸿蒙端 |
| `--login wechatmini` | R1 | 115生活_微信小程序端 |
| `--login alipaymini` | R2 | 115生活_支付宝小程序端 |

> 每个 app 槽位是**独立的单会话**：同一账号在同一槽位重复登录会把先前的踢下线。
> 所以给工具选一个你自己不用的端（比如你手机用 F3，就给工具用 `qandroid`/`tv`），互不干扰。
> 换 cookie / 失效时，再跑一次对应的 `--login` 即可，不要用油猴脚本重复签发。

### 方式二：手动复制（不推荐）

1. 浏览器登录 [115.com](https://115.com)
2. 打开开发者工具（F12）→ Network 标签
3. 刷新页面，找到任意请求
4. 复制请求头中的 Cookie 值到 `config/115-cookies.txt`

Cookie 格式示例：
```
UID=12345678_A1_1234567890; CID=abcdefghijklmnopqrstuvwxyz; SEID=xyz123...; KID=...
```

## ⚙️ 配置说明

### 文件处理模式

```yaml
file_processing:
  move_strategy:
    use_copy: false  # false=移动模式，true=复制模式
```

**移动模式**（默认）
- 可秒传文件：移动到 `可秒传/`
- 不可秒传文件：检测 N 次后移动到 `待秒传/`，继续重检

**复制模式**
- 可秒传文件：复制到 `可秒传/`，原文件保留
- 不可秒传文件：保留在 `待检测/`，继续重检

### 重检配置

```yaml
recheck:
  max_recheck_times: 10  # 最大重新检测次数（超过后触发上传或停止检测）
```

不可秒传文件**立即**移动到 `待秒传/`，由定时任务周期性重检，直到变为可秒传或达到上限。

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

# 重新检测 待秒传 目录
python main_cli.py --recheck

# 扫码登录取 cookie（各端命令见「获取 115 Cookies」章节）
python main_cli.py --login              # 默认 115android(F3)
python main_cli.py --login qandroid     # 换成你不用的槽位

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
docker exec -it aw115mst python main_cli.py --login      # 扫码登录换 cookie（config 需 :rw 挂载）
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
- `/scan` - 立即扫描 待检测 目录
- `/recheck` - 立即重检 待秒传 目录
- `/login [app]` - 扫码登录取 cookie（机器人发二维码，手机扫码后自动写入并热加载，免重启）

> `/login` 不带参数会弹出常用端选择按钮；也可直接 `/login qandroid` 指定槽位。
> 出于安全考虑，`/login` 仅允许配置的 `telegram.chat_id` 使用。

### Bot 菜单功能

- 📊 **查看状态** - 文件分布、系统运行状态
- 🔍 **立即检测** - 手动扫描 待检测 目录（等同 `--manual`）
- 🔄 **重新检测** - 手动重检 待秒传 目录（等同 `--recheck`）
- 🔑 **扫码登录** - 机器人发二维码，手机扫码换 cookie，自动写入并热加载
- 🧹 **清理记录** - 清理已处理文件标记（等同 `--clean-processed`）
- 📈 **查看统计** - 文件统计、秒传率
- 📁 **文件列表** - 最近检测的文件
- ⚙️ **系统信息** - CPU、内存、磁盘使用情况
- 🔔 **通知设置** - 配置通知选项
- ❓ **帮助** - 查看帮助信息

## 📊 工作流程

### 移动模式（默认）

```
待检测/movie.mkv
  ↓ 实时监控检测（立即处理）
  ├─ ✅ 可秒传 → 秒传到115，移动到 可秒传/movie.mkv
  └─ ⚠️ 不可秒传 → 立即移动到 待秒传/movie.mkv
       ↓ 定时任务周期性重检
       ├─ ✅ 变为可秒传 → 秒传到115，移动到 可秒传/movie.mkv
       └─ 超过 max_recheck_times
            ├─ upload.enabled=true → 直接上传到115
            └─ upload.enabled=false → 停止检测，保留在 待秒传/
```

### 复制模式

```
待检测/movie.mkv
  ↓ 实时监控检测（立即处理）
  ├─ ✅ 可秒传 → 复制到 可秒传/movie.mkv，原文件保留并标记已处理
  └─ ⚠️ 不可秒传 → 复制到 待秒传/movie.mkv，原文件保留并标记已分发
       ↓ 定时任务重检 待秒传/ 中的副本
       ├─ ✅ 变为可秒传 → 秒传到115，副本清理
       └─ 超过 max_recheck_times
            ├─ upload.enabled=true → 直接上传到115
            └─ upload.enabled=false → 停止检测，保留在 待秒传/
```

## 🔍 故障排查

### 配置文件缺少新配置项

程序会自动合并配置，保留注释。如需手动更新，参考 `config/config.yaml.example`。

### Docker 容器无法访问文件

检查目录挂载权限，确保容器有读写权限：
```bash
chmod -R 755 待检测 可秒传 待秒传 logs data
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

- Python 3.12+
- p115client == 0.0.9.3.7（已锁定版本，避免上游 API 变动导致启动崩溃）
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
