"""Bộ máy gợi ý dùng cho ứng dụng: danh mục mô hình, huấn luyện / lưu / nạp lại, gợi ý Top-N và dự đoán rating."""
import pickle

import pandas as pd

from src.config import MODELS_DIR
from src.experiment import Experiment
from src.models.base import BaseRecommender
from src.models.baseline import Popularity
from src.models.content_based import ContentBased
from src.models.knn_cf import ItemKNN
from src.models.mf import BiasedMF, ImplicitALS
from src.models.neural import BPRMF, NeuMF

# Siêu tham số lấy theo kết quả dò trên validation trong notebooks 04-07 (tiêu chí chọn: NDCG@10, src.experiment.SELECT_METRIC).
MODELS = {
    "popularity": Popularity,
    "content": ContentBased,
    "item_knn": lambda: ItemKNN(k=5, similarity="pearson"),
    "biased_mf": lambda: BiasedMF(n_factors=200, epochs=15),
    "implicit_als": lambda: ImplicitALS(n_factors=32, n_iter=10, alpha=20),
    "neumf": lambda: NeuMF(n_factors=128, epochs=6),
    "bpr_mf": lambda: BPRMF(n_factors=32, epochs=20),
}

# Nhóm mô hình (= tên file outputs/metrics/<nhóm>.csv mà notebook 08 đọc) -> (nhãn Family, danh sách mô hình)
FAMILIES = {
    "baseline": ("Baseline", ["popularity"]),
    "content": ("Content-based", ["content"]),
    "knn": ("Collaborative (kNN)", ["item_knn"]),
    "mf": ("Matrix Factorization", ["biased_mf", "implicit_als"]),
    "deep": ("Deep learning", ["neumf", "bpr_mf"]),
}

DEFAULT_MODEL = "neumf"


def create_model(key: str):
    if key not in MODELS:
        raise KeyError(f"Không có mô hình '{key}'. Chọn một trong: {', '.join(MODELS)}")
    return MODELS[key]()


def model_path(key: str):
    return MODELS_DIR / f"{key}.pkl"


class FrozenModel(BaseRecommender):
    """Bản "đóng băng" của một mô hình đã fit: chỉ giữ ma trận điểm và chỉ mục, đủ cho predict/recommend.

    Lưu bản này thay vì cả mô hình để file .pkl nhỏ và nạp nhanh (mô hình gốc còn giữ nhiều ma trận
    trung gian lớn).
    """

    def __init__(self, model: BaseRecommender, config: tuple):
        self.name, self.predicts_rating, self.config = model.name, model.predicts_rating, config
        for attr in ("user2idx", "item2idx", "idx2item", "idx2user", "n_users", "n_items", "R", "movies"):
            setattr(self, attr, getattr(model, attr))
        self._scores = model.score_matrix()


def model_signature(model: BaseRecommender, exp: Experiment) -> tuple:
    """Định danh một lần huấn luyện: dữ liệu (exp.config) + mô hình và siêu tham số chính."""
    weights = tuple(getattr(model, "weights", ()))
    parts = tuple(m.name for m in getattr(model, "models", ()))
    return exp.config, model.name, parts, weights


def get_model(key: str, exp: Experiment, retrain: bool = False, verbose: bool = True) -> FrozenModel:
    """Nạp models/<key>.pkl; huấn luyện lại rồi lưu nếu chưa có, file hỏng, retrain=True, hoặc file được huấn luyện
    trên dữ liệu / siêu tham số khác với hiện tại."""
    path = model_path(key)
    if path.exists() and not retrain:
        try:
            with open(path, "rb") as f:
                model = pickle.load(f)
            if isinstance(model, FrozenModel) and model.config == model_signature(create_model(key), exp):
                return model
            print(f"{path.name} được huấn luyện với dữ liệu hoặc siêu tham số khác; huấn luyện lại.")
        except Exception as e:                       # file hỏng / khác phiên bản thư viện -> train lại
            print(f"Không nạp được {path.name} ({e}); huấn luyện lại.")
    model = create_model(key)
    if verbose:
        print(f"Đang huấn luyện {model.name} ...")
    model.fit(exp.train, exp.user2idx, exp.item2idx, exp.movies)
    frozen = FrozenModel(model, model_signature(model, exp))
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(frozen, f, protocol=pickle.HIGHEST_PROTOCOL)
    return frozen


def recommend(model, user_id: int, k: int = 10) -> pd.DataFrame:
    """Top-k phim user chưa chấm trong train."""
    if user_id not in model.user2idx:
        raise KeyError(f"UserID {user_id} không có trong dữ liệu (hợp lệ: 1..{max(model.user2idx)})")
    return model.recommend(user_id, k=k)


def predict_rating(model, user_id: int, movie_id: int) -> float:
    if user_id not in model.user2idx:
        raise KeyError(f"UserID {user_id} không có trong dữ liệu")
    if movie_id not in model.item2idx:
        raise KeyError(f"MovieID {movie_id} không có trong dữ liệu")
    return float(model.predict(pd.DataFrame({"user_id": [user_id], "movie_id": [movie_id]}))[0])


def user_history(exp: Experiment, user_id: int, n: int = 10) -> pd.DataFrame:
    """Các phim user chấm cao nhất trong train (để đối chiếu với gợi ý)."""
    h = exp.train[exp.train["user_id"] == user_id]
    return h.sort_values(["rating", "timestamp"], ascending=[False, False]).head(n)[
        ["movie_id", "title", "genres", "rating"]].reset_index(drop=True)


def search_movies(exp: Experiment, query: str, n: int = 10) -> pd.DataFrame:
    hit = exp.movies[exp.movies["title"].str.contains(query, case=False, regex=False)]
    return hit.head(n).reset_index(drop=True)

