import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

SECRET_KEY = "dev-secret-change-me"
PBKDF2_ITERATIONS = 200_000


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, iters, salt, digest = stored.split("$")
    except ValueError:
        return False
    calc = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), int(iters)
    ).hex()
    return hmac.compare_digest(calc, digest)


def create_token(user_id: int) -> str:
    # В продакшене — JWT. Для каркаса — подписанная строка.
    exp = int((datetime.utcnow() + timedelta(hours=12)).timestamp())
    payload = f"{user_id}.{exp}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def parse_token(token: str) -> int | None:
    try:
        user_id, exp, sig = token.split(".")
        payload = f"{user_id}.{exp}"
        expected = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        if int(exp) < int(datetime.utcnow().timestamp()):
            return None
        return int(user_id)
    except (ValueError, AttributeError):
        return None
