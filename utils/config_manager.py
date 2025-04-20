import yaml
import os
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "option_file": "config.yml",
    "search_cache_folder": "search_cache",
    "pdf_max_pages": 200,
    "batch_size": 20,
    "platform": {
        "type": "napcat",
        "http_host": "127.0.0.1",
        "http_port": 8080,
        "api_token": ""
    }
}

def load_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """加载配置文件"""
    result = DEFAULT_CONFIG.copy()
    
    if config:
        # 更新默认配置
        deep_update(result, config)
    
    # 确保必要的目录存在
    Path(result["search_cache_folder"]).mkdir(exist_ok=True, parents=True)
    
    return result

def deep_update(source: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归更新字典"""
    for key, value in override.items():
        if key in source and isinstance(source[key], dict) and isinstance(value, dict):
            deep_update(source[key], value)
        else:
            source[key] = value
    return source
