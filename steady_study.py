# -*- coding: utf-8 -*-
"""
中国气象局培训学院 - 稳态无人值守挂机脚本（独立新文件）

=============================================================================
定位：只做"把挂机做稳"，不做任何计时/进度伪造
=============================================================================
v1/v2/v3 的实测结论（见 probe_*_v3_out.txt 与 js_probe/scrom/ 静态分析）：

  1) 服务端按真实 wall-clock 累计 learnTime。learningTime_saveLearningTime.action
     提交 studyTime=1082 返回 success:true，但 queryLearningTime 只按真实经过
     时间增长（循环实验里后续每次提交仅 +3 秒 = 请求间隔）。studyTime.js 源码
     为 backupStudyTime + (Date.now()-studyStartTime)/1000，每 5 分钟上报一次
     并带 limitId，响应码含 singleCourseLearnLimited / needFaceRecognition /
     processCaptureSingleTabLearnLimited。伪造上报值无效。
  2) 平台未提供 window.API（8 个 frame 全部 hasAPI:false），cross_domain.js 的
     crossDomain() 被注释。APIWrapper.js 的 doLMSCommit() 在 getAPIHandle()==null
     时直接 return —— v1/v2 注入的 SCORM SetValue/Commit 从未发出任何请求。
  3) saveLearningItem.json 写 videoTime=3600 只持久化"续播位置"，
     getSingleItemCompleteCase.json 仍 completed:"0"，进度 0%。connectionPlay.js
     的 minPlayTimeLong:3 明确"拖动进度视为无效学习时长"。完成状态由服务端
     按真实播放轨迹判定，前端只有查询接口。

因此本脚本【不】做以下任何一件事：
  * 不调用 learningTime_saveLearningTime.action 传伪造 studyTime
  * 不写 cmi.core.* / 不调 doLMSCommit / 不放大 player.player_time
  * 不伪造 videoTime / 不拖视频进度条 / 不改 playbackRate
    （例外：会把【真实 currentTime】写进平台续播位置，见文末第二轮修订）
  * 不并发学习不同课程（平台会终止正在学习的课程）

本脚本只做"人不在电脑前时本该手动做的事"：
  * 调用页面自身的 enterCourse()/enterCourseTimeLimit() + expect_popup 打开真实
    _learnspace（保证 faceRecognition / saveUserToSpaceRecord 前置链路完整）
  * 【v1/v2 缺失的关键一步】点击左侧「课件」tab，让 courseware_index.action
    -> content_webCourseware.action -> kjcourse iframe 链真正加载出来
    （v2 日志里的 no_sco_frame 就是卡在默认的 course_detail.action 简介页）
  * 课件内「开始学习/继续观看」只点一次（重复点会触发 videoPlay() 重建
    <video> 并清空 src，使 mp4 加载反复中断 —— 23:21 diag 实测 P0 修复）、
    自动静音、video.paused 时重新 play；换课件节点加载新 document 后重新点一次
  * 自动点掉 studyTime.js 每 30 分钟弹出的 clickAuth「继续学习」确认框
  * 视频播完 / 长时间停滞后，自动点左侧菜单下一个未完成节点（续播）
  * 每 5 分钟回主站读一次"本年度完成学时"与【本门】平台进度，达标即自停
  * 日志显示课程名称、平台学习百分比、课件节点完成百分比、视频 t/dur
  * 严格单窗口串行：切课前先关闭上一个学习页
  * 防后台节流启动参数（headless 下定时器/视频不被降频）
  * 请求记录器【同时挂主站页 pg 与学习页 lp】，修复 v2 只挂 pg 导致
    fast_v2_requests.log 看不到 pxkckj 学习页请求的缺陷

=============================================================================
2026-11-08 修订：一门课学完才换下一门（依据 05:34~06:11 正式挂机日志）
=============================================================================
用户反馈：「6 门课每门都没到 100%，程序似乎认为当前课程卡住就换下一门，
下一门又从头学」。三个叠加根因：

  1) 旧 PROGRESS_JS 用
       Math.min(所有卡片里 <99.9 的「学习进度：xx%」)
     取的是【整页最小值】，与当前在学哪门课无关。页面上只要有一门 0%
     的课程（用户截图里确实有 0% 的课），就恒返回 0。
     于是 stall 累加到 6，06:11:24 打出「进度连续 30 分钟未增长，换下一门」，
     而视频当时明明在正常播放（t 0 -> 1869.9/2036.2，还自动续播了下一节点）。
  2) build_course_pool() 返回 pool[:6]，seen 轮转完清空后又回到同样 6 门，
     于是脚本永远只在这 6 门里各学 30 分钟 —— 正是用户看到的现象。
  3) mark_seen() 在【打开课程之前】就写入，即使没学完也被视为已轮转过，
     进一步保证不会回头把某门课补到 100%。

本轮改动：
  * 删除「进度连续 30 分钟未增长 -> 换课」判定（它读的根本不是本门进度）；
  * 进度改为按 courseId 精确读取【本门】平台进度 + 学习页 .s_point 节点完成率；
  * 完成判据统一为「平台进度 100%」或「节点全完成且回主站复核通过」；
  * 单次会话到时不换课，用 sticky 在下一轮重新打开【同一门】继续；
  * 课程池上限 6 -> 40，自动补选阈值与池上限解耦；按平台进度降序，
    优先把最接近 100% 的课学完；
  * PARSE_ARGS_JS 带出课程名 / 平台进度% / courseId，日志逐门显示；
  * 不再用历史 seen 过滤课程（重启后未学完的课不会被跳过）；
  * 死循环保护：同一门连续重开 8 轮仍无进展才暂时 skip 并告警。

收益来自"整夜不中断"，不是让 1 小时变成 5 分钟。学习时长由平台按真实
在线时间累计，本脚本不干预计时口径。

=============================================================================
2026-11-08 第二轮修订：真正接上断点续学，不再从头重播
=============================================================================
用户反馈：某门课本来只学剩 40.9%，却从 07:22 一直学到 09:49（约 2.5 小时），
「明显没有断点续学，没有接上之前的学习进度」。静态分析 + 运行日志给出
四个叠加根因：

  1) 平台【根本不保存视频课件的续播位置】。
     courseware_index.js 构造 $.connectionPlay 时传入
         saveLearningItemTimeStatus: video/courseware -> return false
     connectionPlay.js 的 saveLearningItem() 首行即 return，而它只在
     beforeunload 被调用。铁证：steady_requests.log 全程只有
     queryLearningItem.json，一次 saveLearningItem.json 都没有；多数课程
     queryLearningItem 直接返回 {"data":{}}。
  2) 没有续播记录时 courseware_index.js 走 else 分支
     setTimeout(...,100) -> playFirstNode()，永远【从第一个节点从头播】。
     于是已学完的第 1 个节点（占 40.9%）又被完整重播一遍（约 32 分钟）。
  3) completestate 只在【点击后一个节点】时才回填前一个节点
     （courseware_index.js:387-408 的 getSingleItemCompleteState）。
     旧 NEXT_NODE_JS 却总找「第一个 completestate!='1' 的节点」，
     播完第 2 个节点后它仍未标记完成 -> 又点第 2 个 -> 视频重新从 0 加载。
     日志铁证：s_point_6580756626374087 在 07:55 / 08:27 / 08:59 被点了 3 次，
     zx2678361 同一段 1882.2 秒视频播了 3 遍，白耗约 62 分钟。
  4) 旧 NEXT_NODE_JS 的 `next || pts[0]` 在节点全完成时又去点第一个节点，
     09:49:25 日志里 zx2678351 再次从 59.6/1949.9 开始重播。

本轮改动：
  * 打开课程后按 .s_point[completestate] 主动跳到【第一个未完成节点】，
    跳过已完成节点（节点级断点续学），不再受 playFirstNode() 影响；
  * 每 60 秒把【真实 currentTime + 当前节点 itemId】写入平台自己的
    saveLearningItem.json，补齐平台缺失的秒级断点记录；写入值钳制在
    duration-5 以内，避免历史上 videoTime=3600>dur 导致 seek 卡死；
    这是恢复断点，不是伪造学习时长：不写完成状态、不写学时、不拖进度条；
  * NEXT_NODE_JS 改为点【当前选中节点(.s_pointerct)之后】的第一个未完成
    节点，播完一个节点就往后走，绝不回头重播；
  * 全部节点完成时不点任何节点，只回主站复核平台进度；
  * 增加「连续点到同一节点」兜底，防止平台状态刷新滞后时无限重播。

2026-11-08 20:4x 修复（用户日志：《…决定》#4601e0 播完第 3 节点后卡死）：
  * 现象：20:40:53 点第 4 个节点后 kjcourse iframe 消失，视频恒 0.0/0.0s、
    复核 reason=no_kj_frame，请求日志再无任何新 mp4 GET；旧版主循环只有
    `elif not st.get("noVideo")` 分支，对 noVideo 完全不处理 -> 空转到
    360 分钟会话上限。
  * 新增 noVideo 自愈：每 3 分钟回主站读本门平台进度；进度仍涨说明是
    PDF/网页/测验型节点（平台按真实在线时长计进度）-> 保持在线不干预；
    连续两次不增长 -> 结束本轮，由主循环重新打开同一门课重建课件链。
  * 片尾断点防死锁：视频播到片尾时不再把片尾秒数写进平台，改记片尾前
    2 分钟；apply_platform_resume 遇到库里残留的片尾断点同样钳制。
  * 复核后用实时平台进度刷新日志标签，不再一直显示选课时的旧百分比。

=============================================================================
用法
=============================================================================
  run_steady.bat 你的密码              # 正式挂机
  run_steady.bat 你的密码 diag         # 诊断：只跑一门、打印 frames/视频状态后退出
或：
  set "CMATC_PWD=你的密码"            (CMD；切勿写成 set CMATC_PWD='密码')
  python -u steady_study.py

可调环境变量：
  CMATC_TARGET      目标学时，默认 80
  CMATC_DWELL_MIN   单门「单次会话」上限分钟，默认 360（超时仍继续同一门，不换课）
  CMATC_BEAT_SEC    保活节拍秒数，默认 20
  CMATC_CREDIT_EVERY 读学时/进度间隔秒，默认 300
  CMATC_NEED        课程池上限门数，默认 40（旧版 6 会导致永远只在这 6 门里打转）
  CMATC_AUTO_CHOOSE_MIN 课程池少于此数才自动补选，默认 6
  CMATC_ROUNDS      轮数上限，0=不限
  CMATC_DIAG        1=诊断模式
  CMATC_USER        用户名，必填（无内置默认值；通过启动参数或环境变量提供）
  CMATC_SAVE_RESUME 1=保存真实续播位置（默认），0=关闭
  CMATC_APPLY_RESUME 1=重开课程时恢复到平台自己记录的真实播放秒数（默认），0=关闭

※ 2026-11-08 第三轮修订（同名课程「学完又重学」）：
  同一门课在「我的课程」(enterCourse) 与「课程中心」(enterCourseTimeLimit)
  各有一条记录，旧版按 URL 去重，导致同一 cid 留两条：一条 100%、
  一条 pct=None 被当成未完成，于是反复重学已完成的课。
  现改为按 cid 合并 + 按 cid 补读进度 + 开课前复核 100% 直接跳过；
  日志用 #cid短码 区分 6 门同名课程；节点完成状态滞后时不再往回跳。

停止：在脚本目录创建 stop_steady.flag 文件（脚本每轮检查，会先关闭学习页再退出）。

※ 平台为单点登录，本脚本登录会踢掉其他会话：启动前请先停掉
  auto_study.py / fast_study.py / fast_study_v2.py。
※ 本脚本不修改任何现有文件，不结束任何进程。
"""
import os, re, sys, time, json, datetime, traceback, contextlib
from playwright.sync_api import sync_playwright

