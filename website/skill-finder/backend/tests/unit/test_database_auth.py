"""MySQL `caching_sha2_password` 认证的 RSA 公钥交换回归测试。

`asyncmy` 在服务端要求密文传输密码时会先拿到 PEM 公钥，再用 `cryptography`
把「密码 + 结尾 \0」与 20 字节 salt 逐字节异或后做 RSA-OAEP(SHA1) 加密。这里用
自签的一对密钥走完整往返，确认 `sha2_rsa_encrypt` 的异或与填充约定没有被改动：
若该约定被破坏，云端 MySQL（腾讯云 `xixi` 库强制 SHA-2）会直接认证失败。
"""

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
