"""Feature engineering (notebook 03): tạo bảng đặc trưng 90 cột cho từng lượt rating.

Đầu vào là 3 bảng sạch từ src.data.preprocess (schema snake_case). Đầu ra lưu ở data/processed/featured_dataset.parquet.

Lưu ý: các thống kê (trung bình, bias, SVD...) được tính trên TOÀN BỘ ratings truyền vào. Khi dùng cho mô hình
có tập test, hãy truyền riêng ratings của train để tránh rò rỉ dữ liệu.
"""
import time

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD

from src.config import FEATURED_FILE, PROCESSED_DIR, SEED
from src.data.preprocess import genres_multi_hot


def extract_user_features(ratings: pd.DataFrame, users: pd.DataFrame, global_mean: float) -> pd.DataFrame:
    """Đặc trưng người dùng: số lượt / trung bình / độ lệch chuẩn rating, user_bias, mã hóa giới tính,
    one-hot nhóm tuổi và nghề nghiệp (giữ cả mã số gốc age, occupation cho mô hình dạng cây)."""
    u_stats = ratings.groupby("user_id")["rating"].agg(
        user_rating_count="count", user_rating_mean="mean", user_rating_std="std").reset_index()
    u_stats["user_rating_std"] = u_stats["user_rating_std"].fillna(0.0)    # user chỉ có 1 rating
    u_stats["user_bias"] = u_stats["user_rating_mean"] - global_mean

    u_feat = users[["user_id", "gender", "age", "age_group", "occupation"]].merge(u_stats, on="user_id", how="left")
    u_feat["gender_binary"] = (u_feat["gender"] == "M").astype(np.int8)
    age_dummies = pd.get_dummies(u_feat["age_group"], prefix="age", dtype=np.int8)
    occ_dummies = pd.get_dummies(u_feat["occupation"], prefix="occ", dtype=np.int8)
    u_feat = pd.concat([u_feat, age_dummies, occ_dummies], axis=1)
    return u_feat.drop(columns=["gender", "age_group"])


def extract_movie_features(ratings: pd.DataFrame, movies: pd.DataFrame,
                           global_mean: float) -> tuple[pd.DataFrame, list[str]]:
    """Đặc trưng phim: thống kê rating, movie_bias, năm phát hành, số thể loại, multi-hot 18 thể loại.
    Trả về (bảng đặc trưng phim, danh sách cột thể loại)."""
    m_stats = ratings.groupby("movie_id")["rating"].agg(
        movie_rating_count="count", movie_rating_mean="mean", movie_rating_std="std").reset_index()
    m_stats["movie_rating_std"] = m_stats["movie_rating_std"].fillna(0.0)
    m_stats["movie_bias"] = m_stats["movie_rating_mean"] - global_mean

    G = genres_multi_hot(movies)
    genre_cols = list(G.columns)
    movie_encoded = pd.concat([movies.reset_index(drop=True), G.reset_index(drop=True)], axis=1)
    movie_encoded["num_genres"] = movie_encoded[genre_cols].sum(axis=1).astype(np.int8)

    m_feat = movie_encoded[["movie_id", "release_year", "num_genres"] + genre_cols].merge(
        m_stats, on="movie_id", how="left")
    # phim chưa có rating nào
    m_feat["movie_rating_count"] = m_feat["movie_rating_count"].fillna(0).astype(np.int32)
    m_feat["movie_rating_mean"] = m_feat["movie_rating_mean"].fillna(global_mean)
    m_feat["movie_rating_std"] = m_feat["movie_rating_std"].fillna(0.0)
    m_feat["movie_bias"] = m_feat["movie_bias"].fillna(0.0)
    return m_feat, genre_cols


def extract_temporal_features(ratings: pd.DataFrame, movies: pd.DataFrame) -> pd.DataFrame:
    """Đặc trưng thời gian: năm / tháng / thứ đánh giá, cờ cuối tuần, tuổi của phim lúc được đánh giá."""
    temp_df = ratings.copy()
    if not np.issubdtype(temp_df["datetime"].dtype, np.datetime64):
        temp_df["datetime"] = pd.to_datetime(temp_df["datetime"])

    temp_df["rating_year"] = temp_df["datetime"].dt.year.astype(np.int16)
    temp_df["rating_month"] = temp_df["datetime"].dt.month.astype(np.int8)
    temp_df["rating_dayofweek"] = temp_df["datetime"].dt.dayofweek.astype(np.int8)
    temp_df["is_weekend"] = temp_df["rating_dayofweek"].isin([5, 6]).astype(np.int8)

    temp_m = temp_df[["movie_id", "rating_year"]].merge(movies[["movie_id", "release_year"]], on="movie_id", how="left")
    # kẹp về 0 nếu phim ra mắt và được chấm trong cùng năm
    temp_df["movie_age_at_rating"] = np.maximum(0, temp_m["rating_year"] - temp_m["release_year"]).astype(np.int16)
    return temp_df


