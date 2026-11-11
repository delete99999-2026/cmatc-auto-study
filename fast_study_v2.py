# -*- coding: utf-8 -*-
"""
中国气象局培训学院 - 加速学习脚本 v2（独立新文件，不改动 fast_study.py / auto_study.py）

=============================================================================
v1 为什么失败（依据 fast_run.log / fast_requests.log / 站点 JS 静态分析）
=============================================================================
1) api:False —— 学时卡在 33.0 不动的根因
   v1 用 lp.goto(课程中心的 signLearn.action URL) 裸跳进学习页，跳过了平台
   enterCourse()/enterCourseTimeLimit() 的前置链路：
       faceRecognition.json -> saveUserToSpaceRecord.json(记录在学课程)
       -> saveStudentElectiveNoProject.json -> window.open(url,'_learnspace')
   结果 courseware_index / content_webCourseware iframe 被会话拦截页顶掉
   （js_probe/learn_index.html 与 courseware_index.html 即"长时间未操作或操作
   异常，请重新登录"），父窗口没有 window.API。
   而 APIWrapper.js 的 doLMSCommit() 在 getAPIHandle()==null 时直接 return，
   不发送任何 HTTP 请求；v1 注入的 doLMSSetValue/doLMSCommit 全是空操作。
   fast_requests.log 的 18 行也印证：只有 query 类请求，没有任何保存/提交。

2) 反复补选、可学习课程永远 1 门
   chooseCourseTimeLimit() 内部有 layer.confirm('确定要进行选课吗？')，v1 用
   pg.evaluate 直接调它只弹框、无人点"确定"，POST /u/study/saveCourses.json
   从未发出，所以每轮补选同样 8 个 id、列表不变。

3) 学时首轮失败 / 误读 0.0
   nav() 固定 wait 后就读，异步渲染的"本年度完成学时"节点尚未出现；0.0 是
   数据未加载时的占位值。

4) Ctrl+C 时 Playwright cleanup 抛 KeyboardInterrupt 二次异常。

=============================================================================
v2 的修法
=============================================================================
* 入口：不再裸跳。调用页面自身的 enterCourse(...)/enterCourseTimeLimit(...)，
  用 expect_popup 捕获 window.open(...,'_learnspace') 弹出的真实学习页，
  让平台完成签到 + saveUserToSpaceRecord，父窗口才会提供 window.API。
* 选课：绕过 layer.confirm，直接在页面上下文 fetch
  POST /u/study/saveCourses.json (opt=3, entity.itemIds=<openCourseId>)，
  选完刷新后再取课程池。
* 注入前强制探测 window.API；api:False 时自动重开一次入口，仍失败则明确
  跳过并打日志，绝不"假装成功"。
* 加速仍沿用旧油猴脚本思路：放大 player.player_time、主动写
  cmi.core.session_time / lesson_status=completed，并【显式 doLMSCommit()】
  —— 只有 commit 才会触发平台真正的 HTTP 持久化（SCOFunctions 每 60s 只
  SetValue 不 Commit，v2 每 TICK 秒主动提交一次，这就是提速点）。
* 严格单窗口轮转：任一时刻只有一个 _learnspace 学习页，切换前 doQuit +
  close，避免平台"同时学习不同课程会终止"的检测。
* 记录 POST 的 url + post_data + 响应状态到 fast_v2_requests.log，
  便于确认真实上报接口与参数。
* 优雅停止：stop_fast_v2.flag；KeyboardInterrupt 单独捕获，关闭阶段用
  suppress(BaseException) 杜绝二次异常。
* CMATC_DIAG=1 诊断模式：只跑 1 门课，打印 API/frame/请求详情后退出，
  用于先确认 api:True 再全速运行。

※ 平台为单点登录，本脚本登录会踢掉其他会话：请先停掉正在运行的
  auto_study.py / fast_study.py 再启动（用户未停之前本脚本不会被启动）。
※ 本脚本不修改任何现有文件，不结束任何进程。

用法：
  run_fast_v2.bat 你的密码
  run_fast_v2.bat 你的密码 diag        (诊断模式)
或：
  set "CMATC_PWD=你的密码"        (CMD；切勿写成 set CMATC_PWD='密码')
  python -u fast_study_v2.py

可调环境变量：
  CMATC_TARGET      目标学时，默认 80
  CMATC_CHUNK       每次上报的课程时间秒数，默认 120（对齐旧脚本 learntime=120）
  CMATC_TICK        主动上报/提交间隔秒，默认 35（对齐旧脚本 35000ms）
  CMATC_DWELL       每门课停留秒数，默认 12（对齐旧脚本 12000ms）
  CMATC_FORCE       1=写 lesson_status=completed（默认），0=仅放大时长
  CMATC_MAX_COURSES 每轮最多轮转课程数，默认 10
  CMATC_NEED        期望课程池大小，默认 6
  CMATC_ROUNDS      轮数上限，0=不限
  CMATC_DIAG        1=诊断模式（只跑一门并打印详情）
"""
import os, re, sys, time, json, datetime, traceback, contextlib
from playwright.sync_api import sync_playwright

