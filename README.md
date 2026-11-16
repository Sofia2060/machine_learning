# MovieLens 1M Recommender System
## Hệ Thống Gợi Ý Phim Cá Nhân Hóa (phần mềm CineMatch)

### 1. Tổng quan dự án

Dự án giải quyết bài toán gợi ý phim cá nhân hóa trên tập dữ liệu chuẩn MovieLens 1M (6.040 người dùng, 3.883 bộ phim trong danh mục, trong đó 3.706 phim có ít nhất một lượt đánh giá, và 1.000.209 lượt đánh giá). Dự án gồm hai phần:

1. **Phần nghiên cứu mô hình** (`notebooks/`, `src/`, `main.py`): tiền xử lý dữ liệu, phân tích khám phá, tạo đặc trưng, rồi huấn luyện và so sánh **7 mô hình gợi ý**: Popularity(count), Content-based, ItemKNN, BiasedMF, ImplicitALS, NeuMF, BPR-MF. Bài toán được xem là **xếp hạng Top-N** (không dự đoán số sao): mọi mô hình dùng chung một phép chia train/test 80/20 theo từng người dùng, phim có rating >= 4 là phim "liên quan", và đánh giá bằng Precision/Recall/NDCG/HitRate@10 cùng Coverage, Novelty, Diversity@20. Trên tập test, **NeuMF cho NDCG@10 cao nhất (0,2946)** nên được chọn làm mô hình chính của phần mềm (bảng đầy đủ ở mục 3.5).
2. **Phần mềm CineMatch** (`ui/`, `app/`, `run_app.py`): ứng dụng desktop PyQt6 + MySQL cho hai nhóm người dùng. Khách hàng đăng ký, chọn thể loại yêu thích, chấm điểm phim và nhận gợi ý Top-N kèm "% phù hợp". Quản trị viên xem báo cáo kinh doanh, quản lý dữ liệu, thử nghiệm và huấn luyện lại mô hình. Phần mềm chỉ cần numpy để tính gợi ý (không cần torch): mô hình được xuất thành file `models/main_model/neumf.npz`, và người dùng mới nhận gợi ý cá nhân hóa ngay nhờ **fold-in** mà không phải huấn luyện lại.

---

### 2. Cấu trúc thư mục dự án

