# CAN总线新能源汽车用户画像与零部件健康监控系统

基于PySpark/PyFlink的新能源汽车CAN总线大数据分析平台

## 📋 项目概述

本项目是一个完整的新能源汽车数据分析系统，基于CAN总线数据完成用户画像构建、零部件健康监控、加速试验工况转化等任务。

### 核心功能

| 功能模块 | 描述 | 技术栈 |
|---------|------|--------|
| 用户画像 | 提取8组用户标签，识别驾驶工况 | PySpark |
| 健康监控 | 实时监控电机/电池健康状态 | PyFlink |
| 预警系统 | 温度/电压异常检测与告警 | Python |
| 工况转化 | 提取高负载/高温极端工况 | pandas |
| API服务 | RESTful数据接口 | FastAPI |
| 可视化 | 交互式数据分析界面 | Streamlit |

## 🏗️ 技术架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        CAN总线数据                               │
│                   (车速、油门、刹车、电池、电机)                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   爬虫模块    │    │ 合成数据生成  │    │  数据存储     │
│  scraper.py  │    │data_generator │    │  data/raw/    │
└───────────────┘    └───────────────┘    └───────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      特征工程与用户画像                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ 时间特征提取 │  │ 派生特征计算 │  │ 车辆聚合统计 │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ 工况识别     │  │ 聚类分析     │  │ 用户标签构建 │          │
│  │spark_features│ │              │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  健康度评分   │    │ Flink实时监控 │    │ 加速试验转化  │
│ health_score  │    │ flink_monitor │    │   accel_test  │
└───────────────┘    └───────────────┘    └───────────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        数据服务层                                │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │    FastAPI服务       │  │   Streamlit可视化    │            │
│  │   api_service.py     │  │       app.py         │            │
│  └──────────────────────┘  └──────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 项目结构

```
CAN_User_Profile_Health/
├── README.md                    # 项目说明文档
├── requirements.txt             # Python依赖清单
├── config.py                    # 项目配置文件
├── main.py                      # 一键运行入口
├── app.py                       # Streamlit可视化系统
│
├── src/
│   ├── __init__.py             # 模块初始化
│   ├── scraper.py              # 多源数据爬虫
│   ├── data_generator.py       # 新能源汽车CAN合成数据生成
│   ├── spark_features.py       # PySpark特征工程与用户画像
│   ├── flink_monitor.py        # PyFlink窗口聚合实时监控
│   ├── health_score.py         # 零部件健康度评分模型
│   ├── accel_test.py            # 加速试验工况转化
│   └── api_service.py           # FastAPI数据服务API
│
├── data/
│   ├── raw/                     # 原始CAN数据
│   │   └── can_synthetic_data_*.csv
│   └── processed/              # 处理后数据
│       ├── user_profiles.csv    # 用户画像
│       ├── health_reports.csv   # 健康报告
│       └── accelerated_test_sequence.csv  # 工况序列
│
└── output/
    ├── figures/                 # 可视化图表输出
    └── reports/                 # 分析报告
        └── analysis_report_*.txt
```

## 🔧 环境要求

- **Python**: 3.8+
- **系统**: Windows / Linux / macOS
- **内存**: 建议 8GB+
- **CPU**: 多核处理器（PySpark本地模式会利用多核）

## 📦 安装步骤

### 1. 克隆或下载项目

