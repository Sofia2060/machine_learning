"""Gợi ý phim cho phần mềm (PyQt6 + MySQL): nạp NeuMF đã xuất bằng `python main.py export` và tính điểm bằng numpy.

Module này chỉ cần numpy (không import torch hay src.models), để phần mềm đóng gói gọn nhẹ.

    from src.inference import NeuMFRecommender
    rec = NeuMFRecommender("models/neumf.npz")               # nạp một lần khi mở phần mềm
    seen = [1193, 661, 914]                                  # movie_id user đã chấm, lấy từ MySQL
    rec.recommend(user_id=1, k=10, seen=seen)                # -> [(movie_id, điểm), ...] giảm dần

User không có trong mô hình (đăng ký sau lần xuất gần nhất) được gợi ý theo độ phổ biến (`is_personalized` = False).
Phim không có trong mô hình (thêm vào CSDL sau lần xuất) không được gợi ý; xuất lại mô hình để cập nhật.
"""
import json
from pathlib import Path

import numpy as np

FORMAT_VERSION = 1


class NeuMFRecommender:
    def __init__(self, path):
        path = Path(path)
        self.meta = json.loads(path.with_name(path.stem + "_meta.json").read_text(encoding="utf-8"))
        if self.meta.get("format_version") != FORMAT_VERSION:
            raise ValueError(f"{path.name}: định dạng {self.meta.get('format_version')} không được hỗ trợ "
                             f"(cần {FORMAT_VERSION}); hãy xuất lại bằng `python main.py export`")
        with np.load(path) as z:
            self.gu, self.gi, self.mu, self.mi = (z[k] for k in ("gu", "gi", "mu", "mi"))
            self.mlp = [(z[f"mlp_w{k}"], z[f"mlp_b{k}"]) for k in range(self.meta["n_mlp"])]
            self.out_w, self.out_b = z["out_w"], float(z["out_b"][0])
            self.movie_ids, self.popularity = z["movie_ids"], z["popularity"]
            user_ids = z["user_ids"]
        self.user_index = {int(u): k for k, u in enumerate(user_ids)}
        self.movie_index = {int(m): k for k, m in enumerate(self.movie_ids)}
        # Lớp MLP đầu tiên nhận [mu(u) ; mi(i)]: phần của phim không phụ thuộc user nên tính sẵn một lần.
        f = self.mu.shape[1]
        w0, b0 = self.mlp[0]
        self._w0_user = w0[:, :f].T
        self._mlp0_items = self.mi @ w0[:, f:].T + b0

    @property
    def name(self) -> str:
        return self.meta["model"]

    def is_personalized(self, user_id: int) -> bool:
        """True nếu user có trong mô hình (gợi ý cá nhân hóa), False nếu sẽ dùng gợi ý theo độ phổ biến."""
        return int(user_id) in self.user_index

    def scores(self, user_id: int) -> np.ndarray:
        """Điểm NeuMF (logit, chỉ dùng để xếp hạng) của mọi phim cho user, theo thứ tự self.movie_ids."""
        u = self.user_index[int(user_id)]
        gmf = self.gu[u] * self.gi                                   # (n_items, f)
        h = np.maximum(self._mlp0_items + self.mu[u] @ self._w0_user, 0.0)
        for w, b in self.mlp[1:]:
            h = np.maximum(h @ w.T + b, 0.0)
        return np.concatenate([gmf, h], axis=1) @ self.out_w + self.out_b

    def score(self, user_id: int, movie_id: int) -> float | None:
        """Điểm của một phim; None nếu user hoặc phim không có trong mô hình."""
        if not self.is_personalized(user_id) or int(movie_id) not in self.movie_index:
            return None
        return float(self.scores(user_id)[self.movie_index[int(movie_id)]])

    def recommend(self, user_id: int, k: int = 10, seen=()) -> list[tuple[int, float]]:
        """Top-k (movie_id, điểm) giảm dần, bỏ các phim trong `seen`.

        Điểm là logit NeuMF, hoặc số lượt rating nếu user không có trong mô hình (gợi ý theo độ phổ biến).
        """
        if self.is_personalized(user_id):
            s = self.scores(user_id).astype(np.float64)
        else:
            s = self.popularity.astype(np.float64)
        drop = [self.movie_index[int(m)] for m in seen if m is not None and int(m) in self.movie_index]
        s[drop] = -np.inf
        order = np.argsort(-s, kind="stable")[:max(int(k), 0)]
        return [(int(self.movie_ids[j]), float(s[j])) for j in order if np.isfinite(s[j])]
