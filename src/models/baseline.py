"""Mô hình cơ sở: trung bình toàn cục / user / phim, bias (mu + bu + bi), popularity."""
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


class GlobalMean(BaseRecommender):
    name = "GlobalMean"

    def _fit(self):
        pass

    def _score_matrix(self):
        return np.full((self.n_users, self.n_items), self.global_mean, dtype=np.float32)


class UserMean(BaseRecommender):
    name = "UserMean"

    def _fit(self):
        cnt = np.bincount(self.u, minlength=self.n_users)
        s = np.bincount(self.u, weights=self.r, minlength=self.n_users)
        self.um = np.where(cnt > 0, s / np.maximum(cnt, 1), self.global_mean).astype(np.float32)

    def _score_matrix(self):
        return np.repeat(self.um[:, None], self.n_items, axis=1)


class ItemMean(BaseRecommender):
    name = "ItemMean"

    def _fit(self):
        cnt = np.bincount(self.i, minlength=self.n_items)
        s = np.bincount(self.i, weights=self.r, minlength=self.n_items)
        self.im = np.where(cnt > 0, s / np.maximum(cnt, 1), self.global_mean).astype(np.float32)

    def _score_matrix(self):
        return np.repeat(self.im[None, :], self.n_users, axis=0)


class BiasBaseline(BaseRecommender):
    """r_ui ~ mu + b_u + b_i (baseline predictor, có điều chuẩn L2)."""
    name = "BiasBaseline"

    def __init__(self, reg_i: float = 25.0, reg_u: float = 10.0):
        self.reg_i, self.reg_u = reg_i, reg_u

    def _fit(self):
        self.mu, self.bu, self.bi = fit_biases(
            self.u, self.i, self.r, self.n_users, self.n_items, self.reg_i, self.reg_u)

    def _score_matrix(self):
        return self.mu + self.bu[:, None] + self.bi[None, :]


class Popularity(BaseRecommender):
    """Không cá nhân hóa: mọi user nhận cùng một bảng xếp hạng.

    by="weighted": điểm Bayesian kiểu IMDb  (v/(v+m))*R + (m/(v+m))*C, ở thang 1-5.
    by="count"   : số lượt rating (chỉ dùng để xếp hạng, không phải rating).
    """
    def __init__(self, by: str = "weighted", m: float = 100.0):
        assert by in ("weighted", "count")
        self.by, self.m = by, m
        self.name = f"Popularity({by})"
        self.predicts_rating = by == "weighted"

    def _fit(self):
        v = np.bincount(self.i, minlength=self.n_items).astype(np.float64)
        s = np.bincount(self.i, weights=self.r, minlength=self.n_items)
        mean = np.where(v > 0, s / np.maximum(v, 1), self.global_mean)
        if self.by == "count":
            self.item_score = v
        else:
            self.item_score = (v / (v + self.m)) * mean + (self.m / (v + self.m)) * self.global_mean

    def _score_matrix(self):
        return np.repeat(self.item_score[None, :].astype(np.float32), self.n_users, axis=0)
