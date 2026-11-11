# -*- coding: utf-8 -*-
"""公共模块：启动浏览器 + 单会话登录"""
import os
from playwright.sync_api import sync_playwright

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = os.path.dirname(os.path.abspath(__file__))
HOST = "https://cmatcpx-cmatc.cma.cn"
LOGIN_URL = HOST + "/cms/loginNew.htm?portal=index"
# 账号不再内置默认值：必须由启动参数 --user 或环境变量 CMATC_USER 提供，
# 避免任何真实账号出现在可公开的代码仓库里。
USER = os.environ.get("CMATC_USER", "").strip()
PWD = os.environ.get("CMATC_PWD", "")

# 容错：CMD 下 `set CMATC_PWD='密码'` 会把单引号一起存入变量，导致登录失败。
# 正确写法是 `set "CMATC_PWD=密码"`（双引号包住整个赋值式）。
if len(PWD) > 2 and PWD.startswith("'") and PWD.endswith("'"):
    PWD = PWD[1:-1]
    print("[warn] 检测到 CMATC_PWD 首尾带单引号，已自动去除。"
          " CMD 请用：set \"CMATC_PWD=你的密码\"", flush=True)
if PWD and (PWD.strip() != PWD or "你的密码" in PWD):
    print("[warn] 密码值看起来像占位符或含多余空白，请检查 CMATC_PWD", flush=True)

ARGS = ["--no-sandbox", "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--autoplay-policy=no-user-gesture-required"]


def start():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(executable_path=EDGE, headless=True, args=ARGS)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              ignore_https_errors=True)
    page = ctx.new_page()
    page.set_default_timeout(20000)
    return pw, browser, ctx, page


def login(page, verbose=True):
    if not USER:
        raise RuntimeError("CMATC_USER not set：请用 --user <账号> 或环境变量 CMATC_USER 提供登录账号")
    if not PWD:
        raise RuntimeError("CMATC_PWD not set")
    page.goto(LOGIN_URL, wait_until="commit", timeout=30000)
    page.wait_for_selector("#user1", timeout=25000)
    page.wait_for_timeout(1200)
    page.fill("#user1", USER)
    page.fill("#pwd1", PWD)
    page.click("#doSubmitBtn")
    stable, last = 0, ""
    for i in range(40):
        page.wait_for_timeout(1000)
        u = page.url
        if u == last:
            stable += 1
        else:
            stable = 0
            last = u
            if verbose:
                print("  [login] url:", u[:150])
        if stable >= 3 and "loginNew" not in u:
            break
    page.wait_for_timeout(2000)
    if verbose:
        print("  [login] final:", page.url)
    if "loginNew" in page.url:
        raise RuntimeError(
            "登录未成功，仍停留在登录页。请检查："
            "1) 密码是否正确；2) CMD 是否误用了 set CMATC_PWD='密码'（单引号会被算进密码，"
            "应写 set \"CMATC_PWD=密码\"）；3) 是否连续失败触发了验证码。")
    return page


def close(pw, browser, ctx):
    try:
        ctx.close()
    except Exception:
        pass
    try:
        browser.close()
    except Exception:
        pass
    try:
        pw.stop()
    except Exception:
        pass
