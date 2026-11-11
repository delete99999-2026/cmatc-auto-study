# -*- coding: utf-8 -*-
"""
中国气象局培训学院 - 加速学习脚本（升级版，独立于 auto_study.py）

借鉴 old_js/气象干部培训学院科学学习.user.js 的三个核心思路，适配现行
webtrn / learnspace(SCORM) 平台：

  1) 加速："以课程时间记学时"
     旧站：POST recordLearnTimePro.do, learntime=120, 每 35s 一次。
     新站：课件 SCOFunctions.singlevideo.js 每 60s 通过
           doLMSSetValue("cmi.core.session_time", ...) 上报会话时长，
           doQuit() 中用 (duration-60)<=max_time 判定 completed。
     本脚本在课件 iframe 内注入：放大 player.player_time、主动上报放大的
     session_time、置 max_time 满足完成条件、直接写 lesson_status=completed
     并 doLMSCommit()，从而用秒级真实时间换取成倍的课程学时。

  2) 多门课同时推进却不触发"课程被终止"
     平台用 window.open(url, '_learnspace') 固定窗口名，并用
     /u/study/saveUserToSpaceRecord.json 记录当前在学课程；同时打开多个
     学习窗口会互相顶掉并终止前一门的 SCORM 会话。
     本脚本复用【同一个页面】按 12s 间隔轮转各门课程，任一时刻只有一个
     学习页存在；切换时页面 unload 触发 doQuit() 完成提交，与旧脚本
     "一键全学"复用 learnWindow 的做法一致。

  3) 防挂机：自动静音、自动点击"继续观看"弹窗、自动重新播放。

另：记录页面自身发出的学习上报请求到 fast_requests.log，便于后续按真实
接口格式做进一步提速（本脚本不伪造 HTTP 接口，只调用页面自己的 SCORM API）。

※ 严格串行，不并发学习；※ 不修改 auto_study.py；※ 启动会登录一次，
   因平台单点登录会互踢，请【先停掉正在运行的 auto_study.py】再启动本脚本。

用法：
  set "CMATC_PWD=你的密码"       (CMD；注意不要写成 set CMATC_PWD='密码')
  python -u fast_study.py
或 run_fast.bat 你的密码

可调环境变量：
  CMATC_TARGET    目标学时，默认 80
  CMATC_CHUNK     每次上报的课程时间秒数，默认 120（对齐旧脚本 learntime=120）
  CMATC_TICK      主动上报间隔秒，默认 35（对齐旧脚本 35000ms）
  CMATC_DWELL     每门课/课件停留秒数，默认 12（对齐旧脚本 12000ms）
  CMATC_FORCE     1=直接写 lesson_status=completed（默认），0=仅放大时长
  CMATC_MAX_COURSES 每轮最多轮转课程数，默认 12
  CMATC_ROUNDS    轮数上限，0=不限（试运行可设 1）
"""
import os, re, sys, time, json, datetime, traceback
from playwright.sync_api import sync_playwright

from common import EDGE, HOST, OUT, USER, PWD, ARGS, login

TARGET = float(os.environ.get("CMATC_TARGET", "80"))
CHUNK = int(os.environ.get("CMATC_CHUNK", "120"))
TICK = int(os.environ.get("CMATC_TICK", "35"))
DWELL = int(os.environ.get("CMATC_DWELL", "12"))
FORCE = os.environ.get("CMATC_FORCE", "1") == "1"
MAX_COURSES = int(os.environ.get("CMATC_MAX_COURSES", "12"))
ROUNDS = int(os.environ.get("CMATC_ROUNDS", "0"))

STOP_FLAG = os.path.join(OUT, "stop_fast.flag")
LOG = os.path.join(OUT, "fast_run.log")
REQ_LOG = os.path.join(OUT, "fast_requests.log")
SEEN = os.path.join(OUT, "fast_seen.txt")


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


def nav(pg, url, wait=6000):
    try:
        pg.goto(url, wait_until="commit", timeout=60000)
    except Exception as e:
        log("  goto warn: %s" % str(e)[:110])
    pg.wait_for_timeout(wait)


