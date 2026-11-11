# -*- coding: utf-8 -*-
"""受控实测：在当前卡 95.6% 的课程里，真实做完一次自测题并核对进度变化。

这是唯一会写平台数据的诊断：只提交一次「无分数要求」的自测卷，不改学时、
不改完成状态、不快进视频。用于确认做题是否计入进度。
"""
import os, re, json, time
os.environ.setdefault("CMATC_DRY", "1")
import common
import steady_study_fixed as S

OUT = os.path.join(common.OUT, "_diag_test3_out.txt")
LINES = []


def w(s=""):
    LINES.append(str(s))
    print(str(s), flush=True)


ANSWER_JS = r"""() => {
    const n = parseInt((document.getElementById('current_allNum') || {}).value || '0', 10);
    if (!n) return {ok:false, reason:'no_allNum'};
    const detail = [];
    for (let i = 0; i < n; i++) {
        const xs = [...document.getElementsByName('questionInput_' + i)];
        if (!xs.length) { detail.push({i:i, err:'no_input'}); continue; }
        const type = (xs[0].type || '').toLowerCase();
        if (type === 'radio') {
            xs[0].checked = true;
            try { xs[0].dispatchEvent(new Event('change', {bubbles:true})); } catch(e) {}
            detail.push({i:i, type:type, picked:xs[0].value});
        } else if (type === 'checkbox') {
            // 多选至少勾 2 项；无分数要求，取前两项即可
            const k = Math.min(2, xs.length);
            for (let j = 0; j < k; j++) {
                xs[j].checked = true;
                try { xs[j].dispatchEvent(new Event('change', {bubbles:true})); } catch(e) {}
            }
            detail.push({i:i, type:type, picked:xs.slice(0,k).map(x=>x.value).join('')});
        } else {
            detail.push({i:i, type:type, err:'unknown'});
        }
    }
    return {ok:true, n:n, detail:detail,
            myAnswers: (typeof dealUserAnswerToStr === 'function') ? dealUserAnswerToStr() : null};
}"""

FIND_JS = r"""() => ({
    url: location.href,
    title: document.title || '',
    hasPaper: !!document.getElementById('current_allNum'),
    hasRedo: !!document.querySelector('.record_submit_redo'),
    hasSure: !!document.querySelector('.comf_score'),
    bodyText: (document.body ? document.body.innerText : '').replace(/\s+/g,' ').trim().slice(0,400)
})"""


def find_frames(lp):
    out = []
    for f in lp.frames:
        try:
            d = f.evaluate(FIND_JS)
        except Exception:
            continue
        if d.get("hasPaper") or d.get("hasRedo") or "coursewareTest" in (d.get("url") or ""):
            out.append((f, d))
    return out


def prog(pg, cid, tag):
    try:
        p = S.read_progress(pg, cid)
        w("  PROGRESS %s = %s" % (tag, p))
        return p
    except Exception as e:
        w("  PROGRESS %s ERR %s" % (tag, str(e)[:120]))
        return None


def main():
    pw, browser, ctx, pg = common.start()
    net = []
    def attach(page, label):
        def on_req(req):
            if re.search(r"coursewareTest|handSubmit|sureScore|saveOperateLog|queryLearningProgress", req.url, re.I):
                try: pd = (req.post_data or "")[:1500]
                except Exception: pd = ""
                net.append("%s REQ %s %s | %s" % (label, req.method, req.url[:250], pd))
        def on_res(resp):
            if re.search(r"coursewareTest|handSubmit|queryLearningProgress", resp.url, re.I):
                b = ""
                try: b = resp.text()[:3000]
                except Exception as e: b = "ERR" + str(e)[:60]
                net.append("%s RES %s %s | %s" % (label, resp.status, resp.url[:250], b))
        page.on("request", on_req)
        page.on("response", on_res)
    try:
        common.login(pg)
        attach(pg, "PG")
        pool = S.build_course_pool(pg, 40)
        course = next((c for c in pool if (c.get("cid") or "").endswith("dc04a9")), None)
        cid = course["cid"].rstrip("_")
        w("COURSE " + cid)
        p0 = prog(pg, cid, "before")
        lp, how = S.open_learnspace(pg, ctx, course, "diag", None)
        attach(lp, "LP")
        S.click_courseware_tab(lp, "diag")
        lp.wait_for_timeout(3500)

        # 找菜单里的 test 节点并点开
        mf = S.menu_frame(lp)
        tests = mf.evaluate("""() => [...document.querySelectorAll('.s_point')]
            .map((p,i)=>({i:i, id:p.id, type:p.getAttribute('itemtype'),
                          done:p.getAttribute('completestate'),
                          title:p.getAttribute('title')}))""")
        w("MENU " + json.dumps(tests, ensure_ascii=False))
        ti = next((x["i"] for x in tests if x["type"] == "test"), None)
        if ti is None:
            w("NO TEST NODE"); return
        mf.evaluate(S.CLICK_NODE_JS, ti)
        lp.wait_for_timeout(6000)

        frames = find_frames(lp)
        w("TEST FRAMES " + json.dumps([d for _, d in frames], ensure_ascii=False)[:1800])
        tf = next((f for f, d in frames if d.get("hasRedo") or d.get("hasPaper")), None)
        if tf is None:
            w("NO TEST FRAME"); return

        if tf.evaluate("() => !document.getElementById('current_allNum')"):
            w("-> 已有成绩页，点「再做一遍」打开试卷")
            tf.evaluate("() => redoTestPaper()")
            lp.wait_for_timeout(7000)
            frames = find_frames(lp)
            tf = next((f for f, d in frames if d.get("hasPaper")), None)
            if tf is None:
                w("NO PAPER AFTER REDO " + json.dumps([d for _, d in frames], ensure_ascii=False)[:1200])
                return

        ans = tf.evaluate(ANSWER_JS)
        w("ANSWER " + json.dumps(ans, ensure_ascii=False)[:2500])
        lp.wait_for_timeout(2500)
        # 用平台自己的提交函数（会构造表单并跳转到成绩页）
        try:
            r = tf.evaluate("""() => { try { handSubmit(true); return 'CALLED'; }
                                       catch(e) { return 'ERR:'+String(e).slice(0,140); } }""")
            w("SUBMIT " + r)
        except Exception as e:
            w("SUBMIT EXC " + str(e)[:180])
        lp.wait_for_timeout(9000)
        w("AFTER SUBMIT FRAMES " + json.dumps([d for _, d in find_frames(lp)], ensure_ascii=False)[:1800])
        p1 = prog(pg, cid, "after_submit")

        # 若仍未 100%，再点「确定成绩查看答案」并复核
        if p1 is not None and p1 < 99.9:
            frames = find_frames(lp)
            sf = next((f for f, d in frames if d.get("hasSure")), None)
            if sf is not None:
                w("-> 平台仍 %s%%，尝试「确定成绩查看答案」" % p1)
                try:
                    sf.evaluate("() => sureScoreAndQueryAnswer()")
                except Exception as e:
                    w("SURE EXC " + str(e)[:160])
                lp.wait_for_timeout(8000)
                p2 = prog(pg, cid, "after_sure")
            else:
                w("NO SURE LINK; frames=" + json.dumps([d for _, d in frames], ensure_ascii=False)[:1200])
        w("RESULT before=%s after_submit=%s" % (p0, p1))
    finally:
        w("\n########## NETWORK ##########")
        for l in net:
            w(l[:3500])
        open(OUT, "w", encoding="utf-8").write("\n".join(LINES))
        w("OUT -> " + OUT)
        common.close(pw, browser, ctx)


if __name__ == "__main__":
    main()