from common import EDGE, HOST, OUT, USER, PWD, ARGS, login

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
TARGET = float(os.environ.get("CMATC_TARGET", "80"))
# 单门「单次会话」上限：只用于防止单个学习页无限死等；超时后主循环会用
# sticky 重新打开【同一门】继续，绝不因此换下一门。
DWELL_MIN = float(os.environ.get("CMATC_DWELL_MIN", "360"))
BEAT_SEC = int(os.environ.get("CMATC_BEAT_SEC", "20"))
CREDIT_EVERY = int(os.environ.get("CMATC_CREDIT_EVERY", "300"))
# 旧版 NEED=6 + seen 轮转，学完 6 门清空 seen 后又回到同样 6 门，
# 结果就是用户看到的「6 门课每门都没到 100%」。改为覆盖全部课程。
NEED = int(os.environ.get("CMATC_NEED", "40"))
# 自动补选的触发阈值与课程池上限解耦：NEED 变大不应触发狂选课。
AUTO_CHOOSE_MIN = int(os.environ.get("CMATC_AUTO_CHOOSE_MIN", "6"))
ROUNDS = int(os.environ.get("CMATC_ROUNDS", "0"))
DIAG = os.environ.get("CMATC_DIAG", "0") == "1"
# 平台对视频课件不保存续播位置（详见文件头「第二轮修订」）。
# 这里补写【真实 currentTime】，使重开课程能从节点内秒级位置继续。
SAVE_RESUME = os.environ.get("CMATC_SAVE_RESUME", "1") == "1"
# 实测 2026-11-08 10:17~10:24：saveLearningItem.json 确实把 videoTime 写进平台库
# （reset_video_time.py dry 复核到 videoTime=120），但重开课程走「课件 iframe 链
# 已存在，自动进入」路径时平台不再调用 queryLearningItem，播放器仍从 0 秒起播。
# 这里在打开课程后读回平台自己的断点，把播放位置恢复到那个真实秒数。
# 只设 currentTime，不写完成状态、不写学时、不改播放速率、不跳到末尾。
APPLY_RESUME = os.environ.get("CMATC_APPLY_RESUME", "1") == "1"

# 防后台节流：headless 下 Chromium 会把后台页的 timer / 视频降频，
# 会直接影响 studyTime.js 的 5 分钟上报与视频播放。仅在本文件内追加，
# 不修改 common.py。
ARGS = list(ARGS) + [
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-features=CalculateNativeWinOcclusion",
]

STOP_FLAG = os.path.join(OUT, "stop_steady.flag")
LOG = os.path.join(OUT, "steady_run.log")
REQ_LOG = os.path.join(OUT, "steady_requests.log")
SEEN = os.path.join(OUT, "steady_seen.txt")

MY_COURSE_URL = HOST + "/u/student/study/myCourse.action"
MARKET_URL = HOST + "/cms/courseMarketNew.htm"

# 调试时每门课最长停留收敛，避免诊断模式挂一夜
if DIAG:
    DWELL_MIN = min(DWELL_MIN, 2)


def log(msg):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def stopped():
    return os.path.exists(STOP_FLAG)


def load_seen():
    if not os.path.exists(SEEN):
        return set()
    return set(x.strip() for x in open(SEEN, encoding="utf-8") if x.strip())


def mark_seen(x):
    with open(SEEN, "a", encoding="utf-8") as f:
        f.write(x + "\n")


def nav(pg, url, wait=5000):
    try:
        pg.goto(url, wait_until="commit", timeout=60000)
    except Exception as e:
        log("  goto warn: %s" % str(e)[:110])
    pg.wait_for_timeout(wait)


def tick_wait(page, seconds):
    """用 Playwright 的 wait_for_timeout 等待，保证事件回调（请求记录）能被 pump。"""
    try:
        page.wait_for_timeout(int(seconds * 1000))
    except Exception:
        time.sleep(seconds)


# ---------------------------------------------------------------------------
# 学时 / 进度读取（沿用 v2 的稳健实现：显式等节点 + 3 次取样取最大值）
# ---------------------------------------------------------------------------
CREDIT_JS = r"""() => {
    const nodes = document.querySelectorAll('h4,div,span,li,td,p');
    for (const e of nodes) {
        if ((e.textContent||'').trim() === '本年度完成学时') {
            const t = (e.parentElement ? e.parentElement.textContent : '').replace(/\s+/g,' ');
            const m = t.match(/(\d+(?:\.\d+)?)\s*学时/);
            if (m) return {v: m[1], how: 'label'};
        }
    }
    const m2 = (document.body.innerText||'').match(/本年度完成学时[^\d]{0,20}(\d+(?:\.\d+)?)/);
    if (m2) return {v: m2[1], how: 'text'};
    return {v: null, how: 'none'};
}"""

# 学习页课件菜单节点完成情况：这是【当前这门课】最可靠的实时进度，
# 不依赖主站「我的课程」页的分页，也不受别的课程 0% 干扰。
# 旧 PROGRESS_JS 取整页所有「学习进度：xx%」里 <99.9 的最小值，
# 与当前在学哪门课无关；页面只要有一门 0% 就恒返回 0，
# 进而误判「进度连续 30 分钟未增长」并频繁切课 —— 这是本轮修复的核心。
NODE_PROGRESS_JS = r"""() => {
    const pts = [...document.querySelectorAll('.s_point')];
    if (!pts.length) return null;
    const done = pts.filter(p => (p.getAttribute('completestate')||'0') === '1').length;
    return {total: pts.length, done: done,
            pct: Math.round(done * 1000 / pts.length) / 10,
            allDone: done === pts.length};
}"""

# 课件菜单详细状态：当前选中节点 / 第一个未完成节点。
# 平台 playFirstNode() 总是从第一个节点开始，且不会跳过已完成节点，
# 所以需要脚本自己判断「该从第几个节点开始」，实现节点级断点续学。
NODE_INFO_JS = r"""() => {
    const pts = [...document.querySelectorAll('.s_point')];
    if (!pts.length) return null;
    const flags = pts.map(p => (p.getAttribute('completestate')||'0') === '1');
    const curIdx = pts.findIndex(p => p.classList.contains('s_pointerct'));
    const firstUndone = flags.indexOf(false);
    return {
        total: pts.length,
        done: flags.filter(Boolean).length,
        curIdx: curIdx,
        curId: curIdx >= 0 ? (pts[curIdx].id || '') : '',
        firstUndone: firstUndone,
        firstUndoneId: firstUndone >= 0 ? (pts[firstUndone].id || '') : ''
    };
}"""

# 按序号点击课件节点（用于跳到第一个未完成节点）
CLICK_NODE_JS = r"""(i) => {
    const pts = [...document.querySelectorAll('.s_point')];
    if (i < 0 || i >= pts.length) return {ok:false, reason:'bad_index'};
    try { pts[i].click(); }
    catch(e) { return {ok:false, reason:String(e).slice(0,80)}; }
    return {ok:true, id: pts[i].id || '', index:i, total:pts.length};
}"""

# 把【真实播放秒数 + 当前节点 itemId】写进平台自己的断点记录。
# 平台对 video/courseware 把 saveLearningItemTimeStatus 设为 false，
# beforeunload 时 connectionPlay.saveLearningItem() 首行就 return，
# 因此 steady_requests.log 里只有 queryLearningItem、没有 saveLearningItem。
# 结果：重开课程 queryLearningItem 返回 {"data":{}} -> playFirstNode() 从头播。
# 这里补写的是真实 currentTime（Python 侧已钳制到 duration-5 以内），
# 不动完成状态、不动学时、不拖进度条。
SAVE_RESUME_JS = r"""(p) => {
    const $cid = document.querySelector('#currentCourseId');
    const cid = ($cid && $cid.value) ? $cid.value : (p.cid || '');
    const $cur = document.querySelector('.s_point.s_pointerct');
    const iid = $cur ? ($cur.id || '').replace('s_point_', '') : '';
    const t = Math.max(0, Math.floor(p.t || 0));
    if (!cid || !iid || t < 5) {
        return {ok:false, reason:'not_ready', cid:cid, iid:iid, t:t};
    }
    const b = new URLSearchParams();
    b.set('params.courseId', cid);
    b.set('params.itemId', iid);
    b.set('params.videoTime', String(t));
    return fetch('/learnspace/learn/learnCourseware/saveLearningItem.json', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: b.toString(),
        credentials: 'same-origin'
    }).then(r => r.text())
      .then(x => ({ok:true, cid:cid, iid:iid, t:t, resp:x.slice(0,60)}))
      .catch(e => ({ok:false, reason:String(e).slice(0,90)}));
}"""

# 只读：取回平台库里该课程的断点（itemId + videoTime）。
QUERY_RESUME_JS = r"""(p) => {
    const b = new URLSearchParams();
    b.set('params.courseId', p.cid);
    return fetch('/learnspace/learn/learnCourseware/queryLearningItem.json', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: b.toString(),
        credentials: 'same-origin'
    }).then(r => r.text())
      .then(x => {
          let d = null;
          try { d = JSON.parse(x); } catch(e) {
              return {ok:false, reason:'bad_json', raw:String(x).slice(0,80)};
          }
          return {ok:true, data: (d && d.data) ? d.data : {}};
      })
      .catch(e => ({ok:false, reason:String(e).slice(0,90)}));
}"""

