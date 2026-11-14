"""LK888 协议模式登录测试"""
import base64
import json
import random
import string
import time
import sys

from curl_cffi import requests as cffi_requests

# ── 密码加密（逆向工程） ──
I_ARR = [188,125,42,166,175,21,53,39,111,122,214,134,92,108,3,33,63,102,67,255,152,119,164,104,166,113,195,231,106,99,61,121]

def decode_key():
    e = 137
    result = []
    for n in range(len(I_ARR)):
        result.append(chr(I_ARR[n] ^ e))
        e = (e * 17 + 23) & 0xFF
    return ''.join(result)

SECRET_KEY = decode_key()
print(f"[info] 密钥: {SECRET_KEY}")

def gen_random_prefix():
    p1 = ''.join(random.choices(string.ascii_lowercase, k=5))
    n1 = ''.join(random.choices(string.digits, k=3))
    p2 = ''.join(random.choices(string.ascii_lowercase, k=6))
    p3 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{p1}.{n1}@{p2}-{p3}={p2[:2]}"

def encrypt_password(password):
    prefix = gen_random_prefix()
    plain = prefix + "|" + password
    t = [(b + 7) % 256 for b in plain.encode('utf-8')]
    key_bytes = SECRET_KEY.encode('utf-8')
    xored = [t[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(t))]
    xored.reverse()
    return base64.b64encode(bytes(xored)).decode('utf-8')

# ── 行为包生成 ──
def gen_behavior():
    return {
        "v": 1,
        "ts": int(time.time() * 1000),
        "nonce": ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)),
        "qidong": 1,
        "yichang": 0,
        "tingliu": random.randint(100000, 500000),
        "shoujiao": random.randint(100, 200),
        "shubiao": {
            "yangben": random.randint(50, 100),
            "zong": random.randint(200, 500),
            "sujun": random.randint(500, 1500),
            "subiao": random.randint(1000, 2000),
            "zhixiandu": round(random.uniform(0.05, 0.15), 2)
        },
        "dianji": random.randint(2, 5),
        "jianpan": {
            "anzhu": {"n": random.randint(1, 3), "jun": random.randint(50, 150), "biao": 0},
            "jiange": {"n": 0, "jun": 0, "biao": 0}
        },
        "chumo": 0,
        "zidonghua": {
            "webdriver": 0, "wutu": 0, "cdc": 0,
            "lingchuang": 0, "jiachrome": 0, "wuyuyan": 0
        }
    }

# ── 主流程 ──
BASE = "https://ai778.cc"

session = cffi_requests.Session(impersonate="chrome131")

# Step 1: 获取图形验证码
print("\n[Step 1] 获取图形验证码...")
resp = session.get(f"{BASE}/houduan/denglu/tuxingyzm/get", timeout=15)
print(f"  状态码: {resp.status_code}")
data = resp.json()
print(f"  响应: {json.dumps(data, ensure_ascii=False)[:200]}")

if data.get("code") != 200:
    print(f"[error] 获取验证码失败: {data}")
    sys.exit(1)

captcha_id = data["data"]["id"]
captcha_img = data["data"]["img"]
print(f"  验证码ID: {captcha_id}")

# 保存验证码图片
img_data = base64.b64decode(captcha_img)
with open("/tmp/lk888_captcha.png", "wb") as f:
    f.write(img_data)
print(f"  验证码图片已保存: /tmp/lk888_captcha.png")

# 需要人工输入验证码
captcha_text = input("\n请输入验证码图片中的文字: ").strip()
if not captcha_text:
    print("未输入验证码，退出")
    sys.exit(1)

# Step 2: 登录
print(f"\n[Step 2] 登录 (验证码={captcha_text})...")
email = "dirkegirzi@necub.com"
password = "wy7374520"
encrypted_pw = encrypt_password(password)
print(f"  加密后密码: {encrypted_pw}")

login_payload = {
    "youxiang": email,
    "mima": encrypted_pw,
    "yanzhengma": captcha_text,
    "yanzhengmaid": captcha_id,
    "hangweibao": json.dumps(gen_behavior())
}

headers = {
    "Content-Type": "application/json",
    "Cookie": "x-hng=lang=zh-CN&domain=ai778.cc",
    "Referer": "https://ai778.cc/login",
    "Origin": "https://ai778.cc",
}

resp = session.post(
    f"{BASE}/houduan/denglu/mima/denglu",
    json=login_payload,
    headers=headers,
    timeout=15
)
print(f"  状态码: {resp.status_code}")
result = resp.json()
print(f"  响应: {json.dumps(result, ensure_ascii=False)}")

if result.get("code") == 200:
    token = result.get("data", {}).get("token")
    print(f"\n[SUCCESS] 登录成功!")
    print(f"  Token: {token}")
else:
    print(f"\n[FAILED] 登录失败: {result.get('msg', 'unknown')}")
