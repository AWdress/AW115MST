# GitHub Actions 设置指南

## 配置 Docker Hub Secrets

为了让 GitHub Actions 能够推送镜像到 Docker Hub，需要在 GitHub 仓库中配置以下 Secrets：

### 1. 获取 Docker Hub 访问令牌

1. 登录 [Docker Hub](https://hub.docker.com/)
2. 点击右上角头像 → **Account Settings**
3. 选择 **Security** → **New Access Token**
4. 输入 Token 名称（如：`github-actions`）
5. 选择权限：**Read, Write, Delete**
6. 点击 **Generate**
7. **复制生成的 Token**（只显示一次）

### 2. 在 GitHub 仓库中添加 Secrets

1. 打开仓库页面：https://github.com/AWdress/AW115MST
2. 点击 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**
4. 添加以下两个 Secrets：

#### DOCKER_USERNAME
- Name: `DOCKER_USERNAME`
- Value: 你的 Docker Hub 用户名（如：`awdress`）

#### DOCKER_PASSWORD
- Name: `DOCKER_PASSWORD`
- Value: 刚才生成的 Access Token

### 3. 验证配置

配置完成后，推送代码到 `main` 分支会自动触发构建：

```bash
git add .
git commit -m "chore: 添加 GitHub Actions 配置"
git push
```

然后在 GitHub 仓库的 **Actions** 标签页查看构建状态。

## Workflows 说明

### docker-build.yml
自动构建并推送 Docker 镜像到 Docker Hub

**触发条件：**
- 推送到 `main` 分支
- 创建 tag（如 `v1.0.0`）
- Pull Request
- 手动触发

**功能：**
- 构建多平台镜像（amd64, arm64）
- 自动打标签（latest, 版本号）
- 更新 Docker Hub 描述

### release.yml
自动创建 GitHub Release

**触发条件：**
- 创建 tag（如 `v1.0.0`）

**功能：**
- 自动生成 Release Notes
- 创建 GitHub Release

## 发布新版本

```bash
# 1. 更新版本号（在 main_cli.py 中）
# version='AW115MST v1.0.0'

# 2. 提交更改
git add .
git commit -m "chore: bump version to v1.0.0"
git push

# 3. 创建并推送 tag
git tag v1.0.0
git push origin v1.0.0
```

这会自动：
1. 构建 Docker 镜像并推送到 Docker Hub
2. 创建 GitHub Release

## 手动触发构建

1. 打开仓库的 **Actions** 标签页
2. 选择 **Build and Push Docker Image**
3. 点击 **Run workflow**
4. 选择分支
5. 点击 **Run workflow** 按钮

## 查看构建状态

- GitHub Actions: https://github.com/AWdress/AW115MST/actions
- Docker Hub: https://hub.docker.com/r/awdress/aw115mst

## 故障排查

### 构建失败

1. 检查 Secrets 是否正确配置
2. 查看 Actions 日志中的错误信息
3. 确认 Docker Hub Token 权限足够

### 镜像推送失败

1. 确认 Docker Hub 仓库存在（首次需要手动创建）
2. 检查 Token 是否过期
3. 确认网络连接正常

## 注意事项

1. **Token 安全**：不要在代码中硬编码 Token
2. **权限控制**：Token 只给必要的权限
3. **定期更新**：建议定期更换 Access Token
4. **多平台构建**：首次构建可能较慢（需要构建 amd64 和 arm64）
