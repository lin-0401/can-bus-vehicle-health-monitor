"""
CAN总线新能源汽车用户画像与健康监控系统
合成数据生成模块 - 生成基于真实驾驶规律的新能源汽车CAN数据

驾驶风格分类：
1. 经济型 - 温和加速，频繁能量回收
2. 均衡型 - 正常驾驶，偶尔激烈
3. 运动型 - 激进驾驶，高速巡航
4. 拥堵适应型 - 频繁启停，刹车较多
5. 高温工况型 - 长时间高负荷运行
"""

import os
import sys
import random
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    DATA_CONFIG, VEHICLE_IDS, CAN_SIGNAL_RANGES, DATA_RAW_DIR,
    DRIVING_SCENARIO_THRESHOLDS
)

class DrivingProfile:
    """驾驶风格配置类"""
    
    # 预定义的驾驶风格
    PROFILES = {
        "economy": {
            "name": "经济型",
            "throttle_range": (10, 50),          # 油门范围
            "throttle_change_freq": 0.1,         # 油门变化频率
            "brake_freq": 0.3,                   # 刹车频率
            "avg_speed": 50,                    # 平均速度
            "speed_variance": 15,               # 速度方差
            "regen_ratio": 0.6,                 # 能量回收占比
            "cruise_ratio": 0.4,                # 巡航占比
        },
        "balanced": {
            "name": "均衡型",
            "throttle_range": (20, 70),
            "throttle_change_freq": 0.2,
            "brake_freq": 0.2,
            "avg_speed": 70,
            "speed_variance": 25,
            "regen_ratio": 0.4,
            "cruise_ratio": 0.5,
        },
        "sporty": {
            "name": "运动型",
            "throttle_range": (40, 100),
            "throttle_change_freq": 0.4,
            "brake_freq": 0.15,
            "avg_speed": 100,
            "speed_variance": 40,
            "regen_ratio": 0.2,
            "cruise_ratio": 0.3,
        },
        "traffic": {
            "name": "拥堵适应型",
            "throttle_range": (5, 40),
            "throttle_change_freq": 0.5,
            "brake_freq": 0.5,
            "avg_speed": 25,
            "speed_variance": 20,
            "regen_ratio": 0.5,
            "cruise_ratio": 0.1,
        },
        "high_temp": {
            "name": "高温工况型",
            "throttle_range": (30, 80),
            "throttle_change_freq": 0.3,
            "brake_freq": 0.2,
            "avg_speed": 60,
            "speed_variance": 30,
            "regen_ratio": 0.3,
            "cruise_ratio": 0.4,
            "temp_offset": 15,                 # 温度偏移
        }
    }
    
    @classmethod
    def get_profile(cls, profile_type: str) -> Dict:
        """获取驾驶风格配置"""
        return cls.PROFILES.get(profile_type, cls.PROFILES["balanced"])


