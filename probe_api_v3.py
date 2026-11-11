# -*- coding: utf-8 -*-
"""
只读深度探查：定位 SCORM window.API 所在的 frame、LMSCommit 的真实上报格式。
不做任何写入/提交，不改动学时。登录一次，打开一门课，观察后退出。
输出：probe_api_v3_out.txt / probe_api_v3_requests.log
"""
import os, re, json, time, datetime, contextlib
from playwright.sync_api import sync_playwright
from common import EDGE, HOST, OUT, ARGS, login

OUT_TXT = os.path.join(OUT, "probe_api_v3_out.txt")
REQ_LOG = os.path.join(OUT, "probe_api_v3_requests.log")
_buf = []


def out(s):
    s = str(s)
    print(s, flush=True)
    _buf.append(s)


def dump_frames(lp, tag):
    out("\n--- FRAMES [%s] ---" % tag)
    for f in lp.frames:
        out("   name=%-16s url=%s" % (f.name[:16], f.url[:175]))


PROBE = r"""() => {
  const r = {};
  r.url = location.href.slice(0, 155);
  r.hasAPI = !!window.API;
  r.hasAPI1484 = !!window.API_1484_11;
  r.doLMSSet = typeof window.doLMSSetValue;
  r.doLMSCommit = typeof window.doLMSCommit;
  r.getAPIHandle = typeof window.getAPIHandle;
  r.findAPI = typeof window.findAPI;
  r.player = typeof window.player;
  r.APIkeys = window.API ? Object.keys(window.API).slice(0, 30) : [];
  if (window.API && window.API.LMSCommit) {
    try { r.commitSrc = String(window.API.LMSCommit).slice(0, 1100); } catch(e) {}
  }
  if (window.API && window.API.LMSSetValue) {
    try { r.setSrc = String(window.API.LMSSetValue).slice(0, 700); } catch(e) {}
  }
  if (window.API && window.API.LMSGetValue) {
    try { r.lessonStatus = window.API.LMSGetValue('cmi.core.lesson_status'); }
    catch(e) { r.getErr = String(e).slice(0, 90); }
    try { r.sessionTime = window.API.LMSGetValue('cmi.core.session_time'); } catch(e) {}
  }
  return r;
}"""


PARSE_ARGS_JS = r"""(fnName) => {
    const out = [];
    document.querySelectorAll('a[onclick]').forEach(a => {
        const oc = a.getAttribute('onclick') || '';
        if (oc.indexOf(fnName + '(') < 0) return;
        const start = oc.indexOf(fnName + '(') + fnName.length + 1;
        const body = oc.slice(start, oc.lastIndexOf(')') + 1);
        const args = [];
        const re = /'([^']*)'|"([^"]*)"/g;
        let m;
        while ((m = re.exec(body)) !== null) args.push(m[1] !== undefined ? m[1] : m[2]);
        if (args.length) out.push({fn: fnName, args: args, url: args[0]});
    });
    return out;
}"""


