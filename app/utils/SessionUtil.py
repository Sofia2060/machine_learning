import time

from PyQt6.QtCore import QObject, QEvent, QTimer
from PyQt6.QtWidgets import QApplication

from app.utils.ConfigUtil import ConfigUtil


class SessionUtil(QObject):
    # NFR-19: tự động đăng xuất sau 30 phút không thao tác; FR-21: Admin khóa tài khoản thì chấm dứt phiên đang mở
    ACTIVITY_EVENTS = (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress, QEvent.Type.Wheel)

    def __init__(self,MainWindow,on_expired,check_active=None,interval_seconds=15):
        super().__init__()
        self.MainWindow=MainWindow
        self.on_expired=on_expired          # hàm nhận thông báo lý do kết thúc phiên
        self.check_active=check_active      # hàm trả về False nếu tài khoản đã bị khóa
        self.idle_seconds=int(ConfigUtil.get("security","idle_logout_minutes",30))*60
        self.last_activity=time.time()
        self.timer=QTimer()
        self.timer.timeout.connect(self.check)
        self.timer.start(interval_seconds*1000)
        QApplication.instance().installEventFilter(self)
        self.running=True
    def eventFilter(self,obj,event):
        if event.type() in SessionUtil.ACTIVITY_EVENTS:
            self.last_activity=time.time()
        elif obj is self.MainWindow and event.type()==QEvent.Type.Close:
            self.stop()
        return False
    def check(self):
        if not self.running:
            return
        if time.time()-self.last_activity>=self.idle_seconds:
            self.expire(f"Bạn đã không thao tác trong {self.idle_seconds//60} phút nên phiên làm việc đã kết thúc. "
                        f"Vui lòng đăng nhập lại.")
            return
        if self.check_active is not None and self.check_active() is False:
            self.expire("Tài khoản của bạn vừa bị quản trị viên khóa. Phiên làm việc đã kết thúc.")
    def expire(self,message):
        self.stop()
        self.on_expired(message)
    def stop(self):
        if self.running:
            self.running=False
            self.timer.stop()
            QApplication.instance().removeEventFilter(self)
