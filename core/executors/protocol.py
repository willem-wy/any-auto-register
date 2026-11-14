"""纯协议执行器 - 基于 curl_cffi"""
import random

from curl_cffi import requests as curl_requests
from ..base_executor import BaseExecutor, Response

_CHROME_VERSIONS = [
    (120, "120.0.6099.130", "chrome120"),
    (123, "123.0.6312.87", "chrome123"),
    (124, "124.0.6367.91", "chrome124"),
    (131, "131.0.6778.86", "chrome131"),
    (133, "133.0.6943.54", "chrome133a"),
    (136, "136.0.7103.49", "chrome136"),
    (142, "142.0.7444.60", "chrome142"),
    (145, "145.0.7632.6", "chrome145"),
    (150, "150.0.7920.30", "chrome150"),
]

_PLATFORMS = [
    ("Windows NT 10.0; Win64; x64", "Win64", "Windows"),
    ("Macintosh; Intel Mac OS X 10_15_7", "MacIntel", "macOS"),
    ("X11; Linux x86_64", "Linux x86_64", "Linux"),
]

_ACCEPT_LANGUAGES = [
    "zh-CN,zh;q=0.9,en;q=0.8",
    "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "zh-CN,zh;q=0.9",
    "zh-CN,zh;q=0.9,en-GB;q=0.8,en;q=0.7",
]


def random_browser_fingerprint() -> dict:
    major, full_ver, imp_key = random.choice(_CHROME_VERSIONS)
    plat_str, plat_vendor, plat_name = random.choice(_PLATFORMS)
    lang = random.choice(_ACCEPT_LANGUAGES)
    ua = (
        f"Mozilla/5.0 ({plat_str}) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{full_ver} Safari/537.36"
    )
    sec_ch_ua = f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not-A.Brand";v="99"'
    return {
        "impersonate": imp_key,
        "user_agent": ua,
        "sec_ch_ua": sec_ch_ua,
        "sec_ch_ua_mobile": "?0",
        "sec_ch_ua_platform": f'"{plat_name}"',
        "accept_language": lang,
    }


class ProtocolExecutor(BaseExecutor):
    def __init__(self, proxy: str = None, impersonate: str = None):
        super().__init__(proxy)
        fp = random_browser_fingerprint()
        if impersonate:
            fp["impersonate"] = impersonate
        self.s = curl_requests.Session()
        self.s.impersonate = fp["impersonate"]
        if proxy:
            self.s.proxies = {"http": proxy, "https": proxy}
        self.s.headers.update({
            "user-agent": fp["user_agent"],
            "accept-language": fp["accept_language"],
            "sec-ch-ua": fp["sec_ch_ua"],
            "sec-ch-ua-mobile": fp["sec_ch_ua_mobile"],
            "sec-ch-ua-platform": fp["sec_ch_ua_platform"],
        })

    def _wrap(self, r) -> Response:
        cookies = {c.name: c.value for c in self.s.cookies.jar}
        return Response(
            status_code=r.status_code,
            text=r.text,
            headers=dict(r.headers),
            cookies=cookies,
        )

    def get(self, url, *, headers=None, params=None) -> Response:
        r = self.s.get(url, headers=headers, params=params)
        return self._wrap(r)

    def post(self, url, *, headers=None, params=None, data=None, json=None) -> Response:
        r = self.s.post(url, headers=headers, params=params, data=data, json=json)
        return self._wrap(r)

    def get_cookies(self) -> dict:
        return {c.name: c.value for c in self.s.cookies.jar}

    def set_cookies(self, cookies: dict) -> None:
        for k, v in cookies.items():
            self.s.cookies.set(k, v)

    def close(self) -> None:
        self.s.close()
