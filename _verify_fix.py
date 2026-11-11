# -*- coding: utf-8 -*-
"""离线验证：模拟 #600034 的 frame 结构（课件 frame URL 不含 kjcourse）。

不启动浏览器、不联网，只验证修复版的 DOM 定位与保活/状态读取逻辑。
"""
import steady_study as old
import steady_study_fixed as new


class FakeFrame:
    def __init__(self, url, probe, state):
        self.url = url
        self._probe = probe
        self._state = state
        self.calls = []

    def evaluate(self, js, arg=None):
        self.calls.append(js[:40])
        if js == new.VIDEO_PROBE_JS:
            return self._probe
        if "document.querySelectorAll('video')" in js and "const vs" in js and "pinfo" not in js:
            return self._probe
        if "const vs = [...document.querySelectorAll('video')]" in js and "pinfo" in js:
            return self._state
        if "MUTE_PLAY" in js or "let n = 0" in js:
            return {"played": 0}
        if "__STEADY_STARTED__" in js:
            return {"muted": True, "clicked": [], "layer": 0}
        return self._state


class FakePage:
    def __init__(self, frames):
        self.frames = frames

    def evaluate(self, js, arg=None):
        return {"layer": 0}

    def wait_for_timeout(self, ms):
        return None


PROBE = {"n": 1, "t": 320.5, "dur": 1587.0, "ready": 4,
         "paused": False, "ended": False, "hasSrc": True}
STATE = {"videoCount": 1, "t": 320.5, "dur": 1587.0, "ready": 4,
         "paused": False, "ended": False, "rate": 1.0,
         "src": "blob:https://pxvideo...", "currentSrc": "blob:https://pxvideo...",
         "err": None, "player": None}

video_frame = FakeFrame(
    "https://pxkckj-cmatc.cma.cn/learnspace/learn/learn/templateeight/"
    "content_webCourseware.action?params.courseId=2c948082a13e6f5f01a13e9c0d600034___",
    PROBE, STATE)
menu_frame = FakeFrame(
    "https://pxkckj-cmatc.cma.cn/learnspace/learn/learn/templateeight/"
    "courseware_index.action?params.courseId=2c948082a13e6f5f01a13e9c0d600034___",
    None, None)
top_frame = FakeFrame(
    "https://pxkckj-cmatc.cma.cn/learnspace/learn/learn/templateeight/index.action",
    None, None)
lp = FakePage([top_frame, menu_frame, video_frame, FakeFrame("about:blank", None, None)])

print("== old steady_study.py ==")
print("  frame_of(kjcourse):", old.frame_of(lp, "kjcourse"))
print("  video_state      :", old.video_state(lp))
print("== new steady_study_fixed.py ==")
print("  video_frames     :", [(f.url or "")[-45:] for f, _ in new.video_frames(lp)])
print("  video_frame      :", (new.video_frame(lp).url or "")[-45:])
st = new.video_state(lp)
print("  video_state      : t=%s dur=%s ready=%s noVideo=%s frame=%s"
      % (st.get("t"), st.get("dur"), st.get("ready"), st.get("noVideo"),
         (st.get("frameUrl") or "")[-45:]))
print("  beat             :", new.beat(lp, "test", verbose=False)[1])
print("  wait_sco_frame   :", (new.wait_sco_frame(lp, 1).url or "")[-45:])
assert old.video_state(lp).get("noVideo") is True, "旧版应误报 noVideo（复现根因）"
assert st.get("noVideo") is None or st.get("noVideo") is False, "修复版应读到视频"
assert abs(st.get("t") - 320.5) < 0.01, "修复版应读到真实播放秒数"
print("SELFTEST_OK")
