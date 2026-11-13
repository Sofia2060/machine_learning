import hashlib
import hmac
import os
import random
import re
import string

from app.utils.ConfigUtil import ConfigUtil


class SecurityUtil:
    @staticmethod
    def hashPassword(pwd,salt=None,iterations=None):
        # NFR-17: băm PBKDF2-SHA256 có salt ngẫu nhiên, không lưu mật khẩu gốc, không thể giải ngược
        if salt is None:
            salt=os.urandom(16).hex()
        if iterations is None:
            iterations=int(ConfigUtil.get("security","password_iterations",20000))
        digest=hashlib.pbkdf2_hmac("sha256",pwd.encode("utf-8"),salt.encode("utf-8"),iterations).hex()
        return f"pbkdf2_sha256${iterations}${salt}${digest}"
    @staticmethod
    def isLegacyHash(password_hash):
        # Dữ liệu nạp bằng src/database.py lưu SHA-256 không salt (64 ký tự hex)
        return len(str(password_hash))==64 and all(c in "0123456789abcdef" for c in str(password_hash).lower())
    @staticmethod
    def checkPassword(pwd,password_hash):
        if SecurityUtil.isLegacyHash(password_hash):
            legacy=hashlib.sha256(pwd.encode("utf-8")).hexdigest()
            return hmac.compare_digest(legacy,str(password_hash).lower())
        try:
            (algorithm,iterations,salt,digest)=str(password_hash).split("$")
            if algorithm!="pbkdf2_sha256":
                return False
            new_hash=SecurityUtil.hashPassword(pwd,salt,int(iterations))
            return hmac.compare_digest(new_hash,password_hash)
        except:
            return False
    @staticmethod
    def isValidEmail(email):
        return re.match(r"^[\w\.\-+]+@[\w\-]+(\.[\w\-]+)+$", email) is not None
    @staticmethod
    def isValidUsername(username):
        return re.match(r"^[A-Za-z0-9_]{3,30}$", username) is not None
    @staticmethod
    def isStrongPassword(pwd):
        # Tối thiểu 8 ký tự, có cả chữ và số
        return len(pwd)>=8 and re.search(r"[A-Za-z]",pwd) is not None \
               and re.search(r"[0-9]",pwd) is not None
    @staticmethod
    def generateOTP():
        return "".join([str(random.SystemRandom().randint(0,9)) for i in range(6)])
    @staticmethod
    def generateTempPassword():
        # Mật khẩu tạm khi Admin đặt lại mật khẩu (FR-21): 10 ký tự gồm chữ và số
        rnd=random.SystemRandom()
        chars=[rnd.choice(string.ascii_letters) for i in range(6)]+[rnd.choice(string.digits) for i in range(4)]
        rnd.shuffle(chars)
        return "".join(chars)
    @staticmethod
    def fileHash(path):
        # NFR-21: mã băm SHA-256 của tệp mô hình
        h=hashlib.sha256()
        with open(path,"rb") as f:
            for block in iter(lambda: f.read(1024*1024), b""):
                h.update(block)
        return h.hexdigest()
