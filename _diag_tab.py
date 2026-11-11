# -*- coding: utf-8 -*-
"""只读诊断：验证「我的自选课」页的 全部/未完成/已完成 筛选是否可直接用作待学清单。

不点 enterCourse、不选课、不打开学习页、不写任何学习记录。
输出：_diag_tab_out.txt
"""
import json
from common import start, login, close, HOST

MY = HOST + "/u/student/study/myCourse.action"
OUT = "_diag_tab_out.txt"

TAB_JS = r"""() => {
    const out = [];
    for (const e of document.querySelectorAll('a,li,span,div,button')) {
        const t = (e.textContent || '').trim();
        if (t === '未完成' || t === '已完成' || t === '全部') {
            out.push({tag: e.tagName, t: t, html: e.outerHTML.slice(0, 400),
                      parent: ((e.parentElement || {}).outerHTML || '').slice(0, 700)});
        }
    }
    return out.slice(0, 24);
}"""

CLICK_TAB_JS = r"""(t) => {
    const es = [...document.querySelectorAll('a,li,span,div,button')]
        .filter(e => (e.textContent || '').trim() === t);
    const e = es[es.length - 1];           // 取最深层、最精确的那个元素
    if (!e) return 'NOT_FOUND';
    e.click();
    return 'CLICKED ' + e.tagName + ' :: ' + e.outerHTML.slice(0, 220);
}"""

STATE_JS = r"""() => {
    const body = (document.body.innerText || '').replace(/\s+/g, ' ');
    const cards = [...document.querySelectorAll('a[onclick]')]
        .filter(a => (a.getAttribute('onclick') || '').indexOf('enterCourse(') >= 0)
        .map(a => {
            let box = a;
            for (let i = 0; i < 6 && box.parentElement; i++) {
                box = box.parentElement;
                if (/学习进度/.test(box.innerText || '')) break;
            }
            const t = (box.innerText || '').replace(/\s+/g, ' ');
            const pm = t.match(/学习进度[:：]\s*([\d.]+)\s*%/);
            const oc = a.getAttribute('onclick') || '';
            const cm = oc.match(/courseId=([^&']+)/);
            const args = (oc.match(/'([^']*)'/g) || []).map(s => s.slice(1, -1));
            return {cid: cm ? cm[1] : '', pct: pm ? parseFloat(pm[1]) : null,
                    btn: (a.textContent || '').trim().slice(0, 12),
                    oid: args.find(x => /^[0-9a-fA-F]{24,40}$/.test(x) && x !== (cm ? cm[1] : '')) || ''};
        });
    return {url: location.href, cards: cards,
            pager: (body.match(/共\s*\d+\s*页/) || [])[0] || null,
            progressLabels: body.match(/学习进度[:：]\s*[\d.]+\s*%/g) || [],
            bodyHead: body.slice(0, 400), bodyTail: body.slice(-260)};
}"""


def main():
    f = open(OUT, "w", encoding="utf-8")
    pw, browser, ctx, pg = start()
    try:
        login(pg)
        pg.goto(MY, wait_until="commit", timeout=60000)
        pg.wait_for_timeout(5000)
        tabs = pg.evaluate(TAB_JS)
        print("=== TAB elements ===", flush=True)
        print(json.dumps(tabs, ensure_ascii=False, indent=1)[:6000], flush=True)
        f.write("=== TAB elements ===\n" + json.dumps(tabs, ensure_ascii=False, indent=1) + "\n")

        for label in ("全部（初始）", "未完成", "已完成", "全部（回切）"):
            if label == "未完成":
                r = pg.evaluate(CLICK_TAB_JS, "未完成")
                print("click 未完成 ->", r, flush=True)
                pg.wait_for_timeout(3500)
            elif label == "已完成":
                r = pg.evaluate(CLICK_TAB_JS, "已完成")
                print("click 已完成 ->", r, flush=True)
                pg.wait_for_timeout(3500)
            elif label == "全部（回切）":
                r = pg.evaluate(CLICK_TAB_JS, "全部")
                print("click 全部 ->", r, flush=True)
                pg.wait_for_timeout(3500)
            st = pg.evaluate(STATE_JS)
            summary = {"tab": label, "课程数": len(st["cards"]),
                       "进度分布": {}, "分页": st["pager"],
                       "progressLabels": len(st["progressLabels"]),
                       "url": st["url"],
                       "cards": [{"cid": c["cid"][-6:], "pct": c["pct"],
                                  "btn": c["btn"], "oid": c["oid"][:8]} for c in st["cards"]]}
            for c in st["cards"]:
                k = str(c["pct"])
                summary["进度分布"][k] = summary["进度分布"].get(k, 0) + 1
            print("\n=== %s ===\n%s" % (label, json.dumps(summary, ensure_ascii=False, indent=1)[:5000]), flush=True)
            f.write("\n=== %s ===\n%s\n" % (label, json.dumps(st, ensure_ascii=False, indent=1)))
    finally:
        f.close()
        close(pw, browser, ctx)


if __name__ == "__main__":
    main()
