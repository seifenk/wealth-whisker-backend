# 生产环境部署文档

## 📋 目录

- [部署前准备](#部署前准备)
- [快速部署](#快速部署)
- [详细步骤](#详细步骤)
- [配置说明](#配置说明)
- [运维管理](#运维管理)
- [故障排查](#故障排查)
- [安全加固](#安全加固)

---

## 部署前准备

### 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|---------|---------|
| **操作系统** | Linux (Ubuntu 20.04+) | Ubuntu 22.04 LTS |
| **CPU** | 2核 | 4核+ |
| **内存** | 4GB | 8GB+ |
| **磁盘** | 20GB | 50GB+ SSD |
| **Docker** | 20.10+ | 24.0+ |
| **Docker Compose** | 2.0+ | 2.20+ |

---

### 必备工具

```bash
# 检查Docker版本
docker --version
# 输出：Docker version 24.0.0 或更高

# 检查Docker Compose版本
docker-compose --version
# 输出：Docker Compose version v2.20.0 或更高
```

---

## 快速部署（5分钟）

### 一键部署脚本

```bash
# 1. 克隆代码
git clone <repository-url>
cd wealth-whisker-backend

# 2. 准备配置
cp .env.prod.example .env.prod

# 3. 编辑配置（必须修改）
vim .env.prod
# 修改：SECRET_KEY、POSTGRES_PASSWORD、API密钥等

# 4. 构建镜像
docker build -f docker/Dockerfile.prod -t wealthwhisker-app:v1.0.0 .

# 5. 启动服务
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 6. 验证部署
curl http://localhost:8000/health
```

---

## 详细步骤

### Step 1: 准备配置文件

#### 1.1 创建生产环境变量

```bash
# 复制模板
cp .env.prod.example .env.prod

# 编辑配置
vim .env.prod
```

#### 1.2 必须修改的配置项

```bash
# 生成强随机密钥（SECRET_KEY）
python -c "import secrets; print(secrets.token_urlsafe(32))"
# 输出示例：xK9mP2vR8nL3qW7jH5tY6cF4bN1dS0aE

# 生成数据库密码（POSTGRES_PASSWORD）
python -c "import secrets; print(secrets.token_urlsafe(16))"
# 输出示例：aB3cD5eF7gH9iJ1k

# 编辑.env.prod，填入生成的密钥
SECRET_KEY=xK9mP2vR8nL3qW7jH5tY6cF4bN1dS0aE
POSTGRES_PASSWORD=aB3cD5eF7gH9iJ1k
```

#### 1.3 配置真实API密钥

```bash
# OKX API（必须填入真实密钥）
OKX_API_KEY=your-real-okx-api-key
OKX_API_SECRET=your-real-okx-secret
OKX_API_PASSPHRASE=your-real-passphrase

# LLM API（必须填入真实密钥）
LLM_API_KEY=your-real-llm-api-key
```

---

### Step 2: 构建生产镜像

#### 2.1 使用生产Dockerfile构建

```bash
# 设置版本号
export APP_VERSION=v1.0.0

# 构建镜像（多阶段构建，优化大小）
docker build -f docker/Dockerfile.prod -t wealthwhisker-app:${APP_VERSION} .

# 查看镜像大小
docker images wealthwhisker-app:${APP_VERSION}
# 预期：约200-300MB（优化后）
```

#### 2.2 验证镜像内容

```bash
# 检查镜像包含的文件
docker run --rm wealthwhisker-app:${APP_VERSION} ls -la /app

# 预期输出：
# drwxr-xr-x  appuser appuser 4.0K  app/
# drwxr-xr-x  appuser appuser 4.0K  migrations/
# -rw-r--r--  appuser appuser  512  alembic.ini
```

---

### Step 3: 初始化数据库

#### 3.1 启动数据库服务

```bash
# 仅启动数据库和Redis
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d postgres redis

# 等待数据库就绪（约10秒）
docker-compose -f docker-compose.prod.yml logs postgres | grep "ready to accept connections"
```

#### 3.2 运行数据库迁移

```bash
# 方式1：在临时容器中运行迁移
docker run --rm \
    --network wealthwhisker-network \
    -e DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB} \
    wealthwhisker-app:${APP_VERSION} \
    alembic upgrade head

# 方式2：使用专门的迁移容器
docker-compose -f docker-compose.prod.yml --env-file .env.prod run --rm api alembic upgrade head
```

---

### Step 4: 启动全部服务

```bash
# 启动所有服务
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 查看服务状态
docker-compose -f docker-compose.prod.yml ps

# 预期输出：
# NAME                          STATUS    PORTS
# wealthwhisker-api-prod        running   0.0.0.0:8000->8000/tcp
# wealthwhisker-postgres-prod   running   5432/tcp (内部)
# wealthwhisker-redis-prod      running   6379/tcp (内部)
# wealthwhisker-celery-worker   running
# wealthwhisker-celery-beat     running
```

---

### Step 5: 验证部署

#### 5.1 健康检查

```bash
# API健康检查
curl -f http://localhost:8000/health
# 预期输出：{"status": "healthy", ...}

# 数据库连接检查
curl http://localhost:8000/api/v1/assets | jq '.data[0].symbol'
# 预期输出：BTC、ETH等资产数据
```

#### 5.2 日志检查

```bash
# 查看API日志
docker-compose -f docker-compose.prod.yml logs api --tail 100

# 查看Celery Worker日志
docker-compose -f docker-compose.prod.yml logs celery-worker --tail 50

# 确认无ERROR日志
docker-compose -f docker-compose.prod.yml logs | grep -i error
# 预期：无输出或仅警告级别日志
```

---

## 配置说明

### 生产配置对比开发配置

| 配置项 | 开发环境 | 生产环境 | 说明 |
|--------|---------|---------|------|
| **Compose文件** | docker-compose.yml | docker-compose.prod.yml | 独立配置文件 |
| **环境变量** | .env | .env.prod | 生产环境变量 |
| **镜像构建** | docker/Dockerfile | docker/Dockerfile.prod | 多阶段优化构建 |
| **代码位置** | 挂载本地 | 打包到镜像 | 镜像自包含 |
| **启动命令** | --reload | --workers 4 | 多进程并发 |
| **资源限制** | 无 | CPU/内存限制 | 防止资源耗尽 |
| **重启策略** | 无 | unless-stopped | 自动恢复 |
| **日志限制** | 无 | max-size: 50m | 防止磁盘占满 |
| **健康检查** | 部分 | 全部服务 | 自动监控 |
| **镜像版本** | :latest | :v1.0.0 | 固定版本 |
| **端口暴露** | 全部 | 仅API端口 | 安全隔离 |
| **DEBUG模式** | true | false | 关闭调试 |

---

### 资源配置建议

#### 小型部署（单服务器）

```yaml
# docker-compose.prod.yml
api:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '1'
        memory: 1G

postgres:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
```

#### 中型部署（多服务器）

```yaml
# 使用Docker Swarm或Kubernetes
api:
  deploy:
    replicas: 3
    resources:
      limits:
        cpus: '4'
        memory: 4G
```

---

## 运维管理

### 服务管理命令

```bash
# 查看服务状态
docker-compose -f docker-compose.prod.yml ps

# 重启单个服务
docker-compose -f docker-compose.prod.yml restart api

# 重启全部服务
docker-compose -f docker-compose.prod.yml restart

# 停止服务（保留数据）
docker-compose -f docker-compose.prod.yml stop

# 停止并删除容器（保留volume数据）
docker-compose -f docker-compose.prod.yml down

# 完全清理（包括数据，危险操作！）
docker-compose -f docker-compose.prod.yml down -v
```

---

### 日志管理

```bash
# 实时查看日志
docker-compose -f docker-compose.prod.yml logs -f api

# 查看最近100行日志
docker-compose -f docker-compose.prod.yml logs --tail 100 api

# 搜索错误日志
docker-compose -f docker-compose.prod.yml logs | grep -i error

# 导出日志到文件
docker-compose -f docker-compose.prod.yml logs > logs_$(date +%Y%m%d).txt
```

---

### 监控资源使用

```bash
# 实时监控容器资源
docker stats wealthwhisker-api-prod

# 输出示例：
# CONTAINER          CPU %  MEM USAGE / LIMIT  NET I/O
# wealthwhisker-api  5.2%   512MiB / 4GiB      10MB / 5MB

# 查看所有容器资源
docker-compose -f docker-compose.prod.yml top
```

---

### 数据备份

#### PostgreSQL备份

```bash
# 手动备份
docker-compose -f docker-compose.prod.yml exec -T postgres \
    pg_dump -U postgres wealthwhisker | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# 自动备份脚本（cron）
#!/bin/bash
# /etc/cron.daily/backup-wealthwhisker
docker-compose -f docker-compose.prod.yml exec -T postgres \
    pg_dump -U postgres wealthwhisker | gzip > /backups/db_$(date +%Y%m%d).sql.gz

# 保留最近7天备份
find /backups -name "db_*.sql.gz" -mtime +7 -delete
```

#### Volume备份

```bash
# 备份PostgreSQL数据卷
docker run --rm \
    -v wealthwhisker_postgres_data:/data \
    -v $(pwd)/backups:/backup \
    alpine tar czf /backup/postgres_$(date +%Y%m%d).tar.gz /data

# 备份Redis数据卷
docker run --rm \
    -v wealthwhisker_redis_data:/data \
    -v $(pwd)/backups:/backup \
    alpine tar czf /backup/redis_$(date +%Y%m%d).tar.gz /data
```

---

### 版本更新

#### 安全更新流程

```bash
# 1. 备份数据
docker-compose -f docker-compose.prod.yml exec -T postgres \
    pg_dump -U postgres wealthwhisker > backup_before_update.sql

# 2. 构建新版本镜像
docker build -f docker/Dockerfile.prod -t wealthwhisker-app:v1.0.1 .

# 3. 更新版本号
vim .env.prod
# APP_VERSION=v1.0.1

# 4. 重新部署（自动滚动更新）
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 5. 验证新版本
curl http://localhost:8000/health
docker-compose -f docker-compose.prod.yml logs api --tail 50

# 6. 如果有问题，快速回滚
vim .env.prod
# APP_VERSION=v1.0.0
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

---

## 故障排查

### 常见问题

#### 问题1: 容器启动失败

```bash
# 查看容器状态
docker-compose -f docker-compose.prod.yml ps

# 查看错误日志
docker-compose -f docker-compose.prod.yml logs api

# 常见原因：
# - 数据库未就绪：等待postgres健康检查通过
# - 配置错误：检查.env.prod配置项
# - 镜像问题：重新构建镜像
```

#### 问题2: API无法访问

```bash
# 检查端口占用
netstat -tuln | grep 8000

# 检查容器网络
docker network ls
docker network inspect wealthwhisker-network

# 检查防火墙
sudo ufw status
sudo ufw allow 8000/tcp
```

#### 问题3: 数据库连接失败

```bash
# 检查数据库状态
docker-compose -f docker-compose.prod.yml logs postgres

# 测试数据库连接
docker-compose -f docker-compose.prod.yml exec postgres \
    psql -U postgres -d wealthwhisker -c "SELECT 1;"

# 检查密码配置
docker-compose -f docker-compose.prod.yml exec api printenv DATABASE_URL
```

#### 问题4: Celery任务不执行

```bash
# 检查Celery Worker状态
docker-compose -f docker-compose.prod.yml logs celery-worker

# 检查Redis连接
docker-compose -f docker-compose.prod.yml exec redis redis-cli ping

# 手动触发任务（测试）
docker-compose -f docker-compose.prod.yml exec api \
    python -c "from app.tasks.data_sync import sync_crypto_data_task; sync_crypto_data_task.delay()"
```

---

## 安全加固

### 网络安全

```bash
# 1. 限制API端口访问（仅内部或VPN）
sudo ufw default deny incoming
sudo ufw allow from 10.0.0.0/8 to any port 8000  # 仅内网访问

# 2. 使用Nginx反向代理（HTTPS）
# /etc/nginx/sites-available/wealthwhisker
server {
    listen 443 ssl http2;
    server_name api.your-domain.com;
    
    ssl_certificate /etc/ssl/certs/your-domain.crt;
    ssl_certificate_key /etc/ssl/private/your-domain.key;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# 3. 启用Nginx
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl start nginx
```

---

### 密钥管理

```bash
# 1. 定期更换密钥（建议每季度）
# 生成新密钥
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 更新.env.prod
vim .env.prod
# SECRET_KEY=<新密钥>

# 重启服务
docker-compose -f docker-compose.prod.yml restart api

# 2. 使用密钥管理服务（生产推荐）
# - AWS Secrets Manager
# - HashiCorp Vault
# - Azure Key Vault
```

---

### 审计日志

```bash
# 1. 启用详细日志
vim .env.prod
# LOG_LEVEL=INFO

# 2. 配置日志收集
# 使用ELK Stack或Loki收集日志

# 3. 定期审计
# 检查访问日志
docker-compose -f docker-compose.prod.yml logs api | grep "POST\|PUT\|DELETE"

# 检查异常访问
docker-compose -f docker-compose.prod.yml logs api | grep "401\|403\|500"
```

---

## 部署检查清单

### ✅ 部署前检查

- [ ] **系统要求**：CPU/内存/磁盘满足要求
- [ ] **Docker版本**：Docker 24.0+ / Compose 2.20+
- [ ] **配置文件**：.env.prod已创建并修改必要配置
- [ ] **密钥生成**：SECRET_KEY、POSTGRES_PASSWORD已生成强密钥
- [ ] **API密钥**：OKX、LLM等真实密钥已配置
- [ ] **域名配置**：CORS_ORIGINS已配置生产域名
- [ ] **镜像构建**：使用Dockerfile.prod构建镜像

---

### ✅ 部署后验证

- [ ] **服务状态**：所有容器running状态
- [ ] **健康检查**：curl /health返回healthy
- [ ] **API访问**：可正常访问API接口
- [ ] **数据同步**：Celery任务正常执行
- [ ] **日志检查**：无ERROR级别日志
- [ ] **资源监控**：CPU/内存使用正常
- [ ] **数据备份**：备份脚本已配置

---

### ✅ 安全检查

- [ ] **端口暴露**：仅API端口对外暴露
- [ ] **DEBUG关闭**：DEBUG=false已确认
- [ ] **密钥强度**：SECRET_KEY长度>=32字节
- [ ] **HTTPS配置**：Nginx反向代理已配置SSL
- [ ] **防火墙**：UFW已配置端口限制
- [ ] **日志限制**：max-size已配置防止磁盘占满
- [ ] **资源限制**：CPU/内存limits已配置

---

## 联系支持

部署遇到问题？按以下顺序排查：

1. **查看日志**：`docker-compose logs`
2. **检查配置**：验证.env.prod配置项
3. **重启服务**：`docker-compose restart`
4. **重新构建**：`docker build`重建镜像
5. **查看文档**：参考本文档故障排查章节

---

## 附录

### Docker Compose常用命令速查

| 命令 | 说明 |
|------|------|
| `docker-compose up -d` | 启动所有服务 |
| `docker-compose down` | 停止并删除容器 |
| `docker-compose ps` | 查看服务状态 |
| `docker-compose logs -f` | 实时查看日志 |
| `docker-compose restart` | 重启所有服务 |
| `docker-compose exec <service> bash` | 进入容器 |
| `docker-compose build` | 重新构建镜像 |
| `docker-compose top` | 查看容器资源使用 |

---

### 配置文件位置

```
wealth-whisker-backend/
├── docker-compose.prod.yml    # 生产Docker Compose配置
├── .env.prod                   # 生产环境变量（不提交git）
├── .env.prod.example           # 生产环境变量模板
├── docker/
│   ├── Dockerfile.prod         # 生产Dockerfile
│   └── init-db.sql            # 数据库初始化脚本
└── docs/
    └── DEPLOYMENT.md           # 本部署文档
```

---

**部署成功标志**：所有容器running，健康检查通过，API可访问，Celery任务正常执行！🎉