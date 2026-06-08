"""
CAN总线新能源汽车用户画像与健康监控系统
PyFlink窗口聚合实时监控模块

功能：
1. 模拟实时数据流处理
2. 滑动窗口聚合（温度、电压、电流等）
3. 异常检测与实时预警
4. 健康度实时评分
"""

import sys
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Iterator
from dataclasses import dataclass, field
from collections import deque

import pandas as pd
import numpy as np

# 尝试导入Flink
try:
    from pyflink.datastream import StreamExecutionEnvironment
    from pyflink.datastream.window import TumblingEventTimeWindows, Time
    from pyflink.common.typeinfo import Types, RowTypeInfo
    from pyflink.common import Row
    HAS_FLINK = True
except ImportError:
    HAS_FLINK = False
    print("警告: PyFlink未安装，将使用模拟模式运行")

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    FLINK_CONFIG, HEALTH_SCORE_CONFIG, ALERT_RULES, DATA_RAW_DIR
)


@dataclass
class CANSignal:
    """CAN信号数据结构"""
    timestamp: str
    vehicle_id: str
    speed: float
    throttle: float
    brake: float
    battery_soc: float
    battery_voltage: float
    battery_current: float
    battery_temperature: float
    motor_temperature: float
    motor_rpm: float
    motor_torque: float
    cabin_temperature: float
    ac_power: float


@dataclass
class Alert:
    """预警数据结构"""
    timestamp: str
    vehicle_id: str
    alert_type: str
    alert_name: str
    severity: str
    value: float
    threshold: float
    unit: str
    message: str


@dataclass
class WindowAggregate:
    """窗口聚合结果"""
    vehicle_id: str
    window_start: str
    window_end: str
    record_count: int
    
    # 温度统计
    avg_motor_temp: float
    max_motor_temp: float
    avg_battery_temp: float
    max_battery_temp: float
    
    # 电压统计
    avg_battery_voltage: float
    min_battery_voltage: float
    max_battery_voltage: float
    voltage_std: float
    
    # 电流统计
    avg_battery_current: float
    max_battery_current: float
    
    # 健康相关
    avg_speed: float
    avg_throttle: float
    avg_brake: float
    
    # 预警计数
    alert_count: int = 0


class DataStreamSimulator:
    """数据流模拟器 - 模拟实时CAN数据流"""
    
    def __init__(self, data: pd.DataFrame, replay_speed: float = 100.0):
        """
        初始化数据流模拟器
        
        Args:
            data: 原始CAN数据
            replay_speed: 回放速度倍数(默认100倍)
        """
        self.data = data
        self.replay_speed = replay_speed
        self.current_index = 0
        
        # 预计算时间间隔
        self.interval_ms = 100  # 采样间隔
    
    def __iter__(self) -> Iterator[CANSignal]:
        """迭代器协议"""
        for _, row in self.data.iterrows():
            yield CANSignal(
                timestamp=row["timestamp"],
                vehicle_id=row["vehicle_id"],
                speed=float(row["speed"]),
                throttle=float(row["throttle"]),
                brake=float(row["brake"]),
                battery_soc=float(row["battery_soc"]),
                battery_voltage=float(row["battery_voltage"]),
                battery_current=float(row["battery_current"]),
                battery_temperature=float(row["battery_temperature"]),
                motor_temperature=float(row["motor_temperature"]),
                motor_rpm=float(row["motor_rpm"]),
                motor_torque=float(row["motor_torque"]),
                cabin_temperature=float(row["cabin_temperature"]),
                ac_power=float(row["ac_power"]),
            )
    
    def get_batch(self, batch_size: int = 100) -> List[CANSignal]:
        """获取一批数据"""
        batch = []
        for _ in range(batch_size):
            if self.current_index >= len(self.data):
                break
            
            row = self.data.iloc[self.current_index]
            batch.append(CANSignal(
                timestamp=row["timestamp"],
                vehicle_id=row["vehicle_id"],
                speed=float(row["speed"]),
                throttle=float(row["throttle"]),
                brake=float(row["brake"]),
                battery_soc=float(row["battery_soc"]),
                battery_voltage=float(row["battery_voltage"]),
                battery_current=float(row["battery_current"]),
                battery_temperature=float(row["battery_temperature"]),
                motor_temperature=float(row["motor_temperature"]),
                motor_rpm=float(row["motor_rpm"]),
                motor_torque=float(row["motor_torque"]),
                cabin_temperature=float(row["cabin_temperature"]),
                ac_power=float(row["ac_power"]),
            ))
            self.current_index += 1
        
        return batch


