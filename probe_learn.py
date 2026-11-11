# -*- coding: utf-8 -*-
"""探查课程学习页：播放器、计时、进度与检测机制"""
import os
from common import start, login, close, HOST, OUT

pw, browser, ctx, page = start()

def nav(path, wait=8000):
    try:
        page.goto(HOST + path, wait_until="commit", timeout=60000)
    except Exception as e:
        print("  goto warn:", str(e)[:120])
    page.wait_for_timeout(wait)
    print("  URL:", page.url)

def describe(pg, tag):
    print("\n" + "=" * 68)
    print("[%s] URL: %s" % (tag, pg.url))
    try:
        print("[%s] TITLE: %s" % (tag, pg.title()))
    except Exception:
        pass
    try:
        t = pg.evaluate("() => document.body.innerText")
        print("[%s] TEXT (first 2200):\n%s" % (tag, t[:2200]))
    except Exception as e:
        print("  text err", e)
    print("[%s] --- video/audio/iframe ---" % tag)
    try:
        for sel in ["video", "audio", "iframe", "embed", "object"]:
            for e in pg.locator(sel).all()[:12]:
                print("  <%s> id=%s src=%s" % (sel, e.get_attribute("id"),
                                               (e.get_attribute("src") or "")[:150]))
    except Exception as e:
        print("  media err", e)
    print("[%s] --- progress/percent/学时 keywords ---" % tag)
    try:
        hits = pg.evaluate("""() => {
            const out=[];
            document.querySelectorAll('*').forEach(e=>{
                if(e.children.length===0){
                    const t=(e.textContent||'').trim();
                    if(t && /进度|学时|%|分钟|播放|学习时长|已完成|继续学习|验证|采集/.test(t) && t.length<60)
                        out.push(t);
                }
            });
            return out.slice(0,45);
        }""")
        for h in hits:
            print("   ", h)
    except Exception as e:
        print("  kw err", e)

try:
    login(page)
    print("\n### goto 我的课程")
    nav("/u/student/study/myCourse.action")

    print("\n### click 继续学习")
    try:
        with page.expect_popup(timeout=15000) as pop:
            page.get_by_text("继续学习", exact=True).first.click(timeout=10000)
        newp = pop.value
        print("  popup opened")
    except Exception as e:
        print("  no popup (%s), checking ctx.pages" % str(e)[:100])
        newp = None
    page.wait_for_timeout(7000)

    pages = ctx.pages
    print("\n>>> total pages:", len(pages))
    for i, pg in enumerate(pages):
        describe(pg, "PAGE%d" % i)
        try:
            pg.screenshot(path=os.path.join(OUT, "learn_page%d.png" % i), full_page=False)
        except Exception as e:
            print("  screenshot err", e)
finally:
    close(pw, browser, ctx)
