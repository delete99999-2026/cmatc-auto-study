# -*- coding: utf-8 -*-
"""
中国气象局培训学院 - 自动循环学习脚本

实现用户要求的三步循环：
  任务1: 读取当前学时；>= 80 则退出
  任务2: 未达标，从课程中心选一门课并学习
  任务3: 学完一门后回到任务1

重要约束（对应平台检测机制）：
  * 全程单浏览器、单会话、严格串行——同一时刻只打开一个课程学习页，
    学完（或超时）后必须先关闭该页，再开下一门，绝不并发学习不同课程。
  * 不做进度伪造、不调用上报接口、不加速视频，只做"打开课程 + 点击播放 + 保持页面"。
  * 随时可在脚本目录创建 stop.flag 文件优雅停止。

用法（PowerShell / Git Bash 均可，密码用环境变量传入，不写入文件）：
  CMATC_PWD='你的密码' python -u auto_study.py
可选环境变量：
  CMATC_TARGET  目标学时，默认 80
  CMATC_MAX_MIN 单门课最长等待分钟，默认 120
  CMATC_USER    用户名，必填（无内置默认值；通过启动参数或环境变量提供）
"""
import os, re, sys, time, datetime, traceback
from playwright.sync_api import sync_playwright

from common import EDGE, HOST, OUT, USER, PWD, ARGS

TARGET = float(os.environ.get("CMATC_TARGET", "80"))
MAX_MIN = float(os.environ.get("CMATC_MAX_MIN", "120"))
ROUNDS = int(os.environ.get("CMATC_ROUNDS", "0"))   # 0=不限轮数；试运行可设为 1
STOP_FLAG = os.path.join(OUT, "stop.flag")
LOG = os.path.join(OUT, "run.log")
SEEN = os.path.join(OUT, "seen_courses.txt")


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


def mark_seen(cid):
    with open(SEEN, "a", encoding="utf-8") as f:
        f.write(cid + "\n")


def nav(pg, path, wait=7000):
    try:
        pg.goto(HOST + path, wait_until="commit", timeout=60000)
    except Exception as e:
        log("  goto warn: %s" % str(e)[:110])
    pg.wait_for_timeout(wait)


def read_credit(pg):
    """读取学习中心的本年度完成学时"""
    nav(pg, "/u/student/study/myCourse.action")
    val = pg.evaluate("""() => {
        const hs=[...document.querySelectorAll('h4,div,span,li')];
        for(const e of hs){
            if((e.textContent||'').trim()==='本年度完成学时'){
                const t=(e.parentElement?e.parentElement.textContent:'').replace(/\\s+/g,' ');
                const m=t.match(/(\\d+(?:\\.\\d+)?)\\s*学时/);
                if(m) return m[1];
            }
        }
        return null;
    }""")
    try:
        return float(val) if val is not None else None
    except Exception:
        return None


def get_progress(pg):
    """从'我的课程'页抓取未完成课程及其进度"""
    nav(pg, "/u/student/study/myCourse.action")
    return pg.evaluate("""() => {
        const out=[];
        document.querySelectorAll('a').forEach(a=>{
            if((a.textContent||'').trim()==='继续学习'){
                let box=a.closest('li,div');
                for(let i=0;i<4&&box;i++) box=box.parentElement;
                const t=box?box.innerText.replace(/\\s+/g,' '):'';
                const m=t.match(/学习进度[:：]\\s*([\\d.]+)%/);
                const name=(t.match(/(\\d{4}年\\s*[\\d.]+学时\\s*(?:上次学习此课程\\s*)?)(.+?)学习进度/)||[])[2]||'';
                out.push({name:name.trim().slice(0,40), pct:m?parseFloat(m[1]):null});
            }
        });
        return out;
    }""")


