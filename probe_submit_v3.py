# -*- coding: utf-8 -*-
"""
受控实验：验证 learningTime_saveLearningTime.action 能否直接累加学习时长。
只加 CMATC_ADD 秒（默认 600），观察响应、learnTime 变化、以及主站学时变化。
输出 probe_submit_v3_out.txt
"""
import os, re, json, contextlib
from playwright.sync_api import sync_playwright
from common import EDGE, HOST, OUT, ARGS, login

ADD = int(os.environ.get("CMATC_ADD", "600"))
HOST2 = "https://pxkckj-cmatc.cma.cn"
SAVE = HOST2 + "/learnspace/course/study/learningTime_saveLearningTime.action"
QUERY = HOST2 + "/learnspace/course/study/learningTime_queryLearningTime.action"
OUT_TXT = os.path.join(OUT, "probe_submit_v3_out.txt")
_buf = []


def out(s):
    s = str(s)
    print(s, flush=True)
    _buf.append(s)


PARSE_ARGS_JS = r"""(fnName) => {
    const out = [];
    document.querySelectorAll('a[onclick]').forEach(a => {
        const oc = a.getAttribute('onclick') || '';
        if (oc.indexOf(fnName + '(') < 0) return;
        const start = oc.indexOf(fnName + '(') + fnName.length + 1;
        const body = oc.slice(start, oc.lastIndexOf(')') + 1);
        const args = [], re = /'([^']*)'|"([^"]*)"/g;
        let m;
        while ((m = re.exec(body)) !== null) args.push(m[1] !== undefined ? m[1] : m[2]);
        if (args.length) out.push({fn: fnName, args: args, url: args[0]});
    });
    return out;
}"""

POST_JS = r"""async (p) => {
    const body = new URLSearchParams();
    body.append('courseId', p.courseId);
    if (p.withStudyTime) body.append('studyTime', String(p.studyTime));
    if (p.limitId !== null && p.limitId !== undefined) body.append('limitId', String(p.limitId));
    try {
        const r = await fetch(p.url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: body.toString(),
            credentials: 'same-origin'
        });
        let t = '';
        try { t = await r.text(); } catch(e) {}
        return {status: r.status, body: t.slice(0, 600)};
    } catch (e) {
        return {error: String(e).slice(0, 200)};
    }
}"""


def main():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(executable_path=EDGE, headless=True, args=ARGS)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              ignore_https_errors=True)
    pg = ctx.new_page()
    pg.set_default_timeout(25000)
    try:
        out("登录中...")
        login(pg, verbose=False)
        out("登录完成: %s" % pg.url)

        pg.goto(HOST + "/u/student/study/myCourseTheme.action",
                wait_until="commit", timeout=60000)
        pg.wait_for_timeout(7000)
        courses = pg.evaluate(PARSE_ARGS_JS, "enterCourse")
        out("enterCourse 链接: %d" % len(courses))
        if not courses:
            pg.goto(HOST + "/cms/courseMarketNew.htm",
                    wait_until="commit", timeout=60000)
            pg.wait_for_timeout(6000)
            courses = pg.evaluate(PARSE_ARGS_JS, "enterCourseTimeLimit")
        if not courses:
            out("ERROR: 无可用课程")
            return
        c = courses[0]
        with pg.expect_popup(timeout=30000) as pop:
            pg.evaluate("(p) => window[p.fn].apply(null, p.args)",
                        {"fn": c["fn"], "args": c["args"]})
        lp = pop.value
        lp.set_default_timeout(25000)
        lp.wait_for_timeout(8000)

        # 点「课件」tab 让 iframe 链加载
        try:
            lp.get_by_text("课件", exact=True).first.click(timeout=10000)
        except Exception:
            lp.evaluate("""() => {
                const es=[...document.querySelectorAll('*')].filter(
                    e=>e.children.length===0 && (e.textContent||'').trim()==='课件');
                if(es[0]) es[0].click();
            }""")
        lp.wait_for_timeout(7000)
        out("LEARN URL: %s" % lp.url)

        info = lp.evaluate("""() => {
            const u = new URL(location.href);
            const top = window.top || window;
            return {
                courseId: u.searchParams.get('params.courseId'),
                limitId: (typeof top.limitId !== 'undefined' ? top.limitId : null),
                selfLimitId: (typeof window.limitId !== 'undefined' ? window.limitId : null),
                limitInputs: [...document.querySelectorAll('input')].filter(
                    e=>/limit/i.test(e.id||e.name||'')).map(
                    e=>({id:e.id,name:e.name,value:e.value})).slice(0,10),
                hasStudyTime: (window.jQuery && typeof jQuery.studyTime)
            };
        }""")
        out("页面参数: %s" % json.dumps(info, ensure_ascii=False)[:600])
        cid = info.get("courseId")
        limit = info.get("limitId") if info.get("limitId") is not None else info.get("selfLimitId")
        if not cid:
            out("ERROR: 未取到 courseId")
            return

        out("\n--- 1) 查询当前 learnTime ---")
        q0 = lp.evaluate(POST_JS, {"url": QUERY, "courseId": cid,
                                   "withStudyTime": False, "limitId": None})
        out("QUERY: %s" % json.dumps(q0, ensure_ascii=False)[:400])
        m = re.search(r'"learnTime"\s*:\s*"?(\d+)', q0.get("body", ""))
        before = int(m.group(1)) if m else 0
        out("当前 learnTime = %s 秒" % before)

        out("\n--- 2) 提交 studyTime = %s (+%s 秒) ---" % (before + ADD, ADD))
        s1 = lp.evaluate(POST_JS, {"url": SAVE, "courseId": cid,
                                   "withStudyTime": True,
                                   "studyTime": before + ADD,
                                   "limitId": limit})
        out("SAVE : %s" % json.dumps(s1, ensure_ascii=False)[:600])

        out("\n--- 3) 再次查询 learnTime ---")
        q1 = lp.evaluate(POST_JS, {"url": QUERY, "courseId": cid,
                                   "withStudyTime": False, "limitId": None})
        out("QUERY: %s" % json.dumps(q1, ensure_ascii=False)[:400])
        m2 = re.search(r'"learnTime"\s*:\s*"?(\d+)', q1.get("body", ""))
        after = int(m2.group(1)) if m2 else -1
        out("提交后 learnTime = %s 秒 (变化 %s)" % (after, after - before))

        out("\n--- 4) 回主站读本年度完成学时 ---")
        pg.goto(HOST + "/u/student/study/myCourse.action",
                wait_until="commit", timeout=60000)
        pg.wait_for_timeout(6000)
        try:
            t = pg.evaluate("() => document.body.innerText")
            mm = re.search(r"本年度完成学时[^\d]{0,20}(\d+(?:\.\d+)?)", t)
            out("本年度完成学时: %s" % (mm.group(1) if mm else "读取失败"))
        except Exception as e:
            out("读取失败: %s" % str(e)[:100])
        out("\nDONE")
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
