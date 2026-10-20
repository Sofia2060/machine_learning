"""Lớp cha chung cho mọi mô hình khuyến nghị.

Giao diện thống nhất: fit() / predict() / recommend() / score_matrix().
Mọi mô hình trả về điểm cho TOÀN BỘ cặp (user, phim) dưới dạng ma trận dày
(n_users x n_items). Với MovieLens 1M ma trận này chỉ ~90 MB nên cách làm này
đơn giản và nhanh; chỉ số hàng/cột lấy từ user2idx / item2idx.
"""
import numpy as np
import pandas as pd
from scipy import sparse

RATING_MIN, RATING_MAX = 1.0, 5.0


class BaseRecommender:
    name = "base"
    # False nếu điểm trả về không ở thang 1-5 (popularity đếm, BPR, ALS...): predict() không kẹp về [1, 5].
    predicts_rating = True

    # fit
    def fit(self, train: pd.DataFrame, user2idx: dict, item2idx: dict, movies: pd.DataFrame | None = None):
        self.user2idx, self.item2idx = user2idx, item2idx
        self.n_users, self.n_items = len(user2idx), len(item2idx)
        self.idx2item = np.array(sorted(item2idx, key=item2idx.get))
        self.idx2user = np.array(sorted(user2idx, key=user2idx.get))
        self.movies = movies

        self.u = train["user_id"].map(user2idx).to_numpy().copy()
        self.i = train["movie_id"].map(item2idx).to_numpy().copy()
        self.r = train["rating"].to_numpy(dtype=np.float32).copy()
        self.R = sparse.csr_matrix((self.r, (self.u, self.i)), shape=(self.n_users, self.n_items))
        self.B = (self.R > 0).astype(np.float32)  # ma trận nhị phân "đã chấm"
        self.global_mean = float(self.r.mean())

        self._fit()
        self._scores = None
        return self

    def _fit(self) -> None:
        raise NotImplementedError

    def _score_matrix(self) -> np.ndarray:
        raise NotImplementedError

    # scores
    def score_matrix(self) -> np.ndarray:
        """Ma trận (n_users, n_items) điểm dự đoán, có cache."""
        if self._scores is None:
            self._scores = np.asarray(self._score_matrix(), dtype=np.float32)
        return self._scores

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Dự đoán rating cho từng dòng (user_id, movie_id) của df, kẹp về [1, 5]."""
        s = self.score_matrix()
        u = df["user_id"].map(self.user2idx).to_numpy()
        i = df["movie_id"].map(self.item2idx).to_numpy()
        pred = s[u, i]
        return np.clip(pred, RATING_MIN, RATING_MAX) if self.predicts_rating else pred

    def recommend(self, user_id: int, k: int = 10, exclude_seen: bool = True) -> pd.DataFrame:
        """Top-k phim cho một user: cột movie_id, score (và title, genres nếu có bảng phim)."""
        ui = self.user2idx[user_id]
        scores = self.score_matrix()[ui].copy()
        if exclude_seen:
            scores[self.R[ui].indices] = -np.inf
        top = np.argpartition(-scores, k)[:k]
        top = top[np.argsort(-scores[top])]
        out = pd.DataFrame({"movie_id": self.idx2item[top], "score": scores[top]})
        if self.movies is not None:
            out = out.merge(self.movies[["movie_id", "title", "genres"]], on="movie_id", how="left")
        return out

    def __repr__(self) -> str:
        return self.name