from common import EDGE, HOST, OUT, USER, PWD, ARGS, login

TARGET = float(os.environ.get("CMATC_TARGET", "80"))
CHUNK = int(os.environ.get("CMATC_CHUNK", "120"))
TICK = int(os.environ.get("CMATC_TICK", "35"))
DWELL = int(os.environ.get("CMATC_DWELL", "12"))
FORCE = os.environ.get("CMATC_FORCE", "1") == "1"
MAX_COURSES = int(os.environ.get("CMATC_MAX_COURSES", "10"))
NEED = int(os.environ.get("CMATC_NEED", "6"))
ROUNDS = int(os.environ.get("CMATC_ROUNDS", "0"))
DIAG = os.environ.get("CMATC_DIAG", "0") == "1"

STOP_FLAG = os.path.join(OUT, "stop_fast_v2.flag")
LOG = os.path.join(OUT, "fast_v2_run.log")
REQ_LOG = os.path.join(OUT, "fast_v2_requests.log")
SEEN = os.path.join(OUT, "fast_v2_seen.txt")

MY_COURSE_URL = HOST + "/u/student/study/myCourse.action"
MARKET_URL = HOST + "/cms/courseMarketNew.htm"


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


# ---------------------------------------------------------------------------
# 学时读取：显式等待节点 + 多次取样，避免首轮失败与 0.0 误读
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
    for _ in range(3):
        try:
            r = pg.evaluate(CREDIT_JS)
            if r and r.get("v") is not None:
                samples.append(float(r["v"]))
        except Exception:
            pass
        pg.wait_for_timeout(1200)
    if not samples:
        log("  学时读取失败（3 次均未取到，URL=%s）" % pg.url[:110])
        return None
    # 学时单调不减；0.0 多为占位值，取最大有效值最稳妥
    val = max(samples)
    if len(set(samples)) > 1:
        log("  学时取样: %s -> 采用 %s" % (samples, val))
    return val


# ---------------------------------------------------------------------------
# 课程池：我的课程(继续学习) + 课程中心(开始学习)，不足则 HTTP 直接选课
# ---------------------------------------------------------------------------
PARSE_ARGS_JS = r"""(fnName) => {
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
        if (args.length) {
            out.push({fn: fnName, args: args, text: (a.textContent||'').trim().slice(0,20), url: args[0]});
        }
    });
    return out;
}"""


def collect_from_mycourse(pg):
    nav(pg, MY_COURSE_URL, wait=3500)
    return pg.evaluate(PARSE_ARGS_JS, "enterCourse")


def collect_from_market(pg):
    nav(pg, MARKET_URL, wait=4000)
    return pg.evaluate(PARSE_ARGS_JS, "enterCourseTimeLimit")


def collect_choose_ids(pg, limit):
    """课程中心里'立即选课'的 openCourseId（chooseCourseTimeLimit 首参）"""
    return pg.evaluate("""(lim) => {
        const out = [];
        document.querySelectorAll('a[onclick*="chooseCourseTimeLimit"]').forEach(a => {
            const m = (a.getAttribute('onclick')||'').match(/chooseCourseTimeLimit\\(\\s*'([^']+)'/);
            if (m) out.push(m[1]);
        });
        return out.slice(0, lim);
    }""", limit)


