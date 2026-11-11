# -*- coding: utf-8 -*-
"""离线验证 2026-11-10 第七轮修复（课程卡 98.9% 空转 6 小时）。

不启动浏览器、不联网、不写任何平台数据。用假 frame 模拟：
  * 平台停在最后一节（cur=2）、第 1 节仍 completestate=0（first=0）；
  * 平台断点 videoTime=178s（正是 21:56:27 日志里的值）。
验证：
  1) 未完成节点不再被 seek 跳过开头；
  2) 已完成节点仍可正常恢复断点；
  3) 平台停在片尾且前面有未完成节点时，resume_to_unfinished_node 会回跳；
  4) 节点播放中不误回跳；
  5) click_first_unfinished_node 会点回第 1 节并从头真实播放。
"""
import steady_study_fixed as new

S = {
    "points": 3,
    "iid": "2066124287482433",
    "vt": 178,                    # 日志实证：第 1 节被 seek 到 178s
    "cur_done": False,            # 当前节点未完成
    "total": 3, "done": 2, "cur": 2, "first": 0,
    "clicked": [], "seeks": [], "zeros": 0,
    "vstate": {"videoCount": 1, "t": 928.0, "dur": 928.0, "ready": 4,
               "paused": True, "ended": True, "rate": 1,
               "currentSrc": "https://kjcourse-cmatc.cma.cn/2026/dangjsx/zx2678051/sco1/1.mp4",
               "src": "sco1/1.mp4", "err": None, "player": None},
}
S["probe"] = {"n": 1, "t": S["vstate"]["t"], "dur": S["vstate"]["dur"],
              "ready": 4, "paused": True, "ended": True, "hasSrc": True}


class FakeFrame:
    def __init__(self, url, kind):
        self.url, self.kind, self.calls = url, kind, []

    def evaluate(self, js, arg=None):
        self.calls.append(js)
        if js == "() => document.querySelectorAll('.s_point').length":
            return S["points"] if self.kind == "menu" else 0
        if js == new.QUERY_RESUME_JS:
            return {"ok": True, "data": {"itemId": S["iid"], "videoTime": S["vt"]}}
        if js == new.CUR_NODE_DONE_JS:
            return {"id": S["iid"], "done": S["cur_done"]}
        if js == new.NODE_INFO_JS:
            return {"total": S["total"], "done": S["done"], "curIdx": S["cur"],
                    "curId": "s_point_" + S["iid"],
                    "firstUndone": S["first"], "firstUndoneId": "s_point_first"}
        if js == new.NODE_PROGRESS_JS:
            return {"total": S["total"], "done": S["done"],
                    "pct": 66.7, "allDone": False}
        if js == new.CLICK_NODE_JS:
            S["clicked"].append(arg)
            return {"ok": True, "id": "s_point_first", "index": arg,
                    "total": S["total"]}
        if js == new.SEEK_RESUME_JS:
            S["seeks"].append(dict(arg))
            return {"ok": True, "before": 2, "target": arg.get("t"),
                    "after": arg.get("t"), "dur": 1915}
        if js == new.REPLAY_ZERO_JS:
            S["zeros"] += 1
            return {"ok": True, "t": 0, "dur": 1915}
        if js == new.VIDEO_STATE_JS:
            return dict(S["vstate"])
        if js == new.VIDEO_PROBE_JS:
            return S["probe"] if self.kind == "video" else {"n": 0}
        if js == new.NEXT_NODE_JS:
            return {"ok": True, "clicked": False, "allDone": True,
                    "n": S["total"], "cur": S["cur"]}
        if js in (new.KJ_BEAT_JS, new.TOP_BEAT_JS):
            return {"muted": True, "played": False, "clicked": [],
                    "layer": 0, "started": True, "skipped": False, "note": ""}
        return {}


class FakePage:
    url = ("https://pxkckj-cmatc.cma.cn/learnspace/learn/learn/templateeight/"
           "index.action?params.courseId=2c948082a06590c001a0cbe70e1f0c11___")

    def __init__(self, frames):
        self.frames = frames

    def evaluate(self, js, arg=None):
        return {"layer": 0}

    def wait_for_timeout(self, ms):
        return None


top = FakeFrame("https://top/index.action", "top")
menu = FakeFrame("https://menu/courseware_index.action", "menu")
video = FakeFrame("https://kjcourse-cmatc.cma.cn/2026/dangjsx/zx2678051/", "video")
lp = FakePage([top, menu, video])

# beat / tick_wait 在离线验证里不产生真实动作；
# log 改走 stdout，避免把 [test] 行写进正在运行的正式 steady_run.log。
new.beat = lambda *a, **k: ({}, {})
new.tick_wait = lambda *a, **k: None
new.log = lambda msg, *a, **k: print("[selftest] " + str(msg))

print("== 1) 未完成节点 + 断点 178s：不得跳过开头 ==")
S["cur_done"], S["seeks"] = False, []
r1 = new.apply_platform_resume(lp, "test")
print("   apply_platform_resume ->", r1, "| seek 调用:", S["seeks"])
assert r1 is None, "未完成节点不应恢复断点"
assert not S["seeks"], "未完成节点绝不能 seek 跳过开头（0~178s 会永久漏学）"

print("== 2) 已完成节点：仍可恢复断点 ==")
S["cur_done"], S["seeks"], S["cur"] = True, [], 0
r2 = new.apply_platform_resume(lp, "test")
print("   apply_platform_resume ->", r2, "| seek 调用:", S["seeks"])
assert S["seeks"] and S["seeks"][0]["t"] == 178, "已完成节点应正常恢复断点"

print("== 3) 平台停在片尾 + 前面有未完成节点：必须回跳补播 ==")
S["cur_done"], S["cur"], S["first"], S["clicked"] = False, 2, 0, []
S["vstate"]["ended"], S["vstate"]["t"] = True, 928.0
new.resume_to_unfinished_node(lp, "test")
print("   点击节点序号:", S["clicked"])
assert 0 in S["clicked"], "片尾空转时必须点回第 1 个未完成节点"

print("== 4) 当前节点正在播放：不得误回跳 ==")
S["clicked"] = []
S["vstate"]["ended"], S["vstate"]["t"] = False, 100.0
new.resume_to_unfinished_node(lp, "test")
print("   点击节点序号:", S["clicked"])
assert not S["clicked"], "播放中不应打断当前节点"

print("== 5) 回头补播函数：点节点 + 从头真实播放 ==")
S["clicked"], S["zeros"] = [], 0
S["vstate"]["ended"], S["vstate"]["t"] = True, 928.0
rb = new.click_first_unfinished_node(lp, "test")
print("   ->", rb)
assert rb.get("ok") is True and 0 in S["clicked"], "补播应点回第 1 个未完成节点"
assert S["zeros"] >= 1, "补播应把播放位置归零，从头真实播放"

print("== 6) 主循环兜底分支静态检查 ==")
src = open("steady_study_fixed.py", encoding="utf-8").read()
for token in ("backfill_tries", "stuck_confirm", "click_first_unfinished_node(lp, tag)",
              "stuck_confirm >= STUCK_MAX", "backfill_tries < BACKFILL_MAX",
              "result = \"continue\""):
    assert token in src, "缺少兜底代码: " + token
print("   补播次数上限 BACKFILL_MAX=%s，空转上限 STUCK_MAX=%s"
      % (new.BACKFILL_MAX, new.STUCK_MAX))

print("SELFTEST_OK")
