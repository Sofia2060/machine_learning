from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QLineEdit, QApplication

from ui.LoginMainWindow import Ui_MainWindow
from app.services.AuthService import AuthService


class LoginMainWindowEx(Ui_MainWindow):
    def setupUi(self, MainWindow):
        super().setupUi(MainWindow)
        self.MainWindow=MainWindow
        self.lineEditUserName.addAction(QIcon("../images/ic_user.png"), QLineEdit.ActionPosition.LeadingPosition)
        self.lineEditPassword.addAction(QIcon("../images/ic_lock.png"), QLineEdit.ActionPosition.LeadingPosition)
        self.labelLoginError.setVisible(False)
        self.checkConfig()
        self.loadSavedLogin()
        self.setupSignalAndSlot()
    def showWindow(self):
        self.MainWindow.show()

    def setupSignalAndSlot(self):
        self.pushButtonLogin.clicked.connect(self.process_login)
        self.lineEditPassword.returnPressed.connect(self.process_login)
        self.lineEditUserName.returnPressed.connect(self.lineEditPassword.setFocus)
        self.pushButtonRegister.clicked.connect(self.showRegisterUI)
        self.pushButtonForgotPassword.clicked.connect(self.showForgotPasswordUI)
        self.pushButtonExit.clicked.connect(self.MainWindow.close)
    def showMessage(self,text):
        self.labelLoginError.setText(text)
        self.labelLoginError.setVisible(text!="")
    def checkConfig(self):
        # NFR-15: báo rõ khi cấu hình thiếu hoặc không hợp lệ thay vì âm thầm dùng giá trị sai
        from app.utils.ConfigUtil import ConfigUtil
        ConfigUtil.load()
        if ConfigUtil.errors:
            self.showMessage("Cấu hình chưa hợp lệ (app/config/config.json): "+"; ".join(ConfigUtil.errors))
    def loadSavedLogin(self):
        # "Ghi nhớ tên đăng nhập": chỉ lưu tên đăng nhập, không lưu mật khẩu
        settings=QSettings("CineMatch","MovieRecommender")
        username=settings.value("username","")
        if username!="":
            self.lineEditUserName.setText(username)
            self.checkBoxSave.setChecked(True)
            self.lineEditPassword.setFocus()
    def saveLoginInfo(self,username):
        settings=QSettings("CineMatch","MovieRecommender")
        if self.checkBoxSave.isChecked():
            settings.setValue("username",username)
        else:
            settings.remove("username")
    def process_login(self):
        uid = self.lineEditUserName.text().strip()
        pwd = self.lineEditPassword.text()
        if uid=="" or pwd=="":
            self.showMessage("Vui lòng nhập tên đăng nhập (hoặc email) và mật khẩu.")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        result = AuthService.login(uid, pwd)
        QApplication.restoreOverrideCursor()
        if not result.ok:
            self.showMessage(result.message)
            self.lineEditPassword.clear()
            self.lineEditPassword.setFocus()
            return
        self.showMessage("")
        self.saveLoginInfo(uid)
        us = result.account
        # Điều hướng theo vai trò (FR-02)
        if us.role=="admin":
            from ui.AdminDashboardMainWindowEx import AdminDashboardMainWindowEx
            self.myui=AdminDashboardMainWindowEx()
        else:
            from app.dal.customerDAO import customerDAO
            from app.dal.ratingDAO import ratingDAO
            if len(ratingDAO.getRatedMovieIds(us.customer_id))==0 and len(customerDAO.getFavoriteGenreIds(us.customer_id))==0:
                # FR-15: lần đầu sử dụng -> chọn ít nhất 3 thể loại yêu thích trước khi vào trang chủ
                from ui.GenrePreferenceMainWindowEx import GenrePreferenceMainWindowEx
                self.myui=GenrePreferenceMainWindowEx()
            else:
                from ui.UserMainWindowEx import UserMainWindowEx
                self.myui=UserMainWindowEx()
        self.myui.setupUi(QMainWindow())
        self.myui.setLoginUser(us)
        self.myui.showWindow()
        self.MainWindow.close()
    def showRegisterUI(self):
        from ui.RegisterMainWindowEx import RegisterMainWindowEx
        self.myui=RegisterMainWindowEx()
        self.myui.setupUi(QMainWindow())
        self.myui.showWindow()
        self.MainWindow.close()
    def showForgotPasswordUI(self):
        from ui.ForgotPasswordMainWindowEx import ForgotPasswordMainWindowEx
        self.myui=ForgotPasswordMainWindowEx()
        self.myui.setupUi(QMainWindow())
        self.myui.showWindow()
        self.MainWindow.close()
