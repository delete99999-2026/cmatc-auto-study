# -*- coding: utf-8 -*-
"""诊断登录：捕获错误提示 / 验证码状态 / 最终 URL"""
import os
from playwright.sync_api import sync_playwright
from common import EDGE, HOST, USER, PWD, ARGS, OUT

print("PWD repr:", repr(PWD), "len:", len(PWD))

pw = sync_playwright().start()
browser = pw.chromium.launch(executable_path=EDGE, headless=True, args=ARGS)
ctx = browser.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=True)
page = ctx.new_page()
page.set_default_timeout(20000)
try:
    page.goto(HOST + "/cms/loginNew.htm?portal=index", wait_until="commit", timeout=30000)
    page.wait_for_selector("#user1", timeout=25000)
    page.wait_for_timeout(1500)

    print("\n=== 登录前状态 ===")
    print("验证码区域 display:", page.evaluate(
        "() => {const e=document.getElementById('authCodeDiv'); return e?getComputedStyle(e).display:'N/A';}"))
    print("falseNum cookie:", page.evaluate("() => document.cookie"))

    page.fill("#user1", USER)
    page.fill("#pwd1", PWD)
    page.click("#doSubmitBtn")

    for i in range(12):
        page.wait_for_timeout(1500)
        u = page.url
        msgs = page.evaluate("""() => {
            const out=[];
            document.querySelectorAll('div,span,p,a').forEach(e=>{
                const t=(e.textContent||'').trim();
                if(e.children.length===0 && t && /错误|失败|不存在|锁定|验证码|请填写|不能为空|异常/.test(t) && t.length<80)
                    out.push(t);
            });
            return out.slice(0,10);
        }""")
        print("  [%02d] %s | msgs=%s" % (i, u[:110], msgs))
        if "loginNew" not in u:
            break

    print("\n=== 最终 URL ===", page.url)
    print("=== 验证码区域 display(后) ===", page.evaluate(
        "() => {const e=document.getElementById('authCodeDiv'); return e?getComputedStyle(e).display:'N/A';}"))
    print("=== body text ===")
    print(page.evaluate("() => document.body.innerText")[:1200])
    print("=== cookies ===")
    for c in ctx.cookies():
        print("  ", c["name"], "=", (c["value"] or "")[:50])

    page.screenshot(path=os.path.join(OUT, "diag_login.png"), full_page=False)
finally:
    ctx.close(); browser.close(); pw.stop()
