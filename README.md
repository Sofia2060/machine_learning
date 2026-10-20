# MovieLens 1M Recommender System
## Hệ Thống Gợi Ý Phim Cá Nhân Hóa

### 1. Tổng quan dự án

Dự án MovieLens 1M Recommender System tập trung giải quyết bài toán gợi ý phim cá nhân hóa cho người dùng dựa trên tập dữ liệu chuẩn MovieLens 1M (bao gồm 6.040 người dùng, 3.706 bộ phim và 1.000.209 lượt đánh giá).

Mục tiêu chính của dự án là xây dựng một hệ thống gợi ý lai kết hợp giữa phương pháp Lọc cộng tác phân rã ma trận (Matrix Factorization như SVD, SVD++) và các mô hình Học máy dựa trên cây quyết định tăng cường (GBDT như LightGBM, XGBoost). Hệ thống giúp xử lý hiệu quả hiện tượng dữ liệu ma trận tương tác thưa thớt, đồng thời nâng cao độ chính xác dự báo và chất lượng danh sách phim khuyến nghị đến từng khách hàng.

---

### 2. Cấu trúc thư mục dự án

```text
movie-recommender-system/
|-- data/
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
|       `-- featured_dataset.parquet
|-- notebooks/
|   |-- 01_data_preprocessing.ipynb
|   |-- 02_eda.ipynb
|   |-- 03_feature_engineering.ipynb
|   |-- 04_collaborative_knn.ipynb
|   |-- 05_matrix_factorization.ipynb
|   |-- 06_content_based.ipynb
|   |-- 07_deep_learning.ipynb
|   `-- 08_evaluation_compare.ipynb
|-- models/                  # mô hình đã huấn luyện (*.pkl, dùng cho main.py và notebooks)
|   `-- main_model/          # mô hình chính xuất cho phần mềm (neumf.npz + neumf_meta.json)
|-- outputs/                 # metrics/*.csv, figures/*.png (sinh khi chạy)
|-- src/
|   |-- config.py            # đường dẫn (tương đối theo thư mục dự án) + seed
|   |-- experiment.py        # nạp dữ liệu, chia train/test, run_model, save_metrics
|   |-- recommender.py       # danh mục mô hình, huấn luyện/lưu/nạp, gợi ý
|   |-- export.py            # xuất NeuMF thành .npz + _meta.json (cần torch)
|   |-- inference.py         # gợi ý cho phần mềm từ file .npz (chỉ cần numpy)
|   |-- database.py
|   |-- data/preprocess.py   # tiền xử lý (logic notebook 01) + master dataset (notebook 02)
|   |-- data/features.py     # feature engineering (logic notebook 03)
|   |-- evaluation/metrics.py
|   `-- models/              # baseline, knn_cf, mf, content_based, neural
|-- main.py                  # ứng dụng chính
|-- .gitignore
|-- requirements.txt
`-- README.md
```

Mọi đường dẫn được tính từ vị trí file `src/config.py`, nên dự án chạy được ở mọi máy và từ mọi thư mục.

**Một nguồn logic dữ liệu duy nhất:** toàn bộ xử lý dữ liệu và tạo đặc trưng nằm trong `src/data/`. Notebooks 01-03, `python main.py prepare` và các mô hình (notebooks 04-08, `main.py`) đều gọi cùng các hàm này và dùng chung một schema cột snake_case (`user_id`, `movie_id`, `rating`, `timestamp`, `datetime`, `title`, `clean_title`, `release_year`, `genres`, ...). Các mô hình đọc dữ liệu sạch từ `data/processed/cleaned_*.csv` (tự tạo từ `data/raw/` nếu chưa có).

Mô tả vai trò các thư mục chính:
- data/raw: Chứa các tệp dữ liệu gốc từ nguồn MovieLens 1M chưa qua chỉnh sửa.
- data/processed: Chứa dữ liệu đã được làm sạch, bảng tổng hợp và tệp đặc trưng dạng Parquet.
- notebooks: Chứa toàn bộ các sổ tay Jupyter Notebook thực hiện theo quy trình phân tích và huấn luyện mô hình.
- models: Lưu trữ các tệp mô hình đã huấn luyện phục vụ cho việc suy luận dự báo.
- src: Chứa mã nguồn Python mô-đun hóa kết nối cơ sở dữ liệu MySQL và bộ máy gợi ý.
- ui: Chứa mã nguồn giao diện tương tác người dùng và bảng điều khiển quản trị.

---

### 3. Chi tiết quy trình các Notebooks

Quy trình kỹ thuật của dự án được tổ chức tuần tự qua 5 tệp sổ tay:

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
  - data/processed/master_dataset.csv (1.000.209 dòng, dung lượng 145 MB).
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
  - data/processed/featured_dataset.parquet (1.000.209 dòng x 90 cột đặc trưng, tệp nén Snappy 35,4 MB).

#### 3.4. 04 - 07: Huấn luyện các nhóm mô hình
Dự án so sánh 7 mô hình: Popularity(count), Content-based, ItemKNN, BiasedMF, ImplicitALS, NeuMF, BPR-MF. Mọi notebook dùng chung `src.experiment.load_experiment()`: cùng dữ liệu, cùng phép chia train/test 80/20 theo từng người dùng, cùng seed. Siêu tham số được dò trên tập validation tách từ train theo tiêu chí NDCG@10 (`src.experiment.validate`); kết quả trên test lưu vào `outputs/metrics/<nhóm>.csv`.
- 04_collaborative_knn.ipynb: ItemKNN (cosine / Pearson, dò k).
- 05_matrix_factorization.ipynb: BiasedMF (Funk SVD), Implicit ALS.
- 06_content_based.ipynb: Content-based (thể loại + TF-IDF tiêu đề + thập niên).
- 07_deep_learning.ipynb: NeuMF, BPR-MF (PyTorch, tự dùng GPU nếu có).
- Mọi mô hình trừ Popularity (ItemKNN, BiasedMF, Implicit ALS, Content-based, NeuMF, BPR-MF) tính toán bằng PyTorch và tự dùng GPU CUDA nếu có; truyền `device="cpu"` vào hàm khởi tạo để ép chạy CPU.

#### 3.5. 08_evaluation_compare.ipynb (So sánh toàn bộ mô hình)
- Gộp `outputs/metrics/{baseline,content,knn,mf,deep}.csv`, so sánh Precision@10, Recall@10, NDCG@10, HitRate@10, Coverage@20, Novelty@20, Diversity@20.
- Bảng `baseline.csv` (Popularity(count)) không có notebook riêng, sinh bằng `python main.py evaluate --family baseline`.
- Phân tích cold-start: Recall@20 theo mức độ phổ biến của phim cho cả 7 mô hình.

---

### 4. Hướng dẫn cài đặt và chạy dự án

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

#### Bước 5: Chạy ứng dụng chính (main.py)
```bash
python main.py prepare                          # tạo cleaned_*.csv, master_dataset.csv, featured_dataset.parquet (= notebooks 01-03)
python main.py                                  # menu tương tác
python main.py info                             # thống kê dữ liệu, danh sách mô hình
python main.py recommend --user 1 -k 10         # gợi ý Top-10 (mặc định mô hình neumf)
python main.py recommend --user 1 --model biased_mf --retrain
python main.py predict --user 1 --movie 2571    # dự đoán rating
python main.py search "matrix"                  # tìm MovieID theo tên
python main.py evaluate --family all            # đánh giá mọi nhóm mô hình -> outputs/metrics/
python main.py export                          # xuất NeuMF cho phần mềm -> models/main_model/neumf.npz + neumf_meta.json
```
Lần đầu chạy, phép chia train/test được cache ở `data/processed/experiment.pkl` và mô hình được lưu ở `models/<tên>.pkl`; các lần sau nạp lại nên nhanh hơn. Khi dữ liệu sạch được tạo lại (chạy lại notebook 01 hoặc `prepare`), cache và mô hình tự được tạo lại; dùng `--retrain` để ép huấn luyện lại.

#### Bước 6: Nhúng mô hình vào phần mềm (PyQt6 + MySQL)
Mô hình chính của phần mềm là **NeuMF** (NDCG@10 cao nhất, xem notebook 08). Phần mềm **không cần torch**: mô hình được xuất thành file numpy và tính điểm bằng numpy.

1. Xuất mô hình (trên máy dev có torch, có GPU càng nhanh, khoảng 1 phút):
   ```bash
   python main.py export                 # học trên toàn bộ rating -> models/main_model/neumf.npz (~9 MB) + neumf_meta.json
   python main.py export --data train    # chỉ học trên tập train (đúng mô hình đã đánh giá trong notebooks)
   ```
2. Trong phần mềm, nạp mô hình **một lần** khi khởi động rồi gọi `recommend` (mỗi lần khoảng 4 ms trên CPU):
   ```python
   from src.inference import NeuMFRecommender

   rec = NeuMFRecommender("models/main_model/neumf.npz")
   cur.execute("SELECT movie_id FROM ratings WHERE user_id = %s", (uid,))   # cur: cursor MySQL của phần mềm
   seen = [row[0] for row in cur.fetchall()]
   top = rec.recommend(uid, k=10, seen=seen)     # [(movie_id, điểm), ...] giảm dần, đã bỏ phim user đã chấm
   rec.is_personalized(uid)                      # False -> user mới, đang gợi ý theo độ phổ biến
   ```
   - Danh sách phim đã chấm lấy **trực tiếp từ MySQL** nên phim user vừa chấm trên giao diện sẽ không bị gợi ý lại.
   - User đăng ký sau lần xuất gần nhất chưa có trong mô hình: phần mềm tự gợi ý theo độ phổ biến. Phim thêm vào CSDL sau lần xuất cũng chưa được gợi ý. Xuất lại mô hình định kỳ để cập nhật.
   - Điểm NeuMF là điểm xếp hạng (logit), không phải số sao 1–5.
   - Truy vấn MySQL nên chạy trong `QThread` để giao diện không bị đứng; `recommend` đủ nhanh để gọi ở luồng chính.
3. Thư viện cho phần mềm: `numpy` (cho `src.inference`), `PyQt6` và thư viện kết nối MySQL (ví dụ `mysql-connector-python` hoặc `PyMySQL`). Không cần `torch`, `scipy`, `scikit-learn`. Khi phát hành, đóng gói phần mềm (ví dụ bằng PyInstaller) kèm thư mục `models/main_model/` (`neumf.npz` và `neumf_meta.json`), rồi nén cả thư mục thành zip. Khi đóng gói, nên tính đường dẫn tới `neumf.npz` theo thư mục của file chạy (ví dụ `Path(sys.executable).parent` hoặc `sys._MEIPASS` với PyInstaller) thay vì đường dẫn tương đối, và nhớ kèm cả file `_meta.json`.