# 只把播放位置恢复到【平台自己记录的真实秒数】。
# 钳制在 duration-10 以内，绝不跳到片尾，也不会触发节点完成/学时上报。
SEEK_RESUME_JS = r"""(p) => {
    const vs = [...document.querySelectorAll('video')];
    if (!vs.length) return {ok:false, reason:'no_video'};
    const v = vs[0];
    const dur = isFinite(v.duration) ? v.duration : 0;
    if (!dur || v.readyState < 1) {
        return {ok:false, reason:'not_ready', ready:v.readyState, dur:Math.round(dur)};
    }
    const target = Math.max(0, Math.min(p.t, dur - 10));
    const before = v.currentTime || 0;
    if (target - before < 15) {
        return {ok:true, skipped:true, before:Math.round(before),
                target:Math.round(target), reason:'already_there'};
    }
    try { v.currentTime = target; }
    catch(e) { return {ok:false, reason:String(e).slice(0,80)}; }
    return {ok:true, before:Math.round(before), target:Math.round(target),
            after:Math.round(v.currentTime || 0), dur:Math.round(dur)};
}"""


def read_credit(pg):
    nav(pg, MY_COURSE_URL, wait=2500)
    if "loginNew" in pg.url or "/cms/login" in pg.url:
        log("  学时页疑似登录态失效: %s" % pg.url[:110])
        return None
    try:
        pg.wait_for_function("""() => {
            return [...document.querySelectorAll('h4,div,span,li,td,p')].some(
                e => (e.textContent||'').trim() === '本年度完成学时');
        }""", timeout=15000)
    except Exception:
        pass
    samples = []
    for round_i in range(2):
        for _ in range(4):
            try:
                r = pg.evaluate(CREDIT_JS)
                if r and r.get("v") is not None:
                    samples.append(float(r["v"]))
            except Exception:
                pass
            pg.wait_for_timeout(2000)
        # steady_run.log 22:46:57 读到 0.0：页面初始把「本年度完成学时」渲染成
        # 占位 0.0，真实值要晚几秒才由 AJAX 回填。只要出现过非 0 值就取最大值。
        if any(x > 0 for x in samples):
            break
        if round_i == 0:
            log("  学时仍为占位 0.0，页面数据未就绪，再等 8 秒重取...")
            pg.wait_for_timeout(8000)
    if not samples:
        log("  学时读取失败（URL=%s）" % pg.url[:110])
        return None
    val = max(samples)          # 学时单调不减；0.0 多为占位值
    if len(set(samples)) > 1:
        log("  学时取样: %s -> 采用 %s" % (samples, val))
    if val == 0:
        log("  [warn] 学时读到 0.0，若实际已有学时说明页面未渲染完；"
            "达标自停可能失效，请对照学习档案页面确认")
    return val


def read_progress(pg, cid):
    """按 courseId 精确读取【当前这门课】在「我的课程」页显示的进度%。
    旧实现取整页所有课程里的最小进度，页面只要有一门 0% 就恒返回 0，
    与本门是否学完毫无关系 —— 已废弃。
    课程卡片由 AJAX 渲染，故做 3 次取样；仍读不到返回 None（不猜、不误判）。
    """
    if not cid:
        return None
    for i in range(3):
        try:
            v = pg.evaluate(PROGRESS_BY_CID_JS, cid)
            if v is not None:
                return v
        except Exception:
            pass
        if i < 2:
            pg.wait_for_timeout(1200)
    return None


def node_progress(lp):
    """读学习页课件菜单：总节点数 / 已完成数 / 完成率 / 是否全部完成。"""
    for f in lp.frames:
        try:
            r = f.evaluate(NODE_PROGRESS_JS)
        except Exception:
            continue
        if r and r.get("total"):
            return r
    return None


def menu_frame(lp):
    """找到含 .s_point 课件菜单的 frame（不按 URL 猜，frame 顺序不固定）。"""
    for f in lp.frames:
        try:
            if f.evaluate("() => document.querySelectorAll('.s_point').length"):
                return f
        except Exception:
            continue
    return None


def node_info(lp):
    mf = menu_frame(lp)
    if mf is None:
        return None
    try:
        return mf.evaluate(NODE_INFO_JS)
    except Exception:
        return None


def page_course_id(lp):
    """学习页 URL 里的 params.courseId（可能带 ___ 后缀），与平台口径一致。"""
    m = re.search(r"params\.courseId=([^&]+)", lp.url or "")
    return m.group(1) if m else ""


def resume_to_unfinished_node(lp, tag):
    """【节点级断点续学】打开课程后跳到第一个未完成节点。

    平台在 queryLearningItem 返回空记录时走 playFirstNode()，永远从第一个
    节点开始播，已完成节点会被整段重播。这里按 .s_point[completestate]
    主动定位；若平台已正确定位到未完成节点则完全不干预，
    以保留其 iframe URL 里的 params.videoTime 秒级续播位置。
    """
    info = None
    for _ in range(10):                 # 菜单由 AJAX 渲染，最多等约 20 秒
        info = node_info(lp)
        if info and info.get("total"):
            break
        tick_wait(lp, 2)
    if not info or not info.get("total"):
        log("  [%s] 断点续学：未读到课件菜单节点，沿用平台默认起点" % tag)
        return None
    cur, first = info.get("curIdx", -1), info.get("firstUndone", -1)
    log("  [%s] 断点续学：节点已完成 %s/%s，平台当前停在第 %s 个，"
        "第一个未完成是第 %s 个"
        % (tag, info.get("done"), info["total"],
           (cur + 1) if cur >= 0 else "?", (first + 1) if first >= 0 else "无"))
    if first < 0:
        log("  [%s] 断点续学：节点全部已完成，交给主循环复核平台进度" % tag)
        return info
    # 部分课件模板不回写 completestate（日志里 4 个节点播到 61% 仍是 0/4）。
    # 此时 firstUndone 恒为 0，若平台已经自动停在第 3 个节点，旧逻辑会
    # 点回第 1 个节点从头重播 —— 这是「又重新学习」的第二层原因。
    # 只要平台定位不早于首个未完成节点，就保持平台定位，绝不往回跳。
    if first <= cur:
        log("  [%s] 断点续学：平台停在第 %s 个节点，首个未完成是第 %s 个；"
            "保持平台定位不往回跳（节点完成状态可能滞后，保留节点内续播位置）"
            % (tag, cur + 1, first + 1))
        return info
    mf = menu_frame(lp)
    if mf is None:
        return info
    old_src = video_state(lp).get("currentSrc") or ""
    try:
        r = mf.evaluate(CLICK_NODE_JS, first)
    except Exception as e:
        log("  [%s] 断点续学：点击节点异常 %s" % (tag, str(e)[:100]))
        return info
    log("  [%s] 断点续学：跳过前 %s 个已完成节点，改从第 %s 个节点开始 | %s"
        % (tag, first, first + 1, r))
    # 点节点会替换 #mainFrame 的 src，等新 mp4 真正加载出来再 beat()，
    # 否则保活节拍会打到旧 document 上。
    for _ in range(20):
        tick_wait(lp, 1)
        st = video_state(lp)
        ns = st.get("currentSrc") or ""
        if ns and ns != old_src and (st.get("ready") or 0) >= 2:
            log("  [%s] 断点续学：新节点课件已加载 t=%s/%s src=%s"
                % (tag, st.get("t"), st.get("dur"), ns[-45:]))
            break
    return info


def save_resume_position(lp, tag, cid, st, verbose=False):
    """【秒级断点续学】把真实 currentTime + 当前节点写入平台断点记录。

    只调平台自己的 saveLearningItem.json，值来自真实播放进度并钳制到
    duration-5 以内（历史上 videoTime=3600 > dur 会让播放器 seek 卡死）。
    不写完成状态、不写学时、不拖动 currentTime。
    """
    if not SAVE_RESUME:
        return None
    t, dur = st.get("t") or 0, st.get("dur") or 0
    if (st.get("ready") or 0) < 2 or t < 5 or dur <= 0:
        return None
    # 【片尾断点防死锁】旧版把片尾秒数（如 1871/1877）写进平台，下一轮
    # 重开课程时被恢复到片尾，脚本立刻又判「本节点播完」-> 再点下一节点；
    # 若下一节点恰好无视频，就形成「恢复片尾 -> 点下一节点 -> 无视频」死循环。
    # 这里回退到片尾前 2 分钟（这段确实真实播放过），保证重开后仍有真实
    # 播放时间，且绝不在平台库里留下片尾断点。
    if t >= dur - 20:
        safe_t = max(0, int(dur) - 120)
        if safe_t < 10:
            return None
    else:
        safe_t = max(0, min(int(t), int(dur) - 5))
    mf = menu_frame(lp)
    if mf is None:
        return None
    try:
        r = mf.evaluate(SAVE_RESUME_JS,
                        {"cid": page_course_id(lp) or cid, "t": safe_t})
    except Exception as e:
        if verbose:
            log("  [%s] 断点保存异常: %s" % (tag, str(e)[:100]))
        return None
    if verbose or not r.get("ok"):
        log("  [%s] 断点保存: %s" % (tag, r))
    return r


