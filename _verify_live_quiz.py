# -*- coding: utf-8 -*-
"""集成验证：用修复版脚本自己的函数，在真实课程页跑一遍自测题处理。

只读部分：识别 itemtype=test 节点、识别成绩页。
写入部分：force=True 时重做并提交一次「无分数要求」的自测卷
（平台取历次最高分，不掉分），用于验证 handSubmit(false) 这条正式代码路径。
"""
import os, json
os.environ.setdefault("CMATC_DRY", "1")
import common
import steady_study_fixed as S

# 让测试日志只打到屏幕，不污染 steady_run.log
S.log = lambda m: print("  [live] " + str(m), flush=True)


def fresh():
    return {"done": set(), "tries": {}, "clicks": {},
            "last": 0.0, "moved": set()}


def main():
    pw, browser, ctx, pg = common.start()
    try:
        common.login(pg)
        pool = S.build_course_pool(pg, 40)
        course = next((c for c in pool
                       if (c.get("cid") or "").endswith("dc04a9")), None)
        print("COURSE", course.get("cid") if course else "NONE", flush=True)
        lp, how = S.open_learnspace(pg, ctx, course, "live", None)
        S.click_courseware_tab(lp, "live")
        lp.wait_for_timeout(4000)
        nodes = S.test_nodes(lp)
        tests = [x for x in nodes if x["type"] == "test"]
        print("TEST_NODES", json.dumps(tests, ensure_ascii=False), flush=True)
        assert tests, "没找到 itemtype=test 节点"

        mf = S.menu_frame(lp)
        mf.evaluate(S.CLICK_NODE_JS, tests[0]["i"])
        lp.wait_for_timeout(6500)
        frames = S.test_frame_states(lp)
        print("TEST_FRAMES", json.dumps([d for _, d in frames],
                                        ensure_ascii=False)[:1500], flush=True)
        assert frames, "点开自测节点后没找到试卷/成绩页"

        # 1) 非强制：已有成绩页应识别为完成，且不重复提交
        r1 = S.do_test_task(lp, "live", fresh(), allow_click=False, force=False)
        print("PASS1 (no write) =", r1, flush=True)
        assert r1 == "already", "已有成绩应识别为 already，实际 %s" % r1

        # 2) 强制重做：走正式的作答 + handSubmit(false) 提交路径
        r2 = S.do_test_task(lp, "live", fresh(), allow_click=False, force=True)
        print("PASS2 (redo + submit) =", r2, flush=True)
        assert r2 == "submitted", "强制重做应提交成功，实际 %s" % r2

        after = S.test_frame_states(lp)
        print("AFTER", json.dumps([d for _, d in after],
                                  ensure_ascii=False)[:1200], flush=True)
        print("LIVE_QUIZ_OK", flush=True)
    finally:
        common.close(pw, browser, ctx)


if __name__ == "__main__":
    main()
