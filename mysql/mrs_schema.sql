CREATE DATABASE IF NOT EXISTS movie_recommender_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE movie_recommender_system;

-- 1. Bảng Danh mục Nghề nghiệp
CREATE TABLE occupations (
    occupation_id INT PRIMARY KEY,
    occupation_name VARCHAR(100) NOT NULL
);

-- 2. Bảng Khách hàng
CREATE TABLE customers (
    customer_id INT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    gender VARCHAR(10) DEFAULT NULL,
    age INT DEFAULT NULL,
    occupation_id INT DEFAULT NULL,
    zip_code VARCHAR(20) DEFAULT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    failed_login_count INT NOT NULL DEFAULT 0,
    locked_until DATETIME DEFAULT NULL,
    KEY idx_customers_demo (gender, age),
    FOREIGN KEY (occupation_id) REFERENCES occupations(occupation_id) ON DELETE SET NULL
);

-- 3. Bảng Nhân viên Quản trị (Admin)
CREATE TABLE employees (
    employee_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    failed_login_count INT NOT NULL DEFAULT 0,
    locked_until DATETIME DEFAULT NULL
);

-- 4. Bảng Phim
CREATE TABLE movies (
    movie_id INT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    release_year INT DEFAULT NULL,
    duration_minutes INT DEFAULT 120,
    is_hidden BOOLEAN DEFAULT FALSE,
    employee_id INT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    avg_rating DECIMAL(4,3) DEFAULT NULL,
    rating_count INT NOT NULL DEFAULT 0,
    KEY idx_movies_stats (is_hidden, rating_count),
    KEY idx_movies_year (release_year),
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE SET NULL
);

-- 5. Bảng Thể loại Phim
CREATE TABLE genres (
    genre_id INT PRIMARY KEY AUTO_INCREMENT,
    genre_name VARCHAR(50) NOT NULL UNIQUE
);

-- 6. Bảng Phim - Thể loại
CREATE TABLE movie_genres (
    movie_id INT NOT NULL,
    genre_id INT NOT NULL,
    PRIMARY KEY (movie_id, genre_id),
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genres(genre_id) ON DELETE CASCADE
);

-- 7. Bảng Khách hàng - Thể loại yêu thích
CREATE TABLE customer_genres (
    customer_id INT NOT NULL,
    genre_id INT NOT NULL,
    PRIMARY KEY (customer_id, genre_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genres(genre_id) ON DELETE CASCADE
);

-- 8. Bảng Đánh giá & Bình luận
CREATE TABLE ratings (
    rating_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    movie_id INT NOT NULL,
    rating_score FLOAT NOT NULL,
    comment_text TEXT,
    rating_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE KEY unique_customer_movie (customer_id, movie_id),
    KEY idx_ratings_stats (is_valid, rating_time, rating_score, customer_id, movie_id),
    KEY idx_ratings_movie (movie_id, is_valid, rating_score),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE
);

-- 9. Bảng Kết quả Gợi ý Phim AI
CREATE TABLE recommendations (
    rec_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    movie_id INT NOT NULL,
    predicted_score FLOAT NOT NULL,
    rank_position INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    model_name VARCHAR(30) DEFAULT NULL,
    KEY idx_rec_customer (customer_id, created_at),
    KEY idx_rec_time (created_at),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE
);

-- 10. Bảng Nhật ký Quản trị (Admin Logs)
CREATE TABLE admin_logs (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    employee_id INT NOT NULL,
    action VARCHAR(50) NOT NULL,
    target VARCHAR(255) NOT NULL,
    result VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_logs_time (created_at),
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

-- 11. Bảng Quản lý Mô hình AI (Model Registry)
CREATE TABLE model_registry (
    model_id INT PRIMARY KEY AUTO_INCREMENT,
    model_name VARCHAR(50) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_hash CHAR(64) NOT NULL,
    calibration LONGTEXT NOT NULL,
    n_users INT DEFAULT NULL,
    n_items INT DEFAULT NULL,
    n_ratings INT DEFAULT NULL,
    exported_at DATETIME DEFAULT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    employee_id INT DEFAULT NULL,
    registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 12. Bảng Mã xác thực OTP
CREATE TABLE otp_codes (
    otp_id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(100) NOT NULL,
    otp_code CHAR(6) NOT NULL,
    expired_at DATETIME NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    wrong_count INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_otp_email (email, is_used)
);