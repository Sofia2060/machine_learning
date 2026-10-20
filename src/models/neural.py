"""Mô hình xếp hạng Top-N học từ phản hồi implicit (PyTorch): NeuMF/NCF và BPR-MF.

Tất cả nhận tham số `device` ("auto" = dùng GPU CUDA nếu có, ngược lại CPU).
"""
import numpy as np
import torch
from torch import nn

from src.config import SEED
from src.models.base import BaseRecommender
from src.models.device import get_device


def _positives(model: BaseRecommender, min_rating: float):
    keep = model.r >= min_rating
    dev = model.device
    return torch.from_numpy(model.u[keep]).to(dev), torch.from_numpy(model.i[keep]).to(dev)


class BPRMF(BaseRecommender):
    """Bayesian Personalized Ranking + MF (Rendle 2009): tối ưu trực tiếp thứ hạng, positive = rating >= min_rating."""
    predicts_rating = False

    def __init__(self, n_factors: int = 64, epochs: int = 20, lr: float = 0.005, reg: float = 1e-4,
                 batch_size: int = 8192, min_rating: float = 4.0, seed: int = SEED, verbose: bool = False,
                 device: str = "auto"):
        self.n_factors, self.epochs, self.lr, self.reg = n_factors, epochs, lr, reg
        self.batch_size, self.min_rating, self.seed, self.verbose = batch_size, min_rating, seed, verbose
        self.device = get_device(device)
        self.name = f"BPR-MF(f={n_factors})"
        self.history = []

    def _fit(self):
        torch.manual_seed(self.seed)
        dev = self.device
        P = nn.Embedding(self.n_users, self.n_factors).to(dev)
        Q = nn.Embedding(self.n_items, self.n_factors).to(dev)
        bi = nn.Embedding(self.n_items, 1).to(dev)
        for e in (P, Q):
            nn.init.normal_(e.weight, std=0.05)
        nn.init.zeros_(bi.weight)
        opt = torch.optim.Adam(list(P.parameters()) + list(Q.parameters()) + list(bi.parameters()), lr=self.lr)
        u, i = _positives(self, self.min_rating)
        n = len(u)
        self.history = []
        for ep in range(self.epochs):
            perm = torch.randperm(n, device=dev)
            neg = torch.randint(0, self.n_items, (n,), device=dev)
            total = torch.zeros((), device=dev)
            for s in range(0, n, self.batch_size):
                b = perm[s:s + self.batch_size]
                ub, ib, jb = u[b], i[b], neg[b]
                pu, qi, qj = P(ub), Q(ib), Q(jb)
                x = (pu * (qi - qj)).sum(1) + (bi(ib) - bi(jb)).squeeze(1)
                loss = -nn.functional.logsigmoid(x).mean() + self.reg * (
                    pu.pow(2).sum(1).mean() + qi.pow(2).sum(1).mean() + qj.pow(2).sum(1).mean())
                opt.zero_grad()
                loss.backward()
                opt.step()
                total += loss.detach() * len(b)
            self.history.append(total.item() / n)
            if self.verbose:
                print(f"epoch {ep + 1:2d}  BPR loss {total.item() / n:.4f}")
        self.P = P.weight.detach().cpu().numpy()
        self.Q = Q.weight.detach().cpu().numpy()
        self.bi = bi.weight.detach().cpu().numpy().ravel()

    def _score_matrix(self):
        return self.P @ self.Q.T + self.bi[None, :]


class _NeuMFNet(nn.Module):
    def __init__(self, n_users, n_items, f, mlp_layers):
        super().__init__()
        self.gu, self.gi = nn.Embedding(n_users, f), nn.Embedding(n_items, f)
        self.mu, self.mi = nn.Embedding(n_users, f), nn.Embedding(n_items, f)
        layers, d = [], 2 * f
        for h in mlp_layers:
            layers += [nn.Linear(d, h), nn.ReLU()]
            d = h
        self.mlp = nn.Sequential(*layers)
        self.out = nn.Linear(f + d, 1)
        for e in (self.gu, self.gi, self.mu, self.mi):
            nn.init.normal_(e.weight, std=0.05)

    def forward(self, u, i):
        gmf = self.gu(u) * self.gi(i)
        mlp = self.mlp(torch.cat([self.mu(u), self.mi(i)], dim=-1))
        return self.out(torch.cat([gmf, mlp], dim=-1)).squeeze(-1)


class NeuMF(BaseRecommender):
    """Neural Collaborative Filtering (He et al. 2017): GMF + MLP, huấn luyện implicit với BCE và lấy mẫu âm."""
    predicts_rating = False

    def __init__(self, n_factors: int = 32, mlp_layers=(64, 32, 16), epochs: int = 6, lr: float = 1e-3,
                 n_neg: int = 4, batch_size: int = 8192, min_rating: float = 4.0, seed: int = SEED,
                 verbose: bool = False, device: str = "auto"):
        self.n_factors, self.mlp_layers, self.epochs, self.lr = n_factors, tuple(mlp_layers), epochs, lr
        self.n_neg, self.batch_size, self.min_rating, self.seed = n_neg, batch_size, min_rating, seed
        self.verbose = verbose
        self.device = get_device(device)
        self.name = f"NeuMF(f={n_factors})"
        self.history = []

    def _fit(self):
        torch.manual_seed(self.seed)
        dev = self.device
        net = _NeuMFNet(self.n_users, self.n_items, self.n_factors, self.mlp_layers).to(dev)
        opt = torch.optim.Adam(net.parameters(), lr=self.lr)
        bce = nn.BCEWithLogitsLoss()
        u, i = _positives(self, self.min_rating)
        n_pos, k = len(u), self.n_neg
        self.history = []
        for ep in range(self.epochs):
            uu = torch.cat([u, u.repeat_interleave(k)])
            ii = torch.cat([i, torch.randint(0, self.n_items, (n_pos * k,), device=dev)])
            yy = torch.cat([torch.ones(n_pos, device=dev), torch.zeros(n_pos * k, device=dev)])
            perm = torch.randperm(len(yy), device=dev)
            total = torch.zeros((), device=dev)
            for s in range(0, len(yy), self.batch_size):
                b = perm[s:s + self.batch_size]
                loss = bce(net(uu[b], ii[b]), yy[b])
                opt.zero_grad()
                loss.backward()
                opt.step()
                total += loss.detach() * len(b)
            self.history.append(total.item() / len(yy))
            if self.verbose:
                print(f"epoch {ep + 1}  BCE {total.item() / len(yy):.4f}")
        self.net = net.eval()

    def _score_matrix(self):
        out = np.empty((self.n_users, self.n_items), dtype=np.float32)
        dev = self.device
        items = torch.arange(self.n_items, device=dev)
        chunk = 300
        with torch.no_grad():
            for s in range(0, self.n_users, chunk):
                us = torch.arange(s, min(s + chunk, self.n_users), device=dev)
                uu = us.repeat_interleave(self.n_items)
                ii = items.repeat(len(us))
                out[s:s + len(us)] = self.net(uu, ii).view(len(us), self.n_items).cpu().numpy()
        return out
