# -*- coding: utf-8 -*-
"""查看课程'学习进度'页，确认完成条件"""
import os
from common import start, login, close, HOST, OUT

pw, browser, ctx, page = start()
try:
    login(page)
    try:
        page.goto(HOST + "/u/student/study/myCourse.action", wait_until="commit", timeout=60000)
    except Exception as e:
        print("goto warn", str(e)[:100])
    page.wait_for_timeout(7000)
    with page.expect_popup(timeout=15000) as pop:
        page.get_by_text("继续学习", exact=True).first.click(timeout=10000)
    lp = pop.value
    lp.wait_for_timeout(7000)

    print(">>> click 学习进度")
    try:
        lp.get_by_text("学习进度", exact=True).first.click(timeout=10000)
    except Exception as e:
        print("click err", str(e)[:120])
    lp.wait_for_timeout(6000)
    for f in lp.frames:
        try:
            t = f.evaluate("() => document.body.innerText")
            if t and len(t.strip()) > 20:
                print("\n=== frame:", f.url[:130], "===")
                print(t[:1800])
        except Exception:
            pass
    lp.screenshot(path=os.path.join(OUT, "progress_page.png"), full_page=False)
finally:
    close(pw, browser, ctx)