def pick_course(pg, seen):
    """从课程中心挑一门未处理过的、学时较高的课程并选课"""
    nav(pg, "/cms/courseMarketNew.htm", wait=8000)
    items = pg.evaluate("""() => {
        const out=[];
        document.querySelectorAll('a[onclick*="chooseCourseTimeLimit"]').forEach(a=>{
            const oc=a.getAttribute('onclick')||'';
            const m=oc.match(/chooseCourseTimeLimit\\('([^']+)'/);
            if(!m) return;
            let box=a; for(let i=0;i<5;i++) box=box.parentElement;
            const t=box?box.innerText.replace(/\\s+/g,' '):'';
            const h=t.match(/([\\d.]+)学时/);
            const nm=(t.match(/(\\d{4}年\\s*.{0,60}?)\\s*[\\d.]+学时/)||[])[1]||'';
            out.push({id:m[1], hours:h?parseFloat(h[1]):0, text:t.slice(0,90)});
        });
        return out;
    }""")
    log("  课程中心可选课程 %d 门" % len(items))
    cands = [c for c in items if c["id"] not in seen]
    if not cands:
        cands = [c for c in items if c["hours"] > 0]
    if not cands:
        return None
    cands.sort(key=lambda c: -c["hours"])          # 优先高学时，减少课程门数
    c = cands[0]
    log("  选中课程: %s (%s学时) id=%s" % (c["text"][:45], c["hours"], c["id"]))
    try:
        pg.evaluate("(id) => chooseCourseTimeLimit(id, '')", c["id"])
        pg.wait_for_timeout(4000)
        # 可能出现的确认弹窗
        for kw in ["确定", "确认", "选课"]:
            try:
                btn = pg.get_by_text(kw, exact=True).first
                if btn.is_visible(timeout=1500):
                    btn.click(timeout=2000)
                    pg.wait_for_timeout(2000)
                    break
            except Exception:
                pass
    except Exception as e:
        log("  选课异常: %s" % str(e)[:150])
    mark_seen(c["id"])
    return c


def open_learn_page(pg, ctx):
    """在'我的课程'里点'继续学习'，返回新打开的学习页"""
    nav(pg, "/u/student/study/myCourse.action")
    try:
        with pg.expect_popup(timeout=15000) as pop:
            pg.get_by_text("继续学习", exact=True).first.click(timeout=10000)
        lp = pop.value
    except Exception as e:
        log("  打开学习页失败: %s" % str(e)[:130])
        return None
    lp.wait_for_timeout(7000)
    return lp


def start_playback(lp):
    """在课件 iframe 中点击'开始学习'，确保视频处于播放状态"""
    try:
        kj = next((f for f in lp.frames if "kjcourse" in f.url), None)
        if not kj:
            log("  未找到课件视频 frame")
            return
        try:
            kj.get_by_text("开始学习", exact=True).first.click(timeout=8000)
            log("  已点击 开始学习")
        except Exception:
            pass
        kj.evaluate("""() => { const v=document.querySelector('video');
            if(v){ try{ v.play(); }catch(e){} } }""")
    except Exception as e:
        log("  播放启动异常: %s" % str(e)[:120])


def keep_alive(lp, seconds):
    """保持学习页存活，定期轻微活动，防止被判定为无操作"""
    end = time.time() + seconds
    while time.time() < end:
        if stopped():
            return False
        try:
            lp.mouse.move(300 + int(time.time()) % 200, 200)
            lp.evaluate("""() => { const v=document.querySelector('video');
                if(v && v.paused){ try{ v.play(); }catch(e){} } }""")
        except Exception:
            pass
        time.sleep(20)
    return True