class AlertDetector:
    """预警检测器"""
    
    def __init__(self):
        """初始化预警规则"""
        self.alert_rules = ALERT_RULES
    
    def check_signal(self, signal: CANSignal) -> List[Alert]:
        """
        检查单条信号是否触发预警
        
        Args:
            signal: CAN信号
        
        Returns:
            触发的预警列表
        """
        alerts = []
        
        # 电机过热预警
        if signal.motor_temperature > self.alert_rules["motor_overheat"]["threshold"]:
            alerts.append(Alert(
                timestamp=signal.timestamp,
                vehicle_id=signal.vehicle_id,
                alert_type="motor_overheat",
                alert_name=self.alert_rules["motor_overheat"]["name"],
                severity=self.alert_rules["motor_overheat"]["severity"],
                value=signal.motor_temperature,
                threshold=self.alert_rules["motor_overheat"]["threshold"],
                unit="°C",
                message=f"车辆{signal.vehicle_id}电机温度{signal.motor_temperature:.1f}°C超过{self.alert_rules['motor_overheat']['threshold']}°C"
            ))
        
        # 电机严重过热
        if signal.motor_temperature > self.alert_rules["motor_critical"]["threshold"]:
            alerts.append(Alert(
                timestamp=signal.timestamp,
                vehicle_id=signal.vehicle_id,
                alert_type="motor_critical",
                alert_name=self.alert_rules["motor_critical"]["name"],
                severity=self.alert_rules["motor_critical"]["severity"],
                value=signal.motor_temperature,
                threshold=self.alert_rules["motor_critical"]["threshold"],
                unit="°C",
                message=f"【严重】车辆{signal.vehicle_id}电机温度{signal.motor_temperature:.1f}°C超过{self.alert_rules['motor_critical']['threshold']}°C，请立即检查！"
            ))
        
        # 电池过热预警
        if signal.battery_temperature > self.alert_rules["battery_overheat"]["threshold"]:
            alerts.append(Alert(
                timestamp=signal.timestamp,
                vehicle_id=signal.vehicle_id,
                alert_type="battery_overheat",
                alert_name=self.alert_rules["battery_overheat"]["name"],
                severity=self.alert_rules["battery_overheat"]["severity"],
                value=signal.battery_temperature,
                threshold=self.alert_rules["battery_overheat"]["threshold"],
                unit="°C",
                message=f"车辆{signal.vehicle_id}电池温度{signal.battery_temperature:.1f}°C超过{self.alert_rules['battery_overheat']['threshold']}°C"
            ))
        
        # 电池严重过热
        if signal.battery_temperature > self.alert_rules["battery_critical"]["threshold"]:
            alerts.append(Alert(
                timestamp=signal.timestamp,
                vehicle_id=signal.vehicle_id,
                alert_type="battery_critical",
                alert_name=self.alert_rules["battery_critical"]["name"],
                severity=self.alert_rules["battery_critical"]["severity"],
                value=signal.battery_temperature,
                threshold=self.alert_rules["battery_critical"]["threshold"],
                unit="°C",
                message=f"【严重】车辆{signal.vehicle_id}电池温度{signal.battery_temperature:.1f}°C超过{self.alert_rules['battery_critical']['threshold']}°C"
            ))
        
        # 电压过低
        if signal.battery_voltage < self.alert_rules["voltage_low"]["threshold"]:
            alerts.append(Alert(
                timestamp=signal.timestamp,
                vehicle_id=signal.vehicle_id,
                alert_type="voltage_low",
                alert_name=self.alert_rules["voltage_low"]["name"],
                severity=self.alert_rules["voltage_low"]["severity"],
                value=signal.battery_voltage,
                threshold=self.alert_rules["voltage_low"]["threshold"],
                unit="V",
                message=f"车辆{signal.vehicle_id}电池电压{signal.battery_voltage:.1f}V低于{self.alert_rules['voltage_low']['threshold']}V"
            ))
        
        # 电压过高
        if signal.battery_voltage > self.alert_rules["voltage_high"]["threshold"]:
            alerts.append(Alert(
                timestamp=signal.timestamp,
                vehicle_id=signal.vehicle_id,
                alert_type="voltage_high",
                alert_name=self.alert_rules["voltage_high"]["name"],
                severity=self.alert_rules["voltage_high"]["severity"],
                value=signal.battery_voltage,
                threshold=self.alert_rules["voltage_high"]["threshold"],
                unit="V",
                message=f"车辆{signal.vehicle_id}电池电压{signal.battery_voltage:.1f}V超过{self.alert_rules['voltage_high']['threshold']}V"
            ))
        
        # 低电量警告
        if signal.battery_soc < self.alert_rules["low_soc_warning"]["threshold"]:
            alerts.append(Alert(
                timestamp=signal.timestamp,
                vehicle_id=signal.vehicle_id,
                alert_type="low_soc_warning",
                alert_name=self.alert_rules["low_soc_warning"]["name"],
                severity=self.alert_rules["low_soc_warning"]["severity"],
                value=signal.battery_soc,
                threshold=self.alert_rules["low_soc_warning"]["threshold"],
                unit="%",
                message=f"车辆{signal.vehicle_id}电量{signal.battery_soc:.1f}%低于{self.alert_rules['low_soc_warning']['threshold']}%"
            ))
        
        # 低电量严重警告
        if signal.battery_soc < self.alert_rules["low_soc_critical"]["threshold"]:
            alerts.append(Alert(
                timestamp=signal.timestamp,
                vehicle_id=signal.vehicle_id,
                alert_type="low_soc_critical",
                alert_name=self.alert_rules["low_soc_critical"]["name"],
                severity=self.alert_rules["low_soc_critical"]["severity"],
                value=signal.battery_soc,
                threshold=self.alert_rules["low_soc_critical"]["threshold"],
                unit="%",
                message=f"【严重】车辆{signal.vehicle_id}电量{signal.battery_soc:.1f}%低于{self.alert_rules['low_soc_critical']['threshold']}%，请尽快充电！"
            ))
        
        return alerts


