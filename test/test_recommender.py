import os
import sys
# Chạy được cả khi IDE không thêm thư mục gốc dự án vào PYTHONPATH (vd VS Code)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
pd.set_option("display.width",200)
pd.set_option("display.max_columns",10)

from app.ml.MovieRecommender import MovieRecommender

ret=MovieRecommender.loadModel()
print("Đã nạp mô hình:",ret,MovieRecommender.model_name,MovieRecommender.last_error)
print("Dự báo user 1 - phim 2571 (The Matrix) =",MovieRecommender.predictRating(1,2571),"sao")
df=MovieRecommender.recommendTopN(1,10,save=False)
print(df[["rank_no","movie_id","title","predicted_rating"]])
print("User 6041 (đăng ký mới) có trong mô hình?",MovieRecommender.isKnownUser(6041))
print("User 6041 đã cá nhân hóa được (fold-in từ các phim chấm >= 4 sao)?",MovieRecommender.isPersonalized(6041))
