# -*- coding: utf-8 -*-
"""离线回归：自主选课 / 启动参数 / 排除已学课程。不联网、不写平台数据。"""
import os, sys, json, tempfile, subprocess
import steady_study_fixed as S

OK = []
def check(cond, name):
    if not cond:
        raise AssertionError("FAIL: " + name)
    OK.append(name)
    print("  [ok] " + name, flush=True)

# 日志与历史文件都重定向，绝不污染真实运行日志/历史
LOGS = []
S.log = lambda m: LOGS.append(str(m))
_tmp = tempfile.mkdtemp(prefix="cmatc_choose_")
S.STUDIED_LOG = os.path.join(_tmp, "studied_courses.json")
S.STUDIED_LEGACY_LOG = os.path.join(_tmp, "legacy_absent.json")
S.STUDIED_PLAIN_LOG = os.path.join(_tmp, "plain_absent.json")
S.nav = lambda *a, **k: None
S.CHOOSE_BATCH = 2
S.CHOOSE_MAX_PAGES = 5
S.CHOOSE_TOTAL_MAX = 20
S.TARGET = 100.0


class FakePage:
    def __init__(self, pages, save_results=None):
        self.pages = pages
        self.i = 0
        self.save_results = save_results or (lambda ids: [
            {"id": i, "ok": True, "status": 200} for i in ids])
        self.saved = None
        self.saw_js = []

    def evaluate(self, js, arg=None):
        self.saw_js.append(js)
        if js == S.CHOOSE_CANDIDATES_JS:
            return self.pages[min(self.i, len(self.pages) - 1)]
        if js == S.MARKET_NEXT_JS:
            self.i += 1
            return "NEXT" if self.i < len(self.pages) else "NO_NEXT"
        if js == S.SAVE_COURSES_JS:
            self.saved = arg
            return self.save_results(arg)
        return None

    def wait_for_timeout(self, ms):
        pass


def card(i, title, hours=2, flag="", cid=""):
    return {"id": i, "flag": flag, "cid": cid, "title": title,
            "hours": hours, "text": title + " %s学时" % hours}


def reset_history():
    """每阶段的候选集相同，必须清空上一阶段写入的持久化历史。"""
    try:
        os.remove(S.STUDIED_LOG)
    except OSError:
        pass
    LOGS.clear()


POOL = [
    {"cid": "c1", "oid": "o1", "name": "坚持全面从严治党", "pct": 100.0},
    {"cid": "c2", "oid": "o2", "name": "坚持制度治党、依规治党", "pct": 100.0},
    {"cid": "c3", "oid": "o3", "name": "重大天气过程预警信息传播实务", "pct": 100.0},
]

PAGE1 = {
    "choose": [
        card("new1", "雷达业务管理", 4),
        card("o1", "命中已学 openId 的新课", 2),          # openId 命中
        card("new2", "坚持全面从严治党", 2),               # 名称命中
        card("new3", "已结束授课的课程", 2, flag="closed"),  # 禁止选
        card("new4", "", 1),                               # 读不到名称
        card("c1", "命中已学 courseId 的新课", 2),          # cid 命中
        card("new1", "重复 id", 2),                         # 同页重复
    ],
    "enterIds": ["o1", "c1", "o9"],
    "totalPages": 171,
}
PAGE2 = {
    "choose": [card("new5", "双偏振雷达原理与应用", 2)],
    "enterIds": [],
    "totalPages": 171,
}

print("=== A. 候选过滤：只选未学过的课 ===", flush=True)
reset_history()
pg = FakePage([PAGE1, PAGE2])
n = S.auto_choose_courses(pg, POOL, 96.0, 0)
check(pg.saved is not None, "提交了选课请求")
check(pg.saved == ["new1", "new5"], "只选中 2 门未学过课程: %s" % pg.saved)
check(all(x not in pg.saved for x in ("o1", "c1", "new2", "new3", "new4")),
      "已学 cid/openId/名称、closed、无名称、重复 id 全部排除")
check(n == 2, "两门都返回成功")
check(any("自主选课清单" in x for x in LOGS), "日志列出选课清单")
check(any("学时缺口 4.0" in x for x in LOGS), "日志显示学时缺口")

print("\n=== B. 成功判定：只有 success=='1' 才算成功 ===", flush=True)
reset_history()
pg = FakePage([PAGE1, PAGE2], save_results=lambda ids: [
    {"id": ids[0], "ok": True, "status": 200},
    {"id": ids[1], "ok": False, "status": 200, "msg": "已存在订单", "raw": "{\"success\":\"0\"}"}])
n = S.auto_choose_courses(pg, POOL, 96.0, 0)
check(n == 1, "1 成功 1 失败时只计 1 门")
check(any("选课未成功" in x for x in LOGS), "失败课程有 warn 日志")