def main():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(executable_path=EDGE, headless=True, args=ARGS)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              ignore_https_errors=True)
    pg = ctx.new_page()
    pg.set_default_timeout(25000)
    lp = None
    try:
        out("登录中...")
        login(pg, verbose=False)
        out("登录完成: %s" % pg.url)

        pg.goto(HOST + "/u/student/study/myCourseTheme.action",
                wait_until="commit", timeout=60000)
        pg.wait_for_timeout(8000)
        out("我的课程 URL: %s" % pg.url)

        courses = pg.evaluate(PARSE_ARGS_JS, "enterCourse")
        out("找到 enterCourse 链接: %d" % len(courses))
        c = None
        if courses:
            c = courses[0]
        else:
            pg.goto(HOST + "/cms/courseMarketNew.htm",
                    wait_until="commit", timeout=60000)
            pg.wait_for_timeout(6000)
            alt = pg.evaluate(PARSE_ARGS_JS, "enterCourseTimeLimit")
            out("课程中心 enterCourseTimeLimit 链接: %d" % len(alt))
            if alt:
                c = alt[0]
        if not c:
            out("ERROR: 未找到任何可进入学习的课程链接")
            return
        out("选用: %s %s" % (c["fn"], c["url"][:150]))

        out("\n调用 %s 打开学习页..." % c["fn"])
        with pg.expect_popup(timeout=30000) as pop:
            pg.evaluate("(p) => window[p.fn].apply(null, p.args)",
                        {"fn": c["fn"], "args": c["args"]})
        lp = pop.value
        lp.set_default_timeout(25000)

        # 记录学习页(pxkckj 域)自身的请求
        def on_req(req):
            try:
                if req.method in ("POST", "PUT", "GET"):
                    pd = ""
                    try:
                        pd = (req.post_data or "")[:500]
                    except Exception:
                        pass
                    with open(REQ_LOG, "a", encoding="utf-8") as f:
                        f.write("%s REQ %s %s | %s\n" % (
                            datetime.datetime.now().strftime("%H:%M:%S"),
                            req.method, req.url[:260], pd.replace("\n", " ")))
            except Exception:
                pass

        def on_res(resp):
            try:
                body = ""
                try:
                    body = resp.text()[:260]
                except Exception:
                    pass
                with open(REQ_LOG, "a", encoding="utf-8") as f:
                    f.write("%s RES %s %s | %s\n" % (
                        datetime.datetime.now().strftime("%H:%M:%S"),
                        resp.status, resp.url[:220], body.replace("\n", " ")))
            except Exception:
                pass

        lp.on("request", on_req)
        lp.on("response", on_res)

        lp.wait_for_timeout(9000)
        out("LEARN URL: %s" % lp.url)
        dump_frames(lp, "initial(9s)")

        out("\n点击「课件」tab...")
        try:
            lp.get_by_text("课件", exact=True).first.click(timeout=10000)
            out("  课件点击 OK")
        except Exception as e:
            out("  课件点击失败(%s)，用 JS 兜底" % str(e)[:90])
            lp.evaluate("""() => {
                const es=[...document.querySelectorAll('*')].filter(
                    e=>e.children.length===0 && (e.textContent||'').trim()==='课件');
                if(es[0]) es[0].click();
            }""")
        lp.wait_for_timeout(8000)
        dump_frames(lp, "after 课件(8s)")

        out("\n=== 逐 frame 探测 window.API ===")
        for i, f in enumerate(lp.frames):
            try:
                r = f.evaluate(PROBE)
                out("FRAME%d %s" % (i, json.dumps(r, ensure_ascii=False)[:2200]))
            except Exception as e:
                out("FRAME%d ERR %s" % (i, str(e)[:120]))

        out("\n点击课件内「开始学习」...")
        for f in lp.frames:
            try:
                loc = f.get_by_text("开始学习", exact=True)
                if loc.count():
                    loc.first.click(timeout=4000)
                    out("  clicked in %s" % f.url[:100])
            except Exception:
                pass
        lp.wait_for_timeout(8000)
        dump_frames(lp, "after 开始学习(8s)")

        out("\n=== 再次探测 (after 开始学习) ===")
        for i, f in enumerate(lp.frames):
            try:
                r = f.evaluate(PROBE)
                if r.get("hasAPI") or r.get("doLMSSet") != "undefined" or r.get("player") != "undefined":
                    out("FRAME%d %s" % (i, json.dumps(r, ensure_ascii=False)[:2200]))
            except Exception:
                pass

        out("\n观察 25 秒自然请求（不写入、不提交）...")
        lp.wait_for_timeout(25000)

        # 回主站读一次学时（只读）
        pg.goto(HOST + "/u/student/study/myCourse.action",
                wait_until="commit", timeout=60000)
        pg.wait_for_timeout(5000)
        try:
            t = pg.evaluate("() => document.body.innerText")
            m = re.search(r"本年度完成学时[^\d]{0,20}(\d+(?:\.\d+)?)", t)
            out("\n本年度完成学时(只读复核): %s" % (m.group(1) if m else "读取失败"))
        except Exception as e:
            out("学时复核失败: %s" % str(e)[:100])
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
