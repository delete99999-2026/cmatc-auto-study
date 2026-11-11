# -*- coding: utf-8 -*-
"""
一次性清理：把 probe_complete_v3.py 实验写入的异常续播位置 videoTime 归零。

=============================================================================
v2 修复（2026-11-07 23:1x）—— 初版为什么报「无需清理」
=============================================================================
初版只取 myCourseTheme.action 的第一门课 cs[0]，定位错了课程：

  初版打开的  : courseId=2c948082a06590c001a0cbe70e1f0c1c
                itemId=3204476948348128  videoTime=0        <- 干净，故误判「无需清理」
  污染实际在  : courseId=2c948082a06590c001a0cbe70e1f0c18
                itemId=3033293032888929  videoTime=3600
                依据：probe_complete_v3_out.txt:22（写入）、
                      steady_requests.log:35（diag 读到）、
                      steady_seen.txt（diag 打开的正是这门课）

而 steady diag 打开的正是 ...0c18，所以视频在 readyState=0、src 刚 load()
时被 breakPoint() -> player.setPosition(3600) 卡死，40 秒内
t=0 / dur=0 / ready=0 / paused=true 一直不动。

v2 改为：
  * 扫描「我的课程」里【所有】 enterCourse 的 courseId，不再只看第一门
  * 显式把已知污染 courseId 加入扫描集，防止列表顺序变化 / 解析遗漏
  * 每个 courseId 同时用 带___ / 不带___ 两种形式查询与写入
    （平台两种 key 都接受，probe_complete_v3.py 两种都写过且都生效）
  * 只把 videoTime >= 3500 的项归零，低于阈值一律不动，避免误伤真实进度
  * 清理后重新逐 form 复核，只要还有大值就明确告警

=============================================================================
本脚本做什么 / 不做什么
=============================================================================
只做「归零」：把续播位置恢复成从头开始。等价于在播放器里把进度拖回起点，
但由平台自己的接口写回，避免前端拖拽被 connectionPlay.js 的
minPlayTimeLong 判定为无效学习时长。

【不】增加任何学习时长、【不】写 completed / lesson_status、【不】调用
learningTime_saveLearningTime.action、【不】改 playbackRate。这是清理副作用，
不是伪造学习记录。

结果写入 reset_video_time_out.txt；也打印到控制台。
支持 CMATC_DRY_RUN=1 只查询不写入，便于先核对。

用法：
  run_reset.bat 你的密码           # 全量扫描并归零
  run_reset.bat 你的密码 dry       # 全量扫描，只看不写

※ 单点登录会互踢，请先停掉其它学习脚本。本脚本不修改任何现有文件。
"""
import os, re, json, contextlib
from playwright.sync_api import sync_playwright

from common import EDGE, HOST, OUT, ARGS, login

H = "https://pxkckj-cmatc.cma.cn"
QUERY = H + "/learnspace/learn/learnCourseware/queryLearningItem.json"
SAVE = H + "/learnspace/learn/learnCourseware/saveLearningItem.json"
OUT_TXT = os.path.join(OUT, "reset_video_time_out.txt")

# 只清理明显异常的大值；probe_complete_v3.py 写入的是 3600。
# 低于阈值一律不动，避免误伤真实学习进度。
STALE_THRESHOLD = 3500
DRY = os.environ.get("CMATC_DRY_RUN", "0") == "1"

# 已知污染源（probe_complete_v3_out.txt:12/22），显式加入扫描集兜底。
KNOWN_CID = "2c948082a06590c001a0cbe70e1f0c18"

_buf = []


def out(s):
    s = str(s)
    print(s, flush=True)
    _buf.append(s)


PARSE = r"""(fnName) => {
    const out=[];
    document.querySelectorAll('a[onclick]').forEach(a=>{
        const oc=a.getAttribute('onclick')||'';
        if(oc.indexOf(fnName+'(')<0) return;
        const s=oc.indexOf(fnName+'(')+fnName.length+1;
        const b=oc.slice(s,oc.lastIndexOf(')')+1);
        const args=[],re=/'([^']*)'|"([^"]*)"/g; let m;
        while((m=re.exec(b))!==null) args.push(m[1]!==undefined?m[1]:m[2]);
        if(args.length) out.push({fn:fnName,args:args,url:args[0]});
    });
    return out;
}"""

POST = r"""async (p) => {
    const b = new URLSearchParams();
    for (const k in p.data) b.append(k, p.data[k]);
    try {
        const r = await fetch(p.url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: b.toString(),
            credentials: 'same-origin'
        });
        let t = '';
        try { t = await r.text(); } catch(e) {}
        return {status: r.status, body: t.slice(0, 500)};
    } catch (e) {
        return {error: String(e).slice(0, 150)};
    }
}"""


def parse_data(resp):
    try:
        body = resp.get("body") or ""
        return (json.loads(body).get("data") or {})
    except Exception:
        return {}


