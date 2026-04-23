# 财智猫理财平台后端

> **WealthWhisker Backend API** - 多资产理财决策与咨询平台

## 项目简介

财智猫(WealthWhisker)是一个多资产理财决策平台，让用户在同一个平台比较资产、验证策略、低风险试错。

### 核心功能

- **多资产决策看板** - 黄金、基金、股票、加密货币统一观察框架
- **策略回测** - 支持4种规则型策略模板（均线突破、动量轮动、定投再平衡、风险平价）
- **模拟交易** - 无需真实资金的投资体验
- **研究结论卡片** - 可解释、可回测的研究结论展示
- **模型动态校准** - AI预测模型的持续学习与优化
- **招财猫成就系统** - 游戏化的用户激励机制

## 技术栈

| 层级 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| Web框架 | FastAPI |
| ORM | SQLAlchemy 2.0 |
| 数据验证 | Pydantic v2 |
| 数据库 | PostgreSQL + TimescaleDB |
| 缓存 | Redis |
| 任务队列 | Celery |
| 容器化 | Docker + Docker Compose |

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd wealth-whisker-backend
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库连接等参数
```

### 3. 启动 Docker 环境

```bash
docker-compose up -d
```

这将启动以下服务：
- PostgreSQL (TimescaleDB)
- Redis
- RabbitMQ
- FastAPI 应用
- Celery Worker
- Celery Beat

### 4. 运行数据库迁移

```bash
# 在容器内执行
docker-compose exec api alembic upgrade head

# 或在本地执行（需要安装依赖）
alembic upgrade head
```

### 5. 访问 API

- API 文档: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- 健康检查: http://localhost:8000/health

## 项目结构

```
wealth-whisker-backend/
├── app/
│   ├── api/v1/               # API路由
│   ├── core/                 # 核心模块（配置、安全、异常）
│   ├── models/               # SQLAlchemy 数据模型
│   ├── schemas/              # Pydantic 模型
│   ├── services/             # 业务逻辑服务
│   ├── tasks/                # Celery 异步任务
│   ├── data/                 # 数据处理模块
│   ├── utils/                # 工具函数
│   └── main.py               # FastAPI 应用入口
├── migrations/               # Alembic 数据库迁移
├── docker/                   # Docker 配置
├── tests/                    # 测试文件
├── requirements.txt          # Python 依赖
├── docker-compose.yml        # Docker Compose 配置
├── alembic.ini               # Alembic 配置
├── pyproject.toml            # 项目配置
└── README.md                 # 项目文档
```

## 开发指南

### 安装开发依赖

```bash
pip install -r requirements.txt
```

### 运行开发服务器

```bash
uvicorn app.main:app --reload --port 8000
```

### 运行测试

```bash
pytest tests/ -v --cov=app
```

### 代码风格检查

```bash
black app/ tests/
isort app/ tests/
flake8 app/ tests/
mypy app/
```

## API 模块

### 认证模块 `/api/v1/auth`
- 用户注册、登录、Token刷新

### 用户模块 `/api/v1/users`
- 用户信息管理、风险偏好设置

### 资产模块 `/api/v1/assets`
- 资产列表、详情、K线数据、决策看板

### 策略模块 `/api/v1/strategies`
- 策略模板、用户策略配置

### 回测模块 `/api/v1/backtest`
- 回测任务创建、状态查询、结果获取

### 模拟交易模块 `/api/v1/paper-trading`
- 模拟账户、持仓、订单、交易记录

### 研究模块 `/api/v1/research`
- 研究结论卡片、模型预测、校准日志

### 成就模块 `/api/v1/achievements`
- 成就列表、用户成就解锁

## 数据模型

### 核心表结构

- `users` - 用户信息
- `assets` - 资产元信息
- `ohlcv` - K线数据（TimescaleDB）
- `strategy_templates` - 策略模板
- `user_strategies` - 用户策略配置
- `backtest_jobs` - 回测任务
- `paper_accounts` - 模拟账户
- `positions` - 持仓
- `orders` - 订单
- `transactions` - 交易记录
- `research_cards` - 研究结论
- `model_predictions` - 模型预测
- `model_calibration_logs` - 校准日志

## 风险提示

本平台定位为**研究工具**，不提供任何投资建议。详见免责声明。

## 许可证

MIT License