def choose_by_http(pg, ids):
    """绕过 layer.confirm，直接调平台选课接口（同源 fetch，自动带 cookie）"""
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
    seen = set(c["url"] for c in pool)
    for c in items:
        if c.get("url") and c["url"] not in seen:
            pool.append(c)
            seen.add(c["url"])


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

    if len(pool) < need:
        try:
            ids = collect_choose_ids(pg, max(need * 2, 10))
            log("  课程池不足，HTTP 直接选课 %d 门（绕过确认框）..." % len(ids))
            res = choose_by_http(pg, ids)
            ok = sum(1 for r in res if r.get("status") == 200 and "success" in r.get("body", ""))
            log("  选课结果: %s" % json.dumps(res[:8], ensure_ascii=False)[:420])
            log("  其中疑似成功: %d" % ok)
            pg.wait_for_timeout(2000)
            for c in collect_from_market(pg):
                add_unique(pool, c)
            for c in collect_from_mycourse(pg):
                add_unique(pool, c)
        except Exception as e:
            log("  HTTP 选课异常: %s" % str(e)[:150])
    log("  最终课程池: %d 门" % len(pool))
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
    """返回 (学习页, 诊断字符串)。任一时刻只保留一个学习页。"""
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
        # 最后兜底（不推荐，可能缺 window.API，仅用于诊断对比）
        log("  [%s] 未捕获到 _learnspace，兜底直接打开（可能 api:False）" % tag)
        lp = ctx.new_page()
        nav(lp, course["url"], wait=8000)
        how = "fallback_goto"
    lp.set_default_timeout(20000)
    lp.wait_for_timeout(6000)
    return lp, how


# ---------------------------------------------------------------------------
# SCORM API 探测 + 课件 iframe 定位
# ---------------------------------------------------------------------------
PROBE_API_JS = r"""() => {
    let api = null, from = '';
    try { if (typeof getAPIHandle === 'function') { api = getAPIHandle(); if (api) from = 'getAPIHandle'; } } catch(e) {}
    if (!api) {
        try { if (typeof findAPI === 'function') { api = findAPI(window); if (api) from = 'findAPI(window)'; } } catch(e) {}
    }
    if (!api) {
        try {
            let w = window, i = 0;
            while (w && i < 8) {
                if (w.API) { api = w.API; from = 'parent_chain:' + i; break; }
                if (w === w.parent) break;
                w = w.parent; i++;
            }
        } catch(e) { from = 'cross_origin:' + String(e).slice(0,60); }
    }
    return {
        api: !!api, from: from,
        hasSet: typeof doLMSSetValue === 'function',
        hasCommit: typeof doLMSCommit === 'function',
        hasFinish: typeof doLMSFinish === 'function',
        hasPlayer: typeof player !== 'undefined',
        url: location.href.slice(0, 150)
    };
}"""


def sco_frame(lp):
    """优先 kjcourse iframe；否则找含 course_player / SCOFunctions 的 frame"""
    frames = list(lp.frames)
    for f in frames:
        if "kjcourse" in f.url:
            return f
    for f in frames:
        try:
            if f.evaluate("""() => !!document.querySelector('#course_player,video')
                              || typeof doLMSSetValue === 'function'"""):
                return f
        except Exception:
            pass
    return None


def probe_api(lp, tag):
    f = sco_frame(lp)
    frames = [fr.url[:110] for fr in lp.frames]
    if not f:
        log("  [%s] 未找到课件 iframe；当前 frames=%s" % (tag, frames[:6]))
        return {"api": False, "reason": "no_sco_frame", "frames": frames}
    try:
        info = f.evaluate(PROBE_API_JS)
    except Exception as e:
        info = {"api": False, "reason": str(e)[:100], "frames": frames}
    info["frames"] = frames
    info["sco_url"] = f.url[:150]
    return info


