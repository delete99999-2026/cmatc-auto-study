# -*- coding: utf-8 -*-
"""只读：打印课程中心页面自身的选课/分页函数源码，确认接口与参数。绝不点选课。"""
import os, json, re
from playwright.sync_api import sync_playwright
from common import EDGE, HOST, OUT, ARGS, USER, PWD, login

MARKET_URL = HOST + "/cms/courseMarketNew.htm"
buf = []
def w(s=""):
    print(s, flush=True); buf.append(str(s))

FNS_JS = r"""() => {
    const names = ['chooseCourseTimeLimit','chooseCourse','show','jumpPage',
                   'saveCourse','addCourse','enterCourseTimeLimit'];
    const out = {};
    for (const n of names) {
        try { out[n] = (typeof window[n] === 'function') ? String(window[n]).slice(0, 3000) : ('typeof=' + typeof window[n]); }
        catch (e) { out[n] = 'ERR:' + String(e); }
    }
    const srcs = [...document.querySelectorAll('script[src]')].map(s => s.getAttribute('src'));
    out.__scripts = srcs.filter(s => /course|study|market|learn/i.test(s)).slice(0, 30);
    return out;
}"""

def main():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(executable_path=EDGE, headless=True, args=ARGS)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=True)
    pg = ctx.new_page()
    pg.set_default_timeout(20000)
    try:
        login(pg, verbose=False)
        w("LOGIN OK %s" % pg.url)
        pg.goto(MARKET_URL, wait_until="commit", timeout=30000)
        pg.wait_for_timeout(5000)
        w("MARKET %s" % pg.url)
        fns = pg.evaluate(FNS_JS)
        for k, v in fns.items():
            w("\n===== %s =====" % k)
            w(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=1))
        # 外链 JS 里搜 saveCourses / chooseCourse
        urls = []
        for s in pg.evaluate("() => [...document.querySelectorAll('script[src]')].map(x=>x.src)"):
            if re.search(r'course|study|market|learn|common|index', s, re.I):
                urls.append(s)
        w("\n===== candidate scripts (%d) =====" % len(urls))
        for u in urls[:25]: w("  " + u)
        for u in urls[:25]:
            try:
                r = pg.request.get(u, timeout=15000)
                t = r.text()
                if re.search(r'saveCourses|chooseCourseTimeLimit|chooseCourse', t):
                    w("\n===== MATCH %s =====" % u)
                    for m in re.finditer(r'.{0,400}(?:saveCourses|chooseCourseTimeLimit).{0,700}', t):
                        w(m.group(0)[:1200])
                        w("---")
            except Exception as e:
                w("  fetch err %s %s" % (u[:80], str(e)[:80]))
    finally:
        with open(os.path.join(OUT, "_diag_choose_api_out.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(buf))
        w("OUT -> _diag_choose_api_out.txt")
        try:
            ctx.close(); browser.close(); pw.stop()
        except Exception:
            pass

if __name__ == "__main__":
    main()
