"""Mở phần mềm CineMatch (PyQt6 + MySQL): python run_app.py

Chạy được từ bất kỳ thư mục nào: thư mục dự án được thêm vào sys.path và thư mục làm việc được chuyển về ui/
để các đường dẫn ảnh ../images/ trong file giao diện hoạt động.
Lần chạy đầu tiên trên CSDL vừa tạo bằng mysql/mrs_schema.sql + src/database.py, phần mềm tự bổ sung các cột/bảng
hỗ trợ và đăng ký mô hình (giống chạy python app/setup_database.py).
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(os.path.join(ROOT, "ui"))

from app.utils.SchemaUtil import SchemaUtil

missing = SchemaUtil.missingParts()
if missing:
    print("CSDL còn thiếu:", ", ".join(missing[:6]), "..." if len(missing) > 6 else "")
    print("Đang chạy app/setup_database.py ...")
    import runpy
    runpy.run_path(os.path.join(ROOT, "app", "setup_database.py"), run_name="__main__")

from PyQt6.QtWidgets import QApplication, QMainWindow

from ui.LoginMainWindowEx import LoginMainWindowEx

app = QApplication(sys.argv)
myui = LoginMainWindowEx()
myui.setupUi(QMainWindow())
myui.showWindow()
app.exec()
