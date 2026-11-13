from app.connectors.connector import Connector


class modelDAO:
    @staticmethod
    def getActiveModel():
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select * from model_registry where is_active=1 order by model_id desc limit 1")
        conn.disconnect()
        if df is None or len(df)==0:
            return None
        return df.iloc[0]
    @staticmethod
    def getModelById(model_id):
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select * from model_registry where model_id=%s", (model_id,))
        conn.disconnect()
        if df is None or len(df)==0:
            return None
        return df.iloc[0]
    @staticmethod
    def setActive(model_id):
        conn = Connector()
        conn.connect()
        conn.executeNonQuery("update model_registry set is_active=0 where model_id<>%s", (model_id,))
        ret = conn.executeNonQuery("update model_registry set is_active=1 where model_id=%s", (model_id,))
        conn.disconnect()
        return ret>=0
    @staticmethod
    def getModels():
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select model_id, model_name, file_name, n_users, n_items, n_ratings, exported_at, "
                               "is_active, registered_at from model_registry order by model_id desc")
        conn.disconnect()
        return df
    @staticmethod
    def registerModel(model_name,file_name,file_hash,calibration,n_users,n_items,n_ratings,exported_at,
                      employee_id=None,activate=True):
        conn = Connector()
        conn.connect()
        if activate:
            conn.executeNonQuery("update model_registry set is_active=0")
        sql = "insert into model_registry (model_name,file_name,file_hash,calibration,n_users,n_items,n_ratings," \
              "exported_at,is_active,employee_id) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        ret = conn.executeNonQuery(sql, (model_name, file_name, file_hash, calibration, n_users, n_items, n_ratings,
                                         exported_at, 1 if activate else 0, employee_id))
        conn.disconnect()
        return ret>0
    @staticmethod
    def countRatingsAfter(time_value):
        # Số đánh giá mới phát sinh sau lần xuất mô hình (chưa được mô hình học)
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select count(*) as n from ratings where is_valid=1 and rating_time>%s", (time_value,))
        conn.disconnect()
        return 0 if df is None else int(df.iloc[0]["n"])