class CANDataGenerator:
    """新能源汽车CAN数据生成器"""
    
    def __init__(
        self,
        num_vehicles: int = None,
        records_per_vehicle: int = None,
        random_seed: int = 42
    ):
        """
        初始化数据生成器
        
        Args:
            num_vehicles: 车辆数量
            records_per_vehicle: 每辆车记录数
            random_seed: 随机种子
        """
        self.num_vehicles = num_vehicles or DATA_CONFIG["num_vehicles"]
        self.records_per_vehicle = records_per_vehicle or DATA_CONFIG["records_per_vehicle"]
        
        # 设置随机种子
        np.random.seed(random_seed)
        random.seed(random_seed)
        
        # 驾驶风格分配
        self.profile_types = list(DrivingProfile.PROFILES.keys())
        self.vehicle_profiles = self._assign_profiles()
        
        logger.info(f"数据生成器初始化完成: {self.num_vehicles}辆车, 每车{self.records_per_vehicle}条记录")
    
    def _assign_profiles(self) -> Dict[str, str]:
        """为每辆车分配驾驶风格"""
        vehicle_profiles = {}
        profile_distribution = ["economy", "balanced", "sporty", "traffic", "high_temp"]
        
        for i, vehicle_id in enumerate(VEHICLE_IDS[:self.num_vehicles]):
            # 根据车辆索引分配风格(确保多样性)
            profile = profile_distribution[i % len(profile_distribution)]
            vehicle_profiles[vehicle_id] = profile
        
        return vehicle_profiles
    
    def _get_speed_profile(
        self,
        profile: Dict,
        base_timestamp: datetime,
        record_index: int
    ) -> float:
        """
        根据驾驶风格生成速度
        
        Args:
            profile: 驾驶风格配置
            base_timestamp: 基础时间戳
            record_index: 记录索引
        
        Returns:
            速度值 (km/h)
        """
        interval_ms = DATA_CONFIG["sampling_interval_ms"]
        time_seconds = record_index * interval_ms / 1000
        
        # 基础速度(带周期性变化模拟真实路况)
        avg_speed = profile["avg_speed"]
        speed_variance = profile["speed_variance"]
        
        # 添加多种周期成分模拟真实驾驶
        speed = avg_speed + speed_variance * np.sin(2 * np.pi * time_seconds / 300)  # 5分钟周期
        speed += 0.5 * speed_variance * np.sin(2 * np.pi * time_seconds / 60)  # 1分钟周期
        speed += np.random.normal(0, speed_variance * 0.1)  # 随机噪声
        
        # 确保速度在合理范围内
        speed = max(0, min(speed, CAN_SIGNAL_RANGES["speed"]["max"]))
        
        return round(speed, 2)
    
    def _get_throttle_profile(
        self,
        profile: Dict,
        current_speed: float,
        target_speed: float,
        is_accelerating: bool
    ) -> float:
        """
        根据驾驶风格生成油门开度
        
        Args:
            profile: 驾驶风格配置
            current_speed: 当前速度
            target_speed: 目标速度
            is_accelerating: 是否正在加速
        
        Returns:
            油门开度 (0-100%)
        """
        throttle_min, throttle_max = profile["throttle_range"]
        
        if is_accelerating:
            # 需要加速
            speed_diff = target_speed - current_speed
            if speed_diff > 10:
                throttle = throttle_max * (0.8 + np.random.random() * 0.2)
            elif speed_diff > 0:
                throttle = throttle_min + (throttle_max - throttle_min) * 0.5 * (speed_diff / 10)
            else:
                throttle = throttle_min * 0.5  # 保持低速
        else:
            # 巡航或减速
            throttle = throttle_min + (throttle_max - throttle_min) * 0.2
        
        # 添加噪声
        throttle += np.random.normal(0, 3)
        
        return max(0, min(100, round(throttle, 2)))
    
    def _get_brake_profile(
        self,
        profile: Dict,
        current_speed: float,
        target_speed: float,
        should_brake: bool
    ) -> float:
        """
        根据驾驶风格生成刹车力度
        
        Args:
            profile: 驾驶风格配置
            current_speed: 当前速度
            target_speed: 目标速度
            should_brake: 是否需要刹车
        
        Returns:
            刹车力度 (0-100%)
        """
        brake_min, brake_max = 0, 100
        
        if should_brake:
            speed_diff = current_speed - target_speed
            if speed_diff > 20:
                brake = brake_max * (0.7 + np.random.random() * 0.3)
            elif speed_diff > 5:
                brake = brake_min + (brake_max - brake_min) * 0.5 * (speed_diff / 20)
            else:
                brake = brake_min + np.random.random() * 20
        else:
            brake = 0  # 默认不刹车
        
        return max(0, min(100, round(brake, 2)))
    
    def _get_battery_soc(
        self,
        profile: Dict,
        record_index: int,
        total_records: int,
        initial_soc: float = 100.0
    ) -> float:
        """
        根据驾驶风格生成电池SOC
        
        Args:
            profile: 驾驶风格配置
            record_index: 记录索引
            total_records: 总记录数
            initial_soc: 初始SOC
        
        Returns:
            电池SOC (0-100%)
        """
        # 计算耗电率(基于驾驶风格)
        regen_ratio = profile["regen_ratio"]
        avg_speed = profile["avg_speed"]
        
        # 基础放电率 (%/1000条记录)
        base_discharge_rate = 8.0
        if avg_speed > 80:
            base_discharge_rate = 12.0
        elif avg_speed > 50:
            base_discharge_rate = 10.0
        else:
            base_discharge_rate = 6.0
        
        # 考虑能量回收
        effective_discharge = base_discharge_rate * (1 - regen_ratio * 0.3)
        
        # SOC变化
        soc = initial_soc - (record_index / 1000) * effective_discharge
        
        # 添加小幅波动
        soc += np.random.normal(0, 0.5)
        
        return max(0, min(100, round(soc, 2)))
    
    def _get_battery_signals(
        self,
        profile: Dict,
        battery_soc: float,
        record_index: int
    ) -> Tuple[float, float, float]:
        """
        生成电池相关信号
        
        Args:
            profile: 驾驶风格配置
            battery_soc: 当前SOC
            record_index: 记录索引
        
        Returns:
            (电压, 电流, 温度)
        """
        # 电压计算 (280-420V，随SOC变化)
        base_voltage = 350 + battery_soc * 0.5
        voltage = base_voltage + np.random.normal(0, 2)
        
        # 电流计算 (放电为正，充电为负)
        throttle = np.random.uniform(20, 60) if profile else 50
        base_current = throttle * 1.5 + np.random.normal(0, 10)
        current = max(-50, min(150, base_current))
        
        # 温度计算 (考虑高温工况)
        temp_offset = profile.get("temp_offset", 0) if profile else 0
        base_temp = 25 + (100 - battery_soc) * 0.1 + temp_offset
        temperature = base_temp + np.random.normal(0, 1)
        
        return (
            round(voltage, 2),
            round(current, 2),
            round(temperature, 2)
        )
    
    def _get_motor_signals(
        self,
        profile: Dict,
        speed: float,
        throttle: float,
        record_index: int
    ) -> Tuple[float, float, float]:
        """
        生成电机相关信号
        
        Args:
            profile: 驾驶风格配置
            speed: 当前速度
            throttle: 油门开度
            record_index: 记录索引
        
        Returns:
            (电机温度, 转速, 扭矩)
        """
        # 转速计算 (与速度成正比)
        max_rpm = CAN_SIGNAL_RANGES["motor_rpm"]["max"]
        rpm = (speed / 180) * max_rpm + np.random.normal(0, 100)
        
        # 扭矩计算 (与油门成正比)
        max_torque = CAN_SIGNAL_RANGES["motor_torque"]["max"]
        base_torque = (throttle / 100) * max_torque * 0.8
        torque = base_torque + np.random.normal(0, 20)
        
        # 温度计算 (与负载和持续时间相关)
        temp_offset = profile.get("temp_offset", 0) if profile else 0
        base_temp = 40 + (throttle / 100) * 40 + (record_index % 1000) * 0.02 + temp_offset
        temperature = base_temp + np.random.normal(0, 2)
        
        return (
            round(temperature, 2),
            round(max(0, rpm), 0),
            round(torque, 2)
        )
    
    def _get_cabin_signals(
        self,
        profile: Dict,
        record_index: int,
        ambient_temp: float = 30.0
    ) -> Tuple[float, float]:
        """
        生成座舱环境信号
        
        Args:
            profile: 驾驶风格配置
            record_index: 记录索引
            ambient_temp: 环境温度
        
        Returns:
            (座舱温度, 空调功率)
        """
        # 座舱温度 (受环境温度和空调影响)
        cycle_position = (record_index % 500) / 500
        
        # 模拟温度周期性变化
        cabin_temp = ambient_temp - 5 + 3 * np.sin(2 * np.pi * cycle_position)
        cabin_temp += np.random.normal(0, 0.5)
        
        # 空调功率 (根据温度差和驾驶时间变化)
        temp_diff = max(0, ambient_temp - cabin_temp)
        ac_power = min(8, temp_diff * 0.3 + np.random.uniform(0, 2))
        
        return (
            round(cabin_temp, 2),
            round(ac_power, 2)
        )
    
    def _get_location_signals(
        self,
        record_index: int,
        base_lat: float = 31.2304,
        base_lon: float = 121.4737
    ) -> Tuple[float, float]:
        """
        生成位置信号 (模拟轨迹)
        
        Args:
            record_index: 记录索引
            base_lat: 基础纬度
            base_lon: 基础经度
        
        Returns:
            (纬度, 经度)
        """
        # 模拟车辆移动
        lat = base_lat + record_index * 0.00001 + np.random.normal(0, 0.0001)
        lon = base_lon + record_index * 0.000012 + np.random.normal(0, 0.0001)
        
        return (round(lat, 6), round(lon, 6))
    
    def _get_charging_status(
        self,
        battery_soc: float,
        record_index: int
    ) -> int:
        """
        生成充电状态
        
        Args:
            battery_soc: 当前SOC
            record_index: 记录索引
        
        Returns:
            充电状态 (0:未充电 1:慢充 2:快充 3:充满)
        """
        # 根据SOC判断充电状态
        if battery_soc > 95:
            return 3  # 充满
        elif battery_soc < 20 and record_index % 100 == 0:
            # 低电量时模拟充电
            return random.choice([1, 2])  # 慢充或快充
        else:
            return 0  # 未充电
    
    def generate_vehicle_data(
        self,
        vehicle_id: str,
        num_records: int = None,
        start_timestamp: datetime = None
    ) -> pd.DataFrame:
        """
        生成单辆车的CAN数据
        
        Args:
            vehicle_id: 车辆ID
            num_records: 记录数量
            start_timestamp: 起始时间戳
        
        Returns:
            包含所有CAN信号的DataFrame
        """
        num_records = num_records or self.records_per_vehicle
        start_timestamp = start_timestamp or datetime.now()
        
        profile_type = self.vehicle_profiles.get(vehicle_id, "balanced")
        profile = DrivingProfile.get_profile(profile_type)
        
        logger.info(f"生成车辆 {vehicle_id} 的数据 (风格: {profile['name']})")
        
        records = []
        interval_ms = DATA_CONFIG["sampling_interval_ms"]
        
        # 状态变量
        current_speed = 0
        target_speed = profile["avg_speed"]
        battery_soc = 100.0
        ambient_temp = 30.0 + profile.get("temp_offset", 0)
        
        for i in range(num_records):
            # 更新时间戳
            timestamp = start_timestamp + timedelta(milliseconds=i * interval_ms)
            
            # 生成速度
            target_speed = self._get_speed_profile(profile, timestamp, i)
            speed_diff = target_speed - current_speed
            
            # 判断驾驶动作
            is_accelerating = speed_diff > 5
            should_brake = speed_diff < -10 or (current_speed > 0 and np.random.random() < profile["brake_freq"] * 0.1)
            
            # 生成油门和刹车
            throttle = self._get_throttle_profile(profile, current_speed, target_speed, is_accelerating)
            brake = self._get_brake_profile(profile, current_speed, target_speed, should_brake)
            
            # 更新速度
            if should_brake:
                current_speed = max(0, current_speed - brake * 0.5)
            elif is_accelerating:
                current_speed = min(target_speed, current_speed + throttle * 0.1)
            else:
                current_speed = current_speed * 0.98 + target_speed * 0.02
            
            # 生成方向盘角度
            steering_angle = np.random.normal(0, 10) if np.random.random() < 0.1 else 0
            
            # 生成电池信号
            battery_soc = self._get_battery_soc(profile, i, num_records, 100.0)
            battery_voltage, battery_current, battery_temperature = self._get_battery_signals(
                profile, battery_soc, i
            )
            
            # 生成电机信号
            motor_temperature, motor_rpm, motor_torque = self._get_motor_signals(
                profile, current_speed, throttle, i
            )
            
            # 生成座舱信号
            cabin_temperature, ac_power = self._get_cabin_signals(profile, i, ambient_temp)
            
            # 生成充电状态
            charging_status = self._get_charging_status(battery_soc, i)
            
            # 生成位置
            latitude, longitude = self._get_location_signals(i)
            
            # 组装记录
            record = {
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "vehicle_id": vehicle_id,
                "speed": round(current_speed, 2),
                "throttle": throttle,
                "brake": brake,
                "steering_angle": round(steering_angle, 2),
                "battery_soc": battery_soc,
                "battery_voltage": battery_voltage,
                "battery_current": battery_current,
                "battery_temperature": battery_temperature,
                "motor_temperature": motor_temperature,
                "motor_rpm": motor_rpm,
                "motor_torque": motor_torque,
                "cabin_temperature": cabin_temperature,
                "ac_power": ac_power,
                "charging_status": charging_status,
                "latitude": latitude,
                "longitude": longitude,
                "driving_profile": profile_type,
            }
            
            records.append(record)
        
        return pd.DataFrame(records)
    
    def generate_all_data(self) -> pd.DataFrame:
        """
        生成所有车辆的CAN数据
        
        Returns:
            包含所有车辆数据的DataFrame
        """
        logger.info("开始生成所有车辆CAN数据...")
        
        all_data = []
        start_time = datetime.strptime(
            DATA_CONFIG["start_timestamp"],
            "%Y-%m-%d %H:%M:%S"
        )
        
        for vehicle_id in VEHICLE_IDS[:self.num_vehicles]:
            vehicle_data = self.generate_vehicle_data(
                vehicle_id=vehicle_id,
                num_records=self.records_per_vehicle,
                start_timestamp=start_time
            )
            all_data.append(vehicle_data)
            
            # 每辆车数据间隔1小时
            start_time += timedelta(hours=1)
        
        combined_data = pd.concat(all_data, ignore_index=True)
        
        logger.info(f"数据生成完成: {len(combined_data)} 条记录")
        logger.info(f"车辆列表: {combined_data['vehicle_id'].unique().tolist()}")
        logger.info(f"驾驶风格分布:\n{combined_data['driving_profile'].value_counts()}")
        
        return combined_data
    
    def save_data(
        self,
        data: pd.DataFrame,
        filename: str = None,
        include_timestamp: bool = True
    ) -> Path:
        """
        保存数据到CSV文件
        
        Args:
            data: 要保存的数据
            filename: 文件名(不含扩展名)
            include_timestamp: 是否在文件名中包含时间戳
        
        Returns:
            保存的文件路径
        """
        if filename is None:
            filename = "can_synthetic_data"
        
        if include_timestamp:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{filename}_{timestamp_str}"
        
        file_path = DATA_RAW_DIR / f"{filename}.csv"
        
        # 确保目录存在
        DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
        
        # 保存数据
        data.to_csv(file_path, index=False, encoding="utf-8")
        
        file_size = file_path.stat().st_size / 1024 / 1024  # MB
        logger.info(f"数据已保存: {file_path} ({file_size:.2f} MB)")
        
        return file_path
    
    def load_data(self, file_path: Path = None) -> Optional[pd.DataFrame]:
        """
        加载已有数据
        
        Args:
            file_path: 数据文件路径
        
        Returns:
            DataFrame或None
        """
        if file_path is None:
            # 查找最新文件
            csv_files = list(DATA_RAW_DIR.glob("can_synthetic_data_*.csv"))
            if not csv_files:
                logger.warning("未找到数据文件")
                return None
            file_path = sorted(csv_files)[-1]  # 最新文件
        
        if not file_path.exists():
            logger.warning(f"文件不存在: {file_path}")
            return None
        
        logger.info(f"加载数据: {file_path}")
        data = pd.read_csv(file_path)
        logger.info(f"加载完成: {len(data)} 条记录")
        
        return data


