"""Predefined credential for authentication."""
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Predefined credential
BAKED_USERNAME = "guest"

# Generate this hash with:
# python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('squash2025!'))"
BAKED_PW_HASH = "$argon2id$v=19$m=65536,t=3,p=4$xvtOe8+8fy/hPOdd651zrg$0K0YVVxZ+qH6m8OxfLUQQGKb8R5IwS7rPLh7F9w7NRI"

# Password hasher instance
_ph = PasswordHasher()


def verify_password(username: str, plain_password: str) -> bool:
    """
    Verify username and password against baked credential.
    
    Args:
        username: Username to verify
        plain_password: Plain text password
    
    Returns:
        True if credentials match, False otherwise
    """
    if username != BAKED_USERNAME:
        return False
    
    try:
        _ph.verify(BAKED_PW_HASH, plain_password)
        return True
    except VerifyMismatchError:
        return False


def get_baked_username() -> str:
    """Get the predefined username."""
    return BAKED_USERNAME