def extract_interaction_features(ratings: pd.DataFrame, users: pd.DataFrame, movies: pd.DataFrame,
                                 genre_cols: list[str], global_mean: float) -> pd.DataFrame:
    """Đặc trưng tương tác: hồ sơ thể loại của user, genre_match_score (cosine gu user - thể loại phim),
    điểm trung bình của phim theo nhóm giới tính. `ratings` phải có sẵn cột gender; `movies` là bảng
    đặc trưng phim (có num_genres và các cột thể loại)."""
    df = ratings.copy()

    # 1. Tỉ lệ xuất hiện của từng thể loại trong lịch sử của user
    merged_g = df[["user_id", "movie_id"]].merge(movies[["movie_id"] + genre_cols], on="movie_id", how="left")
    user_genre_pref = merged_g.groupby("user_id")[genre_cols].mean()
    pref_cols = [f'user_pref_{col.replace("genre_", "")}' for col in genre_cols]
    user_genre_pref.columns = pref_cols
    user_genre_pref["user_genre_norm"] = np.sqrt((user_genre_pref ** 2).sum(axis=1))

    # 2. Genre Match Score = cosine(hồ sơ thể loại user, multi-hot thể loại phim)
    u_pref_df = df[["user_id", "movie_id"]].merge(user_genre_pref, on="user_id", how="left")
    m_genre_df = df[["user_id", "movie_id"]].merge(movies[["movie_id", "num_genres"] + genre_cols],
                                                   on="movie_id", how="left")
    dot_product = np.zeros(len(df), dtype=np.float32)
    for p_col, g_col in zip(pref_cols, genre_cols):
        dot_product += u_pref_df[p_col].values * m_genre_df[g_col].values
    movie_norm = np.sqrt(m_genre_df["num_genres"].values.astype(np.float32))
    user_norm = u_pref_df["user_genre_norm"].values.astype(np.float32)
    denom = movie_norm * user_norm
    df["genre_match_score"] = np.where(denom > 0, dot_product / denom, 0.0).astype(np.float32)

    # 3. Điểm trung bình của phim theo giới tính người chấm
    rat_u = df[["user_id", "movie_id", "rating"]].merge(users[["user_id", "gender"]], on="user_id", how="left")
    gender_movie_means = rat_u.groupby(["movie_id", "gender"])["rating"].mean().reset_index().rename(
        columns={"rating": "gender_movie_mean_rating"})
    df = df.merge(gender_movie_means, on=["movie_id", "gender"], how="left")
    df["gender_movie_mean_rating"] = df["gender_movie_mean_rating"].fillna(global_mean).astype(np.float32)
    return df


