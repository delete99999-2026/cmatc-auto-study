# -*- coding: utf-8 -*-
"""只读诊断：核对平台「我的课程」真实门数 / 完成门数 / 未完成门数。

严格只读：仅 GET 页面 + 调用平台自己的 queryLearningProgress.json 查询接口。
不点 enterCourse / 不点立即选课 / 不打开学习页 / 不写任何学习记录。
输出：diag_courses_out.txt
"""
import json, re, sys, time
from common import start, login, close, HOST

MY_COURSE_URL = HOST + "/u/student/study/myCourse.action"
MARKET_URL = HOST + "/cms/courseMarketNew.htm"
OUT = "diag_courses_out.txt"

CARDS_JS = r"""() => {
    const KEY = /enterCourse|seeCourse|openResourceByIp|chooseCourseTimeLimit|enterCourseTimeLimit/;
    const out = [];
    document.querySelectorAll('a[onclick]').forEach(a => {
        const oc = a.getAttribute('onclick') || '';
        if (!KEY.test(oc)) return;
        let box = a;
        for (let i = 0; i < 6 && box.parentElement; i++) {
            box = box.parentElement;
            const t = box.innerText || '';
            if (/学习进度|立即选课|开始学习|学时/.test(t)) break;
            if (t.length > 600) break;
        }
        const t = (box.innerText || '').replace(/\s+/g, ' ');
        const pm = t.match(/学习进度[:：]\s*([\d.]+)\s*%/);
        out.push({text: (a.textContent || '').trim().slice(0, 24),
                  oc: oc.slice(0, 500),
                  pct: pm ? parseFloat(pm[1]) : null,
                  done100: /100\s*%/.test(t),
                  box: t.slice(0, 260)});
    });
    return out;
}"""

PAGER_JS = r"""() => {
    const links = [];
    document.querySelectorAll('a').forEach(a => {
        const oc = a.getAttribute('onclick') || '';
        const hr = a.getAttribute('href') || '';
        const t = (a.textContent || '').trim();
        if (/changePage|jumpPage|show\(|下一页|尾页|共\s*\d+\s*页/.test(oc + hr + t)) {
            links.push({t: t, oc: (oc || ('href:' + hr)).slice(0, 200)});
        }
    });
    const body = (document.body.innerText || '').replace(/\s+/g, ' ');
    const m = body.match(/共\s*\d+\s*页|共\s*\d+\s*条/);
    return {links: links.slice(-30), totalHint: m ? m[0] : null,
            url: location.href, textLen: body.length,
            progressLabels: (body.match(/学习进度[:：]\s*[\d.]+\s*%/g) || [])};
}"""

NEXT_PAGE_JS = r"""() => {
    // 分页 JS 可能写在 href="javascript:changePage('1','12')" 里，不是 onclick
    const as = [...document.querySelectorAll('a')];
    let m = null;
    for (const a of as) {
        const s = (a.getAttribute('href') || '') + ' ' + (a.getAttribute('onclick') || '');
        m = s.match(/changePage\(\s*'([^']*)'\s*,\s*'([^']*)'\s*\)/);
        if (m) break;
    }
    if (m && typeof window.changePage === 'function') {
        const cur = parseInt(m[1], 10) || 1;
        try { window.changePage(String(cur + 1), m[2]);
              return 'changePage(' + (cur + 1) + ',' + m[2] + ')'; }
        catch (e) { return 'ERR:' + String(e).slice(0, 80); }
    }
    const nx = as.find(a => (a.textContent || '').trim() === '下一页');
    if (nx) { nx.click(); return 'click_next'; }
    return 'NO_NEXT';
}"""

PROGRESS_API_JS = r"""async (ids) => {
    const body = new URLSearchParams();
    body.append('page.searchItem.openCourseIds', ids.join(','));
    const r = await fetch('/u/study/queryLearningProgress.json', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                  'X-Requested-With': 'XMLHttpRequest'},
        body: body.toString(), credentials: 'same-origin'
    });
    return {status: r.status, body: (await r.text()).slice(0, 60000)};
}"""


def dump(f, title, obj):
    s = json.dumps(obj, ensure_ascii=False, indent=1)
    f.write("\n===== %s =====\n%s\n" % (title, s))
    print("\n===== %s =====\n%s" % (title, s[:6000]), flush=True)


def collect_cards(pg):
    try:
        return pg.evaluate(CARDS_JS)
    except Exception as e:
        return [{"error": str(e)[:120]}]


def cid_openid(cards):
    """从 onclick 实参里精确提取 (courseId, openId)。

    enterCourse(url, cid, '1', '', openId, '')  -> args[1], args[4]
    seeCourse(cid, openId, '1')                 -> args[0], args[1]
    openResourceByIp(cid, openId)               -> args[0], args[1]
    """
    pairs = {}
    for c in cards:
        oc = c.get("oc", "")
        args = re.findall(r"'([^']*)'", oc)
        cid = oid = None
        if "seeCourse(" in oc and len(args) >= 2:
            cid, oid = args[0], args[1]
        elif "openResourceByIp(" in oc and len(args) >= 2:
            cid, oid = args[0], args[1]
        elif "enterCourse(" in oc and len(args) >= 5:
            cid, oid = args[1], args[4]
        elif "enterCourseTimeLimit(" in oc and len(args) >= 5:
            cid, oid = args[1], args[4]
        elif "chooseCourseTimeLimit(" in oc and args:
            oid = args[0]
        if cid and oid and re.match(r"^[0-9a-fA-F]{16,}$", cid) \
                and re.match(r"^[0-9a-fA-F]{16,}$", oid):
            pairs[cid] = oid
    return pairs


