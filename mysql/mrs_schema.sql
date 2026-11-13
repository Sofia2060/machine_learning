CREATE DATABASE movie_recommender_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE movie_recommender_system;

-- 1. Bảng Danh mục Nghề nghiệp (21 ngành nghề theo MovieLens)
CREATE TABLE occupations (
    occupation_id INT PRIMARY KEY,
    occupation_name VARCHAR(100) NOT NULL
);

-- 2. Bảng Khách hàng (6.040 users)
CREATE TABLE customers (
    customer_id INT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    gender VARCHAR(10),
    age INT,
    occupation_id INT,
    zip_code VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 4. Bảng Phim (~3.900 phim)
CREATE TABLE movies (
    movie_id INT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    release_year INT,
    duration_minutes INT DEFAULT 120,
    is_hidden BOOLEAN DEFAULT FALSE,
    employee_id INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE SET NULL
);

-- 5. Bảng Thể loại Phim
CREATE TABLE genres (
    genre_id INT PRIMARY KEY AUTO_INCREMENT,
    genre_name VARCHAR(50) NOT NULL UNIQUE
);

-- 6. Bảng Phim - Thể loại (Bảng trung gian n-m)
CREATE TABLE movie_genres (
    movie_id INT NOT NULL,
    genre_id INT NOT NULL,
    PRIMARY KEY (movie_id, genre_id),
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genres(genre_id) ON DELETE CASCADE
);

-- 7. Bảng Đánh giá & Bình luận (~1.000.000 dòng ratings)
CREATE TABLE ratings (
    rating_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    movie_id INT NOT NULL,
    rating_score FLOAT NOT NULL,
    comment_text TEXT,
    rating_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_customer_movie (customer_id, movie_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE
);

-- 8. Bảng Kết quả Gợi ý Phim Top-N AI
CREATE TABLE recommendations (
    rec_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT NOT NULL,
    movie_id INT NOT NULL,
    predicted_score FLOAT NOT NULL,
    rank_position INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE
);