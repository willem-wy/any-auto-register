"""即梦浏览器注册流程"""
import asyncio
import re
from typing import Callable, Optional
from playwright.async_api import Page, BrowserContext

from platforms.jimeng.core import (
    JIMENG_BASE_URL,
    JIMENG_DOMAIN,
    COOKIE_SESSION_ID,
    COOKIE_SESSION_ID_SS,
    UA,
)


class JimengBrowserRegister:
    """即梦浏览器自动化注册"""

    def __init__(
        self,
        captcha=None,
        headless: bool = True,
        proxy: Optional[str] = None,
        otp_callback: Optional[Callable] = None,
        log_fn: Callable = print,
    ):
        self.captcha = captcha
        self.headless = headless
        self.proxy = proxy
        self.otp_callback = otp_callback
        self.log = log_fn or print

    async def run(self, email: str = "", password: str = "") -> dict:
        """执行注册流程

        即梦使用字节 Passport 登录体系，主要流程：
        1. 打开即梦登录页
        2. 选择手机号/邮箱登录
        3. 输入账号密码
        4. 获取验证码（邮箱/手机）
        5. 完成登录
        6. 提取 Cookie
        """
        from playwright.async_api import async_playwright

        self.log(" 启动即梦浏览器注册流程")

        async with async_playwright() as p:
            # 启动浏览器
            browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )

            # 创建上下文
            context_options = {
                "user_agent": UA,
                "viewport": {"width": 1920, "height": 1080},
                "locale": "zh-CN",
                "timezone_id": "Asia/Shanghai",
            }

            if self.proxy:
                context_options["proxy"] = {"server": self.proxy}

            context = await browser.new_context(**context_options)

            # 注入反检测脚本
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = {runtime: {}};
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
            """)

            page = await context.new_page()

            try:
                # 步骤 1: 打开即梦登录页
                self.log("📱 打开即梦登录页面")
                await page.goto(f"{JIMENG_BASE_URL}/ai-tool/login", wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

                # 步骤 2: 点击登录按钮，打开登录弹窗
                self.log(" 点击登录按钮")
                login_button = page.locator("button:has-text('登录')").first
                if await login_button.is_visible():
                    await login_button.click()
                    await page.wait_for_timeout(2000)

                # 步骤 3: 切换到密码登录（如果有选项）
                self.log("📝 切换到密码登录模式")
                password_login = page.locator("text=密码登录").first
                if await password_login.is_visible():
                    await password_login.click()
                    await page.wait_for_timeout(1000)

                # 步骤 4: 输入邮箱和密码
                if email:
                    self.log(f"📧 输入邮箱：{email}")
                    email_input = page.locator("input[placeholder*='邮箱'], input[type='email']").first
                    if await email_input.is_visible():
                        await email_input.fill(email)
                        await page.wait_for_timeout(500)

                if password:
                    self.log("🔒 输入密码")
                    password_input = page.locator("input[type='password']").first
                    if await password_input.is_visible():
                        await password_input.fill(password)
                        await page.wait_for_timeout(500)

                # 步骤 5: 勾选用户协议
                self.log("✅ 勾选用户协议")
                agreement_checkbox = page.locator("input[type='checkbox']").first
                if await agreement_checkbox.is_visible():
                    is_checked = await agreement_checkbox.is_checked()
                    if not is_checked:
                        await agreement_checkbox.click()
                        await page.wait_for_timeout(500)

                # 步骤 6: 点击登录/注册按钮
                self.log("🚀 提交登录")
                submit_button = page.locator("button:has-text('登录'), button:has-text('注册')").first
                if await submit_button.is_visible():
                    await submit_button.click()

                # 步骤 7: 处理验证码（如果需要）
                self.log("⏳ 等待验证码处理")
                if self.otp_callback:
                    self.log("📬 等待验证码回调")
                    # 等待验证码输入框出现
                    otp_input = page.locator("input[placeholder*='验证码'], input[type='text'][maxlength='6']").first
                    if await otp_input.wait_for(state="visible", timeout=30000):
                        self.log(" 验证码输入框已出现，等待用户输入或自动填充")
                        # 这里可以集成自动验证码填充
                        await page.wait_for_timeout(60000)  # 等待用户手动输入或自动填充

                # 步骤 8: 等待登录成功
                self.log("⏳ 等待登录完成")
                try:
                    # 等待跳转到主页或出现用户头像
                    await page.wait_for_url("**/home**", timeout=30000)
                    self.log("✅ 登录成功，已跳转到主页")
                except:
                    # 检查是否出现用户头像或其他登录成功标志
                    user_avatar = page.locator(".user-avatar, [class*='avatar'], img[alt*='用户']").first
                    if await user_avatar.is_visible(timeout=10000):
                        self.log("✅ 检测到用户头像，登录成功")
                    else:
                        self.log("⚠️ 未明确检测到登录成功，继续提取 Cookie")

                # 步骤 9: 提取 Cookie
                self.log("🍪 提取登录 Cookie")
                cookies = await context.cookies()

                session_id = ""
                session_id_ss = ""

                for cookie in cookies:
                    if cookie["name"] == COOKIE_SESSION_ID:
                        session_id = cookie["value"]
                    elif cookie["name"] == COOKIE_SESSION_ID_SS:
                        session_id_ss = cookie["value"]

                if not session_id and not session_id_ss:
                    self.log("❌ 未找到 sessionid Cookie，登录可能失败")
                    # 截图保存当前状态
                    screenshot_path = "/tmp/jimeng_login_failed.png"
                    await page.screenshot(path=screenshot_path)
                    self.log(f"📸 已保存截图：{screenshot_path}")
                    return {
                        "success": False,
                        "error": "未找到 sessionid Cookie",
                        "email": email,
                    }

                self.log("✅ 成功提取 sessionid")

                # 步骤 10: 获取用户信息
                self.log("👤 获取用户信息")
                user_info = {}
                try:
                    # 通过页面内的 API 获取用户信息
                    response = await page.evaluate("""
                        async () => {
                            const res = await fetch('/api/user/info');
                            return await res.json();
                        }
                    """)
                    user_info = response if isinstance(response, dict) else {}
                except Exception as e:
                    self.log(f"️ 获取用户信息失败：{e}")

                return {
                    "success": True,
                    "email": email,
                    "session_id": session_id,
                    "session_id_ss": session_id_ss,
                    "cookies": {c["name"]: c["value"] for c in cookies},
                    "user_info": user_info,
                }

            except Exception as e:
                self.log(f"❌ 注册流程出错：{e}")
                # 截图保存错误状态
                try:
                    screenshot_path = "/tmp/jimeng_register_error.png"
                    await page.screenshot(path=screenshot_path)
                    self.log(f"📸 已保存错误截图：{screenshot_path}")
                except:
                    pass
                return {
                    "success": False,
                    "error": str(e),
                    "email": email,
                }
            finally:
                await browser.close()
                self.log("🔒 浏览器已关闭")
