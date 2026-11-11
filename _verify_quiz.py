# -*- coding: utf-8 -*-
"""离线回归：课后自测题逻辑 + 目标学时默认 80（启动参数可覆盖），不联网、不写平台数据。

1) 用 Node 跑真实的 TEST_ANSWER_JS（带 DOM 桩），验证 25 题
   单选(A-D)/多选(A-D)/判断(T-F) 都能勾上并拼出 myAnswers。
2) 用假 frame 驱动 do_test_task 状态机，验证提交/已有成绩/强制重做/
   点开节点/次数上限等分支。
"""
import os, sys, json, tempfile, subprocess
os.environ.setdefault("CMATC_DRY", "1")
import steady_study_fixed as S

LOGS = []
S.log = lambda m: LOGS.append(str(m))


def check(cond, msg):
    if not cond:
        raise AssertionError("FAIL: " + msg)
    print("  OK  " + msg)


# ---------------------------------------------------------------------------
print("=== 1. 配置 ===")
check(S.TARGET == 80.0, "TARGET 默认 80 学时（2026-11-11 起可由 --target 覆盖）")
check(S.TEST_ENABLED is True, "课后自测题默认开启")
check(S.TEST_MAX == 2, "同一份卷单会话最多提交 2 次")

# ---------------------------------------------------------------------------
print("=== 2. Node 执行真实 TEST_ANSWER_JS ===")
HARNESS = r"""
const fs = require('fs');
const fnSrc = fs.readFileSync(process.argv[2], 'utf8');
const fn = eval(fnSrc);
const inputs = {};
function mk(name, type, vals) {
  inputs[name] = vals.map(v => ({
    type: type, value: v, checked: false,
    dispatchEvent: function(e) {}
  }));
}
mk('questionInput_0', 'radio', ['A','B','C','D']);          // 单选 1
for (let i = 1; i <= 4; i++)                                  // 多选 4
  mk('questionInput_' + i, 'checkbox', ['A','B','C','D']);
for (let i = 5; i <= 24; i++)                                 // 判断 20
  mk('questionInput_' + i, 'radio', ['T','F']);
global.document = {
  getElementById: id => (id === 'current_allNum') ? {value: '25'} : null,
  getElementsByName: n => inputs[n] || []
};
global.Event = function(t, o) { this.type = t; };
global.dealUserAnswerToStr = () => null;
const r = fn();
console.log(JSON.stringify(r));
"""
with tempfile.TemporaryDirectory() as td:
    fn_path = os.path.join(td, "answer_fn.js")
    run_path = os.path.join(td, "run.js")
    open(fn_path, "w", encoding="utf-8").write(S.TEST_ANSWER_JS)
    open(run_path, "w", encoding="utf-8").write(HARNESS)
    out = subprocess.check_output(["node", run_path, fn_path], text=True)
    r = json.loads(out.strip().splitlines()[-1])
check(r.get("ok") is True, "TEST_ANSWER_JS 返回 ok")
check(r.get("n") == 25, "识别 25 道题")
parts = r.get("myAnswers", "").split("|")
check(len(parts) == 25, "生成 25 个答案位")
check(parts[0] == "A", "单选题勾第一项 A")
check(parts[1:5] == ["AB"] * 4, "4 道多选题各勾 2 项 AB")
check(parts[5:] == ["T"] * 20, "20 道判断题各勾 T（对）")
check(all(p and p != "NULL" for p in parts), "无未作答题目")

# ---------------------------------------------------------------------------
print("=== 3. do_test_task 状态机 ===")


class Frame:
    def __init__(self, url="about:blank", paper=False, result=False,
                 item="item1", score="96", menu=False):
        self.url = url
        self.paper, self.result, self.item, self.score, self.menu = (
            paper, result, item, score, menu)
        self.calls = []

    def evaluate(self, js, arg=None):
        self.calls.append(js)
        if js == S.TEST_FRAME_JS:
            st = {"url": self.url, "title": "测试", "itemId": self.item,
                  "paper": self.paper, "result": self.result,
                  "score": self.score,
                  "n": 25 if self.paper else 0}
            # 菜单 frame 也会被 test_frame_states 扫到，返回非测试结构
            return st if (self.paper or self.result
                          or "coursewareTest" in self.url) else {
                              "url": self.url, "title": "课件",
                              "itemId": "", "paper": False, "result": False,
                              "score": "", "n": 0}
        if js == S.TEST_ANSWER_JS:
            return {"ok": True, "n": 25, "myAnswers": "A|AB|T"}
        if js == S.TEST_SUBMIT_JS:
            return "CALLED"
        if js == S.TEST_REDO_JS:
            return "CALLED"
        if js == S.TEST_MENU_JS:
            return [{"i": 3, "id": "item1", "type": "test", "done": False,
                     "cur": True, "title": "自测（无分数要求）"}]
        if js == S.CLICK_NODE_JS:
            return {"ok": True, "id": "s_point_item1", "index": 3, "total": 4}
        if isinstance(js, str) and js.startswith("() => document.querySelectorAll"):
            return 4 if self.menu else 0
        return {}


