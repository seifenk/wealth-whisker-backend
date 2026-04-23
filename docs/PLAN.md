# 财智猫理财平台后端开发计划

## 进度概览

| Phase | 状态 | 完成度 |
|-------|------|--------|
| Phase 1: 基础设施搭建 | ✅ 已完成 | 90% |
| Phase 2: 用户认证与资产管理 | 🔄 进行中 | 60% |
| Phase 3: 决策看板与策略回测 | ⏳ 待开始 | 0% |
| Phase 4: 模拟交易系统 | ⏳ 待开始 | 0% |
| Phase 5: 研究结论与模型校准 | ⏳ 待开始 | 0% |
| Phase 6: 测试与文档 | ⏳ 待开始 | 10% |

**当前阶段**：Phase 2 - 用户认证与资产管理

**整体进度**：约 20%

---

## Context

**项目背景**：财智猫(WealthWhisker)是一个多资产理财决策平台，让用户在同一个平台比较资产、验证策略、低风险试错。产品特色包括招财猫IP形象和模型动态校准机制。

**当前状态**：项目处于初始阶段，仅有PRD文档，需要从零搭建后端。

**目标**：完成MVP版本后端开发，支持P0核心功能：多资产决策看板、策略回测、模拟交易、研究结论卡片、模型动态校准。

---

## 1. 技术栈选择

### 推荐方案：Python FastAPI

| 层级 | 技术 | 理由 |
|------|------|------|
| **语言** | Python 3.11+ | 金融计算生态(pandas/numpy)、AI/ML原生支持 |
| **Web框架** | FastAPI | 异步高性能、自动API文档、类型安全 |
| **ORM** | SQLAlchemy 2.0 | 异步支持、成熟稳定 |
| **数据验证** | Pydantic v2 | FastAPI原生集成、性能优秀 |
| **数据库** | PostgreSQL + TimescaleDB | 关系型+时序数据(K线存储) |
| **缓存** | Redis | 会话管理、行情缓存、Celery broker |
| **任务队列** | Celery | 异步回测计算、模型校准、数据同步 |
| **容器化** | Docker + Compose | 开发环境一致性 |

### 技术栈选择理由

1. **金融计算核心**：回测引擎需要pandas/numpy/scipy，Python是最佳选择
2. **AI能力内置**：模型动态校准需要scikit-learn，Python原生支持
3. **快速迭代**：FastAPI开发效率极高，适合MVP阶段
4. **生态完整**：量化、回测、数据处理库丰富

---

## 2. 项目结构

```
wealth-whisker-backend/
├── app/
│   ├── api/v1/               # API路由
│   │   ├── auth.py           # 认证授权
│   │   ├── users.py          # 用户管理
│   │   ├── assets.py         # 资产数据
│   │   ├── strategies.py     # 策略管理
│   │   ├── backtest.py       # 回测服务
│   │   ├── paper_trading.py  # 模拟交易
│   │   ├── research.py       # 研究结论
│   │   ├── achievements.py   # 成就系统
│   │   └── system.py         # 系统配置
│   ├── core/                 # 核心模块
│   │   ├── config.py         # 配置管理
│   │   ├── security.py       # JWT认证
│   │   ├── exceptions.py     # 异常处理
│   │   └── middleware.py     # 中间件
│   ├── models/               # SQLAlchemy模型
│   ├── schemas/              # Pydantic模型
│   ├── services/             # 业务逻辑
│   │   ├── backtest_service.py    # 回测引擎
│   │   ├── paper_trading_service.py # 模拟交易
│   │   ├── model_calibration_service.py # 模型校准
│   │   └── achievement_service.py # 成就系统
│   ├── tasks/                # Celery异步任务
│   │   ├── data_sync.py      # 数据同步
│   │   ├── backtest_worker.py # 回测计算
│   │   ├── model_calibration.py # 模型校准
│   │   └── metrics_calculation.py # 指标计算
│   ├── data/                 # 数据处理
│   │   ├── connectors/       # 数据源连接器
│   │   └── calculators/      # 计算引擎
│   ├── utils/                # 工具函数
│   └── main.py               # 应用入口
├── migrations/               # Alembic迁移
├── tests/                    # 测试
├── docker/                   # Docker配置
├── scripts/                  # 脚本
├── alembic.ini               # Alembic配置
├── requirements.txt          # Python依赖
├── docker-compose.yml        # Docker Compose
├── .env.example              # 环境变量示例
├── pyproject.toml            # 项目配置
└── README.md                 # 项目文档
```

---

## 3. 核心数据库模型

### 用户模块
- `users` - 用户基础信息、风险偏好
- `user_settings` - 用户设置
- `achievements` - 成就定义
- `user_achievements` - 用户成就记录

