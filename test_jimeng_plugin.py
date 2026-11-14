"""测试即梦平台插件"""
import sys
sys.path.insert(0, "/Users/admin/Desktop/myapps/any-auto-register")

from core.registry import load_all, list_platforms, get

# 加载所有平台插件
print("加载平台插件...")
load_all()

# 列出所有已注册的平台
platforms = list_platforms()
print(f"\n已注册平台 ({len(platforms)} 个):")
for p in platforms:
    print(f"  - {p['name']}: {p['display_name']} v{p['version']}")

# 检查即梦是否注册成功
print("\n检查即梦平台...")
try:
    jimeng_cls = get("jimeng")
    print(f"✅ 即梦平台已注册：{jimeng_cls.display_name}")
    print(f"   版本：{jimeng_cls.version}")
    print(f"   支持的执行器：{jimeng_cls.supported_executors}")
    print(f"   支持的身份模式：{jimeng_cls.supported_identity_modes}")
    print(f"   平台能力：{jimeng_cls.capabilities}")
except KeyError as e:
    print(f"❌ 即梦平台未注册：{e}")
