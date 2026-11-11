# -*- coding: utf-8 -*-
"""验证：播放视频后 学习时长/进度 是否增长，是否出现核验弹窗"""
import os, re
from common import start, login, close, HOST, OUT

pw, browser, ctx, page = start()

def get_time(pg):
    try:
        t = pg.evaluate("() => document.body.innerText")
        m = re.search(r"学习时长[:：]\s*([0-9:]+)", t)
        return m.group(1) if m else "?"
    except Exception:
        return "?"

def video_state(pg):
    try:
        return pg.evaluate("""() => {
            const v=document.querySelector('video');
            if(!v) return null;
            return {t:v.currentTime, dur:v.duration, paused:v.paused, src:(v.currentSrc||'').slice(0,120)};
        }""")
    except Exception:
        return None

try:
    login(page)
    print(">>> 我的课程")
    try:
        page.goto(HOST + "/u/student/study/myCourse.action", wait_until="commit", timeout=60000)
    except Exception as e:
        print("goto warn", str(e)[:100])
    page.wait_for_timeout(7000)
    mc = page.evaluate("() => document.body.innerText")
    m = re.search(r"坚持以党的政治建设为统领[\s\S]{0,80}?学习进度：([\d.]+%)", mc)
    print("  初始进度:", m.group(1) if m else "?")

    print(">>> 打开学习页")
    with page.expect_popup(timeout=15000) as pop:
        page.get_by_text("继续学习", exact=True).first.click(timeout=10000)
    lp = pop.value
    lp.wait_for_timeout(8000)
    print("  学习时长:", get_time(lp))

    kj = None
    for f in lp.frames:
        if "kjcourse" in f.url:
            kj = f
            break
    if kj:
        print(">>> kjcourse frame:", kj.url)
        try:
            print("  frame text:", kj.evaluate("() => document.body.innerText")[:300])
        except Exception:
            pass
        try:
            kj.get_by_text("开始学习", exact=True).first.click(timeout=8000)
            print("  clicked 开始学习")
        except Exception as e:
            print("  开始学习 click err:", str(e)[:120])
    else:
        print("  !! kjcourse frame not found")

    lp.wait_for_timeout(5000)
    print("  video state after click:", video_state(kj) if kj else None)

    print("\n>>> 观察 180 秒")
    for i in range(6):
        lp.wait_for_timeout(30000)
        vs = video_state(kj) if kj else None
        print("  t+%03ds 学习时长=%s video=%s" % ((i + 1) * 30, get_time(lp), vs))

    print("\n>>> 检查是否有核验/弹窗")
    for f in lp.frames:
        try:
            t = f.evaluate("() => document.body.innerText")
            for kw in ["验证身份", "人脸", "采集", "请完成", "拖动", "滑块", "是否还在"]:
                if kw in t:
                    print("  [%s] 命中关键词 %s: %s" % (f.url[:60], kw, t[:160].replace("\n", " ")))
                    break
        except Exception:
            pass

    print("\n>>> 回我的课程看进度")
    try:
        page.goto(HOST + "/u/student/study/myCourse.action", wait_until="commit", timeout=60000)
    except Exception as e:
        print("goto warn", str(e)[:100])
    page.wait_for_timeout(7000)
    mc2 = page.evaluate("() => document.body.innerText")
    m2 = re.search(r"坚持以党的政治建设为统领[\s\S]{0,80}?学习进度：([\d.]+%)", mc2)
    print("  结束时进度:", m2.group(1) if m2 else "?")
    print("  学时区块:", [l for l in mc2.splitlines() if "学时" in l][:8])
    open(os.path.join(OUT, "verify_mycourse.txt"), "w", encoding="utf-8").write(mc2)
finally:
    close(pw, browser, ctx)
