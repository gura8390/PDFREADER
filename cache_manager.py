"""
缓存管理模块 v2.0
提供缓存大小统计、有效期管理、清理功能
"""

import os
import json
import time
from typing import List, Dict
from utils import setup_logger

logger = setup_logger("cache_manager")


class CacheManager:
    """缓存管理器"""
    
    def __init__(self, cache_dir: str = "cache", max_age_days: int = 30, max_size_mb: int = 500):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录
            max_age_days: 缓存有效期（天）
            max_size_mb: 最大缓存大小（MB）
        """
        self.cache_dir = cache_dir
        self.max_age_days = max_age_days
        self.max_size_mb = max_size_mb
        os.makedirs(cache_dir, exist_ok=True)
    
    def get_cache_files(self) -> List[Dict]:
        """
        获取所有缓存文件信息
        
        Returns:
            缓存文件信息列表
        """
        cache_files = []
        
        if not os.path.exists(self.cache_dir):
            return cache_files
        
        for filename in os.listdir(self.cache_dir):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(self.cache_dir, filename)
            if not os.path.isfile(filepath):
                continue
            
            try:
                stat = os.stat(filepath)
                
                # 读取缓存元数据
                metadata = self._read_cache_metadata(filepath)
                
                cache_files.append({
                    'filename': filename,
                    'path': filepath,
                    'size': stat.st_size,
                    'created': stat.st_ctime,
                    'modified': stat.st_mtime,
                    'age_days': (time.time() - stat.st_mtime) / 86400,
                    'pdf_path': metadata.get('pdf_path', ''),
                    'page_count': metadata.get('page_count', 0)
                })
            except Exception as e:
                logger.warning(f"读取缓存信息失败: {filepath}, {e}")
        
        return cache_files
    
    def _read_cache_metadata(self, filepath: str) -> Dict:
        """读取缓存文件的元数据"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return {
                'pdf_path': data.get('pdf_path', ''),
                'page_count': data.get('page_count', 0)
            }
        except:
            return {}
    
    def get_total_size(self) -> int:
        """获取缓存总大小（字节）"""
        total = 0
        for cache_file in self.get_cache_files():
            total += cache_file['size']
        return total
    
    def get_total_size_str(self) -> str:
        """获取缓存总大小（可读格式）"""
        size_bytes = self.get_total_size()
        
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    def get_cache_count(self) -> int:
        """获取缓存文件数量"""
        return len(self.get_cache_files())
    
    def clear_all(self) -> int:
        """
        清除所有缓存
        
        Returns:
            删除的文件数量
        """
        count = 0
        for cache_file in self.get_cache_files():
            try:
                os.remove(cache_file['path'])
                count += 1
            except Exception as e:
                logger.warning(f"删除缓存失败: {cache_file['path']}, {e}")
        
        logger.info(f"已清除 {count} 个缓存文件")
        return count
    
    def clear_expired(self) -> int:
        """
        清除过期缓存
        
        Returns:
            删除的文件数量
        """
        count = 0
        for cache_file in self.get_cache_files():
            if cache_file['age_days'] > self.max_age_days:
                try:
                    os.remove(cache_file['path'])
                    count += 1
                    logger.debug(f"清除过期缓存: {cache_file['filename']}")
                except Exception as e:
                    logger.warning(f"删除缓存失败: {cache_file['path']}, {e}")
        
        if count > 0:
            logger.info(f"已清除 {count} 个过期缓存文件")
        return count
    
    def clear_by_size(self) -> int:
        """
        当缓存超过大小限制时，清除最旧的缓存
        
        Returns:
            删除的文件数量
        """
        max_size_bytes = self.max_size_mb * 1024 * 1024
        current_size = self.get_total_size()
        
        if current_size <= max_size_bytes:
            return 0
        
        # 按修改时间排序，最旧的在前
        cache_files = sorted(self.get_cache_files(), key=lambda x: x['modified'])
        
        count = 0
        for cache_file in cache_files:
            if current_size <= max_size_bytes:
                break
            
            try:
                os.remove(cache_file['path'])
                current_size -= cache_file['size']
                count += 1
                logger.debug(f"清除缓存: {cache_file['filename']}")
            except Exception as e:
                logger.warning(f"删除缓存失败: {cache_file['path']}, {e}")
        
        if count > 0:
            logger.info(f"已清除 {count} 个缓存文件以释放空间")
        return count
    
    def auto_cleanup(self) -> int:
        """
        自动清理：先清除过期，再检查大小
        
        Returns:
            总共删除的文件数量
        """
        count = 0
        count += self.clear_expired()
        count += self.clear_by_size()
        return count
    
    def get_status(self) -> Dict:
        """
        获取缓存状态
        
        Returns:
            状态信息字典
        """
        cache_files = self.get_cache_files()
        total_size = sum(f['size'] for f in cache_files)
        
        expired_count = sum(1 for f in cache_files if f['age_days'] > self.max_age_days)
        
        return {
            'cache_dir': self.cache_dir,
            'file_count': len(cache_files),
            'total_size': total_size,
            'total_size_str': self.get_total_size_str(),
            'max_age_days': self.max_age_days,
            'max_size_mb': self.max_size_mb,
            'expired_count': expired_count,
            'usage_percent': (total_size / (self.max_size_mb * 1024 * 1024)) * 100 if self.max_size_mb > 0 else 0
        }
    
    def get_status_summary(self) -> str:
        """获取缓存状态摘要"""
        status = self.get_status()
        
        lines = [
            f"缓存目录: {status['cache_dir']}",
            f"文件数量: {status['file_count']}",
            f"总大小: {status['total_size_str']}",
            f"有效期: {status['max_age_days']} 天",
            f"大小限制: {status['max_size_mb']} MB",
        ]
        
        if status['expired_count'] > 0:
            lines.append(f"过期文件: {status['expired_count']} 个")
        
        return '\n'.join(lines)
