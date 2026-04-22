"""
Unit Tests — Identity Service: auth.py helpers
Tests password hashing, verification, and JWT creation/decode
without requiring any database or network connection.
"""
import sys
import os

# Allow importing from parent directory (services/identity/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import jwt
from datetime import timedelta, datetime

from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)


# ─────────────────────────────────────────────────────────────
# Password hashing
# ─────────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        """Hashed password must not equal the original."""
        plain = "SecurePass123!"
        hashed = get_password_hash(plain)
        assert hashed != plain

    def test_hash_is_bcrypt_format(self):
        """bcrypt hashes begin with $2b$."""
        hashed = get_password_hash("anypassword")
        assert hashed.startswith("$2b$")

    def test_verify_correct_password_returns_true(self):
        plain = "MyCorrectPassword"
        hashed = get_password_hash(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password_returns_false(self):
        hashed = get_password_hash("RightPassword")
        assert verify_password("WrongPassword", hashed) is False

    def test_two_hashes_of_same_password_differ(self):
        """bcrypt salts must produce different ciphertext each time."""
        pw = "SamePassword"
        assert get_password_hash(pw) != get_password_hash(pw)

    def test_empty_password_hashes_and_verifies(self):
        """Edge case: empty string is a valid (though insecure) password."""
        hashed = get_password_hash("")
        assert verify_password("", hashed) is True
        assert verify_password("not-empty", hashed) is False


# ─────────────────────────────────────────────────────────────
# JWT token creation
# ─────────────────────────────────────────────────────────────

class TestJWTTokenCreation:
    def test_create_token_returns_string(self):
        token = create_access_token({"sub": "user-123", "username": "alice"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_expected_claims(self):
        data = {"sub": "user-abc", "username": "bob"}
        token = create_access_token(data)
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "user-abc"
        assert decoded["username"] == "bob"

    def test_token_has_expiry_claim(self):
        token = create_access_token({"sub": "user-123"})
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in decoded

    def test_custom_expiry_is_respected(self):
        delta = timedelta(minutes=5)
        before = datetime.utcnow()
        token = create_access_token({"sub": "u1"}, expires_delta=delta)
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = decoded["exp"]
        after = datetime.utcnow()
        # exp should be roughly now + 5 min
        assert exp >= int(before.timestamp()) + 299
        assert exp <= int(after.timestamp()) + 301

    def test_default_expiry_used_when_none_given(self):
        """With no expires_delta, default 15-minute expiry is applied."""
        token = create_access_token({"sub": "u2"})
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        now_ts = int(datetime.utcnow().timestamp())
        # Should be ~15 minutes in the future (give/take 5 s of test runtime)
        assert decoded["exp"] >= now_ts + 14 * 60

    def test_expired_token_raises_on_decode(self):
        token = create_access_token({"sub": "u3"}, expires_delta=timedelta(seconds=-1))
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    def test_tampered_token_raises_on_decode(self):
        token = create_access_token({"sub": "u4"})
        tampered = token[:-4] + "XXXX"
        with pytest.raises(jwt.PyJWTError):
            jwt.decode(tampered, SECRET_KEY, algorithms=[ALGORITHM])

    def test_wrong_secret_raises_on_decode(self):
        token = create_access_token({"sub": "u5"})
        with pytest.raises(jwt.PyJWTError):
            jwt.decode(token, "wrong-secret", algorithms=[ALGORITHM])
