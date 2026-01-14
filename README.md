<div align="center">

# 🚀 AW115MST

**AW 115 Media Scan Tool**

*智能检测 115 网盘秒传状态，自动分类管理文件*

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()
[![GitHub](https://img.shields.io/badge/GitHub-AWdress%2FAW115MST-blue.svg)](https://github.com/AWdress/AW115MST)

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [使用指南](#-使用指南) • [配置说明](#-配置说明) • [常见问题](#-常见问题)

</div>

---

## 📖 简介

**AW115MST** 是一款专为 115 网盘用户设计的智能文件管理工具。它能够自动检测文件是否支持秒传功能，并将文件智能分类到不同目录，大幅提升文件管理效率。

### 💡 什么是秒传？

秒传是 115 网盘的特色功能。如果网盘服务器已经存在相同的文件，你可以"秒传"该文件而无需实际上传，节省大量时间和带宽。

### 🎯 工作流程

```
待检测文件 → input/ → [AW115MST 检测] → 自动分类
                                          ↓
                              ┌───────────┴───────────┐
                              ↓                       ↓
                          rapid/                 non_rapid/
                        (可秒传)                (不可秒传)
```

---

## ✨ 功能特性

<table>
<tr>
<td width="50%">

### 🔍 智能检测
- 自动计算文件 SHA-1 哈希值
- 查询 115 网盘秒传状态
- 支持所有文件类型
- 递归扫描子目录

</td>
<td width="50%">

### 📁 自动分类
- 可秒传 → `rapid/` 目录
- 不可秒传 → `non_rapid/` 目录
- 保持原有目录结构
- 完整移动文件夹

</td>
</tr>
<tr>
<td width="50%">

### 🔄 重新检测
- 定期重新检测不可秒传文件
- 自动发现状态变化
- 智能间隔控制
- 最大次数限制

</td>
<td width="50%">

### 📊 详细日志
- 实时处理进度显示
- 完整操作记录
- CSV 格式报告导出
- 断点续传支持

</td>
</tr>
</table>

---

## 🚀 快速开始

### 1️⃣ 安装依赖

```bash
# 克隆项目
git clone https://github.com/AWdress/AW115MST.git
cd AW115MST

# 安装依赖（需要 Python 3.13+）
pip install -r requirements.txt
```

### 2️⃣ 配置 115 Cookies

```bash
# 编辑配置文件
nano config/115-cookies.txt
```

**获取 Cookies 方法：**
1. 浏览器访问 [115.com](https://115.com) 并登录
2. 按 `F12` 打开开发者工具
3. 切换到 `Network` 标签
4. 刷新页面，找到任意请求
5. 复制 `Request Headers` 中的 `Cookie` 值
6. 粘贴到 `config/115-cookies.txt` 文件

### 3️⃣ 开始使用

```bash
# 方式 1：单次检测
# 将待检测文件放入 input 目录
cp /path/to/your/files/* input/

# 运行检测（自动分类）
python main_cli.py

# 查看结果
ls rapid/      # 可秒传文件
ls non_rapid/  # 不可秒传文件

# 方式 2：监控模式（推荐）
# 启动监控，自动处理新文件
python main_cli.py --watch

# 然后随时将文件放入 input/ 目录，程序会自动处理
```

---

## 📚 使用指南

### 命令行模式（CLI）

```bash
# 基础用法
python main_cli.py                    # 检测 input/ 并自动分类
python main_cli.py --check-only       # 仅检查不移动
python main_cli.py --recheck          # 重新检测 non_rapid/

# 监控模式（实时监控新文件）
python main_cli.py --watch            # 持续监控 input/ 目录
python main_cli.py --watch --debounce 10  # 自定义防抖时间（秒）

# 高级选项
python main_cli.py --input /path      # 指定输入目录
python main_cli.py --target /path     # 指定输出目录
python main_cli.py --no-recursive     # 不递归子目录
python main_cli.py --help             # 查看帮助
```

### 图形界面模式（GUI）

```bash
python main_gui.py
```

### 监控模式说明

监控模式会持续监控 `input/` 目录，自动处理新文件：

```bash
# 启动监控
python main_cli.py --watch

# 特点：
# - 实时检测新文件（使用文件系统监控）
# - 智能防抖（等待文件复制完成后才处理）
# - 自动处理并移动文件
# - 按 Ctrl+C 停止监控
```

### 重新检测功能

不可秒传的文件可能在一段时间后变成可秒传（其他人上传了相同文件）：

```bash
# 重新检测 non_rapid 目录
python main_cli.py --recheck
```

**工作原理：**
- ✅ 首次检测后记录文件信息
- ⏰ 按配置的间隔时间重新检测
- 🔄 发现可秒传后自动移动到 `rapid/`
- 🛑 达到最大次数后停止检测

---

## ⚙️ 配置说明

### 配置文件：`config/config.yaml`

```yaml
# 115 网盘配置
p115:
  cookies_file: "./config/115-cookies.txt"
  check_for_relogin: true

# 文件过滤
file_processing:
  filters:
    min_size: 0                    # 最小文件大小（0=不限制）
    max_size: 107374182400         # 最大文件大小（100GB）
    exclude_extensions:            # 排除的文件类型
      - .txt
      - .log

# 移动策略
  move_strategy:
    rapid_files_dir: "./rapid"
    non_rapid_files_dir: "./non_rapid"
    keep_non_rapid_in_place: false # false=移动所有文件
    create_subdirs: true           # 保持目录结构

# 重新检测
recheck:
  enabled: true
  recheck_interval: 86400          # 检测间隔（秒，24小时）
  max_recheck_times: 10            # 最大检测次数
```

---

## 📂 项目结构

```
AW115MST/
├── input/          # 📥 待检测文件目录
├── rapid/          # ✅ 可秒传文件输出
├── non_rapid/      # ❌ 不可秒传文件输出
├── config/         # ⚙️  配置文件
│   ├── config.yaml
│   └── 115-cookies.txt
├── modules/        # 🔧 核心模块
│   ├── config_manager.py
│   ├── controller.py
│   ├── file_handler.py
│   ├── logger.py
│   └── p115_client.py
├── gui/            # 🖥️  GUI 界面
├── docker/         # 🐳 Docker 配置
├── logs/           # 📊 日志和报告
├── main_cli.py     # 🚀 CLI 主程序
├── main_gui.py     # 🖼️  GUI 主程序
└── README.md       # 📖 项目文档
```

---

## ❓ 常见问题

<details>
<summary><b>Q: 文件会被删除吗？</b></summary>

不会。文件只是被移动到 `rapid/` 或 `non_rapid/` 目录，不会被删除。
</details>

<details>
<summary><b>Q: 可以撤销移动操作吗？</b></summary>

可以。文件只是移动了位置，手动移回即可。日志中有完整的移动记录。
</details>

<details>
<summary><b>Q: 为什么有些文件检测失败？</b></summary>

可能原因：
- 文件被其他程序占用
- 网络连接问题
- Cookies 已过期（重新获取即可）
</details>

<details>
<summary><b>Q: 支持哪些文件类型？</b></summary>

默认支持所有文件类型（除了 .txt、.log）。可在 `config.yaml` 中自定义过滤规则。
</details>

<details>
<summary><b>Q: 重新检测的间隔时间可以修改吗？</b></summary>

可以。在 `config.yaml` 中修改 `recheck.recheck_interval` 参数（单位：秒）。
</details>

---

## 🐳 Docker 部署

### 快速开始

```bash
# 1. 拉取镜像
docker pull awdress/aw115mst:latest

# 2. 进入 Docker 目录
cd docker

# 3. 创建数据目录
mkdir -p data
touch data/checkpoint.json data/recheck.json

# 4. 复制配置文件
cp ../config/config.yaml data/config/
cp ../config/115-cookies.txt data/config/

# 5. 运行检测
docker-compose run --rm aw115mst python main_cli.py
```

### 常用命令

```bash
# 检测并分类
docker-compose run --rm aw115mst python main_cli.py

# 仅检查不移动
docker-compose run --rm aw115mst python main_cli.py --check-only

# 重新检测
docker-compose run --rm aw115mst python main_cli.py --recheck

# 查看帮助
docker-compose run --rm aw115mst python main_cli.py --help
```

### 定时任务

```bash
# 添加到 crontab
crontab -e

# 每天凌晨 2 点检测新文件
0 2 * * * cd /path/to/AW115MST/docker && docker-compose run --rm aw115mst python main_cli.py

# 每天凌晨 3 点重新检测
0 3 * * * cd /path/to/AW115MST/docker && docker-compose run --rm aw115mst python main_cli.py --recheck
```

详细说明请查看 [docker/README.md](docker/README.md)

---

## 📊 使用示例

### 示例 1：批量检测电影文件

```bash
# 1. 将电影文件放入 input
cp ~/Downloads/Movies/* input/

# 2. 运行检测
python main_cli.py

# 3. 结果
# rapid/ 中的文件可以快速秒传到 115 网盘
# non_rapid/ 中的文件需要正常上传
```

### 示例 2：定期重新检测

```bash
# 首次检测
python main_cli.py

# 24 小时后重新检测
python main_cli.py --recheck

# 查看变化
ls rapid/      # 可能有新增的可秒传文件
```

---

## 🛠️ 技术栈

- **Python 3.13+** - 核心语言
- **p115client** - 115 网盘 API
- **PyQt6** - GUI 界面
- **PyYAML** - 配置管理
- **tqdm** - 进度条显示

---

## 📝 更新日志

### v1.0.0 (2026-01-14)
- ✨ 初始版本发布
- ✅ 支持秒传检测和自动分类
- 🔄 支持重新检测功能
- 📊 支持详细日志和 CSV 报告
- 🐳 支持 Docker 部署

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## ⭐ Star History

如果这个项目对你有帮助，请给个 Star ⭐️

---

<div align="center">

**Made with ❤️ by AW**

[⬆ 回到顶部](#-aw115mst)

</div>