def apply_platform_resume(lp, tag):
    """【恢复真实播放位置】重开课程时把 currentTime 设回平台自己记录的秒数。

    实测（2026-11-08）结论：saveLearningItem.json 写入成功，平台库里确有
    videoTime；但课程重开走「课件 iframe 链已存在，自动进入」路径时，
    平台不再调用 queryLearningItem，播放器从 0 秒起播。
    这里读回平台断点，仅在同一节点、视频已就绪、且尚未接上的情况下恢复，
    不写完成状态、不写学时、不改播放速率、不跳到片尾。
    """
    if not APPLY_RESUME:
        return None
    cid = page_course_id(lp)
    if not cid:
        return None
    mf = menu_frame(lp)
    if mf is None:
        return None
    try:
        q = mf.evaluate(QUERY_RESUME_JS, {"cid": cid})
    except Exception as e:
        log("  [%s] 断点读取异常: %s" % (tag, str(e)[:110]))
        return None
    if not q or not q.get("ok"):
        log("  [%s] 断点读取失败: %s" % (tag, q))
        return None
    data = q.get("data") or {}
    iid = str(data.get("itemId") or "")
    try:
        vt = float(data.get("videoTime") or 0)
    except (TypeError, ValueError):
        vt = 0.0
    if not iid or vt < 10:
        log("  [%s] 平台无有效断点（itemId=%s videoTime=%s），按平台默认起点播放"
            % (tag, iid or "-", vt))
        return None
    info = node_info(lp) or {}
    cur = (info.get("curId") or "").replace("s_point_", "")
    if cur and cur != iid:
        log("  [%s] 平台断点属于节点 %s，当前在 %s，不恢复（避免错位重播）"
            % (tag, iid, cur))
        return None
    # beat() 里点「开始学习」会重建 <video>，必须等新的 video 拿到 metadata。
    st = {}
    for _ in range(30):
        st = video_state(lp)
        if (st.get("ready") or 0) >= 2 and (st.get("dur") or 0) > 0:
            break
        tick_wait(lp, 2)
    if (st.get("ready") or 0) < 2 or not (st.get("dur") or 0):
        log("  [%s] 视频未就绪（ready=%s dur=%s），本次不恢复断点"
            % (tag, st.get("ready"), st.get("dur")))
        return None
    # 平台库里可能残留旧版写入的「片尾断点」。恢复到片尾会让本节点立刻
    # 被判播完并反复点下一节点，这里钳制到片尾前 2 分钟（真实播放过的区间）。
    dur = st.get("dur") or 0
    if dur > 180 and vt >= dur - 20:
        old_vt = vt
        vt = dur - 120
        log("  [%s] 平台断点 %ss 已在本节点片尾(%.0fs)，钳制到 %.0fs 避免立即判完成"
            % (tag, int(old_vt), dur, vt))
    kj = frame_of(lp, "kjcourse")
    if kj is None:
        return None
    try:
        r = kj.evaluate(SEEK_RESUME_JS, {"t": vt})
    except Exception as e:
        log("  [%s] 恢复播放位置异常: %s" % (tag, str(e)[:110]))
        return None
    log("  [%s] 恢复播放位置 | 平台断点 itemId=%s videoTime=%ss | 当前 %ss/%ss | %s"
        % (tag, iid, int(vt), st.get("t"), st.get("dur"), r))
    return r


def course_label(c):
    """日志用：课程名 + #cid短码 + 平台进度%。

    平台有 6 门同名《中共中央…》课程，名字还被截断成同一个字符串，
    旧日志完全分不清学的是哪一门口，看起来像「同一门学完又重学」。
    """
    cid = c.get("cid") or ""
    short = cid[-6:] if cid else (c.get("url") or "")[-6:]
    name = c.get("name") or ("课程" + short)
    label = ("%s#%s" % (name, short)) if short else name
    pct = c.get("pct")
    if pct is None:
        return label
    return "%s [%s%%]" % (label, pct)


def already_finished(pg, cid, tag):
    """【开课前最后一道闸】平台已判 100% 就绝不打开学习页。

    课程池去重之外再加一道保险：万一某条重复记录漏网，或平台进度在
    选课后才刷新到 100%，这里也会拦下，不会再出现「学完又重学」。
    """
    if not cid:
        return False
    try:
        nav(pg, MY_COURSE_URL, wait=2500)
        pct = read_progress(pg, cid)
    except Exception as e:
        log("  [%s] 开课前复核异常（按未完成继续）: %s" % (tag, str(e)[:90]))
        return False
    if pct is not None and pct >= 99.9:
        log("  [%s] 开课前复核：平台进度 %s%%，本门已完成，跳过不重学" % (tag, pct))
        return True
    return False


def confirm_done(pg, cid, tag):
    """课件节点全完成后，回主站按 courseId 复核【本门】平台进度是否真的 100%。
    read_credit() 已把 pg 停在「我的课程」页，这里重新导航一次确保数据最新。
    返回 (是否确认完成, 平台进度)。读不到进度时按节点全完成处理但打告警，
    避免因为列表分页（只显示第一页）而永久卡在同一门。
    """
    try:
        nav(pg, MY_COURSE_URL, wait=3000)
        pct = read_progress(pg, cid)
    except Exception as e:
        log("  [%s] 完成复核异常: %s" % (tag, str(e)[:110]))
        return True, None
    if pct is None:
        log("  [%s] [warn] 平台进度未读到（列表分页/渲染延迟）；"
            "因课件节点已全部完成，暂按本门学完处理，下一轮仍会按平台进度重新核对"
            % tag)
        return True, None
    return pct >= 99.9, pct


# ---------------------------------------------------------------------------
# 课程池：我的课程(继续学习) + 课程中心(开始学习)，不足则 HTTP 直接选课
# 说明：HTTP 选课等价于用户点掉 layer.confirm 的「确定」，属正常自动化，
#       不涉及任何学习记录伪造。
# ---------------------------------------------------------------------------
# 解析课程卡片：除原来的 fn/args/url 外，额外带出
#   cid  = URL 里的 courseId（用于按课程精确读取进度）
#   name = 课程名称（日志显示用）
#   pct  = 该卡片的「学习进度：xx%」（平台显示的学习百分比）
PARSE_ARGS_JS = r"""(fnName) => {
    const NOISE = /^(20\d\d年|\d+(\.\d+)?学时|上次学习此课程|已完成|未完成|学习进度.*|继续学习|开始学习|查看详情|立即选课|综合排序|按.*排序|更多|\d+人|无|课程排序.*)$/;
    const out = [];
    document.querySelectorAll('a[onclick]').forEach(a => {
        const oc = a.getAttribute('onclick') || '';
        if (oc.indexOf(fnName + '(') < 0) return;
        const start = oc.indexOf(fnName + '(') + fnName.length + 1;
        const body = oc.slice(start, oc.lastIndexOf(')') + 1);
        const args = [];
        const re = /'([^']*)'|"([^"]*)"/g;
        let m;
        while ((m = re.exec(body)) !== null) args.push(m[1] !== undefined ? m[1] : m[2]);
        if (!args.length) return;
        const url = args[0] || '';
        // enterCourse / enterCourseTimeLimit 的第 2 个参数就是 courseId（32 位 hex），
        // 优先用它；URL 里的 courseId= 作为兜底，并去掉学习页常见的 ___ 后缀。
        let cid = (args[1] && /^[0-9a-zA-Z]{16,}$/.test(args[1]))
                  ? args[1].replace(/_+$/, '') : '';
        if (!cid) {
            const cm = url.match(/courseId=([^&]+)/);
            if (cm) cid = decodeURIComponent(cm[1]).replace(/_+$/, '');
        }

        // 从按钮向上找「卡片」容器：命中「学习进度」即停，避免爬到整页。
        let box = a;
        for (let i = 0; i < 6 && box.parentElement; i++) {
            box = box.parentElement;
            const t = box.innerText || '';
            if (/学习进度/.test(t)) break;
            if (t.length > 500) break;
        }
        const bt = (box.innerText || '').replace(/\s+/g, ' ');
        const pm = bt.match(/学习进度[:：]\s*([\d.]+)\s*%/);
        const pct = pm ? parseFloat(pm[1]) : null;

        // 课程名：优先带 title 的元素 / openResourceByIp 链接文本，
        // 否则取卡片内最长的一行中文（排除年份、学时、按钮等噪声）。
        let name = '';
        const na = box.querySelector('a[onclick*="openResourceByIp"], [title]');
        if (na) name = (na.getAttribute('title') || na.textContent || '').trim();
        if (!name) {
            const parts = (box.innerText || '').split(/\n+/).map(s => s.trim()).filter(Boolean);
            const cand = parts.filter(s => !NOISE.test(s) &&
                /[\u4e00-\u9fa5]/.test(s) && s.length >= 4);
            if (cand.length) name = cand.sort((x, y) => y.length - x.length)[0];
        }
        out.push({fn: fnName, args: args, text: (a.textContent||'').trim().slice(0,20),
                  url: url, cid: cid, name: name.slice(0, 60), pct: pct});
    });
    return out;
}"""

# 在「我的课程」页按 courseId 精确读取【当前这门课】的平台学习进度。
# 旧版取整页最小进度，会被列表里 0% 的课程拉成 0，完全不代表当前课程。
PROGRESS_BY_CID_JS = r"""(cid) => {
    if (!cid) return null;
    for (const a of document.querySelectorAll('a[onclick]')) {
        const oc = a.getAttribute('onclick') || '';
        // 不限定 enterCourse(：课程中心/我的课程两个入口的 onclick 名不同，
        // 只要链接里带这个 courseId 就尝试读它的「学习进度」。
        if (oc.indexOf(cid) < 0) continue;
        let box = a;
        for (let i = 0; i < 6 && box.parentElement; i++) {
            box = box.parentElement;
            if (/学习进度/.test(box.innerText || '')) break;
        }
        const t = (box.innerText || '').replace(/\s+/g, ' ');
        const m = t.match(/学习进度[:：]\s*([\d.]+)\s*%/);
        if (m) return parseFloat(m[1]);
    }
    return null;
}"""


def collect_from_mycourse(pg):
    nav(pg, MY_COURSE_URL, wait=3500)
    return pg.evaluate(PARSE_ARGS_JS, "enterCourse")


def collect_from_market(pg):
    nav(pg, MARKET_URL, wait=4000)
    return pg.evaluate(PARSE_ARGS_JS, "enterCourseTimeLimit")


def collect_choose_ids(pg, limit):
    return pg.evaluate("""(lim) => {
        const out = [];
        document.querySelectorAll('a[onclick*="chooseCourseTimeLimit"]').forEach(a => {
            const m = (a.getAttribute('onclick')||'').match(/chooseCourseTimeLimit\\(\\s*'([^']+)'/);
            if (m) out.push(m[1]);
        });
        return out.slice(0, lim);
    }""", limit)


def choose_by_http(pg, ids):
    return pg.evaluate("""async (ids) => {
        const out = [];
        for (const id of ids) {
            try {
                const body = new URLSearchParams();
                body.append('opt', '3');
                body.append('entity.itemIds', id);
                const r = await fetch('/u/study/saveCourses.json', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: body.toString(),
                    credentials: 'same-origin'
                });
                let txt = '';
                try { txt = (await r.text()).slice(0, 160); } catch(e) {}
                out.push({id: id.slice(0,12), status: r.status, body: txt});
            } catch (e) {
                out.push({id: id.slice(0,12), error: String(e).slice(0,80)});
            }
        }
        return out;
    }""", ids)


