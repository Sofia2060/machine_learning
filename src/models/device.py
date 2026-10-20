"""Chọn thiết bị tính toán cho các mô hình PyTorch."""
import numpy as np
import torch
from scipy import sparse


def get_device(preference: str = "auto") -> torch.device:
    """'auto' -> cuda nếu có, ngược lại cpu. Có thể truyền 'cpu' hoặc 'cuda' để ép."""
    if preference == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if preference.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("Yêu cầu CUDA nhưng torch.cuda.is_available() = False "
                           "(đang cài bản torch CPU hoặc thiếu driver?)")
    return torch.device(preference)


def to_dense(X, device: torch.device, dtype=torch.float32) -> torch.Tensor:
    """Ma trận thưa scipy hoặc mảng numpy -> tensor dày trên device."""
    if sparse.issparse(X):
        X = X.toarray()
    return torch.as_tensor(np.asarray(X), dtype=dtype, device=device)
