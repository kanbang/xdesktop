import secrets

def generate_secret_key(length=32):
    return secrets.token_hex(length)

# 生成一个32字节长的SECRET_KEY
secret_key = generate_secret_key()
print(secret_key)