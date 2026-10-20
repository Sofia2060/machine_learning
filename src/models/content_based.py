"""Content-based filtering: hồ sơ user xây từ đặc trưng nội dung của phim đã xem.

Đặc trưng phim (L2-chuẩn hóa):
  - "genres": one-hot 18 thể loại
  - "genres+title": thể loại + TF-IDF các từ trong tiêu đề (đã bỏ năm) + thập niên phát hành
Hồ sơ user = tổng (rating - trung bình user) * đặc trưng phim, rồi điểm = cosine(hồ sơ user, đặc trưng phim).
Điểm cosine được quy về thang rating bằng  b_ui + w * cosine  (w ước lượng bằng hồi quy trên train).
TF-IDF tính trên CPU (scikit-learn); hồ sơ user và cosine tính bằng PyTorch trên `device` (GPU CUDA nếu có).
"""
import numpy as np
import pandas as pd
import torch
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from src.data.preprocess import genres_multi_hot
from src.models.base import BaseRecommender
from src.models.baseline import fit_biases
from src.models.device import get_device, to_dense


def build_item_features(movies: pd.DataFrame, idx2item: np.ndarray, kind: str = "genres") -> np.ndarray:
    """Ma trận đặc trưng (n_items x d) theo đúng thứ tự cột của ma trận rating.

    movies là bảng phim đã làm sạch (src.data.preprocess.clean_movies): cần clean_title, release_year, genres.
    """
    mv = movies.set_index("movie_id").loc[idx2item]
    G = genres_multi_hot(movies).loc[idx2item].to_numpy(dtype=np.float32)
    if kind == "genres":
        F = G
    elif kind == "genres+title":
        titles = mv["clean_title"].tolist()
        T = TfidfVectorizer(min_df=3, stop_words="english").fit_transform(titles).toarray().astype(np.float32)
        decade = pd.get_dummies(mv["release_year"] // 10 * 10).to_numpy(dtype=np.float32)
        F = np.hstack([G, 0.5 * T, 0.5 * decade])
    else:
        raise ValueError(kind)
    return normalize(F)


class ContentBased(BaseRecommender):
    def __init__(self, features: str = "genres", device: str = "auto"):
        self.features = features
        self.device = get_device(device)
        self.name = f"ContentBased({features})"

    def fit(self, train, user2idx, item2idx, movies=None):
        if movies is None:
            raise ValueError("ContentBased cần bảng movies (truyền movies=... vào fit)")
        return super().fit(train, user2idx, item2idx, movies)

    def _fit(self):
        self.F = build_item_features(self.movies, self.idx2item, self.features)
        mu, bu, bi = fit_biases(self.u, self.i, self.r, self.n_users, self.n_items)
        self.base = (mu + bu[:, None] + bi[None, :]).astype(np.float32)

        resid = self.r - self.base[self.u, self.i]
        E = sparse.csr_matrix((resid, (self.u, self.i)), shape=(self.n_users, self.n_items))
        F = to_dense(self.F, self.device)
        profile = to_dense(E, self.device) @ F            # (n_users, d)
        norm = profile.norm(dim=1, keepdim=True)
        profile = profile / torch.where(norm > 0, norm, torch.ones_like(norm))  # như sklearn normalize
        self.cos = (profile @ F.T).cpu().numpy()

        # w: hồi quy resid ~ w * cos trên các cặp đã chấm
        c = self.cos[self.u, self.i]
        self.w = float((c * resid).sum() / max((c * c).sum(), 1e-9))

    def _score_matrix(self):
        return self.base + self.w * self.cos