def main():
    f = open(OUT, "w", encoding="utf-8")
    pw, browser, ctx, pg = start()
    try:
        login(pg)
        print("LOGIN OK", pg.url, flush=True)

        # ---------- 1. 我的课程：逐页抓全 ----------
        pg.goto(MY_COURSE_URL, wait_until="commit", timeout=60000)
        pg.wait_for_timeout(5000)
        all_pages = []
        seen_cards = {}
        for page_no in range(1, 13):
            cards = collect_cards(pg)
            pager = pg.evaluate(PAGER_JS)
            pairs = cid_openid(cards)
            all_pages.append({"page": page_no, "cards": len(cards),
                              "cids": list(pairs.keys()),
                              "pcts": [c.get("pct") for c in cards],
                              "pager": pager})
            for cid, oid in pairs.items():
                seen_cards.setdefault(cid, oid)
            print("MYCOURSE page %d: %d cards, %d cids, pager=%s"
                  % (page_no, len(cards), len(pairs), pager.get("totalHint")), flush=True)
            if page_no == 1:
                dump(f, "我的课程第1页 卡片明细", cards)
                dump(f, "我的课程第1页 分页控件", pager)
            r = pg.evaluate(NEXT_PAGE_JS)
            print("  next ->", r, flush=True)
            if r == "NO_NEXT" or r.startswith("ERR:"):
                break
            pg.wait_for_timeout(3500)
            new = cid_openid(collect_cards(pg))
            fresh = set(new) - set(seen_cards)
            print("  after next: %d cids, %d fresh" % (len(new), len(fresh)), flush=True)
            if not fresh:
                break
        dump(f, "我的课程逐页汇总", all_pages)
        my_pairs = dict(seen_cards)
        print("MYCOURSE total distinct cid =", len(my_pairs), flush=True)

        # ---------- 2. 课程中心：已选 / 未选 + openId 映射 ----------
        pg.goto(MARKET_URL, wait_until="commit", timeout=60000)
        pg.wait_for_timeout(5000)
        mcards = collect_cards(pg)
        dump(f, "课程中心第1页 卡片明细", mcards)
        dump(f, "课程中心第1页 分页控件", pg.evaluate(PAGER_JS))
        market_pairs = cid_openid(mcards)
        started = [c for c in mcards if "enterCourseTimeLimit" in c.get("oc", "")]
        choose = [c for c in mcards if "chooseCourseTimeLimit" in c.get("oc", "")]
        dump(f, "课程中心第1页 统计",
             {"总卡片": len(mcards), "开始学习(已选)": len(started),
              "立即选课(未选)": len(choose), "cid数": len(market_pairs)})

        # ---------- 3. 平台权威进度接口 ----------
        all_ids = sorted(set(list(my_pairs.values()) + list(market_pairs.values())))
        print("queryLearningProgress with %d openIds" % len(all_ids), flush=True)
        r = pg.evaluate(PROGRESS_API_JS, all_ids)
        plist = []
        try:
            plist = json.loads(r["body"]).get("progressList", [])
        except Exception as e:
            print("PARSE ERR", e, r["body"][:400], flush=True)
        stat = {"请求openId数": len(all_ids), "返回条数": len(plist),
                "进度100": sum(1 for x in plist if float(x.get("progress") or 0) >= 99.9),
                "进度0": sum(1 for x in plist if float(x.get("progress") or 0) == 0),
                "0<进度<100": sum(1 for x in plist if 0 < float(x.get("progress") or 0) < 99.9),
                "有finishDate": sum(1 for x in plist if x.get("finishDate"))}
        dump(f, "平台进度接口汇总", stat)
        dump(f, "平台进度接口明细", plist)
        dump(f, "cid->openId 映射(我的课程)", my_pairs)
        dump(f, "cid->openId 映射(课程中心)", market_pairs)

        # ---------- 4. 对照 ----------
        by_oid = {x.get("openId"): x for x in plist}
        rows = []
        for cid, oid in sorted(set(list(my_pairs.items()) + list(market_pairs.items()))):
            p = by_oid.get(oid)
            rows.append({"cid": cid, "cidShort": cid[-6:], "openId": oid,
                         "progress": p.get("progress") if p else None,
                         "finishDate": p.get("finishDate") if p else None,
                         "inMyCourse": cid in my_pairs,
                         "inMarket": cid in market_pairs})
        dump(f, "逐课对照表", rows)
        print("\nSUMMARY %s" % json.dumps(stat, ensure_ascii=False), flush=True)
    finally:
        f.close()
        close(pw, browser, ctx)


if __name__ == "__main__":
    main()
