import os
from typing import Any
from ruamel.yaml import YAML
import psutil
import socket
import ipaddress

import logging
logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = """
    interface: ""
    ip: ""
    port: 5678
    osc_port: 9001
    parameter_bindings:
    - {parameter_name: 碰左小腿, action_name: A通道触碰}
    - {parameter_name: 碰右小腿, action_name: B通道触碰}
    - {parameter_name: 拉尾巴, action_name: 当前通道触碰}
    - {parameter_name: 按钮面板控制, action_name: 面板控制}
    - {parameter_name: 按钮数值调节, action_name: 数值调节}
    - {parameter_name: 按钮通道调节, action_name: 通道调节}
    - {parameter_name: 按钮1, action_name: 设置模式}
    - {parameter_name: 按钮2, action_name: 重置强度}
    - {parameter_name: 按钮3, action_name: 降低强度}
    - {parameter_name: 按钮4, action_name: 增加强度}
    - {parameter_name: 按钮5, action_name: 一键开火}
    - {parameter_name: 按钮6, action_name: ChatBox状态开关}
    - {parameter_name: 按钮7, action_name: 设置波形为(连击)}
    - {parameter_name: 按钮8, action_name: 设置波形为(挑逗1)}
    - {parameter_name: 按钮9, action_name: 设置波形为(按捏渐强)}
    - {parameter_name: 按钮10, action_name: 设置波形为(心跳节奏)}
    - {parameter_name: 按钮11, action_name: 设置波形为(压缩)}
    - {parameter_name: 按钮12, action_name: 设置波形为(节奏步伐)}
    - {parameter_name: 按钮13, action_name: 设置波形为(颗粒摩擦)}
    - {parameter_name: 按钮14, action_name: 设置波形为(渐变弹跳)}
    - {parameter_name: 按钮15, action_name: 设置波形为(潮汐)}
    custom_pulses: []
    """

yaml=YAML()

# Get active IP addresses (unchanged)
def get_active_ip_addresses() -> dict[str, str]:
    ip_addresses = {}
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

def default_load_settings(default_settings = DEFAULT_SETTINGS) -> Any:
    if not os.path.exists('settings.yml'):
        settings = yaml.load(default_settings)
        save_settings(settings)
        return settings
    else:
        settings = load_settings()
        return settings

# Load the configuration from a YAML file
def load_settings() -> Any:
    if os.path.exists('settings.yml'):
        with open('settings.yml', 'r', encoding='utf-8') as f:
            logger.info("settings.yml found")
            return yaml.load(f)
    logger.info("No settings.yml found")
    return None

# Save the configuration to a YAML file
def save_settings(settings: Any):
    with open('settings.yml', 'w', encoding='utf-8') as f:
        yaml.dump(settings, f)
        logger.info("settings.yml saved")