### 资产模块
- `assets` - 资产元信息(黄金/基金/股票/加密货币)
- `ohlcv` - K线数据(TimescaleDB hypertable)
- `asset_metrics` - 资产指标快照

### 策略回测模块
- `strategy_templates` - 策略模板(均线突破/动量轮动/定投/风险平价)
- `user_strategies` - 用户策略配置
- `backtest_jobs` - 回测任务
- `backtest_results` - 回测结果

### 模拟交易模块
- `paper_accounts` - 模拟账户
- `positions` - 持仓
- `orders` - 订单
- `transactions` - 交易记录
- `account_snapshots` - 账户快照(收益曲线)

### 研究结论模块
- `research_cards` - 研究结论卡片
- `model_predictions` - 模型预测记录
- `model_calibration_logs` - 模型校准日志

### 合规模块
- `disclaimer_versions` - 免责声明版本
- `user_disclaimer_acceptances` - 用户确认记录
- `risk_disclosure_logs` - 风险提示展示记录

---

## 4. API路由设计

### 认证 `/api/v1/auth`
- `POST /register` - 用户注册
- `POST /login` - 用户登录
- `POST /refresh` - 刷新Token

### 用户 `/api/v1/users`
- `GET /me` - 获取用户信息
- `PUT /me` - 更新用户信息
- `PUT /me/risk-preference` - 更新风险偏好
- `GET /me/achievements` - 获取用户成就

### 资产 `/api/v1/assets`
- `GET /` - 资产列表
- `GET /{id}` - 资产详情
- `GET /{id}/ohlcv` - K线数据
- `GET /{id}/metrics` - 资产指标
- `GET /dashboard` - 决策看板数据

### 策略 `/api/v1/strategies`
- `GET /templates` - 策略模板列表
- `POST /` - 创建用户策略
- `GET /` - 用户策略列表

### 回测 `/api/v1/backtest`
- `POST /jobs` - 创建回测任务
- `GET /jobs` - 任务列表
- `GET /jobs/{id}` - 任务状态
- `GET /jobs/{id}/result` - 回测结果

### 模拟交易 `/api/v1/paper-trading`
- `POST /accounts` - 创建模拟账户
- `GET /accounts` - 账户列表
- `GET /accounts/{id}/positions` - 持仓
- `POST /accounts/{id}/orders` - 创建订单
- `GET /accounts/{id}/transactions` - 交易记录
- `GET /accounts/{id}/performance` - 收益分析

### 研究 `/api/v1/research`
- `GET /cards` - 研究结论列表
- `GET /predictions` - 模型预测
- `GET /calibration-logs` - 校准日志

---

## 5. 功能模块拆分与开发顺序

### Phase 1: 基础设施搭建 (第1-2周) ✅ 已完成

**目标**：搭建可运行的开发环境

**任务清单**：
1. 项目初始化
   - [x] ~~创建FastAPI项目结构~~
   - [x] ~~配置Python依赖管理(requirements.txt)~~
   - [x] ~~配置pyproject.toml~~
   
2. Docker环境
   - [x] ~~docker-compose.yml (PostgreSQL + TimescaleDB + Redis + RabbitMQ)~~
   - [x] ~~Dockerfile (应用镜像)~~
   
3. 数据库模型
   - [x] ~~SQLAlchemy模型定义(所有表)~~
   - [x] ~~Alembic迁移脚本~~
   - [x] ~~初始化数据(资产列表、策略模板)~~
   
4. 核心配置
   - [x] ~~config.py (环境变量、数据库连接)~~
   - [x] ~~security.py (JWT工具)~~
   - [x] ~~exceptions.py (统一异常处理)~~
   - [ ] middleware.py (请求日志、错误处理)

**交付物**：
- ✅ 可运行的Docker开发环境
- ✅ 数据库schema完整创建
- ✅ 基础配置模块可用

---

### Phase 2: 用户认证与资产管理 (第3周) 🔄 进行中

**目标**：用户可注册登录，资产数据可查询

**任务清单**：
1. 用户认证模块
   - [x] ~~用户注册API (POST /auth/register)~~
   - [x] ~~用户登录API (POST /auth/login)~~
   - [x] ~~JWT Token生成与验证~~
   - [x] ~~密码加密(bcrypt)~~
   
2. 用户管理模块
   - [x] ~~用户信息API (GET/PUT /users/me)~~
   - [x] ~~风险偏好设置API~~ (通过PUT /users/me实现)
   - [x] ~~免责声明确认流程~~
   
3. 数据源接入
   - [ ] 加密货币数据源连接器(Binance API)
   - [ ] 股票数据源连接器(Alpha Vantage/Yahoo Finance)
   - [ ] 黄金数据源连接器
   - [ ] 基金数据源连接器
   
