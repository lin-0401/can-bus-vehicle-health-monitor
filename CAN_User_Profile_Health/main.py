#!/usr/bin/env python3
"""
CAN总线新能源汽车用户画像与健康监控系统
一键运行入口

流程：
1. 数据获取（爬虫/合成数据）
2. 特征工程与用户画像
3. 健康度评分
4. 加速试验工况转化
5. Flink实时监控
6. 生成分析报告
"""

import sys
import os
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def print_header(title: str):
    """打印标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_step(step: int, total: int, title: str):
    """打印步骤"""
    print(f"\n{'─' * 70}")
    print(f"  步骤 {step}/{total}: {title}")
    print(f"{'─' * 70}")


def step_1_data_acquisition() -> Optional[object]:
    """
    步骤1: 数据获取
    
    优先检查已有数据，如果没有则生成合成数据
    """
    print_step(1, 6, "数据获取")
    
    from src.data_generator import CANDataGenerator
    from src.scraper import CANDataScraper
    
    # 检查爬虫是否找到在线数据
    scraper = CANDataScraper()
    existing_files = scraper.check_existing_data()
    
    if existing_files:
        logger.info(f"发现 {len(existing_files)} 个已有数据文件")
        generator = CANDataGenerator()
        data = generator.load_data()
        if data is not None:
            logger.info("使用已有数据文件")
            return data
    
    # 生成合成数据
    logger.info("生成新能源汽车CAN合成数据...")
    generator = CANDataGenerator(
        num_vehicles=5,
        records_per_vehicle=10000,
        random_seed=42
    )
    
    data = generator.generate_all_data()
    file_path = generator.save_data(data)
    
    print(f"\n✓ 数据生成完成")
    print(f"  文件: {file_path}")
    print(f"  记录数: {len(data)}")
    print(f"  车辆数: {data['vehicle_id'].nunique()}")
    
    return data


def step_2_feature_engineering(data) -> Dict:
    """
    步骤2: 特征工程与用户画像
    
    使用Pandas/Spark进行特征提取和聚合
    """
    print_step(2, 6, "特征工程与用户画像")
    
    from src.spark_features import SparkFeatureEngine, UserProfileBuilder
    from config import DATA_PROCESSED_DIR
    
    # 保存临时CSV
    temp_csv = DATA_PROCESSED_DIR / "temp_can_data.csv"
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    data.to_csv(temp_csv, index=False)
    
    # 创建特征工程引擎（自动选择Pandas或Spark模式）
    logger.info("初始化特征工程引擎...")
    feature_engine = SparkFeatureEngine()
    
    # 加载数据
    logger.info("加载CAN数据...")
    data = feature_engine.load_can_data(temp_csv)
    
    # 添加特征
    logger.info("添加时间特征...")
    data = feature_engine.add_time_features(data)
    
    logger.info("添加派生特征...")
    data = feature_engine.add_derived_features(data)
    
    # 按车辆聚合
    logger.info("按车辆聚合统计...")
    vehicle_stats = feature_engine.aggregate_by_vehicle(data)
    
    # 识别驾驶工况
    logger.info("识别驾驶工况...")
    vehicle_stats = feature_engine.identify_driving_scenario(vehicle_stats)
    
    # 聚类分析
    logger.info("进行聚类分析...")
    vehicle_stats, cluster_centers = feature_engine.cluster_driving_patterns(vehicle_stats)
    
    # 构建用户画像
    logger.info("构建用户画像...")
    profile_builder = UserProfileBuilder()
    profile_df = profile_builder.build_user_profile(vehicle_stats)
    
    # 生成摘要
    summary = profile_builder.generate_profile_summary(profile_df)
    
    # 保存结果
    profile_path = DATA_PROCESSED_DIR / "user_profiles.csv"
    profile_df.to_csv(profile_path, index=False)
    logger.info(f"用户画像已保存: {profile_path}")
    
    stats_path = DATA_PROCESSED_DIR / "vehicle_stats.csv"
    vehicle_stats.to_csv(stats_path, index=False)
    logger.info(f"车辆统计已保存: {stats_path}")
    
    print(f"\n✓ 特征工程完成")
    print(f"  用户画像记录: {len(profile_df)}")
    print(f"  工况分布: {summary.get('scenario_distribution', {})}")
    
    return {
        "profile_df": profile_df,
        "vehicle_stats": vehicle_stats,
        "summary": summary,
    }


def step_3_health_monitoring(data) -> Dict:
    """
    步骤3: 零部件健康度监控
    
    计算各零部件健康评分
    """
    print_step(3, 6, "零部件健康度监控")
    
    from src.health_score import HealthMonitor
    from config import DATA_PROCESSED_DIR
    
    logger.info("初始化健康监控系统...")
    monitor = HealthMonitor()
    
    # 分析车队
    logger.info("分析车队健康状态...")
    reports = monitor.analyze_fleet(data)
    
    # 保存报告
    reports_data = [r.to_dict() for r in reports]
    import pandas as pd
    reports_df = pd.DataFrame(reports_data)
    health_path = DATA_PROCESSED_DIR / "health_reports.csv"
    reports_df.to_csv(health_path, index=False)
    logger.info(f"健康报告已保存: {health_path}")
    
    # 统计
    scores = [r.overall_score for r in reports]
    
    print(f"\n✓ 健康监控完成")
    print(f"  分析车辆: {len(reports)}")
    print(f"  平均健康评分: {sum(scores)/len(scores):.1f}")
    print(f"  评分范围: {min(scores):.1f} - {max(scores):.1f}")
    
    # 显示各车辆评分
    print(f"\n  车辆评分明细:")
    for report in reports:
        print(f"    {report.vehicle_id}: {report.overall_score} ({report.overall_level})")
    
    return {
        "reports": reports,
        "scores": scores,
    }


def step_4_accelerated_test(data) -> Dict:
    """
    步骤4: 加速试验工况转化
    
    提取高负载、高温等极端工况
    """
    print_step(4, 6, "加速试验工况转化")
    
    from src.accel_test import AcceleratedTestConverter
    from config import DATA_PROCESSED_DIR
    
    logger.info("初始化加速试验工况转换器...")
    converter = AcceleratedTestConverter()
    
    # 转换车队数据
    logger.info("转换车队加速耐久工况...")
    profiles = converter.convert_fleet(data)
    
    # 生成测试序列
    test_sequence = converter.generate_test_sequence(profiles)
    
    # 保存结果
    accel_path = DATA_PROCESSED_DIR / "accelerated_test_sequence.csv"
    test_sequence.to_csv(accel_path, index=False)
    logger.info(f"加速试验工况已保存: {accel_path}")
    
    # 统计
    total_segments = len(test_sequence)
    high_value = len(test_sequence[test_sequence["test_value"] == "高价值"])
    total_duration = test_sequence["duration_seconds"].sum() / 60
    
    print(f"\n✓ 加速试验工况转化完成")
    print(f"  总工况段: {total_segments}")
    print(f"  高价值工况: {high_value}")
    print(f"  总时长: {total_duration:.1f} 分钟")
    
    # 显示各类型分布
    type_dist = test_sequence["condition_type"].value_counts()
    print(f"\n  工况类型分布:")
    type_names = {
        "high_load": "高负载",
        "high_temp": "高温",
        "rapid_charge": "急充",
        "rapid_discharge": "急放",
    }
    for seg_type, count in type_dist.items():
        name = type_names.get(seg_type, seg_type)
        print(f"    {name}: {count} 段")
    
    return {
        "profiles": profiles,
        "test_sequence": test_sequence,
    }


def step_5_flink_monitoring(data) -> Dict:
    """
    步骤5: Flink实时监控模拟
    
    模拟实时数据流处理和预警
    """
    print_step(5, 6, "Flink实时监控模拟")
    
    from src.flink_monitor import run_flink_monitoring
    
    logger.info("启动Flink实时监控模拟...")
    
    result = run_flink_monitoring(data)
    
    # 显示结果
    print(f"\n✓ Flink监控模拟完成")
    print(f"  处理记录: {result['process_info']['total_records']}")
    print(f"  处理耗时: {result['process_info']['process_time_seconds']:.2f}秒")
    print(f"  产生窗口: {result['process_info']['total_windows']}")
    
    alert_stats = result["alert_statistics"]
    print(f"\n  预警统计:")
    print(f"    总预警数: {alert_stats['total_alerts']}")
    print(f"    按严重性: {alert_stats['by_severity']}")
    
    # 显示车辆健康摘要
    health_summary = result["vehicle_health_summary"]
    print(f"\n  车辆监控摘要:")
    for vehicle_id, health in health_summary.items():
        print(f"    {vehicle_id}:")
        print(f"      电机温度: {health['avg_motor_temp']}°C")
        print(f"      电池温度: {health['avg_battery_temp']}°C")
        print(f"      电压: {health['avg_voltage']}V")
        print(f"      预警: 严重{health['critical_count']}个, 警告{health['warning_count']}个")
    
    return result


def step_6_generate_report(data, feature_result, health_result, accel_result, flink_result) -> Path:
    """
    步骤6: 生成分析报告
    
    生成综合分析报告
    """
    print_step(6, 6, "生成分析报告")
    
    from config import OUTPUT_REPORTS_DIR
    import pandas as pd
    
    OUTPUT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 生成报告内容
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report_content = f"""
================================================================================
        CAN总线新能源汽车用户画像与零部件健康监控分析报告
