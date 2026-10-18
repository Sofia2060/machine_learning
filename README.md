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
|   |-- 04_model_training.ipynb
|   `-- 05_evaluation.ipynb
|-- models/
|-- src/
|   |-- database.py
|   `-- recommender.py
|-- ui/
|-- .gitignore
|-- requirements.txt
`-- README.md
```

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

#### 3.4. 04_model_training.ipynb (Huấn luyện các mô hình học máy)
- Nhiệm vụ:
  - Phân chia tập dữ liệu thành tập Huấn luyện (Train) và tập Kiểm thử (Test) theo tỷ lệ 80/20 có phân tầng theo người dùng.
  - Huấn luyện nhóm mô hình mốc so sánh (Baseline): Global Mean, Popularity-based, Item-based Collaborative Filtering.
  - Huấn luyện nhóm mô hình Phân rã Ma trận: SVD (Funk SVD) và SVD++ có tính đến thông tin tương tác ẩn.
  - Huấn luyện nhóm mô hình Học máy dạng cây quyết định tăng cường: LightGBM Regressor và XGBoost Regressor trên không gian 90 đặc trưng tổng hợp.
  - Tinh chỉnh siêu tham số và lưu trữ các tệp mô hình tốt nhất vào thư mục models/.
- Đầu ra:
  - Các tệp mô hình đã huấn luyện (.pkl, .joblib) lưu trữ trong thư mục models/.

#### 3.5. 05_evaluation.ipynb (Đánh giá và so sánh hiệu năng)
- Nhiệm vụ:
  - Đo lường sai số dự báo điểm đánh giá thông qua các chỉ số: Root Mean Squared Error (RMSE) và Mean Absolute Error (MAE).
  - Đo lường chất lượng danh sách gợi ý Top-N (Top 10 phim đề xuất) thông qua các chỉ số xếp hạng: Precision@K, Recall@K và Normalized Discounted Cumulative Gain (NDCG@K).
  - Lập bảng so sánh đối đầu giữa các mô hình để chứng minh tính ưu việt của giải pháp gợi ý lai.
  - Trực quan hóa kết quả so sánh và sinh danh sách gợi ý phim thực tế cho các nhóm người dùng mẫu.
- Đầu ra:
  - Bảng tổng hợp các chỉ số đánh giá thực nghiệm phục vụ báo cáo.
  - Biểu đồ so sánh hiệu năng giữa các thuật toán.

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
4. Mở và chạy notebooks/04_model_training.ipynb để huấn luyện các thuật toán gợi ý.
5. Mở và chạy notebooks/05_evaluation.ipynb để kiểm tra các chỉ số đánh giá và sinh danh sách khuyến nghị.
