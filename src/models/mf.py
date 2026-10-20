"""Matrix Factorization: PureSVD (SVD cắt cụt trên phần dư), BiasedMF/FunkSVD (SGD), NMF (có mặt nạ), Implicit ALS.

Mọi mô hình huấn luyện bằng PyTorch, nhận tham số `device` ("auto" = GPU CUDA nếu có, ngược lại CPU).
"""
import numpy as np
import torch
from scipy import sparse

from src.config import SEED
from src.models.base import BaseRecommender
from src.models.baseline import fit_biases
from src.models.device import get_device, to_dense


class PureSVD(BaseRecommender):
    """SVD cắt cụt trên ma trận phần dư r - (mu + bu + bi); ô chưa chấm coi là 0.

    Top-f vector suy biến lấy từ phân rã trị riêng của ma trận Gram (cạnh nhỏ hơn) bằng PyTorch trên device:
    E ~ E V V^T với V = f vector riêng lớn nhất của E^T E (tương đương U_f S_f V_f^T của SVD).
    """

    def __init__(self, n_factors: int = 30, device: str = "auto"):
        self.n_factors = n_factors
        self.device = get_device(device)
        self.name = f"PureSVD(f={n_factors})"

    def _fit(self):
        mu, bu, bi = fit_biases(self.u, self.i, self.r, self.n_users, self.n_items)
        self.base = (mu + bu[:, None] + bi[None, :]).astype(np.float32)
        resid = self.r - self.base[self.u, self.i]
        E = sparse.csr_matrix((resid, (self.u, self.i)), shape=(self.n_users, self.n_items))
        E = to_dense(E, self.device)
        f = self.n_factors
        if not 0 < f < min(self.n_users, self.n_items):
            raise ValueError(f"n_factors phải trong khoảng 1..{min(self.n_users, self.n_items) - 1}")
        if self.n_items <= self.n_users:
            V = torch.linalg.eigh(E.T @ E).eigenvectors[:, -f:]       # (n_items, f)
            US, Vt = E @ V, V.T
        else:
            U = torch.linalg.eigh(E @ E.T).eigenvectors[:, -f:]       # (n_users, f)
            SVt = U.T @ E
            s = SVt.norm(dim=1).clamp_min(1e-12)                      # trị suy biến
            US, Vt = U * s, SVt / s[:, None]                          # Vt trực chuẩn như SVD
        self.US, self.Vt = US.cpu().numpy(), Vt.cpu().numpy()

    def _score_matrix(self):
        return self.base + self.US @ self.Vt


class BiasedMF(BaseRecommender):
    """Funk SVD / Biased MF:  r_ui ~ mu + b_u + b_i + p_u . q_i, huấn luyện bằng mini-batch Adam (PyTorch)."""

    def __init__(self, n_factors: int = 50, epochs: int = 20, lr: float = 0.01, reg: float = 0.05,
                 batch_size: int = 8192, seed: int = SEED, verbose: bool = False, device: str = "auto"):
        self.n_factors, self.epochs, self.lr, self.reg = n_factors, epochs, lr, reg
        self.batch_size, self.seed, self.verbose = batch_size, seed, verbose
        self.device = get_device(device)
        self.name = f"BiasedMF(f={n_factors})"
        self.history = []

    def _fit(self):
        torch.manual_seed(self.seed)
        dev = self.device
        nu, ni, f = self.n_users, self.n_items, self.n_factors
        P = torch.nn.Parameter(torch.randn(nu, f, device=dev) * 0.01)
        Q = torch.nn.Parameter(torch.randn(ni, f, device=dev) * 0.01)
        bu = torch.nn.Parameter(torch.zeros(nu, device=dev))
        bi = torch.nn.Parameter(torch.zeros(ni, device=dev))
        opt = torch.optim.Adam([P, Q, bu, bi], lr=self.lr)

        u, i = torch.from_numpy(self.u).to(dev), torch.from_numpy(self.i).to(dev)
        r = torch.from_numpy(self.r).to(dev)
        n, mu = len(r), self.global_mean
        g = torch.Generator(device=dev).manual_seed(self.seed)
        self.history = []
        for ep in range(self.epochs):
            perm = torch.randperm(n, generator=g, device=dev)
            total = torch.zeros((), device=dev)
            for s in range(0, n, self.batch_size):
                b = perm[s:s + self.batch_size]
                ub, ib, rb = u[b], i[b], r[b]
                pred = mu + bu[ub] + bi[ib] + (P[ub] * Q[ib]).sum(1)
                loss = ((pred - rb) ** 2).mean() + self.reg * (
                    (P[ub] ** 2).sum(1).mean() + (Q[ib] ** 2).sum(1).mean()
                    + 0.1 * (bu[ub] ** 2).mean() + 0.1 * (bi[ib] ** 2).mean())
                opt.zero_grad()
                loss.backward()
                opt.step()
                total += loss.detach() * len(b)
            self.history.append(total.item() / n)
            if self.verbose:
                print(f"epoch {ep + 1:2d}  loss {total.item() / n:.4f}")
        self.P, self.Q = P.detach().cpu().numpy(), Q.detach().cpu().numpy()
        self.bu, self.bi = bu.detach().cpu().numpy(), bi.detach().cpu().numpy()

    def _score_matrix(self):
        return self.global_mean + self.bu[:, None] + self.bi[None, :] + self.P @ self.Q.T


