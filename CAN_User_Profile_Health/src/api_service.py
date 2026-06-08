"""
CAN总线新能源汽车用户画像与健康监控系统
FastAPI数据服务API

端点列表：
1. GET /api/v1/user-profile/{vehicle_id} - 用户画像查询
2. GET /api/v1/health-score/{vehicle_id} - 健康度查询
3. GET /api/v1/alerts - 预警列表
4. GET /api/v1/driving-scenario/{vehicle_id} - 工况序列
5. GET /api/v1/system/status - 系统状态
6. GET /api/v1/accelerated-test/{vehicle_id} - 加速试验工况
7. GET /api/v1/data/overview - 数据概览
8. GET /health - 健康检查
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import API_CONFIG, DATA_RAW_DIR, DATA_PROCESSED_DIR


# ============================================
# 数据模型定义
# ============================================

class UserProfileResponse(BaseModel):
    """用户画像响应模型"""
    vehicle_id: str
    profile_type: str
    driving_aggression_index: float = Field(..., description="驾驶激进指数 0-100")
    ac_dependency: float = Field(..., description="空调依赖度 0-100")
    charging_preference: float = Field(..., description="充电偏好 0-100")
    energy_consumption_level: float = Field(..., description="能耗等级 1-5")
    high_temp_exposure: float = Field(..., description="高温暴露度 0-100")
    rapid_accel_frequency: float = Field(..., description="急加速频率 0-100")
    braking_intensity: float = Field(..., description="制动强度 0-100")
    range_anxiety: float = Field(..., description="续航焦虑度 0-100")
    primary_scenario: str = Field(..., description="主要驾驶工况")
    cluster: int = Field(..., description="聚类编号")
    timestamp: str


class HealthScoreResponse(BaseModel):
    """健康评分响应模型"""
    vehicle_id: str
    overall_score: float = Field(..., description="综合健康评分 0-100")
    overall_level: str = Field(..., description="健康等级")
    component_scores: Dict[str, float] = Field(..., description="零部件评分")
    report_time: str
    critical_alerts: List[str]
    summary: str


class AlertItem(BaseModel):
    """预警项模型"""
    timestamp: str
    vehicle_id: str
    alert_type: str
    alert_name: str
    severity: str
    value: float
    threshold: float
    unit: str
    message: str


class AlertsResponse(BaseModel):
    """预警列表响应模型"""
    total: int
    by_severity: Dict[str, int]
    by_type: Dict[str, int]
    alerts: List[AlertItem]


class DrivingScenarioResponse(BaseModel):
    """驾驶工况响应模型"""
    vehicle_id: str
    scenarios: List[Dict[str, Any]]
    distribution: Dict[str, int]
    avg_metrics: Dict[str, float]


class SystemStatusResponse(BaseModel):
    """系统状态响应模型"""
    status: str
    version: str
    uptime_seconds: float
    data_loaded: bool
    total_records: int
    total_vehicles: int
    api_endpoints: List[str]
    timestamp: str


class AcceleratedTestResponse(BaseModel):
    """加速试验工况响应模型"""
    vehicle_id: str
    test_name: str
    total_segments: int
    total_duration_minutes: float
    avg_severity: float
    high_value_segments: int
    segments: List[Dict[str, Any]]


class DataOverviewResponse(BaseModel):
    """数据概览响应模型"""
    total_records: int
    total_vehicles: int
    time_range: Dict[str, str]
    vehicle_list: List[str]
    metrics_summary: Dict[str, Dict[str, float]]


# ============================================
# 全局数据存储
# ============================================

class DataStore:
    """数据存储中心"""
    
    def __init__(self):
        self.raw_data: Optional[pd.DataFrame] = None
        self.user_profiles: Optional[pd.DataFrame] = None
        self.health_reports: Optional[List[Dict]] = None
        self.alerts: List[Dict] = []
        self.aggregates: List[Dict] = []
        self.accel_profiles: List[Dict] = []
        self.start_time = datetime.now()
        self._load_data()
    
    def _load_data(self):
        """加载数据文件"""
        logger.info("加载数据文件...")
        
        # 加载原始数据
        csv_files = list(DATA_RAW_DIR.glob("*.csv"))
        if csv_files:
            latest_file = sorted(csv_files)[-1]
            self.raw_data = pd.read_csv(latest_file)
            logger.info(f"已加载原始数据: {latest_file.name}, {len(self.raw_data)} 条记录")
        
        # 加载用户画像
        profile_file = DATA_PROCESSED_DIR / "user_profiles.csv"
        if profile_file.exists():
            self.user_profiles = pd.read_csv(profile_file)
            logger.info(f"已加载用户画像: {len(self.user_profiles)} 个用户")
        
        # 加载健康报告
        health_file = DATA_PROCESSED_DIR / "health_reports.csv"
        if health_file.exists():
            self.health_reports = pd.read_csv(health_file).to_dict("records")
            logger.info(f"已加载健康报告: {len(self.health_reports)} 份")
        
        # 加载加速测试工况
        accel_file = DATA_PROCESSED_DIR / "accelerated_test_sequence.csv"
        if accel_file.exists():
            accel_df = pd.read_csv(accel_file)
            self.accel_profiles = accel_df.to_dict("records")
            logger.info(f"已加载加速试验工况: {len(self.accel_profiles)} 个工况段")
    
    def reload_data(self):
        """重新加载数据"""
        self._load_data()


# 全局数据存储实例
data_store: Optional[DataStore] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global data_store
    logger.info("启动数据服务...")
    data_store = DataStore()
    yield
    logger.info("关闭数据服务...")


# ============================================
# FastAPI应用创建
# ============================================

app = FastAPI(
    title=API_CONFIG["title"],
    description=API_CONFIG["description"],
    version=API_CONFIG["version"],
    docs_url=API_CONFIG["docs_url"],
    redoc_url=API_CONFIG["redoc_url"],
    lifespan=lifespan,
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# API端点实现
# ============================================

@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/v1/data/overview", response_model=DataOverviewResponse, tags=["数据"])
async def get_data_overview():
    """
    获取数据概览
    
    返回系统中的数据概况，包括记录数、车辆数、时间范围等
    """
    if data_store.raw_data is None:
        raise HTTPException(status_code=404, detail="数据未加载，请先运行数据生成")
    
    data = data_store.raw_data
    
    # 计算指标摘要
    metrics = {}
    for col in ["speed", "battery_soc", "motor_temperature", "battery_temperature", "throttle", "brake"]:
        if col in data.columns:
            metrics[col] = {
                "mean": round(data[col].mean(), 2),
                "max": round(data[col].max(), 2),
                "min": round(data[col].min(), 2),
            }
    
    return DataOverviewResponse(
        total_records=len(data),
        total_vehicles=data["vehicle_id"].nunique(),
        time_range={
            "start": data["timestamp"].min(),
            "end": data["timestamp"].max(),
        },
        vehicle_list=data["vehicle_id"].unique().tolist(),
        metrics_summary=metrics,
    )


@app.get("/api/v1/user-profile/{vehicle_id}", response_model=UserProfileResponse, tags=["用户画像"])
async def get_user_profile(vehicle_id: str):
    """
    获取用户画像
    
    根据车辆ID返回该用户的完整画像标签
    """
    if data_store.user_profiles is None:
        raise HTTPException(status_code=404, detail="用户画像未加载，请先运行分析")
    
    profile = data_store.user_profiles[data_store.user_profiles["vehicle_id"] == vehicle_id]
    
    if profile.empty:
        raise HTTPException(status_code=404, detail=f"未找到车辆 {vehicle_id} 的画像")
    
    row = profile.iloc[0]
    
    # 确定驾驶风格
    profile_type = "均衡型"
    if row.get("cluster") == 0:
        profile_type = "经济型"
    elif row.get("cluster") == 1:
        profile_type = "运动型"
    elif row.get("cluster") == 2:
        profile_type = "拥堵适应型"
    elif row.get("cluster") == 3:
        profile_type = "高温工况型"
    
    return UserProfileResponse(
        vehicle_id=vehicle_id,
        profile_type=profile_type,
        driving_aggression_index=float(row.get("driving_aggression_index", 50)),
        ac_dependency=float(row.get("ac_dependency", 50)),
        charging_preference=float(row.get("charging_preference", 50)),
        energy_consumption_level=float(row.get("energy_consumption_level", 3)),
        high_temp_exposure=float(row.get("high_temp_exposure", 20)),
        rapid_accel_frequency=float(row.get("rapid_accel_frequency", 30)),
        braking_intensity=float(row.get("braking_intensity", 40)),
        range_anxiety=float(row.get("range_anxiety", 30)),
        primary_scenario=row.get("primary_scenario", "均衡"),
        cluster=int(row.get("cluster", 0)),
        timestamp=datetime.now().isoformat(),
    )


@app.get("/api/v1/health-score/{vehicle_id}", response_model=HealthScoreResponse, tags=["健康监控"])
async def get_health_score(vehicle_id: str):
    """
    获取健康评分
    
    返回指定车辆的健康评分和零部件状态
    """
    if data_store.health_reports is None:
        raise HTTPException(status_code=404, detail="健康报告未加载，请先运行分析")
    
    report = None
    for r in data_store.health_reports:
        if r.get("vehicle_id") == vehicle_id:
            report = r
            break
    
    if report is None:
        raise HTTPException(status_code=404, detail=f"未找到车辆 {vehicle_id} 的健康报告")
    
    # 解析component_scores
    component_scores = report.get("component_scores", {})
    if isinstance(component_scores, str):
        import ast
        component_scores = ast.literal_eval(component_scores)
    
    # 解析critical_alerts
    critical_alerts = report.get("critical_alerts", [])
    if isinstance(critical_alerts, str):
        import ast
        try:
            critical_alerts = ast.literal_eval(critical_alerts)
        except:
            critical_alerts = [critical_alerts]
    
    return HealthScoreResponse(
        vehicle_id=vehicle_id,
        overall_score=float(report.get("overall_score", 0)),
        overall_level=report.get("overall_level", "正常"),
        component_scores=component_scores,
        report_time=report.get("report_time", ""),
        critical_alerts=critical_alerts,
        summary=report.get("summary", ""),
    )


@app.get("/api/v1/alerts", response_model=AlertsResponse, tags=["预警"])
async def get_alerts(
    vehicle_id: Optional[str] = Query(None, description="车辆ID筛选"),
    severity: Optional[str] = Query(None, description="严重性筛选"),
    limit: int = Query(100, description="返回数量限制"),
):
    """
    获取预警列表
    
    返回系统中所有预警或按条件筛选
    """
    alerts = data_store.alerts.copy()
    
    # 筛选
    if vehicle_id:
        alerts = [a for a in alerts if a.get("vehicle_id") == vehicle_id]
    if severity:
        alerts = [a for a in alerts if a.get("severity") == severity]
    
    # 限制数量
    alerts = alerts[:limit]
    
    # 统计
    by_severity = {}
    by_type = {}
    for alert in alerts:
        sev = alert.get("severity", "unknown")
        typ = alert.get("alert_type", "unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_type[typ] = by_type.get(typ, 0) + 1
    
    return AlertsResponse(
        total=len(alerts),
        by_severity=by_severity,
        by_type=by_type,
        alerts=[AlertItem(**a) for a in alerts],
    )


@app.get("/api/v1/driving-scenario/{vehicle_id}", response_model=DrivingScenarioResponse, tags=["驾驶工况"])
async def get_driving_scenario(vehicle_id: str):
    """
    获取驾驶工况分析
    
    返回指定车辆的驾驶工况分布和特征
    """
    if data_store.raw_data is None:
        raise HTTPException(status_code=404, detail="数据未加载")
    
    vehicle_data = data_store.raw_data[data_store.raw_data["vehicle_id"] == vehicle_id]
    
    if vehicle_data.empty:
        raise HTTPException(status_code=404, detail=f"未找到车辆 {vehicle_id} 的数据")
    
    # 简单工况识别
    avg_speed = vehicle_data["speed"].mean()
    avg_throttle = vehicle_data["throttle"].mean()
    avg_brake = vehicle_data["brake"].mean()
    
    scenarios = []
    if avg_speed <= 30 and avg_brake >= 30:
        scenarios.append({"scenario": "拥堵", "ratio": 0.6})
    elif 60 <= avg_speed <= 120:
        scenarios.append({"scenario": "巡航", "ratio": 0.5})
    if avg_throttle >= 70:
        scenarios.append({"scenario": "激烈", "ratio": avg_throttle / 100})
    if avg_throttle <= 50 and avg_speed >= 30:
        scenarios.append({"scenario": "经济", "ratio": 0.4})
    
    # 默认添加均衡
    scenarios.append({"scenario": "均衡", "ratio": 0.3})
    
    # 计算分布
    distribution = {"拥堵": 0, "巡航": 0, "激烈": 0, "经济": 0, "均衡": 0}
    for s in scenarios:
        if s["scenario"] in distribution:
            distribution[s["scenario"]] = int(s["ratio"] * 100)
    
    return DrivingScenarioResponse(
        vehicle_id=vehicle_id,
        scenarios=scenarios,
        distribution=distribution,
        avg_metrics={
            "avg_speed": round(avg_speed, 2),
            "avg_throttle": round(avg_throttle, 2),
            "avg_brake": round(avg_brake, 2),
            "max_speed": round(vehicle_data["speed"].max(), 2),
        },
    )


@app.get("/api/v1/accelerated-test/{vehicle_id}", response_model=AcceleratedTestResponse, tags=["加速试验"])
async def get_accelerated_test(vehicle_id: str):
    """
    获取加速试验工况
    
    返回指定车辆的加速耐久测试工况段
    """
    if not data_store.accel_profiles:
        raise HTTPException(status_code=404, detail="加速试验工况未加载")
    
    vehicle_segments = [s for s in data_store.accel_profiles if s.get("vehicle_id") == vehicle_id]
    
    if not vehicle_segments:
        raise HTTPException(status_code=404, detail=f"未找到车辆 {vehicle_id} 的加速试验工况")
    
    segments_df = pd.DataFrame(vehicle_segments)
    
    return AcceleratedTestResponse(
        vehicle_id=vehicle_id,
        test_name=f"加速耐久测试_{vehicle_id}",
        total_segments=len(vehicle_segments),
        total_duration_minutes=round(segments_df["duration_seconds"].sum() / 60, 2),
        avg_severity=round(segments_df["severity_score"].mean(), 2),
        high_value_segments=len(segments_df[segments_df["test_value"] == "高价值"]),
        segments=vehicle_segments[:20],  # 限制返回数量
    )


@app.get("/api/v1/system/status", response_model=SystemStatusResponse, tags=["系统"])
async def get_system_status():
    """
    获取系统状态
    
    返回系统运行状态和数据加载情况
    """
    uptime = (datetime.now() - data_store.start_time).total_seconds()
    
    return SystemStatusResponse(
        status="running",
        version=API_CONFIG["version"],
        uptime_seconds=round(uptime, 2),
        data_loaded=data_store.raw_data is not None,
        total_records=len(data_store.raw_data) if data_store.raw_data is not None else 0,
        total_vehicles=data_store.raw_data["vehicle_id"].nunique() if data_store.raw_data is not None else 0,
        api_endpoints=[
            "/api/v1/data/overview",
            "/api/v1/user-profile/{vehicle_id}",
            "/api/v1/health-score/{vehicle_id}",
            "/api/v1/alerts",
            "/api/v1/driving-scenario/{vehicle_id}",
            "/api/v1/accelerated-test/{vehicle_id}",
            "/api/v1/system/status",
        ],
        timestamp=datetime.now().isoformat(),
    )


@app.post("/api/v1/data/reload", tags=["系统"])
async def reload_data():
    """
    重新加载数据
    
    重新从文件加载所有数据
    """
    data_store.reload_data()
    return {"message": "数据重新加载完成", "timestamp": datetime.now().isoformat()}


# ============================================
# 主函数
# ============================================

def run_server(host: str = None, port: int = None):
    """运行API服务器"""
    import uvicorn
    
    host = host or API_CONFIG["host"]
    port = port or API_CONFIG["port"]
    
    logger.info(f"启动API服务器: http://{host}:{port}")
    logger.info(f"API文档: http://{host}:{port}{API_CONFIG['docs_url']}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()