```bash
cd /app/data/所有对话/主对话/
git clone <repository_url> CAN_User_Profile_Health
cd CAN_User_Profile_Health
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
.\venv\Scripts\activate   # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 依赖说明

| 依赖包 | 版本 | 用途 |
|-------|------|------|
| pyspark | ≥3.3.0 | 特征工程与聚合计算（本地模式） |
| apache-flink | ≥1.17.0 | 实时窗口监控（本地模式） |
| fastapi | ≥0.104.0 | RESTful API服务 |
| uvicorn | ≥0.24.0 | ASGI服务器 |
| streamlit | ≥1.28.0 | 数据可视化 |
| scikit-learn | ≥1.3.0 | 聚类分析 |
| plotly | ≥5.18.0 | 交互式图表 |
| pandas | ≥1.5.0 | 数据处理 |
| numpy | ≥1.23.0 | 数值计算 |

## 🚀 快速开始

### 一键运行完整流程

```bash
python main.py
```

这将自动完成：
1. 数据获取（优先使用已有数据，否则生成合成数据）
2. 特征工程与用户画像构建
3. 零部件健康度评分
4. 加速试验工况转化
5. Flink实时监控模拟
6. 生成分析报告

### 分步运行

#### 步骤1: 生成数据

```bash
python -c "
from src.data_generator import CANDataGenerator
gen = CANDataGenerator(num_vehicles=5, records_per_vehicle=10000)
data = gen.generate_all_data()
gen.save_data(data)
print('数据生成完成')
"
```

#### 步骤2: 运行特征工程

```bash
python -c "
from main import step_2_feature_engineering
from src.data_generator import CANDataGenerator
gen = CANDataGenerator()
data = gen.load_data()
result = step_2_feature_engineering(data)
print('特征工程完成')
"
```

#### 步骤3: 健康度评分

```bash
python -c "
from main import step_3_health_monitoring
from src.data_generator import CANDataGenerator
gen = CANDataGenerator()
data = gen.load_data()
result = step_3_health_monitoring(data)
print('健康监控完成')
"
```

### 启动可视化界面

```bash
streamlit run app.py --server.port 8501
```

然后在浏览器打开 http://localhost:8501

### 启动API服务

```bash
python -m src.api_service
```

API文档地址: http://localhost:8000/docs

## 📊 功能详情

### 1. 用户画像构建

#### 8组用户标签

| 标签 | 描述 | 范围 |
|------|------|------|
| 驾驶激进指数 | 基于油门/刹车使用模式 | 0-100 |
| 空调依赖度 | 空调使用时长和功率占比 | 0-100 |
| 充电偏好 | 充电频率和时段偏好 | 0-100 |
| 能耗等级 | 基于百公里电耗的评级 | 1-5级 |
| 高温暴露度 | 高温环境下行驶时间比例 | 0-100 |
| 急加速频率 | 急加速事件占比 | 0-100 |
| 制动强度 | 平均制动减速度和频率 | 0-100 |
| 续航焦虑度 | 低SOC运行时长分析 | 0-100 |

#### 驾驶工况识别

- **拥堵**: 平均速度≤30km/h，刹车频繁
- **巡航**: 速度60-120km/h，油门稳定
- **激烈**: 高油门(≥80%)，变化剧烈
- **经济**: 低油门(≤50%)，速度适中

### 2. 零部件健康监控

#### 健康度评分模型

```
综合评分 = 电机温度评分(30%) + 电池温度评分(30%) + 电压评分(25%) + 运行模式评分(15%)
```

#### 评分等级

| 等级 | 分数范围 | 说明 |
|------|---------|------|
| 优秀 | 90-100 | 各指标优秀 |
| 良好 | 80-89 | 正常范围内 |
| 正常 | 60-79 | 有轻微偏离 |
| 警告 | 40-59 | 需要关注 |
| 危险 | 0-39 | 需立即检查 |

### 3. 加速试验工况转化

#### 工况类型

| 类型 | 识别条件 |
|------|---------|
| 高负载 | 油门≥70% 或 速度≥80km/h 或 电机温度≥80°C |
| 高温 | 电机温度≥100°C 或 电池温度≥40°C |
| 急充 | 电流≥100A 且 充电中 |
| 急放 | 电流≥100A 且 高油门(≥50%) |

### 4. FastAPI端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/data/overview` | GET | 数据概览 |
| `/api/v1/user-profile/{vehicle_id}` | GET | 用户画像查询 |
| `/api/v1/health-score/{vehicle_id}` | GET | 健康评分查询 |
| `/api/v1/alerts` | GET | 预警列表 |
| `/api/v1/driving-scenario/{vehicle_id}` | GET | 驾驶工况查询 |
| `/api/v1/accelerated-test/{vehicle_id}` | GET | 加速试验工况 |
| `/api/v1/system/status` | GET | 系统状态 |

## 📝 API使用示例

### 获取用户画像

```bash
curl http://localhost:8000/api/v1/user-profile/EV-0001
```

响应:
```json
{
  "vehicle_id": "EV-0001",
  "driving_aggression_index": 45.2,
  "ac_dependency": 62.3,
  "charging_preference": 78.5,
  "energy_consumption_level": 2.0,
  "primary_scenario": "经济",
  "cluster": 0
}
```

### 获取健康评分

```bash
curl http://localhost:8000/api/v1/health-score/EV-0001
```

响应:
```json
{
  "vehicle_id": "EV-0001",
  "overall_score": 85.5,
  "overall_level": "良好",
  "component_scores": {
    "motor": 88.0,
    "battery": 82.5,
    "operation": 86.0
  },
  "critical_alerts": []
}
```

## 🔍 数据说明

### CAN信号字段

| 字段 | 类型 | 单位 | 描述 |
|------|------|------|------|
| timestamp | string | - | 时间戳 |
| vehicle_id | string | - | 车辆ID |
| speed | float | km/h | 车速 |
| throttle | float | % | 油门踏板 |
| brake | float | % | 刹车踏板 |
| battery_soc | float | % | 电池SOC |
| battery_voltage | float | V | 电池电压 |
| battery_current | float | A | 电池电流 |
| battery_temperature | float | °C | 电池温度 |
| motor_temperature | float | °C | 电机温度 |
| motor_rpm | float | rpm | 电机转速 |
| motor_torque | float | N·m | 电机扭矩 |

### 数据规模

- 默认: 5辆车 × 10000条/车 = 50000条记录
- 可配置: 修改`config.py`中的`DATA_CONFIG`

## ⚙️ 配置说明

主要配置项在`config.py`中:

```python
# 数据生成配置
DATA_CONFIG = {
    "num_vehicles": 5,           # 车辆数量
    "records_per_vehicle": 10000, # 每车记录数
}

# 健康评分阈值
HEALTH_SCORE_CONFIG = {
    "motor_temp": {"normal_max": 120, "warning_max": 150},
    "battery_temp": {"normal_max": 45, "warning_max": 55},
}

# 预警规则
ALERT_RULES = {
    "motor_overheat": {"threshold": 150, "severity": "warning"},
    "low_soc_warning": {"threshold": 15, "severity": "info"},
}
```

## 📱 常见问题

### Q: PySpark/PyFlink需要安装Hadoop吗？

A: 不需要。本项目使用本地模式（LocalMode），不需要安装Hadoop或Flink集群。

### Q: 数据从哪里获取？

A: 优先从在线数据源搜索（Figshare/Zenodo/Mendeley），如果搜索不到则自动生成合成数据。

### Q: 如何增加更多车辆？

A: 修改`config.py`中的`num_vehicles`，然后重新运行数据生成。

### Q: API服务无法启动？

A: 检查端口是否被占用：`lsof -i :8000`

## 📄 许可证

MIT License

## 👥 作者

蒋浩伟

## 🔗 相关资源

- [PySpark Documentation](https://spark.apache.org/docs/latest/)
- [PyFlink Documentation](https://nightlies.apache.org/flink/flink-docs-stable/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)
  
## 最后更新：2026年
## 版权声明：本项目仅供学习和研究使用。
