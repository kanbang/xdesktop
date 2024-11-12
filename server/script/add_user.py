import sys
sys.path.append("..")

from sqlalchemy.orm import Session
from models import User
from database import engine, Base, get_db
from passlib.context import CryptContext

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def create_user(db: Session, username: str, password: str, email: str = None, full_name: str = None):
    hashed_password = get_password_hash(password)
    db_user = User(username=username, hashed_password=hashed_password, email=email, full_name=full_name)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def main():
    db = next(get_db())
    username = input("Enter username: ")
    password = input("Enter password: ")
    email = input("Enter email (optional): ")
    full_name = input("Enter full name (optional): ")
    
    user = create_user(db, username, password, email, full_name)
    print(f"User {user.username} created successfully.")

if __name__ == "__main__":
    main()