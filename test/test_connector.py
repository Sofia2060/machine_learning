import os
import sys
# Chạy được cả khi IDE không thêm thư mục gốc dự án vào PYTHONPATH (vd VS Code)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app.connectors.connector import Connector

conn=Connector()
conn.connect()
sql="select customer_id, username, full_name, gender, age, occupation_id from customers limit 5"
df=conn.queryDataset(sql)
print(df)
sql2="select * from movies where title like %s"
val=("%Star Wars%",)
df2=conn.queryDataset(sql2,val)
print(df2)
sql3="select * from ratings where customer_id=%s"
val=(1,)
df3=conn.queryDataset(sql3,val)
print(df3)
sql4="select count(*) as total from ratings"
df4=conn.queryDataset(sql4)
print(df4)
conn.disconnect()
