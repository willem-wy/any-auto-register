#!/usr/bin/env python3
"""
LK888 自动化签到测试脚本

用法：
  python test_lk888_checkin.py --email <邮箱> --password <密码> --captcha <验证码答案>

示例：
  python test_lk888_checkin.py --email dirkegirzi@necub.com --password wy7374520 --captcha 8125
"""
import argparse
import base64
import hashlib
import json
import random
import string
import sys
import time

# 检查 curl_cffi 是否可用
try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
    print("警告：curl_cffi 未安装，将使用 requests 库")
    import requests as cffi_requests


# ── 加密常量（来自 JiaMi-YflxZtvo.js） ──
I_ARR = [
    188, 125, 42, 166, 175, 21, 53, 39, 111, 122, 214, 134, 92, 108, 3, 33,
    63, 102, 67, 255, 152, 119, 164, 104, 166, 113, 195, 231, 106, 99, 61, 121
]


def _decode_key() -> str:
    """从 I_ARR 生成 32 字节密钥"""
    e = 137
    result = []
    for n in range(len(I_ARR)):
        result.append(chr(I_ARR[n] ^ e))
        e = (e * 17 + 23) & 0xFF
    return ''.join(result)


SECRET_KEY = _decode_key()


def _gen_random_prefix() -> str:
    """生成随机前缀：xxxxx.nnn@xxxxxx-xxxx=xxxxxx"""
    p1 = ''.join(random.choices(string.ascii_lowercase, k=5))
    n1 = ''.join(random.choices(string.digits, k=3))
    p2 = ''.join(random.choices(string.ascii_lowercase + string.ascii_uppercase, k=6))
    p3 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    p4 = ''.join(random.choices(string.ascii_lowercase + string.ascii_uppercase + string.digits, k=6))
    return f'{p1}.{n1}@{p2}-{p3}={p4}'


def xor_encrypt(value: str) -> str:
    """XOR 加密（用于密码和 Token）"""
    prefix = _gen_random_prefix()
    plain = prefix + '|' + value

    t = [(b + 7) % 256 for b in plain.encode('utf-8')]
    key_bytes = SECRET_KEY.encode('utf-8')
    xored = [t[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(t))]
    xored.reverse()

    return base64.b64encode(bytes(xored)).decode('utf-8')


def gen_device_id(account: str) -> str:
    """基于账号生成固定设备标识"""
    h = hashlib.sha256(account.encode('utf-8')).hexdigest()
    return 'web_' + h[:32]


def gen_behavior() -> dict:
    """生成行为包"""
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


