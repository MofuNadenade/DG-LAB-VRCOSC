import asyncio
import sys

from PySide6.QtWidgets import (QApplication)
from qasync import QEventLoop

from gui.ui_controller import UIController
# 配置日志记录器
from logger_config import setup_logging

setup_logging()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    ui_controller = UIController()
    ui_controller.show()

    with loop:
        loop.run_forever()
