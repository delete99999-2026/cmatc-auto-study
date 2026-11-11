# -*- coding: utf-8 -*-
"""验证能否高频重复提交 studyTime（决定加速比）。"""
import os, re, json, time, contextlib
from playwright.sync_api import sync_playwright
from common import EDGE, HOST, OUT, ARGS, login

ADD = int(os.environ.get("CMATC_ADD", "300"))
N = int(os.environ.get("CMATC_N", "6"))
GAP = float(os.environ.get("CMATC_GAP", "3"))
H = "https://pxkckj-cmatc.cma.cn"
SAVE = H + "/learnspace/course/study/learningTime_saveLearningTime.action"
QUERY = H + "/learnspace/course/study/learningTime_queryLearningTime.action"
OUT_TXT = os.path.join(OUT, "probe_submit_loop_v3_out.txt")
_buf = []


def out(s):
    s = str(s)
    print(s, flush=True)
    _buf.append(s)


PARSE = r"""(fnName) => {
    const out=[];
    document.querySelectorAll('a[onclick]').forEach(a=>{
        const oc=a.getAttribute('onclick')||'';
        if(oc.indexOf(fnName+'(')<0) return;
        const s=oc.indexOf(fnName+'(')+fnName.length+1;
        const b=oc.slice(s,oc.lastIndexOf(')')+1);
        const args=[],re=/'([^']*)'|"([^"]*)"/g; let m;
        while((m=re.exec(b))!==null) args.push(m[1]!==undefined?m[1]:m[2]);
        if(args.length) out.push({fn:fnName,args:args,url:args[0]});
    });
    return out;
}"""

POST = r"""async (p) => {
    const b=new URLSearchParams();
    b.append('courseId',p.courseId);
    if(p.studyTime!==null) b.append('studyTime',String(p.studyTime));
    if(p.limitId) b.append('limitId',p.limitId);
    try{
        const r=await fetch(p.url,{method:'POST',headers:{
            'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With':'XMLHttpRequest'},body:b.toString(),credentials:'same-origin'});
        let t=''; try{t=await r.text();}catch(e){}
        return {status:r.status,body:t.slice(0,400)};
    }catch(e){return {error:String(e).slice(0,150)};}
}"""


def main():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(executable_path=EDGE, headless=True, args=ARGS)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              ignore_https_errors=True)
    pg = ctx.new_page()
    pg.set_default_timeout(25000)
    try:
        login(pg, verbose=False)
        pg.goto(HOST + "/u/student/study/myCourseTheme.action",
                wait_until="commit", timeout=60000)
        pg.wait_for_timeout(7000)
        cs = pg.evaluate(PARSE, "enterCourse")
        if not cs:
            pg.goto(HOST + "/cms/courseMarketNew.htm", wait_until="commit", timeout=60000)
            pg.wait_for_timeout(6000)
            cs = pg.evaluate(PARSE, "enterCourseTimeLimit")
        c = cs[0]
        with pg.expect_popup(timeout=30000) as pop:
            pg.evaluate("(p)=>window[p.fn].apply(null,p.args)",
                        {"fn": c["fn"], "args": c["args"]})
        lp = pop.value
        lp.wait_for_timeout(8000)
        try:
            lp.get_by_text("课件", exact=True).first.click(timeout=10000)
        except Exception:
            pass
        lp.wait_for_timeout(6000)

        info = lp.evaluate("""() => {
            const u=new URL(location.href), t=window.top||window;
            return {courseId:u.searchParams.get('params.courseId'),
                    limitId:(typeof t.limitId!=='undefined'?t.limitId:null)};
        }""")
        cid, limit = info["courseId"], info["limitId"]
        out("courseId=%s limitId=%s" % (cid, limit))

        def q():
            r = lp.evaluate(POST, {"url": QUERY, "courseId": cid,
                                   "studyTime": None, "limitId": None})
            m = re.search(r'"learnTime"\s*:\s*"?(\d+)', r.get("body", ""))
            return (int(m.group(1)) if m else -1), r

        v0, _ = q()
        out("起始 learnTime=%s" % v0)
        for i in range(N):
            cur, _ = q()
            target = cur + ADD
            s = lp.evaluate(POST, {"url": SAVE, "courseId": cid,
                                   "studyTime": target, "limitId": limit})
            new, qr = q()
            out("%d) 提交 %s -> 响应 %s | 实测 %s -> %s (Δ=%s)"
                % (i + 1, target, json.dumps(s, ensure_ascii=False)[:180],
                   cur, new, new - cur))
            time.sleep(GAP)

        out("\n--- 主站学时复核 ---")
        pg.goto(HOST + "/u/student/study/myCourse.action",
                wait_until="commit", timeout=60000)
        pg.wait_for_timeout(8000)
        t = pg.evaluate("() => document.body.innerText")
        mm = re.search(r"本年度完成学时[^\d]{0,20}(\d+(?:\.\d+)?)", t)
        out("本年度完成学时: %s" % (mm.group(1) if mm else "读取失败"))
        out("DONE")
    finally:
        with open(OUT_TXT, "w", encoding="utf-8") as f:
            f.write("\n".join(_buf) + "\n")
        for fn in (lambda: ctx.close(), lambda: browser.close(), lambda: pw.stop()):
            with contextlib.suppress(BaseException):
                fn()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        out("Ctrl+C")
    except Exception:
        import traceback
        out(traceback.format_exc()[-1500:])
