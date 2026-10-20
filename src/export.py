"""Xuất NeuMF đã huấn luyện thành file numpy cho phần mềm: <tên>.npz (trọng số) + <tên>_meta.json (mô tả).

Phần mềm đọc lại bằng src.inference.NeuMFRecommender, chỉ cần numpy (không cần torch).
"""
import json
import time
from pathlib import Path

import numpy as np
from torch import nn

from src.models.neural import NeuMF

FORMAT_VERSION = 1


def meta_path(path: Path) -> Path:
    """models/main_model/neumf.npz -> models/main_model/neumf_meta.json"""
    return path.with_name(path.stem + "_meta.json")


def export_neumf(model: NeuMF, path, extra_meta: dict | None = None) -> tuple[Path, Path]:
    """Ghi trọng số của một NeuMF đã fit, thứ tự user/phim của các bảng embedding và độ phổ biến của phim
    (số lượt rating trong dữ liệu huấn luyện, dùng để gợi ý dự phòng cho user không có trong mô hình)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    net = model.net

    def arr(t):
        return t.detach().cpu().numpy().astype(np.float32)

    linears = [m for m in net.mlp if isinstance(m, nn.Linear)]
    data = {
        "gu": arr(net.gu.weight), "gi": arr(net.gi.weight),      # nhánh GMF
        "mu": arr(net.mu.weight), "mi": arr(net.mi.weight),      # nhánh MLP
        "out_w": arr(net.out.weight).ravel(), "out_b": arr(net.out.bias),
        "user_ids": model.idx2user.astype(np.int64),             # hàng k của bảng user  <-> user_ids[k]
        "movie_ids": model.idx2item.astype(np.int64),            # hàng k của bảng phim  <-> movie_ids[k]
        "popularity": np.bincount(model.i, minlength=model.n_items).astype(np.int64),
    }
    for k, lin in enumerate(linears):
        data[f"mlp_w{k}"], data[f"mlp_b{k}"] = arr(lin.weight), arr(lin.bias)
    np.savez_compressed(path, **data)

    meta = {
        "format_version": FORMAT_VERSION,
        "model": model.name,
        "n_factors": model.n_factors,
        "mlp_layers": list(model.mlp_layers),
        "n_mlp": len(linears),
        "epochs": model.epochs,
        "seed": model.seed,
        "n_users": model.n_users,
        "n_items": model.n_items,
        "n_ratings": int(len(model.r)),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        **(extra_meta or {}),
    }
    mp = meta_path(path)
    mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, mp