class WindowAggregator:
    """滑动窗口聚合器"""
    
    def __init__(
        self,
        window_size_seconds: int = None,
        slide_interval_seconds: int = None
    ):
        """
        初始化窗口聚合器
        
        Args:
            window_size_seconds: 窗口大小(秒)
            slide_interval_seconds: 滑动间隔(秒)
        """
        self.window_size = window_size_seconds or FLINK_CONFIG["window_size_seconds"]
        self.slide_interval = slide_interval_seconds or FLINK_CONFIG["slide_interval_seconds"]
        
        # 按车辆维护窗口缓冲
        self.buffers: Dict[str, deque] = {}
    
    def add_signal(self, signal: CANSignal) -> Optional[WindowAggregate]:
        """
        添加信号到窗口缓冲区
        
        Args:
            signal: CAN信号
        
        Returns:
            如果窗口闭合则返回聚合结果，否则返回None
        """
        vehicle_id = signal.vehicle_id
        
        # 初始化车辆缓冲区
        if vehicle_id not in self.buffers:
            self.buffers[vehicle_id] = deque()
        
        # 添加信号到缓冲区
        self.buffers[vehicle_id].append(signal)
        
        # 检查窗口是否闭合(达到窗口大小)
        window_capacity = int(self.window_size * 1000 / 100)  # 假设100ms采样
        
        if len(self.buffers[vehicle_id]) >= window_capacity:
            # 计算窗口聚合
            aggregate = self._calculate_aggregate(vehicle_id)
            
            # 滑动窗口：移除旧数据
            slide_count = int(self.slide_interval * 1000 / 100)
            for _ in range(min(slide_count, len(self.buffers[vehicle_id]))):
                if len(self.buffers[vehicle_id]) > 0:
                    self.buffers[vehicle_id].popleft()
            
            return aggregate
        
        return None
    
    def _calculate_aggregate(self, vehicle_id: str) -> WindowAggregate:
        """
        计算窗口聚合结果
        
        Args:
            vehicle_id: 车辆ID
        
        Returns:
            窗口聚合结果
        """
        buffer = self.buffers[vehicle_id]
        
        timestamps = [s.timestamp for s in buffer]
        motor_temps = [s.motor_temperature for s in buffer]
        battery_temps = [s.battery_temperature for s in buffer]
        voltages = [s.battery_voltage for s in buffer]
        currents = [s.battery_current for s in buffer]
        speeds = [s.speed for s in buffer]
        throttles = [s.throttle for s in buffer]
        brakes = [s.brake for s in buffer]
        
        return WindowAggregate(
            vehicle_id=vehicle_id,
            window_start=timestamps[0],
            window_end=timestamps[-1],
            record_count=len(buffer),
            avg_motor_temp=round(np.mean(motor_temps), 2),
            max_motor_temp=round(np.max(motor_temps), 2),
            avg_battery_temp=round(np.mean(battery_temps), 2),
            max_battery_temp=round(np.max(battery_temps), 2),
            avg_battery_voltage=round(np.mean(voltages), 2),
            min_battery_voltage=round(np.min(voltages), 2),
            max_battery_voltage=round(np.max(voltages), 2),
            voltage_std=round(np.std(voltages), 2),
            avg_battery_current=round(np.mean(currents), 2),
            max_battery_current=round(np.max(currents), 2),
            avg_speed=round(np.mean(speeds), 2),
            avg_throttle=round(np.mean(throttles), 2),
            avg_brake=round(np.mean(brakes), 2),
        )


