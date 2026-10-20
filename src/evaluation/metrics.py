"""Chỉ số đánh giá chất lượng danh sách gợi ý Top-N (bài toán xếp hạng).

Quy ước Top-N:
  - Danh sách gợi ý của mỗi user loại bỏ các phim user đã chấm trong train.
  - Phim "liên quan" = phim trong test được user chấm >= RELEVANT_RATING.
  - Precision/Recall/NDCG/HitRate tính trung bình trên các user có ít nhất 1 phim liên quan.
  - Coverage/Novelty/Diversity tính trên danh sách của mọi user có trong test.
"""
import numpy as np
import pandas as pd

from src.config import RELEVANT_RATING


def top_k_items(scores: np.ndarray, seen, k: int) -> np.ndarray:
    """Chỉ số cột của k phim điểm cao nhất mỗi hàng (giảm dần), bỏ các ô seen (ma trận thưa cùng shape)."""
    s = np.array(scores, dtype=np.float32, copy=True)
    rows, cols = seen.nonzero()
    s[rows, cols] = -np.inf
    top = np.argpartition(-s, k, axis=1)[:, :k]
    order = np.argsort(-np.take_along_axis(s, top, axis=1), axis=1, kind="stable")
    return np.take_along_axis(top, order, axis=1)


def ranking_metrics(top: np.ndarray, relevant: list[set], k: int) -> dict:
    """Precision/Recall/NDCG/HitRate@k. top: (n_users, >=k) chỉ số phim; relevant[u]: tập phim liên quan."""
    discount = 1.0 / np.log2(np.arange(2, k + 2))
    prec, rec, ndcg, hit = [], [], [], []
    for u, rel in enumerate(relevant):
        if not rel:
            continue
        h = np.fromiter((it in rel for it in top[u, :k]), dtype=bool, count=k)
        n_hit = int(h.sum())
        prec.append(n_hit / k)
        rec.append(n_hit / len(rel))
        idcg = discount[:min(len(rel), k)].sum()
        ndcg.append(float((h * discount).sum() / idcg))
        hit.append(float(n_hit > 0))
    return {f"Precision@{k}": float(np.mean(prec)), f"Recall@{k}": float(np.mean(rec)),
            f"NDCG@{k}": float(np.mean(ndcg)), f"HitRate@{k}": float(np.mean(hit))}


def coverage(top: np.ndarray, n_items: int) -> float:
    """Tỉ lệ phim trong kho xuất hiện ít nhất một lần trong các danh sách gợi ý."""
    return len(np.unique(top)) / n_items


def novelty(top: np.ndarray, item_count: np.ndarray, n_users: int) -> float:
    """Trung bình -log2(độ phổ biến) của phim được gợi ý; độ phổ biến = số user đã chấm / tổng user."""
    pop = np.maximum(item_count, 1) / n_users
    return float(np.mean(-np.log2(pop[top])))


def diversity(top: np.ndarray, item_features: np.ndarray) -> float:
    """Đa dạng trong danh sách = 1 - cosine trung bình giữa các cặp phim (theo vector thể loại)."""
    F = item_features / np.maximum(np.linalg.norm(item_features, axis=1, keepdims=True), 1e-9)
    k = top.shape[1]
    V = F[top]                                         # (n_users, k, d)
    S = np.einsum("ukd,ujd->ukj", V, V)
    mean_sim = (S.sum(axis=(1, 2)) - np.trace(S, axis1=1, axis2=2)) / (k * (k - 1))
    return float(np.mean(1.0 - mean_sim))


def evaluate_model(model, test: pd.DataFrame, k: int = 10, k_beyond: int = 20,
                   item_features: np.ndarray | None = None) -> dict:
    """Mọi chỉ số cho một mô hình đã fit. item_features (n_items x d) theo thứ tự item2idx, dùng cho Diversity."""
    out = {}
    users = np.sort(test["user_id"].unique())
    uidx = np.array([model.user2idx[u] for u in users])
    top = top_k_items(model.score_matrix()[uidx], model.R[uidx], max(k, k_beyond))

    rel_df = test[test["rating"] >= RELEVANT_RATING]
    rel_map = rel_df.groupby("user_id")["movie_id"].agg(lambda s: {model.item2idx[m] for m in s}).to_dict()
    relevant = [rel_map.get(u, set()) for u in users]
    out.update(ranking_metrics(top, relevant, k))

    topb = top[:, :k_beyond]
    item_count = np.bincount(model.i, minlength=model.n_items)
    out[f"Coverage@{k_beyond}"] = coverage(topb, model.n_items)
    out[f"Novelty@{k_beyond}"] = novelty(topb, item_count, model.n_users)
    if item_features is not None:
        out[f"Diversity@{k_beyond}"] = diversity(topb, item_features)
    return out
