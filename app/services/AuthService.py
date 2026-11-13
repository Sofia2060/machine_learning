from app.dal.accountDAO import accountDAO
from app.dal.otpDAO import otpDAO
from app.models.customer import Customer
from app.models.employee import Employee
from app.utils.ConfigUtil import ConfigUtil
from app.utils.EmailUtil import EmailUtil
from app.utils.SecurityUtil import SecurityUtil


class LoginResult:
    def __init__(self,ok,message="",account=None):
        self.ok=ok
        self.message=message
        self.account=account     # Employee (Admin) hoặc Customer (User)


class AuthService:
    # Tầng xử lý nghiệp vụ xác thực (NFR-16): giao diện gọi AuthService, AuthService gọi tầng dữ liệu (DAO)

    @staticmethod
    def login(login,password):
        # FR-02, NFR-19: đăng nhập bằng tên đăng nhập hoặc email; sai 5 lần liên tiếp khóa tạm 15 phút
        max_fail=int(ConfigUtil.get("security","max_login_fail",5))
        lock_minutes=int(ConfigUtil.get("security","login_lock_minutes",15))
        (role,row)=accountDAO.findAccount(login)
        if role=="error":
            return LoginResult(False,"Không kết nối được cơ sở dữ liệu. Vui lòng kiểm tra MySQL và config.json.")
        if row is None:
            return LoginResult(False,"Tên đăng nhập/email hoặc mật khẩu không đúng.")
        account_id=int(row["account_id"])
        if int(row["is_active"])==0:
            return LoginResult(False,"Tài khoản đã bị khóa. Vui lòng liên hệ quản trị viên.")
        if int(row["is_locked"])==1:
            minutes=max(1,(int(row["locked_seconds"])+59)//60)
            return LoginResult(False,f"Bạn đã nhập sai {max_fail} lần liên tiếp. Tài khoản tạm khóa, "
                                     f"vui lòng thử lại sau {minutes} phút.")
        if not SecurityUtil.checkPassword(password,row["password_hash"]):
            count=accountDAO.registerFailed(role,account_id,max_fail,lock_minutes)
            if count>=max_fail:
                return LoginResult(False,f"Bạn đã nhập sai {max_fail} lần liên tiếp. "
                                         f"Tài khoản tạm khóa {lock_minutes} phút.")
            return LoginResult(False,f"Tên đăng nhập/email hoặc mật khẩu không đúng "
                                     f"(còn {max_fail-count} lần thử trước khi bị khóa tạm).")
        accountDAO.resetFailed(role,account_id)
        if SecurityUtil.isLegacyHash(row["password_hash"]):
            # NFR-17: mật khẩu SHA-256 cũ được băm lại bằng PBKDF2 có salt ngay khi đăng nhập đúng
            accountDAO.setPasswordHash(role,account_id,SecurityUtil.hashPassword(password))
        if role=="admin":
            account=Employee(account_id,row["username"],row["email"],row["full_name"],int(row["is_active"]))
        else:
            account=Customer(account_id,row["username"],row["email"],row["full_name"],row["gender"],
                             None if row["age"] is None or row["age"]!=row["age"] else int(row["age"]),
                             None if row["occupation_id"] is None or row["occupation_id"]!=row["occupation_id"]
                             else int(row["occupation_id"]),row["zip_code"],int(row["is_active"]),row["created_at"])
        return LoginResult(True,"OK",account)
    # ---------------- Quên mật khẩu (FR-03, NFR-18) ----------------
    @staticmethod
    def sendOTP(email):
        # Trả về (ok, thông báo, mã OTP nếu đang ở chế độ demo)
        (role,row)=accountDAO.findByEmail(email)
        if role=="error":
            return (False,"Không kết nối được cơ sở dữ liệu.",None)
        if row is None:
            return (False,"Email này chưa được đăng ký trong hệ thống.",None)
        otp=SecurityUtil.generateOTP()
        if not otpDAO.createOTP(email,otp):
            return (False,"Không tạo được mã OTP, vui lòng thử lại.",None)
        if EmailUtil.isConfigured():
            if EmailUtil.sendOTP(email,otp):
                return (True,f"Đã gửi mã OTP đến {email}.",None)
            return (False,"Gửi email thất bại. Vui lòng kiểm tra cấu hình email hoặc kết nối mạng.",None)
        return (True,"Chế độ demo (chưa cấu hình email): mã OTP được hiển thị trên màn hình.",otp)
    @staticmethod
    def verifyOTP(email,otp):
        return otpDAO.verifyOTP(email,otp)
    @staticmethod
    def resetPassword(email,password):
        # Chỉ gọi sau khi OTP đã được xác minh ở bước trước
        (role,row)=accountDAO.findByEmail(email)
        if row is None:
            return False
        return accountDAO.setPasswordHash(role,int(row["account_id"]),SecurityUtil.hashPassword(password))