# ---------------------------------------------------------------------------
# 注入课件 iframe 的加速脚本（node --check 校验通过）
# ---------------------------------------------------------------------------
INJECT_JS = r"""
(function () {
  if (window.__FAST2_INJECTED__) return {already:true, commits: window.__FAST2_COMMITS__||0};
  window.__FAST2_INJECTED__ = true;
  window.__FAST2_COMMITS__ = 0;
  var CHUNK = __CHUNK__, TICK = __TICK__, FORCE = (__FORCE__ === 1);

  function pad(n){ return (n<10?'0':'') + n; }
  function hms(sec){
    var h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60), s = sec%60;
    return h + ':' + pad(m) + ':' + pad(s);
  }
  function getApi(){
    try { if (typeof getAPIHandle === 'function') { var a = getAPIHandle(); if (a) return a; } } catch(e){}
    try { if (typeof findAPI === 'function') { var b = findAPI(window); if (b) return b; } } catch(e){}
    try {
      var w = window, i = 0;
      while (w && i < 8) { if (w.API) return w.API; if (w === w.parent) break; w = w.parent; i++; }
    } catch(e){}
    return null;
  }
  function setv(k, v){
    try { if (typeof doLMSSetValue === 'function') { doLMSSetValue(k, v); return true; } } catch(e){}
    try { var a = getApi(); if (a && a.LMSSetValue) { a.LMSSetValue(k, v); return true; } } catch(e){}
    return false;
  }
  function commit(){
    try { if (typeof doLMSCommit === 'function') { doLMSCommit(); window.__FAST2_COMMITS__++; return true; } } catch(e){}
    try { var a = getApi(); if (a && a.LMSCommit) { a.LMSCommit(''); window.__FAST2_COMMITS__++; return true; } } catch(e){}
    return false;
  }
  function dur(){
    try { if (typeof player !== 'undefined' && player.getDuration) {
      var d = player.getDuration(); if (d && !isNaN(d)) return d; } } catch(e){}
    return 100000;
  }

  // 1) 放大课件自身计时变量（页面每 60s 会把 player_time 上报为 session_time）
  try { if (typeof player !== 'undefined') player.player_time = (player.player_time||0) + CHUNK; } catch(e){}

  // 2) 满足 doQuit() 的完成判定 (duration-60) <= max_time
  try { max_time = dur(); if (typeof send_data !== 'undefined') send_data = true; } catch(e){}

  // 3) 主动上报 + 【显式 Commit】（SCOFunctions 只 SetValue 不 Commit，这是提速关键）
  function report(){
    var ok = true;
    ok = setv('cmi.core.session_time', hms(CHUNK)) && ok;
    ok = setv('cmi.core.lesson_location', '99999.0') && ok;
    if (FORCE) ok = setv('cmi.core.lesson_status', 'completed') && ok;
    ok = setv('cmi.core.lesson_mode', 'normal') && ok;
    ok = commit() && ok;
    try { if (typeof player !== 'undefined') player.player_time += CHUNK; } catch(e){}
    return ok;
  }
  var first = report();
  window.__FAST2_TIMER__ = setInterval(report, TICK * 1000);

  // 4) 防挂机：自动静音 + 点击继续观看 + 重新播放
  window.__FAST2_KEEP__ = setInterval(function(){
    try {
      var vs = document.querySelectorAll('video');
      for (var i=0;i<vs.length;i++){ try { vs[i].muted = true; if (vs[i].paused) vs[i].play(); } catch(e){} }
      ['#msgbt', '.continue .user_choise', '.user_choise'].forEach(function(sel){
        try { var e = document.querySelector(sel);
              if (e && e.offsetParent !== null) e.click(); } catch(e){}
      });
    } catch(e){}
  }, 4000);

  // 5) 切换前收尾（等价于页面 unload 时的 doQuit）
  window.__FAST2_QUIT__ = function(){
    try {
      if (typeof send_data !== 'undefined') send_data = true;
      if (typeof max_time === 'undefined' || !max_time) max_time = dur();
      setv('cmi.core.exit', 'logout');
      setv('cmi.core.session_time', hms(CHUNK));
      setv('cmi.core.lesson_location', '99999.0');
      setv('cmi.core.entry', 'resume');
      if (FORCE) setv('cmi.core.lesson_status', 'completed');
      commit();
      try { if (typeof doLMSFinish === 'function') doLMSFinish(''); } catch(e){}
    } catch(e){}
    try { clearInterval(window.__FAST2_TIMER__); clearInterval(window.__FAST2_KEEP__); } catch(e){}
  };

  return {
    api: !!getApi(), first_report: first,
    chunk: CHUNK, tick: TICK, force: FORCE,
    max_time: (typeof max_time !== 'undefined' ? max_time : null),
    commits: window.__FAST2_COMMITS__
  };
})()
"""


def build_inject():
    return (INJECT_JS.replace("__CHUNK__", str(CHUNK))
                     .replace("__TICK__", str(TICK))
                     .replace("__FORCE__", "1" if FORCE else "0"))


