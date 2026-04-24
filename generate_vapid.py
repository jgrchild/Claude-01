"""Run once to generate VAPID keys for push notifications."""
from py_vapid import Vapid

v = Vapid()
v.generate_keys()

public_key = v.public_key.public_bytes(
    __import__('cryptography').hazmat.primitives.serialization.Encoding.X962,
    __import__('cryptography').hazmat.primitives.serialization.PublicFormat.UncompressedPoint,
)
private_key = v.private_key.private_bytes(
    __import__('cryptography').hazmat.primitives.serialization.Encoding.PEM,
    __import__('cryptography').hazmat.primitives.serialization.PrivateFormat.TraditionalOpenSSL,
    __import__('cryptography').hazmat.primitives.serialization.NoEncryption(),
)

import base64
pub = base64.urlsafe_b64encode(public_key).decode().rstrip('=')
priv = private_key.decode().strip()

print("Add these to your .env file:\n")
print(f"VAPID_PUBLIC_KEY={pub}")
print(f"VAPID_PRIVATE_KEY={priv}")