def main():
    """主函数 - 测试数据生成"""
    print("=" * 60)
    print("新能源汽车CAN合成数据生成测试")
    print("=" * 60)
    
    # 创建生成器
    generator = CANDataGenerator(
        num_vehicles=5,
        records_per_vehicle=10000,
        random_seed=42
    )
    
    # 生成数据
    print("\n生成CAN数据...")
    data = generator.generate_all_data()
    
    # 显示数据概况
    print("\n数据概况:")
    print(f"  总记录数: {len(data)}")
    print(f"  车辆数: {data['vehicle_id'].nunique()}")
    print(f"  时间范围: {data['timestamp'].min()} ~ {data['timestamp'].max()}")
    print(f"\n各车辆记录数:")
    print(data['vehicle_id'].value_counts())
    
    # 数据统计
    print("\n关键指标统计:")
    numeric_cols = ['speed', 'throttle', 'brake', 'battery_soc', 'motor_temperature', 'battery_temperature']
    print(data[numeric_cols].describe().round(2))
    
    # 保存数据
    print("\n保存数据...")
    file_path = generator.save_data(data)
    print(f"数据已保存到: {file_path}")
    
    print("\n" + "=" * 60)
    print("数据生成测试完成")
    print("=" * 60)
    
    return data


if __name__ == "__main__":
    data = main()
