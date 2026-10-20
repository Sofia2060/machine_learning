"""Mô hình cơ sở không cá nhân hóa (Popularity) và hàm ước lượng bias (mu + bu + bi) dùng chung."""
import numpy as np

from src.models.base import BaseRecommender


def fit_biases(u, i, r, n_users, n_items, reg_i: float = 25.0, reg_u: float = 10.0, n_iter: int = 10):
    """Ước lượng mu, bu, bi bằng bình phương tối thiểu có điều chuẩn (luân phiên bi <-> bu)."""
    mu = float(r.mean())
    bu = np.zeros(n_users, dtype=np.float64)
    bi = np.zeros(n_items, dtype=np.float64)
    for _ in range(n_iter):
        bi = np.bincount(i, weights=r - mu - bu[u], minlength=n_items) / (
            reg_i + np.bincount(i, minlength=n_items))
        bu = np.bincount(u, weights=r - mu - bi[i], minlength=n_users) / (
            reg_u + np.bincount(u, minlength=n_users))
    return mu, bu.astype(np.float32), bi.astype(np.float32)


class Popularity(BaseRecommender):
    """Không cá nhân hóa: mọi user nhận cùng một bảng xếp hạng phim theo số lượt rating trong train.

    Điểm là số lượt rating (chỉ dùng để xếp hạng, không phải rating).
    """
    name = "Popularity(count)"
    predicts_rating = False

    def _fit(self):
        self.item_score = np.bincount(self.i, minlength=self.n_items).astype(np.float64)

    def _score_matrix(self):
        return np.repeat(self.item_score[None, :].astype(np.float32), self.n_users, axis=0)