def add_unique(pool, items):
    """按 courseId 去重并合并信息。

    【2026-11-08 修复】旧版按 URL 去重，但同一门课在「我的课程」走
    enterCourse()、「课程中心」走 enterCourseTimeLimit()，两条 URL 字符串不同，
    于是同一 cid 在课程池里出现两次：一条带进度 100%，一条 pct=None。
    主循环把 pct=None 当作「未完成」，结果反复重学已经 100% 的课程
    （日志 15:57 / 18:47 两次重学 cid=...604a5 即此因）。
    现在同一 cid 只保留一条，并把进度/名称合并进来。
    """
    by_cid, by_url = {}, {}
    for i, c in enumerate(pool):
        if c.get("cid"):
            by_cid.setdefault(c["cid"], i)
        if c.get("url"):
            by_url.setdefault(c["url"], i)

    def merge(old, new):
        op, np_ = old.get("pct"), new.get("pct")
        if np_ is not None and (op is None or np_ > op):
            old["pct"] = np_
        if len(new.get("name") or "") > len(old.get("name") or ""):
            old["name"] = new["name"]
        if not old.get("cid") and new.get("cid"):
            old["cid"] = new["cid"]
        return old

    for c in items:
        if not c.get("url"):
            continue
        cid = c.get("cid")
        i = by_cid.get(cid) if cid else None
        if i is None:
            i = by_url.get(c["url"])
        if i is None:
            i = len(pool)
            pool.append(dict(c))
        else:
            merge(pool[i], c)
        by_url.setdefault(c["url"], i)
        if cid:
            by_cid.setdefault(cid, i)


def build_course_pool(pg, need):
    pool = []
    try:
        a = collect_from_mycourse(pg)
        log("  我的课程(继续学习/查看详情): %d 门" % len(a))
        add_unique(pool, a)
    except Exception as e:
        log("  我的课程读取异常: %s" % str(e)[:120])
    try:
        b = collect_from_market(pg)
        log("  课程中心(开始学习): %d 门" % len(b))
        add_unique(pool, b)
    except Exception as e:
        log("  课程中心读取异常: %s" % str(e)[:120])

    if len(pool) < AUTO_CHOOSE_MIN:
        try:
            ids = collect_choose_ids(pg, max(AUTO_CHOOSE_MIN * 2, 10))
            log("  课程池不足 %d 门，HTTP 直接选课 %d 门（等价于点确认框）..."
                % (AUTO_CHOOSE_MIN, len(ids)))
            res = choose_by_http(pg, ids)
            ok = 0
            for r in res:
                if not isinstance(r, dict):
                    continue
                if r.get("status") == 200 and "success" in str(r.get("body", "")):
                    ok += 1
            log("  选课结果: %s" % json.dumps(res[:8], ensure_ascii=False)[:420])
            log("  其中疑似成功: %d" % ok)
            pg.wait_for_timeout(2000)
            for c in collect_from_market(pg):
                add_unique(pool, c)
            for c in collect_from_mycourse(pg):
                add_unique(pool, c)
        except Exception as e:
            log("  HTTP 选课异常: %s" % str(e)[:150])
    # 课程中心卡片不显示「学习进度：xx%」，解析出的 pct 是 None。
    # 在「我的课程」页按 cid 补读一次：既让日志显示真实百分比，
    # 也避免把「已完成但卡片没写进度」的课当成未完成而重学。
    try:
        nav(pg, MY_COURSE_URL, wait=2500)
        missing = [c for c in pool if c.get("pct") is None and c.get("cid")]
        if missing:
            filled = 0
            for c in missing:
                try:
                    v = pg.evaluate(PROGRESS_BY_CID_JS, c["cid"])
                except Exception:
                    v = None
                if v is not None:
                    c["pct"] = v
                    filled += 1
            log("  按 cid 补读平台进度: %d/%d 门读到" % (filled, len(missing)))
    except Exception as e:
        log("  补读进度异常: %s" % str(e)[:110])
    # 平台进度降序：优先把最接近 100% 的课学完，尽快拿到一门「已完成」。
    # pct 缺失（课程中心未选修的课）视为 0，排在后面。
    pool.sort(key=lambda c: (-(c.get("pct") if c.get("pct") is not None else 0),
                            not bool(c.get("name"))))
    log("  最终课程池: %d 门（按平台学习进度降序）" % len(pool))
    for c in pool[:12]:
        log("    · %s  cid=%s" % (course_label(c), c.get("cid") or "-"))
    if len(pool) > 12:
        log("    · ... 其余 %d 门略" % (len(pool) - 12))
    return pool[:need]


# ---------------------------------------------------------------------------
# 打开真实学习页：调页面自身函数 -> expect_popup 捕获 _learnspace
# ---------------------------------------------------------------------------
CALL_FN_JS = r"""(p) => {
    const fn = window[p.fn];
    if (typeof fn !== 'function') return 'NO_FN';
    try { fn.apply(null, p.args); return 'CALLED'; }
    catch (e) { return 'ERR:' + String(e).slice(0,100); }
}"""


def ensure_fn_page(pg, course):
    want = MY_COURSE_URL if course["fn"] == "enterCourse" else MARKET_URL
    key = "myCourse" if course["fn"] == "enterCourse" else "courseMarketNew"
    if key not in pg.url:
        nav(pg, want, wait=4000)
    ok = pg.evaluate("(n) => typeof window[n] === 'function'", course["fn"])
    if not ok:
        nav(pg, want, wait=5000)
        ok = pg.evaluate("(n) => typeof window[n] === 'function'", course["fn"])
    return ok


def open_learnspace(pg, ctx, course, tag, old_lp):
    """返回 (学习页, 打开方式)。任一时刻只保留一个学习页。"""
    if old_lp is not None and not old_lp.is_closed():
        with contextlib.suppress(BaseException):
            old_lp.close()
    if not ensure_fn_page(pg, course):
        log("  [%s] 页面缺少函数 %s，跳过" % (tag, course["fn"]))
        return None, "missing_fn"
    lp = None
    how = "popup"
    try:
        with pg.expect_popup(timeout=25000) as pop:
            r = pg.evaluate(CALL_FN_JS, {"fn": course["fn"], "args": course["args"]})
            if r != "CALLED":
                log("  [%s] 调用函数返回 %s" % (tag, r))
        lp = pop.value
    except Exception as e:
        log("  [%s] expect_popup 超时(%s)，尝试从已有页面查找" % (tag, str(e)[:70]))
    if lp is None:
        for p in ctx.pages:
            u = p.url
            if "signLearn" in u or "learnspace/learn" in u or "templateeight" in u:
                lp = p
                how = "existing_page"
                break
    if lp is None:
        log("  [%s] 未捕获到 _learnspace，跳过本门（不裸跳，避免前置链路缺失）" % tag)
        return None, "no_popup"
    lp.set_default_timeout(20000)
    lp.wait_for_timeout(6000)
    return lp, how


# ---------------------------------------------------------------------------
# 稳态播放：本脚本的核心新增部分
# ---------------------------------------------------------------------------
def frame_of(lp, kw):
    for f in lp.frames:
        if kw in (f.url or ""):
            return f
    return None


def click_courseware_tab(lp, tag):
    """
    【v1/v2 缺失的关键一步】
    学习页默认停在 course_detail.action（课程简介），不点「课件」就不会加载
    courseware_index.action -> content_webCourseware.action -> kjcourse iframe 链，
    v2 日志里的 no_sco_frame 正是这个原因。
    """
    if frame_of(lp, "courseware_index.action") or frame_of(lp, "kjcourse"):
        log("  [%s] 课件 iframe 链已存在（断点续学自动进入），无需点「课件」tab" % tag)
        return "already"
    how = "none"
    try:
        lp.get_by_text("课件", exact=True).first.click(timeout=8000)
        how = "playwright"
    except Exception:
        pass
    if how == "none":
        # steady_run.log 22:47:54 显示点击结果 'none'：上一版只搜主 frame 且加了
        # offsetParent!==null，把 tab 过滤掉了。改为遍历所有 frame、不做可见性过滤。
        for f in lp.frames:
            try:
                r = f.evaluate("""() => {
                    const es = [...document.querySelectorAll('*')].filter(
                        e => e.children.length === 0 && (e.textContent||'').trim() === '课件');
                    if (!es.length) return 'none';
                    try { es[0].click(); return 'js'; }
                    catch(e) { return 'err:' + String(e).slice(0,60); }
                }""")
            except Exception:
                continue
            if r != "none":
                how = "%s@%s" % (r, (f.url or "")[-30:])
                break
    lp.wait_for_timeout(8000)
    log("  [%s] 点击「课件」tab: %s" % (tag, how))
    return how


def wait_sco_frame(lp, timeout=50):
    """等待 kjcourse 课件 iframe 出现（视频慢热，v3 实测 45s 后 readyState 才到 2）。"""
    end = time.time() + timeout
    while time.time() < end:
        f = frame_of(lp, "kjcourse")
        if f is not None:
            return f
        tick_wait(lp, 1)
    return None


# 在 kjcourse 课件 iframe 内执行：静音 + 自动播放 + 点掉遮罩/确认按钮
#
# 2026-11-07 23:2x P0 修复：开始/继续类遮罩【同一 document 内只点一次】。
# diag 实测（23:21:53 起 120s）：每个 20s 节拍都 clicked:['开始学习']，而该元素
# 会触发 jquery.course.player.video.js 的 videoPlay()，其中
#   $("#video_box").empty().append(videoTag)  会重建 <video> 并清空 src。
# 证据：立即状态 src='sco1/1.mp4' / currentSrc=完整 mp4 URL / network=2(LOADING)
#       / paused=false，且 steady_requests.log 只有一次 .mp4 GET；
#       t+20s 起 src='' / currentSrc='' / network=0(EMPTY) / paused=true，
#       120s 内 t 恒为 0 —— mp4 加载被反复中断，永远起不来。
# 现在：src 已存在就绝不点；src 为空才点一次并设 window.__STEADY_STARTED__。
# 之后每个节拍只静音 + play()，不再碰 DOM。切换课件节点会加载新 document，
# 标记自然消失，新节点会重新走一次这个流程。
KJ_BEAT_JS = r"""() => {
    const out = {muted:false, played:false, clicked:[], layer:0,
                 started:false, skipped:false, note:''};
    const v = document.querySelector('video');
    if (v) {
        try { v.muted = true; v.volume = 0; out.muted = true; } catch(e) {}
        try {
            if (v.paused && !v.ended) {
                // play() 返回 Promise；readyState=0 时可能被拒绝，捕获但不 await
                // （await 会一直 pending 到视频有数据，阻塞整个保活节拍）。
                const p = v.play();
                if (p && typeof p.catch === 'function') p.catch(() => {});
                out.played = true;
            }
        } catch(e) {}
    }
    if (window.__STEADY_STARTED__) {
        out.started = true;
        out.skipped = true;                    // 本节拍不点任何遮罩
    } else {
        const hasSrc = !!(v && (v.getAttribute('src') || v.currentSrc));
        if (hasSrc) {
            // 页面已自行调 videoPlay() 设好 src，再点只会重建元素、中断加载。
            window.__STEADY_STARTED__ = true;
            out.started = true;
            out.note = 'src_present_no_click';
        } else {
            // 只点播放相关遮罩；不做 offsetParent 可见性过滤（遮罩文本常在隐藏容器里）。
            const kws = ['开始学习','继续学习','继续观看','继续播放'];
            for (const k of kws) {
                const es = [...document.querySelectorAll('*')].filter(e =>
                    e.children.length === 0 && (e.textContent||'').trim() === k);
                if (es.length) {
                    try {
                        es[0].click();
                        out.clicked.push(k);
                        window.__STEADY_STARTED__ = true;   // 只点一次，避免重建 <video>
                        out.started = true;
                        out.note = 'clicked_once';
                        break;
                    } catch(e) {}
                }
            }
        }
    }
    // 弹窗确认按钮：同一 DOM 元素只点一次（clickAuth 每 30 分钟是新元素，仍会被点），
    // 避免常驻按钮每 20s 被点一次而误触发 videoPlay()。
    if (!window.__STEADY_LAYER_SET__) window.__STEADY_LAYER_SET__ = new WeakSet();
    document.querySelectorAll('.layui-layer-btn0, #msgbt').forEach(e => {
        if (e.offsetParent !== null && !window.__STEADY_LAYER_SET__.has(e)) {
            try { e.click(); out.layer++; window.__STEADY_LAYER_SET__.add(e); } catch(_) {}
        }
    });
    return out;
}"""

