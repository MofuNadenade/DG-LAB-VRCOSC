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
    language: "zh"
    enable_remote: false
    remote_address: ""
    custom_pulses: []
    custom_addresses: []
    enable_chatbox_status: false
    strength_step: 30
    fire_mode_disabled: false
    enable_panel_control: true
    dynamic_bone_mode_a: false
    dynamic_bone_mode_b: false
    pulse_mode_a: "连击"
    pulse_mode_b: "连击"
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

def default_load_settings(default_settings: Any = DEFAULT_SETTINGS) -> Any:
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
def save_settings(settings: Any) -> None:
    with open('settings.yml', 'w', encoding='utf-8') as f:
        yaml.dump(settings, f)
        logger.info("settings.yml saved")