def inject(lp, tag):
    f = sco_frame(lp)
    if not f:
        log("  [%s] 注入跳过：无课件 iframe" % tag)
        return False
    try:
        # 点掉"开始学习/继续学习"遮罩，让 send_data=true（doQuit 才会提交）
        try:
            f.get_by_text("开始学习", exact=True).first.click(timeout=4000)
        except Exception:
            pass
        try:
            f.get_by_text("继续学习", exact=True).first.click(timeout=3000)
        except Exception:
            pass
        f.evaluate("""() => {
            document.querySelectorAll('video').forEach(v=>{ try{v.muted=true;v.play();}catch(e){} });
            var e=document.querySelector('.continue .user_choise')||document.querySelector('#msgbt');
            if(e) e.click();
        }""")
        res = f.evaluate(build_inject())
        log("  [%s] 注入结果: %s" % (tag, res))
        return bool(res and res.get("api"))
    except Exception as e:
        log("  [%s] 注入失败: %s" % (tag, str(e)[:180]))
        return False


def hold_and_report(lp, seconds, tag):
    end = time.time() + seconds
    while time.time() < end:
        if stopped():
            return False
        f = sco_frame(lp)
        if f:
            try:
                f.evaluate("""() => {
                    document.querySelectorAll('video').forEach(v=>{try{v.muted=true; if(v.paused)v.play();}catch(e){}});
                    ['#msgbt','.continue .user_choise','.user_choise'].forEach(function(s){
                        try{var e=document.querySelector(s); if(e&&e.offsetParent!==null)e.click();}catch(e){}
                    });
                    if(window.__FAST2_INJECTED__ && typeof player!=='undefined') player.player_time += %d;
                }""" % CHUNK)
            except Exception:
                pass
        time.sleep(min(4, max(1, end - time.time())))
    return True


def quit_current(lp):
    f = sco_frame(lp)
    if f:
        with contextlib.suppress(BaseException):
            f.evaluate("() => { if(window.__FAST2_QUIT__) window.__FAST2_QUIT__(); }")
    with contextlib.suppress(BaseException):
        lp.wait_for_timeout(800)


# ---------------------------------------------------------------------------
# 请求/响应记录：抓真实上报接口与 post_data
# ---------------------------------------------------------------------------
KEY = re.compile(r"learn|time|record|study|progress|commit|scorm|saveCourses|saveUserToSpace", re.I)


def attach_recorder(pg):
    def on_request(req):
        try:
            if req.method in ("POST", "PUT") and KEY.search(req.url):
                pd = ""
                try:
                    pd = (req.post_data or "")[:400]
                except Exception:
                    pass
                with open(REQ_LOG, "a", encoding="utf-8") as f:
                    f.write("%s REQ %s %s | %s\n" % (
                        datetime.datetime.now().strftime("%H:%M:%S"),
                        req.method, req.url[:240], pd.replace("\n", " ")))
        except Exception:
            pass

    def on_response(resp):
        try:
            if resp.request.method in ("POST", "PUT") and KEY.search(resp.url):
                body = ""
                try:
                    body = resp.text()[:200]
                except Exception:
                    pass
                with open(REQ_LOG, "a", encoding="utf-8") as f:
                    f.write("%s RES %s %s | %s\n" % (
                        datetime.datetime.now().strftime("%H:%M:%S"),
                        resp.status, resp.url[:200], body.replace("\n", " ")))
        except Exception:
            pass

    pg.on("request", on_request)
    pg.on("response", on_response)


# ---------------------------------------------------------------------------
# 关闭阶段：吞掉所有异常（含二次 KeyboardInterrupt）
# ---------------------------------------------------------------------------
def shutdown(ctx, browser, pw):
    for fn in (lambda: ctx.close(), lambda: browser.close(), lambda: pw.stop()):
        with contextlib.suppress(BaseException):
            fn()