def read_credit(pg):
    nav(pg, HOST + "/u/student/study/myCourse.action")
    val = pg.evaluate("""() => {
        for (const e of document.querySelectorAll('h4,div,span,li')) {
            if ((e.textContent||'').trim() === '本年度完成学时') {
                const t = (e.parentElement?e.parentElement.textContent:'').replace(/\\s+/g,' ');
                const m = t.match(/(\\d+(?:\\.\\d+)?)\\s*学时/);
                if (m) return m[1];
            }
        }
        return null;
    }""")
    try:
        return float(val) if val is not None else None
    except Exception:
        return None


def collect_courses(pg):
    """从课程中心提取可直接进入学习的课程链接（enterCourseTimeLimit 首参）"""
    nav(pg, HOST + "/cms/courseMarketNew.htm", wait=8000)
    return pg.evaluate("""() => {
        const out = [];
        document.querySelectorAll('a[onclick*="enterCourseTimeLimit"]').forEach(a => {
            const oc = a.getAttribute('onclick') || '';
            const m = oc.match(/enterCourseTimeLimit\\(\\s*'([^']+)'/);
            if (m && m[1]) out.push({url: m[1], oc: oc.slice(0, 200)});
        });
        return out;
    }""")


def collect_choose_ids(pg, limit):
    """课程不足时，返回可'立即选课'的课程 id"""
    return pg.evaluate("""(lim) => {
        const out = [];
        document.querySelectorAll('a[onclick*="chooseCourseTimeLimit"]').forEach(a => {
            const m = (a.getAttribute('onclick')||'').match(/chooseCourseTimeLimit\\(\\s*'([^']+)'/);
            if (m) out.push(m[1]);
        });
        return out.slice(0, lim);
    }""", limit)


def choose_courses(pg, n):
    ids = collect_choose_ids(pg, n)
    for cid in ids:
        try:
            pg.evaluate("(id) => chooseCourseTimeLimit(id, '')", cid)
            pg.wait_for_timeout(1200)
            log("  补选课程 %s" % cid[:16])
        except Exception as e:
            log("  补选异常 %s" % str(e)[:90])
    if ids:
        pg.wait_for_timeout(3000)
    return len(ids)


def collect_items(lp):
    """在学习页里提取本门课的所有课件链接（含 itemId）"""
    urls = []
    for f in lp.frames:
        try:
            if "courseware_index" not in f.url and "content_webCourseware" not in f.url:
                continue
            got = f.evaluate("""() => {
                const s = new Set();
                document.querySelectorAll('a').forEach(a => {
                    const h = (a.getAttribute('href')||'') + ' ' + (a.getAttribute('onclick')||'');
                    const m = h.match(/itemId[=:'"\\s]+([0-9A-Za-z_-]+)/);
                    if (m) s.add(h.trim());
                });
                return [...s];
            }""")
            for g in got:
                if g not in urls:
                    urls.append(g)
        except Exception:
            pass
    # 只保留能拼成 content_webCourseware URL 的
    clean = []
    for u in urls:
        m = re.search(r"(https?://[^\s'\"]*content_webCourseware\.action[^\s'\"]*)", u)
        if m:
            clean.append(m.group(1))
        elif u.startswith("/learnspace"):
            clean.append("https://pxkckj-cmatc.cma.cn" + u)
    return clean[:12]


