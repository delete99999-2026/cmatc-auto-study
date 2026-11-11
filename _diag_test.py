# -*- coding: utf-8 -*-
"""只读诊断：抓「课后自测题」节点的页面 DOM / 接口结构。

不提交任何答案、不点提交按钮、不写完成状态、不写学时。
只做：登录 -> 打开目标课程学习页 -> 点课件菜单里的 test 节点 -> 抓帧/表单/接口。
"""
import os, sys, json, re, time

os.environ.setdefault("CMATC_DRY", "1")
import common
import steady_study_fixed as S

OUT = os.path.join(common.OUT, "_diag_test_out.txt")
CID_TAIL = "dc04a9"
LINES = []


def w(s=""):
    s = str(s)
    LINES.append(s)
    print(s, flush=True)


DUMP_JS = r"""() => {
    const txt = s => String(s || '').replace(/\s+/g, ' ').trim();
    const inputs = [...document.querySelectorAll('input,textarea,select')].map(e => ({
        tag: e.tagName.toLowerCase(), type: e.type || '', name: e.name || '',
        id: e.id || '', cls: (e.className || '').toString().slice(0, 70),
        value: (e.value || '').slice(0, 60), checked: !!e.checked,
        placeholder: e.placeholder || '', onclick: (e.getAttribute('onclick') || '').slice(0, 160)
    }));
    const btns = [...document.querySelectorAll('button, a, [onclick], input[type=button], input[type=submit]')]
        .map(e => ({
            tag: e.tagName.toLowerCase(), type: e.type || '',
            text: txt(e.textContent || e.value || '').slice(0, 60),
            id: e.id || '', cls: (e.className || '').toString().slice(0, 60),
            onclick: (e.getAttribute('onclick') || '').slice(0, 200),
            href: (e.getAttribute('href') || '').slice(0, 160)
        }))
        .filter(x => x.text || x.onclick || x.id)
        .slice(0, 90);
    const forms = [...document.querySelectorAll('form')].map(f => ({
        id: f.id || '', action: f.action || '', method: f.method || '',
        name: f.name || ''
    }));
    const frames = [...document.querySelectorAll('iframe,frame')].map(f => ({
        id: f.id || '', name: f.name || '', src: (f.getAttribute('src') || '').slice(0, 220)
    }));
    const points = [...document.querySelectorAll('.s_point')].map((p, i) => ({
        i: i, id: p.id || '', cls: p.className || '',
        completestate: p.getAttribute('completestate') || '',
        onclick: (p.getAttribute('onclick') || '').slice(0, 220),
        attrs: [...p.attributes].map(a => a.name + '=' + String(a.value).slice(0, 90)).slice(0, 24),
        text: txt(p.textContent || '').slice(0, 80),
        html: (p.outerHTML || '').slice(0, 900)
    }));
    return {
        url: location.href, title: document.title || '',
        bodyText: txt(document.body ? document.body.innerText : '').slice(0, 3500),
        inputs: inputs.slice(0, 120), btns: btns, forms: forms, frames: frames,
        points: points,
        questionLike: [...document.querySelectorAll('[class*="question"],[class*="timu"],[class*="option"],[class*="answer"],[class*="exam"],[class*="test"]')]
            .slice(0, 30).map(e => ({tag: e.tagName.toLowerCase(),
                cls: (e.className || '').toString().slice(0, 90),
                text: txt(e.textContent || '').slice(0, 120)}))
    };
}"""


def dump_frames(lp, label):
    w("\n########## FRAMES %s ##########" % label)
    for i, f in enumerate(lp.frames):
        try:
            d = f.evaluate(DUMP_JS)
        except Exception as e:
            w("  FRAME%d ERR %s | %s" % (i, str(e)[:100], (f.url or "")[:160]))
            continue
        w("  ---- FRAME%d %s ----" % (i, (f.url or "")[:220]))
        w("  title=%r body=%r" % (d.get("title"), d.get("bodyText", "")[:700]))
        w("  json=" + json.dumps({k: v for k, v in d.items()
                                  if k not in ("bodyText",)}, ensure_ascii=False)[:14000])
        try:
            html = f.content()
            p = os.path.join(common.OUT, "_diag_test_%s_f%d.html" % (label, i))
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(html)
            w("  html -> %s (%d chars)" % (os.path.basename(p), len(html)))
        except Exception as e:
            w("  html err " + str(e)[:80])


def main():
    pw, browser, ctx, pg = common.start()
    net = []

    def attach(page, label):
        def on_req(req):
            u = req.url
            if re.search(r"test|exam|question|paper|quiz|answer|item|save", u, re.I):
                try:
                    pd = (req.post_data or "")[:1500]
                except Exception:
                    pd = ""
                net.append("%s REQ %s %s | %s" % (label, req.method, u[:300], pd))

        def on_res(resp):
            u = resp.url
            if re.search(r"test|exam|question|paper|quiz|answer|item", u, re.I):
                body = ""
                try:
                    if resp.request.method != "GET" or not re.search(
                            r"\.(js|css|png|jpg|gif|mp4|flv|woff|ico)(\?|$)", u, re.I):
                        body = resp.text()[:20000]
                except Exception as e:
                    body = "ERR:" + str(e)[:80]
                net.append("%s RES %s %s | %s" % (label, resp.status, u[:300], body))

        page.on("request", on_req)
        page.on("response", on_res)

    try:
        common.login(pg)
        attach(pg, "PG")
        w("LOGIN OK " + pg.url)
        pool = S.build_course_pool(pg, 40)
        course = next((c for c in pool
                       if (c.get("cid") or "").endswith(CID_TAIL)), None)
        if not course:
            w("NOT FOUND cid tail " + CID_TAIL)
            return
        w("COURSE " + json.dumps({k: course.get(k) for k in
                                  ("cid", "name", "fn", "args", "pct", "todo")},
                                 ensure_ascii=False)[:1200])
        lp, how = S.open_learnspace(pg, ctx, course, "diag", None)
        if lp is None:
            w("NO LEARN PAGE")
            return
        attach(lp, "LP")
        w("LEARN PAGE %s %s" % (how, lp.url[:180]))
        S.click_courseware_tab(lp, "diag")
        S.wait_sco_frame(lp, 20)
        w("NODE INFO before: " + json.dumps(S.node_info(lp), ensure_ascii=False))
        dump_frames(lp, "before")

        mf = S.menu_frame(lp)
        if mf is None:
            w("NO MENU FRAME")
        else:
            info = S.node_info(lp) or {}
            total = info.get("total") or 0
            # 优先点最后一个节点（通常就是课后自测题），也把所有未完成的点一遍试试
            idxs = [total - 1] if total else []
            w("CLICK NODE IDX %s" % idxs)
            for idx in idxs:
                try:
                    r = mf.evaluate(S.CLICK_NODE_JS, idx)
                    w("CLICK RESULT " + json.dumps(r, ensure_ascii=False))
                except Exception as e:
                    w("CLICK ERR " + str(e)[:150])
                lp.wait_for_timeout(9000)
                dump_frames(lp, "after%d" % idx)
                w("NODE INFO after: " + json.dumps(S.node_info(lp), ensure_ascii=False))

        for p in ctx.pages:
            w("CTX PAGE " + (p.url or "")[:220])
    finally:
        w("\n########## NETWORK ##########")
        for l in net:
            w(l[:20000])
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(LINES))
        w("OUT -> " + OUT)
        common.close(pw, browser, ctx)


if __name__ == "__main__":
    main()
