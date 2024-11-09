import sys
import asyncio

from PySide6.QtWidgets import (QApplication)
from qasync import QEventLoop

from core_ui import MainWindow

# 配置日志记录器
from logger_config import setup_logging
setup_logging()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()