================================================================================

生成时间: {report_time}

一、项目概述
--------------------------------------------------------------------------------
本项目基于新能源汽车CAN总线数据，完成以下分析任务：
1. 用户画像构建 - 基于驾驶行为分析8组用户标签
2. 零部件健康监控 - 实时监控电机/电池温度与电压
3. 加速试验工况转化 - 提取高负载、高温等极端工况
4. FastAPI数据服务 - 提供RESTful API接口

二、数据概况
--------------------------------------------------------------------------------
- 总记录数: {len(data)}
- 车辆数量: {data['vehicle_id'].nunique()}
- 车辆列表: {', '.join(data['vehicle_id'].unique())}
- 时间范围: {data['timestamp'].min()} ~ {data['timestamp'].max()}

关键指标统计:
{data[['speed', 'battery_soc', 'motor_temperature', 'battery_temperature']].describe().round(2).to_string()}

三、用户画像分析
--------------------------------------------------------------------------------
"""
    
    # 添加用户画像详情
    profile_df = feature_result["profile_df"]
    summary = feature_result["summary"]
    
    report_content += f"""
驾驶风格分布:
"""
    for scenario, count in summary.get("scenario_distribution", {}).items():
        report_content += f"  - {scenario}: {count}辆\n"
    
    report_content += f"""
