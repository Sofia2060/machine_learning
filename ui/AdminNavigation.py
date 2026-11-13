from PyQt6.QtWidgets import QMainWindow, QMessageBox

from app.utils.SessionUtil import SessionUtil


class AdminNavigation:
    # Các hàm dùng chung cho các cửa sổ Admin: thanh menu bên trái, tên admin trên header, phiên làm việc
    def setupNavigation(self):
        self.loginUser=None
        self.session=None
        self.pushButtonNavDashboard.clicked.connect(self.showDashboardUI)
        self.pushButtonNavRecommend.clicked.connect(self.showRecommendationStatsUI)
        self.pushButtonNavData.clicked.connect(self.showDataManagementUI)
        self.pushButtonLogout.clicked.connect(self.process_logout)
    def setLoginUser(self,us):
        # FR-06: kiểm tra quyền ở tầng xử lý, không chỉ ẩn màn hình
        if getattr(us,"role",None)!="admin":
            raise PermissionError("Chỉ tài khoản quản trị mới được mở màn hình quản trị.")
        self.loginUser=us
        self.labelAdminName.setText(us.username)
        self.labelAdminRole.setText(us.full_name if us.full_name else "Quản trị viên")
        # NFR-19: tự động đăng xuất sau 30 phút không thao tác
        self.session=SessionUtil(self.MainWindow,self.forceLogout)
        self.loadData()
    def loadData(self):
        pass
    def openAdminWindow(self,myui):
        if self.loginUser is None:
            return
        if self.session is not None:
            self.session.stop()
        self.myui=myui
        self.myui.setupUi(QMainWindow())
        self.myui.setLoginUser(self.loginUser)
        self.myui.showWindow()
        self.MainWindow.close()
    def showDashboardUI(self):
        from ui.AdminDashboardMainWindowEx import AdminDashboardMainWindowEx
        if isinstance(self, AdminDashboardMainWindowEx):
            return
        self.openAdminWindow(AdminDashboardMainWindowEx())
    def showRecommendationStatsUI(self):
        from ui.RecommendationStatsMainWindowEx import RecommendationStatsMainWindowEx
        if isinstance(self, RecommendationStatsMainWindowEx):
            return
        self.openAdminWindow(RecommendationStatsMainWindowEx())
    def showDataManagementUI(self):
        from ui.DataManagementMainWindowEx import DataManagementMainWindowEx
        if isinstance(self, DataManagementMainWindowEx):
            return
        self.openAdminWindow(DataManagementMainWindowEx())
    def confirm(self,title,text):
        # NFR-25: hộp xác nhận trước thao tác xóa / khóa
        ret=QMessageBox.question(self.MainWindow,title,text,QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                                 QMessageBox.StandardButton.No)
        return ret==QMessageBox.StandardButton.Yes
    def showMessage(self,text,icon=QMessageBox.Icon.Warning,title="CineMatch - Quản trị"):
        self.msgBox=QMessageBox(self.MainWindow)
        self.msgBox.setWindowTitle(title)
        self.msgBox.setIcon(icon)
        self.msgBox.setText(text)
        self.msgBox.exec()
    def openLogin(self):
        if self.session is not None:
            self.session.stop()
        from ui.LoginMainWindowEx import LoginMainWindowEx
        self.myui=LoginMainWindowEx()
        self.myui.setupUi(QMainWindow())
        self.myui.showWindow()
        self.MainWindow.close()
    def forceLogout(self,message):
        self.openLogin()
        self.myui.showMessage(message)
    def process_logout(self):
        if not self.confirm("Đăng xuất","Bạn có chắc muốn đăng xuất?"):
            return
        self.openLogin()
