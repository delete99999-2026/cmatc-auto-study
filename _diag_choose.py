# -*- coding: utf-8 -*-
"""只读诊断：课程中心「立即选课」候选 + 我的课程「已学」清单对照。

绝不提交任何选课请求、不打开学习页、不写平台数据。
输出：_diag_choose_out.txt / _diag_choose_market.html / _diag_choose_my.html
"""
import os, json, re, sys, datetime
from playwright.sync_api import sync_playwright
from common import EDGE, HOST, OUT, ARGS, USER, PWD, login

OUTDIR = OUT
MARKET_URL = HOST + "/cms/courseMarketNew.htm"
MY_COURSE_URL = HOST + "/u/student/study/myCourse.action"

# 抓取课程中心「所有卡片」：按钮函数名、按钮实参、课程标题、学时、seeCourse 的 cid
CARD_JS = r"""() => {
    const clean = s => String(s || '').replace(/\s+/g, ' ').trim()
                        .replace(/[.。…]+$/, '').trim();
    const out = [];
    document.querySelectorAll('a[onclick*="chooseCourseTimeLimit"], a[onclick*="enterCourseTimeLimit"]').forEach(a => {
        const oc = a.getAttribute('onclick') || '';
        const isChoose = oc.indexOf('chooseCourseTimeLimit') >= 0;
        const body = (oc.match(/\(([\s\S]*)\)/) || [])[1] || '';
        const args = [...body.matchAll(/'([^']*)'|"([^"]*)"/g)]
                     .map(x => x[1] !== undefined ? x[1] : x[2]);
        // 向上找卡片容器（限制长度，避免爬到整页）
        let box = a;
        for (let i = 0; i < 7 && box.parentElement; i++) {
            const p = box.parentElement;
            if ((p.innerText || '').length > 700) break;
            box = p;
            if (/学时/.test(p.innerText || '') && /选课|学习/.test(p.innerText || '')) break;
        }
        const card = a.closest('li.cell, div.card, div.card-wrap') || box;
        const txt = clean(card.innerText || box.innerText || '');
        const hm = txt.match(/([\d.]+)\s*学时/);
        const ym = txt.match(/20\d\d年/);
        let title = '';
        const t = card.querySelector('.title[title], [class*="title"][title]');
        if (t) title = clean(t.getAttribute('title') || t.textContent || '');
        if (!title) {
            const t2 = card.querySelector('[title]');
            if (t2) title = clean(t2.getAttribute('title') || '');
        }
        let cid = '';
        const see = card.querySelector('[onclick*="seeCourse"]');
        if (see) {
            const sm = (see.getAttribute('onclick') || '').match(/['"]([0-9a-zA-Z]{16,})['"]/);
            if (sm) cid = sm[1];
        }
        if (!cid) {
            const im = oc.match(/['"]([0-9a-zA-Z]{24,40})['"]/);
            if (im) cid = im[1];
        }
        out.push({
            btn: isChoose ? 'choose' : 'enter',
            id: args[0] || '', args: args,
            cid: cid, title: title, hours: hm ? hm[1] : '',
            year: ym ? ym[0] : '', text: txt.slice(0, 220),
            linkText: clean(a.textContent || '')
        });
    });
    return out;
}"""

PAGER_JS = r"""() => {
    const links = [];
    document.querySelectorAll('a').forEach(a => {
        const h = a.getAttribute('href') || '', oc = a.getAttribute('onclick') || '';
        const t = (a.textContent || '').trim();
        if (/changePage|jumpPage|goPage|下一页|尾页|pageNo|currentPage/.test(h + ' ' + oc + ' ' + t)) {
            links.push({t: t, href: h.slice(0, 160), oc: oc.slice(0, 160)});
        }
    });
    const m = (document.body.innerText || '').match(/共\s*(\d+)\s*[页条]|(\d+)\s*门课程|共\s*(\d+)\s*条/);
    return {links: links.slice(-20), totalHint: m ? m[0] : '',
            bodyTail: (document.body.innerText || '').slice(-500)};
}"""

NEXT_JS = r"""() => {
    for (const a of document.querySelectorAll('a')) {
        const s = (a.getAttribute('href') || '') + ' ' + (a.getAttribute('onclick') || '');
        const m = s.match(/changePage\(\s*'([^']*)'\s*,\s*'([^']*)'\s*\)/);
        if (m && typeof window.changePage === 'function') {
            const cur = parseInt(m[1], 10) || 1;
            try { window.changePage(String(cur + 1), m[2]); return 'PAGE' + (cur + 1); }
            catch (e) { return 'ERR:' + String(e).slice(0, 80); }
        }
    }
    const nx = [...document.querySelectorAll('a')]
        .find(a => (a.textContent || '').trim() === '下一页');
    if (nx) { nx.click(); return 'CLICK_NEXT'; }
    return 'NO_NEXT';
}"""

