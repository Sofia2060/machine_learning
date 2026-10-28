"""Gợi ý phim cho phần mềm (PyQt6 + MySQL): nạp NeuMF đã xuất bằng `python main.py export` và tính điểm bằng numpy.

Module này chỉ cần numpy (không import torch hay src.models), để phần mềm đóng gói gọn nhẹ.

    from src.inference import NeuMFRecommender
    rec = NeuMFRecommender("models/main_model/neumf.npz")    # nạp một lần khi mở phần mềm
    seen = [1193, 661, 914]                                  # movie_id user đã chấm, lấy từ MySQL
    rec.recommend(user_id=1, k=10, seen=seen)                # -> [(movie_id, điểm), ...] giảm dần

User đăng ký sau lần xuất gần nhất chưa có vector trong mô hình (`is_personalized` = False):
    rec.recommend(user_id, k=10, seen=seen)                  # -> gợi ý theo độ phổ biến
    ratings = {1193: 5, 661: 3, 914: 4}                      # {movie_id: số sao} của user, lấy từ MySQL
    rec.recommend_from_ratings(ratings, k=10)                # -> gợi ý cá nhân hóa nhờ fold-in

Fold-in: giữ nguyên mọi trọng số đã học (phim + MLP), chỉ học vector của user từ các rating của họ.
Phim không có trong mô hình (thêm vào CSDL sau lần xuất) không được gợi ý; xuất lại mô hình để cập nhật.
"""
import json
from pathlib import Path

import numpy as np

