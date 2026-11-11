# -*- coding: utf-8 -*-
"""验证 saveLearningItem.json 提交大 videoTime 能否把课件标记 completed。"""
import os, re, json, contextlib
from playwright.sync_api import sync_playwright
from common import EDGE, HOST, OUT, ARGS, login

H = "https://pxkckj-cmatc.cma.cn"
SAVE = H + "/learnspace/learn/learnCourseware/saveLearningItem.json"
QUERY_ITEM = H + "/learnspace/learn/learnCourseware/queryLearningItem.json"
COMPLETE = H + "/learnspace/learn/learnCourseware/getSingleItemCompleteCase.json"
OUT_TXT = os.path.join(OUT, "probe_complete_v3_out.txt")
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
    for (const k in p.data) b.append(k, p.data[k]);
    try{
        const r=await fetch(p.url,{method:'POST',headers:{
            'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With':'XMLHttpRequest'},body:b.toString(),credentials:'same-origin'});
        let t=''; try{t=await r.text();}catch(e){}
        return {status:r.status,body:t.slice(0,500)};
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
        cs = []
        for attempt in range(3):
            pg.goto(HOST + "/u/student/study/myCourseTheme.action",
                    wait_until="commit", timeout=60000)
            pg.wait_for_timeout(9000)
            cs = pg.evaluate(PARSE, "enterCourse")
            out("尝试%d: enterCourse=%d url=%s" % (attempt + 1, len(cs), pg.url[:100]))
            if cs:
                break
        if not cs:
            pg.goto(HOST + "/cms/courseMarketNew.htm",
                    wait_until="commit", timeout=60000)
            pg.wait_for_timeout(8000)
            cs = pg.evaluate(PARSE, "enterCourseTimeLimit")
            out("课程中心兜底: enterCourseTimeLimit=%d" % len(cs))
        if not cs:
            out("BODY(前300): %s" % pg.evaluate("() => document.body.innerText")[:300])
            return
        c = cs[0]
        with pg.expect_popup(timeout=30000) as pop:
            pg.evaluate("(p)=>window[p.fn].apply(null,p.args)",
                        {"fn": c["fn"], "args": c["args"]})
        lp = pop.value
        lp.wait_for_timeout(8000)
        try:
            lp.get_by_text("课件", exact=True).first.click(timeout=10000)
            out("课件点击 OK")
        except Exception as e:
            out("课件点击失败(%s)，JS 兜底" % str(e)[:90])
            lp.evaluate("""() => {
                const es=[...document.querySelectorAll('*')].filter(
                    e=>e.children.length===0 && (e.textContent||'').trim()==='课件');
                if(es[0]) es[0].click();
            }""")
        for i in range(24):
            if any("content_webCourseware" in f.url for f in lp.frames):
                break
            lp.wait_for_timeout(1500)
        out("--- frames after 课件 ---")
        for f in lp.frames:
            out("  FRAME %s" % f.url[:185])

        cid_full = None
        item_id = None
        duration = 0
        for f in lp.frames:
            m = re.search(r"params\.courseId=([^&]+)", f.url)
            if m and not cid_full:
                cid_full = m.group(1)
            m2 = re.search(r"params\.itemId=([^&]+)", f.url)
            if m2 and not item_id:
                item_id = m2.group(1)
            if "kjcourse-cmatc.cma.cn" in f.url and not duration:
                with contextlib.suppress(Exception):
                    duration = f.evaluate("""() => {
                        try { return Math.ceil(player.getDuration()); } catch(e) { return 0; }
                    }""")
        if not item_id:
            for f in lp.frames:
                if "courseware_index" in f.url:
                    with contextlib.suppress(Exception):
                        item_id = f.evaluate("""() => {
                            const e=document.querySelector('[id^="s_point_"]');
                            return e ? e.id.replace('s_point_','') : null;
                        }""")
        if not duration:
            for f in lp.frames:
                if "kjcourse-cmatc.cma.cn" in f.url:
                    with contextlib.suppress(Exception):
                        duration = f.evaluate("""() => {
                            try { return Math.ceil(player.getDuration()); } catch(e) { return 0; }
                        }""")
        cid = cid_full.split("___")[0] if cid_full else ""
        out("courseId(full)=%s  courseId=%s  itemId=%s  duration=%s"
            % (cid_full, cid, item_id, duration))
        if not item_id:
            out("ERROR: 未取到 itemId")
            return
        import math
        try:
            d = int(duration) if duration and not (
                isinstance(duration, float) and math.isnan(duration)) else 0
        except Exception:
            d = 0
        big = max(d, 3600)
        out("拟提交 videoTime=%s (duration=%s)" % (big, duration))

        def post(url, data):
            return lp.evaluate(POST, {"url": url, "data": data})

        out("\n--- 提交前完成状态 ---")
        out(str(post(COMPLETE, {"params.courseId": cid_full,
                                "params.itemId": item_id}))[:400])
        out(str(post(QUERY_ITEM, {"params.courseId": cid}))[:400])

        for label, cidv in [("带___", cid_full), ("不带___", cid)]:
            out("\n--- saveLearningItem (%s) ---" % label)
            r = post(SAVE, {"params.courseId": cidv,
                            "params.itemId": item_id,
                            "params.videoTime": str(big)})
            out("SAVE: %s" % json.dumps(r, ensure_ascii=False)[:500])
            out("COMPLETE: %s" % json.dumps(post(COMPLETE, {
                "params.courseId": cid_full, "params.itemId": item_id}),
                ensure_ascii=False)[:400])
            out("QUERY_ITEM: %s" % json.dumps(post(QUERY_ITEM, {
                "params.courseId": cid}), ensure_ascii=False)[:400])

        out("\n--- 主站学时/进度复核 ---")
        pg.goto(HOST + "/u/student/study/myCourse.action",
                wait_until="commit", timeout=60000)
        pg.wait_for_timeout(8000)
        t = pg.evaluate("() => document.body.innerText")
        mm = re.search(r"本年度完成学时[^\d]{0,20}(\d+(?:\.\d+)?)", t)
        out("本年度完成学时: %s" % (mm.group(1) if mm else "读取失败"))
        out("课程进度片段: %s" % re.findall(r"学习进度[：:]\s*[\d.]+%", t)[:5])
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
