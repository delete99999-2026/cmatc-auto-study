# -*- coding: utf-8 -*-
"""探查中国气象局培训学院在线培训平台的登录页与结构"""
import os, sys
from playwright.sync_api import sync_playwright

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE = "https://cmatcpx-cmatc.cma.cn/"
OUT = os.path.dirname(os.path.abspath(__file__))

def dump(page, tag):
    print("=" * 60)
    print("[%s] URL: %s" % (tag, page.url))
    try:
        print("[%s] TITLE: %s" % (tag, page.title()))
    except Exception as e:
        print("title err", e)
    try:
        txt = page.locator("body").inner_text(timeout=8000)
        print("[%s] BODY TEXT (first 2500):\n%s" % (tag, txt[:2500]))
    except Exception as e:
        print("body err", e)
    print("[%s] --- INPUTS ---" % tag)
    try:
        for i in page.locator("input").all():
            print("  input type=%s name=%s id=%s placeholder=%s value=%s" % (
                i.get_attribute("type"), i.get_attribute("name"), i.get_attribute("id"),
                i.get_attribute("placeholder"), (i.get_attribute("value") or "")[:40]))
    except Exception as e:
        print("inputs err", e)
    print("[%s] --- BUTTONS / links with login keyword ---" % tag)
    try:
        for b in page.locator("button, a, .btn, [onclick]").all()[:60]:
            t = (b.inner_text() or "").strip().replace("\n", " ")[:40]
            h = b.get_attribute("href") or b.get_attribute("onclick") or ""
            if t or h:
                print("  <%s> %-40s | %s" % (b.evaluate("e=>e.tagName"), t, h[:110]))
    except Exception as e:
        print("btns err", e)
    print("[%s] --- FRAMES ---" % tag)
    for f in page.frames:
        print("  frame:", f.name, f.url[:160])

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=EDGE, headless=True,
                                    args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(15000)
        try:
            page.goto(BASE, wait_until="commit", timeout=30000)
        except Exception as e:
            print("GOTO ERROR:", e)
        page.wait_for_timeout(6000)
        dump(page, "HOME")
        page.screenshot(path=os.path.join(OUT, "probe_home.png"), full_page=True)
        print("screenshot saved: probe_home.png")
        ctx.close()
        browser.close()

if __name__ == "__main__":
    main()
