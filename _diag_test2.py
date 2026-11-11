# -*- coding: utf-8 -*-
"""只读诊断 2：抓测试页 JS + 打开自测题试卷页看题目 DOM（不提交答案）。"""
import os, re, json
os.environ.setdefault("CMATC_DRY", "1")
import common
import steady_study_fixed as S

JS_FILES = [
    "/learnspace/resource/test/scripts/test_page_operation.js?a=20230516",
    "/learnspace/resource/test/scripts/test_student_operation.js",
    "/learnspace/resource/test/scripts/test_common.js",
]
OUT = os.path.join(common.OUT, "_diag_test2_out.txt")
LINES = []


def w(s=""):
    LINES.append(str(s))
    print(str(s), flush=True)


DUMP_JS = r"""() => {
    const txt = s => String(s || '').replace(/\s+/g, ' ').trim();
    const q = [...document.querySelectorAll('input')].map(e => ({
        tag: 'input', type: e.type, name: e.name, id: e.id,
        cls: (e.className || '').toString().slice(0, 80),
        value: (e.value || '').slice(0, 80), checked: e.checked,
        onclick: (e.getAttribute('onclick') || '').slice(0, 140)
    }));
    const els = [...document.querySelectorAll('a,button,div[onclick],span[onclick],label')]
        .map(e => ({tag: e.tagName.toLowerCase(), id: e.id || '',
                    cls: (e.className || '').toString().slice(0, 70),
                    text: txt(e.textContent || '').slice(0, 90),
                    onclick: (e.getAttribute('onclick') || '').slice(0, 160),
                    href: (e.getAttribute('href') || '').slice(0, 140)}))
        .filter(x => x.text || x.onclick || x.id).slice(0, 100);
    const qblocks = [...document.querySelectorAll('[class*="question"],[class*="timu"],[class*="option"],[class*="test_paper"],[class*="bank_"],[id*="question"],[id*="option"]')]
        .slice(0, 60).map(e => ({tag: e.tagName.toLowerCase(),
            cls: (e.className || '').toString().slice(0, 90),
            id: e.id || '', text: txt(e.textContent || '').slice(0, 260)}));
    return {url: location.href, title: document.title,
            bodyText: txt(document.body ? document.body.innerText : '').slice(0, 4500),
            inputs: q.slice(0, 150), els: els, qblocks: qblocks,
            iframes: [...document.querySelectorAll('iframe,frame')].map(f => ({
                id: f.id, src: (f.getAttribute('src') || '').slice(0, 220)}))};
}"""


def dump(lp, label):
    w("\n########## FRAMES %s ##########" % label)
    for i, f in enumerate(lp.frames):
        try:
            d = f.evaluate(DUMP_JS)
        except Exception as e:
            w("  F%d ERR %s %s" % (i, str(e)[:90], (f.url or "")[:140]))
            continue
        w("  ---- F%d %s ----" % (i, (f.url or "")[:230]))
        w("  title=%s body=%r" % (d.get("title"), d.get("bodyText", "")[:900]))
        w("  json=" + json.dumps(d, ensure_ascii=False)[:16000])
        try:
            html = f.content()
            p = os.path.join(common.OUT, "_diag_test2_%s_f%d.html" % (label, i))
            open(p, "w", encoding="utf-8").write(html)
            w("  html->%s (%d)" % (os.path.basename(p), len(html)))
        except Exception as e:
            w("  htmlerr " + str(e)[:70])


def main():
    pw, browser, ctx, pg = common.start()
    net = []
    def attach(page, label):
        def on_req(req):
            if re.search(r"test|exam|paper|answer|question|item|save|submit", req.url, re.I):
                try: pd = (req.post_data or "")[:2000]
                except Exception: pd = ""
                net.append("%s REQ %s %s | %s" % (label, req.method, req.url[:280], pd))
        def on_res(resp):
            if re.search(r"test|exam|paper|answer|question|item", resp.url, re.I) and \
               not re.search(r"\.(js|css|png|jpg|gif|woff|ico)(\?|$)", resp.url, re.I):
                b = ""
                try: b = resp.text()[:12000]
                except Exception as e: b = "ERR" + str(e)[:60]
                net.append("%s RES %s %s | %s" % (label, resp.status, resp.url[:280], b))
        page.on("request", on_req)
        page.on("response", on_res)
    try:
        common.login(pg)
        attach(pg, "PG")
        pool = S.build_course_pool(pg, 40)
        course = next((c for c in pool if (c.get("cid") or "").endswith("dc04a9")), None)
        w("COURSE " + (course.get("cid") if course else "NONE"))
        lp, how = S.open_learnspace(pg, ctx, course, "diag", None)
        attach(lp, "LP")
        S.click_courseware_tab(lp, "diag")
        lp.wait_for_timeout(4000)
        mf = S.menu_frame(lp)
        info = S.node_info(lp) or {}
        w("NODE " + json.dumps(info, ensure_ascii=False))
        # 点最后一个 test 节点
        mf.evaluate(S.CLICK_NODE_JS, (info.get("total") or 4) - 1)
        lp.wait_for_timeout(6000)

        # 抓 JS 源码（同源 GET，只读）
        for u in JS_FILES:
            try:
                r = lp.evaluate("async (u) => { const x = await fetch(u); return {s:x.status, t:(await x.text())}; }", u)
                p = os.path.join(common.OUT, "_diag_js_" + os.path.basename(u.split("?")[0]))
                open(p, "w", encoding="utf-8").write(r["t"])
                w("JS %s status=%s len=%d -> %s" % (u, r["s"], len(r["t"]), os.path.basename(p)))
            except Exception as e:
                w("JS ERR %s %s" % (u, str(e)[:120]))

        dump(lp, "testinfo")

        # 找含 redoTestPaper 的 frame，点「再做一遍」打开试卷（不提交）
        for f in lp.frames:
            try:
                has = f.evaluate("() => typeof redoTestPaper === 'function' && !!document.querySelector('.record_submit_redo')")
            except Exception:
                has = False
            if not has:
                continue
            w("REDO FRAME " + (f.url or "")[:160])
            try:
                r = f.evaluate("""() => { try { redoTestPaper(); return 'CALLED'; }
                    catch(e) { return 'ERR:' + String(e).slice(0,120); } }""")
                w("REDO " + r)
            except Exception as e:
                w("REDO EXC " + str(e)[:150])
            lp.wait_for_timeout(9000)
            dump(lp, "paper")
            for p in ctx.pages:
                w("CTXPAGE " + (p.url or "")[:220])
            break
    finally:
        w("\n########## NETWORK ##########")
        for l in net:
            w(l[:12000])
        open(OUT, "w", encoding="utf-8").write("\n".join(LINES))
        w("OUT -> " + OUT)
        common.close(pw, browser, ctx)


if __name__ == "__main__":
    main()
