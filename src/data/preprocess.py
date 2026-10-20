"""Tiền xử lý dữ liệu MovieLens 1M: nguồn logic DUY NHẤT cho notebook 01, 02 và mọi mô hình.

Quy trình (notebook 01 + phần tạo master của notebook 02):
    read_raw() -> clean_users / clean_movies / clean_ratings -> save_cleaned() -> build_master_dataset()

Schema chung (snake_case) của dữ liệu đã làm sạch:
    users  : user_id, gender, gender_desc, age, age_group, occupation, occupation_name, zip_code
    movies : movie_id, title, clean_title, release_year, genres
    ratings: user_id, movie_id, rating, timestamp, datetime
"""
import numpy as np
import pandas as pd

from src.config import (CLEANED_MOVIES_FILE, CLEANED_RATINGS_FILE, CLEANED_USERS_FILE, MASTER_FILE,
                        PROCESSED_DIR, RAW_DIR)

AGE_MAP = {1: "Under 18", 18: "18-24", 25: "25-34", 35: "35-44", 45: "45-49", 50: "50-55", 56: "56+"}
AGE_ORDER = list(AGE_MAP.values())

OCCUPATION_MAP = {
    0: "other", 1: "academic/educator", 2: "artist", 3: "clerical/admin", 4: "college/grad student",
    5: "customer service", 6: "doctor/health care", 7: "executive/managerial", 8: "farmer", 9: "homemaker",
    10: "K-12 student", 11: "lawyer", 12: "programmer", 13: "retired", 14: "sales/marketing", 15: "scientist",
    16: "self-employed", 17: "technician/engineer", 18: "tradesman/craftsman", 19: "unemployed", 20: "writer",
}

GENDER_MAP = {"M": "Male", "F": "Female"}

# Tiêu đề thô có dạng "Tên Phim (YYYY)"
YEAR_PATTERN = r"\((\d{4})\)\s*$"
YEAR_SUFFIX_PATTERN = r"\s*\(\d{4}\)\s*$"


# đọc dữ liệu thô
def read_raw(raw_dir=RAW_DIR) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Đọc users.dat, movies.dat, ratings.dat (phân cách '::', mã latin-1). Trả về (users, movies, ratings)."""
    users = pd.read_csv(raw_dir / "users.dat", sep="::", engine="python", encoding="latin-1", header=None,
                        names=["user_id", "gender", "age", "occupation", "zip_code"])
    movies = pd.read_csv(raw_dir / "movies.dat", sep="::", engine="python", encoding="latin-1", header=None,
                         names=["movie_id", "title", "genres"])
    # ratings.dat chỉ chứa số: tách theo ':' bằng engine C (nhanh hơn nhiều engine python) rồi lấy cột chẵn.
    ratings = pd.read_csv(raw_dir / "ratings.dat", sep=":", header=None, usecols=[0, 2, 4, 6],
                          names=["user_id", "_a", "movie_id", "_b", "rating", "_c", "timestamp"])
    return users, movies, ratings


# làm sạch từng bảng
def clean_users(users_raw: pd.DataFrame) -> pd.DataFrame:
    """Thêm nhãn giới tính / nhóm tuổi / nghề nghiệp, làm sạch zip_code."""
    users = users_raw.copy()
    users["gender_desc"] = users["gender"].map(GENDER_MAP)
    users["age_group"] = users["age"].map(AGE_MAP)
    users["occupation_name"] = users["occupation"].map(OCCUPATION_MAP)
    users["zip_code"] = users["zip_code"].astype(str).str.strip()
    return users[["user_id", "gender", "gender_desc", "age", "age_group",
                  "occupation", "occupation_name", "zip_code"]]


def clean_movies(movies_raw: pd.DataFrame) -> pd.DataFrame:
    """Tách release_year từ tiêu đề, tạo clean_title (bỏ năm), chuẩn hóa genres."""
    movies = movies_raw.copy()
    movies["release_year"] = movies["title"].str.extract(YEAR_PATTERN, expand=False).astype(int)
    movies["clean_title"] = movies["title"].str.replace(YEAR_SUFFIX_PATTERN, "", regex=True).str.strip()
    movies["genres"] = movies["genres"].str.strip()
    return movies[["movie_id", "title", "clean_title", "release_year", "genres"]]


def clean_ratings(ratings_raw: pd.DataFrame) -> pd.DataFrame:
    """Thêm cột datetime, ép kiểu số nguyên, sắp xếp theo (user_id, timestamp)."""
    ratings = ratings_raw.copy()
    ratings["datetime"] = pd.to_datetime(ratings["timestamp"], unit="s")
    for col in ("user_id", "movie_id", "rating"):
        ratings[col] = ratings[col].astype(int)
    return ratings.sort_values(by=["user_id", "timestamp"]).reset_index(drop=True)


def preprocess_raw(raw_dir=RAW_DIR) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Đọc + làm sạch cả 3 bảng. Trả về (users, movies, ratings) đã làm sạch."""
    users_raw, movies_raw, ratings_raw = read_raw(raw_dir)
    return clean_users(users_raw), clean_movies(movies_raw), clean_ratings(ratings_raw)


