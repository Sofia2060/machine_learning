import os
import sys
# Chạy được cả khi IDE không thêm thư mục gốc dự án vào PYTHONPATH (vd VS Code)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app.services.AuthService import AuthService

ret=AuthService.login("user_1","123456")
print(ret.ok,ret.message,ret.account.customer_id if ret.ok else None)
ret=AuthService.login("admin","123456")
print(ret.ok,ret.message,ret.account.role if ret.ok else None)
ret=AuthService.login("user_1","sai_mat_khau")
print(ret.ok,ret.message)
AuthService.login("user_1","123456")    # đăng nhập đúng -> đặt lại bộ đếm sai
