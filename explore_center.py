# -*- coding: utf-8 -*-
"""用已保存会话探查学习中心 / 学时统计入口"""
import os
from playwright.sync_api import sync_playwright

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(OUT, "state.json")
HOST = "https://cmatcpx-cmatc.cma.cn"

def dump(page, tag, limit=3500):
    print("\n" + "=" * 70)
    print("[%s] URL: %s" % (tag, page.url))
    try:
        print("[%s] TITLE: %s" % (tag, page.title()))
    except Exception:
        pass
    try:
        print("[%s] BODY:\n%s" % (tag, page.locator("body").inner_text()[:limit]))
    except Exception as e:
        print("body err", e)
    print("[%s] --- links containing keywords ---" % tag)
    try:
        seen = set()
        for a in page.locator("a").all():
            t = (a.inner_text() or "").strip().replace("\n", " ")[:45]
            h = a.get_attribute("href") or ""
            key = (t, h)
            if key in seen:
                continue
            seen.add(key)
            if any(k in t for k in ["学时", "档案", "统计", "成绩", "记录", "中心", "课程", "学习", "证书", "积分"]):
                print("  %-42s | %s" % (t, h[:130]))
    except Exception as e:
        print("links err", e)
    print("[%s] --- elements containing 学时 ---" % tag)
    try:
        for el in page.locator("text=学时").all()[:25]:
            print("  <%s> %s" % (el.evaluate("e=>e.tagName"), (el.inner_text() or "")[:120].replace("\n", " ")))
    except Exception as e:
        print("xueshi err", e)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=EDGE, headless=True,
                                args=["--no-sandbox", "--disable-dev-shm-usage",
                                      "--disable-blink-features=AutomationControlled"])
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              ignore_https_errors=True, storage_state=STATE)
    page = ctx.new_page()
    page.set_default_timeout(20000)

    for path, tag in [("/u/student/study/myCourse.action", "MY_COURSE"),
                      ("/cms/", "HOME_LOGGED")]:
        try:
            page.goto(HOST + path, wait_until="commit", timeout=30000)
        except Exception as e:
            print("goto err", tag, e)
        page.wait_for_timeout(6000)
        dump(page, tag)
        page.screenshot(path=os.path.join(OUT, "explore_%s.png" % tag), full_page=False)

    ctx.storage_state(path=STATE)
    ctx.close()
    browser.close()
