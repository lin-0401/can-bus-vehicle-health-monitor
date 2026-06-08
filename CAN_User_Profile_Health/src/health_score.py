"""
CAN总线新能源汽车用户画像与健康监控系统
零部件健康度评分模型

功能：
1. 基于温度、电压等信号计算零部件健康度
2. 综合评分模型 (0-100分)
3. 健康状态等级划分
4. 历史趋势分析
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import pandas as pd
import numpy as np

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import HEALTH_SCORE_CONFIG, DATA_PROCESSED_DIR


class HealthLevel(Enum):
    """健康等级枚举"""
    EXCELLENT = "优秀"
    GOOD = "良好"
    NORMAL = "正常"
    WARNING = "警告"
    CRITICAL = "危险"


@dataclass
class ComponentHealth:
    """零部件健康状态"""
    component_name: str
    health_score: float       # 健康评分 (0-100)
    health_level: str         # 健康等级
    metrics: Dict[str, float] # 各项指标得分
    warnings: List[str]      # 警告信息
    recommendations: List[str]  # 建议


@dataclass  
class VehicleHealthReport:
    """车辆健康报告"""
    vehicle_id: str
    overall_score: float      # 综合健康评分
    overall_level: str        # 综合健康等级
    component_scores: Dict[str, float]  # 各零部件评分
    report_time: str          # 报告时间
    critical_alerts: List[str]  # 严重警告
    summary: str              # 健康摘要
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "vehicle_id": self.vehicle_id,
            "overall_score": self.overall_score,
            "overall_level": self.overall_level,
            "component_scores": self.component_scores,
            "report_time": self.report_time,
            "critical_alerts": self.critical_alerts,
            "summary": self.summary,
        }


class HealthScorer:
    """健康度评分器"""
    
    def __init__(self):
        """初始化评分器"""
        self.config = HEALTH_SCORE_CONFIG
        self.weights = self.config["weights"]
    
    def _get_motor_temp_score(self, avg_temp: float, max_temp: float) -> Tuple[float, List[str], List[str]]:
        """
        计算电机温度得分
        
        Args:
            avg_temp: 平均温度
            max_temp: 最高温度
        
        Returns:
            (得分, 警告列表, 建议列表)
        """
        warnings = []
        recommendations = []
        
        # 获取阈值
        normal_max = self.config["motor_temp"]["normal_max"]
        warning_max = self.config["motor_temp"]["warning_max"]
        critical_max = self.config["motor_temp"]["critical_max"]
        
        # 基础得分
        if avg_temp <= normal_max:
            score = 100 - (avg_temp / normal_max) * 20
        elif avg_temp <= warning_max:
            score = 80 - ((avg_temp - normal_max) / (warning_max - normal_max)) * 30
        else:
            score = 50 - min(50, ((avg_temp - warning_max) / (critical_max - warning_max)) * 50)
        
        # 检查最高温度
        if max_temp > warning_max:
            warnings.append(f"电机最高温度{max_temp:.1f}°C超过正常范围")
            recommendations.append("建议检查电机散热系统")
        
        if max_temp > critical_max:
            warnings.append(f"电机温度严重过高: {max_temp:.1f}°C")
            recommendations.append("建议立即停车检查，等待冷却后联系维修")
        
        return (max(0, min(100, score)), warnings, recommendations)
    
    def _get_battery_temp_score(
        self, 
        avg_temp: float, 
        max_temp: float,
        avg_voltage: float,
        min_voltage: float,
        max_voltage: float
    ) -> Tuple[float, List[str], List[str]]:
        """
        计算电池健康得分
        
        Args:
            avg_temp: 平均温度
            max_temp: 最高温度
            avg_voltage: 平均电压
            min_voltage: 最低电压
            max_voltage: 最高电压
        
        Returns:
            (得分, 警告列表, 建议列表)
        """
        warnings = []
        recommendations = []
        
        # 温度评分
        temp_normal_max = self.config["battery_temp"]["normal_max"]
        temp_warning_max = self.config["battery_temp"]["warning_max"]
        temp_critical_max = self.config["battery_temp"]["critical_max"]
        
        if avg_temp <= temp_normal_max:
            temp_score = 100 - (avg_temp / temp_normal_max) * 15
        elif avg_temp <= temp_warning_max:
            temp_score = 85 - ((avg_temp - temp_normal_max) / (temp_warning_max - temp_normal_max)) * 35
        else:
            temp_score = 50 - min(50, ((avg_temp - temp_warning_max) / (temp_critical_max - temp_warning_max)) * 50)
        
        # 电压评分
        voltage_normal_min = self.config["battery_voltage"]["normal_min"]
        voltage_normal_max = self.config["battery_voltage"]["normal_max"]
        voltage_warning_min = self.config["battery_voltage"]["warning_min"]
        voltage_warning_max = self.config["battery_voltage"]["warning_max"]
        
        # 电压偏离度
        voltage_mid = (voltage_normal_min + voltage_normal_max) / 2
        voltage_range = (voltage_normal_max - voltage_normal_min) / 2
        
        voltage_deviation = abs(avg_voltage - voltage_mid) / voltage_range
        voltage_score = 100 - voltage_deviation * 30
        
        # 检查电压异常
        if min_voltage < voltage_warning_min:
            warnings.append(f"电池最低电压{min_voltage:.1f}V过低")
            recommendations.append("建议尽快充电，避免深度放电")
            voltage_score -= 20
        
        if max_voltage > voltage_warning_max:
            warnings.append(f"电池最高电压{max_voltage:.1f}V过高")
            recommendations.append("建议降低充电电流，避免过充")
            voltage_score -= 20
        
        # 温度警告
        if max_temp > temp_warning_max:
            warnings.append(f"电池最高温度{max_temp:.1f}°C超过正常范围")
            recommendations.append("建议检查电池冷却系统")
        
        if max_temp > temp_critical_max:
            warnings.append(f"电池温度严重过高: {max_temp:.1f}°C")
            recommendations.append("建议立即停车，等待冷却")
        
        # 综合评分
        combined_score = temp_score * 0.6 + max(0, voltage_score) * 0.4
        
        return (max(0, min(100, combined_score)), warnings, recommendations)
    
    def _get_operation_pattern_score(
        self,
        avg_throttle: float,
        max_throttle: float,
        avg_brake: float,
        avg_speed: float
    ) -> Tuple[float, List[str], List[str]]:
        """
        计算运行模式得分
        
        Args:
            avg_throttle: 平均油门
            max_throttle: 最大油门
            avg_brake: 平均刹车
            avg_speed: 平均速度
        
        Returns:
            (得分, 警告列表, 建议列表)
        """
        warnings = []
        recommendations = []
        
        # 激进驾驶评分
        # 高油门比例
        high_throttle_ratio = max_throttle / 100.0
        
        # 刹车频繁度
        brake_frequency = avg_brake / 100.0
        
        # 速度稳定性
        speed_score = 100 - min(30, avg_speed / 5)  # 速度越高评分略低
        
        # 驾驶激进度
        aggression_score = 100 - (high_throttle_ratio * 30 + brake_frequency * 20)
        
        # 综合得分
        pattern_score = (aggression_score * 0.5 + speed_score * 0.5)
        
        # 警告和建议
        if high_throttle_ratio > 0.8:
            warnings.append("检测到频繁急加速")
            recommendations.append("建议温和驾驶以延长零部件寿命")
        
        if brake_frequency > 0.5:
            warnings.append("刹车使用频率较高")
            recommendations.append("建议预判路况，减少紧急制动")
        
        if avg_speed > 120:
            warnings.append("长时间高速行驶")
            recommendations.append("建议适时休息，降低高速巡航时间")
        
        return (max(0, min(100, pattern_score)), warnings, recommendations)
    
    def calculate_component_scores(
        self,
        avg_motor_temp: float,
        max_motor_temp: float,
        avg_battery_temp: float,
        max_battery_temp: float,
        avg_battery_voltage: float,
        min_battery_voltage: float,
        max_battery_voltage: float,
        avg_throttle: float,
        max_throttle: float,
        avg_brake: float,
        avg_speed: float
    ) -> Dict[str, ComponentHealth]:
        """
        计算各零部件健康得分
        
        Args:
            各信号统计数据
        
        Returns:
            零部件健康状态字典
        """
        components = {}
        
        # 电机健康
        motor_score, motor_warnings, motor_recs = self._get_motor_temp_score(
            avg_motor_temp, max_motor_temp
        )
        motor_level = self._score_to_level(motor_score)
        components["motor"] = ComponentHealth(
            component_name="驱动电机",
            health_score=round(motor_score, 2),
            health_level=motor_level.value,
            metrics={
                "avg_temperature": avg_motor_temp,
                "max_temperature": max_motor_temp,
                "temp_score": motor_score,
            },
            warnings=motor_warnings,
            recommendations=motor_recs
        )
        
        # 电池健康
        battery_score, battery_warnings, battery_recs = self._get_battery_temp_score(
            avg_battery_temp, max_battery_temp,
            avg_battery_voltage, min_battery_voltage, max_battery_voltage
        )
        battery_level = self._score_to_level(battery_score)
        components["battery"] = ComponentHealth(
            component_name="动力电池",
            health_score=round(battery_score, 2),
            health_level=battery_level.value,
            metrics={
                "avg_temperature": avg_battery_temp,
                "max_temperature": max_battery_temp,
                "avg_voltage": avg_battery_voltage,
                "voltage_score": battery_score,
            },
            warnings=battery_warnings,
            recommendations=battery_recs
        )
        
        # 运行模式
        pattern_score, pattern_warnings, pattern_recs = self._get_operation_pattern_score(
            avg_throttle, max_throttle, avg_brake, avg_speed
        )
        pattern_level = self._score_to_level(pattern_score)
        components["operation"] = ComponentHealth(
            component_name="运行模式",
            health_score=round(pattern_score, 2),
            health_level=pattern_level.value,
            metrics={
                "avg_throttle": avg_throttle,
                "max_throttle": max_throttle,
                "avg_brake": avg_brake,
                "avg_speed": avg_speed,
            },
            warnings=pattern_warnings,
            recommendations=pattern_recs
        )
        
        return components
    
    def _score_to_level(self, score: float) -> HealthLevel:
        """
        将评分转换为健康等级
        
        Args:
            score: 健康评分
        
        Returns:
            健康等级
        """
        if score >= 90:
            return HealthLevel.EXCELLENT
        elif score >= 80:
            return HealthLevel.GOOD
        elif score >= 60:
            return HealthLevel.NORMAL
        elif score >= 40:
            return HealthLevel.WARNING
        else:
            return HealthLevel.CRITICAL
    
    def calculate_overall_score(self, components: Dict[str, ComponentHealth]) -> Tuple[float, str]:
        """
        计算综合健康评分
        
        Args:
            components: 零部件健康状态
        
        Returns:
            (综合评分, 综合等级)
        """
        weights = {
            "motor": self.weights["motor_temp"],
            "battery": self.weights["battery_temp"] + self.weights["battery_voltage"],
            "operation": self.weights["operation_pattern"],
        }
        
        total_score = 0
        total_weight = 0
        
        for name, weight in weights.items():
            if name in components:
                total_score += components[name].health_score * weight
                total_weight += weight
        
        overall_score = total_score / total_weight if total_weight > 0 else 0
        overall_level = self._score_to_level(overall_score).value
        
        return (round(overall_score, 2), overall_level)
    
    def generate_health_report(
        self,
        vehicle_id: str,
        avg_motor_temp: float,
        max_motor_temp: float,
        avg_battery_temp: float,
        max_battery_temp: float,
        avg_battery_voltage: float,
        min_battery_voltage: float,
        max_battery_voltage: float,
        avg_throttle: float,
        max_throttle: float,
        avg_brake: float,
        avg_speed: float
    ) -> VehicleHealthReport:
        """
        生成车辆健康报告
        
        Args:
            各信号统计数据
        
        Returns:
            车辆健康报告
        """
        # 计算零部件得分
        components = self.calculate_component_scores(
            avg_motor_temp, max_motor_temp,
            avg_battery_temp, max_battery_temp,
            avg_battery_voltage, min_battery_voltage, max_battery_voltage,
            avg_throttle, max_throttle, avg_brake, avg_speed
        )
        
        # 计算综合得分
        overall_score, overall_level = self.calculate_overall_score(components)
        
        # 收集所有警告
        all_warnings = []
        for name, component in components.items():
            all_warnings.extend(component.warnings)
        
        # 生成摘要
        summary_parts = [
            f"综合健康评分{overall_score:.0f}分",
            f"等级{overall_level}",
        ]
        
        if components["motor"].health_score < 70:
            summary_parts.append("电机状态需关注")
        if components["battery"].health_score < 70:
            summary_parts.append("电池状态需关注")
        if components["operation"].health_score < 70:
            summary_parts.append("建议改善驾驶习惯")
        
        summary = "，".join(summary_parts) if summary_parts else "各系统运行正常"
        
        return VehicleHealthReport(
            vehicle_id=vehicle_id,
            overall_score=overall_score,
            overall_level=overall_level,
            component_scores={
                "motor": components["motor"].health_score,
                "battery": components["battery"].health_score,
                "operation": components["operation"].health_score,
            },
            report_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            critical_alerts=all_warnings,
            summary=summary,
        )


class HealthMonitor:
    """健康监控系统"""
    
    def __init__(self):
        """初始化健康监控"""
        self.scorer = HealthScorer()
        self.history: Dict[str, List[VehicleHealthReport]] = {}
    
    def analyze_vehicle(self, vehicle_data: pd.DataFrame) -> VehicleHealthReport:
        """
        分析单辆车健康状态
        
        Args:
            vehicle_data: 单辆车数据
        
        Returns:
            健康报告
        """
        vehicle_id = vehicle_data["vehicle_id"].iloc[0]
        
        # 计算统计指标
        stats = {
            "avg_motor_temp": vehicle_data["motor_temperature"].mean(),
            "max_motor_temp": vehicle_data["motor_temperature"].max(),
            "avg_battery_temp": vehicle_data["battery_temperature"].mean(),
            "max_battery_temp": vehicle_data["battery_temperature"].max(),
            "avg_battery_voltage": vehicle_data["battery_voltage"].mean(),
            "min_battery_voltage": vehicle_data["battery_voltage"].min(),
            "max_battery_voltage": vehicle_data["battery_voltage"].max(),
            "avg_throttle": vehicle_data["throttle"].mean(),
            "max_throttle": vehicle_data["throttle"].max(),
            "avg_brake": vehicle_data["brake"].mean(),
            "avg_speed": vehicle_data["speed"].mean(),
        }
        
        # 生成报告
        report = self.scorer.generate_health_report(
            vehicle_id=vehicle_id,
            **stats
        )
        
        # 保存历史
        if vehicle_id not in self.history:
            self.history[vehicle_id] = []
        self.history[vehicle_id].append(report)
        
        return report
    
    def analyze_fleet(self, data: pd.DataFrame) -> List[VehicleHealthReport]:
        """
        分析车队健康状态
        
        Args:
            data: 所有车辆数据
        
        Returns:
            健康报告列表
        """
        reports = []
        
        for vehicle_id in data["vehicle_id"].unique():
            vehicle_data = data[data["vehicle_id"] == vehicle_id]
            report = self.analyze_vehicle(vehicle_data)
            reports.append(report)
            logger.info(f"车辆 {vehicle_id} 健康评分: {report.overall_score}")
        
        return reports
    
    def get_trend_analysis(self, vehicle_id: str) -> Optional[Dict]:
        """
        获取车辆健康趋势分析
        
        Args:
            vehicle_id: 车辆ID
        
        Returns:
            趋势分析字典
        """
        if vehicle_id not in self.history or len(self.history[vehicle_id]) < 2:
            return None
        
        reports = self.history[vehicle_id]
        
        # 计算趋势
        scores = [r.overall_score for r in reports]
        first_score = scores[0]
        last_score = scores[-1]
        trend = "stable"
        
        if last_score - first_score > 5:
            trend = "improving"
        elif first_score - last_score > 5:
            trend = "declining"
        
        return {
            "vehicle_id": vehicle_id,
            "report_count": len(reports),
            "first_score": first_score,
            "last_score": last_score,
            "score_change": round(last_score - first_score, 2),
            "trend": trend,
            "average_score": round(np.mean(scores), 2),
        }


def main():
    """主函数 - 测试健康度评分"""
    print("=" * 60)
    print("零部件健康度评分模型测试")
    print("=" * 60)
    
    # 导入数据
    from src.data_generator import CANDataGenerator
    
    generator = CANDataGenerator(num_vehicles=3, records_per_vehicle=5000)
    data = generator.load_data()
    
    if data is None:
        print("生成测试数据...")
        data = generator.generate_all_data()
    
    print(f"\n数据概况: {len(data)} 条记录")
    
    # 创建健康监控
    monitor = HealthMonitor()
    
    # 分析车队
    print("\n分析车队健康状态...")
    reports = monitor.analyze_fleet(data)
    
    # 显示结果
    print("\n" + "-" * 50)
    print("车队健康报告汇总")
    print("-" * 50)
    
    for report in reports:
        print(f"\n【{report.vehicle_id}】")
        print(f"  综合评分: {report.overall_score} ({report.overall_level})")
        print(f"  电机健康: {report.component_scores['motor']}")
        print(f"  电池健康: {report.component_scores['battery']}")
        print(f"  运行模式: {report.component_scores['operation']}")
        
        if report.critical_alerts:
            print(f"  警告信息:")
            for alert in report.critical_alerts[:3]:
                print(f"    - {alert}")
        
        print(f"  摘要: {report.summary}")
    
    # 统计摘要
    scores = [r.overall_score for r in reports]
    print(f"\n车队整体统计:")
    print(f"  平均评分: {np.mean(scores):.2f}")
    print(f"  最高评分: {np.max(scores):.2f}")
    print(f"  最低评分: {np.min(scores):.2f}")
    
    # 保存报告
    reports_data = [r.to_dict() for r in reports]
    reports_df = pd.DataFrame(reports_data)
    output_path = DATA_PROCESSED_DIR / "health_reports.csv"
    reports_df.to_csv(output_path, index=False)
    print(f"\n健康报告已保存: {output_path}")
    
    print("\n" + "=" * 60)
    print("健康度评分测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
