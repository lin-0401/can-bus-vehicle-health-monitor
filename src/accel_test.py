"""
CAN总线新能源汽车用户画像与健康监控系统
加速试验工况转化模块

功能：
1. 识别高负载、高温、剧烈充放电时段
2. 提取加速耐久工况序列
3. 生成符合行业标准的测试工况
4. 工况统计分析
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_PROCESSED_DIR, OUTPUT_REPORTS_DIR


@dataclass
class AccelConditionSegment:
    """加速耐久工况段"""
    segment_id: int
    start_index: int
    end_index: int
    start_time: str
    end_time: str
    duration_seconds: float
    
    # 工况类型
    condition_type: str  # high_load, high_temp, rapid_charge, rapid_discharge
    
    # 主要特征
    avg_motor_temp: float
    max_motor_temp: float
    avg_battery_temp: float
    max_battery_temp: float
    avg_throttle: float
    max_throttle: float
    avg_speed: float
    max_speed: float
    avg_current: float
    max_current: float
    
    # 评分
    severity_score: float  # 严苛程度评分
    test_value: str  # 测试价值评估


@dataclass
class AccelTestProfile:
    """加速耐久测试工况配置"""
    test_name: str
    vehicle_id: str
    total_duration_seconds: float
    segments: List[AccelConditionSegment]
    summary: Dict


class AccelConditionExtractor:
    """加速工况提取器"""
    
    # 工况识别阈值
    THRESHOLDS = {
        # 高负载
        "high_load": {
            "throttle_min": 70,          # 高油门
            "speed_min": 80,            # 高速
            "motor_temp_min": 80,        # 电机高温
        },
        # 高温工况
        "high_temp": {
            "motor_temp_min": 100,      # 电机温度下限
            "battery_temp_min": 40,     # 电池温度下限
        },
        # 急充
        "rapid_charge": {
            "current_max": 100,          # 大电流（充电为负，取绝对值）
            "soc_max_change": 5,         # SOC变化率
        },
        # 急放
        "rapid_discharge": {
            "current_max": 100,          # 大电流放电
            "throttle_min": 50,          # 高功率输出
        },
    }
    
    def __init__(self, min_segment_duration: int = 10):
        """
        初始化提取器
        
        Args:
            min_segment_duration: 最小工况段持续时间(采样点数)
        """
        self.min_segment_duration = min_segment_duration
    
    def _identify_high_load_periods(self, df: pd.DataFrame) -> List[Tuple[int, int]]:
        """
        识别高负载时段
        
        Args:
            df: 车辆数据
        
        Returns:
            [(start, end), ...] 索引元组列表
        """
        t = self.THRESHOLDS["high_load"]
        
        mask = (
            (df["throttle"] >= t["throttle_min"]) |
            ((df["speed"] >= t["speed_min"]) & (df["throttle"] >= t["throttle_min"] * 0.5)) |
            (df["motor_temperature"] >= t["motor_temp_min"])
        )
        
        return self._extract_continuous_periods(mask.values)
    
    def _identify_high_temp_periods(self, df: pd.DataFrame) -> List[Tuple[int, int]]:
        """
        识别高温工况时段
        
        Args:
            df: 车辆数据
        
        Returns:
            索引元组列表
        """
        t = self.THRESHOLDS["high_temp"]
        
        mask = (
            (df["motor_temperature"] >= t["motor_temp_min"]) |
            (df["battery_temperature"] >= t["battery_temp_min"])
        )
        
        return self._extract_continuous_periods(mask.values)
    
    def _identify_rapid_charge_periods(self, df: pd.DataFrame) -> List[Tuple[int, int]]:
        """
        识别急充时段
        
        Args:
            df: 车辆数据
        
        Returns:
            索引元组列表
        """
        t = self.THRESHOLDS["rapid_charge"]
        
        # 充电时电流为负，取绝对值判断
        current_abs = df["battery_current"].abs()
        
        # SOC变化率
        soc_diff = df["battery_soc"].diff().fillna(0)
        
        mask = (
            (current_abs >= t["current_max"]) & (df["battery_current"] < 0) |
            (soc_diff >= t["soc_max_change"] / 100)  # 每采样点SOC变化
        )
        
        return self._extract_continuous_periods(mask.values)
    
    def _identify_rapid_discharge_periods(self, df: pd.DataFrame) -> List[Tuple[int, int]]:
        """
        识别急放时段
        
        Args:
            df: 车辆数据
        
        Returns:
            索引元组列表
        """
        t = self.THRESHOLDS["rapid_discharge"]
        
        mask = (
            (df["battery_current"] >= t["current_max"]) &
            (df["throttle"] >= t["throttle_min"])
        )
        
        return self._extract_continuous_periods(mask.values)
    
    def _extract_continuous_periods(
        self, 
        mask: np.ndarray, 
        min_length: int = None
    ) -> List[Tuple[int, int]]:
        """
        从布尔数组中提取连续为True的区间
        
        Args:
            mask: 布尔数组
            min_length: 最小区间长度
        
        Returns:
            [(start, end), ...] 索引元组列表
        """
        min_length = min_length or self.min_segment_duration
        
        periods = []
        start = None
        
        for i, val in enumerate(mask):
            if val and start is None:
                start = i
            elif not val and start is not None:
                if i - start >= min_length:
                    periods.append((start, i))
                start = None
        
        # 处理末尾
        if start is not None and len(mask) - start >= min_length:
            periods.append((start, len(mask)))
        
        return periods
    
    def _calculate_segment_stats(
        self,
        segment_data: pd.DataFrame
    ) -> Dict:
        """
        计算工况段统计特征
        
        Args:
            segment_data: 工况段数据
        
        Returns:
            统计特征字典
        """
        return {
            "avg_motor_temp": round(segment_data["motor_temperature"].mean(), 2),
            "max_motor_temp": round(segment_data["motor_temperature"].max(), 2),
            "avg_battery_temp": round(segment_data["battery_temperature"].mean(), 2),
            "max_battery_temp": round(segment_data["battery_temperature"].max(), 2),
            "avg_throttle": round(segment_data["throttle"].mean(), 2),
            "max_throttle": round(segment_data["throttle"].max(), 2),
            "avg_speed": round(segment_data["speed"].mean(), 2),
            "max_speed": round(segment_data["speed"].max(), 2),
            "avg_current": round(segment_data["battery_current"].mean(), 2),
            "max_current": round(segment_data["battery_current"].abs().max(), 2),
            "duration_seconds": len(segment_data) * 0.1,  # 100ms采样
        }
    
    def _calculate_severity_score(self, stats: Dict, condition_type: str) -> float:
        """
        计算工况严苛程度评分
        
        Args:
            stats: 工况统计
            condition_type: 工况类型
        
        Returns:
            严苛度评分 (0-100)
        """
        scores = []
        
        if condition_type == "high_load":
            # 高负载评分
            throttle_score = min(100, stats["max_throttle"] / 80 * 100)
            speed_score = min(100, stats["max_speed"] / 150 * 100)
            temp_score = min(100, stats["max_motor_temp"] / 150 * 100)
            scores = [throttle_score * 0.4, speed_score * 0.3, temp_score * 0.3]
        
        elif condition_type == "high_temp":
            # 高温评分
            motor_temp_score = min(100, stats["max_motor_temp"] / 150 * 100)
            battery_temp_score = min(100, stats["max_battery_temp"] / 55 * 100)
            scores = [motor_temp_score * 0.5, battery_temp_score * 0.5]
        
        elif condition_type == "rapid_charge":
            # 急充评分
            current_score = min(100, stats["max_current"] / 150 * 100)
            temp_score = min(100, stats["avg_battery_temp"] / 45 * 100)
            scores = [current_score * 0.6, temp_score * 0.4]
        
        elif condition_type == "rapid_discharge":
            # 急放评分
            current_score = min(100, stats["max_current"] / 150 * 100)
            throttle_score = min(100, stats["max_throttle"] / 100 * 100)
            scores = [current_score * 0.5, throttle_score * 0.5]
        
        return round(sum(scores) / len(scores) if scores else 0, 2)
    
    def _get_test_value(self, stats: Dict, condition_type: str) -> str:
        """
        评估测试价值
        
        Args:
            stats: 工况统计
            condition_type: 工况类型
        
        Returns:
            测试价值评估
        """
        score = self._calculate_severity_score(stats, condition_type)
        
        if score >= 80:
            return "高价值"
        elif score >= 50:
            return "中等价值"
        else:
            return "一般价值"
    
    def extract_segments(
        self,
        df: pd.DataFrame,
        vehicle_id: str
    ) -> List[AccelConditionSegment]:
        """
        提取所有加速耐久工况段
        
        Args:
            df: 车辆数据
            vehicle_id: 车辆ID
        
        Returns:
            工况段列表
        """
        segments = []
        segment_id = 0
        
        # 重置索引
        df = df.reset_index(drop=True)
        
        # 提取各类型工况
        all_periods = {
            "high_load": self._identify_high_load_periods(df),
            "high_temp": self._identify_high_temp_periods(df),
            "rapid_charge": self._identify_rapid_charge_periods(df),
            "rapid_discharge": self._identify_rapid_discharge_periods(df),
        }
        
        # 合并重叠区间
        merged_periods = self._merge_periods(all_periods)
        
        # 创建工况段
        for start, end in merged_periods:
            # 确定主要工况类型
            condition_type = self._determine_main_type(df.iloc[start:end])
            
            # 计算统计
            stats = self._calculate_segment_stats(df.iloc[start:end])
            
            # 计算严苛度
            severity = self._calculate_severity_score(stats, condition_type)
            test_value = self._get_test_value(stats, condition_type)
            
            segment = AccelConditionSegment(
                segment_id=segment_id,
                start_index=start,
                end_index=end,
                start_time=df.iloc[start]["timestamp"],
                end_time=df.iloc[end-1]["timestamp"],
                duration_seconds=stats["duration_seconds"],
                condition_type=condition_type,
                avg_motor_temp=stats["avg_motor_temp"],
                max_motor_temp=stats["max_motor_temp"],
                avg_battery_temp=stats["avg_battery_temp"],
                max_battery_temp=stats["max_battery_temp"],
                avg_throttle=stats["avg_throttle"],
                max_throttle=stats["max_throttle"],
                avg_speed=stats["avg_speed"],
                max_speed=stats["max_speed"],
                avg_current=stats["avg_current"],
                max_current=stats["max_current"],
                severity_score=severity,
                test_value=test_value,
            )
            
            segments.append(segment)
            segment_id += 1
        
        logger.info(f"车辆 {vehicle_id} 提取了 {len(segments)} 个加速耐久工况段")
        
        return segments
    
    def _determine_main_type(self, segment_data: pd.DataFrame) -> str:
        """确定主要工况类型"""
        conditions = []
        
        t_high_load = self.THRESHOLDS["high_load"]
        t_high_temp = self.THRESHOLDS["high_temp"]
        
        if segment_data["throttle"].mean() >= t_high_load["throttle_min"] * 0.7:
            conditions.append("high_load")
        if segment_data["motor_temperature"].mean() >= t_high_temp["motor_temp_min"] * 0.8:
            conditions.append("high_temp")
        if segment_data["battery_current"].abs().mean() >= 80:
            if segment_data["battery_current"].mean() < 0:
                conditions.append("rapid_charge")
            else:
                conditions.append("rapid_discharge")
        
        return conditions[0] if conditions else "high_load"
    
    def _merge_periods(
        self,
        all_periods: Dict[str, List[Tuple[int, int]]]
    ) -> List[Tuple[int, int]]:
        """合并所有类型的时间段"""
        all_intervals = []
        
        for periods in all_periods.values():
            all_intervals.extend(periods)
        
        if not all_intervals:
            return []
        
        # 按起始位置排序
        all_intervals.sort(key=lambda x: x[0])
        
        # 合并重叠区间
        merged = [all_intervals[0]]
        
        for start, end in all_intervals[1:]:
            last_start, last_end = merged[-1]
            
            if start <= last_end:  # 重叠
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        
        return merged


class AcceleratedTestConverter:
    """加速试验工况转换器"""
    
    def __init__(self):
        """初始化转换器"""
        self.extractor = AccelConditionExtractor(min_segment_duration=10)
    
    def convert_vehicle(
        self,
        df: pd.DataFrame,
        vehicle_id: str
    ) -> AccelTestProfile:
        """
        转换车辆数据为加速耐久测试工况
        
        Args:
            df: 车辆数据
            vehicle_id: 车辆ID
        
        Returns:
            加速测试工况配置
        """
        logger.info(f"转换车辆 {vehicle_id} 的加速耐久工况...")
        
        # 提取工况段
        segments = self.extractor.extract_segments(df, vehicle_id)
        
        # 生成摘要
        summary = self._generate_summary(segments)
        
        profile = AccelTestProfile(
            test_name=f"加速耐久测试_{vehicle_id}",
            vehicle_id=vehicle_id,
            total_duration_seconds=sum(s.duration_seconds for s in segments),
            segments=segments,
            summary=summary,
        )
        
        return profile
    
    def _generate_summary(self, segments: List[AccelConditionSegment]) -> Dict:
        """生成工况摘要"""
        if not segments:
            return {
                "total_segments": 0,
                "total_duration_minutes": 0,
                "avg_severity": 0,
                "by_type": {},
            }
        
        by_type = {}
        for seg in segments:
            if seg.condition_type not in by_type:
                by_type[seg.condition_type] = {
                    "count": 0,
                    "total_duration": 0,
                    "avg_severity": 0,
                }
            by_type[seg.condition_type]["count"] += 1
            by_type[seg.condition_type]["total_duration"] += seg.duration_seconds
        
        # 计算各类型平均严苛度
        for seg_type in by_type:
            type_segments = [s for s in segments if s.condition_type == seg_type]
            by_type[seg_type]["avg_severity"] = round(
                np.mean([s.severity_score for s in type_segments]), 2
            )
        
        return {
            "total_segments": len(segments),
            "total_duration_minutes": round(sum(s.duration_seconds for s in segments) / 60, 2),
            "avg_severity": round(np.mean([s.severity_score for s in segments]), 2),
            "max_severity": round(max(s.severity_score for s in segments), 2),
            "high_value_segments": sum(1 for s in segments if s.test_value == "高价值"),
            "by_type": by_type,
        }
    
    def convert_fleet(
        self,
        data: pd.DataFrame
    ) -> List[AccelTestProfile]:
        """
        转换车队数据
        
        Args:
            data: 所有车辆数据
        
        Returns:
            加速测试工况列表
        """
        profiles = []
        
        for vehicle_id in data["vehicle_id"].unique():
            vehicle_data = data[data["vehicle_id"] == vehicle_id]
            profile = self.convert_vehicle(vehicle_data, vehicle_id)
            profiles.append(profile)
        
        return profiles
    
    def generate_test_sequence(
        self,
        profiles: List[AccelTestProfile],
        max_duration_minutes: float = 60
    ) -> pd.DataFrame:
        """
        生成综合测试序列
        
        Args:
            profiles: 测试工况列表
            max_duration_minutes: 最大总时长(分钟)
        
        Returns:
            测试序列DataFrame
        """
        all_segments = []
        
        for profile in profiles:
            for seg in profile.segments:
                if seg.duration_seconds / 60 <= max_duration_minutes:
                    all_segments.append({
                        "vehicle_id": profile.vehicle_id,
                        "segment_id": seg.segment_id,
                        "condition_type": seg.condition_type,
                        "start_time": seg.start_time,
                        "end_time": seg.end_time,
                        "duration_seconds": seg.duration_seconds,
                        "max_motor_temp": seg.max_motor_temp,
                        "max_battery_temp": seg.max_battery_temp,
                        "max_throttle": seg.max_throttle,
                        "max_speed": seg.max_speed,
                        "severity_score": seg.severity_score,
                        "test_value": seg.test_value,
                    })
        
        return pd.DataFrame(all_segments)


def main():
    """主函数 - 测试加速试验工况转化"""
    print("=" * 60)
    print("加速试验工况转化测试")
    print("=" * 60)
    
    # 导入数据
    from src.data_generator import CANDataGenerator
    
    generator = CANDataGenerator(num_vehicles=3, records_per_vehicle=5000)
    data = generator.load_data()
    
    if data is None:
        print("生成测试数据...")
        data = generator.generate_all_data()
    
    print(f"\n数据概况: {len(data)} 条记录")
    
    # 创建转换器
    converter = AcceleratedTestConverter()
    
    # 转换车队数据
    print("\n转换加速耐久工况...")
    profiles = converter.convert_fleet(data)
    
    # 显示结果
    print("\n" + "-" * 50)
    print("加速耐久测试工况汇总")
    print("-" * 50)
    
    for profile in profiles:
        print(f"\n【{profile.vehicle_id}】")
        print(f"  测试名称: {profile.test_name}")
        print(f"  工况段数: {profile.summary['total_segments']}")
        print(f"  总时长: {profile.summary['total_duration_minutes']:.2f} 分钟")
        print(f"  平均严苛度: {profile.summary['avg_severity']}")
        print(f"  高价值工况: {profile.summary['high_value_segments']} 段")
        
        print(f"\n  工况类型分布:")
        for seg_type, info in profile.summary["by_type"].items():
            type_name = {
                "high_load": "高负载",
                "high_temp": "高温",
                "rapid_charge": "急充",
                "rapid_discharge": "急放",
            }.get(seg_type, seg_type)
            print(f"    {type_name}: {info['count']}段, {info['total_duration']/60:.1f}分钟, 严苛度{info['avg_severity']}")
    
    # 生成测试序列
    print("\n生成综合测试序列...")
    test_sequence = converter.generate_test_sequence(profiles)
    print(f"测试序列: {len(test_sequence)} 个工况段")
    
    # 保存结果
    test_sequence.to_csv(DATA_PROCESSED_DIR / "accelerated_test_sequence.csv", index=False)
    print(f"测试序列已保存: {DATA_PROCESSED_DIR / 'accelerated_test_sequence.csv'}")
    
    # 显示高价值工况示例
    high_value = test_sequence[test_sequence["test_value"] == "高价值"]
    if len(high_value) > 0:
        print(f"\n高价值工况示例:")
        print(high_value[["vehicle_id", "condition_type", "duration_seconds", "max_motor_temp", "severity_score"]].head())
    
    print("\n" + "=" * 60)
    print("加速试验工况转化测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