```text
machine_learning/
|-- data/                    # không nằm trong git (tự tạo từ data/raw hoặc tải MovieLens 1M)
|   |-- raw/
|   |   |-- movies.dat
|   |   |-- ratings.dat
|   |   |-- users.dat
|   |   `-- README
|   `-- processed/
|       |-- cleaned_users.csv
|       |-- cleaned_movies.csv
|       |-- cleaned_ratings.csv
|       |-- master_dataset.csv
|       |-- featured_dataset.parquet
|       `-- experiment.pkl   # cache phép chia train/test (sinh khi chạy)
|-- notebooks/
|   |-- 01_data_preprocessing.ipynb
|   |-- 02_eda.ipynb
|   |-- 03_feature_engineering.ipynb
|   |-- 04_collaborative_knn.ipynb
|   |-- 05_matrix_factorization.ipynb
|   |-- 06_content_based.ipynb
|   |-- 07_deep_learning.ipynb
|   `-- 08_evaluation_compare.ipynb
|-- models/                  # mô hình đã huấn luyện (*.pkl, không nằm trong git; dùng cho main.py và notebooks)
|   `-- main_model/          # mô hình chính xuất cho phần mềm (neumf.npz + neumf_meta.json), có trong git
|-- outputs/                 # không nằm trong git: metrics/*.csv, figures/*.png (sinh khi chạy)
|-- src/                     # phần nghiên cứu mô hình
|   |-- config.py            # đường dẫn (tương đối theo thư mục dự án) + seed + tỉ lệ chia dữ liệu
|   |-- experiment.py        # nạp dữ liệu, chia train/test, run_model, save_metrics
|   |-- recommender.py       # danh mục mô hình, huấn luyện/lưu/nạp, gợi ý
|   |-- export.py            # xuất NeuMF thành .npz + _meta.json (cần torch)
|   |-- inference.py         # gợi ý từ file .npz, có fold-in cho người dùng mới (chỉ cần numpy)
|   |-- database.py          # ETL: nạp MovieLens vào MySQL
|   |-- data/preprocess.py   # tiền xử lý (logic notebook 01) + master dataset (notebook 02)
|   |-- data/features.py     # feature engineering (logic notebook 03)
|   |-- evaluation/metrics.py
|   `-- models/              # base, baseline, knn_cf, mf, content_based, neural, device
|-- mysql/
|   `-- mrs_schema.sql       # tạo CSDL movie_recommender_system (13 bảng, bảng cha accounts)
|-- ui/                      # phần mềm CineMatch: 10 màn hình + hộp thoại chi tiết phim (.ui, .py do pyuic6 sinh, Ex.py)
|-- images/                  # icon, banner cho giao diện (.ui tham chiếu ../images/)
|-- app/                     # phần xử lý của phần mềm
|   |-- config/              # config.example.json (sao chép thành config.json, không nằm trong git)
|   |-- connectors/          # kết nối MySQL
|   |-- models/              # lớp thực thể Customer, Employee, Movie, Rating
|   |-- dal/                 # truy vấn dữ liệu (accountDAO, customerDAO, movieDAO, ratingDAO, recommendationDAO, ...)
|   |-- services/            # AuthService: đăng nhập, khóa tạm, OTP
|   |-- ml/                  # MovieRecommender: nạp NeuMF, Top-N, % phù hợp, kích hoạt/huấn luyện lại mô hình
|   |-- utils/               # cấu hình, bảo mật, email OTP, bảng, biểu đồ, poster/TMDB, nhập dữ liệu, kiểm tra CSDL
|   |-- setup_database.py    # bổ sung cột/bảng phần mềm cần + đăng ký mô hình
|   `-- download_posters.py  # tải sẵn poster phim từ TMDB vào posters/ (tùy chọn), ghi tmdb_map.csv
|-- posters/                 # không nằm trong git: poster phim (<movie_id>.jpg), tmdb_map.csv, not_found.txt
|-- test/                    # file chạy thử từng màn hình và từng thành phần (test_login.py, test_user.py, ...)
|-- run_app.py               # mở phần mềm
|-- main.py                  # dòng lệnh: chuẩn bị dữ liệu, gợi ý, đánh giá, xuất mô hình
|-- .gitignore
|-- requirements.txt         # môi trường đầy đủ để huấn luyện / notebooks (có torch)
|-- requirements-app.txt     # thư viện tối thiểu để chạy phần mềm (không có torch)
`-- README.md
```

Mọi đường dẫn được tính từ vị trí file `src/config.py`, nên dự án chạy được ở mọi máy và từ mọi thư mục.

**Một nguồn logic dữ liệu duy nhất:** toàn bộ xử lý dữ liệu và tạo đặc trưng nằm trong `src/data/`. Notebooks 01-03, `python main.py prepare` và các mô hình (notebooks 04-08, `main.py`) đều gọi cùng các hàm này và dùng chung một schema cột snake_case (`user_id`, `movie_id`, `rating`, `timestamp`, `datetime`, `title`, `clean_title`, `release_year`, `genres`, ...). Các mô hình đọc dữ liệu sạch từ `data/processed/cleaned_*.csv` (tự tạo từ `data/raw/` nếu chưa có).

Mô tả vai trò các thư mục chính:
- data/raw: Chứa các tệp dữ liệu gốc từ nguồn MovieLens 1M chưa qua chỉnh sửa.
- data/processed: Chứa dữ liệu đã được làm sạch, bảng tổng hợp, tệp đặc trưng dạng Parquet và cache thí nghiệm.
- notebooks: Chứa các sổ tay Jupyter Notebook thực hiện theo quy trình phân tích và huấn luyện mô hình.
- models: Lưu các tệp mô hình đã huấn luyện; `models/main_model/` chứa mô hình chính của phần mềm.
- src: Mã nguồn Python mô-đun hóa: xử lý dữ liệu, các mô hình, đánh giá, xuất mô hình, suy luận bằng numpy và nạp MySQL.
- mysql: Script tạo cơ sở dữ liệu MySQL.
- ui, images: Giao diện phần mềm (Qt Designer) và hình ảnh.
- app: Phần xử lý của phần mềm (kết nối CSDL, truy vấn, nghiệp vụ, mô hình, poster).
- posters: Poster phim tải về từ TMDB (tùy chọn).
- test: File chạy thử từng màn hình.

**Những gì không nằm trong git** (xem `.gitignore`): `data/raw/`, `data/processed/`, `models/*.pkl`, `outputs/`, `posters/`, `app/config/config.json`, `venv/`, `CLAUDE.md`. Riêng `models/main_model/neumf.npz` được commit để cả nhóm dùng ngay sau khi clone.

---

### 3. Chi tiết quy trình các Notebooks

Quy trình kỹ thuật của dự án được tổ chức tuần tự qua 8 tệp sổ tay (01-03: dữ liệu; 04-07: huấn luyện mô hình; 08: so sánh).

#### 3.1. 01_data_preprocessing.ipynb (Tiền xử lý và chuẩn hóa dữ liệu)
- Nhiệm vụ:
  - Đọc dữ liệu từ 3 tệp thô users.dat, movies.dat và ratings.dat với dấu phân cách hai dấu hai chấm và bảng mã latin-1.
  - Chuẩn hóa tên cột cho thống nhất theo quy chuẩn kỹ thuật.
  - Ánh xạ mã nhóm tuổi (Age) sang các dải tuổi rõ ràng (ví dụ: Under 18, 18-24, 25-34).
  - Ánh xạ mã nghề nghiệp (Occupation) từ 0 đến 20 sang danh xưng nghề nghiệp tường minh.
  - Ánh xạ giới tính (Gender) thành nhãn đầy đủ Male và Female.
  - Sử dụng biểu thức chính quy (Regex) trích xuất năm phát hành (release_year) từ tên phim và tạo tên phim sạch (clean_title).
  - Chuyển đổi dấu thời gian Unix sang định dạng ngày giờ chuẩn (datetime).
- Đầu ra:
  - data/processed/cleaned_users.csv
  - data/processed/cleaned_movies.csv
  - data/processed/cleaned_ratings.csv

#### 3.2. 02_eda.ipynb (Phân tích khám phá và trực quan hóa dữ liệu)
- Nhiệm vụ:
  - Hợp nhất 3 bảng dữ liệu đã làm sạch thành một bảng tổng hợp duy nhất (master_df).
  - Phân tích và trực quan hóa 9 biểu đồ kinh doanh:
    - Biểu đồ 1: Phân bố điểm đánh giá và nhận diện hiện tượng thiên lệch tích cực (Positivity Bias).
    - Biểu đồ 2: Cơ cấu nhân khẩu học theo nhóm tuổi và giới tính của người dùng.
    - Biểu đồ 3: Xếp hạng top 10 ngành nghề có tần suất đánh giá cao nhất.
    - Biểu đồ 4: Thống kê số lượng đánh giá theo từng thể loại phim.
    - Biểu đồ 5: Xu hướng số lượng phim phát hành và điểm đánh giá trung bình theo dòng thời gian.
    - Biểu đồ 6: Phân bố tương tác người dùng theo quy luật đuôi dài và nhận diện vấn đề khởi đầu lạnh (Cold-Start).
    - Biểu đồ 7: Phân tích độ phổ biến của phim và hiện tượng thiên lệch bom tấn (Popularity Bias).
    - Biểu đồ 8: Biểu đồ nhiệt thể hiện sự khác biệt về khẩu vị phim giữa các thế hệ người dùng.
    - Biểu đồ 9: Minh họa trực quan độ thưa thớt của ma trận tương tác User-Item (độ thưa toàn cục đạt 95,53%).
  - Trình bày các nhận xét kinh doanh tương ứng dưới từng biểu đồ để đưa trực tiếp vào báo cáo đồ án.
- Đầu ra:
  - data/processed/master_dataset.csv (1.000.209 dòng, dung lượng khoảng 145 MB).
  - Toàn bộ hình ảnh biểu đồ và phân tích kinh doanh trong notebook.

#### 3.3. 03_feature_engineering.ipynb (Kỹ thuật trích xuất đặc trưng nâng cao)
- Nhiệm vụ:
  - Xây dựng các hàm trích xuất đặc trưng mô-đun hóa không gây rò rỉ dữ liệu (Data Leakage).
  - Trích xuất nhóm đặc trưng Người dùng (User Features): số lượng đánh giá, điểm trung bình, độ lệch chuẩn, độ lệch cá nhân (user_bias), mã hóa nhị phân giới tính, mã hóa one-hot nhóm tuổi và nghề nghiệp.
  - Trích xuất nhóm đặc trưng Bộ phim (Movie Features): số lượng đánh giá, điểm trung bình, độ lệch chuẩn, độ lệch phim (movie_bias), năm phát hành, số lượng thể loại và biểu diễn đa thể loại (multi-hot cho 18 thể loại).
  - Trích xuất nhóm đặc trưng Thời gian (Temporal Features): năm, tháng, thứ trong tuần, cờ cuối tuần và tuổi của phim tại thời điểm đánh giá.
  - Trích xuất nhóm đặc trưng Tương tác (Interaction Features): hồ sơ sở thích thể loại của người dùng, điểm tương đồng gu phim (Genre Match Score qua Cosine Similarity), điểm đánh giá trung bình theo nhóm giới tính cho từng phim.
  - Trích xuất nhóm đặc trưng Tiềm ẩn (Latent Features): áp dụng TruncatedSVD rút trích không gian nhúng 10 chiều cho User và Movie, đồng thời tính tích vô hướng tương tác tiềm ẩn (svd_dot_product).
  - Tối ưu hóa bộ nhớ RAM bằng kỹ thuật ép kiểu dữ liệu (Type Downcasting).
  - Kiểm tra tính toàn vẹn (không có giá trị thiếu) và vẽ biểu đồ nhiệt ma trận tương quan giữa các đặc trưng chủ chốt với điểm đánh giá.
- Đầu ra:
  - data/processed/featured_dataset.parquet (1.000.209 dòng x 90 cột đặc trưng, tệp nén Snappy khoảng 37 MB).
- Lưu ý: các mô hình ở notebooks 04-08 học trực tiếp từ ma trận đánh giá, không đọc tệp đặc trưng này.

#### 3.4. 04 - 07: Huấn luyện các nhóm mô hình
Dự án so sánh 7 mô hình: Popularity(count), Content-based, ItemKNN, BiasedMF, ImplicitALS, NeuMF, BPR-MF. Mọi notebook dùng chung `src.experiment.load_experiment()`: cùng dữ liệu, cùng phép chia train/test 80/20 theo từng người dùng, cùng seed (42). Siêu tham số được dò trên tập validation (10% tách từ train) theo tiêu chí NDCG@10 (`src.experiment.validate`); kết quả trên test lưu vào `outputs/metrics/<nhóm>.csv`.
- 04_collaborative_knn.ipynb: ItemKNN (cosine / Pearson, dò k).
- 05_matrix_factorization.ipynb: BiasedMF (Funk SVD), Implicit ALS.
- 06_content_based.ipynb: Content-based (thể loại + TF-IDF tiêu đề + thập niên).
- 07_deep_learning.ipynb: NeuMF, BPR-MF (PyTorch, tự dùng GPU nếu có).
- Mọi mô hình trừ Popularity (ItemKNN, BiasedMF, Implicit ALS, Content-based, NeuMF, BPR-MF) tính toán bằng PyTorch và tự dùng GPU CUDA nếu có; truyền `device="cpu"` vào hàm khởi tạo để ép chạy CPU.

#### 3.5. 08_evaluation_compare.ipynb (So sánh toàn bộ mô hình)
- Gộp `outputs/metrics/{baseline,content,knn,mf,deep}.csv`, so sánh Precision@10, Recall@10, NDCG@10, HitRate@10, Coverage@20, Novelty@20, Diversity@20.
- Bảng `baseline.csv` (Popularity(count)) không có notebook riêng, sinh bằng `python main.py evaluate --family baseline`.
- Phân tích cold-start: Recall@20 theo mức độ phổ biến của phim cho cả 7 mô hình.
- Kết quả trên tập test (lần chạy gần nhất của nhóm, tính tại K=10; sắp theo NDCG@10):

| Mô hình | Precision@10 | Recall@10 | NDCG@10 | HitRate@10 |
|---|---|---|---|---|
| NeuMF (f=128) | 0,2477 | 0,1693 | **0,2946** | 0,8135 |
| BPR-MF (f=32) | 0,2293 | 0,1527 | 0,2711 | 0,7829 |
| ImplicitALS (f=32) | 0,2054 | 0,1690 | 0,2502 | 0,8220 |
| Popularity (count) | 0,1484 | 0,0862 | 0,1735 | 0,6064 |
| ContentBased (genres + title) | 0,0715 | 0,0441 | 0,0875 | 0,4269 |
| ItemKNN (k=5, Pearson) | 0,0581 | 0,0487 | 0,0668 | 0,4161 |
| BiasedMF (f=200) | 0,0541 | 0,0314 | 0,0582 | 0,3441 |

  BiasedMF và ItemKNN là mô hình dự đoán điểm 1-5 nên xếp thấp khi dùng để xếp hạng Top-N; chúng được giữ lại để so sánh. Con số có thể thay đổi nhẹ khi chạy lại trên máy khác (GPU/CPU).

---

### 4. Hướng dẫn cài đặt và chạy dự án

Dự án có hai cách dùng, cài đặt khác nhau:
- **Chỉ chạy phần mềm CineMatch**: đi thẳng tới Bước 7 (cần Python >= 3.10, MySQL, `pip install -r requirements-app.txt`).
- **Chạy lại phần nghiên cứu** (notebooks, `main.py`, huấn luyện): làm từ Bước 1.

Dữ liệu MovieLens 1M (`movies.dat`, `ratings.dat`, `users.dat`) cần đặt ở `data/raw/` (tải từ https://grouplens.org/datasets/movielens/1m/).

#### Bước 1: Mở Terminal và tạo môi trường ảo Python

Trên hệ điều hành Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Trên hệ điều hành Linux hoặc macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

#### Bước 2: Cài đặt các thư viện cần thiết
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
`requirements.txt` là môi trường đầy đủ để huấn luyện (có `torch`, `scikit-learn`, `scipy`, `jupyterlab`, ...). Chỉ chạy phần mềm thì dùng `requirements-app.txt` (xem Bước 7).

#### Bước 3: Khởi chạy môi trường Jupyter Lab
```bash
jupyter lab
```

#### Bước 4: Thực thi các notebook theo đúng thứ tự
Thực hiện chạy lần lượt các tệp notebook theo trình tự sau:
1. Mở và chạy notebooks/01_data_preprocessing.ipynb để tiền xử lý và sinh 3 tệp CSV sạch.
2. Mở và chạy notebooks/02_eda.ipynb để tạo master_dataset.csv và quan sát các biểu đồ phân tích kinh doanh.
3. Mở và chạy notebooks/03_feature_engineering.ipynb để tạo tệp đặc trưng featured_dataset.parquet.
4. Chạy lần lượt notebooks/04 đến 07 để huấn luyện và đánh giá từng nhóm mô hình.
5. Chạy `python main.py evaluate --family baseline` để tạo bảng baseline, rồi chạy notebooks/08_evaluation_compare.ipynb.

#### Bước 5: Chạy dòng lệnh (main.py)
```bash
python main.py prepare                          # tạo cleaned_*.csv, master_dataset.csv, featured_dataset.parquet (= notebooks 01-03)
python main.py prepare --skip-features          # như trên nhưng bỏ bước tạo đặc trưng (notebook 03)
python main.py                                  # menu tương tác
python main.py info                             # thống kê dữ liệu, danh sách mô hình
python main.py recommend --user 1 -k 10         # gợi ý Top-10 (mặc định mô hình neumf)
python main.py recommend --user 1 --model biased_mf --retrain
python main.py predict --user 1 --movie 2571    # độ phù hợp của user với phim (NeuMF: xác suất thích phim, %)
python main.py search "matrix"                  # tìm MovieID theo tên
python main.py evaluate --family all            # đánh giá mọi nhóm mô hình -> outputs/metrics/
python main.py export                           # xuất NeuMF cho phần mềm -> models/main_model/neumf.npz + neumf_meta.json
```
Mô hình có thể chọn bằng `--model`: `popularity`, `content`, `item_knn`, `biased_mf`, `implicit_als`, `neumf`, `bpr_mf`. Nhóm đánh giá (`--family`): `baseline`, `content`, `knn`, `mf`, `deep`, `all`.

Lần đầu chạy, phép chia train/test được cache ở `data/processed/experiment.pkl` và mô hình được lưu ở `models/<tên>.pkl` (mỗi file khoảng 96 MB); các lần sau nạp lại nên nhanh hơn. Khi dữ liệu sạch được tạo lại (chạy lại notebook 01 hoặc `prepare`), cache và mô hình tự được tạo lại; dùng `--retrain` để ép huấn luyện lại.

#### Bước 6: Nhúng mô hình vào phần mềm (PyQt6 + MySQL)
Mô hình chính của phần mềm là **NeuMF** (NDCG@10 cao nhất, xem mục 3.5). Phần mềm **không cần torch**: mô hình được xuất thành file numpy và tính điểm bằng numpy.

Mô hình đã xuất sẵn nằm trong repo (`models/main_model/neumf.npz` khoảng 9 MB + `neumf_meta.json`, học trên toàn bộ 1 triệu rating), nên người làm giao diện chỉ cần clone repo và cài `pip install -r requirements-app.txt`.

1. Xuất lại mô hình khi cần (trên máy dev có torch, có GPU càng nhanh, khoảng 1 phút), rồi commit file mới:
   ```bash
   python main.py export                 # học trên toàn bộ rating -> models/main_model/neumf.npz + neumf_meta.json
   python main.py export --data train    # chỉ học trên tập train (đúng mô hình đã đánh giá trong notebooks)
   ```
   Mã băm SHA-256 của hai file này được lưu trong bảng `model_registry`; phần mềm từ chối nạp file có mã băm không khớp (xem `python app/setup_database.py --register` ở Bước 7).
2. Trong phần mềm, lớp `app/ml/MovieRecommender.py` bọc `src/inference.py` và là nơi duy nhất giao diện gọi để lấy gợi ý (`recommendTopN`, `compatibility`, `fallbackMovies`, `activateModel`, `retrainModel`). Dùng trực tiếp `NeuMFRecommender` (nạp **một lần** khi khởi động, khoảng 0,3 giây; mỗi lần `recommend` khoảng 10 ms trên CPU):
   ```python
   from src.inference import NeuMFRecommender

   rec = NeuMFRecommender("models/main_model/neumf.npz")
   cur.execute("SELECT movie_id, rating_score FROM ratings WHERE customer_id = %s AND is_valid = 1", (cid,))
   ratings = cur.fetchall()                       # [(movie_id, số sao), ...] – đúng 2 cột
   if rec.is_personalized(cid):                   # khách hàng đã có trong mô hình (MovieLens 1-6040)
       top = rec.recommend(cid, k=10, seen=[m for m, _ in ratings])
   else:                                          # khách hàng mới: fold-in từ chính các đánh giá của họ
       top = rec.recommend_from_ratings(ratings, k=10)
   # top = [(movie_id, điểm), ...] giảm dần, đã bỏ các phim đã chấm
   ```
   - **Fold-in:** giữ nguyên trọng số đã học, chỉ học vector của khách hàng từ các phim họ chấm >= 4 sao (khoảng 0,3 giây, nên gọi trong `QThread`). Khách hàng chưa chấm phim nào >= 4 sao thì `recommend_from_ratings` gợi ý theo độ phổ biến; trong phần mềm, màn hình chính khi đó hiện phim nổi bật theo thể loại yêu thích (`MovieRecommender.fallbackMovies`).
   - Danh sách phim đã chấm lấy **trực tiếp từ MySQL** nên phim khách hàng vừa chấm trên giao diện sẽ không bị gợi ý lại; phim bị ẩn (`is_hidden`) cũng bị loại.
   - **ID trong MySQL phải khớp với mô hình** (sai thì không báo lỗi mà gợi ý sai): `movie_id` phải đúng MovieID của MovieLens; mô hình đã có khách hàng 1-6040, nên khách hàng đăng ký mới phải có `customer_id` **từ 6041 trở đi**. Phần mềm tự cấp mã này (`customer_id` không tự tăng mà được cấp bằng giá trị lớn nhất + 1, xem `app/dal/customerDAO.py`) nên sau khi nạp 6.040 khách hàng bằng `src/database.py` thì khách hàng đầu tiên đăng ký sẽ là 6041. Nếu tự thêm khách hàng bằng cách khác, đừng dùng lại mã 1-6040: phần mềm sẽ đưa ra gợi ý của người dùng MovieLens có cùng mã.
   - Phim thêm vào CSDL sau lần xuất chưa được gợi ý. Xuất lại mô hình định kỳ (hoặc dùng chức năng huấn luyện lại ở màn hình "Hiệu quả gợi ý") để cập nhật cả khách hàng mới lẫn phim mới.
   - Điểm NeuMF là điểm xếp hạng (logit), không phải số sao 1-5. Phần mềm hiển thị `sigmoid(điểm)` thành "% phù hợp" (xác suất mô hình dự đoán khách hàng thích phim); phần mềm không dự đoán số sao.
   - Truy vấn MySQL nên chạy trong `QThread` để giao diện không bị đứng.
3. Thư viện cho phần mềm: `requirements-app.txt` (`numpy` cho `src.inference`, `PyQt6`, `mysql-connector-python`, `pandas`, `matplotlib`, `sqlalchemy` + `pymysql` cho `src/database.py`). Không cần `torch`, `scipy`, `scikit-learn` (chỉ cần `torch` nếu dùng chức năng huấn luyện lại). Khi phát hành, đóng gói phần mềm (ví dụ bằng PyInstaller) kèm thư mục `models/main_model/` (`neumf.npz` và `neumf_meta.json`), rồi nén cả thư mục thành zip. Khi đóng gói, nên tính đường dẫn tới `neumf.npz` theo thư mục của file chạy (ví dụ `Path(sys.executable).parent` hoặc `sys._MEIPASS` với PyInstaller) thay vì đường dẫn tương đối, và nhớ kèm cả file `_meta.json`.

#### Bước 7: Chạy phần mềm CineMatch (PyQt6 + MySQL)
Cần MySQL đang chạy và Python >= 3.10. Chạy các lệnh ở thư mục gốc dự án:
```bash
pip install -r requirements-app.txt
mysql -u root -p < mysql/mrs_schema.sql                   # 1. tạo CSDL movie_recommender_system
python src/database.py                                    # 2. nạp dữ liệu (cần data/processed/cleaned_*.csv từ notebook 01)
copy app\config\config.example.json app\config\config.json   # 3. sửa mục "database" (mật khẩu MySQL); macOS/Linux dùng cp
python run_app.py                                         # 4. mở phần mềm
python app/download_posters.py                            # 5. (tùy chọn) tải sẵn poster phim, xem mục "Poster phim" bên dưới
```
- `src/database.py` đọc mật khẩu MySQL từ biến môi trường `DB_PASS` (cũng có `DB_USER`, `DB_HOST`, `DB_PORT`, `DB_NAME`), hoặc sửa trực tiếp trong file. Script xóa dữ liệu cũ trên 13 bảng rồi nạp lại, nên chỉ chạy khi tạo mới CSDL.
- Lần đầu mở, phần mềm kiểm tra CSDL (đủ 13 bảng theo `mysql/mrs_schema.sql`), tính điểm trung bình từng phim và đăng ký mô hình `models/main_model/neumf.npz`. Có thể chạy riêng bước này: `python app/setup_database.py` (thêm `--register` để đăng ký lại tệp mô hình, ví dụ sau khi vừa clone/pull bản mô hình mới và mã băm khác bản đã đăng ký). CSDL tạo từ bản schema cũ (chưa có bảng `accounts`) cần tạo lại bằng `mysql/mrs_schema.sql` rồi `python src/database.py`.
- **Tài khoản mẫu:** `admin` / `123456` (quản trị), `user_1` … `user_6040` / `123456` (khách hàng), hoặc tự đăng ký tài khoản khách hàng mới. Mật khẩu SHA-256 của dữ liệu mẫu được băm lại bằng PBKDF2 có salt ở lần đăng nhập đúng đầu tiên. Đăng nhập sai quá số lần cho phép thì tài khoản bị khóa tạm; phiên tự đăng xuất khi không hoạt động.
- **Các màn hình:**
  - Dùng chung: Đăng nhập, Đăng ký tài khoản, Quên mật khẩu (xác minh OTP) rồi Đặt lại mật khẩu.
  - Khách hàng: Thể loại yêu thích (chọn ít nhất 3 thể loại), màn hình chính "Gợi ý phim cá nhân hóa" (Top-5/Top-10 kèm % phù hợp, tìm kiếm và sắp xếp phim, chấm điểm và xem lịch sử đánh giá của mình) và hộp thoại Chi tiết phim.
  - Quản trị viên: Tổng quan kinh doanh (biểu đồ kèm nhận xét), Quản lý dữ liệu (quản lý phim, khách hàng, đánh giá và nhập `movies.dat`, `users.dat`, `ratings.dat` của MovieLens chạy nền), Thử nghiệm mô hình (nhập một `customer_id` để xem Top-N của mô hình đang dùng, đối chiếu với các phim khách hàng đó đã đánh giá cao) và Hiệu quả gợi ý (thống kê hiệu quả gợi ý, chọn phiên bản mô hình hoạt động, huấn luyện lại và đăng ký mô hình mới).
- **Cấu hình `app/config/config.json`** (sao chép từ `config.example.json`, không đưa lên git):
  - `database`: máy chủ, cổng, tên CSDL, tài khoản và mật khẩu MySQL.
  - `recommendation`: số phim gợi ý mặc định (`top_n_default`, `top_n_options`), `featured_min_ratings`, đường dẫn mô hình `model_path`.
  - `security`: số lần lặp PBKDF2, số lần đăng nhập sai tối đa và thời gian khóa, thời gian tự đăng xuất, thời hạn và số lần nhập sai OTP.
  - `email`: `sender_email` và `app_password` (mật khẩu ứng dụng Gmail 16 ký tự) để gửi OTP. Để trống thì chạy chế độ DEMO: mã OTP hiện ngay trên hộp thoại thay vì gửi email.
  - `tmdb`: `api_key` để lấy poster (xem bên dưới). Để trống thì giao diện dùng ảnh bìa tự vẽ.
  - `paths`: `dataset_dir`, `poster_dir` (mặc định `posters`).
- **Poster phim** (tùy chọn): phần mềm đọc poster từ `posters/<movie_id>.jpg`; phim chưa có file thì hiện ảnh bìa tự vẽ theo thể loại. Thư mục `posters/` không nằm trong git (khoảng 170 MB), mỗi máy tự tải một lần:
  1. Đăng ký khóa API miễn phí tại https://www.themoviedb.org/settings/api, dán vào `app/config/config.json` mục `tmdb` > `api_key` (hoặc đặt biến môi trường `TMDB_API_KEY`, hoặc truyền `--key`). Khóa v3 (tối đa 40 ký tự) và token v4 đều dùng được.
  2. `python app/download_posters.py` tải poster cho mọi phim trong `data/processed/cleaned_movies.csv` (4 luồng, khoảng 25 phút; chạy lại sẽ bỏ qua phim đã có và tiếp tục phần còn dang dở). Nếu `api.themoviedb.org` bị chặn (một số mạng ở Việt Nam), thêm `--api-url https://api.tmdb.org/3`.
  3. Một phim có thể trùng tên với nhiều phim khác trên TMDB, nên script chấm điểm từng ứng viên (năm phát hành, độ giống tên, số lượt bình chọn) thay vì lấy kết quả đầu tiên. Kết quả ghép từng phim nằm trong `posters/tmdb_map.csv` (cột `status`: `ok`, `review` là ghép được nhưng nên xem lại, `rejected` là bị loại nên không tải ảnh). Phim không có poster hợp lệ ghi trong `posters/not_found.txt`.
  4. Các tùy chọn khác: `--no-images` (chỉ ghép và ghi `poster_path`, không tải ảnh), `--retry-missing` (tìm lại các phim đã ghi là không có poster), `--force` (tìm và chấm điểm lại tất cả), `--limit N` (thử với N phim), `--size` (cỡ ảnh: `w92`, `w154`, `w185`, `w342`, `w500`, `w780`, `original`; mặc định `w342`, cùng cỡ phần mềm dùng), `--workers N`. Xem đầu file `app/download_posters.py` để biết chi tiết.
  - Không tải sẵn cũng được: nếu có khóa API trong `config.json`, phần mềm tự tải poster của từng phim ở lần đầu hiển thị (cách này dùng kết quả tìm đầu tiên nên có thể ghép nhầm phim trùng tên). Khóa API không được đưa lên git (`config.json` đã nằm trong `.gitignore`). Dữ liệu từ TMDB cần ghi nguồn khi phát hành phần mềm: "This product uses the TMDB API but is not endorsed or certified by TMDB."
- Chạy thử từng màn hình: các file trong `test/` (vd `python test/test_user.py`, `python test/test_admin_dashboard.py`, `python test/test_model_test.py`); các file này mở thẳng màn hình, bỏ qua bước đăng nhập. `python test/test_recommender.py` thử riêng phần gợi ý.
- Sửa giao diện: mở file `.ui` trong `ui/` bằng Qt Designer, rồi chạy `pyuic6 XxxMainWindow.ui -o XxxMainWindow.py` trong thư mục `ui`.