class FlinkMonitorSimulator:
    """Flink监控模拟器 - 模拟PyFlink实时处理流程"""
    
    def __init__(
        self,
        data: pd.DataFrame,
        window_size_seconds: int = None,
        slide_interval_seconds: int = None
    ):
        """
        初始化监控模拟器
        
        Args:
            data: CAN数据
            window_size_seconds: 窗口大小
            slide_interval_seconds: 滑动间隔
        """
        self.data = data
        self.window_size = window_size_seconds or FLINK_CONFIG["window_size_seconds"]
        self.slide_interval = slide_interval_seconds or FLINK_CONFIG["slide_interval_seconds"]
        
        # 初始化组件
        self.stream_simulator = DataStreamSimulator(data)
        self.alert_detector = AlertDetector()
        self.window_aggregator = WindowAggregator(
            window_size_seconds=self.window_size,
            slide_interval_seconds=self.slide_interval
        )
        
        # 结果存储
        self.all_alerts: List[Alert] = []
        self.all_aggregates: List[WindowAggregate] = []
        self.processed_count = 0
    
    def process_stream(self) -> Tuple[List[Alert], List[WindowAggregate]]:
        """
        处理数据流
        
        Returns:
            (预警列表, 窗口聚合列表)
        """
        logger.info(f"开始处理数据流: {len(self.data)} 条记录")
        logger.info(f"窗口配置: {self.window_size}秒窗口, {self.slide_interval}秒滑动")
        
        batch_size = 100
        batch_count = 0
        
        for signal in self.stream_simulator:
            self.processed_count += 1
            
            # 检测预警
            alerts = self.alert_detector.check_signal(signal)
            if alerts:
                self.all_alerts.extend(alerts)
            
            # 添加到窗口
            aggregate = self.window_aggregator.add_signal(signal)
            if aggregate:
                self.all_aggregates.append(aggregate)
                batch_count += 1
                
                # 定期输出进度
                if batch_count % 50 == 0:
                    logger.info(f"已处理 {self.processed_count} 条记录, 产生 {batch_count} 个窗口")
        
        logger.info(f"处理完成: 共处理 {self.processed_count} 条记录")
        logger.info(f"产生 {len(self.all_alerts)} 条预警, {len(self.all_aggregates)} 个窗口聚合")
        
        return self.all_alerts, self.all_aggregates
    
    def get_vehicle_health_summary(self) -> Dict:
        """
        获取车辆健康摘要
        
        Returns:
            车辆健康状态字典
        """
        summary = {}
        
        for vehicle_id in self.data["vehicle_id"].unique():
            vehicle_alerts = [a for a in self.all_alerts if a.vehicle_id == vehicle_id]
            vehicle_aggregates = [a for a in self.all_aggregates if a.vehicle_id == vehicle_id]
            
            if not vehicle_aggregates:
                continue
            
            # 计算平均健康指标
            avg_motor_temp = np.mean([a.avg_motor_temp for a in vehicle_aggregates])
            avg_battery_temp = np.mean([a.avg_battery_temp for a in vehicle_aggregates])
            avg_voltage = np.mean([a.avg_battery_voltage for a in vehicle_aggregates])
            
            # 统计预警
            alert_counts = {}
            for alert in vehicle_alerts:
                alert_counts[alert.alert_type] = alert_counts.get(alert.alert_type, 0) + 1
            
            # 严重预警
            critical_alerts = [a for a in vehicle_alerts if a.severity == "critical"]
            warning_alerts = [a for a in vehicle_alerts if a.severity == "warning"]
            
            summary[vehicle_id] = {
                "avg_motor_temp": round(avg_motor_temp, 2),
                "avg_battery_temp": round(avg_battery_temp, 2),
                "avg_voltage": round(avg_voltage, 2),
                "total_alerts": len(vehicle_alerts),
                "critical_count": len(critical_alerts),
                "warning_count": len(warning_alerts),
                "alert_details": alert_counts,
            }
        
        return summary


