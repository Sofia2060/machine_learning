import json
import os

# Đọc cấu hình vận hành từ config/config.json (NFR-15, NFR-20): thông tin kết nối CSDL, tài khoản
# admin mặc định, N của gợi ý, ngưỡng phim nổi bật, đường dẫn mô hình... không ghi cứng trong mã nguồn
folder_project=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # thư mục app
folder_root=os.path.dirname(folder_project)                                         # thư mục gốc dự án (có main.py, src/)
file_config=os.path.join(folder_project,"config","config.json")
# config.json chứa mật khẩu MySQL nên không đưa lên git; chưa có thì dùng file mẫu config.example.json
file_config_example=os.path.join(folder_project,"config","config.example.json")


class ConfigUtil:
    config=None
    errors=[]

    @staticmethod
    def load():
        if ConfigUtil.config is None:
            try:
                path=file_config if os.path.exists(file_config) else file_config_example
                ConfigUtil.config=json.load(open(path,encoding="utf-8"))
            except Exception as e:
                print("Không đọc được config.json:",e)
                ConfigUtil.config={}
            ConfigUtil.errors=ConfigUtil.validate(ConfigUtil.config)
        return ConfigUtil.config
    @staticmethod
    def get(section,key,default=None):
        return ConfigUtil.load().get(section,{}).get(key,default)
    @staticmethod
    def projectPath(relative_path):
        return os.path.join(folder_project,relative_path)
    @staticmethod
    def rootPath(relative_path):
        # Đường dẫn trong config tính từ thư mục gốc dự án
        return relative_path if os.path.isabs(relative_path) else os.path.join(folder_root,relative_path)
    @staticmethod
    def validate(config):
        # Kiểm tra cấu hình khi khởi tạo, trả về danh sách lỗi để giao diện thông báo rõ ràng
        errors=[]
        db=config.get("database",{})
        for key in ("server","port","database","username"):
            if key not in db:
                errors.append(f"Thiếu database.{key}")
        rec=config.get("recommendation",{})
        options=rec.get("top_n_options",[5,10])
        if not isinstance(options,list) or len(options)==0 or \
                not all(isinstance(n,int) and 1<=n<=50 for n in options):
            errors.append("recommendation.top_n_options phải là danh sách số nguyên từ 1 đến 50")
        if rec.get("top_n_default",10) not in options:
            errors.append("recommendation.top_n_default phải nằm trong top_n_options")
        threshold=rec.get("featured_min_ratings",5)
        if not isinstance(threshold,int) or threshold<1:
            errors.append("recommendation.featured_min_ratings phải là số nguyên dương")
        if not rec.get("model_path"):
            errors.append("Thiếu recommendation.model_path")
        return errors
    @staticmethod
    def topNOptions():
        options=ConfigUtil.get("recommendation","top_n_options",[5,10])
        return options if "top_n_options" not in " ".join(ConfigUtil.errors) else [5,10]
    @staticmethod
    def featuredMinRatings():
        value=ConfigUtil.get("recommendation","featured_min_ratings",5)
        return value if isinstance(value,int) and value>=1 else 5
