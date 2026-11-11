# -*- coding: utf-8 -*-
"""探查学习档案(学时明细) + 课程中心(可选课程) + 我的课程"""
import os, re
from common import start, login, close, HOST, OUT

pw, browser, ctx, page = start()

def nav(path, wait=8000):
    try:
        page.goto(HOST + path, wait_until="commit", timeout=60000)
    except Exception as e:
        print("  goto warn:", str(e)[:120])
    page.wait_for_timeout(wait)
    print("  URL:", page.url)

def save_text(name):
    t = page.evaluate("() => document.body.innerText")
    open(os.path.join(OUT, name), "w", encoding="utf-8").write(t)
    print("  text len:", len(t), "->", name)
    return t

def show_links(name, limit=70):
    links = page.evaluate("""() => Array.from(document.querySelectorAll('a')).map(a=>({
        t:(a.textContent||'').trim().replace(/\\s+/g,' ').slice(0,50),
        h:a.getAttribute('href')||'', o:(a.getAttribute('onclick')||'').slice(0,90)
    })).filter(x=>x.t)""")
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        for l in links:
            f.write("%-50s | %-95s | %s\n" % (l["t"], l["h"][:95], l["o"]))
    print("  links:", len(links), "->", name)
    for l in links[:limit]:
        print("   %-46s | %s" % (l["t"], l["h"][:95]))

try:
    login(page)
    print("\n### 1. 学习中心 - 读取学时")
    nav("/u/student/study/myCourse.action")
    cr = page.evaluate("""() => {
        const res={};
        document.querySelectorAll('h4,div,span,li').forEach(e=>{
            const t=(e.textContent||'').trim();
            if(t==='本年度完成学时'||t==='完成总学时'||t==='本年度完成学分'||t==='完成总学分'){
                let p=e.parentElement;
                res[t]=(p?p.textContent:'').replace(/\\s+/g,' ').trim().slice(0,120);
            }
        });
        return res;
    }""")
    print("  CREDIT:", cr)

    print("\n### 2. 我的课程列表")
    nav("/u/student/study/myCourse.action")
    t = save_text("mycourse_text.txt")
    print("  --- preview ---")
    print("\n".join([l for l in t.splitlines() if l.strip()][:60]))
    show_links("mycourse_links.txt", 50)

    print("\n### 3. 学习档案")
    nav("/u/student/study/archives.action")
    t = save_text("archives_text.txt")
    print("  --- preview ---")
    print("\n".join([l for l in t.splitlines() if l.strip()][:70]))
    show_links("archives_links.txt", 30)
    page.screenshot(path=os.path.join(OUT, "archives.png"), full_page=False)

    print("\n### 4. 课程中心")
    nav("/cms/courseMarketNew.htm")
    t = save_text("market_text.txt")
    print("  --- preview ---")
    print("\n".join([l for l in t.splitlines() if l.strip()][:80]))
    show_links("market_links.txt", 60)
    page.screenshot(path=os.path.join(OUT, "market.png"), full_page=False)
finally:
    close(pw, browser, ctx)
