class Customer:
    # Khách hàng (User) - bảng customers
    def __init__(self,customer_id=None,username=None,email=None,full_name=None,
                 gender=None,age=None,occupation=None,zip_code=None,is_active=1,created_at=None):
        self.customer_id = customer_id
        self.username = username
        self.email = email
        self.full_name = full_name
        self.gender = gender
        self.age = age
        self.occupation = occupation
        self.zip_code = zip_code
        self.is_active = is_active
        self.created_at = created_at
        self.role = "user"
