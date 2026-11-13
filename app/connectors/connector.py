import mysql.connector
import pandas as pd

from app.utils.ConfigUtil import ConfigUtil

USE_CONFIG = "config"


class Connector:
    # Thông tin kết nối mặc định lấy từ config/config.json (NFR-20: không ghi cứng trong mã nguồn)
    def __init__(self,server=None,port=None,
                 database=USE_CONFIG,
                 username=None,password=None):
        self.server=server if server is not None else ConfigUtil.get("database","server","localhost")
        self.port=port if port is not None else ConfigUtil.get("database","port",3306)
        self.database=ConfigUtil.get("database","database","movierecommender") if database==USE_CONFIG else database
        self.username=username if username is not None else ConfigUtil.get("database","username","root")
        self.password=password if password is not None else ConfigUtil.get("database","password","")
        self.conn=None
    def connect(self):
        try:
            self.conn = mysql.connector.connect(
                host=self.server,
                port=self.port,
                database=self.database,
                user=self.username,
                password=self.password,
                use_pure=True )
            return self.conn
        except Exception as e:
            self.conn=None
            print(str(e))
            return None
    def disconnect(self):
        try:
            if self.conn!=None:
                self.conn.close()
        except Exception as e:
            print(str(e))
    def queryDataset(self,sql,val=None):
        # Trả về DataFrame (có tên cột kể cả khi 0 dòng); lỗi thì trả None
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql,val)
            df=pd.DataFrame(cursor.fetchall(),columns=cursor.column_names)
            cursor.close()
            return df
        except Exception as e:
            print(str(e))
            return None
    def executeNonQuery(self,sql,val=None):
        # Dùng cho insert/update/delete; trả về số dòng bị ảnh hưởng, lỗi thì trả -1
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql,val)
            self.conn.commit()
            rowcount=cursor.rowcount
            cursor.close()
            return rowcount
        except Exception as e:
            print(str(e))
            return -1
    def isConnected(self):
        return self.conn is not None
    def executeMany(self,sql,val):
        try:
            cursor = self.conn.cursor()
            cursor.executemany(sql,val)
            self.conn.commit()
            rowcount=cursor.rowcount
            cursor.close()
            return rowcount
        except Exception as e:
            print(str(e))
            return -1
