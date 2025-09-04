import asyncio
import logging
import signal
import sys
from types import FrameType
from typing import Optional

from PySide6.QtWidgets import (QApplication)
from qasync import QEventLoop

from core.app_controller import AppController
# 配置日志记录器
from logger_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)


def signal_handler(signum: int, frame: Optional[FrameType]) -> None:
    """处理 Ctrl+C 信号"""
    logger.info("收到 Ctrl+C 信号，正在关闭应用...")
    QApplication.quit()


def main():
    """Main entry point for the application"""
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    
    ui_controller = AppController()
    ui_controller.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