4. 数据同步任务
   - [ ] Celery数据同步任务(tasks/data_sync.py)
   - [ ] 定时调度配置(每小时更新)
   
5. 资产数据API
   - [ ] 资产列表API (GET /assets)
   - [ ] 资产详情API (GET /assets/{id})
   - [ ] K线数据查询API (GET /assets/{id}/ohlcv)

**交付物**：
- ✅ 用户注册登录流程可用
- ⏳ 资产数据持续同步 (待实现)
- ⏳ K线数据可查询 (待实现)

---

### Phase 3: 决策看板与策略回测 (第4-5周) ⏳ 待开始

**目标**：用户可查看多资产决策看板，执行策略回测

**任务清单**：
1. 决策看板API
   - [ ] 多资产汇总API (GET /assets/dashboard)
   - [ ] 指标计算服务(涨跌幅、波动率、夏普比率)
   - [ ] 信号计算(趋势判断)
   - [ ] 风险等级计算
   
2. 策略模板系统
   - [ ] 策略模板数据定义(4种模板)
   - [ ] 策略参数校验
   - [ ] 用户策略配置API
   
3. 回测引擎核心
   - [ ] 回测任务队列(tasks/backtest_worker.py)
   - [ ] 均线突破策略实现
   - [ ] 动量轮动策略实现
   - [ ] 定投/再平衡策略实现
   - [ ] 风险平价策略实现
   
4. 回测计算服务
   - [ ] 指标计算(累计收益、年化收益、最大回撤、夏普比率、胜率)
   - [ ] 资金曲线生成
   - [ ] 结果存储
   
5. 回测API
   - [ ] 创建回测任务API (POST /backtest/jobs)
   - [ ] 查询任务状态API (GET /backtest/jobs/{id})
   - [ ] 获取回测结果API (GET /backtest/jobs/{id}/result)

**交付物**：
- ⏳ 决策看板数据API可用 (待实现)
- ⏳ 4种策略模板回测功能可用 (待实现)
- ⏳ 异步回测任务执行 (待实现)

---

### Phase 4: 模拟交易系统 (第6-7周) ⏳ 待开始

**目标**：用户可创建模拟账户并交易

**任务清单**：
1. 模拟账户管理
   - [ ] 创建模拟账户API
   - [ ] 账户资金管理
   - [ ] 账户快照定时任务
   
2. 订单与交易系统
   - [ ] 创建订单API(市价/限价)
   - [ ] 订单撮合引擎(模拟)
   - [ ] 订单状态管理
   - [ ] 交易记录管理
   
3. 持仓管理
   - [ ] 持仓更新服务
   - [ ] 实时盈亏计算
   - [ ] 持仓价格同步任务
   
4. 收益分析
   - [ ] 收益曲线生成
   - [ ] 绩效指标计算
   - [ ] 风险指标计算
   
5. 成就系统(P1)
   - [ ] 成就规则定义
   - [ ] 成就触发机制
   - [ ] 成就解锁通知

**交付物**：
- ⏳ 完整模拟交易系统可用 (待实现)
- ⏳ 支持4种资产交易 (待实现)
- ⏳ 收益分析功能可用 (待实现)

---

### Phase 5: 研究结论与模型校准 (第8周) ⏳ 待开始

**目标**：研究结论卡片和模型动态校准功能

**任务清单**：
1. 研究结论卡片
   - [ ] 结论生成服务
   - [ ] 置信度计算
   - [ ] 依据指标整理
   - [ ] 风险提示生成
   
2. 模型预测系统
   - [ ] 基础预测模型(线性回归/ARIMA)
   - [ ] 预测记录存储
   - [ ] 预测更新任务
   
3. 模型动态校准
   - [ ] 偏差检测任务
   - [ ] 校准触发逻辑(加密货币4小时/股票T+1)
   - [ ] 校准执行服务
   - [ ] 校准日志记录
   
4. 透明度展示
   - [ ] 历史准确性查询API
   - [ ] 校准日志查询API
   - [ ] 模型版本管理

**交付物**：
- ⏳ 研究结论卡片功能可用 (待实现)
- ⏳ 模型动态校准系统运行 (待实现)
- ⏳ 合规话术正确展示 (待实现)

---

### Phase 6: 测试与文档 (第9周) ⏳ 待开始

**目标**：测试覆盖率达标，文档完整

**任务清单**：
1. 单元测试
   - [ ] API测试(pytest)
   - [ ] 服务层测试
   - [ ] 覆盖率>80%
   
2. 集成测试
   - [ ] 端到端流程测试
   - [ ] 回测流程测试
   - [ ] 模拟交易流程测试
   
