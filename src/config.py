import ipaddress
import logging
import os
import socket
from typing import Optional, Any, Dict

import psutil
from ruamel.yaml import YAML

from core.defaults import DEFAULT_ADDRESSES, DEFAULT_PULSES, DEFAULT_TEMPLATES, DEFAULT_BINDINGS
from models import SettingsDict

logger = logging.getLogger(__name__)


def get_default_settings() -> SettingsDict:
    """获取默认设置，包含所有默认配置"""
    return {
        # 全局设置
        'osc_port': 9001,
        'language': "zh",

        # 网络设置
        'websocket': {
            'interface': "",
            'ip': "",
            'port': 5678,
            'enable_remote': False,
            'remote_address': "",
        },

        # 控制器设置
        'controller': {
            'enable_chatbox_status': False,
            'fire_mode_strength_step': 30,
            'fire_mode_disabled': False,
            'enable_panel_control': True,
            'dynamic_bone_mode_a': False,
            'dynamic_bone_mode_b': False,
            'current_pulse_a': "无波形",
            'current_pulse_b': "无波形",
        },

        # 默认配置数据
        'addresses': DEFAULT_ADDRESSES,
        'pulses': {name: list(data) for name, data in DEFAULT_PULSES.items()},
        'templates': DEFAULT_TEMPLATES,
        'bindings': DEFAULT_BINDINGS
    }


yaml: YAML = YAML()
# 禁用YAML引用以提高可读性
yaml.representer.ignore_aliases = lambda *args: True  # type: ignore


# Get active IP addresses (unchanged)
def get_active_ip_addresses() -> Dict[str, str]:
    ip_addresses: Dict[str, str] = {}
    for interface, addrs in psutil.net_if_addrs().items():
        if psutil.net_if_stats()[interface].isup:
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    ip_addresses[interface] = addr.address
    return ip_addresses


# Validate IP address (unchanged)
def validate_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


# Validate port (unchanged)
def validate_port(port: str | int) -> bool:
    try:
        port = int(port)
        return 0 < port < 65536
    except ValueError:
        return False


def default_load_settings() -> SettingsDict:
    """加载设置，如果不存在则创建默认设置"""
    if not os.path.exists('settings.yml'):
        settings = get_default_settings()
        save_settings(settings)
        logger.info("Created default settings.yml with all default configurations")
        return settings
    else:
        loaded_settings = load_settings()
        if loaded_settings is None:
            settings = get_default_settings()
            save_settings(settings)
            logger.info("Recreated corrupted settings.yml")
            return settings
        return loaded_settings


# Load the configuration from a YAML file
def load_settings() -> Optional[SettingsDict]:
    if os.path.exists('settings.yml'):
        with open('settings.yml', 'r', encoding='utf-8') as f:
            logger.info("settings.yml found")
            data: Any = yaml.load(f)  # type: ignore
            if isinstance(data, dict):
                return data  # type: ignore[return-value]
            else:
                logger.warning("settings.yml does not contain a valid dictionary")
                return None
    logger.info("No settings.yml found")
    return None


# Save the configuration to a YAML file
def save_settings(settings: SettingsDict) -> None:
    with open('settings.yml', 'w', encoding='utf-8') as f:
        yaml.dump(settings, f)  # type: ignore
        logger.info("settings.yml saved")
