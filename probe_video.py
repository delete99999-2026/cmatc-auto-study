# -*- coding: utf-8 -*-
"""诊断视频播放：playbackRate / readyState / buffered / 节流"""
import os
from playwright.sync_api import sync_playwright
from common import EDGE, HOST, OUT, USER, PWD

ARGS = ["--no-sandbox", "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--autoplay-policy=no-user-gesture-required",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
        "--disable-features=CalculateNativeWinOcclusion"]

pw = sync_playwright().start()
browser = pw.chromium.launch(executable_path=EDGE, headless=True, args=ARGS)
ctx = browser.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=True)
page = ctx.new_page()
page.set_default_timeout(20000)
try:
    page.goto(HOST + "/cms/loginNew.htm?portal=index", wait_until="commit", timeout=30000)
    page.wait_for_selector("#user1", timeout=25000)
    page.wait_for_timeout(1000)
    page.fill("#user1", USER); page.fill("#pwd1", PWD); page.click("#doSubmitBtn")
    page.wait_for_timeout(9000)
    print("login url:", page.url)

    try:
        page.goto(HOST + "/u/student/study/myCourse.action", wait_until="commit", timeout=60000)
    except Exception as e:
        print("goto warn", str(e)[:100])
    page.wait_for_timeout(7000)
    with page.expect_popup(timeout=15000) as pop:
        page.get_by_text("继续学习", exact=True).first.click(timeout=10000)
    lp = pop.value
    lp.wait_for_timeout(7000)

    kj = next((f for f in lp.frames if "kjcourse" in f.url), None)
    print("kj frame:", kj.url if kj else None)
    if kj:
        try:
            kj.get_by_text("开始学习", exact=True).first.click(timeout=8000)
            print("clicked 开始学习")
        except Exception as e:
            print("click err", str(e)[:100])
        kj.wait_for_timeout(3000)
        print("initial:", kj.evaluate("""() => {const v=document.querySelector('video');
            return v?{t:v.currentTime,rate:v.playbackRate,ready:v.readyState,net:v.networkState,
            paused:v.paused,dur:v.duration,buf:v.buffered.length?v.buffered.end(0):0,
            err:v.error?v.error.code:null}:null;}"""))

        for i in range(6):
            kj.wait_for_timeout(15000)
            st = kj.evaluate("""() => {const v=document.querySelector('video');
                return v?{t:+v.currentTime.toFixed(1),rate:v.playbackRate,ready:v.readyState,
                paused:v.paused,buf:v.buffered.length?+v.buffered.end(0).toFixed(1):0,
                err:v.error?v.error.code:null}:null;}""")
            print("  t+%03ds %s" % ((i + 1) * 15, st))
finally:
    ctx.close(); browser.close(); pw.stop()
