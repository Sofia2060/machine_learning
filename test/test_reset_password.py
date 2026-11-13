import os
import sys
# Chạy được cả khi IDE không thêm thư mục gốc dự án vào PYTHONPATH (vd VS Code)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMainWindow

from ui.ResetPasswordMainWindowEx import ResetPasswordMainWindowEx
app=QApplication(sys.argv)
myui=ResetPasswordMainWindowEx()
myui.setupUi(QMainWindow())
myui.setEmail("user_1@gmail.com")
myui.showWindow()
app.exec()