# 在学习页顶层执行：点掉 studyTime.js 每 30 分钟弹出的 clickAuth 确认框
# 同一 DOM 元素只点一次（新弹窗是新元素，仍会被点），避免常驻按钮每 20s 被误点。
TOP_BEAT_JS = r"""() => {
    let n = 0;
    if (!window.__STEADY_TOP_LAYER_SET__) window.__STEADY_TOP_LAYER_SET__ = new WeakSet();
    document.querySelectorAll('.layui-layer-btn0').forEach(e => {
        if (!window.__STEADY_TOP_LAYER_SET__.has(e)) {
            try { e.click(); n++; window.__STEADY_TOP_LAYER_SET__.add(e); } catch(_) {}
        }
    });
    return {layer: n};
}"""

# 在 courseware_index.action（左侧课件菜单）内执行：点【当前节点之后】的
# 第一个未完成节点。
# 旧实现总找「第一个未完成节点」并用 next||pts[0] 兜底，有两个致命问题：
#   1) completestate 只在点击后一个节点时才回填前一个节点
#      (courseware_index.js:387-408)，于是刚播完的节点仍未标记完成，
#      旧逻辑反复点同一个节点 -> 同一段视频反复从头播（日志里
#      s_point_6580756626374087 被点 3 次、zx2678361 播了 3 遍）；
#   2) 全部节点完成时 fallback 到 pts[0]，又从第一个节点重播。
# 现在按 .s_point.s_pointerct 定位当前节点，只往后找；找不到就返回
# allDone 且【不点任何节点】。
NEXT_NODE_JS = r"""() => {
    const pts = [...document.querySelectorAll('.s_point')];
    if (!pts.length) return {ok:false, reason:'no_points', n:0, allDone:false};
    const cur = pts.findIndex(p => p.classList.contains('s_pointerct'));
    let target = -1;
    for (let i = Math.max(cur + 1, 0); i < pts.length; i++) {
        if ((pts[i].getAttribute('completestate')||'0') !== '1') {
            target = i; break;
        }
    }
    if (target < 0) {
        // 后面已无未完成节点：绝不点 pts[0]，避免整门课从头重播
        return {ok:true, clicked:false, allDone:true, n:pts.length, cur:cur};
    }
    try {
        pts[target].click();
        return {ok:true, clicked:true, id: pts[target].id || '',
                index:target, cur:cur, n:pts.length, allDone:false};
    } catch(e) {
        return {ok:false, clicked:false, allDone:false,
                reason: String(e).slice(0,80)};
    }
}"""

VIDEO_STATE_JS = r"""() => {
    const vs = [...document.querySelectorAll('video')];
    if (!vs.length) return {noVideo:true, videoCount:0};
    const v = vs[0];
    const r = n => Math.round(n * 10) / 10;
    // kj_index.html 里的 <video> 没有 src，src 由 jquery.course.player.video.js
    // 的 videoPlay() 动态设置。把这些字段打出来才能区分「没触发 videoPlay」
    // 与「mp4 加载慢」两种情况。
    let pinfo = null;
    try {
        if (typeof player !== 'undefined' && player) {
            pinfo = {
                src: (typeof player.getSrc === 'function') ? String(player.getSrc()) : null,
                clips: (typeof switchPlayList !== 'undefined' && switchPlayList)
                       ? switchPlayList.length : null,
                firstClip: (typeof switchPlayList !== 'undefined' && switchPlayList
                            && switchPlayList[0]) ? String(switchPlayList[0].url) : null
            };
        }
    } catch(e) { pinfo = {err: String(e).slice(0, 70)}; }
    return {
        videoCount: vs.length,
        t: r(v.currentTime || 0),
        dur: isFinite(v.duration) ? r(v.duration) : 0,
        ready: v.readyState,
        network: v.networkState,
        paused: v.paused,
        ended: v.ended,
        rate: v.playbackRate,
        src: (v.getAttribute('src') || '').slice(0, 90),
        currentSrc: (v.currentSrc || '').slice(0, 90),
        err: v.error ? v.error.code : null,
        player: pinfo
    };
}"""


def beat(lp, tag, verbose=False):
    """一次保活：顶层确认框 + 课件 iframe 静音/播放/继续观看。全程不改播放速率、不拖进度。"""
    r_top, r_kj = {}, {}
    try:
        r_top = lp.evaluate(TOP_BEAT_JS)
    except Exception:
        pass
    kj = frame_of(lp, "kjcourse")
    if kj is not None:
        try:
            r_kj = kj.evaluate(KJ_BEAT_JS)
        except Exception:
            pass
    if verbose:
        log("  [%s] beat top=%s kj=%s" % (tag, r_top, r_kj))
    return r_top, r_kj


def video_state(lp):
    kj = frame_of(lp, "kjcourse")
    if kj is None:
        return {"noVideo": True, "reason": "no_kj_frame"}
    try:
        return kj.evaluate(VIDEO_STATE_JS)
    except Exception as e:
        return {"noVideo": True, "reason": str(e)[:80]}


def click_next_node(lp, tag):
    """遍历所有 frame 找课件菜单节点（.s_point 所在 frame 不固定，不按 URL 猜）。"""
    for f in lp.frames:
        try:
            n = f.evaluate("() => document.querySelectorAll('.s_point').length")
        except Exception:
            continue
        if not n:
            continue
        try:
            r = f.evaluate(NEXT_NODE_JS)
            log("  [%s] 自动续播下一节点(frame=%s): %s" % (tag, (f.url or "")[-45:], r))
            return r
        except Exception as e:
            log("  [%s] 续播异常: %s" % (tag, str(e)[:110]))
            return {"ok": False, "reason": str(e)[:80]}
    log("  [%s] 未找到 .s_point 菜单节点，尝试平台自带 playFirstNode()" % tag)
    for f in lp.frames:
        try:
            ok = f.evaluate("""() => {
                if (typeof window.playFirstNode === 'function') {
                    window.playFirstNode(); return true;
                }
                return false;
            }""")
            if ok:
                log("  [%s] 已调用 playFirstNode()" % tag)
                return {"ok": True, "reason": "playFirstNode"}
        except Exception:
            pass
    return {"ok": False, "reason": "no_menu_frame"}


