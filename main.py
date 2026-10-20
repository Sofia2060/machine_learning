"""Ứng dụng chính: hệ thống gợi ý phim MovieLens 1M.

Cách dùng (chạy từ bất kỳ thư mục nào, mọi đường dẫn tính tương đối theo vị trí dự án):
    python main.py                                   # chế độ tương tác (menu)
    python main.py prepare                           # tạo dữ liệu sạch, master, đặc trưng (= notebooks 01-03)
    python main.py info                              # thống kê dữ liệu và danh sách mô hình
    python main.py recommend --user 1 -k 10          # gợi ý Top-10 cho user 1 (mô hình mặc định: hybrid)
    python main.py recommend --user 1 --model biased_mf --retrain
    python main.py predict --user 1 --movie 1193     # dự đoán rating
    python main.py search "matrix"                   # tìm MovieID theo tên phim
    python main.py evaluate --family baseline        # đánh giá một nhóm mô hình -> outputs/metrics/<family>.csv
    python main.py evaluate --family all

Mô hình đã huấn luyện được lưu ở models/<tên>.pkl và nạp lại ở lần chạy sau.
"""
import argparse
import sys

import pandas as pd

from src import recommender as rs
from src.data.features import build_full_feature_pipeline, save_featured
from src.data.preprocess import build_master_dataset, preprocess_raw, save_cleaned, save_master
from src.experiment import load_experiment, run_model, save_metrics

pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 60)


def check_ids(exp, user=None, movie=None, k=None, n=None):
    """Kiểm tra đầu vào TRƯỚC khi nạp/huấn luyện mô hình (có thể mất vài chục giây)."""
    if user is not None and user not in exp.user2idx:
        raise KeyError(f"UserID {user} không có trong dữ liệu (hợp lệ: {min(exp.user2idx)}..{max(exp.user2idx)})")
    if movie is not None and movie not in exp.item2idx:
        raise KeyError(f"MovieID {movie} không có trong dữ liệu (dùng lệnh search để tìm MovieID)")
    if k is not None and not 1 <= k <= 100:
        raise KeyError(f"k phải trong khoảng 1..100 (nhận {k})")
    if n is not None and n < 0:
        raise KeyError(f"số dòng hiển thị phải >= 0 (nhận {n})")


def cmd_prepare(args):
    """Chạy lại toàn bộ pipeline dữ liệu bằng đúng các hàm mà notebooks 01-03 gọi."""
    users, movies, ratings = preprocess_raw()
    for path in save_cleaned(users, movies, ratings):
        print(f"Đã lưu {path}")
    print(f"Đã lưu {save_master(build_master_dataset(users, movies, ratings))}")
    if args.skip_features:
        return
    features = build_full_feature_pipeline(ratings, users, movies)
    try:
        print(f"Đã lưu {save_featured(features)}")
    except ImportError as e:                      # pandas cần pyarrow để ghi parquet
        print(f"Không ghi được parquet ({e}). Cài bằng: pip install pyarrow", file=sys.stderr)


def cmd_info(exp, args):
    n_u, n_i, n = len(exp.user2idx), len(exp.item2idx), len(exp.train) + len(exp.test)
    print(f"Users: {n_u:,} | Phim: {n_i:,} | Ratings: {n:,} (train {len(exp.train):,} / test {len(exp.test):,})")
    print(f"Độ thưa ma trận: {1 - n / (n_u * n_i):.2%}")
    print("\nMô hình có sẵn (--model):")
    for family, (label, keys) in rs.FAMILIES.items():
        print(f"  {label:<22} " + ", ".join(k + ("*" if rs.model_path(k).exists() else "") for k in keys))
    print("  (* = đã có file trong models/)")


def cmd_recommend(exp, args):
    check_ids(exp, user=args.user, k=args.k, n=args.history)
    model = rs.get_model(args.model, exp, retrain=args.retrain)
    if args.history:
        print(f"\nPhim user {args.user} đã chấm cao nhất:")
        print(rs.user_history(exp, args.user, args.history).to_string(index=False))
    rec = rs.recommend(model, args.user, args.k)
    print(f"\nTop-{args.k} gợi ý cho user {args.user} ({model.name}):")
    print(rec.round(3).to_string(index=False))


def cmd_predict(exp, args):
    check_ids(exp, user=args.user, movie=args.movie)
    model = rs.get_model(args.model, exp, retrain=args.retrain)
    title = exp.movies.set_index("movie_id")["title"].get(args.movie, "?")
    score = rs.predict_rating(model, args.user, args.movie)
    kind = "rating dự đoán" if model.predicts_rating else "điểm xếp hạng (không phải thang 1-5)"
    print(f"User {args.user} - '{title}': {kind} = {score:.3f}  ({model.name})")


def cmd_search(exp, args):
    check_ids(exp, n=args.n)
    hit = rs.search_movies(exp, args.query, args.n)
    print(hit.to_string(index=False) if len(hit) else "Không tìm thấy phim nào.")


