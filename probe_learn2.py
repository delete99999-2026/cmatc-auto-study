# -*- coding: utf-8 -*-
"""深入课程学习页：课件列表、播放器、计时是否随播放增长"""
import os, re, time
from common import start, login, close, HOST, OUT

pw, browser, ctx, page = start()

def frames_dump(pg, tag):
    print("\n--- [%s] FRAMES ---" % tag)
    for f in pg.frames:
        print("   name=%-18r url=%s" % (f.name, f.url[:190]))

def text_of(pg, tag, limit=1800):
    try:
        t = pg.evaluate("() => document.body.innerText")
        print("\n--- [%s] MAIN TEXT ---\n%s" % (tag, t[:limit]))
        return t
    except Exception as e:
        print("text err", e)
        return ""

try:
    login(page)
    print("\n### goto 我的课程")
    try:
        page.goto(HOST + "/u/student/study/myCourse.action", wait_until="commit", timeout=60000)
    except Exception as e:
        print("goto warn", str(e)[:100])
    page.wait_for_timeout(7000)

    print("\n### click 继续学习")
    with page.expect_popup(timeout=15000) as pop:
        page.get_by_text("继续学习", exact=True).first.click(timeout=10000)
    lp = pop.value
    lp.wait_for_timeout(8000)
    print("LEARN URL:", lp.url)
    frames_dump(lp, "initial")
    t0 = text_of(lp, "initial")

    m = re.search(r"学习时长[:：]\s*([0-9:]+)", t0)
    t_start = m.group(1) if m else "?"
    print("\n>>> 学习时长 START:", t_start)

    print("\n### click 课件")
    try:
        lp.get_by_text("课件", exact=True).first.click(timeout=10000)
    except Exception as e:
        print("课件 click err:", str(e)[:150])
        lp.evaluate("""() => {
            const es=[...document.querySelectorAll('*')].filter(e=>e.children.length===0 && (e.textContent||'').trim()==='课件');
            if(es[0]) es[0].click();
        }""")
    lp.wait_for_timeout(6000)
    frames_dump(lp, "after 课件")
    t1 = text_of(lp, "after 课件")

    print("\n--- media elements in all frames ---")
    for f in lp.frames:
        try:
            for sel in ["video", "audio", "iframe", "object", "embed"]:
                for e in f.locator(sel).all()[:10]:
                    print("   frame[%s] <%s> id=%s src=%s" % (
                        f.url[:60], sel, e.get_attribute("id"),
                        (e.get_attribute("src") or "")[:140]))
        except Exception as e:
            print("   frame err", str(e)[:100])

    print("\n--- 课件/章节 links & buttons ---")
    for f in lp.frames:
        try:
            items = f.evaluate("""() => Array.from(document.querySelectorAll('a,li,span,div')).filter(e=>{
                const t=(e.textContent||'').trim();
                return e.children.length===0 && t && /播放|学习|课件|第.章|视频|时长|继续/.test(t) && t.length<40;
            }).map(e=>(e.textContent||'').trim()).slice(0,30)""")
            if items:
                print("   frame[%s]: %s" % (f.url[:70], items[:20]))
        except Exception:
            pass

    lp.screenshot(path=os.path.join(OUT, "learn_kejian.png"), full_page=False)
    print("\nscreenshot: learn_kejian.png")

    print("\n### wait 70s to observe timer (keeping page alive)...")
    for i in range(7):
        lp.wait_for_timeout(10000)
        try:
            tt = lp.evaluate("() => document.body.innerText")
            mm = re.search(r"学习时长[:：]\s*([0-9:]+)", tt)
            print("   t+%02ds 学习时长=%s" % ((i + 1) * 10, mm.group(1) if mm else "?"))
        except Exception as e:
            print("   timer read err", str(e)[:80])
    lp.screenshot(path=os.path.join(OUT, "learn_after_wait.png"), full_page=False)
finally:
    close(pw, browser, ctx)
