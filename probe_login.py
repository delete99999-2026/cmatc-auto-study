# -*- coding: utf-8 -*-
"""探查登录 iframe 内部表单结构"""
import os
from playwright.sync_api import sync_playwright

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE = "https://cmatcpx-cmatc.cma.cn/"
OUT = os.path.dirname(os.path.abspath(__file__))

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=EDGE, headless=True,
                                args=["--no-sandbox", "--disable-dev-shm-usage"])
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=True)
    page = ctx.new_page()
    page.set_default_timeout(15000)
    try:
        page.goto(BASE, wait_until="commit", timeout=30000)
    except Exception as e:
        print("GOTO ERROR:", e)
    page.wait_for_timeout(6000)

    print("=== ALL FRAMES ===")
    for f in page.frames:
        print("  name=%r url=%s" % (f.name, f.url[:180]))

    lf = None
    for f in page.frames:
        if "loginNew" in f.url:
            lf = f
            break
    if lf is None:
        print("!! login frame not found")
    else:
        print("\n=== LOGIN FRAME TEXT ===")
        try:
            print(lf.locator("body").inner_text()[:2000])
        except Exception as e:
            print("err", e)
        print("\n=== LOGIN FRAME INPUTS ===")
        for i in lf.locator("input").all():
            print("  input type=%-10s name=%-20s id=%-20s placeholder=%-20s value=%s" % (
                i.get_attribute("type"), i.get_attribute("name"), i.get_attribute("id"),
                i.get_attribute("placeholder"), (i.get_attribute("value") or "")[:40]))
        print("\n=== LOGIN FRAME BUTTONS/LINKS ===")
        for b in lf.locator("button, a, .btn, [onclick], img").all()[:50]:
            t = (b.inner_text() or "").strip().replace("\n", " ")[:40]
            h = b.get_attribute("href") or b.get_attribute("onclick") or b.get_attribute("src") or ""
            if t or h:
                print("  <%s> %-30s | %s" % (b.evaluate("e=>e.tagName"), t, h[:120]))
        print("\n=== IMG / captcha hints ===")
        for im in lf.locator("img").all():
            print("  img id=%s src=%s" % (im.get_attribute("id"), (im.get_attribute("src") or "")[:160]))
        print("\n=== relevant JS globals ===")
        for js in ["typeof $", "typeof jQuery", "typeof document.forms.length",
                   "document.forms.length"]:
            try:
                print("  %s => %s" % (js, lf.evaluate(js)))
            except Exception as e:
                print("  %s => err %s" % (js, e))
    page.screenshot(path=os.path.join(OUT, "probe_login.png"), full_page=False)
    print("screenshot saved: probe_login.png")
    ctx.close()
    browser.close()
