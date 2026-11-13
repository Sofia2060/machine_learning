"""
Script ETL (Extract - Transform - Load) nạp dữ liệu vào CSDL MySQL movie_recommender_system.

Thứ tự nạp dữ liệu tuân thủ nghiêm ngặt các ràng buộc khóa ngoại (Foreign Keys):
  1. occupations     : Danh mục 21 ngành nghề chuẩn MovieLens (ID 0-20)
  2. customers       : 6,040 khách hàng (giả lập username, email, password_hash, map occupation -> occupation_id)
  3. employees       : 1 tài khoản Admin mặc định (admin@moviesystem.com)
  4. movies          : 3,883 bộ phim (thời lượng ngẫu nhiên 90-180 phút, gán employee_id=1, is_hidden=False)
  5. genres          : Danh mục thể loại phim trích xuất từ chuỗi genres (Action|Comedy)
  6. movie_genres    : Bảng trung gian liên kết Phim - Thể loại
  7. ratings         : 1,000,209 bản ghi đánh giá (timestamp -> datetime, giả lập comment_text theo rating_score, nạp chunksize=10000)
  8. recommendations : Bảng lưu kết quả gợi ý phim AI cho người dùng
"""

import os
import sys
import time
import hashlib
import numpy as np
import pandas as pd
from pathlib import Path
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# ==============================================================================
# 1. QUẢN LÝ ĐƯỜNG DẪN ĐỘNG (PATHLIB.PATH)
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "processed"

USERS_CSV = DATA_DIR / "cleaned_users.csv"
MOVIES_CSV = DATA_DIR / "cleaned_movies.csv"
RATINGS_CSV = DATA_DIR / "cleaned_ratings.csv"

# ==============================================================================
# 2. CẤU HÌNH THÔNG SỐ KẾT NỐI MYSQL
# ==============================================================================
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "MATKHAUCUABAN")  # Thay đổi mật khẩu phù hợp với MySQL của bạn
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "movie_recommender_system")

ENCODED_PASS = quote_plus(DB_PASS)
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{ENCODED_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# Danh mục 21 ngành nghề chuẩn hóa từ MovieLens 1M (ID từ 0 đến 20)
MOVIELENS_OCCUPATIONS = [
    (0, "other"),
    (1, "academic/educator"),
    (2, "artist"),
    (3, "clerical/admin"),
    (4, "college/grad student"),
    (5, "customer service"),
    (6, "doctor/health care"),
    (7, "executive/managerial"),
    (8, "farmer"),
    (9, "homemaker"),
    (10, "K-12 student"),
    (11, "lawyer"),
    (12, "programmer"),
    (13, "retired"),
    (14, "sales/marketing"),
    (15, "scientist"),
    (16, "self-employed"),
    (17, "technician/engineer"),
    (18, "tradesman/craftsman"),
    (19, "unemployed"),
    (20, "writer"),
]

# Mẫu bình luận tích cực (rating >= 4) và trung bình/tiêu cực (rating < 4)
POSITIVE_COMMENTS = np.array([
    "Phim cực kỳ xuất sắc, kịch bản lôi cuốn và giàu cảm xúc!",
    "Diễn xuất đỉnh cao, âm thanh và hình ảnh vô cùng ấn tượng.",
    "Một siêu phẩm điện ảnh tuyệt vời, rất đáng xem lại nhiều lần.",
    "Cốt truyện lôi cuốn với nhiều nút thắt bất ngờ đến phút cuối.",
    "Tuyệt tác điện ảnh, đạo diễn và dàn diễn viên làm việc quá tốt!",
    "Nội dung ý nghĩa, thông điệp nhân văn sâu sắc và đáng suy ngẫm.",
    "Phim xem rất bánh cuốn, kỹ xảo mãn nhãn, chấm 10/10!",
    "Rất ấn tượng với phong cách kể chuyện và chiều sâu nhân vật."
])

NEUTRAL_NEGATIVE_COMMENTS = np.array([
    "Phim ở mức trung bình, xem tạm ổn để giải trí cuối tuần.",
    "Kịch bản hơi dễ đoán, nhịp phim ở một vài đoạn còn dài dòng.",
    "Diễn xuất tròn vai nhưng chưa thực sự để lại ấn tượng sâu đậm.",
    "Kỹ xảo tạm được, tuy nhiên nội dung còn khá rời rạc.",
    "Phim không đạt được kỳ vọng ban đầu, tiết tấu còn gượng gạo.",
    "Nội dung khá buồn ngủ và thiếu những phân cảnh cao trào kịch tính.",
    "Một bộ phim bình thường, không có nhiều điểm nhấn đặc sắc.",
    "Phim khá chán, xem hết thấy hơi lãng phí thời gian."
])


def get_db_engine():
    """Tạo SQLAlchemy Engine kết nối tới MySQL."""
    return create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True
    )


