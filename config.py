"""
CAN总线新能源汽车用户画像与健康监控系统
配置文件 - 包含所有项目配置参数
"""

import os
from pathlib import Path

# ============================================
# 项目根目录配置
# ============================================
PROJECT_ROOT = Path("/app/data/所有对话/主对话/CAN_User_Profile_Health")
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_FIGURES_DIR = PROJECT_ROOT / "output" / "figures"
OUTPUT_REPORTS_DIR = PROJECT_ROOT / "output" / "reports"

# 确保目录存在
for dir_path in [DATA_RAW_DIR, DATA_PROCESSED_DIR, OUTPUT_FIGURES_DIR, OUTPUT_REPORTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ============================================
# 数据生成配置
# ============================================
DATA_CONFIG = {
    "num_vehicles": 5,                    # 车辆数量
    "records_per_vehicle": 10000,         # 每辆车记录数
    "sampling_interval_ms": 100,          # 采样间隔(毫秒)
    "start_timestamp": "2024-01-01 00:00:00",
}

# 车辆ID列表
VEHICLE_IDS = [f"EV-{str(i).zfill(4)}" for i in range(1, DATA_CONFIG["num_vehicles"] + 1)]

# ============================================
# CAN信号范围配置
# ============================================
CAN_SIGNAL_RANGES = {
    # 基础行驶信号
    "speed": {"min": 0, "max": 180, "unit": "km/h"},           # 车速
    "throttle": {"min": 0, "max": 100, "unit": "%"},          # 油门踏板
    "brake": {"min": 0, "max": 100, "unit": "%"},             # 刹车踏板
    "steering_angle": {"min": -540, "max": 540, "unit": "deg"}, # 方向盘角度
    
    # 电池系统信号
    "battery_soc": {"min": 0, "max": 100, "unit": "%"},       # 电池SOC
    "battery_voltage": {"min": 280, "max": 420, "unit": "V"}, # 电池电压
    "battery_current": {"min": -200, "max": 200, "unit": "A"}, # 电池电流
    "battery_temperature": {"min": -20, "max": 60, "unit": "°C"}, # 电池温度
    
    # 电机系统信号
    "motor_temperature": {"min": 20, "max": 180, "unit": "°C"}, # 电机温度
    "motor_rpm": {"min": 0, "max": 15000, "unit": "rpm"},     # 电机转速
    "motor_torque": {"min": -300, "max": 500, "unit": "N·m"}, # 电机扭矩
    
    # 座舱环境信号
    "cabin_temperature": {"min": -10, "max": 50, "unit": "°C"}, # 座舱温度
    "ac_power": {"min": 0, "max": 10, "unit": "kW"},          # 空调功率
    
    # 充电状态
    "charging_status": {"min": 0, "max": 3, "unit": ""},      # 0:未充电 1:慢充 2:快充 3:充满
}

# ============================================
# 驾驶工况阈值配置
# ============================================
DRIVING_SCENARIO_THRESHOLDS = {
    "拥堵": {
        "speed_max": 30,           # 平均速度上限
        "throttle_avg_max": 40,    # 平均油门上限
        "brake_avg_min": 30,       # 平均刹车下限
    },
    "巡航": {
        "speed_min": 60,           # 平均速度下限
        "speed_max": 120,          # 平均速度上限
        "throttle_std_max": 15,    # 油门稳定性要求
    },
    "激烈": {
        "throttle_max": 80,        # 最大油门要求
        "throttle_std_min": 25,   # 油门变化要求
        "brake_max_min": 70,       # 最大刹车要求
        "speed_var_min": 40,       # 速度变化要求
    },
    "经济": {
        "throttle_avg_max": 50,    # 平均油门上限
        "throttle_std_max": 20,    # 油门稳定性要求
        "speed_avg_min": 30,       # 平均速度下限
        "regen_ratio_min": 0.3,    # 能量回收占比要求
    }
}

# ============================================
# 用户画像标签配置
# ============================================
USER_PROFILE_TAGS = {
    "driving_aggression_index": {
        "name": "驾驶激进指数",
        "description": "基于油门/刹车使用模式计算的激进程度评分",
        "range": (0, 100),
    },
    "ac_dependency": {
        "name": "空调依赖度",
        "description": "空调使用时长和功率占总行驶时间的比例",
        "range": (0, 100),
    },
    "charging_preference": {
        "name": "充电偏好",
        "description": "充电频率和时段偏好分析",
        "range": (0, 100),
    },
    "energy_consumption_level": {
        "name": "能耗等级",
        "description": "基于百公里电耗的能效评级",
        "range": (1, 5),
    },
    "high_temp_exposure": {
        "name": "高温暴露度",
        "description": "在高温环境下行驶的累计时间比例",
        "range": (0, 100),
    },
    "rapid_accel_frequency": {
        "name": "急加速频率",
        "description": "急加速事件占总加速事件的比例",
        "range": (0, 100),
    },
    "braking_intensity": {
        "name": "制动强度",
        "description": "平均制动减速度和制动频率的综合评分",
        "range": (0, 100),
    },
    "range_anxiety": {
        "name": "续航焦虑度",
        "description": "低SOC运行时长和充电行为模式分析",
        "range": (0, 100),
    }
}

# ============================================
# 健康度评分配置
# ============================================
HEALTH_SCORE_CONFIG = {
    # 温度阈值 (°C)
    "motor_temp": {
        "normal_max": 120,         # 正常上限
        "warning_max": 150,        # 警告上限
        "critical_max": 180,       # 严重上限
    },
    "battery_temp": {
        "normal_max": 45,          # 正常上限
        "warning_max": 55,         # 警告上限
        "critical_max": 60,        # 严重上限
    },
    # 电压阈值 (V)
    "battery_voltage": {
        "normal_min": 300,         # 正常下限
        "normal_max": 400,         # 正常上限
        "warning_min": 280,        # 警告下限
        "warning_max": 420,        # 警告上限
    },
    # 评分权重
    "weights": {
        "motor_temp": 0.3,         # 电机温度权重
        "battery_temp": 0.3,       # 电池温度权重
        "battery_voltage": 0.25,   # 电池电压权重
        "operation_pattern": 0.15, # 运行模式权重
    }
}

# ============================================
# 预警规则配置
# ============================================
ALERT_RULES = {
    "motor_overheat": {
        "name": "电机过热预警",
        "condition": "motor_temperature > 150",
        "severity": "warning",
        "threshold": 150,
        "unit": "°C"
    },
    "motor_critical": {
        "name": "电机严重过热",
        "condition": "motor_temperature > 170",
        "severity": "critical",
        "threshold": 170,
        "unit": "°C"
    },
    "battery_overheat": {
        "name": "电池过热预警",
        "condition": "battery_temperature > 50",
        "severity": "warning",
        "threshold": 50,
        "unit": "°C"
    },
    "battery_critical": {
        "name": "电池严重过热",
        "condition": "battery_temperature > 55",
        "severity": "critical",
        "threshold": 55,
        "unit": "°C"
    },
    "voltage_low": {
        "name": "电池电压过低",
        "condition": "battery_voltage < 290",
        "severity": "warning",
        "threshold": 290,
        "unit": "V"
    },
    "voltage_high": {
        "name": "电池电压过高",
        "condition": "battery_voltage > 415",
        "severity": "warning",
        "threshold": 415,
        "unit": "V"
    },
    "voltage_fluctuation": {
        "name": "电压波动异常",
        "condition": "voltage_std > 5 over window",
        "severity": "warning",
        "threshold": 5,
        "unit": "V"
    },
    "low_soc_warning": {
        "name": "低电量警告",
        "condition": "battery_soc < 15",
        "severity": "info",
        "threshold": 15,
        "unit": "%"
    },
    "low_soc_critical": {
        "name": "低电量严重警告",
        "condition": "battery_soc < 5",
        "severity": "critical",
        "threshold": 5,
        "unit": "%"
    }
}

# ============================================
# PyFlink窗口配置
# ============================================
FLINK_CONFIG = {
    "window_size_seconds": 10,         # 滑动窗口大小
    "slide_interval_seconds": 5,       # 滑动间隔
    "checkpoint_interval_ms": 1000,    # 检查点间隔
    "processing_time": True,           # 使用处理时间语义
}

# ============================================
# PySpark配置
# ============================================
SPARK_CONFIG = {
    "app_name": "CAN_Data_Analysis",
    "master": "local[*]",               # 本地模式，使用所有CPU核心
    "driver_memory": "2g",
    "executor_memory": "2g",
    "max_result_size": "1g",
    "shuffle_partitions": 8,
}

# ============================================
# FastAPI配置
# ============================================
API_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "title": "CAN总线新能源汽车数据服务API",
    "description": "提供用户画像、健康监控、预警查询等数据服务",
    "version": "1.0.0",
    "docs_url": "/docs",
    "redoc_url": "/redoc",
}