def run_flink_monitoring(data: pd.DataFrame) -> Dict:
    """
    运行Flink监控模拟
    
    Args:
        data: CAN数据
    
    Returns:
        监控结果字典
    """
    logger.info("=" * 60)
    logger.info("启动Flink实时监控模拟")
    logger.info("=" * 60)
    
    # 创建监控模拟器
    monitor = FlinkMonitorSimulator(
        data=data,
        window_size_seconds=FLINK_CONFIG["window_size_seconds"],
        slide_interval_seconds=FLINK_CONFIG["slide_interval_seconds"]
    )
    
    # 处理数据流
    start_time = time.time()
    alerts, aggregates = monitor.process_stream()
    process_time = time.time() - start_time
    
    logger.info(f"处理耗时: {process_time:.2f} 秒")
    
    # 获取健康摘要
    health_summary = monitor.get_vehicle_health_summary()
    
    # 预警统计
    alert_stats = {
        "total_alerts": len(alerts),
        "by_severity": {},
        "by_type": {},
    }
    
    for alert in alerts:
        # 按严重性统计
        alert_stats["by_severity"][alert.severity] = \
            alert_stats["by_severity"].get(alert.severity, 0) + 1
        
        # 按类型统计
        alert_stats["by_type"][alert.alert_type] = \
            alert_stats["by_type"].get(alert.alert_type, 0) + 1
    
    result = {
        "process_info": {
            "total_records": len(data),
            "processed_count": monitor.processed_count,
            "process_time_seconds": round(process_time, 2),
            "window_size_seconds": FLINK_CONFIG["window_size_seconds"],
            "slide_interval_seconds": FLINK_CONFIG["slide_interval_seconds"],
            "total_windows": len(aggregates),
        },
        "alert_statistics": alert_stats,
        "vehicle_health_summary": health_summary,
        "recent_alerts": alerts[-20:] if len(alerts) > 20 else alerts,  # 最近20条预警
        "recent_aggregates": aggregates[-10:] if len(aggregates) > 10 else aggregates,  # 最近10个窗口
    }
    
    return result


def main():
    """主函数 - 测试Flink监控"""
    print("=" * 60)
    print("PyFlink实时监控模拟测试")
    print("=" * 60)
    
    # 导入数据生成器
    from src.data_generator import CANDataGenerator
    
    # 生成或加载数据
    generator = CANDataGenerator(num_vehicles=3, records_per_vehicle=5000)
    data = generator.load_data()
    
    if data is None:
        print("生成测试数据...")
        data = generator.generate_all_data()
    
    print(f"\n数据概况: {len(data)} 条记录")
    print(f"车辆列表: {data['vehicle_id'].unique().tolist()}")
    
    # 运行监控
    result = run_flink_monitoring(data)
    
    # 显示结果
    print("\n" + "-" * 40)
    print("监控结果摘要")
    print("-" * 40)
    
    print(f"\n处理信息:")
    for key, value in result["process_info"].items():
        print(f"  {key}: {value}")
    
    print(f"\n预警统计:")
    print(f"  总预警数: {result['alert_statistics']['total_alerts']}")
    print(f"  按严重性: {result['alert_statistics']['by_severity']}")
    print(f"  按类型: {result['alert_statistics']['by_type']}")
    
    print(f"\n车辆健康摘要:")
    for vehicle_id, health in result["vehicle_health_summary"].items():
        print(f"  {vehicle_id}:")
        print(f"    平均电机温度: {health['avg_motor_temp']}°C")
        print(f"    平均电池温度: {health['avg_battery_temp']}°C")
        print(f"    平均电压: {health['avg_voltage']}V")
        print(f"    严重预警: {health['critical_count']}, 警告: {health['warning_count']}")
    
    # 显示最近预警
    if result["recent_alerts"]:
        print(f"\n最近预警 (前5条):")
        for alert in result["recent_alerts"][:5]:
            print(f"  [{alert.severity}] {alert.vehicle_id}: {alert.message}")
    
    print("\n" + "=" * 60)
    print("Flink监控测试完成")
    print("=" * 60)
    
    return result


if __name__ == "__main__":
    result = main()
