# 研究结论模块自动化流程使用说明

## 概述

研究结论模块已改为后台自动化任务系统，前端只需查询结果展示，无需手动触发生成流程。

## 架构变更

### 前端查询接口（保留）

| 接口 | 说明 | 游客可访问 |
|------|------|-----------|
| `GET /api/v1/research/cards` | 查询研究结论列表 | ✅ |
| `GET /api/v1/research/cards/{card_id}` | 查询研究结论详情 | ✅ |
| `GET /api/v1/research/predictions` | 查询预测列表 | ✅ |
| `GET /api/v1/research/predictions/{asset_id}/accuracy` | 查询预测准确性 | ✅ |
| `GET /api/v1/research/calibration-logs` | 查询校准日志 | ✅ |
| `GET /api/v1/research/model-versions` | 查询模型版本 | ✅ |
| `GET /api/v1/research/disclaimer` | 查询免责声明 | ✅ |
| `GET /api/v1/research/analysis/{asset_id}` | 查询综合分析 | ✅ |

### 后台自动化任务（新增）

| 任务 | 执行频率 | 说明 |
|------|---------|------|
| 加密货币研究生成 | 每4小时 | 0:00, 4:00, 8:00, 12:00, 16:00, 20:00 UTC |
| 加密货币预测创建 | 每4小时 | 研究生成后15分钟 |
| 股票研究生成 | 每日17:00 UTC | 美股收盘后，T+1机制 |
| 股票预测创建 | 每日17:15 UTC | 研究生成后15分钟 |
| 基金研究生成 | 每日07:30 UTC | 北京时间15:30，A股收盘后 |
| 基金预测创建 | 每日07:45 UTC | 研究生成后15分钟 |
| 黄金研究生成 | 每日17:05 UTC | 黄金市场收盘后 |
| 黄金预测创建 | 每日17:20 UTC | 研究生成后15分钟 |
| 实际值更新 | 每日00:30 UTC | 检查所有到期预测 |
| 自动校准 | 每日01:00 UTC | 处理触发校准的预测 |

## 启动方式

### 1. 启动Celery Worker

```bash
celery -A app.core.celery_app worker --loglevel=info
```

### 2. 启动Celery Beat调度器

```bash
celery -A app.core.celery_app beat --loglevel=info
```

### 3. 可选：启动Flower监控面板

```bash
pip install flower
celery -A app.core.celery_app flower --port=5555
# 访问 http://localhost:5555 查看任务状态
```

## 手动触发测试

如果需要手动测试任务，可以使用Python环境：

```python
from app.tasks.research_tasks import generate_research_cards_task

# 测试加密货币研究生成
result = generate_research_cards_task.delay(asset_type="crypto")
print(result.get())  # 查看执行结果

# 测试所有资产
result = generate_research_cards_task.delay()
print(result.get())

# 测试预测创建
from app.tasks.research_tasks import create_model_predictions_task
result = create_model_predictions_task.delay(asset_type="crypto")
print(result.get())

# 测试实际值更新
from app.tasks.research_tasks import update_prediction_actuals_task
result = update_prediction_actuals_task.delay()
print(result.get())

# 测试自动校准
from app.tasks.research_tasks import auto_calibrate_models_task
result = auto_calibrate_models_task.delay()
print(result.get())
```

## 验证流程

运行验证脚本：

```bash
python scripts/verify_research_automation.py
```

验证内容：
- ✓ Celery定时调度配置
- ✓ 研究卡片自动生成
- ✓ 预测自动创建
- ✓ 实际值自动更新
- ✓ 校准自动触发
- ✓ API接口变更

## 数据库监控

查询最近的研究卡片：

```sql
SELECT id, asset_id, title, confidence_score, created_at
FROM research_cards
ORDER BY created_at DESC
LIMIT 10;
```

查询预测记录：

```sql
SELECT id, asset_id, predicted_value, actual_value, deviation, calibration_triggered
FROM model_predictions
WHERE target_date <= CURRENT_DATE
ORDER BY predicted_at DESC;
```

查询校准日志：

```sql
SELECT id, asset_id, calibration_type, before_params, after_params, triggered_at
FROM model_calibration_logs
ORDER BY triggered_at DESC
LIMIT 10;
```

## 偏差阈值机制

| 资产类型 | 偏差阈值 | 说明 |
|---------|---------|------|
| 加密货币 | 5% | DEVIATION_THRESHOLD_CRYPTO = 0.05 |
| 股票 | 3% | DEVIATION_THRESHOLD_STOCK = 0.03 |

触发逻辑：
- 预测到期后自动获取当前价格作为实际值
- 计算偏差：`|actual - predicted| / predicted * 100`
- 偏差超过阈值 → 标记 `calibration_triggered = True`
- 每日凌晨自动执行校准

## 前端集成建议

### 1. 研究结论展示

```javascript
// 获取研究结论列表
const response = await fetch('/api/v1/research/cards');
const data = response.json();

// 展示卡片
data.data.items.forEach(card => {
  console.log(`${card.title} - 置信度: ${card.confidence_score}`);
});
```

### 2. 预测准确性展示

```javascript
// 获取预测准确性
const response = await fetch(`/api/v1/research/predictions/${assetId}/accuracy?days=30`);
const data = response.json();

// 展示准确性统计
console.log(`准确率: ${data.data.accuracy_rate}%`);
console.log(`平均偏差: ${data.data.avg_deviation}%`);
```

### 3. 校准日志展示

```javascript
// 获取校准日志
const response = await fetch('/api/v1/research/calibration-logs');
const data = response.json();

// 展示校准历史
data.data.items.forEach(log => {
  console.log(`校准类型: ${log.calibration_type}, 时间: ${log.triggered_at}`);
});
```

## 注意事项

1. **游客访问**：所有查询接口均支持游客访问，无需登录
2. **自动化执行**：后台任务自动执行，前端无需触发
3. **数据时效性**：
   - 加密货币：每4小时更新
   - 股票/基金：每日收盘后更新（T+1）
   - 黄金：每日更新
4. **免责声明**：所有预测页面必须展示免责声明

## 合规要求

- 预测图表显著位置增加声明："本预测基于算法模型动态生成，不构成任何实质性投资建议。"
- 话术框架：
  - ✅ 推荐："基于最新市场数据，模型已更新预测结果"
  - ❌ 避免："之前的预测有误，现已纠正"

## 问题排查

如果自动化任务未执行：

1. 检查Celery Worker和Beat是否启动
2. 检查数据库连接是否正常
3. 检查Redis连接是否正常
4. 查看Celery日志是否有错误
5. 使用Flower监控面板查看任务状态

## 更多信息

- PRD文档：`docs/PRD.md` 第5.6节"模型动态校准机制"
- 开发计划：`docs/PLAN.md` Phase 5
- 实施计划：`/Users/sun/.claude/plans/encapsulated-gathering-emerson.md`