from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QMessageBox, QMainWindow, QLineEdit, QApplication

from ui.ForgotPasswordMainWindow import Ui_MainWindow
from app.services.AuthService import AuthService


class ForgotPasswordMainWindowEx(Ui_MainWindow):
    # FR-03 bước 1: gửi OTP, đếm ngược thời hạn 5 phút, xác minh OTP rồi mới sang màn hình đặt lại mật khẩu
    def setupUi(self, MainWindow):
        super().setupUi(MainWindow)
        self.MainWindow=MainWindow
        self.email=None
        self.remaining=0
        self.lineEditEmail.addAction(QIcon("../images/ic_email.png"), QLineEdit.ActionPosition.LeadingPosition)
        self.timer=QTimer()
        self.timer.timeout.connect(self.tick)
        self.frameOTP.setEnabled(False)
        self.setupSignalAndSlot()
    def showWindow(self):
        self.MainWindow.show()

    def setupSignalAndSlot(self):
        self.pushButtonSendOTP.clicked.connect(self.process_sendOTP)
        self.lineEditEmail.returnPressed.connect(self.process_sendOTP)
        self.pushButtonResendOTP.clicked.connect(self.process_sendOTP)
        self.pushButtonVerifyOTP.clicked.connect(self.process_verifyOTP)
        self.lineEditOTP.returnPressed.connect(self.process_verifyOTP)
        self.pushButtonBackLogin.clicked.connect(self.showLoginUI)
    def showMessage(self,text,icon=QMessageBox.Icon.Warning):
        self.msgBox=QMessageBox(self.MainWindow)
        self.msgBox.setWindowTitle("Quên mật khẩu")
        self.msgBox.setIcon(icon)
        self.msgBox.setText(text)
        self.msgBox.exec()
    def process_sendOTP(self):
        from app.utils.SecurityUtil import SecurityUtil
        from app.dal.otpDAO import otpDAO

        email=self.lineEditEmail.text().strip().lower()
        if not SecurityUtil.isValidEmail(email):
            self.showMessage("Vui lòng nhập đúng email đã đăng ký.")
            self.lineEditEmail.setFocus()
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        (ok,message,demo_otp)=AuthService.sendOTP(email)
        QApplication.restoreOverrideCursor()
        if not ok:
            self.labelOTPStatus.setText(f"<span style='color:#DC2626'>{message}</span>")
            return
        self.email=email
        self.lineEditEmail.setReadOnly(True)
        self.pushButtonSendOTP.setEnabled(False)
        self.frameOTP.setEnabled(True)
        self.lineEditOTP.clear()
        self.lineEditOTP.setFocus()
        self.labelOTPStatus.setText(f"<span style='color:#15803D'>{message}</span>")
        self.remaining=otpDAO.getRemainingSeconds(email)
        self.updateCountdown()
        self.timer.start(1000)
        if demo_otp is not None:
            self.showMessage(f"Chế độ demo: mã OTP của bạn là {demo_otp}\n\n"
                             f"(Điền email gửi OTP trong config/config.json để gửi mã qua Gmail.)",
                             QMessageBox.Icon.Information)
    def tick(self):
        self.remaining-=1
        self.updateCountdown()
    def updateCountdown(self):
        # Đồng hồ đếm ngược thời hạn OTP 5 phút (NFR-18): xanh > 1 phút, cam ≤ 1 phút, đỏ khi hết hạn
        remaining=max(self.remaining,0)
        self.progressBarCountdown.setValue(remaining)
        if remaining<=0:
            self.timer.stop()
            self.setCountdownState("expired","../images/ic_clock_red.png")
            self.labelCountdown.setText("00:00")
            self.labelCountdownCaption.setText("Mã đã hết hạn")
            self.pushButtonVerifyOTP.setEnabled(False)
            return
        self.setCountdownState("warn" if remaining<=60 else "ok","../images/ic_clock.png")
        self.labelCountdown.setText(f"{remaining//60:02d}:{remaining%60:02d}")
        self.labelCountdownCaption.setText("còn lại")
        self.pushButtonVerifyOTP.setEnabled(True)
    def setCountdownState(self,state,icon):
        if self.frameCountdown.property("state")==state:
            return
        for widget in (self.frameCountdown,self.progressBarCountdown):
            widget.setProperty("state",state)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        for label in (self.labelCountdown,self.labelCountdownCaption):
            label.style().unpolish(label)
            label.style().polish(label)
        self.labelClockIcon.setPixmap(QPixmap(icon))
    def process_verifyOTP(self):
        if self.email is None:
            return
        otp=self.lineEditOTP.text().strip()
        if len(otp)!=6 or not otp.isdigit():
            self.showMessage("Mã OTP gồm đúng 6 chữ số.")
            self.lineEditOTP.setFocus()
            return
        (ok,message)=AuthService.verifyOTP(self.email,otp)
        if not ok:
            self.showMessage(message)
            self.lineEditOTP.selectAll()
            self.lineEditOTP.setFocus()
            if "hết hạn" in message or "bị khóa" in message or "không còn hiệu lực" in message:
                self.remaining=0
                self.updateCountdown()
            return
        self.timer.stop()
        from ui.ResetPasswordMainWindowEx import ResetPasswordMainWindowEx
        self.myui=ResetPasswordMainWindowEx()
        self.myui.setupUi(QMainWindow())
        self.myui.setEmail(self.email)
        self.myui.showWindow()
        self.MainWindow.close()
    def showLoginUI(self):
        self.timer.stop()
        from ui.LoginMainWindowEx import LoginMainWindowEx
        self.myui=LoginMainWindowEx()
        self.myui.setupUi(QMainWindow())
        self.myui.showWindow()
        self.MainWindow.close()
