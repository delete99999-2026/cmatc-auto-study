# -*- coding: utf-8 -*-
"""登录中国气象局培训学院在线培训平台，并保存会话状态"""
import os, sys
from playwright.sync_api import sync_playwright

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(OUT, "state.json")
USER = os.environ.get("CMATC_USER", "").strip()
PWD = os.environ.get("CMATC_PWD", "")
LOGIN_URL = "https://cmatcpx-cmatc.cma.cn/cms/loginNew.htm?portal=index"

if not PWD:
    print("ERROR: CMATC_PWD not set")
    sys.exit(1)

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=EDGE, headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage",
              "--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              ignore_https_errors=True)
    page = ctx.new_page()
    page.set_default_timeout(20000)

    print("goto:", LOGIN_URL)
    try:
        page.goto(LOGIN_URL, wait_until="commit", timeout=30000)
    except Exception as e:
        print("goto err:", e)
    page.wait_for_selector("#user1", timeout=25000)
    page.wait_for_timeout(1500)
    print("login page url:", page.url)
    print("inputs:", [(i.get_attribute("id"), i.get_attribute("placeholder"))
                      for i in page.locator("input").all()])

    page.fill("#user1", USER)
    page.fill("#pwd1", PWD)
    print("filled credentials, clicking submit...")
    try:
        page.click("#doSubmitBtn", timeout=10000)
    except Exception as e:
        print("click err:", e)
        page.evaluate("doSubmit()")

    # 登录涉及 AJAX -> sso 跳转链，轮询 URL 变化
    last = ""
    for i in range(24):
        page.wait_for_timeout(1500)
        u = page.url
        if u != last:
            print("  [%02d] %s" % (i, u[:170]))
            last = u
        if "loginNew" not in u and ("myCourse" in u or "study" in u or "index" in u.lower()):
            pass
    page.wait_for_timeout(3000)

    print("\n=== FINAL URL ===")
    print(page.url)
    print("\n=== BODY TEXT (first 3500) ===")
    try:
        print(page.locator("body").inner_text()[:3500])
    except Exception as e:
        print("body err:", e)
    print("\n=== page messages / errors hints ===")
    try:
        for sel in [".login-error", ".layui-layer-content", "[class*=error]", "#mt8_pwd", "#mt8_user"]:
            for el in page.locator(sel).all()[:5]:
                t = (el.inner_text() or "").strip()
                if t:
                    print("  msg[%s]: %s" % (sel, t[:200]))
    except Exception as e:
        print("msg err:", e)

    ctx.storage_state(path=STATE)
    print("\nstate saved:", STATE)
    page.screenshot(path=os.path.join(OUT, "after_login.png"), full_page=False)
    print("screenshot: after_login.png")
    ctx.close()
    browser.close()
