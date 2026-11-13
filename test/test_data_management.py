import os
import sys
# Chạy được cả khi IDE không thêm thư mục gốc dự án vào PYTHONPATH (vd VS Code)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMainWindow

from ui.DataManagementMainWindowEx import DataManagementMainWindowEx
from app.services.AuthService import AuthService

# Mở thẳng màn hình này (bỏ qua bước đăng nhập) để chạy thử nhanh
us=AuthService.login("admin","123456").account
app=QApplication(sys.argv)
myui=DataManagementMainWindowEx()
myui.setupUi(QMainWindow())
myui.setLoginUser(us)
myui.showWindow()
app.exec()