print("\n=== C. DRY 只规划、不提交 ===", flush=True)
reset_history()
pg = FakePage([PAGE1, PAGE2])
n = S.auto_choose_courses(pg, POOL, 96.0, 0, dry=True)
check(n == 2, "DRY 返回规划门数")
check(pg.saved is None, "DRY 未提交任何选课请求")
check(any("未提交任何选课请求" in x for x in LOGS), "DRY 明示未写平台数据")

print("\n=== D. 持久化历史：选过的课不再被重选 ===", flush=True)
reset_history()
S.record_chosen([{"id": "new1", "title": "雷达业务管理", "hours": 4}])
d = S.load_studied()
check("new1" in d["openIds"], "选过的 openId 写入历史")
check("雷达业务管理" in d["names"], "选过的课程名写入历史")
pg = FakePage([PAGE1, PAGE2])
S.auto_choose_courses(pg, POOL, 96.0, 0, dry=True)
check(pg.saved is None, "DRY 不提交")
check("new1" not in (pg.saved or []), "已被排除")
# 直接验证过滤后的规划清单内容
LOGS.clear()
pg = FakePage([PAGE1, PAGE2])
S.auto_choose_courses(pg, POOL, 96.0, 0)
check("new1" not in pg.saved and "new5" in pg.saved,
      "历史已选的 new1 被跳过，改选下一门 new5: %s" % pg.saved)

print("\n=== E. 已选清单并入历史 ===", flush=True)
reset_history()
S.record_chosen([{"id": "keepme", "title": "已自主选过的课", "hours": 2}])
S.record_studied(POOL)
d = S.load_studied()
check(all(c in d["cids"] for c in ("c1", "c2", "c3")), "已学 cid 持久化")
check(all(o in d["openIds"] for o in ("o1", "o2", "o3")), "已学 openId 持久化")
check("坚持全面从严治党" in d["names"], "已学课程名持久化")
check(S.load_studied()["chosen"], "历史 chosen 未被覆盖")

print("\n=== F. 上限保护 ===", flush=True)
pg = FakePage([PAGE1, PAGE2])
n = S.auto_choose_courses(pg, POOL, 96.0, S.CHOOSE_TOTAL_MAX)
check(n == 0 and pg.saved is None, "达到累计上限后不再选课")

print("\n=== G. 损坏/缺失历史文件容错 ===", flush=True)
S.STUDIED_LOG = os.path.join(_tmp, "missing.json")
check(S.load_studied()["cids"] == [], "文件不存在时返回空历史")
with open(S.STUDIED_LOG, "w", encoding="utf-8") as f:
    f.write("{not json")
check(S.load_studied()["names"] == [], "文件损坏时返回空历史")
S.STUDIED_LOG = os.path.join(_tmp, "studied_courses.json")

print("\n=== H. 三段新 JS 语法（Node 真实解析） ===", flush=True)
try:
    for name in ("CHOOSE_CANDIDATES_JS", "MARKET_NEXT_JS", "SAVE_COURSES_JS"):
        js = getattr(S, name)
        r = subprocess.run(["node", "-e", "new Function(" + json.dumps("return " + js) + ")"],
                           capture_output=True, text=True, timeout=30)
        check(r.returncode == 0, "%s 语法正确" % name)
except FileNotFoundError:
    print("  [skip] 未安装 Node，跳过 JS 语法检查", flush=True)

print("\n=== I. 默认目标 80 / 参数解析 ===", flush=True)
src = open(os.path.join(os.path.dirname(S.__file__), "steady_study_fixed.py"),
           encoding="utf-8").read()
check('os.environ.get("CMATC_TARGET", "80")' in src, "默认目标学时为 80")
check('AUTO_CHOOSE = os.environ.get("CMATC_AUTO_CHOOSE", "1") == "1"' in src,
      "自主选课默认开启")
check("if not unfinished:" in src and "auto_choose_courses(pg, pool, credit, chosen_total)" in src,
      "主循环已接入自主选课")
check("课程池不足 %d 门，HTTP 直接选课" not in src, "旧的乱选课逻辑已移除")
check("record_studied(pool)" in src, "build_course_pool 会记录已学清单")
check("hashlib.sha256" in src and "STUDIED_PLAIN_LOG" in src,
      "已学历史按账号哈希隔离，文件名不含明文账号")

print("\n=== J. 账号隔离：换账号不继承已学清单 ===", flush=True)
S.STUDIED_LOG = os.path.join(_tmp, "studied_AAA.json")
S.record_studied([{"cid": "aaa1", "oid": "aaa_o1", "name": "A账号学过的课"}])
S.STUDIED_LOG = os.path.join(_tmp, "studied_BBB.json")
d_b = S.load_studied()
check("aaa1" not in d_b["cids"] and "A账号学过的课" not in d_b["names"],
      "B 账号读不到 A 账号的已学课程")
S.STUDIED_LOG = os.path.join(_tmp, "studied_courses.json")

print("\nCHOOSE_SELFTEST_OK  (%d checks)" % len(OK), flush=True)