FORMAT_VERSION = 1
MIN_RATING = 4.0        # như khi huấn luyện NeuMF: rating >= 4 là phản hồi dương


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
        # Vector khởi tạo cho fold-in: "user trung bình" của mô hình.
        self._g0, self._m0 = self.gu.mean(axis=0), self.mu.mean(axis=0)

    @property
    def name(self) -> str:
        return self.meta["model"]

    def is_personalized(self, user_id: int) -> bool:
        """True nếu user có trong mô hình (gợi ý cá nhân hóa), False nếu sẽ dùng gợi ý theo độ phổ biến."""
        return int(user_id) in self.user_index

    def _forward(self, g: np.ndarray, m: np.ndarray):
        """Logit của mọi phim cho vector user (g: nhánh GMF, m: nhánh MLP) và tiền kích hoạt các lớp MLP."""
        pre = [self._mlp0_items + m @ self._w0_user]
        h = np.maximum(pre[0], 0.0)
        for w, b in self.mlp[1:]:
            pre.append(h @ w.T + b)
            h = np.maximum(pre[-1], 0.0)
        f = len(g)
        z = (self.gi @ (g * self.out_w[:f])) + h @ self.out_w[f:] + self.out_b
        return z, pre

    def scores(self, user_id: int) -> np.ndarray:
        """Điểm NeuMF (logit, chỉ dùng để xếp hạng) của mọi phim cho user, theo thứ tự self.movie_ids."""
        u = self.user_index[int(user_id)]
        return self._forward(self.gu[u], self.mu[u])[0]

    @staticmethod
    def _rating_dict(ratings) -> dict:
        """{movie_id: số sao} từ dict hoặc danh sách cặp (movie_id, số sao); bỏ movie_id rỗng (None/NaN).
        Phim xuất hiện nhiều lần thì lấy rating cuối cùng."""
        pairs = ratings.items() if isinstance(ratings, dict) else ratings
        return {int(mv): r for mv, r in pairs if mv is not None and mv == mv}

    def fold_in(self, ratings, steps: int = 50, lr: float = 0.1, reg: float = 0.01, n_neg: int = 4):
        """Học vector (g, m) cho một user từ `ratings` ({movie_id: số sao} hoặc danh sách cặp (movie_id, số sao)),
        giữ nguyên mọi trọng số khác của mô hình. Trả về None nếu user chưa có phim nào >= MIN_RATING trong mô hình.

        Hàm mất mát giống lúc huấn luyện (BCE, mỗi phim dương kèm n_neg phim âm ngẫu nhiên), nhưng lấy kỳ vọng
        thay cho lấy mẫu: mọi phim đều là phim âm với trọng số n_neg * |dương| / n_items, nên kết quả tất định.
        `reg` kéo vector về "user trung bình" (khởi tạo) để user có ít rating không bị khớp quá mức.
        Mặc định steps/lr/reg được chọn theo NDCG@10 trên các user bị bỏ hẳn khỏi lúc huấn luyện (giả lập user mới).
        """
        pos = sorted(self.movie_index[mv] for mv, r in self._rating_dict(ratings).items()
                     if r is not None and float(r) >= MIN_RATING and mv in self.movie_index)
        if not pos:
            return None
        n_items, f = len(self.movie_ids), len(self._g0)
        y = np.zeros(n_items, dtype=np.float32)
        y[pos] = 1.0
        w_neg = n_neg * len(pos) / n_items
        total = len(pos) * (1 + n_neg)
        x0 = np.concatenate([self._g0, self._m0])                  # float32 như trọng số: nhanh gấp ~2 lần float64
        x, mom, vel = x0.copy(), np.zeros_like(x0), np.zeros_like(x0)
        b1, b2, eps = 0.9, 0.999, 1e-8
        for t in range(1, steps + 1):
            g, m = x[:f], x[f:]
            z, pre = self._forward(g, m)
            p = 0.5 * (1.0 + np.tanh(0.5 * z))                       # sigmoid, không tràn số
            dz = (y * (p - 1.0) + w_neg * p) / total               # đạo hàm BCE có trọng số theo logit
            grad_g = (dz @ self.gi) * self.out_w[:f]
            d = np.outer(dz, self.out_w[f:])                       # lan truyền ngược qua các lớp MLP
            for k in range(len(self.mlp) - 1, -1, -1):
                d = d * (pre[k] > 0)
                if k > 0:
                    d = d @ self.mlp[k][0]
            grad_m = d.sum(axis=0) @ self._w0_user.T
            grad = np.concatenate([grad_g, grad_m]) + 2.0 * reg * (x - x0)
            mom = b1 * mom + (1 - b1) * grad                        # Adam
            vel = b2 * vel + (1 - b2) * grad * grad
            x -= lr * (mom / (1 - b1 ** t)) / (np.sqrt(vel / (1 - b2 ** t)) + eps)
        return x[:f].copy(), x[f:].copy()

    def recommend_from_ratings(self, ratings, k: int = 10) -> list[tuple[int, float]]:
        """Top-k cho user từ chính các rating của họ (fold-in), bỏ các phim đã chấm.

        Dùng cho user mới (không có trong mô hình). Cũng dùng được cho user cũ để phản ánh ngay rating mới, khi đó
        truyền TOÀN BỘ rating của user (vector được học lại từ "user trung bình", không dùng vector đã huấn luyện).
        Nếu user chưa có phim nào >= MIN_RATING thì gợi ý theo độ phổ biến.
        Mất khoảng 0.3 s (fold-in) nên trong PyQt6 hãy gọi trong QThread.
        """
        rated = self._rating_dict(ratings)
        vec = self.fold_in(rated)
        s = None if vec is None else self._forward(*vec)[0]
        return self._top_k(s, k, rated)

    def score(self, user_id: int, movie_id: int) -> float | None:
        """Điểm của một phim; None nếu user hoặc phim không có trong mô hình."""
        if not self.is_personalized(user_id) or int(movie_id) not in self.movie_index:
            return None
        return float(self.scores(user_id)[self.movie_index[int(movie_id)]])

    def recommend(self, user_id: int, k: int = 10, seen=()) -> list[tuple[int, float]]:
        """Top-k (movie_id, điểm) giảm dần, bỏ các phim trong `seen`.

        Điểm là logit NeuMF, hoặc số lượt rating nếu user không có trong mô hình (gợi ý theo độ phổ biến).
        """
        return self._top_k(self.scores(user_id) if self.is_personalized(user_id) else None, k, seen)

    def _top_k(self, s, k, seen):
        """Top-k theo điểm s (None = theo độ phổ biến), bỏ các phim trong seen."""
        s = (self.popularity if s is None else s).astype(np.float64)
        drop = [self.movie_index[int(m)] for m in seen if m is not None and m == m and int(m) in self.movie_index]
        s[drop] = -np.inf
        order = np.argsort(-s, kind="stable")[:max(int(k), 0)]
        return [(int(self.movie_ids[j]), float(s[j])) for j in order if np.isfinite(s[j])]