def extract_latent_svd_features(ratings: pd.DataFrame, n_components: int = 10,
                                random_state: int = SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Embedding ẩn từ TruncatedSVD trên ma trận User-Item. Trả về (user_svd_df, movie_svd_df)."""
    user_ids = sorted(ratings["user_id"].unique())
    movie_ids = sorted(ratings["movie_id"].unique())
    u_map = {uid: i for i, uid in enumerate(user_ids)}
    m_map = {mid: i for i, mid in enumerate(movie_ids)}

    rows = ratings["user_id"].map(u_map)
    cols = ratings["movie_id"].map(m_map)
    R = csr_matrix((ratings["rating"].values, (rows, cols)), shape=(len(user_ids), len(movie_ids)), dtype=np.float32)

    svd = TruncatedSVD(n_components=n_components, random_state=random_state)
    U = svd.fit_transform(R)          # (n_users, k)
    V = svd.components_.T             # (n_movies, k)

    user_svd_cols = [f"user_svd_{i}" for i in range(n_components)]
    movie_svd_cols = [f"movie_svd_{i}" for i in range(n_components)]
    user_svd_df = pd.DataFrame(U, index=user_ids, columns=user_svd_cols).reset_index().rename(columns={"index": "user_id"})
    movie_svd_df = pd.DataFrame(V, index=movie_ids, columns=movie_svd_cols).reset_index().rename(columns={"index": "movie_id"})
    return user_svd_df, movie_svd_df


def optimize_memory_usage(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """Ép kiểu để giảm RAM: int64 -> int8/16/32 theo miền giá trị, float64 -> float32, bool -> int8."""
    initial_mem = df.memory_usage(deep=True).sum() / (1024 ** 2)
    for col in df.columns:
        col_type = df[col].dtype
        if np.issubdtype(col_type, np.integer):
            c_min, c_max = df[col].min(), df[col].max()
            if c_min >= -128 and c_max <= 127:
                df[col] = df[col].astype(np.int8)
            elif c_min >= -32768 and c_max <= 32767:
                df[col] = df[col].astype(np.int16)
            elif c_min >= -2147483648 and c_max <= 2147483647:
                df[col] = df[col].astype(np.int32)
        elif np.issubdtype(col_type, np.floating):
            df[col] = df[col].astype(np.float32)
        elif col_type == "bool":
            df[col] = df[col].astype(np.int8)
    final_mem = df.memory_usage(deep=True).sum() / (1024 ** 2)
    if verbose:
        reduction = 100 * (initial_mem - final_mem) / initial_mem
        print(f"Dung lượng ban đầu: {initial_mem:.2f} MB")
        print(f"Dung lượng sau tối ưu: {final_mem:.2f} MB (Giảm {reduction:.1f}%)")
    return df


def build_full_feature_pipeline(ratings: pd.DataFrame, users: pd.DataFrame, movies: pd.DataFrame,
                                n_svd: int = 10, verbose: bool = True) -> pd.DataFrame:
    """Chạy toàn bộ pipeline đặc trưng, trả về bảng (số rating x 90 cột) không còn giá trị thiếu."""
    log = print if verbose else (lambda *a, **k: None)
    start_time = time.time()
    log("=" * 80)
    log("BẮT ĐẦU QUY TRÌNH TRÍCH XUẤT ĐẶC TRƯNG TOÀN DIỆN (FULL FEATURE PIPELINE)")
    log("=" * 80)

    global_mean = float(ratings["rating"].mean())
    log(f"1. Điểm đánh giá trung bình toàn cầu (Global Mean): {global_mean:.4f}")

    log("2. Đang tạo User Features (Thống kê lịch sử, bias, mã hóa nhân khẩu học)...")
    user_feat = extract_user_features(ratings, users, global_mean)

    log("3. Đang tạo Movie Features (Thống kê phim, bias, multi-hot thể loại)...")
    movie_feat, genre_cols = extract_movie_features(ratings, movies, global_mean)

    log("4. Đang tạo Temporal Features (Năm, tháng, thứ, cuối tuần, tuổi của phim)...")
    temp_ratings = extract_temporal_features(ratings, movies)
    temp_ratings = temp_ratings.merge(users[["user_id", "gender"]], on="user_id", how="left")  # gender tạm thời

    log("5. Đang tạo Interaction Features (Genre Match Score, Group Mean Rating)...")
    inter_ratings = extract_interaction_features(temp_ratings, users, movie_feat, genre_cols, global_mean)

    log(f"6. Đang huấn luyện TruncatedSVD (k={n_svd}) để tạo Latent Embeddings...")
    u_svd, m_svd = extract_latent_svd_features(ratings, n_components=n_svd)

    log("7. Đang hợp nhất toàn bộ các khối đặc trưng vào bảng master features_df...")
    features_df = inter_ratings.merge(user_feat, on="user_id", how="left")
    features_df = features_df.merge(movie_feat, on="movie_id", how="left")
    features_df = features_df.merge(u_svd, on="user_id", how="left")
    features_df = features_df.merge(m_svd, on="movie_id", how="left")

    log("8. Đang tính toán tích vô hướng tương tác tiềm ẩn (SVD Dot Product)...")
    svd_dot = np.zeros(len(features_df), dtype=np.float32)
    for i in range(n_svd):
        svd_dot += features_df[f"user_svd_{i}"].values * features_df[f"movie_svd_{i}"].values
    features_df["svd_dot_product"] = svd_dot

    features_df = features_df.drop(columns=[c for c in ("gender", "timestamp", "datetime") if c in features_df.columns])
    features_df = features_df.fillna(0.0)

    log("9. Đang tối ưu hóa dung lượng bộ nhớ...")
    features_df = optimize_memory_usage(features_df, verbose=verbose)

    log("=" * 80)
    log(f"HOÀN TẤT FEATURE ENGINEERING PIPELINE TRONG {time.time() - start_time:.2f} GIÂY!")
    log(f"Kích thước tập đặc trưng cuối cùng: {features_df.shape[0]:,} dòng x {features_df.shape[1]} cột")
    log("=" * 80)
    return features_df


def save_featured(features_df: pd.DataFrame):
    """Lưu bảng đặc trưng ra Parquet (nén Snappy) tại data/processed/featured_dataset.parquet."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    features_df.to_parquet(FEATURED_FILE, engine="pyarrow", compression="snappy", index=False)
    return FEATURED_FILE


def load_featured() -> pd.DataFrame:
    return pd.read_parquet(FEATURED_FILE, engine="pyarrow")
