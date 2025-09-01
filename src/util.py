import io
import os
import sys

import qrcode
import qrcode.constants
from PySide6.QtGui import QPixmap


def resource_path(relative_path: str) -> str:
    """ 获取资源的绝对路径，确保开发和打包后都能正常使用。 """
    if hasattr(sys, '_MEIPASS'):  # PyInstaller 打包后的路径
        return os.path.join(getattr(sys, '_MEIPASS', ''), relative_path)
    # 开发环境下，从 src 目录开始构建路径
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def generate_qrcode(data: str) -> QPixmap:
    """生成二维码并转换为PySide6可显示的QPixmap"""
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=16, border=0)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')

    buffer = io.BytesIO()
    img.save(buffer)
    buffer.seek(0)

    qimage = QPixmap()
    qimage.loadFromData(buffer.read())

    return qimage
