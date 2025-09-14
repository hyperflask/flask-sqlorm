from flask import current_app
from sqlorm.types.encrypted import Encrypted as BaseEncrypted
import hashlib


class Encrypted(BaseEncrypted):
    def __init__(self, key=None):
        if not key:
            key = lambda: current_app.config.get("SQLORM_ENCRYPTION_KEY") or hashlib.md5(current_app.config["SECRET_KEY"].encode()).digest()
        super().__init__(key)