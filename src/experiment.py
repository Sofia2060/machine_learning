"""Thiết lập thí nghiệm dùng chung cho notebooks 04-08 và main.py: cùng dữ liệu, cùng phép chia, cùng seed."""
import pickle
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import CLEANED_MOVIES_FILE, CLEANED_RATINGS_FILE, CLEANED_USERS_FILE, PROCESSED_DIR, RESULTS_DIR, SEED, TEST_FRAC, VAL_FRAC
from src.data.preprocess import genres_multi_hot, load_cleaned
from src.evaluation.metrics import evaluate_model

CACHE_FILE = PROCESSED_DIR / "experiment.pkl"
CACHE_VERSION = 2          # tăng khi đổi logic tạo Experiment để bỏ cache cũ


@dataclass
class Experiment:
    train: pd.DataFrame          # cleaned ratings (user_id, movie_id, rating, timestamp, datetime) + title, genres
    test: pd.DataFrame
    movies: pd.DataFrame         # cleaned movies (movie_id, title, clean_title, release_year, genres)
    users: pd.DataFrame
    user2idx: dict
    item2idx: dict
    config: tuple = field(default=())   # exp_config() tại thời điểm đọc dữ liệu sạch

    @property
    def item_genres(self) -> np.ndarray:
        """Multi-hot thể loại (n_items x 18) theo đúng thứ tự item2idx."""
        idx2item = sorted(self.item2idx, key=self.item2idx.get)
        return genres_multi_hot(self.movies).loc[idx2item].to_numpy(dtype=np.float32)


def exp_config() -> tuple:
    """Cấu hình quyết định dữ liệu train/test; cache và mô hình đã lưu chỉ dùng lại khi khớp.

    Gồm phiên bản cache, seed, tỉ lệ test và thời điểm sửa các file dữ liệu sạch
    (chạy lại notebook 01 / `main.py prepare` -> tạo lại cache, huấn luyện lại mô hình).
    """
    files = (CLEANED_USERS_FILE, CLEANED_MOVIES_FILE, CLEANED_RATINGS_FILE)
    mtimes = tuple(p.stat().st_mtime_ns if p.exists() else None for p in files)
    return (CACHE_VERSION, SEED, TEST_FRAC, mtimes)


def split_per_user(df: pd.DataFrame, frac: float, seed: int = SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chia ngẫu nhiên trong TỪNG user: round(frac * n_u) rating của user u vào phần thứ hai.

    Mọi user giữ lại ít nhất 1 rating ở phần thứ nhất (để luôn có trong ma trận huấn luyện).
    """
    rng = np.random.default_rng(seed)
    shuffled = df.iloc[rng.permutation(len(df))]
    rank = shuffled.groupby("user_id").cumcount().to_numpy()
    size = shuffled.groupby("user_id")["user_id"].transform("size").to_numpy()
    n_hold = np.minimum(np.round(frac * size), size - 1)
    hold = rank < n_hold
    return shuffled[~hold].sort_index(), shuffled[hold].sort_index()


def load_experiment(use_cache: bool = True) -> Experiment:
    """Dữ liệu sạch (src.data.preprocess) -> chia train/test 80/20 theo từng user. Cache ở data/processed/experiment.pkl."""
    if use_cache and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "rb") as f:
                config, exp = pickle.load(f)
            if config == exp_config():
                return exp
        except Exception:
            pass                                      # cache cũ / hỏng -> tạo lại

    users, movies, ratings = load_cleaned()           # tự tạo cleaned_*.csv nếu chưa có
    config = exp_config()                             # lấy ngay sau khi đọc, gắn với đúng dữ liệu này
    ratings = ratings.merge(movies[["movie_id", "title", "genres"]], on="movie_id", how="left")
    # chỉ số hàng/cột của ma trận rating: mọi user và mọi phim có ít nhất 1 rating (6040 x 3706)
    user2idx = {u: k for k, u in enumerate(np.sort(ratings["user_id"].unique()))}
    item2idx = {m: k for k, m in enumerate(np.sort(ratings["movie_id"].unique()))}
    movies = movies[movies["movie_id"].isin(item2idx)].reset_index(drop=True)

    train, test = split_per_user(ratings, TEST_FRAC, SEED)
    exp = Experiment(train.reset_index(drop=True), test.reset_index(drop=True), movies, users, user2idx, item2idx,
                     config)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "wb") as f:
        pickle.dump((config, exp), f)
    return exp


def make_validation(exp: Experiment, frac: float = VAL_FRAC) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tách (sub-train, validation) từ train để dò siêu tham số mà không chạm vào test."""
    sub, val = split_per_user(exp.train, frac, SEED + 1)
    return sub.reset_index(drop=True), val.reset_index(drop=True)


SELECT_METRIC = "ValNDCG@10"   # tiêu chí chọn siêu tham số trên validation (notebooks 04-07)


def validate(model, val: pd.DataFrame, k: int = 10) -> dict:
    """Chỉ số của một mô hình đã fit trên sub-train, đo trên tập validation, dùng để dò siêu tham số.

    ValNDCG@k là tiêu chí chọn (cùng quy ước Top-N với tập test: loại phim đã chấm trong sub-train,
    phim liên quan = rating >= RELEVANT_RATING).
    """
    m = evaluate_model(model, val, k=k, k_beyond=k)
    return {f"ValNDCG@{k}": m[f"NDCG@{k}"]}


def run_model(model, exp: Experiment, k: int = 10, k_beyond: int = 20) -> dict:
    """Fit trên train, đánh giá trên test. Trả về một dòng kết quả (dict) cho bảng so sánh."""
    t0 = time.perf_counter()
    model.fit(exp.train, exp.user2idx, exp.item2idx, exp.movies)
    fit_time = time.perf_counter() - t0
    row = {"Model": model.name}
    row.update(evaluate_model(model, exp.test, k, k_beyond, exp.item_genres))
    row["FitTime_s"] = fit_time
    return row


def save_metrics(df: pd.DataFrame, name: str):
    """Lưu bảng kết quả vào outputs/metrics/<name>.csv (notebook 08 gộp các file này)."""
    out = RESULTS_DIR / "metrics"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.csv"
    df.to_csv(path, index=False)
    return path
