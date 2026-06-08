"""
CAN总线新能源汽车用户画像与健康监控系统
PySpark特征工程与用户画像模块

功能：
1. 数据加载与预处理
2. 特征工程（统计特征、时序特征、行为特征）
3. 驾驶工况识别（拥堵、巡航、激烈、经济）
4. 用户画像标签构建（8组标签）
5. 聚类分析

支持PySpark和Pandas两种模式，当PySpark不可用时自动降级到Pandas
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

import pandas as pd
import numpy as np

# 尝试导入PySpark
HAS_PYSPARK = False
SparkSession = None
DataFrame = None
F = None
VectorAssembler = None
StandardScaler = None
KMeans = None
Pipeline = None

try:
    from pyspark.sql import SparkSession, DataFrame
    from pyspark.sql import functions as F
    from pyspark.ml.feature import VectorAssembler, StandardScaler
    from pyspark.ml.clustering import KMeans
    from pyspark.ml import Pipeline
    HAS_PYSPARK = True
except ImportError:
    print("警告: PySpark未安装，将使用Pandas模拟模式")

from sklearn.preprocessing import MinMaxScaler

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    SPARK_CONFIG, CLUSTERING_CONFIG, DRIVING_SCENARIO_THRESHOLDS,
    USER_PROFILE_TAGS, DATA_PROCESSED_DIR, OUTPUT_REPORTS_DIR
)


class SparkFeatureEngine:
    """特征工程引擎（支持PySpark和Pandas两种模式）"""
    
    def __init__(self, app_name: str = None):
        """
        初始化引擎
        
        Args:
            app_name: Spark应用名称（仅PySpark模式使用）
        """
        self.app_name = app_name or SPARK_CONFIG["app_name"]
        self.use_spark = HAS_PYSPARK
        self.spark = None
        
        if self.use_spark:
            self.spark = self._create_spark_session()
            logger.info(f"Spark会话创建成功: {self.app_name}")
        else:
            logger.info("使用Pandas模式进行特征工程")
    
    def _create_spark_session(self):
        """创建Spark会话"""
        builder = (
            SparkSession.builder
            .appName(self.app_name)
            .master(SPARK_CONFIG["master"])
            .config("spark.driver.memory", SPARK_CONFIG["driver_memory"])
            .config("spark.executor.memory", SPARK_CONFIG["executor_memory"])
            .config("spark.driver.maxResultSize", SPARK_CONFIG["max_result_size"])
            .config("spark.sql.shuffle.partitions", SPARK_CONFIG["shuffle_partitions"])
        )
        return builder.getOrCreate()
    
    def load_can_data(self, file_path: Path) -> pd.DataFrame:
        """
        加载CAN数据
        
        Args:
            file_path: CSV文件路径
        
        Returns:
            Pandas DataFrame
        """
        logger.info(f"加载数据: {file_path}")
        data = pd.read_csv(file_path)
        logger.info(f"数据加载完成: {len(data)} 条记录")
        return data
    
    def add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        添加时间特征
        
        Args:
            df: 原始数据
        
        Returns:
            添加时间特征后的DataFrame
        """
        df = df.copy()
        
        # 解析时间戳
        df['ts'] = pd.to_datetime(df['timestamp'], format='%Y-%m-%d %H:%M:%S.%f', errors='coerce')
        if df['ts'].isna().any():
            df['ts'] = pd.to_datetime(df['timestamp'], errors='coerce')
        
        df['hour'] = df['ts'].dt.hour
        df['day_of_week'] = df['ts'].dt.dayofweek
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        
        # 时间段
        def get_time_period(hour):
            if 7 <= hour <= 9:
                return '早高峰'
            elif 17 <= hour <= 19:
                return '晚高峰'
            elif 22 <= hour or hour <= 6:
                return '夜间'
            else:
                return '日间'
        
        df['time_period'] = df['hour'].apply(get_time_period)
        
        return df
    
    def add_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        添加派生特征
        
        Args:
            df: 原始数据
        
        Returns:
            添加派生特征后的DataFrame
        """
        df = df.copy()
        
        # 动能变化代理
        df['acceleration_proxy'] = np.where(df['throttle'] > 50, 1.0,
                                            np.where(df['brake'] > 30, -1.0, 0.0))
        
        # 能量消耗率
        df['energy_consumption_rate'] = np.abs(df['battery_current']) * df['battery_voltage'] / 1000
        
        # 电机负载率
        df['motor_load_rate'] = (df['motor_torque'] + 300) / 800 * 100
        
        # 电池健康状态代理
        def get_soc_level(soc):
            if soc < 15:
                return 'low'
            elif soc < 30:
                return 'medium_low'
            elif soc < 70:
                return 'medium'
            else:
                return 'high'
        
        df['soc_level'] = df['battery_soc'].apply(get_soc_level)
        
        return df
    
    def aggregate_by_vehicle(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        按车辆聚合计算统计特征
        
        Args:
            df: 添加特征后的DataFrame
        
        Returns:
            按车辆聚合的DataFrame
        """
        agg_dict = {
            'speed': ['mean', 'max', 'min', 'std'],
            'throttle': ['mean', 'max', 'std'],
            'brake': ['mean', 'max', 'std'],
            'battery_soc': ['mean', 'min'],
            'battery_temperature': ['mean', 'max'],
            'motor_temperature': ['mean', 'max'],
            'battery_voltage': ['mean', 'min', 'max'],
            'battery_current': 'mean',
            'ac_power': ['mean', 'sum'],
            'timestamp': 'count',
            'energy_consumption_rate': 'mean',
        }
        
        vehicle_stats = df.groupby('vehicle_id').agg(agg_dict)
        
        # 扁平化列名
        vehicle_stats.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col 
                                for col in vehicle_stats.columns]
        vehicle_stats = vehicle_stats.reset_index()
        
        # 重命名列
        rename_map = {
            'speed_mean': 'avg_speed',
            'speed_max': 'max_speed',
            'speed_min': 'min_speed',
            'speed_std': 'speed_std',
            'throttle_mean': 'avg_throttle',
            'throttle_max': 'max_throttle',
            'throttle_std': 'throttle_std',
            'brake_mean': 'avg_brake',
            'brake_max': 'max_brake',
            'brake_std': 'brake_std',
            'battery_soc_mean': 'avg_battery_soc',
            'battery_soc_min': 'min_battery_soc',
            'battery_temperature_mean': 'avg_battery_temp',
            'battery_temperature_max': 'max_battery_temp',
            'motor_temperature_mean': 'avg_motor_temp',
            'motor_temperature_max': 'max_motor_temp',
            'battery_voltage_mean': 'avg_battery_voltage',
            'battery_voltage_min': 'min_battery_voltage',
            'battery_voltage_max': 'max_battery_voltage',
            'battery_current_mean': 'avg_battery_current',
            'ac_power_mean': 'avg_ac_power',
            'ac_power_sum': 'total_ac_power',
            'timestamp_count': 'total_records',
            'energy_consumption_rate_mean': 'avg_energy_rate',
        }
        
        vehicle_stats = vehicle_stats.rename(columns=rename_map)
        
        # 计算派生特征
        vehicle_stats['speed_range'] = vehicle_stats['max_speed'] - vehicle_stats['min_speed']
        vehicle_stats['throttle_range'] = vehicle_stats['max_throttle'] - vehicle_stats['avg_throttle']
        vehicle_stats['high_throttle_ratio'] = vehicle_stats['max_throttle'] / 100.0
        vehicle_stats['high_brake_ratio'] = vehicle_stats['max_brake'] / 100.0
        
        return vehicle_stats
    
    def identify_driving_scenario(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        识别驾驶工况
        
        Args:
            df: 车辆聚合数据
        
        Returns:
            添加工况标签的DataFrame
        """
        df = df.copy()
        
        def classify_scenario(row):
            speed = row['avg_speed']
            throttle = row['avg_throttle']
            brake = row['avg_brake']
            throttle_std = row.get('throttle_std', 30)
            
            # 拥堵
            if speed <= 30 and brake >= 30:
                return '拥堵'
            # 巡航
            elif 60 <= speed <= 120 and throttle_std <= 15:
                return '巡航'
            # 激烈
            elif throttle >= 80 and throttle_std >= 25:
                return '激烈'
            # 经济
            elif throttle <= 50 and throttle_std <= 20:
                return '经济'
            else:
                return '均衡'
        
        df['driving_scenario'] = df.apply(classify_scenario, axis=1)
        
        return df
    
    def cluster_driving_patterns(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        使用K-Means聚类驾驶模式
        
        Args:
            df: 车辆聚合数据
        
        Returns:
            (聚类后的DataFrame, 聚类中心)
        """
        feature_cols = CLUSTERING_CONFIG["features_for_clustering"]
        
        # 确保所有特征列存在
        for col in feature_cols:
            if col not in df.columns:
                df[col] = 50  # 默认值
        
        # 使用sklearn进行聚类
        features = df[feature_cols].fillna(50)
        
        # 标准化
        scaler = MinMaxScaler()
        scaled_features = scaler.fit_transform(features)
        
        # 确定聚类数量（不能大于样本数）
        n_samples = len(df)
        n_clusters = min(CLUSTERING_CONFIG["n_clusters"], n_samples)
        
        # K-Means聚类
        from sklearn.cluster import KMeans as SklearnKMeans
        kmeans = SklearnKMeans(
            n_clusters=n_clusters,
            random_state=CLUSTERING_CONFIG["random_state"],
            n_init=10
        )
        df['cluster'] = kmeans.fit_predict(scaled_features)
        
        # 聚类中心
        cluster_centers = pd.DataFrame(
            kmeans.cluster_centers_,
            columns=feature_cols
        )
        cluster_centers['cluster'] = range(len(cluster_centers))
        
        logger.info(f"聚类完成，共{n_clusters}个簇")
        
        return df, cluster_centers


class UserProfileBuilder:
    """用户画像构建器"""
    
    def __init__(self):
        """初始化画像构建器"""
        self.profile_tags = USER_PROFILE_TAGS
    
    def calculate_driving_aggression_index(
        self,
        avg_throttle: float,
        max_throttle: float,
        throttle_std: float,
        avg_brake: float,
        max_brake: float
    ) -> float:
        """计算驾驶激进指数"""
        throttle_score = (avg_throttle * 0.3 + max_throttle * 0.4 + throttle_std * 0.3)
        brake_score = (avg_brake * 0.3 + max_brake * 0.7)
        aggression_index = throttle_score * 0.6 + brake_score * 0.4
        return round(min(100, max(0, aggression_index)), 2)
    
    def calculate_ac_dependency(
        self,
        avg_ac_power: float,
        total_ac_power: float,
        total_records: int
    ) -> float:
        """计算空调依赖度"""
        power_score = min(100, avg_ac_power * 10)
        usage_score = min(100, (total_ac_power / total_records) * 100)
        return round((power_score + usage_score) / 2, 2)
    
    def calculate_charging_preference(
        self,
        min_soc: float,
        avg_soc: float
    ) -> float:
        """计算充电偏好"""
        low_soc_ratio = max(0, (20 - min_soc) / 20)
        high_soc_ratio = (avg_soc - 30) / 70
        preference_score = (1 - low_soc_ratio) * 50 + high_soc_ratio * 50
        return round(min(100, max(0, preference_score)), 2)
    
    def calculate_energy_consumption_level(
        self,
        avg_energy_rate: float,
        avg_speed: float
    ) -> float:
        """计算能耗等级"""
        if avg_speed > 0:
            kwh_per_100km = (avg_energy_rate / avg_speed) * 100
        else:
            kwh_per_100km = 20
        
        if kwh_per_100km < 12:
            return 1.0
        elif kwh_per_100km < 15:
            return 2.0
        elif kwh_per_100km < 18:
            return 3.0
        elif kwh_per_100km < 22:
            return 4.0
        else:
            return 5.0
    
    def calculate_high_temp_exposure(
        self,
        avg_battery_temp: float,
        max_battery_temp: float,
        avg_motor_temp: float,
        max_motor_temp: float
    ) -> float:
        """计算高温暴露度"""
        battery_score = 0
        if avg_battery_temp > 40:
            battery_score += 25
        if max_battery_temp > 50:
            battery_score += 25
        
        motor_score = 0
        if avg_motor_temp > 80:
            motor_score += 25
        if max_motor_temp > 120:
            motor_score += 25
        
        return round(battery_score + motor_score, 2)
    
    def calculate_rapid_accel_frequency(
        self,
        max_throttle: float,
        throttle_std: float
    ) -> float:
        """计算急加速频率"""
        max_score = min(100, max_throttle)
        std_score = min(100, throttle_std * 3)
        return round((max_score + std_score) / 2, 2)
    
    def calculate_braking_intensity(
        self,
        avg_brake: float,
        max_brake: float,
        brake_std: float
    ) -> float:
        """计算制动强度"""
        avg_score = avg_brake
        max_score = min(100, max_brake)
        std_score = min(100, brake_std * 3)
        return round(avg_score * 0.4 + max_score * 0.4 + std_score * 0.2, 2)
    
    def calculate_range_anxiety(
        self,
        min_soc: float,
        avg_soc: float
    ) -> float:
        """计算续航焦虑度"""
        if min_soc < 5:
            low_soc_score = 100
        elif min_soc < 15:
            low_soc_score = 80
        elif min_soc < 20:
            low_soc_score = 50
        else:
            low_soc_score = max(0, 30 - (min_soc - 20) * 3)
        
        if avg_soc < 30:
            avg_soc_score = 80
        elif avg_soc < 50:
            avg_soc_score = 50
        else:
            avg_soc_score = max(0, 30 - (avg_soc - 50) * 0.6)
        
        return round(low_soc_score * 0.6 + avg_soc_score * 0.4, 2)
    
    def build_user_profile(self, vehicle_stats: pd.DataFrame) -> pd.DataFrame:
        """构建用户画像"""
        profiles = []
        
        for _, row in vehicle_stats.iterrows():
            profile = {
                "vehicle_id": row["vehicle_id"],
                "driving_aggression_index": self.calculate_driving_aggression_index(
                    row.get("avg_throttle", 50),
                    row.get("max_throttle", 80),
                    row.get("throttle_std", 15),
                    row.get("avg_brake", 20),
                    row.get("max_brake", 50)
                ),
                "ac_dependency": self.calculate_ac_dependency(
                    row.get("avg_ac_power", 2),
                    row.get("total_ac_power", 2000),
                    row.get("total_records", 1000)
                ),
                "charging_preference": self.calculate_charging_preference(
                    row.get("min_battery_soc", 30),
                    row.get("avg_battery_soc", 70)
                ),
                "energy_consumption_level": self.calculate_energy_consumption_level(
                    row.get("avg_energy_rate", 5),
                    row.get("avg_speed", 60)
                ),
                "high_temp_exposure": self.calculate_high_temp_exposure(
                    row.get("avg_battery_temp", 30),
                    row.get("max_battery_temp", 40),
                    row.get("avg_motor_temp", 60),
                    row.get("max_motor_temp", 90)
                ),
                "rapid_accel_frequency": self.calculate_rapid_accel_frequency(
                    row.get("max_throttle", 70),
                    row.get("throttle_std", 15)
                ),
                "braking_intensity": self.calculate_braking_intensity(
                    row.get("avg_brake", 20),
                    row.get("max_brake", 50),
                    row.get("brake_std", 10)
                ),
                "range_anxiety": self.calculate_range_anxiety(
                    row.get("min_battery_soc", 30),
                    row.get("avg_battery_soc", 70)
                ),
            }
            
            profiles.append(profile)
        
        profile_df = pd.DataFrame(profiles)
        
        if "driving_scenario" in vehicle_stats.columns:
            profile_df["primary_scenario"] = vehicle_stats["driving_scenario"].values
        
        if "cluster" in vehicle_stats.columns:
            profile_df["cluster"] = vehicle_stats["cluster"].values
        
        logger.info(f"用户画像构建完成: {len(profile_df)} 个用户")
        
        return profile_df
    
    def generate_profile_summary(self, profile_df: pd.DataFrame) -> Dict:
        """生成画像摘要"""
        summary = {
            "total_users": len(profile_df),
            "timestamp": datetime.now().isoformat(),
            "tag_statistics": {}
        }
        
        for tag in ["driving_aggression_index", "ac_dependency", "charging_preference",
                    "high_temp_exposure", "rapid_accel_frequency", "braking_intensity", "range_anxiety"]:
            if tag in profile_df.columns:
                summary["tag_statistics"][tag] = {
                    "mean": round(profile_df[tag].mean(), 2),
                    "std": round(profile_df[tag].std(), 2),
                    "min": round(profile_df[tag].min(), 2),
                    "max": round(profile_df[tag].max(), 2),
                }
        
        if "energy_consumption_level" in profile_df.columns:
            summary["energy_level_distribution"] = profile_df["energy_consumption_level"].value_counts().to_dict()
        
        if "primary_scenario" in profile_df.columns:
            summary["scenario_distribution"] = profile_df["primary_scenario"].value_counts().to_dict()
        
        if "cluster" in profile_df.columns:
            summary["cluster_distribution"] = profile_df["cluster"].value_counts().to_dict()
        
        return summary


def main():
    """主函数 - 测试特征工程和用户画像"""
    print("=" * 60)
    print("特征工程与用户画像测试")
    print("=" * 60)
    
    from src.data_generator import CANDataGenerator
    
    # 生成或加载数据
    generator = CANDataGenerator(num_vehicles=5, records_per_vehicle=10000)
    data = generator.load_data()
    
    if data is None:
        print("未找到数据，开始生成...")
        data = generator.generate_all_data()
        generator.save_data(data)
    
    # 创建特征工程引擎
    print("\n初始化特征工程引擎...")
    feature_engine = SparkFeatureEngine()
    
    # 添加特征
    print("添加时间特征...")
    data = feature_engine.add_time_features(data)
    
    print("添加派生特征...")
    data = feature_engine.add_derived_features(data)
    
    # 按车辆聚合
    print("按车辆聚合统计...")
    vehicle_stats = feature_engine.aggregate_by_vehicle(data)
    
    # 识别驾驶工况
    print("识别驾驶工况...")
    vehicle_stats = feature_engine.identify_driving_scenario(vehicle_stats)
    
    # 聚类分析
    print("进行聚类分析...")
    vehicle_stats, cluster_centers = feature_engine.cluster_driving_patterns(vehicle_stats)
    
    # 构建用户画像
    print("\n构建用户画像...")
    profile_builder = UserProfileBuilder()
    profile_df = profile_builder.build_user_profile(vehicle_stats)
    
    # 显示结果
    print("\n用户画像结果:")
    print(profile_df[['vehicle_id', 'driving_aggression_index', 'energy_consumption_level', 
                      'primary_scenario', 'cluster']].to_string())
    
    # 生成画像摘要
    summary = profile_builder.generate_profile_summary(profile_df)
    print("\n画像摘要:")
    for key, value in summary.items():
        if key != 'tag_statistics':
            print(f"  {key}: {value}")
    
    # 保存结果
    profile_path = DATA_PROCESSED_DIR / "user_profiles.csv"
    profile_df.to_csv(profile_path, index=False)
    print(f"\n用户画像已保存: {profile_path}")
    
    stats_path = DATA_PROCESSED_DIR / "vehicle_stats.csv"
    vehicle_stats.to_csv(stats_path, index=False)
    print(f"车辆统计已保存: {stats_path}")
    
    print("\n" + "=" * 60)
    print("特征工程与用户画像测试完成")
    print("=" * 60)
    
    return profile_df, vehicle_stats


if __name__ == "__main__":
    profile_df, vehicle_stats = main()
