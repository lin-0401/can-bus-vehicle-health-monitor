#!/usr/bin/env python3
"""
CAN总线新能源汽车用户画像与健康监控系统
Streamlit可视化系统

页面：
1. 首页概览 - 项目介绍、数据概况
2. 用户画像 - 驾驶工况分布、8组标签雷达图
3. 健康监控 - 实时监控模拟、健康度评分、预警列表
4. 工况转化 - 加速耐久工况序列可视化
5. API文档 - FastAPI端点展示
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime

# 添加项目根目录
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 导入配置
from config import DATA_RAW_DIR, DATA_PROCESSED_DIR, OUTPUT_REPORTS_DIR, API_CONFIG


# ============================================
# 页面配置
# ============================================

st.set_page_config(
    page_title="CAN总线新能源汽车分析系统",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #ff7f0e;
        padding: 0.5rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)


# ============================================
# 数据加载
# ============================================

@st.cache_data
def load_raw_data():
    """加载原始数据"""
    csv_files = list(DATA_RAW_DIR.glob("*.csv"))
    if csv_files:
        latest = sorted(csv_files)[-1]
        return pd.read_csv(latest)
    return None


@st.cache_data
def load_processed_data():
    """加载处理后数据"""
    results = {}
    
    # 用户画像
    profile_file = DATA_PROCESSED_DIR / "user_profiles.csv"
    if profile_file.exists():
        results["profiles"] = pd.read_csv(profile_file)
    
    # 健康报告
    health_file = DATA_PROCESSED_DIR / "health_reports.csv"
    if health_file.exists():
        results["health"] = pd.read_csv(health_file)
    
    # 车辆统计
    stats_file = DATA_PROCESSED_DIR / "vehicle_stats.csv"
    if stats_file.exists():
        results["stats"] = pd.read_csv(stats_file)
    
    # 加速试验
    accel_file = DATA_PROCESSED_DIR / "accelerated_test_sequence.csv"
    if accel_file.exists():
        results["accel"] = pd.read_csv(accel_file)
    
    return results


# ============================================
# 页面组件
# ============================================

def render_header():
    """渲染页面头部"""
    st.markdown('<p class="main-header">🚗 CAN总线新能源汽车用户画像与健康监控系统</p>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: gray;">基于PySpark/PyFlink的新能源汽车大数据分析平台</p>', unsafe_allow_html=True)
    st.divider()


def render_metric_card(label, value, delta=None):
    """渲染指标卡片"""
    col = st.columns(1)[0]
    with col:
        st.metric(label=label, value=value, delta=delta)


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.header("📊 系统导航")
        
        # 页面选择
        page = st.selectbox(
            "选择页面",
            ["🏠 首页概览", "👤 用户画像", "💚 健康监控", "⚡ 加速试验", "📡 API文档"]
        )
        
        st.divider()
        
        # 数据状态
        st.subheader("📁 数据状态")
        data = load_raw_data()
        if data is not None:
            st.success("✓ 原始数据已加载")
            st.info(f"记录数: {len(data):,}")
            st.info(f"车辆数: {data['vehicle_id'].nunique()}")
        else:
            st.warning("⚠ 原始数据未加载")
        
        processed = load_processed_data()
        if processed:
            st.success("✓ 处理数据已加载")
        else:
            st.warning("⚠ 处理数据未加载")
        
        st.divider()
        
        # 系统信息
        st.subheader("ℹ️ 系统信息")
        st.info(f"版本: {API_CONFIG['version']}")
        st.info(f"API端口: {API_CONFIG['port']}")
        
        return page


# ============================================
# 页面1: 首页概览
# ============================================

def page_overview():
    """首页概览"""
    st.subheader("📊 项目概览")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总记录数", "50,000+", "合成数据")
    with col2:
        st.metric("车辆数", "5", "多种驾驶风格")
    with col3:
        st.metric("用户标签", "8组", "全面画像")
    with col4:
        st.metric("API端点", "7个", "RESTful")
    
    st.divider()
    
    # 项目介绍
    st.subheader("🎯 项目功能")
    
    features = st.columns(3)
    
    with features[0]:
        st.markdown("""
        ### 👤 用户画像
        - 基于CAN总线数据分析驾驶行为
        - 识别4种驾驶工况
        - 构建8组用户标签体系
        - 使用PySpark进行特征工程
        """)
    
    with features[1]:
        st.markdown("""
        ### 💚 健康监控
        - 实时监控电机/电池温度
        - 电压波动异常检测
        - 基于PyFlink窗口聚合
        - 健康度0-100评分
        """)
    
    with features[2]:
        st.markdown("""
        ### ⚡ 加速试验
        - 提取高负载、高温工况
        - 识别急充急放时段
        - 生成耐久测试序列
        - 严苛度评分分析
        """)
    
    st.divider()
    
    # 技术架构
    st.subheader("🏗️ 技术架构")
    
    tech_col1, tech_col2 = st.columns(2)
    
    with tech_col1:
        st.markdown("""
        **数据处理**
        - PySpark本地模式: 特征工程与聚合
        - PyFlink本地模式: 实时窗口监控
        - scikit-learn: 聚类分析
        
        **数据源**
        - Figshare API: 新能源汽车数据集
        - Zenodo API: 驾驶行为数据
        - 合成数据生成: 基于真实驾驶规律
        """)
    
    with tech_col2:
        st.markdown("""
        **可视化与服务**
        - Streamlit: 数据可视化系统
        - FastAPI: RESTful API服务
        - Plotly: 交互式图表
        
        **CAN信号**
        - 车速、油门、刹车
        - 电池SOC/电压/温度
        - 电机温度/转速/扭矩
        """)
    
    # 数据预览
    st.divider()
    st.subheader("📋 数据预览")
    
    data = load_raw_data()
    if data is not None:
        st.dataframe(data.head(10), use_container_width=True)
        
        st.divider()
        st.subheader("📈 关键指标统计")
        
        numeric_cols = ['speed', 'battery_soc', 'motor_temperature', 'battery_temperature', 'throttle', 'brake']
        stats_df = data[numeric_cols].describe().round(2)
        st.dataframe(stats_df, use_container_width=True)
    else:
        st.info("请先运行 `python main.py` 生成数据")


# ============================================
# 页面2: 用户画像
# ============================================

def page_user_profile():
    """用户画像页面"""
    st.subheader("👤 用户画像分析")
    
    processed = load_processed_data()
    
    if "profiles" not in processed:
        st.warning("请先运行 `python main.py` 完成分析")
        return
    
    profiles = processed["profiles"]
    
    # 车辆选择
    vehicle_ids = profiles["vehicle_id"].unique()
    selected_vehicle = st.selectbox("选择车辆", vehicle_ids)
    
    # 获取选中车辆画像
    vehicle_profile = profiles[profiles["vehicle_id"] == selected_vehicle].iloc[0]
    
    # 显示8组标签
    st.divider()
    st.subheader("📊 8组用户标签")
    
    tag_cols = st.columns(4)
    
    tags_info = [
        ("driving_aggression_index", "驾驶激进指数", "🚗"),
        ("ac_dependency", "空调依赖度", "❄️"),
        ("charging_preference", "充电偏好", "🔌"),
        ("energy_consumption_level", "能耗等级", "⚡"),
        ("high_temp_exposure", "高温暴露度", "🌡️"),
        ("rapid_accel_frequency", "急加速频率", "🏎️"),
        ("braking_intensity", "制动强度", "🛑"),
        ("range_anxiety", "续航焦虑度", "🔋"),
    ]
    
    for i, (tag_key, tag_name, icon) in enumerate(tags_info):
        with tag_cols[i % 4]:
            value = vehicle_profile.get(tag_key, 0)
            if tag_key == "energy_consumption_level":
                st.metric(f"{icon} {tag_name}", f"{value:.0f}级")
            else:
                st.metric(f"{icon} {tag_name}", f"{value:.1f}")
    
    # 雷达图
    st.divider()
    st.subheader("🎯 标签雷达图")
    
    # 准备雷达图数据
    radar_tags = [
        ("驾驶激进指数", vehicle_profile.get("driving_aggression_index", 0)),
        ("空调依赖", vehicle_profile.get("ac_dependency", 0)),
        ("充电偏好", vehicle_profile.get("charging_preference", 0)),
        ("高温暴露", vehicle_profile.get("high_temp_exposure", 0)),
        ("急加速频率", vehicle_profile.get("rapid_accel_frequency", 0)),
        ("制动强度", vehicle_profile.get("braking_intensity", 0)),
        ("续航焦虑", vehicle_profile.get("range_anxiety", 0)),
    ]
    
    # 创建雷达图
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=[v for _, v in radar_tags] + [radar_tags[0][1]],  # 闭合
        theta=[k for k, _ in radar_tags] + [radar_tags[0][0]],
        fill='toself',
        fillcolor='rgba(31, 119, 180, 0.3)',
        line=dict(color='rgb(31, 119, 180)', width=2),
        name=f'{selected_vehicle}画像'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )
        ),
        showlegend=True,
        height=400,
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 工况分布
    st.divider()
    st.subheader("🚦 驾驶工况分布")
    
    if "primary_scenario" in vehicle_profile:
        scenario = vehicle_profile["primary_scenario"]
        st.info(f"主要驾驶工况: **{scenario}**")
    
    # 聚类信息
    if "cluster" in vehicle_profile:
        cluster = vehicle_profile["cluster"]
        cluster_names = ["经济型", "均衡型", "运动型", "拥堵适应型", "高温工况型"]
        cluster_name = cluster_names[cluster] if cluster < len(cluster_names) else "未知"
        st.info(f"聚类分组: **{cluster_name}** (聚类{cluster})")
    
    # 全部车辆对比
    st.divider()
    st.subheader("📊 全部车辆画像对比")
    
    # 能耗等级对比
    fig2 = px.bar(
        profiles,
        x="vehicle_id",
        y="energy_consumption_level",
        color="energy_consumption_level",
        title="各车辆能耗等级对比",
        labels={"energy_consumption_level": "能耗等级", "vehicle_id": "车辆"}
    )
    st.plotly_chart(fig2, use_container_width=True)
    
    # 激进指数对比
    fig3 = px.bar(
        profiles,
        x="vehicle_id",
        y="driving_aggression_index",
        color="driving_aggression_index",
        title="各车辆驾驶激进指数对比",
        labels={"driving_aggression_index": "激进指数", "vehicle_id": "车辆"}
    )
    st.plotly_chart(fig3, use_container_width=True)


# ============================================
# 页面3: 健康监控
# ============================================

def page_health_monitor():
    """健康监控页面"""
    st.subheader("💚 零部件健康监控")
    
    processed = load_processed_data()
    
    if "health" not in processed:
        st.warning("请先运行 `python main.py` 完成分析")
        return
    
    health_df = processed["health"]
    
    # 健康评分概览
    st.divider()
    st.subheader("📊 健康评分概览")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_score = health_df["overall_score"].mean()
        st.metric("平均健康评分", f"{avg_score:.1f}")
    
    with col2:
        min_score = health_df["overall_score"].min()
        st.metric("最低评分", f"{min_score:.1f}")
    
    with col3:
        excellent = len(health_df[health_df["overall_score"] >= 80])
        st.metric("优秀车辆", f"{excellent}/{len(health_df)}")
    
    with col4:
        warning = len(health_df[health_df["overall_score"] < 60])
        st.metric("需关注车辆", f"{warning}")
    
    # 车辆选择
    vehicle_ids = health_df["vehicle_id"].unique()
    selected_vehicle = st.selectbox("选择车辆查看详情", vehicle_ids)
    
    # 获取选中车辆健康报告
    vehicle_health = health_df[health_df["vehicle_id"] == selected_vehicle].iloc[0]
    
    st.divider()
    st.subheader(f"🚗 {selected_vehicle} 健康详情")
    
    # 综合评分
    score = vehicle_health["overall_score"]
    level = vehicle_health["overall_level"]
    
    score_col1, score_col2 = st.columns([1, 2])
    
    with score_col1:
        # 评分仪表盘
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 40], 'color': "red"},
                    {'range': [40, 60], 'color': "orange"},
                    {'range': [60, 80], 'color': "yellow"},
                    {'range': [80, 100], 'color': "green"},
                ],
            }
        ))
        fig_gauge.update_layout(height=200)
        st.plotly_chart(fig_gauge, use_container_width=True)
        st.caption(f"健康等级: {level}")
    
    with score_col2:
        # 零部件评分
        st.markdown("**零部件评分**")
        
        component_scores = vehicle_health.get("component_scores", {})
        if isinstance(component_scores, str):
            import ast
            component_scores = ast.literal_eval(component_scores)
        
        comp_cols = st.columns(3)
        
        for i, (comp, score_val) in enumerate(component_scores.items()):
            comp_names = {"motor": "电机", "battery": "电池", "operation": "运行模式"}
            comp_name = comp_names.get(comp, comp)
            
            with comp_cols[i % 3]:
                st.metric(f"{comp_name}", f"{score_val:.1f}")
    
    # 预警信息
    st.divider()
    st.subheader("⚠️ 预警信息")
    
    alerts = vehicle_health.get("critical_alerts", [])
    if isinstance(alerts, str):
        import ast
        try:
            alerts = ast.literal_eval(alerts)
        except:
            alerts = [alerts] if alerts else []
    
    if alerts:
        for alert in alerts[:5]:
            st.warning(f"⚠️ {alert}")
    else:
        st.success("✓ 暂无预警信息")
    
    # 摘要
    summary = vehicle_health.get("summary", "")
    if summary:
        st.info(f"**健康摘要**: {summary}")
    
    # 全部车辆对比
    st.divider()
    st.subheader("📊 全部车辆健康评分对比")
    
    fig_health = px.bar(
        health_df,
        x="vehicle_id",
        y="overall_score",
        color="overall_level",
        title="各车辆健康评分对比",
        labels={"overall_score": "健康评分", "vehicle_id": "车辆", "overall_level": "健康等级"}
    )
    st.plotly_chart(fig_health, use_container_width=True)
    
    # 零部件评分对比
    if "stats" in processed:
        stats_df = processed["stats"]
        
        st.divider()
        st.subheader("📈 零部件指标对比")
        
        # 电机温度对比
        if "avg_motor_temp" in stats_df.columns:
            fig_motor = px.bar(
                stats_df,
                x="vehicle_id",
                y="avg_motor_temp",
                title="各车辆平均电机温度对比",
                labels={"avg_motor_temp": "平均电机温度 (°C)", "vehicle_id": "车辆"}
            )
            st.plotly_chart(fig_motor, use_container_width=True)
        
        # 电池温度对比
        if "avg_battery_temp" in stats_df.columns:
            fig_battery = px.bar(
                stats_df,
                x="vehicle_id",
                y="avg_battery_temp",
                title="各车辆平均电池温度对比",
                labels={"avg_battery_temp": "平均电池温度 (°C)", "vehicle_id": "车辆"}
            )
            st.plotly_chart(fig_battery, use_container_width=True)


# ============================================
# 页面4: 加速试验
# ============================================

def page_accelerated_test():
    """加速试验工况页面"""
    st.subheader("⚡ 加速试验工况转化")
    
    processed = load_processed_data()
    
    if "accel" not in processed:
        st.warning("请先运行 `python main.py` 完成分析")
        return
    
    accel_df = processed["accel"]
    
    # 概览统计
    st.divider()
    st.subheader("📊 工况概览")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总工况段", len(accel_df))
    
    with col2:
        total_duration = accel_df["duration_seconds"].sum() / 60
        st.metric("总时长", f"{total_duration:.1f} 分钟")
    
    with col3:
        high_value = len(accel_df[accel_df["test_value"] == "高价值"])
        st.metric("高价值工况", high_value)
    
    with col4:
        avg_severity = accel_df["severity_score"].mean()
        st.metric("平均严苛度", f"{avg_severity:.1f}")
    
    # 工况类型分布
    st.divider()
    st.subheader("📊 工况类型分布")
    
    type_names = {
        "high_load": "高负载",
        "high_temp": "高温",
        "rapid_charge": "急充",
        "rapid_discharge": "急放",
    }
    
    type_dist = accel_df["condition_type"].value_counts().reset_index()
    type_dist.columns = ["类型", "数量"]
    type_dist["类型"] = type_dist["类型"].map(type_names)
    
    fig_pie = px.pie(
        type_dist,
        values="数量",
        names="类型",
        title="工况类型分布",
        hole=0.4
    )
    st.plotly_chart(fig_pie, use_container_width=True)
    
    # 车辆选择
    vehicle_ids = accel_df["vehicle_id"].unique()
    selected_vehicle = st.selectbox("选择车辆查看工况详情", vehicle_ids)
    
    vehicle_accel = accel_df[accel_df["vehicle_id"] == selected_vehicle]
    
    st.divider()
    st.subheader(f"🚗 {selected_vehicle} 工况详情")
    
    # 工况列表
    st.dataframe(
        vehicle_accel[[
            "condition_type", "duration_seconds", 
            "max_motor_temp", "max_battery_temp", 
            "max_throttle", "severity_score", "test_value"
        ]].head(20),
        use_container_width=True
    )
    
    # 严苛度分布
    st.divider()
    st.subheader("📈 严苛度分布")
    
    fig_severity = px.histogram(
        accel_df,
        x="severity_score",
        color="condition_type",
        title="严苛度评分分布",
        labels={"severity_score": "严苛度评分", "count": "数量"},
        nbins=20
    )
    st.plotly_chart(fig_severity, use_container_width=True)
    
    # 高价值工况
    st.divider()
    st.subheader("⭐ 高价值工况")
    
    high_value_df = accel_df[accel_df["test_value"] == "高价值"]
    
    if len(high_value_df) > 0:
        st.dataframe(
            high_value_df[[
                "vehicle_id", "condition_type", "duration_seconds",
                "max_motor_temp", "max_battery_temp", "severity_score"
            ]],
            use_container_width=True
        )
    else:
        st.info("暂无高价值工况段")


# ============================================
# 页面5: API文档
# ============================================

def page_api_docs():
    """API文档页面"""
    st.subheader("📡 FastAPI数据服务")
    
    st.markdown(f"""
    **API基础信息**
    - 文档地址: `http://localhost:{API_CONFIG['port']}/docs`
    - Redoc地址: `http://localhost:{API_CONFIG['port']}/redoc`
    - API版本: {API_CONFIG['version']}
    """)
    
    st.divider()
    st.subheader("📋 API端点列表")
    
    endpoints = [
        {
            "method": "GET",
            "path": "/api/v1/data/overview",
            "description": "获取数据概览",
            "params": "-",
            "response": "数据记录数、车辆数、时间范围、指标统计"
        },
        {
            "method": "GET",
            "path": "/api/v1/user-profile/{vehicle_id}",
            "description": "获取用户画像",
            "params": "vehicle_id: 车辆ID",
            "response": "8组用户标签、驾驶工况、聚类分组"
        },
        {
            "method": "GET",
            "path": "/api/v1/health-score/{vehicle_id}",
            "description": "获取健康评分",
            "params": "vehicle_id: 车辆ID",
            "response": "综合评分、零部件评分、预警信息"
        },
        {
            "method": "GET",
            "path": "/api/v1/alerts",
            "description": "获取预警列表",
            "params": "vehicle_id(可选), severity(可选), limit(默认100)",
            "response": "预警列表、按类型/严重性统计"
        },
        {
            "method": "GET",
            "path": "/api/v1/driving-scenario/{vehicle_id}",
            "description": "获取驾驶工况分析",
            "params": "vehicle_id: 车辆ID",
            "response": "工况分布、平均指标"
        },
        {
            "method": "GET",
            "path": "/api/v1/accelerated-test/{vehicle_id}",
            "description": "获取加速试验工况",
            "params": "vehicle_id: 车辆ID",
            "response": "工况段列表、总时长、严苛度统计"
        },
        {
            "method": "GET",
            "path": "/api/v1/system/status",
            "description": "获取系统状态",
            "params": "-",
            "response": "系统运行状态、数据加载情况、API端点列表"
        },
    ]
    
    for ep in endpoints:
        with st.expander(f"`{ep['method']}` {ep['path']}", expanded=False):
            st.markdown(f"**描述**: {ep['description']}")
            st.markdown(f"**参数**: {ep['params']}")
            st.markdown(f"**响应**: {ep['response']}")
    
    st.divider()
    
    # API调用示例
    st.subheader("💻 API调用示例")
    
    st.markdown("""
    ```bash
    # 启动API服务
    python -m src.api_service
    
    # 获取系统状态
    curl http://localhost:8000/api/v1/system/status
    
    # 获取用户画像
    curl http://localhost:8000/api/v1/user-profile/EV-0001
    
    # 获取健康评分
    curl http://localhost:8000/api/v1/health-score/EV-0001
    
    # 获取预警列表
    curl "http://localhost:8000/api/v1/alerts?severity=warning&limit=50"
    ```
    """)
    
    st.divider()
    
    # 启动按钮
    st.subheader("🚀 启动服务")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📡 启动API服务", type="primary"):
            st.info("请在终端运行: `python -m src.api_service`")
            st.code("python -m src.api_service", language="bash")
    
    with col2:
        if st.button("📊 启动Streamlit", type="primary"):
            st.info("请在终端运行: `streamlit run app.py`")
            st.code("streamlit run app.py --server.port 8501", language="bash")


# ============================================
# 主函数
# ============================================

def main():
    """主函数"""
    # 渲染头部
    render_header()
    
    # 渲染侧边栏并获取页面选择
    page = render_sidebar()
    
    # 根据选择渲染页面
    if page == "🏠 首页概览":
        page_overview()
    elif page == "👤 用户画像":
        page_user_profile()
    elif page == "💚 健康监控":
        page_health_monitor()
    elif page == "⚡ 加速试验":
        page_accelerated_test()
    elif page == "📡 API文档":
        page_api_docs()


if __name__ == "__main__":
    main()
