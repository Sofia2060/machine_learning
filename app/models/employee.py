class Employee:
    # Nhân viên quản trị (Admin) - bảng employees
    def __init__(self,employee_id=None,username=None,email=None,full_name=None,is_active=1):
        self.employee_id = employee_id
        self.username = username
        self.email = email
        self.full_name = full_name
        self.is_active = is_active
        self.role = "admin"
