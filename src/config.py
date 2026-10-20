"""Cấu hình chung: đường dẫn (tính từ vị trí file này nên chạy được ở mọi máy) và hằng số thí nghiệm."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # thư mục gốc dự án

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"                            # movies.dat, ratings.dat, users.dat
PROCESSED_DIR = DATA_DIR / "processed"                # dữ liệu đã làm sạch + cache
MODELS_DIR = ROOT / "models"                          # mô hình đã huấn luyện (.pkl)
RESULTS_DIR = ROOT / "outputs"                        # metrics/*.csv, figures/*.png

# Đầu ra dữ liệu dùng chung cho mọi notebook / script (do src.data.preprocess và src.data.features tạo)
CLEANED_USERS_FILE = PROCESSED_DIR / "cleaned_users.csv"
CLEANED_MOVIES_FILE = PROCESSED_DIR / "cleaned_movies.csv"
CLEANED_RATINGS_FILE = PROCESSED_DIR / "cleaned_ratings.csv"
MASTER_FILE = PROCESSED_DIR / "master_dataset.csv"
FEATURED_FILE = PROCESSED_DIR / "featured_dataset.parquet"

SEED = 42
TEST_FRAC = 0.2          # tỉ lệ test trong phép chia theo từng user
VAL_FRAC = 0.1           # tỉ lệ validation tách từ train (dò siêu tham số)
RELEVANT_RATING = 4.0    # phim trong test có rating >= ngưỡng này được coi là "liên quan" khi đánh giá Top-N