3. 性能测试
   - [ ] API响应时间测试
   - [ ] 回测计算性能测试
   
4. 文档完善
   - [x] ~~API文档(FastAPI自动生成)~~
   - [ ] 部署文档
   - [ ] 开发文档

**交付物**：
- ⏳ 测试覆盖率达标 (待实现)
- ✅ API文档可访问 (FastAPI自带)
- ⏳ 部署文档完整 (待实现)

---

## 6. 关键文件清单

### 核心配置
- `app/core/config.py` - 环境变量、数据库连接、API密钥
- `app/core/security.py` - JWT生成/验证、密码加密
- `app/main.py` - FastAPI应用入口、路由注册、中间件配置

### 数据模型
- `app/models/user.py` - 用户相关模型
- `app/models/asset.py` - 资产模型
- `app/models/strategy.py` - 策略与回测模型
- `app/models/paper_trading.py` - 模拟交易模型
- `app/models/research.py` - 研究结论与预测模型

### 业务服务
- `app/services/backtest_service.py` - 回测引擎核心(策略执行、指标计算)
- `app/services/paper_trading_service.py` - 模拟交易服务(订单撮合、持仓管理)
- `app/services/model_calibration_service.py` - 模型校准服务(偏差检测、模型重训练)
- `app/services/achievement_service.py` - 成就系统服务

### 异步任务
- `app/tasks/data_sync.py` - 数据同步任务(多数据源)
- `app/tasks/backtest_worker.py` - 回测计算Worker
- `app/tasks/model_calibration.py` - 模型校准任务
- `app/tasks/metrics_calculation.py` - 指标计算任务

### 数据处理
- `app/data/connectors/binance_connector.py` - Binance API连接器
- `app/data/connectors/stock_connector.py` - 股票数据连接器
- `app/data/calculators/indicator_calculator.py` - 指标计算器(均线、RSI、波动率)
- `app/data/calculators/backtest_engine.py` - 回测引擎核心逻辑

---

## 7. 验证方案

### 开发环境验证
```bash
# 1. 启动Docker环境
docker-compose up -d

# 2. 运行数据库迁移
alembic upgrade head

# 3. 启动API服务
uvicorn app.main:app --reload

# 4. 访问API文档
open http://localhost:8000/docs
```

### 功能验证流程

1. **用户注册登录**
   - POST /api/v1/auth/register
   - POST /api/v1/auth/login
   - 验证JWT Token有效

2. **资产数据查询**
   - GET /api/v1/assets (查看资产列表)
   - GET /api/v1/assets/{id}/ohlcv (查看K线数据)
   - 验证数据同步任务运行

3. **决策看板**
   - GET /api/v1/assets/dashboard
   - 验证多资产汇总、信号、风险等级

4. **策略回测**
   - POST /api/v1/backtest/jobs (创建任务)
   - GET /api/v1/backtest/jobs/{id} (查看状态)
   - GET /api/v1/backtest/jobs/{id}/result (查看结果)
   - 验证回测指标正确计算

5. **模拟交易**
   - POST /api/v1/paper-trading/accounts (创建账户)
   - POST /api/v1/paper-trading/accounts/{id}/orders (下单)
   - GET /api/v1/paper-trading/accounts/{id}/positions (查看持仓)
   - GET /api/v1/paper-trading/accounts/{id}/performance (查看收益)
   - 验证订单执行、持仓更新、盈亏计算

6. **研究结论**
   - GET /api/v1/research/cards
   - 验证置信度、依据、风险提示展示

7. **模型校准**
   - 检查Celery日志，验证校准任务执行
   - GET /api/v1/research/calibration-logs (查看校准日志)

### 测试验证
```bash
# 运行单元测试
pytest tests/unit -v --cov=app

# 运行集成测试
pytest tests/integration -v

# 检查覆盖率
pytest --cov=app --cov-report=html
```

---

## 8. 风险与应对

| 风险 | 应对策略 |
|------|----------|
| **数据源不稳定** | 多数据源备份、Redis缓存、错误监控告警 |
| **回测计算阻塞** | Celery异步队列、结果缓存、资源限制 |
| **模型预测不准** | 透明度设计、动态校准、合规免责声明 |
| **合规风险** | 全站风险提示、强制免责确认、研究工具定位 |

---

## 9. 总结

**预计工期**：9周完成MVP后端

**技术栈核心**：Python + FastAPI + PostgreSQL/TimescaleDB + Redis + Celery

**关键成功因素**：
- 金融计算生态成熟(pandas/numpy)
- AI能力内置(scikit-learn)
- 快速迭代(FastAPI开发效率)
- 合规话术正确实现(模型校准透明度)