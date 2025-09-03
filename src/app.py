import asyncio
import sys

from PySide6.QtWidgets import (QApplication)
from qasync import QEventLoop

from core.app_controller import AppController
# 配置日志记录器
from logger_config import setup_logging

setup_logging()


def main():
    """Main entry point for the application"""
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    ui_controller = AppController()
    ui_controller.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