# lưu / đọc dữ liệu sạch
def save_cleaned(users: pd.DataFrame, movies: pd.DataFrame, ratings: pd.DataFrame) -> list:
    """Lưu 3 bảng sạch vào data/processed/cleaned_*.csv. Trả về danh sách đường dẫn."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    paths = [CLEANED_USERS_FILE, CLEANED_MOVIES_FILE, CLEANED_RATINGS_FILE]
    for df, path in zip((users, movies, ratings), paths):
        df.to_csv(path, index=False, encoding="utf-8")
    return paths


def load_cleaned(build_if_missing: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Đọc 3 bảng sạch từ data/processed/ (cùng kiểu dữ liệu như lúc tạo ra).

    Nếu chưa có file và build_if_missing=True thì chạy tiền xử lý từ data/raw/ rồi lưu lại.
    """
    paths = (CLEANED_USERS_FILE, CLEANED_MOVIES_FILE, CLEANED_RATINGS_FILE)
    if not all(p.exists() for p in paths):
        if not build_if_missing:
            raise FileNotFoundError("Chưa có dữ liệu sạch, hãy chạy notebook 01 hoặc `python main.py prepare`")
        users, movies, ratings = preprocess_raw()
        save_cleaned(users, movies, ratings)
        return users, movies, ratings
    users = pd.read_csv(CLEANED_USERS_FILE, dtype={"zip_code": str})
    movies = pd.read_csv(CLEANED_MOVIES_FILE)
    ratings = pd.read_csv(CLEANED_RATINGS_FILE, parse_dates=["datetime"])
    ratings["datetime"] = ratings["datetime"].astype("datetime64[s]")   # như pd.to_datetime(unit="s") lúc tạo
    return users, movies, ratings


# master dataset 
def build_master_dataset(users: pd.DataFrame, movies: pd.DataFrame, ratings: pd.DataFrame) -> pd.DataFrame:
    """Gộp ratings + users + movies (inner join) thành một bảng phẳng cho EDA."""
    return ratings.merge(users, on="user_id", how="inner").merge(movies, on="movie_id", how="inner")


def save_master(master: pd.DataFrame):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    master.to_csv(MASTER_FILE, index=False, encoding="utf-8")
    return MASTER_FILE


# tiện ích dùng chung
def genres_multi_hot(movies: pd.DataFrame) -> pd.DataFrame:
    """Multi-hot thể loại: index = movie_id, cột genre_<Thể loại> (sắp xếp theo tên), kiểu int8."""
    genres = sorted({g for sub in movies["genres"].dropna().str.split("|") for g in sub})
    G = movies["genres"].fillna("").str.get_dummies(sep="|").reindex(columns=genres, fill_value=0)
    G.columns = [f"genre_{g}" for g in genres]
    G.index = movies["movie_id"].to_numpy()
    return G.astype(np.int8)
