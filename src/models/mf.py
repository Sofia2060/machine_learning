"""Matrix Factorization: BiasedMF/FunkSVD (mini-batch Adam) và Implicit ALS.

Mọi mô hình huấn luyện bằng PyTorch, nhận tham số `device` ("auto" = GPU CUDA nếu có, ngược lại CPU).
"""
import numpy as np
import torch

from src.config import SEED
from src.models.base import BaseRecommender
from src.models.device import get_device, to_dense


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