# ---------------------------------------------------------------------------
# 注入课件 iframe 的加速脚本（语法由 node -c 校验；此处只做字符串模板）
# ---------------------------------------------------------------------------
INJECT_JS = r"""
(function () {
  if (window.__FAST_INJECTED__) return {already:true};
  window.__FAST_INJECTED__ = true;
  var CHUNK = __CHUNK__, TICK = __TICK__, FORCE = (__FORCE__ === 1);

  function pad(n){ return (n<10?'0':'') + n; }
  function hms(sec){
    var h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60), s = sec%60;
    return h + ':' + pad(m) + ':' + pad(s);
  }
  function getApi(){
    try {
      if (typeof getAPIHandle === 'function') { var a = getAPIHandle(); if (a) return a; }
    } catch(e){}
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
    try { if (typeof doLMSCommit === 'function') { doLMSCommit(); return; } } catch(e){}
    try { var a = getApi(); if (a && a.LMSCommit) a.LMSCommit(''); } catch(e){}
  }
  function dur(){
    try { if (typeof player !== 'undefined' && player.getDuration) {
      var d = player.getDuration(); if (d && !isNaN(d)) return d; } } catch(e){}
    return 100000;
  }

  // 1) 放大课件自身计时变量（页面每 60s 会把 player_time 上报为 session_time）
  try { if (typeof player !== 'undefined') player.player_time = (player.player_time||0) + CHUNK; } catch(e){}

  // 2) 满足 doQuit() 的完成判定 (duration-60) <= max_time
  try {
    max_time = dur();
    if (typeof send_data !== 'undefined') send_data = true;
  } catch(e){}

  // 3) 主动、放大地上报会话时长
  function report(){
    try {
      setv('cmi.core.session_time', hms(CHUNK));
      setv('cmi.core.lesson_location', '99999.0');
      if (FORCE) setv('cmi.core.lesson_status', 'completed');
      setv('cmi.core.lesson_mode', 'normal');
      commit();
    } catch(e){}
    try { if (typeof player !== 'undefined') player.player_time += CHUNK; } catch(e){}
  }
  report();
  window.__FAST_TIMER__ = setInterval(report, TICK * 1000);

  // 4) 防挂机：自动静音 + 点击"继续观看" + 重新播放
  window.__FAST_KEEP__ = setInterval(function(){
    try {
      var vs = document.querySelectorAll('video');
      for (var i=0;i<vs.length;i++){ try { vs[i].muted = true; if (vs[i].paused) vs[i].play(); } catch(e){} }
      ['#msgbt', '.continue .user_choise', '.user_choise'].forEach(function(sel){
        try { var e = document.querySelector(sel);
              if (e && e.offsetParent !== null) e.click(); } catch(e){}
      });
    } catch(e){}
  }, 4000);

  // 5) 切换前手动收尾（等价于页面 unload 时的 doQuit）
  window.__FAST_QUIT__ = function(){
    try {
      if (typeof send_data !== 'undefined') send_data = true;
      if (typeof max_time === 'undefined' || !max_time) max_time = dur();
      setv('cmi.core.exit', 'logout');
      setv('cmi.core.session_time', hms(CHUNK));
      setv('cmi.core.lesson_location', '99999.0');
      setv('cmi.core.entry', 'resume');
      if (FORCE) setv('cmi.core.lesson_status', 'completed');
      commit();
      try { if (typeof doLMSFinish === 'function') doLMSFinish(); } catch(e){}
    } catch(e){}
  };

  return {api: !!getApi(), chunk: CHUNK, tick: TICK, force: FORCE, max_time: (typeof max_time!=='undefined'?max_time:null)};
})()
"""


def build_inject():
    return (INJECT_JS.replace("__CHUNK__", str(CHUNK))
                     .replace("__TICK__", str(TICK))
                     .replace("__FORCE__", "1" if FORCE else "0"))


def kj_frame(lp):
    return next((f for f in lp.frames if "kjcourse" in f.url), None)


def inject(lp, tag):
    f = kj_frame(lp)
    if not f:
        log("  [%s] 未找到课件 iframe，跳过" % tag)
        return False
    try:
        # 自动点击"开始学习"（旧脚本的 .user_choise）
        try:
            f.get_by_text("开始学习", exact=True).first.click(timeout=4000)
        except Exception:
            pass
        f.evaluate("""() => {
            document.querySelectorAll('video').forEach(v=>{ try{v.muted=true;v.play();}catch(e){} });
            var e=document.querySelector('.continue .user_choise')||document.querySelector('#msgbt');
            if(e) e.click();
        }""")
        res = f.evaluate(build_inject())
        log("  [%s] 注入完成: %s" % (tag, res))
        return True
    except Exception as e:
        log("  [%s] 注入失败: %s" % (tag, str(e)[:160]))
        return False


def hold_and_report(lp, seconds, tag):
    """停留期间保持活跃，定期再次上报；支持随时停止"""
    end = time.time() + seconds
    while time.time() < end:
        if stopped():
            return False
        f = kj_frame(lp)
        if f:
            try:
                f.evaluate("""() => {
                    document.querySelectorAll('video').forEach(v=>{try{v.muted=true; if(v.paused)v.play();}catch(e){}});
                    ['#msgbt','.continue .user_choise','.user_choise'].forEach(function(s){
                        try{var e=document.querySelector(s); if(e&&e.offsetParent!==null)e.click();}catch(e){}
                    });
                    if(window.__FAST_INJECTED__ && typeof player!=='undefined') player.player_time += %d;
                }""" % CHUNK)
            except Exception:
                pass
        time.sleep(min(4, max(1, end - time.time())))
    return True


