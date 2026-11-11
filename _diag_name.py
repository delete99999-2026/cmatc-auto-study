# -*- coding: utf-8 -*-
"""只读诊断：定位「我的课程 / 我的自选课」里【每门课真实名称】所在的 DOM 节点。

不点 enterCourse、不选课、不打开学习页、不写任何学习记录。
输出：_diag_name_out.txt / _diag_name_mycourse.html / _diag_name_undone.html
"""
import json
from common import start, login, close, HOST

MY = HOST + "/u/student/study/myCourse.action"

CHAIN_JS = r"""() => {
    const as = [...document.querySelectorAll('a[onclick]')]
        .filter(a => (a.getAttribute('onclick') || '').indexOf('enterCourse(') >= 0);
    const out = [];
    for (const a of as.slice(0, 4)) {
        const chain = [];
        let e = a;
        for (let i = 0; i < 9 && e; i++, e = e.parentElement) {
            chain.push({i: i, tag: e.tagName,
                        cls: String(e.className || '').slice(0, 100),
                        id: e.id || '',
                        txt: (e.innerText || '').replace(/\s+/g, ' ').slice(0, 350),
                        html: i >= 2 ? (e.outerHTML || '').slice(0, 3000) : ''});
        }
        out.push({oc: (a.getAttribute('onclick') || '').slice(0, 200), chain: chain});
    }
    return out;
}"""

TITLES_JS = r"""() => {
    const out = [];
    document.querySelectorAll('[title]').forEach(e => {
        const t = (e.getAttribute('title') || '').trim();
        if (t) out.push({tag: e.tagName, cls: String(e.className || '').slice(0, 60),
                         title: t.slice(0, 200), text: (e.innerText || '').replace(/\s+/g, ' ').slice(0, 120)});
    });
    return out.slice(0, 60);
}"""

SEECOURSE_JS = r"""() => {
    return [...document.querySelectorAll('a[onclick]')]
        .filter(a => (a.getAttribute('onclick') || '').indexOf('seeCourse(') >= 0)
        .slice(0, 4)
        .map(a => ({oc: (a.getAttribute('onclick') || '').slice(0, 200),
                    self: (a.outerHTML || '').slice(0, 1200),
                    parent: ((a.parentElement || {}).outerHTML || '').slice(0, 2500),
                    grand: (((a.parentElement || {}).parentElement || {}).outerHTML || '').slice(0, 3000)}));
}"""

TEXT_JS = r"""() => (document.body.innerText || '').split(/\n+/)
    .map(s => s.replace(/\s+/g, ' ').trim()).filter(Boolean).slice(0, 120)"""

TAB_CLICK_JS = r"""(t) => {
    const es = [...document.querySelectorAll('a,li,span,div,button')]
        .filter(e => (e.textContent || '').trim() === t);
    const e = es[es.length - 1];
    if (!e) return 'NOT_FOUND';
    e.click();
    return 'CLICKED ' + e.tagName;
}"""


def dump(f, pw, browser, ctx, pg, title, html_path):
    f.write("\n\n########## %s ##########\n" % title)
    f.write("URL: %s\n" % pg.url)
    html = pg.evaluate("() => document.documentElement.outerHTML")
    open(html_path, "w", encoding="utf-8").write(html)
    f.write("HTML bytes: %d -> %s\n" % (len(html), html_path))

    f.write("\n----- body 文本行 -----\n")
    f.write(json.dumps(pg.evaluate(TEXT_JS), ensure_ascii=False, indent=1))

    f.write("\n----- [title] 元素 -----\n")
    f.write(json.dumps(pg.evaluate(TITLES_JS), ensure_ascii=False, indent=1))

    f.write("\n----- seeCourse 卡片 HTML -----\n")
    f.write(json.dumps(pg.evaluate(SEECOURSE_JS), ensure_ascii=False, indent=1))

    f.write("\n----- enterCourse 按钮祖先链 -----\n")
    f.write(json.dumps(pg.evaluate(CHAIN_JS), ensure_ascii=False, indent=1))


def main():
    f = open("_diag_name_out.txt", "w", encoding="utf-8")
    pw, browser, ctx, pg = start()
    try:
        login(pg)
        pg.goto(MY, wait_until="commit", timeout=60000)
        pg.wait_for_timeout(6000)
        dump(f, pw, browser, ctx, pg, "我的课程 全部(初始)", "_diag_name_mycourse.html")

        r = pg.evaluate(TAB_CLICK_JS, "未完成")
        print("click 未完成 ->", r, flush=True)
        pg.wait_for_timeout(4500)
        dump(f, pw, browser, ctx, pg, "我的自选课 未完成筛选", "_diag_name_undone.html")
        print("DONE", flush=True)
    finally:
        f.close()
        close(pw, browser, ctx)


if __name__ == "__main__":
    main()
