import os
import hashlib
from database.models import User


def get_a_new_user(user_id: str, username: str, password: str) -> User:
    salt = os.urandom(16).hex()
    hash_password = hashlib.sha256((password + salt).encode()).hexdigest()
    new_user = User(
        user_id=user_id,
        username=username,
        hash_password=hash_password,
        salt=salt
    )
    return new_user