class NMF(BaseRecommender):
    """Non-negative MF với mặt nạ (chỉ tối thiểu hóa sai số trên ô đã chấm), cập nhật nhân (Lee & Seung), PyTorch."""

    def __init__(self, n_factors: int = 20, n_iter: int = 80, reg: float = 0.1, seed: int = SEED,
                 device: str = "auto"):
        self.n_factors, self.n_iter, self.reg, self.seed = n_factors, n_iter, reg, seed
        self.device = get_device(device)
        self.name = f"NMF(f={n_factors})"

    def _fit(self):
        rng = np.random.default_rng(self.seed)
        k = self.n_factors
        scale = np.sqrt(self.global_mean / k)
        W0 = (rng.random((self.n_users, k), dtype=np.float32) + 0.5) * scale
        H0 = (rng.random((k, self.n_items), dtype=np.float32) + 0.5) * scale
        dev = self.device
        R = to_dense(self.R, dev)
        M = (R > 0).float()
        W, H = to_dense(W0, dev), to_dense(H0, dev)
        eps = 1e-9
        for _ in range(self.n_iter):
            WH = W @ H
            W *= (R @ H.T) / ((M * WH) @ H.T + self.reg * W + eps)
            WH = W @ H
            H *= (W.T @ R) / (W.T @ (M * WH) + self.reg * H + eps)
        self.W, self.H = W.cpu().numpy(), H.cpu().numpy()

    def _score_matrix(self):
        return self.W @ self.H


class ImplicitALS(BaseRecommender):
    """ALS cho implicit feedback (Hu, Koren, Volinsky 2008): mọi lượt rating là "đã tương tác", độ tin cậy 1+alpha.

    Điểm trả về là mức ưa thích (không phải rating 1-5) nên chỉ dùng để xếp hạng Top-N.
    """
    predicts_rating = False

    def __init__(self, n_factors: int = 32, n_iter: int = 10, alpha: float = 20.0, reg: float = 0.1,
                 seed: int = SEED, device: str = "auto"):
        self.n_factors, self.n_iter, self.alpha, self.reg, self.seed = n_factors, n_iter, alpha, reg, seed
        self.device = get_device(device)
        self.name = f"ImplicitALS(f={n_factors})"

    def _solve(self, B: torch.Tensor, Y: torch.Tensor) -> torch.Tensor:
        """Giải đồng thời mọi hàng: (Y^T Y + reg I + alpha * Y_r^T Y_r) x_r = (1 + alpha) * sum Y_r.

        B: ma trận nhị phân (n_rows, n_cols) trên device; Y_r = các hàng của Y mà hàng r đã tương tác.
        Y_r^T Y_r của mọi hàng tính một lần bằng B @ (y_j y_j^T trải phẳng).
        """
        f = self.n_factors
        YtY = Y.T @ Y + self.reg * torch.eye(f, device=Y.device)
        outer = (Y[:, :, None] * Y[:, None, :]).reshape(len(Y), f * f)
        A = YtY + self.alpha * (B @ outer).view(-1, f, f)
        rhs = (1.0 + self.alpha) * (B @ Y)
        X = torch.linalg.solve(A, rhs)
        X[B.sum(1) == 0] = 0.0                       # hàng không có tương tác giữ vector 0
        return X

    def _fit(self):
        rng = np.random.default_rng(self.seed)
        dev = self.device
        X = to_dense(rng.standard_normal((self.n_users, self.n_factors)) * 0.01, dev)
        Y = to_dense(rng.standard_normal((self.n_items, self.n_factors)) * 0.01, dev)
        Bu = to_dense(self.B, dev)
        for _ in range(self.n_iter):
            X = self._solve(Bu, Y)
            Y = self._solve(Bu.T, X)
        self.X, self.Y = X.cpu().numpy(), Y.cpu().numpy()

    def _score_matrix(self):
        return self.X @ self.Y.T
