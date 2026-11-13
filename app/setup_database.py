import os
import sys
# Chạy ở thư mục gốc dự án: python app/setup_database.py (hoặc chạy trực tiếp trong IDE)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time

from app.ml.MovieRecommender import MovieRecommender
from app.dal.modelDAO import modelDAO
from app.utils.ConfigUtil import ConfigUtil
from app.utils.SchemaUtil import SchemaUtil

# Chuẩn bị CSDL cho phần mềm, chạy SAU 2 bước tạo CSDL của nhóm:
#   1. mysql -u root -p < mysql/mrs_schema.sql
#   2. python src/database.py
#   3. python app/setup_database.py   <- file này (run_app.py cũng tự gọi khi thấy còn thiếu)
# Việc làm: thêm cột/bảng hỗ trợ (không đụng dữ liệu gốc), tính điểm TB từng phim, đăng ký mô hình NeuMF.
start=time.time()
print("Bổ sung cột/bảng phần mềm cần:")
if not SchemaUtil.ensureSchema():
    exit()
info=modelDAO.getActiveModel()
model_path=ConfigUtil.rootPath(ConfigUtil.get("recommendation","model_path","models/main_model/neumf.npz"))
if info is None:
    if os.path.exists(model_path):
        print("Đăng ký mô hình",ConfigUtil.get("recommendation","model_path"),"...")
        print("   kết quả:",MovieRecommender.registerModel(model_path))
    else:
        print("Chưa có tệp mô hình",model_path,"- hãy chạy: python main.py export")
else:
    print("Mô hình đang dùng:",info["model_name"],info["file_name"])
print("Nạp thử mô hình:",MovieRecommender.loadModel(),MovieRecommender.last_error)
print(f"HOÀN TẤT ({time.time()-start:.0f} giây). Mở phần mềm: python run_app.py")
