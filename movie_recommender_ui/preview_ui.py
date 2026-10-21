import os
import sys

from PyQt6 import uic
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton

# Xem trước 7 màn hình thiết kế trong thư mục ui (chỉ hiển thị giao diện, chưa kết nối CSDL)
# Cách chạy:  python preview_ui.py                 -> mở menu chọn màn hình
#             python preview_ui.py LoginMainWindow -> mở thẳng 1 màn hình
folder_ui=os.path.join(os.path.dirname(os.path.abspath(__file__)),"ui")
# Đường dẫn ảnh trong file .ui là ../images/... nên phải lấy thư mục ui làm thư mục làm việc
os.chdir(folder_ui)

SCREENS=[("LoginMainWindow","Đăng nhập"),
         ("RegisterMainWindow","Đăng ký tài khoản"),
         ("ForgotPasswordMainWindow","Quên mật khẩu (OTP)"),
         ("UserMainWindow","User – Trang chủ / Tìm kiếm / Lịch sử"),
         ("AdminDashboardMainWindow","Admin – Dashboard EDA"),
         ("ModelTestingMainWindow","Admin – Thử nghiệm mô hình ML"),
         ("DataManagementMainWindow","Admin – Quản lý CSDL")]

def openScreen(name):
    window=QMainWindow()
    uic.loadUi(f"{name}.ui",window)
    window.setWindowTitle(window.windowTitle()+"  [xem trước giao diện]")
    window.show()
    windows.append(window)

def createMenu():
    menu=QWidget()
    menu.setWindowTitle("CineMatch – Xem trước giao diện")
    menu.setMinimumWidth(380)
    layout=QVBoxLayout(menu)
    layout.setContentsMargins(20,20,20,20)
    layout.setSpacing(8)
    title=QLabel("<b style='font-size:16px'>Chọn màn hình muốn xem</b>")
    layout.addWidget(title)
    for (name,caption) in SCREENS:
        button=QPushButton(caption)
        button.setMinimumHeight(36)
        button.clicked.connect(lambda checked,n=name: openScreen(n))
        layout.addWidget(button)
    menu.show()
    return menu

app=QApplication(sys.argv)
windows=[]
if len(sys.argv)>1:
    openScreen(sys.argv[1].replace(".ui",""))
else:
    menu=createMenu()
app.exec()
