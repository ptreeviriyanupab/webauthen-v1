import hashlib
import hmac

# These algorithms are intentionally weak/unsalted -- this app is a
# controlled classroom target for a hash-cracking exercise, not a
# real authentication system. See README.md for the production warning.
SUPPORTED_ALGORITHMS = {"md5", "sha1", "sha256", "sha512"}


def hash_password(password: str, algorithm: str) -> str:
    algorithm = (algorithm or "").strip().lower()
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(f"Unsupported hash algorithm: {algorithm!r}")
    return hashlib.new(algorithm, password.encode("utf-8")).hexdigest()


def verify_password(password: str, stored_hash: str, algorithm: str) -> bool:
    try:
        computed = hash_password(password, algorithm)
    except ValueError:
        # Unknown/corrupted algorithm on the stored record -- fail closed.
        return False
    return hmac.compare_digest(computed, stored_hash)