用户标签统计:
"""
    for tag, stats in summary.get("tag_statistics", {}).items():
        tag_name = {
            "driving_aggression_index": "驾驶激进指数",
            "ac_dependency": "空调依赖度",
            "charging_preference": "充电偏好",
            "high_temp_exposure": "高温暴露度",
            "rapid_accel_frequency": "急加速频率",
            "braking_intensity": "制动强度",
            "range_anxiety": "续航焦虑度",
        }.get(tag, tag)
        report_content += f"  {tag_name}:\n"
        report_content += f"    平均值: {stats['mean']:.1f}\n"
        report_content += f"    范围: {stats['min']:.1f} - {stats['max']:.1f}\n"
    
    # 添加健康评分详情
    report_content += f"""

四、零部件健康评分
--------------------------------------------------------------------------------
"""
    
    reports = health_result["reports"]
    for report in reports:
        report_content += f"""
{report.vehicle_id}:
  综合评分: {report.overall_score} ({report.overall_level})
  电机健康: {report.component_scores.get('motor', 'N/A')}
  电池健康: {report.component_scores.get('battery', 'N/A')}
  运行模式: {report.component_scores.get('operation', 'N/A')}
  摘要: {report.summary}
"""
    
    # 添加加速试验详情
    report_content += f"""

五、加速试验工况
--------------------------------------------------------------------------------
"""
    
    test_sequence = accel_result["test_sequence"]
    type_dist = test_sequence["condition_type"].value_counts()
    
    report_content += f"""
总工况段数: {len(test_sequence)}
总测试时长: {test_sequence['duration_seconds'].sum()/60:.1f} 分钟
高价值工况: {len(test_sequence[test_sequence['test_value'] == '高价值'])} 段

