"""即梦平台常量配置"""

# 即梦域名
JIMENG_DOMAIN = "jimeng.jianying.com"
JIMENG_BASE_URL = f"https://{JIMENG_DOMAIN}"

# 字节 Passport 登录相关
PASSPORT_DOMAIN = "passport.bytedance.com"
PASSPORT_LOGIN_URL = f"https://{PASSPORT_DOMAIN}/login"

# 即梦 API 端点
JIMENG_API_BASE = f"https://{JIMENG_DOMAIN}/api"

# 默认 User-Agent
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# Cookie 关键字段
COOKIE_SESSION_ID = "sessionid"
COOKIE_SESSION_ID_SS = "sessionid_ss"
COOKIE_PASSPORT_CSRF_TOKEN = "passport_csrf_token"

# 账号状态检测端点
ACCOUNT_STATUS_URL = f"{JIMENG_API_BASE}/user/info"

# 积分查询端点
CREDIT_QUERY_URL = f"{JIMENG_API_BASE}/credit/balance"