def test_connection(engine):
    """Kiểm tra tính khả dụng của kết nối MySQL trước khi chạy ETL."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT DATABASE(), VERSION();")).fetchone()
        db_name, db_ver = result[0], result[1]
        print(f"Kết nối thành công! CSDL: '{db_name}' | Phiên bản MySQL: {db_ver}\n")


def clean_existing_data(engine):
    """
    Xóa sạch dữ liệu cũ theo đúng thứ tự an toàn Foreign Keys để sẵn sàng nạp mới.
    Sử dụng FOREIGN_KEY_CHECKS = 0 để tránh lỗi ràng buộc khi truncate bảng.
    """
    tables_to_clear = [
        "recommendations",
        "ratings",
        "movie_genres",
        "genres",
        "movies",
        "employees",
        "customers",
        "occupations"
    ]
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        for tbl in tables_to_clear:
            conn.execute(text(f"TRUNCATE TABLE `{tbl}`;"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
    print("Đã dọn dẹp sạch dữ liệu cũ trên tất cả 8 bảng.\n")


def load_occupations(engine):
    """
    1) occupations: Nạp 21 danh mục ngành nghề chuẩn (ID 0-20 theo MovieLens).
    """
    start_time = time.time()

    df_occupations = pd.DataFrame(
        MOVIELENS_OCCUPATIONS,
        columns=["occupation_id", "occupation_name"]
    )
    df_occupations.to_sql("occupations", con=engine, if_exists="append", index=False)

    elapsed = time.time() - start_time
    print(f"Đã nạp thành công {len(df_occupations)} ngành nghề chuẩn vào 'occupations' ({elapsed:.2f}s).\n")
    return df_occupations


def load_customers(engine):
    """
    2) customers: Giả lập các cột còn thiếu trên DataFrame:
       - username = user_{id}
       - email = user_{id}@gmail.com
       - password_hash = SHA256('123456')
       - is_active = True
       - Ánh xạ occupation thành occupation_id
    """
    start_time = time.time()

    if not USERS_CSV.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {USERS_CSV}")

    df_users = pd.read_csv(USERS_CSV)
    fixed_pwd_hash = hashlib.sha256("123456".encode("utf-8")).hexdigest()

    df_customers = pd.DataFrame({
        "customer_id": df_users["user_id"],
        "username": df_users["user_id"].apply(lambda uid: f"user_{uid}"),
        "email": df_users["user_id"].apply(lambda uid: f"user_{uid}@gmail.com"),
        "password_hash": fixed_pwd_hash,
        "gender": df_users["gender_desc"] if "gender_desc" in df_users.columns else df_users["gender"],
        "age": df_users["age"].fillna(25).astype(int),
        "occupation_id": df_users["occupation"].astype(int),
        "zip_code": df_users["zip_code"].astype(str).fillna("00000"),
        "is_active": True
    })

    df_customers.to_sql("customers", con=engine, if_exists="append", index=False, chunksize=5000)

    elapsed = time.time() - start_time
    print(f"Đã nạp thành công {len(df_customers):,} khách hàng vào 'customers' ({elapsed:.2f}s).\n")
    return df_customers


def load_employees(engine):
    """
    3) employees: Tạo 1 tài khoản Admin mặc định:
       - username = 'admin'
       - email = 'admin@moviesystem.com'
    """
    start_time = time.time()

    admin_pwd_hash = hashlib.sha256("123456".encode("utf-8")).hexdigest()
    df_employees = pd.DataFrame([{
        "employee_id": 1,
        "username": "admin",
        "email": "admin@moviesystem.com",
        "password_hash": admin_pwd_hash,
        "full_name": "System Administrator",
        "is_active": True
    }])

    df_employees.to_sql("employees", con=engine, if_exists="append", index=False)

    elapsed = time.time() - start_time
    print(f"Đã tạo tài khoản quản trị mặc định 'admin' vào 'employees' ({elapsed:.2f}s).\n")
    return df_employees


def load_movies(engine):
    """
    4) movies: Đọc cleaned_movies.csv:
       - Giả lập thời lượng duration_minutes ngẫu nhiên (90-180 phút)
       - Gán employee_id = 1
       - is_hidden = False
    """
    start_time = time.time()

    if not MOVIES_CSV.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {MOVIES_CSV}")

    df_movies_raw = pd.read_csv(MOVIES_CSV)

    np.random.seed(42)
    duration_array = np.random.randint(90, 181, size=len(df_movies_raw))

    title_col = df_movies_raw["clean_title"] if "clean_title" in df_movies_raw.columns else df_movies_raw["title"]

    df_movies = pd.DataFrame({
        "movie_id": df_movies_raw["movie_id"],
        "title": title_col,
        "release_year": df_movies_raw["release_year"].fillna(2000).astype(int),
        "duration_minutes": duration_array,
        "is_hidden": False,
        "employee_id": 1
    })

    df_movies.to_sql("movies", con=engine, if_exists="append", index=False, chunksize=2000)

    elapsed = time.time() - start_time
    print(f"Đã nạp thành công {len(df_movies):,} bộ phim vào 'movies' ({elapsed:.2f}s).\n")
    return df_movies, df_movies_raw


def load_genres_and_movie_genres(engine, df_movies_raw):
    """
    5) genres & movie_genres:
       - Tách chuỗi thể loại chứa dấu '|' (ví dụ: Action|Comedy)
       - Nạp danh mục thể loại duy nhất vào genres
       - Nạp bảng trung gian movie_genres
    """
    start_time = time.time()

    # Trích xuất danh mục thể loại duy nhất
    unique_genres = set()
    for genre_str in df_movies_raw["genres"].dropna():
        for g in str(genre_str).split("|"):
            g_clean = g.strip()
            if g_clean:
                unique_genres.add(g_clean)

    sorted_genres = sorted(list(unique_genres))
    df_genres = pd.DataFrame({
        "genre_id": range(1, len(sorted_genres) + 1),
        "genre_name": sorted_genres
    })
    df_genres.to_sql("genres", con=engine, if_exists="append", index=False)
    print(f"Đã nạp {len(df_genres)} thể loại phim duy nhất vào 'genres'.")

    # Tạo bảng trung gian movie_genres
    genre_name_to_id = dict(zip(df_genres["genre_name"], df_genres["genre_id"]))
    movie_genres_records = []

    for _, row in df_movies_raw.iterrows():
        m_id = row["movie_id"]
        g_str = row.get("genres")
        if pd.notna(g_str):
            for g in str(g_str).split("|"):
                g_clean = g.strip()
                if g_clean in genre_name_to_id:
                    movie_genres_records.append({
                        "movie_id": m_id,
                        "genre_id": genre_name_to_id[g_clean]
                    })

    df_movie_genres = pd.DataFrame(movie_genres_records).drop_duplicates()
    df_movie_genres.to_sql("movie_genres", con=engine, if_exists="append", index=False, chunksize=5000)

    elapsed = time.time() - start_time
    print(f"Đã nạp {len(df_movie_genres):,} liên kết Phim-Thể loại vào 'movie_genres' ({elapsed:.2f}s).\n")
    return df_genres, df_movie_genres


def load_ratings(engine, valid_customers, valid_movies):
    """
    6) ratings: Đọc cleaned_ratings.csv:
       - Chuyển Unix timestamp thành DATETIME
       - Giả lập comment_text ngẫu nhiên dựa vào mức điểm:
         + rating >= 4: câu tích cực
         + rating < 4: câu trung bình / tiêu cực
       - Nạp 1.000.209 dòng bằng pandas.to_sql() với chunksize=10000 để tối ưu RAM và tốc độ
    """
    start_time = time.time()

    if not RATINGS_CSV.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {RATINGS_CSV}")

    df_ratings = pd.read_csv(RATINGS_CSV)
    total_raw_ratings = len(df_ratings)
    print(f"Tổng số dòng ratings đọc từ CSV: {total_raw_ratings:,}")

    # Vectorized comment generation theo mức điểm đánh giá để tối ưu tốc độ xử lý
    np.random.seed(42)
    is_positive = df_ratings["rating"] >= 4.0
    num_pos = int(is_positive.sum())
    num_neg = total_raw_ratings - num_pos

    generated_comments = np.empty(total_raw_ratings, dtype=object)
    generated_comments[is_positive] = np.random.choice(POSITIVE_COMMENTS, size=num_pos)
    generated_comments[~is_positive] = np.random.choice(NEUTRAL_NEGATIVE_COMMENTS, size=num_neg)

    # Chuyển đổi Unix timestamp thành DATETIME
    if "timestamp" in df_ratings.columns:
        rating_time_series = pd.to_datetime(df_ratings["timestamp"], unit="s")
    else:
        rating_time_series = pd.to_datetime(df_ratings["datetime"])

    df_ratings_db = pd.DataFrame({
        "customer_id": df_ratings["user_id"].astype(int),
        "movie_id": df_ratings["movie_id"].astype(int),
        "rating_score": df_ratings["rating"].astype(float),
        "comment_text": generated_comments,
        "rating_time": rating_time_series
    })

    # Đảm bảo toàn vẹn dữ liệu: chỉ giữ các bản ghi có customer_id và movie_id hợp lệ
    cust_set = set(valid_customers["customer_id"])
    mov_set = set(valid_movies["movie_id"])
    initial_count = len(df_ratings_db)
    df_ratings_db = df_ratings_db[
        df_ratings_db["customer_id"].isin(cust_set) &
        df_ratings_db["movie_id"].isin(mov_set)
    ]
    if len(df_ratings_db) < initial_count:
        print(f"Đã lọc bỏ {initial_count - len(df_ratings_db):,} dòng ratings không hợp lệ khóa ngoại.")

    # Nạp theo từng khối (chunksize=10000) vào MySQL để tối ưu bộ nhớ RAM và tốc độ
    df_ratings_db.to_sql(
        "ratings",
        con=engine,
        if_exists="append",
        index=False,
        chunksize=10000
    )

    elapsed = time.time() - start_time
    print(f"Đã nạp thành công {len(df_ratings_db):,} đánh giá vào 'ratings' ({elapsed:.2f}s - chunksize=10,000).\n")
    return df_ratings_db


def seed_sample_recommendations(engine, valid_customers, valid_movies):
    """
    8) recommendations: Khởi tạo dữ liệu mẫu Top 10 phim gợi ý AI cho một số khách hàng đầu tiên.
    """
    start_time = time.time()

    np.random.seed(42)
    sample_customers = list(valid_customers["customer_id"])[:300]
    movie_pool = list(valid_movies["movie_id"])

    rec_records = []
    for c_id in sample_customers:
        selected_movies = np.random.choice(movie_pool, size=10, replace=False)
        scores = np.sort(np.random.uniform(3.8, 5.0, size=10))[::-1]

        for rank, (m_id, score) in enumerate(zip(selected_movies, scores), start=1):
            rec_records.append({
                "customer_id": c_id,
                "movie_id": m_id,
                "predicted_score": round(float(score), 2),
                "rank_position": rank
            })

    df_recs = pd.DataFrame(rec_records)
    df_recs.to_sql("recommendations", con=engine, if_exists="append", index=False, chunksize=3000)

    elapsed = time.time() - start_time
    print(f"Đã nạp {len(df_recs):,} kết quả gợi ý AI vào 'recommendations' ({elapsed:.2f}s).\n")
    return df_recs


def main():
    total_start_time = time.time()
    print("BẮT ĐẦU QUY TRÌNH ETL NẠP DỮ LIỆU VÀO MYSQL (MOVIE RECOMMENDER SYSTEM)")
    try:
        # Bước 1: Khởi tạo kết nối SQLAlchemy
        engine = get_db_engine()
        test_connection(engine)

        # Bước 2: Dọn dẹp dữ liệu cũ an toàn
        clean_existing_data(engine)

        # Bước 3: Nạp 21 danh mục nghề nghiệp chuẩn MovieLens (occupations)
        load_occupations(engine)

        # Bước 4: Nạp khách hàng (customers)
        df_customers = load_customers(engine)

        # Bước 5: Nạp tài khoản nhân viên / admin mặc định (employees)
        load_employees(engine)

        # Bước 6: Nạp danh sách phim (movies)
        df_movies, df_movies_raw = load_movies(engine)

        # Bước 7: Nạp danh mục thể loại (genres) & bảng liên kết (movie_genres)
        load_genres_and_movie_genres(engine, df_movies_raw)

        # Bước 8: Nạp 1.000.209 đánh giá & giả lập bình luận (ratings) với chunksize=10,000
        load_ratings(engine, df_customers, df_movies)

        # Bước 9: Nạp gợi ý phim AI mẫu (recommendations)
        seed_sample_recommendations(engine, df_customers, df_movies)

        total_elapsed = time.time() - total_start_time
        print(f"HOÀN THÀNH QUY TRÌNH ETL NẠP DỮ LIỆU THÀNH CÔNG VÀO 8 BẢNG!")

    except SQLAlchemyError as db_err:
        print("\n" + "!" * 70)
        print(f"[LỖI CSDL]: Lỗi xảy ra trong quá trình kết nối hoặc thao tác với MySQL:")
        print(f"   Chi tiết: {db_err}")
        print("Gợi ý khắc phục:")
        print("   1. Kiểm tra dịch vụ MySQL Server đang khởi chạy (XAMPP / MySQL Service).")
        print("   2. Kiểm tra tài khoản (DB_USER) và mật khẩu (DB_PASS) trong file cấu hình.")
        print("   3. Đảm bảo CSDL 'movie_recommender_system' đã được tạo trước:")
        print("      mysql -u root -p < mysql/mrs_schema.sql")
        print("!" * 70)
        sys.exit(1)

    except FileNotFoundError as fnf_err:
        print("\n" + "!" * 70)
        print(f"[LỖI TẬP TIN]: {fnf_err}")
        print("Vui lòng đảm bảo các file CSV đã được sinh ra trong thư mục data/processed/:")
        print("   - cleaned_users.csv")
        print("   - cleaned_movies.csv")
        print("   - cleaned_ratings.csv")
        print("!" * 70)
        sys.exit(1)

    except Exception as ex:
        print("\n" + "!" * 70)
        print(f"[LỖI KHÔNG XÁC ĐỊNH]: {ex}")
        print("!" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()