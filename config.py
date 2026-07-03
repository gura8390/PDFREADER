"""
配置管理模块 v2.0
负责读写config.json，保存用户设置
"""

import json
import os
from typing import Any, Dict
from utils import setup_logger

logger = setup_logger("config")

# 默认配置
DEFAULT_CONFIG = {
    # 窗口设置
    "window": {
        "width": 1200,
        "height": 800,
        "x": None,
        "y": None,
        "maximized": False
    },
    
    # 最近打开的目录
    "recent": {
        "keyword_dir": "",
        "pdf_dir": "",
        "output_dir": ""
    },
    
    # 匹配设置
    "match": {
        "mode": "exact",           # exact=精确, fuzzy=模糊, regex=正则
        "case_sensitive": True,    # 区分大小写
        "context_length": 30       # 上下文长度
    },
    
    # PDF设置
    "pdf": {
        "input_type": "single",    # single=单个, multiple=多个, folder=文件夹
        "use_ocr": False,          # 是否使用OCR
        "auto_detect_ocr": True    # 自动检测是否需要OCR
    },
    
    # 缓存设置
    "cache": {
        "enabled": True,           # 是否启用缓存
        "max_age_days": 30,        # 缓存有效期（天）
        "max_size_mb": 500         # 最大缓存大小（MB）
    },
    
    # 导出设置
    "export": {
        "formats": {
            "excel": True,
            "csv": False,
            "json": False
        },
        "include_context": True,   # 是否包含上下文
        "context_chars_before": 30,
        "context_chars_after": 30,
        "sort_by": "count",        # count=次数, name=名称, first_page=首次出现
        "sort_order": "desc"       # asc=升序, desc=降序
    },
    
    # OCR设置
    "ocr": {
        "language": "chi_sim+eng",  # OCR语言
        "dpi": 300                  # OCR分辨率
    },
    
    # 日志设置
    "log": {
        "level": "INFO",
        "file": ""
    }
}


class Config:
    """配置管理类"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.data = {}
        self.load()
    
    def load(self) -> None:
        """加载配置文件"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                logger.info(f"加载配置文件: {self.config_path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"配置文件加载失败，使用默认配置: {e}")
                self.data = {}
        
        # 合并默认配置（确保所有键都存在）
        self._merge_defaults(DEFAULT_CONFIG, self.data)
    
    def save(self) -> None:
        """保存配置文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            logger.info(f"保存配置文件: {self.config_path}")
        except IOError as e:
            logger.error(f"配置文件保存失败: {e}")
    
    def _merge_defaults(self, defaults: Dict, target: Dict) -> None:
        """递归合并默认配置"""
        for key, value in defaults.items():
            if key not in target:
                target[key] = value
            elif isinstance(value, dict) and isinstance(target[key], dict):
                self._merge_defaults(value, target[key])
    
    def get(self, *keys, default=None) -> Any:
        """
        获取配置值
        
        使用方式:
            config.get("window", "width")
            config.get("match", "mode")
        """
        current = self.data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
    
    def set(self, *keys_and_value) -> None:
        """
        设置配置值
        
        使用方式:
            config.set("window", "width", 1400)
            config.set("match", "mode", "fuzzy")
        """
        if len(keys_and_value) < 2:
            raise ValueError("至少需要一个键和一个值")
        
        *keys, value = keys_and_value
        current = self.data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
    
    def update_recent(self, **kwargs) -> None:
        """
        更新最近打开的目录
        
        Args:
            keyword_dir: 关键词库目录
            pdf_dir: PDF目录
            output_dir: 输出目录
        """
        for key, value in kwargs.items():
            if value and key in ["keyword_dir", "pdf_dir", "output_dir"]:
                self.set("recent", key, value)
        self.save()
    
    def update_window(self, width: int, height: int, x: int = None, y: int = None, maximized: bool = False) -> None:
        """更新窗口设置"""
        self.set("window", "width", width)
        self.set("window", "height", height)
        if x is not None:
            self.set("window", "x", x)
        if y is not None:
            self.set("window", "y", y)
        self.set("window", "maximized", maximized)
        self.save()
    
    def reset(self) -> None:
        """重置为默认配置"""
        self.data = json.loads(json.dumps(DEFAULT_CONFIG))
        self.save()
        logger.info("配置已重置为默认值")


# 全局配置实例
_config_instance = None


def get_config(config_path: str = "config.json") -> Config:
    """获取全局配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_path)
    return _config_instance
