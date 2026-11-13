from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMessageBox, QMainWindow, QLineEdit

from app.models.customer import Customer
from ui.RegisterMainWindow import Ui_MainWindow
from app.utils.FormUtil import FormUtil


class RegisterMainWindowEx(Ui_MainWindow):
    def setupUi(self, MainWindow):
        super().setupUi(MainWindow)
        self.MainWindow=MainWindow
        self.lineEditFullName.addAction(QIcon("../images/ic_user.png"), QLineEdit.ActionPosition.LeadingPosition)
        self.lineEditUserName.addAction(QIcon("../images/ic_user.png"), QLineEdit.ActionPosition.LeadingPosition)
        self.lineEditEmail.addAction(QIcon("../images/ic_email.png"), QLineEdit.ActionPosition.LeadingPosition)
        self.lineEditPassword.addAction(QIcon("../images/ic_lock.png"), QLineEdit.ActionPosition.LeadingPosition)
        self.lineEditConfirmPassword.addAction(QIcon("../images/ic_lock.png"), QLineEdit.ActionPosition.LeadingPosition)
        FormUtil.fillProfileCombos(self.comboBoxGender,self.comboBoxAge,self.comboBoxOccupation)
        self.setupSignalAndSlot()
    def showWindow(self):
        self.MainWindow.show()

    def setupSignalAndSlot(self):
        self.pushButtonRegister.clicked.connect(self.process_register)
        self.pushButtonBackLogin.clicked.connect(self.showLoginUI)
    def showMessage(self,text,icon=QMessageBox.Icon.Warning):
        self.msgBox=QMessageBox(self.MainWindow)
        self.msgBox.setWindowTitle("Đăng ký tài khoản")
        self.msgBox.setIcon(icon)
        self.msgBox.setText(text)
        self.msgBox.exec()
    def process_register(self):
        from app.dal.accountDAO import accountDAO
        from app.dal.customerDAO import customerDAO
        from app.utils.SecurityUtil import SecurityUtil

        full_name=self.lineEditFullName.text().strip()
        username=self.lineEditUserName.text().strip()
        email=self.lineEditEmail.text().strip().lower()
        pwd=self.lineEditPassword.text()
        confirm=self.lineEditConfirmPassword.text()
        # FR-01: họ tên, email, tên đăng nhập, mật khẩu là bắt buộc
        missing=[name for (name,value) in (("Họ và tên",full_name),("Tên đăng nhập",username),("Email",email),
                                           ("Mật khẩu",pwd),("Nhập lại mật khẩu",confirm)) if value==""]
        if missing:
            self.showMessage("Vui lòng nhập các mục bắt buộc: "+", ".join(missing)+".")
            return
        if not SecurityUtil.isValidUsername(username):
            self.showMessage("Tên đăng nhập gồm 3–30 ký tự: chữ cái, chữ số hoặc dấu gạch dưới.")
            self.lineEditUserName.setFocus()
            return
        if not SecurityUtil.isValidEmail(email):
            self.showMessage("Email không đúng định dạng.")
            self.lineEditEmail.setFocus()
            return
        if not SecurityUtil.isStrongPassword(pwd):
            self.showMessage("Mật khẩu tối thiểu 8 ký tự và phải có cả chữ lẫn số.")
            self.lineEditPassword.setFocus()
            return
        if pwd!=confirm:
            self.showMessage("Mật khẩu nhập lại không khớp.")
            self.lineEditConfirmPassword.setFocus()
            return
        if accountDAO.isUsernameExist(username):
            self.showMessage("Tên đăng nhập đã tồn tại, vui lòng chọn tên khác.")
            return
        if accountDAO.isEmailExist(email):
            self.showMessage("Email đã được đăng ký.")
            return
        cus=Customer()
        cus.full_name=full_name
        cus.username=username
        cus.email=email
        cus.gender=self.comboBoxGender.currentData()
        cus.age=self.comboBoxAge.currentData()
        cus.occupation=self.comboBoxOccupation.currentData()
        if customerDAO.register(cus,pwd) is not None:
            self.showMessage("Đăng ký thành công! Hãy đăng nhập để chọn thể loại yêu thích và bắt đầu.",
                             QMessageBox.Icon.Information)
            self.showLoginUI(username)
        else:
            self.showMessage("Đăng ký thất bại, vui lòng thử lại.", QMessageBox.Icon.Critical)
    def showLoginUI(self,username=None):
        from ui.LoginMainWindowEx import LoginMainWindowEx
        self.myui=LoginMainWindowEx()
        self.myui.setupUi(QMainWindow())
        if isinstance(username,str):
            self.myui.lineEditUserName.setText(username)
            self.myui.lineEditPassword.setFocus()
        self.myui.showWindow()
        self.MainWindow.close()
