# -*- coding: utf-8 -*-
"""受控实测：真实提交 1 门【未学过】课程的选课请求，验证闭环。

仅选 1 门、不打开学习页、不写任何学时/完成状态；
验证 saveCourses.json 返回 success=1，且该课出现在「我的课程」待学清单。
"""
import os, sys, json
import steady_study_fixed as S
from common import EDGE, ARGS, login
from playwright.sync_api import sync_playwright

S.TARGET = 100.0
S.CHOOSE_BATCH = 1          # 本次实测只选 1 门，最小化对账号的影响
S.CHOOSE_MAX_PAGES = 8
S.CHOOSE_TOTAL_MAX = 20
S.DRY = False

buf = []
def w(s=""):
    print(s, flush=True)
    buf.append(str(s))

def main():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(executable_path=EDGE, headless=True, args=ARGS)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=True)
    pg = ctx.new_page()
    pg.set_default_timeout(20000)
    S.attach_recorder(pg, "PG")
    try:
        login(pg, verbose=False)
        w("LOGIN OK")
        credit = S.read_credit(pg)
        w("CREDIT %s / %s" % (credit, S.TARGET))
        pool = S.build_course_pool(pg, S.NEED)
        before = set(c.get("cid") for c in pool if c.get("cid"))
        w("BEFORE pool=%d cids=%d todo=%d"
          % (len(pool), len(before), sum(1 for c in pool if c.get("todo"))))

        n = S.auto_choose_courses(pg, pool, credit, 0)
        w("CHOOSE_RESULT n=%d" % n)

        pg.wait_for_timeout(4000)
        pool2 = S.build_course_pool(pg, S.NEED)
        after = set(c.get("cid") for c in pool2 if c.get("cid"))
        new_cids = after - before
        todo2 = [c for c in pool2 if c.get("todo")]
        w("AFTER pool=%d cids=%d new=%d todo=%d"
          % (len(pool2), len(after), len(new_cids), len(todo2)))
        for c in todo2[:5]:
            w("  TODO %s [%s%%] cid=%s" % (c.get("name") or "?", c.get("pct"),
                                            (c.get("cid") or "-")[-6:]))
        hist = S.load_studied()
        w("HIST chosen=%d cids=%d" % (len(hist.get("chosen", [])), len(hist.get("cids", []))))
        for x in hist.get("chosen", [])[-3:]:
            w("  CHOSEN %s (%s学时) id=%s" % (x.get("name"), x.get("hours"),
                                              (x.get("id") or "")[:12]))
        ok = (n >= 1 and len(new_cids) >= 1 and bool(todo2))
        w("LIVE_CHOOSE_OK" if ok else "LIVE_CHOOSE_INCONCLUSIVE")
        w("RESULT_JSON " + json.dumps({
            "chosen": n, "new_cids": len(new_cids), "todo": len(todo2),
            "ok": ok, "credit": credit}, ensure_ascii=False))
    finally:
        with open(os.path.join(S.OUT, "_verify_live_choose_out.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(buf))
        try:
            ctx.close(); browser.close(); pw.stop()
        except Exception:
            pass

if __name__ == "__main__":
    main()