class LP:
    def __init__(self, frames):
        self.frames = frames

    def wait_for_timeout(self, ms):
        pass


def new_state():
    return {"done": set(), "tries": {}, "clicks": {},
            "last": 0.0, "moved": set()}


S.click_next_node = lambda lp, tag: {"ok": True, "clicked": False,
                                     "allDone": True}

# (a) 试卷页 -> 作答并提交
paper = Frame(url="https://x/coursewareTest_intoRedoTestPage.action", paper=True)
menu = Frame(url="https://x/courseware_index.action", menu=True)
lp = LP([menu, paper])
st = new_state()
S.menu_frame = lambda l: menu
r = S.do_test_task(lp, "t", st, allow_click=False)
check(r == "submitted", "试卷页 -> submitted")
check("item1" in st["done"] and st["tries"]["item1"] == 1, "提交后记录 done/tries")
check(S.TEST_ANSWER_JS in paper.calls and S.TEST_SUBMIT_JS in paper.calls,
      "调用了平台自带作答与提交")

# (b) 成绩页（非强制）-> 视为已完成，不重做
res = Frame(url="https://x/coursewareTest_getTestInfo.action", result=True)
lp = LP([menu, res])
st = new_state()
r = S.do_test_task(lp, "t", st, allow_click=False)
check(r == "already", "已有成绩页 -> already")
check(S.TEST_REDO_JS not in res.calls, "非强制不点「再做一遍」")
check(S.TEST_SUBMIT_JS not in res.calls, "非强制不重复提交")

# (c) 强制重做：成绩页 -> redo(触发 frame 导航到试卷页) -> 提交
class RedoFrame(Frame):
    """模拟 redoTestPaper() 把当前 frame 导航成试卷页。"""

    def __init__(self, lp_ref, paper_frame):
        super().__init__(url="https://x/coursewareTest_getTestInfo.action",
                         result=True)
        self.lp_ref, self.paper_frame = lp_ref, paper_frame

    def evaluate(self, js, arg=None):
        if js == S.TEST_REDO_JS:
            # 真实平台会 window.location.href 跳转，旧 frame 被试卷页替换
            self.lp_ref["lp"].frames = [menu, self.paper_frame]
        return super().evaluate(js, arg)


paper2 = Frame(url="https://x/coursewareTest_intoRedoTestPage.action", paper=True)
holder = {}
res = RedoFrame(holder, paper2)
lp = LP([menu, res])
holder["lp"] = lp
st = new_state()
r = S.do_test_task(lp, "t", st, allow_click=False, force=True)
check(r == "submitted", "进度卡住时强制重做并提交")
check(S.TEST_REDO_JS in res.calls, "调用了 redoTestPaper")
check(st["tries"].get("item1", 0) >= 1, "重做计入次数上限")

# (d) 没有测试 frame、允许点节点 -> 点开自测题节点
clicked = {"n": 0}


menu_only = Frame(url="https://x/courseware_index.action", menu=True)
S.menu_frame = lambda l: menu_only
lp = LP([menu_only])
st = new_state()
r = S.do_test_task(lp, "t", st, allow_click=True)
check(r == "opened", "无试卷 frame 时点开菜单里的 test 节点")
check(any(c == S.CLICK_NODE_JS for c in menu_only.calls), "确实点了菜单节点")
check(st["clicks"].get("item1", 0) <= 2, "点节点次数有上限，不会无限点")

# (e) 视频在播（allow_click=False）时不切节点
lp = LP([Frame(url="https://x/courseware_index.action", menu=True)])
st = new_state()
r = S.do_test_task(lp, "t", st, allow_click=False)
check(r is None, "视频播放中不切到自测题节点")

# (f) 次数上限：达到 TEST_MAX 后不再重复提交
p3 = Frame(url="https://x/coursewareTest_intoRedoTestPage.action", paper=True)
lp = LP([menu, p3])
st = new_state()
st["tries"]["item1"] = S.TEST_MAX
r = S.do_test_task(lp, "t", st, allow_click=False)
check(r == "skipped", "达到 TEST_MAX 后停止提交，避免无限重做")

# ---------------------------------------------------------------------------
print("=== 4. 关键代码存在性 ===")
src = open(os.path.join(os.path.dirname(__file__), "steady_study_fixed.py"),
           encoding="utf-8").read()
for token in ("CMATC_DO_TESTS", "TEST_MENU_JS", "test_frame_states(lp)",
              "force_test = (no_video_beats >= 3) or (test_idle >= 2)",
              "if st.get(\"noVideo\") and test_active:",
              "confirm_done(pg, cid, tag)",
              "coursewareTest_handSubmitPaperToResult"):
    check(token in src, "源码含 " + token[:45])

print("\nQUIZ_SELFTEST_OK  (日志条数 %d，未写入 steady_run.log)" % len(LOGS))