# 我的课程全分页：cid + 完整标题
MYCARD_JS = r"""() => {
    const clean = s => String(s || '').replace(/\s+/g, ' ').trim()
                        .replace(/[.。…]+$/, '').trim();
    const names = {};
    document.querySelectorAll('[onclick*="seeCourse"]').forEach(e => {
        const m = (e.getAttribute('onclick') || '').match(/['"]([0-9a-zA-Z]{16,})['"]/);
        if (!m) return;
        const cid = m[1];
        const t = clean(e.getAttribute('title') || '');
        if (t.length >= 4 && t.length > (names[cid] || '').length) names[cid] = t;
    });
    const out = [];
    document.querySelectorAll('a[onclick*="enterCourse"]').forEach(a => {
        const oc = a.getAttribute('onclick') || '';
        const body = (oc.match(/\(([\s\S]*)\)/) || [])[1] || '';
        const args = [...body.matchAll(/'([^']*)'|"([^"]*)"/g)]
                     .map(x => x[1] !== undefined ? x[1] : x[2]);
        let cid = (args[1] || '').replace(/_+$/, '');
        if (!/^[0-9a-zA-Z]{16,}$/.test(cid)) cid = '';
        let name = names[cid] || '';
        const card = a.closest('li.cell, div.card, div.card-wrap');
        if (!name && card) {
            const t = card.querySelector('.title[title], [class*="title"][title]');
            if (t) name = clean(t.getAttribute('title') || t.textContent || '');
        }
        out.push({cid: cid, name: name, args: args,
                  text: clean(a.textContent || '').slice(0, 30)});
    });
    return out;
}"""

buf = []
def w(s=""):
    print(s, flush=True)
    buf.append(str(s))

def section(name, obj):
    w("\n########## %s ##########" % name)
    w(json.dumps(obj, ensure_ascii=False, indent=1))

def main():
    if not PWD:
        w("ERROR: CMATC_PWD not set")
        return
    pw = sync_playwright().start()
    browser = pw.chromium.launch(executable_path=EDGE, headless=True, args=ARGS)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=True)
    pg = ctx.new_page()
    pg.set_default_timeout(20000)
    try:
        w("LOGIN USER=%s" % USER)
        login(pg, verbose=False)
        w("LOGIN OK -> %s" % pg.url)

        # ---------- 我的课程：已学清单（全分页） ----------
        pg.goto(MY_COURSE_URL, wait_until="commit", timeout=30000)
        pg.wait_for_timeout(5000)
        my_all, seen = [], set()
        for p in range(1, 8):
            cards = pg.evaluate(MYCARD_JS)
            fresh = [c for c in cards if c.get("cid") and c["cid"] not in seen]
            for c in fresh:
                seen.add(c["cid"])
            my_all.extend(cards)
            w("MYCOURSE page %d: %d cards / %d fresh / total %d" %
              (p, len(cards), len(fresh), len(seen)))
            if p == 1:
                section("我的课程 第1页 分页控件", pg.evaluate(PAGER_JS))
            r = pg.evaluate(NEXT_JS)
            w("MYCOURSE next -> %s" % r)
            if r in ("NO_NEXT",) or r.startswith("ERR:"):
                break
            pg.wait_for_timeout(3500)
            if not fresh and p > 1:
                break
        section("我的课程 已学清单(全分页)", my_all)

        # ---------- 课程中心：候选课程（含分页） ----------
        pg.goto(MARKET_URL, wait_until="commit", timeout=30000)
        pg.wait_for_timeout(5000)
        market_all, seen_m = [], set()
        for p in range(1, 12):
            cards = pg.evaluate(CARD_JS)
            w("MARKET page %d: %d cards (choose=%d enter=%d)" %
              (p, len(cards), sum(1 for c in cards if c["btn"] == "choose"),
               sum(1 for c in cards if c["btn"] == "enter")))
            market_all.extend(cards)
            if p == 1:
                section("课程中心 第1页 分页控件", pg.evaluate(PAGER_JS))
                with open(os.path.join(OUTDIR, "_diag_choose_market.html"), "w", encoding="utf-8") as f:
                    f.write(pg.content())
            key0 = json.dumps(cards, ensure_ascii=False, sort_keys=True)
            if key0 in seen_m:
                w("MARKET page %d duplicate, stop" % p)
                break
            seen_m.add(key0)
            r = pg.evaluate(NEXT_JS)
            w("MARKET next -> %s" % r)
            if r in ("NO_NEXT",) or r.startswith("ERR:"):
                break
            pg.wait_for_timeout(4000)
        section("课程中心 全部卡片", market_all)

        # ---------- 对照 ----------
        my_cids = set(c["cid"] for c in my_all if c.get("cid"))
        my_names = set(re.sub(r"\s+", "", c["name"]) for c in my_all if c.get("name"))
        w("\n########## 对照结论 ##########")
        w("已选/已学 cid 数: %d, 名称数: %d" % (len(my_cids), len(my_names)))
        cand = []
        for c in market_all:
            if c["btn"] != "choose":
                continue
            nm = re.sub(r"\s+", "", c["title"])
            dup = (c["cid"] and c["cid"] in my_cids) or (nm and nm in my_names) \
                  or (c["id"] and c["id"] in my_cids)
            cand.append({**c, "duplicate": bool(dup), "key": nm})
        w("立即选课候选: %d 门，其中与已学重复 %d 门，可选 %d 门"
          % (len(cand), sum(1 for c in cand if c["duplicate"]),
             sum(1 for c in cand if not c["duplicate"])))
        section("未学过的可选课程", [c for c in cand if not c["duplicate"]])
        section("与已学重复的课程(必须排除)", [c for c in cand if c["duplicate"]])
    finally:
        with open(os.path.join(OUTDIR, "_diag_choose_out.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(buf))
        w("OUT -> _diag_choose_out.txt")
        try:
            ctx.close(); browser.close(); pw.stop()
        except Exception:
            pass

if __name__ == "__main__":
    main()
