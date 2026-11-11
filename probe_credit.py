# -*- coding: utf-8 -*-
"""登录后精确读取学时、检查资料弹窗、列出课程与导航"""
import os, sys
from common import start, login, close, HOST, OUT

pw, browser, ctx, page = start()
try:
    login(page)
    print("\n>>> goto study center")
    try:
        page.goto(HOST + "/u/student/study/myCourse.action", wait_until="commit", timeout=60000)
    except Exception as e:
        print("goto warn:", str(e)[:200])
    page.wait_for_timeout(9000)
    print("URL:", page.url)

    body = page.locator("body").inner_text()
    open(os.path.join(OUT, "credit_page.txt"), "w", encoding="utf-8").write(body)
    print("body length:", len(body), "-> credit_page.txt")

    print("\n=== 学时/学分 related nodes ===")
    nodes = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('*').forEach(e => {
            if (e.children.length === 0 && /学时|学分|积分/.test(e.textContent)) {
                out.push({tag:e.tagName, cls:e.className, txt:e.textContent.trim().slice(0,80),
                          parent:(e.parentElement&&e.parentElement.textContent||'').trim().slice(0,140)});
            }
        });
        return out.slice(0, 40);
    }""")
    for n in nodes:
        print("  <%s> %-30s | parent: %s" % (n["tag"], n["txt"], n["parent"].replace("\n", " ")))

    print("\n=== visible dialogs / 个人资料 hints ===")
    dlg = page.evaluate("""() => {
        const out=[];
        document.querySelectorAll('div,section').forEach(e=>{
            const t=(e.textContent||'').trim();
            if(t.includes('为了保障您的学习成果') || t.includes('完善个人资料')){
                const r=e.getBoundingClientRect();
                if(r.width>100&&r.height>50&&t.length<600){
                    out.push({tag:e.tagName,id:e.id,cls:String(e.className).slice(0,80),
                              txt:t.replace(/\\s+/g,' ').slice(0,300),w:r.width,h:r.height});
                }
            }
        });
        return out.slice(0,8);
    }""")
    for d in dlg:
        print("  ", d)

    print("\n=== inputs in dialogs ===")
    for i in page.locator("input").all()[:40]:
        try:
            print("  input id=%-20s name=%-18s type=%-10s placeholder=%s" % (
                i.get_attribute("id"), i.get_attribute("name"), i.get_attribute("type"),
                i.get_attribute("placeholder")))
        except Exception:
            pass

    print("\n=== ALL links (href + text) ===")
    links = page.evaluate("""() => Array.from(document.querySelectorAll('a')).map(a=>({
        t:(a.textContent||'').trim().replace(/\\s+/g,' ').slice(0,40),
        h:a.getAttribute('href')||'', o:(a.getAttribute('onclick')||'').slice(0,80)
    })).filter(x=>x.t||x.h)""")
    with open(os.path.join(OUT, "center_links.txt"), "w", encoding="utf-8") as f:
        for l in links:
            f.write("%-42s | %-90s | %s\n" % (l["t"], l["h"][:90], l["o"]))
    print("  total links:", len(links), "-> center_links.txt")
    for l in links[:60]:
        print("  %-40s | %s" % (l["t"], l["h"][:100]))

    page.screenshot(path=os.path.join(OUT, "credit_page.png"), full_page=False)
    print("\nscreenshot: credit_page.png")
finally:
    close(pw, browser, ctx)
