from asyncmy.auth import sha2_rsa_encrypt


def test_mysql_sha2_authentication_supports_rsa_exchange() -> None:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    password = b"YOUR_PASSWORD_HERE"
    salt = b"01234567890123456789"

    encrypted = sha2_rsa_encrypt(password, salt, public_key)
    decrypted = private_key.decrypt(
        encrypted,
        padding.OAEP(mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None),
    )
    expected = bytes(value ^ salt[index % len(salt)] for index, value in enumerate(password + b"\0"))
    assert decrypted == expected
