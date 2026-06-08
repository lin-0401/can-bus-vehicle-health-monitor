"""
CAN总线新能源汽车用户画像与健康监控系统
爬虫模块 - 从多源获取CAN总线数据或驾驶行为数据

支持的数据源：
1. Figshare API - 新能源汽车/CAN相关数据集
2. Zenodo API - 驾驶行为数据集
3. Mendeley Data API - CAN总线数据集
4. 合成数据生成 - 基于真实驾驶规律
"""

import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import urllib.request
import urllib.error
import ssl

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入配置
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SCRAPER_CONFIG, DATA_RAW_DIR, DATA_CONFIG

class CANDataScraper:
    """CAN总线数据爬虫类 - 支持多源数据获取"""
    
    def __init__(self, timeout: int = None, retry_times: int = None):
        """
        初始化爬虫
        
        Args:
            timeout: 请求超时时间(秒)
            retry_times: 重试次数
        """
        self.timeout = timeout or SCRAPER_CONFIG["timeout"]
        self.retry_times = retry_times or SCRAPER_CONFIG["retry_times"]
        self.user_agent = SCRAPER_CONFIG["user_agent"]
        self.headers = SCRAPER_CONFIG["headers"]
        
        # 创建SSL上下文(忽略证书验证)
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        # 数据源URL
        self.data_sources = {
            "figshare": "https://api.figshare.com/v2",
            "zenodo": "https://zenodo.org/api",
            "mendeley": "https://data.mendeley.com/api",
        }
        
        # 已检查的数据集标识
        self.checked_datasets = set()
    
    def _create_request(self, url: str, method: str = "GET") -> urllib.request.Request:
        """
        创建HTTP请求对象
        
        Args:
            url: 请求URL
            method: 请求方法
        
        Returns:
            urllib.request.Request对象
        """
        headers = {
            "User-Agent": self.user_agent,
            **self.headers
        }
        return urllib.request.Request(url, headers=headers, method=method)
    
    def _fetch_url(self, url: str, data: bytes = None) -> Optional[str]:
        """
        获取URL内容
        
        Args:
            url: 目标URL
            data: POST数据
        
        Returns:
            响应内容字符串，失败返回None
        """
        for attempt in range(self.retry_times):
            try:
                request = self._create_request(url)
                if data:
                    request.data = data
                
                with urllib.request.urlopen(
                    request, 
                    timeout=self.timeout,
                    context=self.ssl_context
                ) as response:
                    content = response.read().decode("utf-8")
                    logger.info(f"成功获取URL: {url}")
                    return content
                    
            except urllib.error.HTTPError as e:
                logger.warning(f"HTTP错误 {e.code}: {url} (尝试 {attempt + 1}/{self.retry_times})")
                if attempt < self.retry_times - 1:
                    time.sleep(SCRAPER_CONFIG["retry_delay"])
                    
            except urllib.error.URLError as e:
                logger.warning(f"URL错误: {e.reason} (尝试 {attempt + 1}/{self.retry_times})")
                if attempt < self.retry_times - 1:
                    time.sleep(SCRAPER_CONFIG["retry_delay"])
                    
            except Exception as e:
                logger.error(f"未知错误: {str(e)}")
                break
                
        return None
    
    def search_figshare(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        搜索Figshare数据集
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
        
        Returns:
            数据集信息列表
        """
        logger.info(f"正在搜索Figshare: {query}")
        
        # Figshare搜索API
        search_url = f"{self.data_sources['figshare']}/articles/search"
        params = f"?search_for={query}&page_size={max_results}"
        
        content = self._fetch_url(search_url + params)
        if not content:
            logger.warning("Figshare搜索失败或无结果")
            return []
        
        try:
            data = json.loads(content)
            results = []
            
            for item in data.get("items", []):
                results.append({
                    "source": "figshare",
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "doi": item.get("doi"),
                    "url": item.get("url"),
                    "files": item.get("files", []),
                    "published_date": item.get("published_date"),
                })
            
            logger.info(f"Figshare返回 {len(results)} 个结果")
            return results
            
        except json.JSONDecodeError as e:
            logger.error(f"Figshare响应JSON解析失败: {e}")
            return []
    
    def search_zenodo(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        搜索Zenodo数据集
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
        
        Returns:
            数据集信息列表
        """
        logger.info(f"正在搜索Zenodo: {query}")
        
        # Zenodo搜索API
        search_url = f"{self.data_sources['zenodo']}/records"
        params = f"?q={query}&size={max_results}&sort=mostrecent"
        
        content = self._fetch_url(search_url + params)
        if not content:
            logger.warning("Zenodo搜索失败或无结果")
            return []
        
        try:
            data = json.loads(content)
            results = []
            
            for hit in data.get("hits", {}).get("hits", []):
                metadata = hit.get("metadata", {})
                results.append({
                    "source": "zenodo",
                    "id": hit.get("id"),
                    "title": metadata.get("title"),
                    "doi": hit.get("doi"),
                    "url": hit.get("links", {}).get("self"),
                    "files": [
                        {
                            "key": f.get("key"),
                            "size": f.get("size"),
                            "type": f.get("type"),
                        }
                        for f in hit.get("files", [])
                    ],
                    "published_date": metadata.get("publication_date"),
                })
            
            logger.info(f"Zenodo返回 {len(results)} 个结果")
            return results
            
        except json.JSONDecodeError as e:
            logger.error(f"Zenodo响应JSON解析失败: {e}")
            return []
    
    def search_mendeley(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        搜索Mendeley Data数据集
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
        
        Returns:
            数据集信息列表
        """
        logger.info(f"正在搜索Mendeley: {query}")
        
        # Mendeley Data搜索API (公开API)
        search_url = f"https://data.mendeley.com/api/datasets"
        params = f"?search={query}&limit={max_results}"
        
        content = self._fetch_url(search_url + params)
        if not content:
            logger.warning("Mendeley搜索失败或无结果")
            return []
        
        try:
            data = json.loads(content)
            results = []
            
            for item in data.get("data", []):
                results.append({
                    "source": "mendeley",
                    "id": item.get("id"),
                    "title": item.get("name"),
                    "url": item.get("href"),
                    "files": item.get("files", []),
                    "published_date": item.get("created"),
                })
            
            logger.info(f"Mendeley返回 {len(results)} 个结果")
            return results
            
        except json.JSONDecodeError as e:
            logger.error(f"Mendeley响应JSON解析失败: {e}")
            return []
    
    def check_existing_data(self) -> List[Path]:
        """
        检查data/raw目录下已有的数据文件
        
        Returns:
            已有CSV文件路径列表
        """
        logger.info("检查已有数据文件...")
        
        existing_files = []
        if DATA_RAW_DIR.exists():
            for file_path in DATA_RAW_DIR.glob("*.csv"):
                file_size = file_path.stat().st_size / 1024 / 1024  # MB
                existing_files.append(file_path)
                logger.info(f"发现已有文件: {file_path.name} ({file_size:.2f} MB)")
        
        return existing_files
    
    def fetch_all_sources(self, keywords: List[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        从所有数据源搜索数据
        
        Args:
            keywords: 搜索关键词列表
        
        Returns:
            各数据源的搜索结果字典
        """
        if keywords is None:
            keywords = [
                "electric vehicle CAN bus",
                "driving behavior dataset",
                "vehicle telemetry",
                "battery management system",
            ]
        
        all_results = {
            "figshare": [],
            "zenodo": [],
            "mendeley": [],
        }
        
        for keyword in keywords:
            # 搜索各数据源
            figshare_results = self.search_figshare(keyword)
            all_results["figshare"].extend(figshare_results)
            
            time.sleep(1)  # 避免请求过快
            
            zenodo_results = self.search_zenodo(keyword)
            all_results["zenodo"].extend(zenodo_results)
            
            time.sleep(1)
            
            mendeley_results = self.search_mendeley(keyword)
            all_results["mendeley"].extend(mendeley_results)
            
            time.sleep(1)
        
        # 去重
        for source in all_results:
            seen_ids = set()
            unique_results = []
            for item in all_results[source]:
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    unique_results.append(item)
            all_results[source] = unique_results
        
        return all_results
    
    def download_dataset(self, dataset_info: Dict[str, Any], save_path: Path = None) -> bool:
        """
        下载数据集
        
        Args:
            dataset_info: 数据集信息字典
            save_path: 保存路径
        
        Returns:
            是否下载成功
        """
        source = dataset_info.get("source")
        url = dataset_info.get("url")
        
        if not url:
            logger.error(f"数据集无下载URL: {dataset_info}")
            return False
        
        if save_path is None:
            save_path = DATA_RAW_DIR / f"{source}_{dataset_info['id']}.json"
        
        logger.info(f"尝试下载数据集: {dataset_info.get('title', 'unknown')}")
        
        content = self._fetch_url(url)
        if content:
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info(f"数据集已保存到: {save_path}")
                return True
            except IOError as e:
                logger.error(f"保存数据集失败: {e}")
        
        return False


def main():
    """主函数 - 测试爬虫功能"""
    print("=" * 60)
    print("CAN总线数据爬虫测试")
    print("=" * 60)
    
    scraper = CANDataScraper()
    
    # 检查已有数据
    existing_files = scraper.check_existing_data()
    
    if existing_files:
        print(f"\n发现 {len(existing_files)} 个已有数据文件")
        print("将使用已有数据，跳过爬虫搜索")
    else:
        print("\n未发现已有数据，开始搜索在线数据源...")
        
        # 搜索关键词
        keywords = [
            "electric vehicle CAN",
            "driving behavior",
            "vehicle telemetry",
        ]
        
        results = scraper.fetch_all_sources(keywords)
        
        print("\n搜索结果汇总:")
        for source, items in results.items():
            print(f"  {source}: {len(items)} 个数据集")
        
        # 尝试下载第一个可用数据集
        for source in ["zenodo", "figshare", "mendeley"]:
            if results[source]:
                dataset = results[source][0]
                print(f"\n尝试下载 {source} 数据集: {dataset.get('title')}")
                scraper.download_dataset(dataset)
                break
    
    print("\n" + "=" * 60)
    print("爬虫测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
