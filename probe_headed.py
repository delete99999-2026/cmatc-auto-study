# -*- coding: utf-8 -*-
"""有界面浏览器下视频播放是否正常（决定自动化可行性）"""
import os
from playwright.sync_api import sync_playwright
from common import EDGE, HOST, USER, PWD

ARGS = ["--no-sandbox", "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--autoplay-policy=no-user-gesture-required",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows"]

pw = sync_playwright().start()
try:
    browser = pw.chromium.launch(executable_path=EDGE, headless=False, args=ARGS)
except Exception as e:
    print("HEADED LAUNCH FAILED:", str(e)[:300])
    pw.stop()
    raise SystemExit(0)

ctx = browser.new_context(viewport={"width": 1280, "height": 800}, ignore_https_errors=True)
page = ctx.new_page()
page.set_default_timeout(20000)
try:
    page.goto(HOST + "/cms/loginNew.htm?portal=index", wait_until="commit", timeout=30000)
    page.wait_for_selector("#user1", timeout=25000)
    page.wait_for_timeout(1000)
    page.fill("#user1", USER); page.fill("#pwd1", PWD); page.click("#doSubmitBtn")
    page.wait_for_timeout(9000)
    print("login:", page.url)

    try:
        page.goto(HOST + "/u/student/study/myCourse.action", wait_until="commit", timeout=60000)
    except Exception as e:
        print("goto warn", str(e)[:100])
    page.wait_for_timeout(8000)
    with page.expect_popup(timeout=15000) as pop:
        page.get_by_text("继续学习", exact=True).first.click(timeout=10000)
    lp = pop.value
    lp.wait_for_timeout(7000)
    kj = next((f for f in lp.frames if "kjcourse" in f.url), None)
    print("kj:", kj.url if kj else None)
    if kj:
        try:
            kj.get_by_text("开始学习", exact=True).first.click(timeout=8000)
        except Exception as e:
            print("click err", str(e)[:100])
        for i in range(5):
            kj.wait_for_timeout(15000)
            st = kj.evaluate("""() => {const v=document.querySelector('video');
                return v?{t:+v.currentTime.toFixed(1),ready:v.readyState,paused:v.paused,
                buf:v.buffered.length?+v.buffered.end(0).toFixed(1):0}:null;}""")
            print("  t+%03ds %s" % ((i + 1) * 15, st))
finally:
    ctx.close(); browser.close(); pw.stop()