# ============================================
# 爬虫配置
# ============================================
SCRAPER_CONFIG = {
    "timeout": 30,                       # 请求超时(秒)
    "retry_times": 3,                   # 重试次数
    "retry_delay": 5,                   # 重试延迟(秒)
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "headers": {
        "Accept": "application/json, text/html",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
}

# ============================================
# API数据端点配置
# ============================================
API_ENDPOINTS = {
    "user_profile": "/api/v1/user-profile/{vehicle_id}",
    "health_score": "/api/v1/health-score/{vehicle_id}",
    "alerts": "/api/v1/alerts",
    "driving_scenario": "/api/v1/driving-scenario/{vehicle_id}",
    "system_status": "/api/v1/system/status",
    "accelerated_test": "/api/v1/accelerated-test/{vehicle_id}",
}

# ============================================
# 聚类分析配置
# ============================================
CLUSTERING_CONFIG = {
    "n_clusters": 4,                    # 工况类别数量
    "features_for_clustering": [
        "avg_speed", "avg_throttle", "avg_brake",
        "throttle_std", "brake_std", "speed_std"
    ],
    "random_state": 42,
}

# ============================================
# 可视化配置
# ============================================
VISUALIZATION_CONFIG = {
    "figure_size": (12, 8),
    "dpi": 100,
    "style": "seaborn-v0_8-darkgrid",
    "color_palette": "Set2",
    "plotly_template": "plotly_dark",
}

# ============================================
# 日志配置
# ============================================
LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": PROJECT_ROOT / "logs" / "app.log",
}