def collect(pg):
    """返回 (全部 courseId 列表, 用于打开学习页的 enterCourse 链接列表)。"""
    ids, cs = set(), []
    for attempt in range(3):
        pg.goto(HOST + "/u/student/study/myCourseTheme.action",
                wait_until="commit", timeout=60000)
        pg.wait_for_timeout(8000)
        cs = pg.evaluate(PARSE, "enterCourse")
        out("尝试%d: enterCourse=%d 条" % (attempt + 1, len(cs)))
        if cs:
            for c in cs:
                m = re.search(r"courseId=([^&]+)", c.get("url") or "")
                if m:
                    ids.add(m.group(1).split("___")[0])
                for a in c.get("args", []):
                    a = (a or "").split("___")[0]
                    if re.fullmatch(r"[0-9a-fA-F]{32}", a):
                        ids.add(a)
            break
    ids.add(KNOWN_CID)  # 兜底：防止「我的课程」列表变化导致漏扫
    ids = sorted(ids)
    out("扫描课程数: %d" % len(ids))
    for i in ids:
        out("  - %s%s" % (i, "   <== 已知污染课" if i == KNOWN_CID else ""))
    return ids, cs


def build_forms(ids):
    """每个 courseId 生成 不带___ / 带___ 两种形式，平台两种 key 都接受。"""
    fs = []
    for cid in ids:
        base = cid.split("___")[0]
        for f in (base, base + "___"):
            if f not in fs:
                fs.append(f)
    return fs


def main():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(executable_path=EDGE, headless=True, args=ARGS)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              ignore_https_errors=True)
    pg = ctx.new_page()
    pg.set_default_timeout(25000)
    try:
        out("=" * 70)
        out("videoTime 全量清理 v2 | DRY_RUN=%s | 阈值=%s 秒" % (DRY, STALE_THRESHOLD))
        login(pg, verbose=False)
        out("登录完成: %s" % pg.url)

        ids, cs = collect(pg)
        if not cs:
            out("ERROR: 未找到 enterCourse 链接，无法建立 pxkckj 同域请求通道")
            return

        # 只打开一个学习页，作为 pxkckj 域的 HTTP 通道；查询按 params.courseId
        # 定位，与当前打开的是哪门课无关（已由 probe / steady 日志验证）。
        with pg.expect_popup(timeout=30000) as pop:
            pg.evaluate("(p)=>window[p.fn].apply(null,p.args)",
                        {"fn": cs[0]["fn"], "args": cs[0]["args"]})
        lp = pop.value
        lp.wait_for_timeout(9000)
        out("同域请求通道(学习页): %s" % lp.url[:140])

        def post(url, data):
            return lp.evaluate(POST, {"url": url, "data": data})

        forms = build_forms(ids)

        def scan(tag):
            rows = []
            out("")
            out("--- %s：逐课查询续播位置（共 %d 个 key）---" % (tag, len(forms)))
            for form in forms:
                r = post(QUERY, {"params.courseId": form})
                d = parse_data(r)
                if not d:
                    out("  %-38s -> 无数据 %s" % (form, str(r)[:80]))
                    rows.append((form, None, 0.0))
                    continue
                item = d.get("itemId")
                try:
                    vt = float(d.get("videoTime") or 0)
                except Exception:
                    vt = 0.0
                flag = "   <<< 异常" if vt >= STALE_THRESHOLD else ""
                out("  %-38s itemId=%-18s videoTime=%-9s%s"
                    % (form, item, vt, flag))
                rows.append((form, item, vt))
            return rows

        rows = scan("扫描")
        dirty = [(f, i, v) for f, i, v in rows if i and v >= STALE_THRESHOLD]
        out("")
        out("发现异常续播位置: %d 项" % len(dirty))

        if not dirty:
            out("未发现 videoTime >= %s 的记录，无需写入。" % STALE_THRESHOLD)
            out("若 run_steady.bat ... diag 里视频仍卡在 readyState=0，")
            out("说明原因不在续播位置，请贴新的 steady_run.log / steady_requests.log")
            out("（重点看是否出现 .mp4 的 GET 记录）回来复核。")
            out("DONE")
            return

        if DRY:
            out("DRY RUN：不写入。去掉 dry 参数即会执行归零。")
            out("DONE")
            return

        out("")
        out("--- 开始归零（只写 videoTime=0，不写完成状态/学时）---")
        for form, item, vt in dirty:
            r = post(SAVE, {"params.courseId": form,
                            "params.itemId": str(item),
                            "params.videoTime": "0"})
            out("  SAVE %-38s itemId=%s  %s" % (form, item, str(r)[:130]))

        rows2 = scan("复核")
        left = [(f, i, v) for f, i, v in rows2 if i and v >= STALE_THRESHOLD]
        if left:
            out("")
            out("WARN: 仍有 %d 项大值残留：" % len(left))
            for f, i, v in left:
                out("   %s itemId=%s videoTime=%s" % (f, i, v))
            out("请把 reset_video_time_out.txt 贴回助手复核。")
        else:
            out("")
            out("OK: 所有异常续播位置已归零。")
            out("下一步：run_steady.bat 你的密码 diag   （新版 diag 观察 120 秒）")
        out("DONE")
    finally:
        with open(OUT_TXT, "w", encoding="utf-8") as f:
            f.write("\n".join(_buf) + "\n")
        for fn in (lambda: ctx.close(), lambda: browser.close(), lambda: pw.stop()):
            with contextlib.suppress(BaseException):
                fn()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        out("Ctrl+C")
    except Exception:
        import traceback
        out(traceback.format_exc()[-1500:])