def main():
    if not PWD:
        log("ERROR: 请设置环境变量 CMATC_PWD（或 run_fast_v2.bat 密码）")
        sys.exit(1)
    if os.path.exists(STOP_FLAG):
        os.remove(STOP_FLAG)
    log("=" * 70)
    log("加速学习 v2 启动 | 目标 %s | CHUNK=%ss TICK=%ss DWELL=%ss FORCE=%s DIAG=%s"
        % (TARGET, CHUNK, TICK, DWELL, FORCE, DIAG))
    log("v2 修复：真实 _learnspace 弹窗入口 / HTTP 直接选课 / 强制 window.API 检测 / 显式 doLMSCommit")
    log("严格单窗口轮转；创建 stop_fast_v2.flag 可优雅停止。")
    log("提示：单点登录会互踢，启动前请先停掉 auto_study.py / fast_study.py。")

    pw = sync_playwright().start()
    browser = pw.chromium.launch(executable_path=EDGE, headless=True, args=ARGS)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              ignore_https_errors=True)
    pg = ctx.new_page()
    pg.set_default_timeout(20000)
    attach_recorder(pg)

    seen = load_seen()
    rounds = 0
    lp = None
    try:
        log("登录中...")
        try:
            login(pg, verbose=False)
        except Exception as e:
            log("登录失败：%s" % str(e)[:300])
            log("已停止。确认已停掉其他会话、密码正确后重启。")
            return
        log("登录完成: %s" % pg.url)

        while not stopped():
            rounds += 1
            log("-" * 70)
            log("第 %d 轮：检查学时" % rounds)
            credit = read_credit(pg)
            if credit is None:
                log("  学时读取失败，5 秒后重试")
                pg.wait_for_timeout(5000)
                continue
            log("  当前本年度完成学时: %s / %s" % (credit, TARGET))
            if credit >= TARGET:
                log("已达标（%s >= %s），退出。" % (credit, TARGET))
                break

            pool = build_course_pool(pg, NEED)
            courses = [c for c in pool if c["url"] not in seen]
            if not courses:
                log("  课程池已全部轮转过，清空 seen 重新开始")
                seen.clear()
                courses = pool
            courses = courses[:MAX_COURSES]
            if DIAG:
                courses = courses[:1]
            if not courses:
                log("  仍未找到可学习课程，退出")
                break
            for c in courses:
                mark_seen(c["url"])
                seen.add(c["url"])

            log("  本轮轮转 %d 门课程（单窗口串行，不并发）" % len(courses))
            for idx, c in enumerate(courses):
                if stopped():
                    break
                tag = "course%d" % (idx + 1)
                log("  (%d/%d) %s -> %s" % (idx + 1, len(courses), c["fn"], c["url"][:95]))
                try:
                    lp, how = open_learnspace(pg, ctx, c, tag, lp)
                except Exception as e:
                    log("  [%s] 打开学习页异常: %s" % (tag, str(e)[:160]))
                    continue
                if lp is None:
                    continue

                # 关键：注入前强制检测 window.API
                info = probe_api(lp, tag)
                log("  [%s] 入口=%s API检测=%s" % (tag, how, json.dumps(
                    {k: v for k, v in info.items() if k != "frames"}, ensure_ascii=False)[:300]))
                if not info.get("api"):
                    log("  [%s] api:False，重开一次入口..." % tag)
                    with contextlib.suppress(BaseException):
                        lp.close()
                    lp = None
                    lp, how = open_learnspace(pg, ctx, c, tag, lp)
                    if lp is not None:
                        info = probe_api(lp, tag)
                        log("  [%s] 重开后 API检测=%s" % (tag, json.dumps(
                            {k: v for k, v in info.items() if k != "frames"},
                            ensure_ascii=False)[:300]))
                if lp is None or not info.get("api"):
                    log("  [%s] 仍无 window.API，跳过（不做无效注入）" % tag)
                    if DIAG:
                        log("  [DIAG] frames=%s" % info.get("frames"))
                    continue

                ok = inject(lp, tag)
                if not ok:
                    log("  [%s] 注入未成功，跳过" % tag)
                    continue
                hold_and_report(lp, DWELL, tag)
                quit_current(lp)
                if DIAG:
                    f = sco_frame(lp)
                    if f:
                        with contextlib.suppress(BaseException):
                            log("  [DIAG] commits=%s" % f.evaluate(
                                "() => window.__FAST2_COMMITS__"))
                    log("  [DIAG] 诊断完成，退出（查看 fast_v2_requests.log 确认真实上报请求）")
                    return

            # 收掉学习窗口，避免残留与下一轮冲突
            if lp is not None and not lp.is_closed():
                with contextlib.suppress(BaseException):
                    lp.close()
            lp = None
            with contextlib.suppress(BaseException):
                pg.goto("about:blank", wait_until="commit", timeout=15000)

            if ROUNDS and rounds >= ROUNDS:
                log("达到试运行轮数上限 %d，结束。" % ROUNDS)
                break
    finally:
        shutdown(ctx, browser, pw)
        log("脚本结束。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("收到 Ctrl+C，已退出（建议用 stop_fast_v2.flag 优雅停止）。")
    except SystemExit:
        raise
    except Exception:
        log("未捕获异常:\n%s" % traceback.format_exc()[-1200:])
