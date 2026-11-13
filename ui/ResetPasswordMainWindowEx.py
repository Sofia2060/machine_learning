from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMessageBox, QMainWindow, QLineEdit

from ui.ResetPasswordMainWindow import Ui_MainWindow
from app.services.AuthService import AuthService


class ResetPasswordMainWindowEx(Ui_MainWindow):
    # FR-03 bước 2: chỉ mở được sau khi OTP đã xác minh thành công
    def setupUi(self, MainWindow):
        super().setupUi(MainWindow)
        self.MainWindow=MainWindow
        self.email=None
        self.lineEditEmail.addAction(QIcon("../images/ic_email.png"), QLineEdit.ActionPosition.LeadingPosition)
        self.lineEditNewPassword.addAction(QIcon("../images/ic_lock.png"), QLineEdit.ActionPosition.LeadingPosition)
        self.lineEditConfirmPassword.addAction(QIcon("../images/ic_lock.png"), QLineEdit.ActionPosition.LeadingPosition)
        self.setupSignalAndSlot()
    def showWindow(self):
        self.MainWindow.show()

    def setupSignalAndSlot(self):
        self.pushButtonResetPassword.clicked.connect(self.process_resetPassword)
        self.lineEditConfirmPassword.returnPressed.connect(self.process_resetPassword)
        self.pushButtonBackLogin.clicked.connect(self.showLoginUI)
    def setEmail(self,email):
        self.email=email
        self.lineEditEmail.setText(email)
        self.lineEditNewPassword.setFocus()
    def showMessage(self,text,icon=QMessageBox.Icon.Warning):
        self.msgBox=QMessageBox(self.MainWindow)
        self.msgBox.setWindowTitle("Đặt lại mật khẩu")
        self.msgBox.setIcon(icon)
        self.msgBox.setText(text)
        self.msgBox.exec()
    def process_resetPassword(self):
        from app.utils.SecurityUtil import SecurityUtil

        pwd=self.lineEditNewPassword.text()
        confirm=self.lineEditConfirmPassword.text()
        if not SecurityUtil.isStrongPassword(pwd):
            self.showMessage("Mật khẩu mới tối thiểu 8 ký tự và phải có cả chữ lẫn số.")
            self.lineEditNewPassword.setFocus()
            return
        if pwd!=confirm:
            self.showMessage("Mật khẩu nhập lại không khớp.")
            self.lineEditConfirmPassword.setFocus()
            return
        if AuthService.resetPassword(self.email,pwd):
            self.showMessage("Đặt lại mật khẩu thành công. Vui lòng đăng nhập bằng mật khẩu mới.",
                             QMessageBox.Icon.Information)
            self.showLoginUI()
        else:
            self.showMessage("Không cập nhật được mật khẩu, vui lòng thử lại.", QMessageBox.Icon.Critical)
    def showLoginUI(self):
        from ui.LoginMainWindowEx import LoginMainWindowEx
        self.myui=LoginMainWindowEx()
        self.myui.setupUi(QMainWindow())
        self.myui.showWindow()
        self.MainWindow.close()