def cmd_evaluate(exp, args):
    families = list(rs.FAMILIES) if args.family == "all" else [args.family]
    for family in families:
        rows = []
        for key in rs.FAMILIES[family][1]:
            model = rs.create_model(key)
            row = run_model(model, exp)
            row["Family"] = rs.family_label(family, model)
            rows.append(row)
            print(f"  {row['Model']:<32} NDCG@10={row['NDCG@10']:.4f}  HitRate@10={row['HitRate@10']:.4f}  "
                  f"({row['FitTime_s']:.1f}s)")
            del model
        path = save_metrics(pd.DataFrame(rows), family)
        print(f"[{family}] đã lưu {path}")


def interactive(exp):
    model_key = rs.DEFAULT_MODEL
    model = None
    menu = ("\n=== HỆ THỐNG GỢI Ý PHIM (mô hình: {}) ===\n"
            "1. Gợi ý phim cho user\n2. Dự đoán rating\n3. Tìm phim theo tên\n"
            "4. Đổi mô hình\n5. Thông tin dữ liệu\n0. Thoát")
    while True:
        print(menu.format(model_key))
        try:
            choice = input("Chọn: ").strip()
            if choice == "0":
                return
            if choice == "1":
                uid = int(input("UserID: "))
                k = int(input("Số phim (Enter = 10): ") or 10)
                check_ids(exp, user=uid, k=k)
                model = model or rs.get_model(model_key, exp)
                print(rs.user_history(exp, uid, 5).to_string(index=False))
                print(f"\nGợi ý ({model.name}):")
                print(rs.recommend(model, uid, k).round(3).to_string(index=False))
            elif choice == "2":
                uid, mid = int(input("UserID: ")), int(input("MovieID: "))
                check_ids(exp, user=uid, movie=mid)
                model = model or rs.get_model(model_key, exp)
                kind = "Rating dự đoán" if model.predicts_rating else "Điểm xếp hạng (không phải thang 1-5)"
                print(f"{kind}: {rs.predict_rating(model, uid, mid):.3f}")
            elif choice == "3":
                cmd_search(exp, argparse.Namespace(query=input("Từ khóa: "), n=15))
            elif choice == "4":
                print("Mô hình: " + ", ".join(rs.MODELS))
                key = input("Tên mô hình: ").strip()
                if key in rs.MODELS:
                    model_key, model = key, None
                else:
                    print("Không có mô hình này.")
            elif choice == "5":
                cmd_info(exp, None)
        except (ValueError, KeyError) as e:
            print(f"Lỗi: {e.args[0] if e.args else e}")
        except (EOFError, KeyboardInterrupt):
            print()
            return


def build_parser():
    p = argparse.ArgumentParser(description="Hệ thống gợi ý phim MovieLens 1M")
    sub = p.add_subparsers(dest="command")
    pp = sub.add_parser("prepare", help="tạo cleaned_*.csv, master_dataset.csv, featured_dataset.parquet")
    pp.add_argument("--skip-features", action="store_true", help="bỏ qua bước tạo đặc trưng (notebook 03)")
    sub.add_parser("info", help="thống kê dữ liệu và danh sách mô hình")

    def add_model_args(sp):
        sp.add_argument("--model", default=rs.DEFAULT_MODEL, choices=list(rs.MODELS))
        sp.add_argument("--retrain", action="store_true", help="huấn luyện lại thay vì nạp models/<model>.pkl")

    r = sub.add_parser("recommend", help="gợi ý Top-k phim cho một user")
    r.add_argument("--user", type=int, required=True)
    r.add_argument("-k", type=int, default=10)
    r.add_argument("--history", type=int, default=5, help="số phim đã xem hiển thị kèm (0 = ẩn)")
    add_model_args(r)

    pr = sub.add_parser("predict", help="dự đoán rating của user cho một phim")
    pr.add_argument("--user", type=int, required=True)
    pr.add_argument("--movie", type=int, required=True)
    add_model_args(pr)

    s = sub.add_parser("search", help="tìm phim theo tên")
    s.add_argument("query")
    s.add_argument("-n", type=int, default=10)

    e = sub.add_parser("evaluate", help="huấn luyện + đánh giá trên test, lưu outputs/metrics/<family>.csv")
    e.add_argument("--family", default="all", choices=["all", *rs.FAMILIES])
    return p


def main(argv=None):
    # Console Windows mặc định cp1252 không in được tiếng Việt
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if args.command == "prepare":
        cmd_prepare(args)
        return 0
    exp = load_experiment()
    commands = {"info": cmd_info, "recommend": cmd_recommend, "predict": cmd_predict,
                "search": cmd_search, "evaluate": cmd_evaluate}
    if args.command is None:
        interactive(exp)
        return 0
    try:
        commands[args.command](exp, args)
    except KeyError as e:
        print(f"Lỗi: {e.args[0]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
