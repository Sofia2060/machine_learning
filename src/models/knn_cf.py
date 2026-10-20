"""Collaborative Filtering dựa trên láng giềng (memory-based): Item-based kNN.

Dự đoán theo dạng "kNN with baseline":
    r_ui = b_ui + sum_j sim(i,j) * (r_uj - b_uj) / sum_j |sim(i,j)|
với b = mu + b_u + b_i, lấy tổng trên k phim láng giềng giống nhất đã được user chấm.
Phép tính độ tương đồng và tổng có trọng số chạy bằng PyTorch (GPU CUDA nếu có, tham số `device`).
"""
import numpy as np
import torch
from scipy import sparse

from src.models.base import BaseRecommender
from src.models.baseline import fit_biases
from src.models.device import get_device, to_dense


def _similarity(X: sparse.csr_matrix, center: bool, shrink: float, k: int,
                device: torch.device) -> sparse.csr_matrix:
    """Độ tương đồng giữa các hàng của X (cosine, hoặc Pearson nếu center=True), giữ top-k mỗi hàng.

    - cosine : trên rating thô.
    - pearson: trừ trung bình của chính hàng (chỉ tính trên phần tử đã chấm) rồi mới cosine.
    - shrink : nhân thêm n/(n+shrink) với n = số phần tử chung, để phạt cặp trùng ít.
    Tính bằng phép nhân ma trận dày trên device vì ma trận rating đủ nhỏ, nhanh hơn nhân ma trận thưa.
    """
    Xd = to_dense(X, device)
    Bd = (Xd > 0).float()
    if center:
        mean = Xd.sum(1) / Bd.sum(1).clamp_min(1)
        Xd = (Xd - mean[:, None]) * Bd                   # chỉ trừ ở ô đã chấm
    Xd = Xd / Xd.norm(dim=1).clamp_min(1e-9)[:, None]
    S = Xd @ Xd.T
    if shrink > 0:
        common = Bd @ Bd.T
        S *= common / (common + shrink)
    S.fill_diagonal_(0.0)
    S.clamp_(min=0.0)  # chỉ giữ láng giềng tương quan dương
    if k < S.shape[1]:
        top = S.topk(k, dim=1).indices
        S = torch.zeros_like(S).scatter_(1, top, S.gather(1, top))
    return sparse.csr_matrix(S.cpu().numpy())


class ItemKNN(BaseRecommender):
    def __init__(self, k: int = 40, similarity: str = "cosine", shrink: float = 10.0, device: str = "auto"):
        assert similarity in ("cosine", "pearson")
        self.k, self.similarity, self.shrink = k, similarity, shrink
        self.device = get_device(device)
        self.name = f"ItemKNN(k={k},{similarity})"

    def _fit(self):
        mu, bu, bi = fit_biases(self.u, self.i, self.r, self.n_users, self.n_items)
        self.base = (mu + bu[:, None] + bi[None, :]).astype(np.float32)
        resid = self.r - self.base[self.u, self.i]  # phần dư so với baseline, chỉ ở ô đã chấm
        self.E = sparse.csr_matrix((resid, (self.u, self.i)), shape=(self.n_users, self.n_items))
        self.S = _similarity(self.R.T.tocsr(), self.similarity == "pearson", self.shrink, self.k, self.device)

    def _score_matrix(self):
        S, E, B = (to_dense(m, self.device) for m in (self.S, self.E, self.B))
        num, den = E @ S.T, B @ S.abs().T
        adj = torch.where(den > 0, num / den, torch.zeros_like(num))
        return self.base + adj.cpu().numpy()
