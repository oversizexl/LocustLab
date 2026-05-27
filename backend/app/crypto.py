import base64
from cryptography.fernet import Fernet
from app.config import SECRET_KEY

def _build_fernet() -> Fernet:
    raw = SECRET_KEY.encode()
    key = base64.urlsafe_b64encode(raw[:32].ljust(32, b"0"))
    return Fernet(key)

_fernet = _build_fernet()


def encrypt(plain: str) -> str:
    if not plain:
        return ""
    return _fernet.encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except Exception:
        return ""