def quit_current(lp):
    f = kj_frame(lp)
    if f:
        try:
            f.evaluate("() => { if(window.__FAST_QUIT__) window.__FAST_QUIT__(); }")
        except Exception:
            pass


def study_round(pg, lp, courses):
    """单窗口轮转：同一时刻只有 lp 这一个学习页"""
    for idx, c in enumerate(courses):
        if stopped():
            return
        url = c["url"]
        log("  (%d/%d) 进入课程 %s" % (idx + 1, len(courses), url[:95]))
        try:
            nav(lp, url, wait=6000)
        except Exception as e:
            log("    打开失败: %s" % str(e)[:110])
            continue
        # 若被拦回登录/异常页，跳过
        if "login" in lp.url.lower() and "loginNew" in lp.url:
            log("    被重定向到登录页，跳过")
            continue
        inject(lp, "course%d" % (idx + 1))
        if not hold_and_report(lp, DWELL, "course%d" % (idx + 1)):
            return
        quit_current(lp)          # 主动提交，再切下一门（unload 还会再触发 doQuit）
        lp.wait_for_timeout(600)


def main():
    if not PWD:
        log("ERROR: 请设置环境变量 CMATC_PWD")
        sys.exit(1)
    if os.path.exists(STOP_FLAG):
        os.remove(STOP_FLAG)
    log("=" * 66)
    log("加速学习启动 | 目标 %s 学时 | CHUNK=%ss TICK=%ss DWELL=%ss FORCE=%s" %
        (TARGET, CHUNK, TICK, DWELL, FORCE))
    log("提示：平台为单点登录，本脚本登录会踢掉其他会话，请先停掉 auto_study.py。")
    log("严格单窗口轮转，任一时刻只有一个学习页；创建 stop_fast.flag 可停止。")

    pw = sync_playwright().start()
    browser = pw.chromium.launch(executable_path=EDGE, headless=True, args=ARGS)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              ignore_https_errors=True)
    pg = ctx.new_page()
    pg.set_default_timeout(20000)
    lp = ctx.new_page()          # 唯一的学习窗口，对应平台 '_learnspace'
    lp.set_default_timeout(20000)

    # 记录页面自身的学习上报请求，便于后续按真实接口进一步优化
    def on_request(req):
        try:
            if req.method in ("POST", "PUT") and re.search(
                    r"learn|time|record|study|progress|commit|scorm", req.url, re.I):
                with open(REQ_LOG, "a", encoding="utf-8") as f:
                    f.write("%s %s %s\n" % (
                        datetime.datetime.now().strftime("%H:%M:%S"),
                        req.method, req.url[:220]))
        except Exception:
            pass
    lp.on("request", on_request)

    seen = load_seen()
    rounds = 0
    try:
        log("登录中...")
        try:
            login(pg, verbose=False)
        except Exception as e:
            log("登录失败：%s" % str(e)[:300])
            log("已停止。请确认已停掉 auto_study.py 并修正密码后重启。")
            return
        log("登录完成: %s" % pg.url)

        while not stopped():
            rounds += 1
            log("-" * 66)
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

            courses = collect_courses(pg)
            log("  可直接学习的课程: %d 门" % len(courses))
            if len(courses) < 3:
                log("  课程不足，自动补选...")
                choose_courses(pg, max(3, min(MAX_COURSES, 8)))
                courses = collect_courses(pg)
                log("  补选后可学习课程: %d 门" % len(courses))
            courses = [c for c in courses if c["url"] not in seen]
            if not courses:
                seen.clear()
                courses = collect_courses(pg)
            courses = courses[:MAX_COURSES]
            for c in courses:
                mark_seen(c["url"])
                seen.add(c["url"])
            if not courses:
                log("  未找到可学习课程，退出")
                break

            log("  本轮轮转 %d 门课程（单窗口串行，不并发）" % len(courses))
            try:
                study_round(pg, lp, courses)
            except Exception as e:
                log("  轮转异常: %s" % str(e)[:180])
                log(traceback.format_exc()[-400:])
            # 轮转完把学习窗口置空，避免残留学习页与下一轮冲突
            try:
                lp.goto("about:blank", wait_until="commit", timeout=15000)
            except Exception:
                pass

            if ROUNDS and rounds >= ROUNDS:
                log("达到试运行轮数上限 %d，结束。" % ROUNDS)
                break
    finally:
        try:
            ctx.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass
        pw.stop()
        log("脚本结束。")


if __name__ == "__main__":
    main()