def lk888_checkin(email: str, password: str, captcha_answer: str):
    """
    LK888 完整签到流程

    Args:
        email: 邮箱账号
        password: 明文密码
        captcha_answer: 验证码答案
    """
    print(f"{'='*60}")
    print(f"LK888 自动化签到")
    print(f"{'='*60}")
    print(f"账号：{email}")
    print(f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 创建会话
    if HAS_CURL_CFFI:
        session = cffi_requests.Session(impersonate="chrome131")
    else:
        session = cffi_requests.Session()

    BASE_URL = "https://ai778.cc"

    # Step 1: 获取验证码
    print("[1/4] 获取图形验证码...")
    resp = session.get(
        f"{BASE_URL}/houduan/denglu/tuxingyzm/get",
        timeout=15,
        verify=False
    )

    if resp.status_code != 200:
        print(f"✗ 获取验证码失败：HTTP {resp.status_code}")
        return False

    data = resp.json()
    if data.get("code") != 200:
        print(f"✗ 获取验证码失败：{data.get('msg')}")
        return False

    captcha_id = data["data"]["验证码 ID"]
    captcha_img = data["data"]["图片 base64"]

    # 保存验证码图片
    if ',' in captcha_img[:50]:
        captcha_img_b64 = captcha_img.split(',', 1)[1]
    else:
        captcha_img_b64 = captcha_img

    padding = len(captcha_img_b64) % 4
    if padding:
        captcha_img_b64 += '=' * (4 - padding)

    img_data = base64.b64decode(captcha_img_b64)
    with open('/tmp/lk888_captcha.png', 'wb') as f:
        f.write(img_data)

    print(f"  ✓ 验证码 ID: {captcha_id}")
    print(f"  ✓ 验证码答案：{captcha_answer}")
    print(f"  ✓ 图片已保存：/tmp/lk888_captcha.png")
    print()

    # Step 2: 登录
    print("[2/4] 登录账号...")
    encrypted_pw = xor_encrypt(password)
    device_id = gen_device_id(email)

    login_payload = {
        "账号": email,
        "密码": encrypted_pw,
        "设备类型": "web",
        "设备标识": device_id,
        "使用语言": "zh-CN",
        "图形验证码 ID": captcha_id,
        "图形验证码答案": captcha_answer,
        "行为包": json.dumps(gen_behavior()),
        "nonce": ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)),
        "timestamp": int(time.time() * 1000)
    }

    headers = {
        "Content-Type": "application/json",
        "Cookie": "x-hng=lang=zh-CN&domain=ai778.cc",
        "Referer": f"{BASE_URL}/login",
        "Origin": BASE_URL,
    }

    resp = session.post(
        f"{BASE_URL}/houduan/denglu/mima/denglu",
        json=login_payload,
        headers=headers,
        timeout=15,
        verify=False
    )

    if resp.status_code != 200:
        print(f" 登录失败：HTTP {resp.status_code}")
        return False

    result = resp.json()
    if result.get("code") != 200:
        print(f"✗ 登录失败：{result.get('msg')}")
        return False

    token = result["data"]["token"]
    user_id = result["data"].get("用户 id", "")
    expires = result["data"].get("过期时间", "")

    print(f"  ✓ 登录成功")
    print(f"  ✓ Token: {token[:20]}...")
    print(f"  ✓ 用户 ID: {user_id}")
    print(f"  ✓ 过期时间：{expires}")
    print()

    # Step 3: 签到
    print("[3/4] 执行签到...")
    encrypted_token = xor_encrypt(token)

    checkin_headers = {
        "token": encrypted_token,
        "Content-Type": "application/json",
        "Cookie": "x-hng=lang=zh-CN&domain=ai778.cc",
        "Referer": f"{BASE_URL}/",
        "Origin": BASE_URL,
    }

    resp = session.post(
        f"{BASE_URL}/houduan/marketing/qiandao",
        headers=checkin_headers,
        timeout=15,
        verify=False
    )

    if resp.status_code != 200:
        print(f"✗ 签到失败：HTTP {resp.status_code}")
        return False

    checkin_result = resp.json()

    if checkin_result.get("code") == 200:
        data = checkin_result.get("data", {})
        reward = data.get("奖励金额", 0)
        total = data.get("总奖励", 0)
        consecutive = data.get("连续天数", 0)
        total_days = data.get("累计天数", 0)

        print(f"  ✓ 签到成功！")
        print(f"  ✓ 本次奖励：+{reward} 算力")
        print(f"  ✓ 总奖励：{total} 算力")
        print(f"  ✓ 连续签到：{consecutive} 天")
        print(f"  ✓ 累计签到：{total_days} 天")

        # 显示下一个里程碑
        milestone = data.get("下一个里程碑", {})
        if milestone:
            print(f"  ✓ 下一个里程碑：{milestone.get('名称', '')} (还差{milestone.get('还差天数', 0)}天)")

        print()
        print(f"{'='*60}")
        print(f"✓ 签到完成！")
        print(f"{'='*60}")
        return True

    elif checkin_result.get("code") == 400:
        print(f"  ⚠ 今日已签到：{checkin_result.get('msg', '')}")
        print()
        print(f"{'='*60}")
        print(f"✓ 流程完成（今日已签到）")
        print(f"{'='*60}")
        return True

    else:
        print(f"✗ 签到失败：{checkin_result.get('msg')}")
        return False


def main():
    parser = argparse.ArgumentParser(description='LK888 自动化签到')
    parser.add_argument('--email', required=True, help='邮箱账号')
    parser.add_argument('--password', required=True, help='密码')
    parser.add_argument('--captcha', required=True, help='验证码答案')

    args = parser.parse_args()

    success = lk888_checkin(args.email, args.password, args.captcha)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