def diag_dump(lp, tag):
    log("  [%s] --- DIAG frames ---" % tag)
    for i, f in enumerate(lp.frames):
        log("    FRAME%d %s" % (i, (f.url or "")[:150]))
    log("  [%s] 视频状态(立即): %s" % (tag, video_state(lp)))
    # video_out.txt 实测视频慢热：45s 仍 readyState=0，60s 才 readyState=2。
    # 上一版 diag 只看 40 秒，不足以判断视频是否会开始加载，故延长到 120 秒。
    span = int(os.environ.get("CMATC_DIAG_SEC", "120"))
    step = 20
    n = max(1, span // step)
    log("  [%s] 等待 %d 秒观察自然加载与上报（不写入任何数据）..." % (tag, n * step))
    for i in range(n):
        tick_wait(lp, step)
        try:
            beat(lp, tag, verbose=True)
        except Exception as e:
            log("    beat err: %s" % str(e)[:100])
        log("    t+%03ds 视频状态: %s" % ((i + 1) * step, video_state(lp)))
    log("  [%s] --- DIAG END ---" % tag)
    # 结束判定：一眼看出「src 被清空」还是「真的起播了」，减少来回贴日志。
    try:
        fin = video_state(lp)
        if not fin.get("src") and not fin.get("currentSrc"):
            log("  [%s] WARN: 结束时 <video> src 仍为空"
                "（network=%s ready=%s t=%s），mp4 加载未建立；"
                "请把 steady_requests.log 里 .mp4 GET 次数一并贴回。"
                % (tag, fin.get("network"), fin.get("ready"), fin.get("t")))
        elif (fin.get("ready") or 0) >= 2 and (fin.get("t") or 0) > 0:
            log("  [%s] OK: 视频已起播 t=%s dur=%s ready=%s network=%s"
                % (tag, fin.get("t"), fin.get("dur"),
                   fin.get("ready"), fin.get("network")))
        else:
            log("  [%s] 视频状态(结束): %s" % (tag, fin))
    except Exception as e:
        log("  [%s] 结束状态读取异常: %s" % (tag, str(e)[:100]))


# ---------------------------------------------------------------------------
# 请求 / 响应记录：同时挂主站页 pg 与学习页 lp（修复 v2 只挂 pg 的缺陷）
# ---------------------------------------------------------------------------
KEY = re.compile(
    r"learn|time|record|study|progress|commit|scorm|saveCourses|saveUserToSpace|complete",
    re.I)


def attach_recorder(page, label):
    def on_request(req):
        try:
            u = req.url
            # mp4 是 GET、学习时长兜底上报（Chrome>=78 走 new Image()）也是 GET，
            # 只记 POST/PUT 会完全看不到「视频是否真的在下载」。
            is_media_or_get_save = (
                req.method == "GET"
                and (".mp4" in u or "learningTime_saveLearningTime" in u))
            if (req.method in ("POST", "PUT") and KEY.search(u)) or is_media_or_get_save:
                pd = ""
                try:
                    pd = (req.post_data or "")[:400]
                except Exception:
                    pass
                with open(REQ_LOG, "a", encoding="utf-8") as f:
                    f.write("%s [%s] REQ %s %s | %s\n" % (
                        datetime.datetime.now().strftime("%H:%M:%S"), label,
                        req.method, u[:240], pd.replace("\n", " ")))
        except Exception:
            pass

    def on_response(resp):
        try:
            # GET 的 mp4 响应体是二进制，绝不 resp.text()
            if resp.request.method == "GET":
                return
            if resp.request.method in ("POST", "PUT") and KEY.search(resp.url):
                body = ""
                try:
                    body = resp.text()[:200]
                except Exception:
                    pass
                with open(REQ_LOG, "a", encoding="utf-8") as f:
                    f.write("%s [%s] RES %s %s | %s\n" % (
                        datetime.datetime.now().strftime("%H:%M:%S"), label,
                        resp.status, resp.url[:200], body.replace("\n", " ")))
        except Exception:
            pass

    page.on("request", on_request)
    page.on("response", on_response)


# ---------------------------------------------------------------------------
# 单门课：打开 -> 点课件 -> 真实播放 -> 自动续播/确认 -> 到时或完成 -> 关闭
# ---------------------------------------------------------------------------
def study_one_course(pg, ctx, course, tag, old_lp):
    """学一门课，返回状态：
       done     本门已达 100%（平台进度或课件节点全完成）
       target   总学时已达标
       stop     收到停止信号
       continue 单次会话到时但本门未学完 —— 主循环必须重新打开【同一门】继续
       error    异常/未能打开学习页
    """
    clabel = course_label(course)
    cid = (course.get("cid") or "").rstrip("_")
    if already_finished(pg, cid, tag):
        return "done"
    lp, how = open_learnspace(pg, ctx, course, tag, old_lp)
    if lp is None:
        return "error"
    try:
        attach_recorder(lp, "LP")       # 关键：学习页也挂记录器
        log("  [%s] 课程: %s" % (tag, clabel))
        log("  [%s] 学习页(%s): %s" % (tag, how, lp.url[:130]))

        click_courseware_tab(lp, tag)
        kj = wait_sco_frame(lp, 50)
        if kj is None:
            log("  [%s] 未等到 kjcourse 课件 iframe（可能是 PDF/网页型课件或加载较慢），继续保活" % tag)
        else:
            log("  [%s] kjcourse iframe 已加载: %s" % (tag, kj.url[:110]))
        # 【断点续学】平台 playFirstNode() 总从第一个节点开始播，
        # 这里主动跳到第一个未完成节点，跳过已学完的节点。
        resume_to_unfinished_node(lp, tag)
        beat(lp, tag, verbose=True)
        # 重开课程时平台不读自己保存的 videoTime，这里恢复到那个真实秒数。
        apply_platform_resume(lp, tag)

        if DIAG:
            np = node_progress(lp)
            log("  [%s] DIAG 课程=%s cid=%s 节点进度=%s" % (tag, clabel, cid or "-", np))
            diag_dump(lp, tag)
            return "diag"

        deadline = time.time() + DWELL_MIN * 60
        last_t, t_stall = -1, 0
        last_next_id, same_next = None, 0   # 防止连续重播同一节点
        no_video_beats, no_video_pct = 0, None   # 课件 iframe 丢失自愈
        tick = 0
        result = "continue"
        log("  [%s] 开始学习【%s】；本门 100%% 才换课，单次会话上限 %.0f 分钟"
            % (tag, clabel, DWELL_MIN))
        log("  [%s] 进度口径：平台=我的课程页该课百分比；节点=课件菜单完成率；"
            "每 %ss 保活、每 %ss 复核" % (tag, BEAT_SEC, CREDIT_EVERY))
        while time.time() < deadline:
            if stopped():
                log("  [%s] 收到停止信号" % tag)
                return "stop"
            try:
                beat(lp, tag)
            except Exception as e:
                log("  [%s] beat 异常: %s" % (tag, str(e)[:110]))
            tick_wait(lp, BEAT_SEC)
            tick += 1

            # 每 3 个节拍（默认 60s）：显示学习百分比 + 处理节点续播
            if tick % 3 == 0:
                st = video_state(lp)
                np = node_progress(lp)
                # 有的课件模板不回写 completestate，节点完成率会一直是 0/4，
                # 与平台上实际在涨的百分比对不上。这里按「当前节点序号 +
                # 本节点视频播放比例」给出一个单调递增的播放估算，只用于显示，
                # 不写入平台、不参与完成判定。
                ni = node_info(lp) or {}
                total, cur_idx = ni.get("total") or 0, ni.get("curIdx", -1)
                dur, tnow = st.get("dur") or 0, st.get("t") or 0
                est = "-"
                if total and cur_idx >= 0 and dur > 0:
                    est = "%.1f" % ((cur_idx + min(1.0, tnow / dur)) * 100.0 / total)
                log("  [%s] 进度 | %s | 课件节点 %s/%s (%s%%) | 播放约 %s%% "
                    "| 视频 %.1f/%.1f s ready=%s"
                    % (tag, clabel,
                       np.get("done") if np else "-",
                       np.get("total") if np else "-",
                       np.get("pct") if np else "-",
                       est,
                       st.get("t", 0) or 0, st.get("dur", 0) or 0, st.get("ready")))
                # 【课件链丢失自愈】点开新节点后 kjcourse iframe 可能整个消失
                # （2026-11-08 20:40:53 点第 4 节点后 no_kj_frame，之后 7 分钟
                #  恒 0.0/0.0s）。旧版对 noVideo 没有任何分支，会一直空转到
                #  单次会话上限。这里区分两种情况：
                #   * 非视频型节点（PDF/网页/测验）：平台按真实在线时长
                #    (learningTime_saveLearningTime.action) 计进度，进度还在涨
                #    -> 保持在线，不干预；
                #   * 课件链真的断了：进度也不涨 -> 结束本轮，主循环会重新
                #    打开【同一门】课，触发平台重新初始化课件 iframe 链。
                if st.get("noVideo"):
                    no_video_beats += 1
                    if no_video_beats in (1, 3, 6, 9):
                        log("  [%s] 课件 iframe 已丢失 %s 分钟（%s）；"
                            "在线时长仍在上报，观察平台进度"
                            % (tag, no_video_beats, st.get("reason", "-")))
                    if no_video_beats >= 3 and no_video_beats % 3 == 0:
                        try:
                            nav(pg, MY_COURSE_URL, wait=2500)
                            pct_now = read_progress(pg, cid)
                        except Exception as e:
                            log("  [%s] 无视频复核异常: %s" % (tag, str(e)[:90]))
                            pct_now = None
                        if pct_now is not None and pct_now >= 99.9:
                            log("  [%s] 平台进度已达 100%%，本门学完" % tag)
                            result = "done"
                            break
                        if pct_now is not None and no_video_pct is not None \
                                and pct_now <= no_video_pct + 0.05:
                            log("  [%s] 无视频且平台进度 %s%% 连续两次不增长，"
                                "结束本轮并重新打开本门课重建课件链"
                                % (tag, pct_now))
                            result = "continue"
                            break
                        if pct_now is not None:
                            log("  [%s] 无视频但平台进度仍在涨 %s%% -> %s%%，"
                                "保持在线（按在线时长计进度）"
                                % (tag,
                                   no_video_pct if no_video_pct is not None else "-",
                                   pct_now))
                            no_video_pct = pct_now
                        no_video_beats = 1
                else:
                    no_video_beats = 0
                    no_video_pct = None
                # 【秒级断点续学】平台对视频课件不写 saveLearningItem.json，
                # 这里补写真实播放秒数；每 5 分钟打一条日志，失败时立即打。
                save_resume_position(lp, tag, cid, st,
                                     verbose=(tick <= 3 or tick % 15 == 0))
                # 完成判据之一：课件菜单节点全部完成 —— 但先回主站复核平台进度，
                # 避免节点状态与平台 100% 不同步时误判「学完」而跳过本门。
                if np and np.get("allDone") and np.get("total"):
                    log("  [%s] 课件节点已全部完成（%s/%s），回主站复核平台进度..."
                        % (tag, np["done"], np["total"]))
                    ok, pct_now = confirm_done(pg, cid, tag)
                    if ok:
                        log("  [%s] 复核通过（平台进度=%s），本门学完"
                            % (tag, pct_now if pct_now is not None else "未读到"))
                        result = "done"
                        break
                    log("  [%s] 平台进度仅 %s%%，节点状态领先于平台，继续学本门"
                        % (tag, pct_now))
                # dur=0 表示时长未知（视频还在慢热加载），绝不能判定为"快播完"
                if st.get("ended") or ((st.get("dur") or 0) > 0
                                       and st.get("dur") - st.get("t", 0) < 3
                                       and st.get("t", 0) > 5):
                    r = click_next_node(lp, tag)
                    if r.get("allDone") or not r.get("clicked", True):
                        log("  [%s] 已无后续未完成节点，回主站复核平台进度..." % tag)
                        ok, pct_now = confirm_done(pg, cid, tag)
                        if ok:
                            log("  [%s] 复核通过（平台进度=%s），本门学完"
                                % (tag, pct_now if pct_now is not None else "未读到"))
                            result = "done"
                            break
                        log("  [%s] 平台进度仅 %s%%，继续学本门（不重播已完成节点）"
                            % (tag, pct_now))
                    else:
                        # 兜底：平台完成状态刷新滞后时，可能连续点到同一节点。
                        # 同一 id 连点 2 次就复核，避免整段视频被反复重播。
                        new_id = r.get("id") or ""
                        if new_id and new_id == last_next_id:
                            same_next += 1
                            log("  [%s] 连续 %s 次点到同一节点 %s，等待平台刷新完成状态"
                                % (tag, same_next, new_id))
                            if same_next >= 2:
                                log("  [%s] 疑似重复播放，回主站复核平台进度" % tag)
                                ok, pct_now = confirm_done(pg, cid, tag)
                                if ok:
                                    result = "done"
                                    break
                                same_next = 0
                        else:
                            same_next = 0
                        last_next_id = new_id
                    t_stall = 0
                elif not st.get("noVideo"):
                    # 视频慢热：readyState=0 可持续 60~90 秒，这段时间不算「停滞」。
                    if (st.get("ready") or 0) < 2:
                        t_stall = 0
                        if tick % 9 == 0:
                            log("  [%s] 视频慢热加载 readyState=%s src=%s，耐心等待"
                                % (tag, st.get("ready"), st.get("src")))
                    elif st.get("t") == last_t:
                        t_stall += 1
                        if t_stall >= 5:
                            log("  [%s] 视频 %s 个节拍未推进（state=%s），尝试续播下一节点"
                                % (tag, t_stall, st))
                            click_next_node(lp, tag)
                            t_stall = 0
                    else:
                        t_stall = 0
                    last_t = st.get("t")

            # 每 CREDIT_EVERY 秒：回主站读学时 + 按 cid 精确读【本门】进度
            if tick * BEAT_SEC >= CREDIT_EVERY and tick % max(1, CREDIT_EVERY // BEAT_SEC) == 0:
                try:
                    credit = read_credit(pg)
                    pct = read_progress(pg, cid)
                    np = node_progress(lp)
                    cached = course.get("pct")
                    log("  [%s] 复核 | %s | 平台进度=%s%% | 节点进度=%s%% (%s/%s)"
                        " | 选课时=%s%% | 学时=%s/%s | 视频=%s"
                        % (tag, clabel,
                           ("%.1f" % pct) if pct is not None else "未读到",
                           ("%.1f" % np["pct"]) if np else "-",
                           np.get("done") if np else "-",
                           np.get("total") if np else "-",
                           cached if cached is not None else "-",
                           credit, TARGET, video_state(lp)))
                    # 进度日志改用实时平台进度：旧版一直显示选课时的缓存值
                    # （[61.1%]），复核已到 71.6% 却看不出来，像「进度错」。
                    if pct is not None:
                        course["pct"] = pct
                        clabel = course_label(course)
                    if credit is not None and credit >= TARGET:
                        log("  [%s] 总学时已达标，结束" % tag)
                        return "target"
                    if pct is not None and pct >= 99.9:
                        log("  [%s] 平台进度 100%%，本门学完" % tag)
                        result = "done"
                        break
                    # 【关键修复】这里不再因为「进度未增长」而切课。
                    # 旧版 stalled>=6 用的是整页最小进度（恒为 0），
                    # 每门只学 30 分钟就被换掉，正是用户看到的
                    # 「6 门课每门都没到 100%」的根因。
                except Exception as e:
                    log("  [%s] 复核异常: %s" % (tag, str(e)[:130]))
        else:
            log("  [%s] 单次会话 %.0f 分钟到时，本门尚未确认 100%%；"
                "主循环会重新打开【同一门】继续，不换课" % (tag, DWELL_MIN))
            result = "continue"
        return result
    except Exception as e:
        log("  [%s] 学习过程异常: %s" % (tag, str(e)[:200]))
        log(traceback.format_exc()[-500:])
        return "error"
    finally:
        # 关键：先关闭学习页，再开下一门，避免平台"同时学习不同课程被终止"
        with contextlib.suppress(BaseException):
            lp.close()
        pg.wait_for_timeout(2000)


# ---------------------------------------------------------------------------
# 关闭阶段：吞掉所有异常（含 Ctrl+C 二次异常）
# ---------------------------------------------------------------------------
def shutdown(ctx, browser, pw):
    for fn in (lambda: ctx.close(), lambda: browser.close(), lambda: pw.stop()):
        with contextlib.suppress(BaseException):
            fn()


def main():
    if not PWD:
        log("ERROR: 请设置环境变量 CMATC_PWD（或 run_steady.bat 密码）")
        sys.exit(1)
    if os.path.exists(STOP_FLAG):
        os.remove(STOP_FLAG)
    log("=" * 72)
    log("稳态挂机启动 | 目标 %s 学时 | 单次会话上限 %.0f 分钟 | 节拍 %ss | 复核间隔 %ss | DIAG=%s"
        % (TARGET, DWELL_MIN, BEAT_SEC, CREDIT_EVERY, DIAG))
    log("规则：一门课 100% 才换下一门；未完成则下一轮重新打开同一门继续。")
    log("原则：真实在线、真实播放、不伪造计时/完成状态；严格单窗口串行。")
    log("创建 stop_steady.flag 可优雅停止。单点登录会互踢，启动前请停掉其他学习脚本。")

    pw = sync_playwright().start()
    browser = pw.chromium.launch(executable_path=EDGE, headless=True, args=ARGS)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              ignore_https_errors=True)
    pg = ctx.new_page()
    pg.set_default_timeout(20000)
    attach_recorder(pg, "PG")

    seen = load_seen()     # 仅作历史记录，不再参与课程筛选
    done_count = 0
    done_urls = set()      # 本次运行已确认 100% 的课程，下一轮不再选回
    sticky = None          # 未学完的课程 URL：下一轮必须重新打开同一门
    sticky_rounds = 0      # 同一门连续重开次数，用于死循环保护
    sticky_fails = 0       # 同一门连续异常次数
    skip = set()           # 暂时跳过的课程（异常/多轮无进展）
    rounds = 0
    fail_reads = 0
    try:
        log("登录中...")
        try:
            login(pg, verbose=False)
        except Exception as e:
            log("登录失败：%s" % str(e)[:300])
            log("已停止，未执行任何选课/学习操作。确认已停掉其他会话、密码正确后重启。")
            return
        log("登录完成: %s" % pg.url)

        while not stopped():
            rounds += 1
            log("-" * 72)
            log("第 %d 轮：检查学时" % rounds)
            credit = read_credit(pg)
            if credit is None:
                fail_reads += 1
                log("  学时读取失败（%d/3）" % fail_reads)
                if fail_reads >= 3:
                    log("  连续 3 次读取失败，疑似登录态失效，停止脚本。")
                    break
                pg.wait_for_timeout(5000)
                continue
            fail_reads = 0
            log("  当前本年度完成学时: %s / %s" % (credit, TARGET))
            if credit >= TARGET:
                log("已达标（%s >= %s），退出。" % (credit, TARGET))
                break

            pool = build_course_pool(pg, NEED)
            # 【空池防御】平台偶发把「我的课程」和「课程中心」同时渲染成空
            # 列表（2026-11-08 20:56 实测：46 学时账号一轮采集到 0 门）。
            # 直接退出会误判「没课可学」，这里重新导航并重试 2 次。
            for retry in range(2):
                if pool:
                    break
                log("  课程池为空（第 %d 次），等待平台列表渲染后重试..."
                    % (retry + 1))
                try:
                    nav(pg, MY_COURSE_URL, wait=8000)
                except Exception as e:
                    log("  重试导航异常: %s" % str(e)[:100])
                pg.wait_for_timeout(5000)
                pool = build_course_pool(pg, NEED)
            if not pool:
                log("  课程池连续 3 次为空，请人工在浏览器确认平台课程列表后重启；"
                    "脚本退出")
                break

            # 只把「平台进度 100%」当作已学完；pct 缺失一律视为未完成。
            # 旧版用 seen（打开过就算学过）过滤 + 进度恒 0 的 stall 判定，
            # 每门只学 30 分钟就被换掉，且课程池只有 6 门来回打转。
            unfinished = [c for c in pool
                          if (c.get("pct") is None or c["pct"] < 99.9)
                          and c["url"] not in skip
                          and c["url"] not in done_urls]
            if not unfinished:
                log("  课程池内课程已全部 100%% / 已完成 / 被跳过，清空记录重新核对")
                skip.clear()
                done_urls.clear()
                unfinished = [c for c in pool
                              if c.get("pct") is None or c["pct"] < 99.9]
                if not unfinished:
                    log("  所有课程均已 100%%，但学时仍为 %s/%s（口径疑问），退出。"
                        % (credit, TARGET))
                    break

            # sticky 优先：上一门没学完，就继续同一门，绝不换课。
            cur = None
            if sticky:
                for c in unfinished:
                    if c["url"] == sticky:
                        cur = c
                        log("  继续上一门未学完的课程: %s (第 %d 次重开)"
                            % (course_label(c), sticky_rounds + 1))
                        break
                if cur is None:
                    log("  sticky 课程已达 100%%，解除 sticky，换下一门")
                    sticky = None
                    sticky_rounds = 0
                    sticky_fails = 0
            if cur is None:
                cur = unfinished[0]      # 池已按平台进度降序，优先最接近 100% 的
                sticky_rounds = 0
                sticky_fails = 0

            log("  本轮只学 1 门: %s  cid=%s  (未完成池 %d 门，本次已完成 %d 门)"
                % (course_label(cur), cur.get("cid") or "-",
                   len(unfinished), done_count))
            log("    %s -> %s" % (cur["fn"], cur["url"][:95]))

            try:
                res = study_one_course(pg, ctx, cur, "course1", None)
            except Exception as e:
                log("  本门异常: %s" % str(e)[:200])
                res = "error"

            if res == "diag":
                log("  诊断模式只跑一门，结束。")
                return
            if res == "target":
                log("  总学时达标，退出。")
                break
            if res == "stop":
                break
            if res == "done":
                mark_seen(cur["url"])
                done_urls.add(cur["url"])
                done_count += 1
                sticky = None
                sticky_rounds = 0
                sticky_fails = 0
                log("  本门已学完，下一轮按平台进度核对后换下一门（累计完成 %d 门）"
                    % done_count)
            elif res == "error":
                sticky_fails += 1
                if sticky_fails >= 3:
                    log("  本门连续 3 次异常，暂时跳过换下一门")
                    skip.add(cur["url"])
                    sticky = None
                    sticky_rounds = 0
                    sticky_fails = 0
                else:
                    sticky = cur["url"]
                    sticky_rounds += 1
                    log("  本门异常，下一轮重试同一门（%d/3）" % sticky_fails)
            else:  # continue：单次会话到时但本门未 100%
                sticky = cur["url"]
                sticky_rounds += 1
                # 死循环保护：同一门重开过多轮仍无进展，暂时跳过并明确告警。
                if sticky_rounds >= 8:
                    log("  [warn] 同一门连续重开 %d 次仍未被平台判为 100%%，"
                        "暂时加入 skip 换下一门；请核对日志里的平台进度/节点进度"
                        % sticky_rounds)
                    skip.add(cur["url"])
                    sticky = None
                    sticky_rounds = 0
                    sticky_fails = 0
                else:
                    log("  本门未学完，下一轮重新打开【同一门】继续，不换课"
                        "（连续第 %d 轮）" % sticky_rounds)

            if ROUNDS and rounds >= ROUNDS:
                log("达到试运行轮数上限 %d，结束。" % ROUNDS)
                break
    except KeyboardInterrupt:
        log("收到 Ctrl+C，正在关闭...")
    except Exception as e:
        log("主循环异常: %s" % str(e)[:250])
        log(traceback.format_exc()[-600:])
    finally:
        shutdown(ctx, browser, pw)
        log("脚本结束。")


if __name__ == "__main__":
    main()