工况类型分布:
"""
    type_names = {"high_load": "高负载", "high_temp": "高温", "rapid_charge": "急充", "rapid_discharge": "急放"}
    for seg_type, count in type_dist.items():
        name = type_names.get(seg_type, seg_type)
        report_content += f"  - {name}: {count}段\n"
    
    # 添加Flink监控详情
    report_content += f"""

六、Flink实时监控结果
--------------------------------------------------------------------------------
"""
    
    flink_stats = flink_result["alert_statistics"]
    report_content += f"""
处理记录: {flink_result['process_info']['total_records']}
处理耗时: {flink_result['process_info']['process_time_seconds']:.2f}秒
产生窗口: {flink_result['process_info']['total_windows']}

预警统计:
  总预警数: {flink_stats['total_alerts']}
  严重预警: {flink_stats['by_severity'].get('critical', 0)}
  警告预警: {flink_stats['by_severity'].get('warning', 0)}
  信息预警: {flink_stats['by_severity'].get('info', 0)}

预警类型分布:
"""
    for alert_type, count in flink_stats["by_type"].items():
        report_content += f"  - {alert_type}: {count}\n"
    
    # 添加API端点说明
    report_content += f"""

七、API服务
--------------------------------------------------------------------------------
启动FastAPI服务后可访问以下端点:

GET /api/v1/data/overview          - 数据概览
GET /api/v1/user-profile/{{vehicle_id}}  - 用户画像查询
GET /api/v1/health-score/{{vehicle_id}}  - 健康评分查询
GET /api/v1/alerts                  - 预警列表
GET /api/v1/driving-scenario/{{vehicle_id}} - 驾驶工况
GET /api/v1/accelerated-test/{{vehicle_id}} - 加速试验工况
GET /api/v1/system/status           - 系统状态

API文档: http://localhost:8000/docs

八、项目结构
--------------------------------------------------------------------------------
CAN_User_Profile_Health/
├── README.md                    # 项目说明文档
├── requirements.txt             # 依赖清单
├── config.py                    # 项目配置
├── main.py                      # 一键运行入口
├── src/
│   ├── scraper.py               # 爬虫数据获取
│   ├── data_generator.py       # 合成数据生成
│   ├── spark_features.py       # PySpark特征工程
│   ├── flink_monitor.py        # PyFlink实时监控
│   ├── health_score.py         # 健康度评分模型
│   ├── accel_test.py           # 加速试验工况转化
│   └── api_service.py          # FastAPI数据服务
├── data/
│   ├── raw/                    # 原始数据
│   └── processed/              # 处理后数据
├── output/
│   ├── figures/                # 可视化图表
│   └── reports/                # 分析报告
└── app.py                       # Streamlit可视化系统

================================================================================
                              报告结束
================================================================================
"""
    
    # 保存报告
    report_path = OUTPUT_REPORTS_DIR / f"analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    logger.info(f"分析报告已保存: {report_path}")
    
    print(f"\n✓ 分析报告生成完成")
    print(f"  报告路径: {report_path}")
    
    return report_path


def run_pipeline():
    """运行完整分析流程"""
    start_time = time.time()
    
    print_header("CAN总线新能源汽车用户画像与零部件健康监控系统")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 步骤1: 数据获取
        data = step_1_data_acquisition()
        if data is None:
            logger.error("数据获取失败")
            return
        
        # 步骤2: 特征工程与用户画像
        feature_result = step_2_feature_engineering(data)
        
        # 步骤3: 健康度监控
        health_result = step_3_health_monitoring(data)
        
        # 步骤4: 加速试验工况转化
        accel_result = step_4_accelerated_test(data)
        
        # 步骤5: Flink实时监控
        flink_result = step_5_flink_monitoring(data)
        
        # 步骤6: 生成报告
        report_path = step_6_generate_report(
            data, feature_result, health_result, accel_result, flink_result
        )
        
        # 完成
        total_time = time.time() - start_time
        
        print_header("分析完成")
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"总耗时: {total_time:.2f} 秒 ({total_time/60:.1f} 分钟)")
        print(f"分析报告: {report_path}")
        print(f"\n启动API服务: python -m src.api_service")
        print(f"启动可视化: streamlit run app.py --server.port 8501")
        
    except Exception as e:
        logger.error(f"分析流程出错: {e}", exc_info=True)
        print(f"\n错误: {e}")
        raise


if __name__ == "__main__":
    run_pipeline()