def study_one_course(pg, ctx):
    """串行学习一门课：打开 -> 播放 -> 等待完成/超时 -> 关闭"""
    lp = open_learn_page(pg, ctx)
    if not lp:
        return False
    try:
        log("  学习页: %s" % lp.url[:120])
        start_playback(lp)
        deadline = time.time() + MAX_MIN * 60
        last_pct, stall = None, 0
        while time.time() < deadline:
            if stopped():
                log("  收到停止信号")
                return False
            if not keep_alive(lp, 60):
                return False
            # 每 5 分钟回列表查一次进度（学习页保持打开，不并发学习）
            if int(time.time() - (deadline - MAX_MIN * 60)) % 300 < 60:
                try:
                    ps = get_progress(pg)
                    pct = ps[0]["pct"] if ps else None
                    log("  当前进度: %s  学习时长累计中" % pct)
                    if pct is not None and pct >= 99.9:
                        log("  课程进度已达 100%，本门完成")
                        return True
                    if pct is not None and last_pct is not None and pct <= last_pct:
                        stall += 1
                    else:
                        stall = 0
                    last_pct = pct
                    # 进度长时间不涨（视频解码受限）则换下一门，避免无效死等
                    if stall >= 6:
                        log("  进度连续 30 分钟未增长，判定本门受阻，换下一门")
                        return False
                except Exception as e:
                    log("  进度查询异常: %s" % str(e)[:110])
        log("  单门课达到最长等待 %s 分钟，换下一门" % MAX_MIN)
        return False
    finally:
        try:
            lp.close()          # 关键：先关闭学习页，再开下一门，避免并发
        except Exception:
            pass
        pg.wait_for_timeout(2000)


def main():
    if not PWD:
        log("ERROR: 请设置环境变量 CMATC_PWD")
        sys.exit(1)
    if os.path.exists(STOP_FLAG):
        os.remove(STOP_FLAG)
    log("=" * 60)
    log("自动学习启动 | 目标 %s 学时 | 单门上限 %s 分钟 | 轮数上限 %s" %
        (TARGET, MAX_MIN, "不限" if ROUNDS == 0 else ROUNDS))
    log("严格串行：同一时刻只学习一门课程。创建 stop.flag 可随时停止。")

    pw = sync_playwright().start()
    browser = pw.chromium.launch(executable_path=EDGE, headless=True, args=ARGS)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              ignore_https_errors=True)
    pg = ctx.new_page()
    pg.set_default_timeout(20000)

    seen = load_seen()
    rounds = 0
    fail_reads = 0
    try:
        # 单会话登录一次；失败立即止损，避免"读学时失败 -> 反复登录"死循环
        from common import login
        log("登录中...")
        try:
            login(pg, verbose=False)
        except Exception as e:
            log("登录失败：%s" % str(e)[:300])
            log("已停止，未执行任何选课/学习操作。请修正密码后重新启动。")
            return
        log("登录完成: %s" % pg.url)

        while not stopped():
            rounds += 1
            log("-" * 60)
            log("第 %d 轮：检查学时" % rounds)
            credit = read_credit(pg)
            if credit is None:
                fail_reads += 1
                log("  学时读取失败（%d/3）" % fail_reads)
                if fail_reads >= 3:
                    log("  连续 3 次读取失败，疑似登录态失效，停止脚本。")
                    break
                try:
                    login(pg, verbose=False)
                except Exception as e:
                    log("  重新登录失败：%s" % str(e)[:150])
                    break
                pg.wait_for_timeout(5000)
                continue
            fail_reads = 0
            log("  当前本年度完成学时: %s / %s" % (credit, TARGET))
            if credit >= TARGET:
                log("已达标（%s >= %s），退出。" % (credit, TARGET))
                break
            log("未达标，还差 %.1f 学时 -> 选课" % (TARGET - credit))
            try:
                c = pick_course(pg, seen)
                if not c:
                    log("  课程中心无可选课程，退出")
                    break
                seen.add(c["id"])
                log("开始学习一门课程（串行）")
                study_one_course(pg, ctx)
            except Exception as e:
                log("  本轮异常: %s" % str(e)[:200])
                log(traceback.format_exc()[-500:])
                pg.wait_for_timeout(5000)

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
