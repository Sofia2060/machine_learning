"""Hybrid: kết hợp tuyến tính điểm của nhiều mô hình (thường CF + content-based)."""
import numpy as np

from src.models.base import BaseRecommender


class WeightedHybrid(BaseRecommender):
    """score = sum_k w_k * score_k  (w được chuẩn hóa để tổng bằng 1).

    Các mô hình thành phần nên cùng thang rating 1-5 (BiasedMF, ItemKNN, ContentBased...).
    prefit=True: dùng mô hình đã fit sẵn, không huấn luyện lại (tiện khi dò trọng số trên tập validation).
    """

    def __init__(self, models: list[BaseRecommender], weights: list[float], prefit: bool = False,
                 label: str | None = None):
        assert len(models) == len(weights)
        w = np.asarray(weights, dtype=np.float64)
        self.models, self.weights, self.prefit = models, w / w.sum(), prefit
        self.predicts_rating = all(m.predicts_rating for m in models)
        parts = "+".join(f"{wi:.2f}*{m.name.split('(')[0]}" for wi, m in zip(self.weights, models))
        self.name = label or f"Hybrid[{parts}]"

    def fit(self, train, user2idx, item2idx, movies=None):
        self._args = (train, user2idx, item2idx, movies)
        return super().fit(train, user2idx, item2idx, movies)

    def _fit(self):
        if not self.prefit:
            for m in self.models:
                m.fit(*self._args)

    def _score_matrix(self):
        return sum(w * m.score_matrix() for w, m in zip(self.weights, self.models))
