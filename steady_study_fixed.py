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
  【2026-11-11 第九轮】账号 / 密码 / 目标学时均为启动参数，默认目标 80 学时：
  run_steady.bat <账号> <密码>                 # 目标 80 学时（默认）
  run_steady.bat <账号> <密码> 100             # 目标 100 学时
  run_steady.bat <账号> <密码> 100 dry         # 只读统计 + 自主选课规划
  run_steady.bat <账号> <密码> 100 diag        # 诊断：只跑一门、打印 frames/视频状态
  run_steady.bat <密码> [diag|dry]             # 兼容旧用法（账号取默认）
或直接用 Python：
  python -u steady_study_fixed.py --user U --pwd P --target 100 [--diag|--dry]
  python -u steady_study_fixed.py U P 100 [dry|diag]
或环境变量（CMD；切勿写成 set CMATC_PWD='密码'）：
  set "CMATC_USER=账号"
  set "CMATC_PWD=你的密码"
  set "CMATC_TARGET=100"
  python -u steady_study_fixed.py

可调环境变量：
  CMATC_TARGET      目标学时，默认 80（2026-11-11 按用户要求改为启动参数）
  CMATC_DWELL_MIN   单门「单次会话」上限分钟，默认 360（超时仍继续同一门，不换课）
  CMATC_BEAT_SEC    保活节拍秒数，默认 20
  CMATC_CREDIT_EVERY 读学时/进度间隔秒，默认 300
  CMATC_NEED        课程池上限门数，默认 40（旧版 6 会导致永远只在这 6 门里打转）
  CMATC_AUTO_CHOOSE    1=学时未达标且已选课全完成时自主选课（默认），0=关闭
  CMATC_CHOOSE_BATCH   每轮最多自主选几门，默认 2
  CMATC_CHOOSE_MAX_PAGES 课程中心最多翻几页找未学过的课，默认 12
  CMATC_CHOOSE_TOTAL_MAX 本次运行自主选课总上限，默认 20
  CMATC_ROUNDS      轮数上限，0=不限
  CMATC_DIAG        1=诊断模式
  CMATC_USER        用户名，必填（无内置默认值；通过启动参数或环境变量提供）
  CMATC_SAVE_RESUME 1=保存真实续播位置（默认），0=关闭
  CMATC_APPLY_RESUME 1=重开课程时恢复到平台自己记录的真实播放秒数（默认），0=关闭
  CMATC_SEEK_UNFINISHED 1=允许未完成节点也 seek 跳过开头（默认 0=禁止，防漏学）
  CMATC_BACKFILL_MAX  每轮最多回头补播未完成节点次数，默认 2
  CMATC_STUCK_MAX     连续几次「无后续节点且进度不涨」就结束本轮，默认 3
  CMATC_DO_TESTS      1=自动完成课后自测题（默认），0=关闭
  CMATC_TEST_MAX      单会话内同一份卷最多提交次数，默认 2

※ 2026-11-08 第三轮修订（同名课程「学完又重学」）：
  同一门课在「我的课程」(enterCourse) 与「课程中心」(enterCourseTimeLimit)
  各有一条记录，旧版按 URL 去重，导致同一 cid 留两条：一条 100%、
  一条 pct=None 被当成未完成，于是反复重学已完成的课。
  现改为按 cid 合并 + 按 cid 补读进度 + 开课前复核 100% 直接跳过；
  日志用 #cid短码 区分 6 门同名课程；节点完成状态滞后时不再往回跳。

=============================================================================
2026-11-09 第四轮修订：修复《…决定》#600034 卡在 5.3%（用户日志 14:36~16:28）
=============================================================================
现象：同一门课连续重开 26 轮，平台进度恒 5.3%，日志恒
  「未等到 kjcourse 课件 iframe」「课件节点 0/6」「视频 0.0/0.0 s ready=None」
  「无视频且平台进度 5.3% 连续两次不增长，结束本轮并重新打开本门课」。

根因（对照 steady_requests.log 请求证据）：
  1) 这门课不是 kjcourse 静态 SCORM 包（旧课程视频是
     https://kjcourse-cmatc.cma.cn/2026/dangjsx/.../sco1/1.mp4），而是平台
     自带 FLV 分段播放器（pxvideo .../videoseg/*.flv + meta.json，
     cloud_updateVideoTotalTime.action 上报 00:26:27）。它的课件 frame URL
     不含 "kjcourse"，所以 frame_of(lp, "kjcourse") 恒为 None。
  2) 视频其实一直在播（请求日志每 40~55s 都有 .flv 分片 GET，
     saveVideoLearnDetailRecord.action 返回「保存成功」），但脚本的
     video_state()/beat() 只认 kjcourse，误报 no_kj_frame。
  3) 误报后走「无视频自愈」：每 3 分钟复核一次、连续两次进度不涨（约 6 分钟）
     就结束本轮重开整门课；重开后 playFirstNode() 从第一个节点 0 秒重播，
     视频最多播到第 2 个分片就被打断 -> 覆盖率永远停在 31.1% ≈ 5.3%，
     形成 26 轮死循环。learningTime 已累计 10903s 却没有任何进度。

本轮改动（全部只改"看得见/守得住"，不伪造任何计时或完成状态）：
  * 新增 video_frames()/video_frame()：遍历所有 frame，按 DOM 里有没有
    <video> 定位播放器，兼容 kjcourse 静态包与 FLV 分段播放器；
    beat / video_state / wait_sco_frame / 断点恢复全部改用它。
  * 保活会对【所有】含 video 的 frame 静音 + play()，
    只在主视频 frame 上点一次「开始学习/继续观看」遮罩。
  * 「读不到视频」不再 6 分钟就重开：新增 CMATC_NOVIDEO_GRACE_MIN（默认 20
    分钟）观察窗口，且必须同时满足平台进度连续不涨才允许重开课程。
  * 播完判定加双重确认 + 时长>=120s 门槛：FLV 分段播放器的 duration 可能
    是已缓冲分片长度，避免把「分片边界」误判成节点播完而跳节点。
  * 视频停滞跳节点阈值 5 分钟 -> 10 分钟，给慢热/缓冲留足时间。

=============================================================================
2026-11-09 第五轮修订：课程数/完成数统计与浏览器不符
=============================================================================
现象（用户日志 20:57）：浏览器「共选 24 门 / 已完成 15 / 未完成 9」，
脚本却报「课程中心 20 门 / 最终课程池 22 门 / 未完成池 19 门」，
并开始重学一门已经 100% 的课程（#1f0c11 断点 119s 但平台进度 0%）。

只读实测证据（_diag_courses.py，2026-11-09 21:0x）：
  * 「我的课程」myCourse.action 实际渲染 myCourseTheme.action，
    每页 12 门、共 2 页 = 24 门；第 1 页 3 门 100% + 9 门 0%，
    第 2 页 12 门全部 100% -> 15 门已完成 / 9 门未完成。
  * 平台接口 POST /u/study/queryLearningProgress.json
    （page.searchItem.openCourseIds=逗号分隔 openId）返回 24 条：
    15 条 progress=100 且 finishDate 非空、9 条 progress=0，
    与浏览器完全一致 —— 它是权威进度源。
  * 旧 collect_from_mycourse 只读第 1 页；课程中心 20 门卡片不显示
    「学习进度」，pct 恒 None；按 cid 补读只在当前页 DOM 找（0/10 门读到）；
    主循环把 pct=None 一律算未完成 -> 19 门。

本轮改动：
  * PARSE_ARGS_JS 额外解析 openId（enterCourse 的 args[4] /
    enterCourseTimeLimit 的 args[3]）。
  * collect_from_mycourse 调页面自身 changePage() 翻完所有分页。
  * 新增 fetch_progress_map()：按 openId 批量读平台权威进度；
    read_progress() 改为接口优先、DOM 兜底，不再受分页影响。
  * build_course_pool 以「我的课程」全分页为唯一清单来源；课程中心
    只补 openId/名称，独有卡片必须接口确认已选才补入；显式输出
    「已选 / 已完成 / 未完成 / 进度未知」四项统计。
  * 主循环只有「平台明确返回 <100%」才算待学；进度未知不主动学习，
    避免重学已完成课程。
  * 用户补充「我的自选课上有未完成，不用从全部中筛选」后再次调整：
    新增 collect_unfinished_tab() 点「未完成」标签，用平台筛出的 9 门
    作为唯一待学清单（todo 标记）；「全部」全分页只保留作总数统计与
    openId 映射，已完成的课根本不进待学池。筛选失败才回退按进度判断。
  * 新增 DRY 只读模式（CMATC_DRY=1 / run_steady.bat 密码 dry）：
    只统计不学习、不选课、不写任何平台数据。旧 bat 只认 diag，
    用户传 dry 会被静默忽略而直接开始正式挂机。

=============================================================================
2026-11-10 第七轮修订：一门 2 学时的课学 6 小时，卡在 98.9%
=============================================================================
现象（用户日志 2026-11-09 21:56 ~ 11-10 05:53）：《坚持全面从严治党》
#1f0c11 分上/中/下 3 节；第 2、3 节学完，第 1 节始终未完成，
平台进度 98.4% -> 98.9% 后再也不涨，剩余 1.1% 由用户手工补学。
日志里 23:21 之后每隔约 2 分钟重复一次：
  「视频播完已连续 2 次确认（t=928/928）」->「allDone: True」
  ->「平台进度仅 98.9%，继续学本门（不重播已完成节点）」，共约 6.5 小时。

根因（逐条有日志/请求证据）：
  1) 21:56:27 「恢复播放位置 | 平台断点 videoTime=178s | 当前 1.5s/1915s」
     —— apply_platform_resume 把【未完成】的第 1 节从 0 直接 seek 到 178s，
     0~178s 从未真实播放。平台按真实播放轨迹/分段记录判定节点完成
     （saveVideoLearnDetailRecord.action 同时上报「节点学习时长和完成状态」），
     这段缺口使第 1 节 completestate 恒为 0，课程进度永远差一点。
  2) NEXT_NODE_JS 只从「当前节点之后」找未完成节点。平台停在最后一节时，
     前面第 1 节再没完成，它也返回 allDone=True 且不点任何节点；
     旧主循环在这个分支只打印一行日志就继续，视频停在 t=928/928
     反复判「播完」，既没有回头补播，也没有退出条件 -> 无限空转。
  3) resume_to_unfinished_node 的「保持平台定位不往回跳」规则，
     使重开课程后平台仍停在最后一节时也无法回到第 1 节，重启亦补不回。

本轮改动：
  * apply_platform_resume：当前节点 completestate != 1 且断点 >30s 时
    不恢复断点，从 0 秒真实播放（CMATC_SEEK_UNFINISHED=1 可恢复旧行为）。
  * 新增 click_first_unfinished_node()：从 0 号节点开始找真正的未完成
    节点，点回它并把 currentTime 归零，从头真实播放（不快进、不改速率）。
  * 主循环 allDone 且平台 <100% 时：先回头补播（最多 CMATC_BACKFILL_MAX
    次）；补不动或菜单全完成时累计无进展次数，达到 CMATC_STUCK_MAX 就
    结束本轮重新打开本门课核对，绝不无限空转。
  * resume_to_unfinished_node：当前节点已播完且前面还有未完成节点时，
    允许回跳补播；节点正在播放时仍保持平台定位，避免误打断。
  * 片尾断点仍写 dur-120（防恢复片尾死循环），本轮未改。

=============================================================================
2026-11-10 第八轮修订：目标 100 学时 + 课后自测题
=============================================================================
  * CMATC_TARGET 默认 80 -> 100（启动器提示同步更新）。
  * 有些课程在课件菜单里带 itemtype="test" 的「自测（无分数要求）」节点，
    没有 <video>；旧脚本只打印「未读到 <video>」并空等 20 分钟观察窗，
    不做题则平台进度永远补不满 100%。
  * 实测 DOM：#current_allNum=题目数；questionInput_i 分别是
    单选 radio(A-D) / 多选 checkbox(A-D) / 判断 radio(T-F)；
    平台 handSubmit() 拼 myAnswers 并提交到
    coursewareTest_handSubmitPaperToResult.action，跳回成绩页。
  * 新增 do_test_task()：每 60s 检查，试卷页 -> 逐题作答并调用平台自带
    handSubmit(false) 提交；成绩页 -> 已有成绩视为完成（不点不可逆的
    「确定成绩查看答案」）；平台仍 <100% 时最多重做 CMATC_TEST_MAX 次
    （平台取历次最高分，不掉分）。
  * 只有「当前选中节点就是 test」才点菜单重载，绝不从别处主动跳过去：
    PDF/网页课件同样没有 <video>，误跳会打断按在线时长计进度的节点。
    自测页不进入「无视频 20 分钟观察窗」，连续 5 个节拍仍无进展才交回
    通用逻辑，避免无限空转。
  * 不伪造分数、不查答案、不改学时、不写完成状态，只走平台自己的提交接口。

2026-11-11 第九轮修订：学时未达标时自主选课 + 启动参数化
  * 用户场景：已选 30 门课全部 100%，学时仍 96.0/100.0，旧版直接退出。
  * 实测（_diag_choose.py / _diag_choose_api.py）：课程中心共 171 页、
    每页 20 门；已选课「开始学习」(enterCourseTimeLimit)，未选课
    「立即选课」(chooseCourseTimeLimit('<openId>','<timeLimitFlag>'))。
    平台自己的选课函数 POST /u/study/saveCourses.json，
    data={opt:'3','entity.itemIds':openId}，成功判定
    txt.page.items[0].success === '1'（旧版只查 "success" 字样会误判失败）。
  * 新增 auto_choose_courses()：全部已选课 100% 且学时 < 目标时触发，
    按 courseId / openId / 完整课程名 /持久化 studied_courses.json 三重排除
    「已经学过的课程」；每轮至多 2 门、累计上限 20 门；连续 3 轮选课后
    学时仍不涨且无待学课程即停止，杜绝无限选课；DRY 只输出规划不提交。
  * 旧版「课程池 < 6 门就 HTTP 乱选课」逻辑已彻底移除（不区分是否已学过）。
  * 账号 / 密码 / 目标学时做成启动参数，默认目标改回 80 学时；
    优先级 命令行 > 环境变量 > 默认值，兼容旧 bat 用法。

停止：在脚本目录创建 stop_steady.flag 文件（脚本每轮检查，会先关闭学习页再退出）。

※ 平台为单点登录，本脚本登录会踢掉其他会话：启动前请先停掉
  auto_study.py / fast_study.py / fast_study_v2.py。
※ 本脚本不修改任何现有文件，不结束任何进程。
"""
import os, re, sys, time, json, datetime, traceback, contextlib, argparse, hashlib
from playwright.sync_api import sync_playwright


def _startup_args():
    """启动参数：账号 / 密码 / 目标学时。

    2026-11-11 第九轮：按用户要求把三者做成启动参数，目标学时默认 80。
    优先级：命令行 > 环境变量 > 默认值。必须在 import common 之前把值写回
    os.environ —— common.USER / common.PWD 在模块导入时就从环境变量取值。

    支持（可混用）：
      python -u steady_study_fixed.py --user U --pwd P --target 100 [--diag|--dry]
      python -u steady_study_fixed.py U P 100 [dry|diag]      # 位置参数
      python -u steady_study_fixed.py P [dry|diag]            # 兼容旧用法
    """
    ap = argparse.ArgumentParser(add_help=True, description="稳态挂机：账号/密码/目标学时")
    ap.add_argument("--user", "-u", default=None, help="登录账号")
    ap.add_argument("--pwd", "-p", "--password", dest="pwd", default=None, help="登录密码")
    ap.add_argument("--target", "-t", default=None, help="目标学时，默认 80")
    ap.add_argument("--diag", action="store_true", help="诊断模式（只跑一门）")
    ap.add_argument("--dry", action="store_true", help="只读统计模式（不学习、不选课）")
    ap.add_argument("pos", nargs="*", help="兼容位置参数 USER PWD [TARGET] [diag|dry]")
    ns, _unknown = ap.parse_known_args()
    user, pwd, target = ns.user, ns.pwd, ns.target
    mode = "diag" if ns.diag else ("dry" if ns.dry else "")
    rest = list(ns.pos or [])
    if rest and rest[-1].lower() in ("diag", "dry"):
        mode = rest.pop().lower()
    if len(rest) >= 2:
        user = user or rest[0]
        pwd = pwd or rest[1]
        if len(rest) >= 3 and target in (None, ""):
            target = rest[2]
    elif len(rest) == 1:
        # 兼容旧用法：唯一的位置参数是密码，账号用平台默认值
        pwd = pwd or rest[0]

    if user:
        os.environ["CMATC_USER"] = user
    if pwd:
        os.environ["CMATC_PWD"] = pwd
    if target not in (None, ""):
        try:
            float(target)
            os.environ["CMATC_TARGET"] = str(target)
        except (TypeError, ValueError):
            print("[warn] 目标学时不是数字，已忽略: %r" % target, flush=True)
    if mode == "diag":
        os.environ["CMATC_DIAG"] = "1"
    if mode == "dry":
        os.environ["CMATC_DRY"] = "1"
    return {"user": user, "pwd": pwd, "target": target, "mode": mode}


STARTUP = _startup_args()

from common import EDGE, HOST, OUT, USER, PWD, ARGS, login

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
# 2026-11-11 第九轮：目标学时改回默认 80，且可用 --target / CMATC_TARGET 指定。
TARGET = float(os.environ.get("CMATC_TARGET", "80"))
# 单门「单次会话」上限：只用于防止单个学习页无限死等；超时后主循环会用
# sticky 重新打开【同一门】继续，绝不因此换下一门。
DWELL_MIN = float(os.environ.get("CMATC_DWELL_MIN", "360"))
BEAT_SEC = int(os.environ.get("CMATC_BEAT_SEC", "20"))
CREDIT_EVERY = int(os.environ.get("CMATC_CREDIT_EVERY", "300"))
# 旧版 NEED=6 + seen 轮转，学完 6 门清空 seen 后又回到同样 6 门，
# 结果就是用户看到的「6 门课每门都没到 100%」。改为覆盖全部课程。
NEED = int(os.environ.get("CMATC_NEED", "40"))
# 【已废弃】旧版「课程池少于 6 门就 HTTP 乱选课」的阈值。2026-11-11 起
# 不再在 build_course_pool 里自动选课（它不区分是否已学过）；自主选课统一
# 由主循环在「已选课程全部 100% 且学时未达标」时触发，见 AUTO_CHOOSE。
AUTO_CHOOSE_MIN = int(os.environ.get("CMATC_AUTO_CHOOSE_MIN", "6"))
# 2026-11-11 第九轮：学时未达标时自主选课。
#   CMATC_AUTO_CHOOSE=0 关闭；CMATC_CHOOSE_BATCH 每轮最多选几门；
#   CMATC_CHOOSE_MAX_PAGES 课程中心最多翻几页找未学过的课；
#   CMATC_CHOOSE_TOTAL_MAX 整个运行最多自主选几门（兜底，防无限选课）。
AUTO_CHOOSE = os.environ.get("CMATC_AUTO_CHOOSE", "1") == "1"
CHOOSE_BATCH = max(1, int(os.environ.get("CMATC_CHOOSE_BATCH", "2")))
CHOOSE_MAX_PAGES = max(1, int(os.environ.get("CMATC_CHOOSE_MAX_PAGES", "12")))
CHOOSE_TOTAL_MAX = max(1, int(os.environ.get("CMATC_CHOOSE_TOTAL_MAX", "20")))
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
# 2026-11-09 修复：读不到 <video> 时至少观察这么久，才允许重开整门课。
# 旧版 3 分钟 x 2 次就重开，26 分钟的一个节点根本来不及播完就被打回 0 秒。
# 只有同时满足「超过观察窗口」+「平台进度连续两次不涨」才会重开。
NOVIDEO_GRACE_MIN = float(os.environ.get("CMATC_NOVIDEO_GRACE_MIN", "20"))
# 2026-11-10 第七轮：课程卡在 98.9% 空转 6 小时的两个修复开关。
#   * 未完成节点不允许 seek 跳过开头（跳过的前 N 秒永远没有真实播放轨迹，
#     平台据此判该节点「未完成」，课程进度就差最后一点永远到不了 100%）；
#   * 平台停在末节点但前面还有未完成节点时，必须回头补播；实在补不动
#     也要在 N 次内结束本轮重新核对，绝不无限空转。
SEEK_UNFINISHED = os.environ.get("CMATC_SEEK_UNFINISHED", "0") == "1"
BACKFILL_MAX = int(os.environ.get("CMATC_BACKFILL_MAX", "2"))
STUCK_MAX = int(os.environ.get("CMATC_STUCK_MAX", "3"))
# 2026-11-10 第八轮：课后自测题（无分数要求）。默认开启，做题计入进度。
#   CMATC_DO_TESTS=0 可关闭；CMATC_TEST_MAX 是单个会话里同一份卷最多提交次数
#   （平台取历次最高分，重交不会把已有高分改低）。
TEST_ENABLED = os.environ.get("CMATC_DO_TESTS", "1") == "1"
TEST_MAX = int(os.environ.get("CMATC_TEST_MAX", "2"))
# 2026-11-09 第五轮：DRY = 只读统计课程池（不打开学习页、不选课、不写任何数据）
DRY = os.environ.get("CMATC_DRY", "0") == "1"
# 「我的课程」每页 12 门，允许翻的最大页数（防止分页逻辑异常时无限循环）
MAX_COURSE_PAGES = int(os.environ.get("CMATC_MAX_COURSE_PAGES", "12"))
# cid -> openId 映射，由 build_course_pool 填充；read_progress 用它查平台权威进度
CID_OPENID = {}

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
# 持久化「已学过 / 已自主选过」的课程，跨重启也能避免重复选课。
# 账号已是启动参数，历史必须按账号隔离：换账号不能继承别人学过的清单。
# 文件名只放账号哈希，避免真实账号出现在文件名里（也避免被误传仓库）。
_STUDIED_USER = hashlib.sha256(str(USER or "default").encode("utf-8")).hexdigest()[:12]
STUDIED_LOG = os.path.join(OUT, "studied_courses_%s.json" % _STUDIED_USER)
# 兼容旧版本以明文账号命名的历史文件（只读取，不再写入）。
_STUDIED_PLAIN = re.sub(r"[^A-Za-z0-9_.-]", "_", str(USER or "default"))
STUDIED_PLAIN_LOG = os.path.join(OUT, "studied_courses_%s.json" % _STUDIED_PLAIN)
STUDIED_LEGACY_LOG = os.path.join(OUT, "studied_courses.json")

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

# 当前选中的课件节点是否已完成。用于判断「平台断点能不能跳」：
# 未完成节点一律从头真实播放，绝不跳过开头。
CUR_NODE_DONE_JS = r"""() => {
    const p = document.querySelector('.s_point.s_pointerct');
    if (!p) return null;
    return {id: (p.id || '').replace('s_point_', ''),
            done: (p.getAttribute('completestate') || '0') === '1'};
}"""

# 回头补播时把播放位置归零（不是快进，是从头真实重播）。
# SEEK_RESUME_JS 有「target-before<15 就跳过」的防抖，不能用来归零。
REPLAY_ZERO_JS = r"""() => {
    const vs = [...document.querySelectorAll('video')];
    if (!vs.length) return {ok:false, reason:'no_video'};
    const v = vs[0];
    try {
        v.currentTime = 0;
        if (v.paused) { try { v.play(); } catch(e) {} }
    } catch(e) { return {ok:false, reason:String(e).slice(0,80)}; }
    return {ok:true, t:Math.round(v.currentTime || 0),
            dur:Math.round(v.duration || 0)};
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


# 平台自己给「我的课程」页用的进度查询接口（只读，POST 同域 JSON）。
# 返回 progressList: [{openId, progress, score, finishDate}, ...]
# 2026-11-09 实测：传 24 个已选 openId 返回 24 条，其中 15 条 progress=100
# 且 finishDate 非空、9 条 progress=0 —— 与浏览器「已完成 15/未完成 9」完全一致。
# 旧版只解析「我的课程」第 1 页 DOM 的「学习进度：xx%」，第 2 页 12 门
# 已完成的课永远读不到，于是被当成未完成反复重学。
PROGRESS_API_JS = r"""async (ids) => {
    const body = new URLSearchParams();
    body.append('page.searchItem.openCourseIds', ids.join(','));
    const r = await fetch('/u/study/queryLearningProgress.json', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                  'X-Requested-With': 'XMLHttpRequest'},
        body: body.toString(), credentials: 'same-origin'
    });
    return {status: r.status, body: (await r.text()).slice(0, 200000)};
}"""


def fetch_progress_map(pg, oids):
    """按 openId 批量读平台权威进度，返回 {openId: float(progress)}。

    只读查询，不写任何学习记录。分批避免请求体过长；读不到返回空字典，
    由调用方决定是否回退到 DOM 解析（绝不猜 0%、更不猜 100%）。
    """
    ids = [x for x in dict.fromkeys([o for o in oids if o])]
    out = {}
    for i in range(0, len(ids), 40):
        try:
            r = pg.evaluate(PROGRESS_API_JS, ids[i:i + 40])
            data = json.loads(r.get("body") or "{}")
            for x in (data.get("progressList") or []):
                oid = x.get("openId")
                if not oid:
                    continue
                try:
                    out[oid] = float(x.get("progress") or 0)
                except (TypeError, ValueError):
                    pass
        except Exception as e:
            log("  [warn] 平台进度接口异常: %s" % str(e)[:110])
    return out


def read_progress(pg, cid):
    """读【当前这门课】的平台进度%。

    2026-11-09 修复：优先用 queryLearningProgress.json 按 openId 精确查，
    不受「我的课程」分页影响（该页每页 12 门、共 2 页，旧版只读第 1 页）。
    DOM 解析仅作兜底；仍读不到返回 None（不猜、不误判）。
    """
    if not cid:
        return None
    oid = CID_OPENID.get(cid)
    if oid:
        pmap = fetch_progress_map(pg, [oid])
        if oid in pmap:
            return pmap[oid]
    for i in range(2):
        try:
            v = pg.evaluate(PROGRESS_BY_CID_JS, cid)
            if v is not None:
                return v
        except Exception:
            pass
        if i < 1:
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
        # 平台停在末节点、该节点视频已播完，而前面还有未完成节点时，
        # 说明平台正停在片尾空转（2026-11-09 23:21~11-10 05:53 的
        # 98.9% 就是这种状态）。此时必须回跳补播，不能沿用
        # 「保持平台定位不往回跳」，否则连重启都补不回第 1 节。
        st = video_state(lp)
        dur, tnow = st.get("dur") or 0, st.get("t") or 0
        at_end = bool(st.get("ended")) or (dur > 60 and tnow >= dur - 3)
        if first < cur and at_end:
            log("  [%s] 断点续学：平台停在第 %s 个节点且已播完，"
                "第 %s 个节点仍未完成；回跳补播（不再保持片尾定位）"
                % (tag, cur + 1, first + 1))
        else:
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
    # 【2026-11-10 修复】未完成节点绝不允许 seek 跳过开头。
    # 日志实证（21:56:27）：第 1 节被从 1.5s 直接恢复到 178s，0~178s
    # 从未真实播放；三节中只有第 1 节 completestate 恒为 0，课程卡
    # 98.9% 空转 6 小时，最后靠人工补学那 1.1% 才 100%。
    # 平台按真实播放轨迹/分段记录判定节点完成，跳过的段是永久缺口。
    if not SEEK_UNFINISHED:
        cur_state = None
        try:
            cur_state = mf.evaluate(CUR_NODE_DONE_JS)
        except Exception:
            pass
        if cur_state and cur_state.get("done") is False and vt > 30:
            log("  [%s] 当前节点 %s 未完成，平台断点 %ss 会跳过开头；"
                "为保证节点完成率，本次不恢复断点，从 0 秒真实播放"
                % (tag, (cur_state.get("id") or "-")[:12], int(vt)))
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
    kj = video_frame(lp)
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
    """日志用：平台卡片完整标题 + #cid短码 + 平台进度%。

    2026-11-09：标题取自「我的自选课」卡片的 title 属性（完整名，
    浏览器列宽截断显示的「…」已去掉）。有两门课同名，故必须带 cid
    短码才能与浏览器逐条对照、也才能区分到底在学哪一门。
    """
    cid = c.get("cid") or ""
    short = cid[-6:] if cid else (c.get("url") or "")[-6:]
    name = (c.get("name") or ("课程" + short)).strip().rstrip(".。… ")
    label = ("%s#%s" % (name, short)) if short else name
    pct = c.get("pct")
    if pct is None:
        return label + " [进度未知]"
    return "%s [%s%%]" % (label, ("%g" % pct) if isinstance(pct, (int, float)) else pct)


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

    // 【2026-11-09 名称修复】浏览器「我的自选课」里每门课的真实标题在
    // 该卡片自己的 <div class="title" title="完整标题" onclick="seeCourse('cid',...)">
    // 上；可见文本因列宽被截成「…」，title 属性才是完整标题。
    // 旧版从按钮向上爬 6 层再做 querySelector('[title]')，爬到了整个
    // #courseList 列表容器，取到的恒是其中一张卡片的标题，于是 24 门课
    // 在日志里全显示《中共中央关于…决定》，根本无法与浏览器对照。
    // 现在先按 cid 建立「本卡片标题」映射，卡片名只按 cid 取，绝不串课。
    const nameByCid = {}, sureName = {}, softName = {};
    const clean = (raw) => String(raw || '').replace(/\s+/g, ' ').trim()
                          .replace(/[.。…]+$/, '').trim();
    // title 属性 = 平台存的完整标题，最高优先级（浏览器可见文本被截断）。
    const putTitle = (cid, raw) => {
        const t = clean(raw);
        if (cid && t.length >= 4 && !NOISE.test(t)) sureName[cid] = t;
    };
    // 元素文本只在没有 title 时用，且必须滤掉「2学时 上次学习此课程」
    // 这类卡片浮层文字（比课程名更长，旧逻辑会被它抢走）。
    const putText = (cid, raw) => {
        const t = clean(raw);
        if (!cid || t.length < 4 || NOISE.test(t)) return;
        if (/学时|学习进度|开始学习|查看详情|上次学习|已完成|选课|\d+人/.test(t)) return;
        if (t.length > (softName[cid] || '').length) softName[cid] = t;
    };
    document.querySelectorAll('[onclick*="seeCourse"], [onclick*="openResourceByIp"]').forEach(e => {
        const oc = e.getAttribute('onclick') || '';
        const m = oc.match(/['"]([0-9a-zA-Z]{16,})['"]/);
        if (!m) return;
        const cid = m[1];
        putTitle(cid, e.getAttribute('title') || '');
        putText(cid, e.textContent || '');
        const card = e.closest('li.cell, div.card, div.card-wrap') || e.parentElement;
        if (card) {
            const t = card.querySelector('.title[title], [class*="title"][title]');
            if (t) { putTitle(cid, t.getAttribute('title') || ''); putText(cid, t.textContent || ''); }
        }
    });
    for (const k in sureName) nameByCid[k] = sureName[k];
    for (const k in softName) if (!nameByCid[k]) nameByCid[k] = softName[k];

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

        // 课程名：严格按本按钮自己的 cid 从「本卡片标题」映射取。
        // 这样两门同名课（如「坚持制度治党、依规治党」）也能靠 cid 短码区分，
        // 且日志显示的是 title 属性里的完整标题，不再带列宽截断的「…」。
        let name = nameByCid[cid] || '';
        const card = a.closest('li.cell, div.card, div.card-wrap');
        if (!name && card) {
            const t = card.querySelector('.title[title], [class*="title"][title]');
            if (t) name = (t.getAttribute('title') || t.textContent || '').trim()
                          .replace(/\s+/g, ' ').replace(/[.。…]+$/, '').trim();
        }
        if (!name && card) {
            const parts = (card.innerText || '').split(/\n+/).map(s => s.trim()).filter(Boolean);
            const cand = parts.filter(s => !NOISE.test(s) &&
                /[\u4e00-\u9fa5]/.test(s) && s.length >= 4);
            if (cand.length) name = cand.sort((x, y) => y.length - x.length)[0];
        }
        // openId：平台 queryLearningProgress.json 用的课程实例 ID。
        // enterCourse(url, cid, '1', '', openId, '')        -> args[4]
        // enterCourseTimeLimit(url, cid, '', openId, '')   -> args[3]
        // 统一规则：args[1:] 里第一个「32位 hex 且不是 cid」的实参。
        let oid = '';
        for (let i = 1; i < args.length; i++) {
            const v = args[i] || '';
            if (/^[0-9a-fA-F]{24,40}$/.test(v) && v !== cid) { oid = v; break; }
        }
        out.push({fn: fnName, args: args, text: (a.textContent||'').trim().slice(0,20),
                  url: url, cid: cid, oid: oid, name: name.slice(0, 80), pct: pct});
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


# 「我的课程」页的分页 JS 写在 href="javascript:changePage('1','12')" 里
# （不是 onclick），点击「下一页」链接本身没有 onclick。实测调用
# changePage('2','12') 后等 3 秒即可拿到第 2 页 12 门课。
MYCOURSE_NEXT_JS = r"""() => {
    let m = null;
    for (const a of document.querySelectorAll('a')) {
        const s = (a.getAttribute('href') || '') + ' ' + (a.getAttribute('onclick') || '');
        m = s.match(/changePage\(\s*'([^']*)'\s*,\s*'([^']*)'\s*\)/);
        if (m) break;
    }
    if (!m || typeof window.changePage !== 'function') return 'NO_NEXT';
    const cur = parseInt(m[1], 10) || 1;
    try {
        window.changePage(String(cur + 1), m[2]);
        return 'PAGE' + (cur + 1);
    } catch (e) {
        return 'ERR:' + String(e).slice(0, 80);
    }
}"""


# 「我的自选课」页的 全部/未完成/已完成 筛选标签（<a class="tabs-link">）。
# 2026-11-09 实测：点「未完成」后页面直接列出 9 门待学课且无分页；
# 点「已完成」列出 15 门（2 页）。由平台自己判定完成状态，最权威。
MYCOURSE_TAB_JS = r"""(t) => {
    const es = [...document.querySelectorAll('a,li,span,button')]
        .filter(e => (e.textContent || '').trim() === t);
    const e = es.find(x => x.tagName === 'A' && /tabs-link/.test(x.className || ''))
              || es[es.length - 1];
    if (!e) return 'NOT_FOUND';
    e.click();
    return 'CLICKED ' + e.tagName + '.' + (e.className || '');
}"""


def _collect_pages(pg, label):
    """翻完当前筛选视图的所有分页，收集 enterCourse 卡片。"""
    items, seen, pages = [], set(), 0
    for page_no in range(1, MAX_COURSE_PAGES + 1):
        try:
            cur = pg.evaluate(PARSE_ARGS_JS, "enterCourse")
        except Exception as e:
            log("  %s 第 %d 页解析异常: %s" % (label, page_no, str(e)[:90]))
            break
        pages = page_no
        for c in cur:
            if c.get("cid"):
                seen.add(c["cid"])
            items.append(c)
        log("  %s 第 %d 页: %d 门（累计 %d 门）" % (label, page_no, len(cur), len(seen)))

        try:
            r = pg.evaluate(MYCOURSE_NEXT_JS)
        except Exception as e:
            r = "ERR:" + str(e)[:70]
        if r == "NO_NEXT" or r.startswith("ERR:"):
            # jQuery 事件绑定的「下一页」没有 onclick；点一下试试。
            # 「未完成」筛选只有 9 门、无分页，页面也没有该链接 -> 立即收工。
            try:
                clicked = pg.evaluate("""() => {
                    const a = [...document.querySelectorAll('a')]
                        .find(x => (x.textContent || '').trim() === '下一页');
                    if (a) { a.click(); return true; }
                    return false;
                }""")
            except Exception:
                clicked = False
            if not clicked:
                break
            pg.wait_for_timeout(3000)
            try:
                nxt = pg.evaluate(PARSE_ARGS_JS, "enterCourse")
            except Exception:
                nxt = []
            if not any(c.get("cid") and c["cid"] not in seen for c in nxt):
                break
            continue
        log("  %s 翻页: %s" % (label, r))
        # changePage 走 AJAX 重渲染，实测 3s 偶尔不够。确实还有下一页时
        # 最多等 3 次；已在末页 / 无分页文本的视图（如「未完成」9 门）
        # 只等 1 次就收工，避免每轮白等 10 秒。
        try:
            total_pages = pg.evaluate("""() => {
                const m = (document.body.innerText || '').match(/共\s*(\d+)\s*页/);
                return m ? parseInt(m[1], 10) : 0;
            }""")
        except Exception:
            total_pages = 0
        retries = 3 if total_pages > page_no else 1
        fresh = set()
        for _ in range(retries):
            pg.wait_for_timeout(3500)
            try:
                nxt = pg.evaluate(PARSE_ARGS_JS, "enterCourse")
            except Exception:
                nxt = []
            fresh = set(c.get("cid") for c in nxt if c.get("cid")) - seen
            if fresh:
                break
        if not fresh:
            break
    log("  %s: 共 %d 页 / %d 门（去重后 %d 门）" % (label, pages, len(items), len(seen)))
    return items


def collect_from_mycourse(pg):
    """「全部」视图全分页：用于统计已选总数、补全 cid -> openId 映射。

    2026-11-09 修复：该页每页 12 门、共 2 页（24 门），旧版只读第 1 页，
    第 2 页 12 门已 100% 的课全漏掉，是「19 门未完成」虚高的主因之一。
    【待学清单不再从这里按百分比挑】—— 改用「未完成」筛选，见下。
    """
    nav(pg, MY_COURSE_URL, wait=5000)
    return _collect_pages(pg, "我的课程(全部)")


def collect_unfinished_tab(pg):
    """【待学清单首选】点「未完成」标签，直接用平台筛出的课程。

    用户 2026-11-09 指出：我的自选课自带「未完成」筛选，不用从「全部」
    里再按进度挑。实测该视图列出 9 门、无分页，且已完成的课程根本不出现，
    从源头杜绝「学完又重学」。
    """
    nav(pg, MY_COURSE_URL, wait=5000)
    r = pg.evaluate(MYCOURSE_TAB_JS, "未完成")
    log("  我的自选课「未完成」筛选: %s" % r)
    pg.wait_for_timeout(3000)
    return _collect_pages(pg, "我的课程(未完成)")


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


# ---------------------------------------------------------------------------
# 2026-11-11 第九轮：学时未达标时自主选课（严格排除已学过的课程）
# ---------------------------------------------------------------------------
# 实测（_diag_choose.py / _diag_choose_api.py）：
#   * 课程中心 courseMarketNew.htm 共 171 页、每页 20 门；已选课显示
#     「开始学习」(enterCourseTimeLimit)，未选课显示「立即选课」
#     (chooseCourseTimeLimit('<openId>','<timeLimitFlag>'))。
#   * 按钮参数是 openId（不是 courseId），与 enter 卡片的 args[3] 同命名空间。
#   * 平台自己的选课函数最终 POST /u/study/saveCourses.json，
#     data = {opt:'3', 'entity.itemIds': openId}，
#     成功判定 txt.page.items[0].success === '1'（旧版只看响应里有没有
#     "success" 字样，会把失败误判成成功）。
CHOOSE_CANDIDATES_JS = r"""() => {
    const clean = s => String(s || '').replace(/\s+/g, ' ').trim()
                        .replace(/[.。…]+$/, '').trim();
    const choose = [], enterIds = [];
    const argsOf = oc => {
        const body = (oc.match(/\(([\s\S]*)\)/) || [])[1] || '';
        return [...body.matchAll(/'([^']*)'|"([^"]*)"/g)]
               .map(x => x[1] !== undefined ? x[1] : x[2]);
    };
    document.querySelectorAll('a[onclick*="chooseCourseTimeLimit"]').forEach(a => {
        const oc = a.getAttribute('onclick') || '';
        const args = argsOf(oc);
        const openId = args[0] || '', flag = args[1] || '';
        if (!openId) return;
        let box = a;
        for (let i = 0; i < 7 && box.parentElement; i++) {
            const p = box.parentElement;
            if ((p.innerText || '').length > 700) break;
            box = p;
            if (/学时/.test(p.innerText || '') && /选课|学习/.test(p.innerText || '')) break;
        }
        const card = a.closest('li.cell, div.card, div.card-wrap') || box;
        const txt = clean(card.innerText || box.innerText || '');
        const hm = txt.match(/([\d.]+)\s*学时/);
        let title = '';
        const t = card.querySelector('.title[title], [class*="title"][title]');
        if (t) title = clean(t.getAttribute('title') || t.textContent || '');
        if (!title) {
            const t2 = card.querySelector('[title]');
            if (t2) title = clean(t2.getAttribute('title') || '');
        }
        if (!title) {
            const cand = txt.split(/\n+/).map(s => s.trim()).filter(Boolean)
                .filter(s => /[\u4e00-\u9fa5A-Za-z]/.test(s) && s.length >= 4
                             && !/学时|立即选课|开始学习|查看详情|选课|\d+人/.test(s));
            if (cand.length) title = cand.sort((x, y) => y.length - x.length)[0];
        }
        let cid = '';
        const see = card.querySelector('[onclick*="seeCourse"]');
        if (see) {
            const sm = (see.getAttribute('onclick') || '').match(/['"]([0-9a-zA-Z]{16,})['"]/);
            if (sm) cid = sm[1];
        }
        choose.push({id: openId, flag: flag, cid: cid, title: title,
                     hours: hm ? parseFloat(hm[1]) : 0, text: txt.slice(0, 160)});
    });
    // 同页已选课程的 courseId / openId 也纳入排除集（多一层保险）
    document.querySelectorAll('a[onclick*="enterCourseTimeLimit"]').forEach(a => {
        const args = argsOf(a.getAttribute('onclick') || '');
        if (args[1]) enterIds.push(args[1]);
        for (const v of args.slice(2)) {
            if (/^[0-9a-fA-F]{24,40}$/.test(v)) { enterIds.push(v); break; }
        }
    });
    const mt = (document.body.innerText || '').match(/共\s*(\d+)\s*页/);
    return {choose: choose, enterIds: enterIds,
            totalPages: mt ? parseInt(mt[1], 10) : 0};
}"""

MARKET_NEXT_JS = r"""() => {
    const nx = [...document.querySelectorAll('a')]
        .find(a => (a.textContent || '').trim() === '下一页');
    if (!nx) return 'NO_NEXT';
    const href = nx.getAttribute('href') || '';
    try { nx.click(); return 'NEXT:' + href.slice(0, 60); }
    catch (e) { return 'ERR:' + String(e).slice(0, 80); }
}"""

SAVE_COURSES_JS = r"""async (ids) => {
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
                body: body.toString(), credentials: 'same-origin'
            });
            let txt = '';
            try { txt = await r.text(); } catch (e) {}
            let ok = false, msg = '';
            try {
                const j = JSON.parse(txt);
                const it = j && j.page && j.page.items && j.page.items[0];
                ok = !!(it && String(it.success) === '1');
                msg = it ? String(it.msg || it.message || it.info || '') : '';
            } catch (e) { msg = 'non_json'; }
            out.push({id: id, status: r.status, ok: ok,
                      msg: msg.slice(0, 120), raw: String(txt).slice(0, 180)});
        } catch (e) {
            out.push({id: id, ok: false, error: String(e).slice(0, 100)});
        }
    }
    return out;
}"""


def _norm_name(s):
    return re.sub(r"\s+", "", str(s or "")).replace("…", "").strip()


def _studied_read_path():
    """新哈希文件不存在时，依次读旧明文账号文件、旧通用文件（自动迁移，不丢历史）。"""
    if os.path.exists(STUDIED_LOG):
        return STUDIED_LOG
    for old in (STUDIED_PLAIN_LOG, STUDIED_LEGACY_LOG):
        if old != STUDIED_LOG and os.path.exists(old):
            return old
    return STUDIED_LOG


def load_studied():
    d = {"cids": [], "names": [], "openIds": [], "chosen": []}
    try:
        with open(_studied_read_path(), encoding="utf-8") as f:
            x = json.load(f)
        for k in ("cids", "names", "openIds"):
            v = x.get(k, [])
            if isinstance(v, list):
                d[k] = [str(i) for i in v if i]
        v = x.get("chosen", [])
        if isinstance(v, list):
            d["chosen"] = [i for i in v if isinstance(i, dict)]
    except Exception:
        pass
    return d


def save_studied(d):
    try:
        d = dict(d)
        d["updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(STUDIED_LOG, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception as e:
        log("  [warn] 已学课程记录写入失败: %s" % str(e)[:90])


def record_studied(pool):
    """把本轮「我的课程」权威清单并入历史，跨重启也能避免重选已学课程。"""
    d = load_studied()
    cids, names, oids = set(d["cids"]), set(d["names"]), set(d["openIds"])
    for c in pool:
        if c.get("cid"):
            cids.add(c["cid"])
        if c.get("oid"):
            oids.add(c["oid"])
        n = _norm_name(c.get("name"))
        if len(n) >= 4:
            names.add(n)
    d.update(cids=sorted(cids), names=sorted(names), openIds=sorted(oids))
    save_studied(d)


def record_chosen(items):
    """记录自主选过的课（openId + 名称），防止失败/结算延迟导致重复选。"""
    d = load_studied()
    chosen = list(d.get("chosen") or [])
    known = set(x.get("id") for x in chosen if x.get("id"))
    oids, names = set(d["openIds"]), set(d["names"])
    for it in items:
        oid = it.get("id")
        if not oid or oid in known:
            continue
        chosen.append({"id": oid, "name": it.get("title") or "",
                       "hours": it.get("hours") or 0,
                       "at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        known.add(oid)
        oids.add(oid)
        n = _norm_name(it.get("title"))
        if len(n) >= 4:
            names.add(n)
    d.update(chosen=chosen[-200:], openIds=sorted(oids), names=sorted(names))
    save_studied(d)


def auto_choose_courses(pg, pool, credit, chosen_total=0, dry=False):
    """已选课程全部 100% 但学时未达标时，从课程中心选【没学过】的新课。

    排除（三重，任一命中即跳过）：
      1) 本轮「我的课程」池的 cid / openId / 完整课程名；
      2) 历史持久化 studied_courses.json（跨重启有效，含已自主选过的课）；
      3) 课程中心同页「开始学习」卡片的 courseId / openId。
    只走平台自己的 saveCourses.json（等价于用户点「确定要进行选课吗」），
    不伪造学时/完成状态。dry=True 只输出规划，不提交任何请求。
    返回成功选课数量（dry 时返回规划数量）。
    """
    hist = load_studied()
    known_ids = set(hist["openIds"]) | set(hist["cids"]) | set(
        x.get("id") for x in (hist["chosen"] or []) if x.get("id"))
    known_cids = set(c.get("cid") for c in pool if c.get("cid")) | set(hist["cids"])
    known_oids = set(c.get("oid") for c in pool if c.get("oid")) | set(hist["openIds"])
    known_names = set(_norm_name(c.get("name")) for c in pool) | set(hist["names"])
    for s in (known_ids, known_cids, known_oids, known_names):
        s.discard("")

    gap = max(0.0, TARGET - float(credit or 0))
    quota = min(CHOOSE_BATCH, max(0, CHOOSE_TOTAL_MAX - chosen_total))
    if quota <= 0:
        log("  自主选课已达本次运行上限 %d 门，不再选课" % CHOOSE_TOTAL_MAX)
        return 0
    log("  学时缺口 %.1f，准备自主选课（本轮至多 %d 门；累计上限 %d；历史已学 %d 门）"
        % (gap, quota, CHOOSE_TOTAL_MAX, len(known_cids)))

    try:
        nav(pg, MARKET_URL, wait=4500)
    except Exception as e:
        log("  课程中心打开异常: %s" % str(e)[:120])
        return 0

    picked, picked_ids, page_keys = [], set(), set()
    for pno in range(1, CHOOSE_MAX_PAGES + 1):
        try:
            data = pg.evaluate(CHOOSE_CANDIDATES_JS) or {}
        except Exception as e:
            log("  课程中心第 %d 页读取异常: %s" % (pno, str(e)[:100]))
            break
        for oid in data.get("enterIds") or []:
            known_ids.add(oid)
        cards = data.get("choose") or []
        key = "|".join(c.get("id") or "" for c in cards)
        if key in page_keys:
            log("  课程中心第 %d 页内容重复，停止翻页" % pno)
            break
        page_keys.add(key)
        fresh = 0
        for c in cards:
            oid = c.get("id") or ""
            nm = _norm_name(c.get("title"))
            cid = c.get("cid") or ""
            if not oid or oid in picked_ids:
                continue
            if str(c.get("flag") or "") == "closed":   # 已结束授课，平台禁止选
                continue
            if oid in known_ids or oid in known_cids or oid in known_oids:
                continue
            if cid and (cid in known_cids or cid in known_ids):
                continue
            if nm and nm in known_names:
                continue
            if not nm:                                 # 读不到名字就不冒险选
                continue
            picked.append(c)
            picked_ids.add(oid)
            fresh += 1
        log("  课程中心第 %d 页: %d 张「立即选课」卡片，%d 门未学过（累计候选 %d）"
            % (pno, len(cards), fresh, len(picked)))
        if len(picked) >= quota:
            break
        try:
            r = pg.evaluate(MARKET_NEXT_JS)
        except Exception as e:
            r = "ERR:" + str(e)[:70]
        if r == "NO_NEXT" or r.startswith("ERR:"):
            log("  课程中心翻页结束: %s" % r)
            break
        pg.wait_for_timeout(4000)

    if not picked:
        log("  课程中心前 %d 页未找到【未学过】的可选课程" % CHOOSE_MAX_PAGES)
        return 0

    # 优先挑学时最接近缺口的课，尽量一轮补齐；同分按学时大的在前。
    if gap > 0:
        picked.sort(key=lambda c: (abs((c.get("hours") or 0) - gap),
                                   -(c.get("hours") or 0)))
    plan = picked[:quota]
    log("  ---- 自主选课清单（均已排除已学课程，可与浏览器对照）----")
    for i, c in enumerate(plan, 1):
        log("    %d. %s  %s学时  openId=%s"
            % (i, c.get("title") or "(无标题)", c.get("hours") or "-",
               (c.get("id") or "")[:12]))
    if dry:
        log("  DRY 只读：以上仅为选课规划，未提交任何选课请求、未写平台数据")
        return len(plan)

    ids = [c["id"] for c in plan]
    try:
        res = pg.evaluate(SAVE_COURSES_JS, ids)
    except Exception as e:
        log("  选课请求异常: %s" % str(e)[:140])
        return 0
    by_id = {c["id"]: c for c in plan}
    ok_items, failed = [], []
    for r in (res if isinstance(res, list) else []):
        if not isinstance(r, dict):
            continue
        c = by_id.get(r.get("id")) or {}
        if r.get("ok"):
            ok_items.append(c)
            log("  选课成功: %s (%s学时)"
                % (c.get("title") or r.get("id"), c.get("hours") or "-"))
        else:
            failed.append(r)
            log("  [warn] 选课未成功: %s status=%s msg=%s raw=%s"
                % ((c.get("title") or r.get("id") or "?")[:40], r.get("status"),
                   r.get("msg") or r.get("error"), str(r.get("raw", ""))[:90]))
    if ok_items:
        record_chosen(ok_items)
        log("  自主选课完成：成功 %d 门 / 失败 %d 门；下一轮重新读取「我的课程」后开始学习"
            % (len(ok_items), len(failed)))
    return len(ok_items)


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
        if not old.get("oid") and new.get("oid"):
            old["oid"] = new["oid"]
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
    """课程池 = 「我的课程」全部分页（权威已选清单） + 平台权威进度。

    2026-11-09 第五轮修复（用户反馈：浏览器 24 门 / 已完成 15 / 未完成 9，
    脚本却报 20 门 / 19 门未完成）：
      1) 「我的课程」每页 12 门、共 2 页，旧版只读第 1 页，漏掉第 2 页
         12 门已 100% 完成的课；
      2) 「课程中心」20 门卡片不显示「学习进度」，解析出的 pct 恒 None；
      3) 按 cid 补读只在当前页 DOM 找卡片，第 2 页课程找不到 -> 0/10 门；
      4) 主循环把 pct=None 一律视为未完成 -> 19 门。
    【待学清单】按用户 2026-11-09 建议，直接取「我的自选课-未完成」筛选
    （平台自己判定，实测 9 门、无分页、不含任何已完成课程），不再从
    「全部」课程里按百分比挑。「全部」全分页只用于统计总数和补 openId。
    进度以 queryLearningProgress.json（按 openId）为准；课程中心只补
    openId/名称，绝不把「进度未知」的卡片当作待学课程。
    """
    global CID_OPENID
    pool = []
    my_items, market_items = [], []
    try:
        my_items = collect_from_mycourse(pg)
        log("  我的课程(继续学习/查看详情): %d 门"
            % len(set(c.get("cid") for c in my_items if c.get("cid"))))
        add_unique(pool, my_items)
    except Exception as e:
        log("  我的课程读取异常: %s" % str(e)[:120])
    try:
        market_items = collect_from_market(pg)
        log("  课程中心(开始学习): %d 门（仅用于补 openId/名称，不直接算待学课）"
            % len(market_items))
    except Exception as e:
        log("  课程中心读取异常: %s" % str(e)[:120])

    # 【待学清单】用户 2026-11-09 指出：我的自选课自带「未完成」筛选，
    # 不用从「全部」课程里按百分比挑。实测该视图 9 门、无分页、
    # 已完成的课程根本不出现，从源头杜绝「学完又重学」。
    tab_items = []
    try:
        tab_items = collect_unfinished_tab(pg)
    except Exception as e:
        log("  [warn] 「未完成」筛选读取异常: %s" % str(e)[:110])
    tab_cids = set(c.get("cid") for c in tab_items if c.get("cid"))
    tab_ok = bool(tab_cids)
    if tab_ok:
        log("  待学清单来源: 平台「未完成」筛选 %d 门（不从全部课程里挑选）"
            % len(tab_cids))
    else:
        log("  [warn] 「未完成」筛选为空或读取失败，回退按平台进度 <100%% 筛选")

    # cid -> openId 映射：三个来源合并，供 read_progress 全程使用
    for c in my_items + market_items + tab_items:
        cid, oid = c.get("cid"), c.get("oid")
        if cid and oid:
            CID_OPENID.setdefault(cid, oid)

    # 【名称权威来源】与浏览器「我的自选课」一致：只认该页卡片自己的
    # title 属性（完整标题）。课程中心的卡片文本常被平台硬截断，只作为
    # 缺名时的兜底，绝不覆盖「我的课程」里的标题。
    def _name_map(items):
        m = {}
        for c in items:
            cid, n = c.get("cid"), (c.get("name") or "").strip()
            if cid and n and len(n) > len(m.get(cid, "")):
                m[cid] = n
        return m

    my_name = _name_map(my_items + tab_items)
    market_name = _name_map(market_items)

    # 课程中心独有卡片：只有平台进度接口确认「已选」才补入课程池。
    # 未选课程（立即选课）/ 接口无记录的课一律不进池，避免虚增未完成数。
    have = set(c.get("cid") for c in pool)
    extra = [c for c in market_items
             if c.get("url") and c.get("cid") and c["cid"] not in have]
    if extra:
        extra_map = fetch_progress_map(pg, [c.get("oid") for c in extra])
        added = 0
        for c in extra:
            oid = c.get("oid")
            if oid and oid in extra_map:
                c["pct"] = extra_map[oid]
                add_unique(pool, [c])
                added += 1
        log("  课程中心独有 %d 门：平台确认已选 %d 门补入，其余不进入课程池"
            % (len(extra), added))
    # 「未完成」筛选里出现、但「全部」分页漏掉的课，直接补入池
    for c in tab_items:
        if c.get("url") and c.get("cid") and c["cid"] not in have:
            add_unique(pool, [c])
            have.add(c["cid"])
            log("  「未完成」筛选补入课程 %s" % (c["cid"][-6:] if c.get("cid") else "?"))

    # 2026-11-11 第九轮：旧的「课程池 < AUTO_CHOOSE_MIN 就 HTTP 直接选课」
    # 已移除。它不区分是否已学过、不看课程名，且只在列表异常变少时误触发。
    # 自主选课统一由主循环在「已选课程全部 100% 且学时未达标」时调用
    # auto_choose_courses()，严格排除已学课程（cid / openId / 名称 / 历史记录）。
    # 这里无论课程池多少门，都绝不选课。

    # 【权威进度】按 openId 批量查询，覆盖/补齐每门课的真实百分比
    oids = []
    for c in pool:
        oid = c.get("oid") or CID_OPENID.get(c.get("cid"))
        if oid:
            c["oid"] = oid
            oids.append(oid)
    pmap = fetch_progress_map(pg, oids)
    for c in pool:
        oid = c.get("oid")
        if oid and oid in pmap:
            c["pct"] = pmap[oid]
            c["pct_src"] = "api"
    log("  平台进度接口: 查询 %d 个 openId，返回 %d 门课的真实进度"
        % (len(set(oids)), len(pmap)))

    # 【待学标记】以平台「未完成」筛选为准，不从「全部」里按百分比挑；
    # 平台进度接口明确 100% 的课一律不学（防结算延迟下的重学）。
    # 2026-11-10 加固：实测「未完成」标签偶发点错（点成 "A.trans active"，
    # 读到的是「全部」第 1 页 12 门），会漏掉第 2 页真正未完成的课。
    # 这里用平台进度接口做并集兜底：接口明确 <100% 的课一律纳入待学，
    # 但绝不给「进度未知」或已 100% 的课打 todo，避免回到 19 门虚高的老问题。
    api_todo = set(c.get("cid") for c in pool
                   if c.get("cid") and c.get("pct") is not None
                   and c["pct"] < 99.9)
    if tab_ok and (api_todo - tab_cids):
        log("  [warn] 「未完成」筛选漏掉 %d 门平台明确 <100%% 的课，"
            "按平台进度补入待学: %s"
            % (len(api_todo - tab_cids),
               ", ".join((x or "?")[-6:] for x in list(api_todo - tab_cids)[:8])))
    for c in pool:
        cid, pct = c.get("cid"), c.get("pct")
        if pct is not None and pct >= 99.9:
            c["todo"] = False
        elif tab_ok:
            c["todo"] = (cid in tab_cids) or (cid in api_todo)
        else:
            c["todo"] = pct is not None and pct < 99.9

    # 【名称最终对齐】在所有 add_unique / 补入动作完成后统一覆盖，
    # 避免课程中心的截断名或旧的错误同名标题污染日志。
    for c in pool:
        n = my_name.get(c.get("cid")) or market_name.get(c.get("cid"))
        if n:
            c["name"] = n

    # DOM 兜底：接口偶发失败时，再用「我的课程」卡片文本补读（不猜数值）
    try:
        nav(pg, MY_COURSE_URL, wait=2000)
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
            log("  DOM 兜底补读进度: %d/%d 门读到" % (filled, len(missing)))
    except Exception as e:
        log("  补读进度异常: %s" % str(e)[:110])

    done = [c for c in pool if c.get("pct") is not None and c["pct"] >= 99.9]
    todo = [c for c in pool if c.get("todo")]
    unknown = [c for c in pool if c.get("pct") is None]
    log("  平台口径: 已选 %d 门 | 已完成 %d 门 | 未完成 %d 门 | 进度未知 %d 门"
        " | 待学来源=%s"
        % (len(pool), len(done), len(todo), len(unknown),
           "未完成筛选" if tab_ok else "进度兜底"))
    if unknown:
        log("  [warn] 平台未返回进度的课程，本轮不视为未完成、不主动学习: %s"
            % ", ".join((c.get("cid") or "?")[-6:] for c in unknown[:10]))

    # 排序：待学(进度降序) -> 进度未知/其它 -> 已完成(排最后，绝不重学)
    pool.sort(key=lambda c: (
        0 if c.get("todo") else
        (2 if (c.get("pct") is not None and c["pct"] >= 99.9) else 1),
        -(c.get("pct") or 0),
        not bool(c.get("name"))))
    todo_sorted = [c for c in pool if c.get("todo")]
    done_sorted = [c for c in pool if c.get("pct") is not None
                   and c["pct"] >= 99.9 and not c.get("todo")]
    tid, did = set(map(id, todo_sorted)), set(map(id, done_sorted))
    rest_sorted = [c for c in pool if id(c) not in tid and id(c) not in did]
    log("  最终课程池: %d 门 | 待学 %d 门 | 已完成 %d 门 | 其它 %d 门"
        % (len(pool), len(todo_sorted), len(done_sorted), len(rest_sorted)))
    log("  ---- 待学清单（平台「未完成」筛选，可与浏览器逐条对照）----")
    for i, c in enumerate(todo_sorted, 1):
        log("    %2d. %s  cid=%s" % (i, course_label(c), c.get("cid") or "-"))
    log("  ---- 已完成 %d 门（本轮不学）----" % len(done_sorted))
    for c in done_sorted:
        log("    · %s  cid=%s" % (course_label(c), c.get("cid") or "-"))
    if rest_sorted:
        log("  ---- 其它 %d 门（进度未知，本轮不学）----" % len(rest_sorted))
        for c in rest_sorted:
            log("    · %s  cid=%s" % (course_label(c), c.get("cid") or "-"))
    # 本轮权威已选清单并入历史，供自主选课时排除「已经学过的课程」
    record_studied(pool)
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


# ---------------------------------------------------------------------------
# 2026-11-09 第四轮修订的核心：课件播放器不再靠 URL 里的 "kjcourse" 猜。
#
# 课程 #600034 用平台自带 FLV 分段播放器（pxvideo .../videoseg/*.flv），
# 课件 frame URL 里没有 kjcourse；旧 frame_of(lp,"kjcourse") 恒为 None，
# 于是 beat()/video_state() 全程误报 no_kj_frame，主循环误以为"课件链断了"
# 每 6 分钟重开一次整门课，视频永远从第一节点 0 秒重播 -> 进度恒 5.3%。
# 改为：遍历所有 frame，按 DOM 里有没有 <video> 定位真正的播放器。
# ---------------------------------------------------------------------------
VIDEO_PROBE_JS = r"""() => {
    const vs = [...document.querySelectorAll('video')];
    if (!vs.length) return null;
    const v = vs[0];
    return {
        n: vs.length,
        t: Math.round((v.currentTime || 0) * 10) / 10,
        dur: isFinite(v.duration) ? Math.round(v.duration * 10) / 10 : 0,
        ready: v.readyState,
        paused: v.paused,
        ended: v.ended,
        hasSrc: !!(v.getAttribute('src') || v.currentSrc)
    };
}"""

# 对"非主"视频 frame 只做静音 + play()，不点任何遮罩按钮：
# 重复点「开始学习」会触发 videoPlay() 重建 <video> 并清空 src（历史 P0 坑）。
MUTE_PLAY_JS = r"""() => {
    let n = 0;
    for (const v of [...document.querySelectorAll('video')]) {
        try { v.muted = true; v.volume = 0; } catch(e) {}
        try {
            if (v.paused && !v.ended) {
                const p = v.play();
                if (p && typeof p.catch === 'function') p.catch(() => {});
                n++;
            }
        } catch(e) {}
    }
    return {played: n};
}"""


def video_frames(lp):
    """列出所有含 <video> 的 frame，按「真正在播」的优先级排序。

    返回 [(frame, probe), ...]。frame 顺序不固定、URL 也不固定，
    所以只认 DOM；跨域 iframe 由 Playwright 直接 evaluate，不受同源策略限制。
    """
    cand = []
    for f in lp.frames:
        try:
            p = f.evaluate(VIDEO_PROBE_JS)
        except Exception:
            continue
        if not p:
            continue
        u = f.url or ""
        score = 0
        if (p.get("t") or 0) > 1 or p.get("hasSrc"):
            score += 4
        if "kjcourse" in u:
            score += 2
        if (p.get("ready") or 0) >= 2:
            score += 1
        cand.append((score, f, p))
    cand.sort(key=lambda x: -x[0])
    return [(f, p) for _, f, p in cand]


def video_frame(lp):
    """主视频 frame；找不到时回退旧的 kjcourse URL 匹配（兼容老课程）。"""
    vs = video_frames(lp)
    if vs:
        return vs[0][0]
    return frame_of(lp, "kjcourse")


def click_courseware_tab(lp, tag):
    """
    【v1/v2 缺失的关键一步】
    学习页默认停在 course_detail.action（课程简介），不点「课件」就不会加载
    courseware_index.action -> content_webCourseware.action -> kjcourse iframe 链，
    v2 日志里的 no_sco_frame 正是这个原因。
    """
    if frame_of(lp, "courseware_index.action") or frame_of(lp, "kjcourse") or video_frames(lp):
        log("  [%s] 课件链已存在（菜单/视频 frame 已加载），无需点「课件」tab" % tag)
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
    """等待含 <video> 的课件 frame 出现（视频慢热，v3 实测 45s 才 readyState=2）。

    兼容两类课件：kjcourse 静态 SCORM 包 与 pxvideo FLV 分段播放器。
    不再只看 URL 里的 "kjcourse"，否则 #600034 会被误判为「课件链没加载」。
    """
    end = time.time() + timeout
    while time.time() < end:
        vs = video_frames(lp)
        if vs:
            return vs[0][0]
        tick_wait(lp, 1)
    # 兜底：老课程可能先出现 kjcourse frame、稍后才由 JS 创建 <video>。
    return frame_of(lp, "kjcourse")


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
    """一次保活：顶层确认框 + 所有含 <video> 的 frame 静音/播放/继续观看。

    全程不改播放速率、不拖进度。主视频 frame 才点一次「开始学习」遮罩，
    其余视频 frame 只静音 + play()，避免重复触发 videoPlay() 重建 <video>。
    """
    r_top, r_kj = {}, {}
    try:
        r_top = lp.evaluate(TOP_BEAT_JS)
    except Exception:
        pass
    vfs = video_frames(lp)
    if vfs:
        try:
            r_kj = vfs[0][0].evaluate(KJ_BEAT_JS)
        except Exception:
            pass
        for f, _ in vfs[1:]:
            try:
                f.evaluate(MUTE_PLAY_JS)
            except Exception:
                pass
    if verbose:
        urls = [(f.url or "")[-48:] for f, _ in vfs]
        log("  [%s] beat top=%s kj=%s video_frames=%s" % (tag, r_top, r_kj, urls))
    return r_top, r_kj


def video_state(lp):
    """读主视频 frame 的真实播放状态；附带 frameUrl 便于定位课件模板。"""
    vf = video_frame(lp)
    if vf is None:
        return {"noVideo": True, "reason": "no_video_frame", "frameUrl": None}
    furl = (vf.url or "")[:120]
    try:
        st = vf.evaluate(VIDEO_STATE_JS)
        if isinstance(st, dict):
            st["frameUrl"] = furl
        return st
    except Exception as e:
        return {"noVideo": True, "reason": str(e)[:80], "frameUrl": furl}


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


def click_first_unfinished_node(lp, tag):
    """【回头补播】点回菜单里第一个 completestate != 1 的节点，从头真实播放。

    NEXT_NODE_JS 只从「当前节点之后」找未完成节点。平台停在最后一节、
    前面还有未完成节点（第 1 节因断点 seek 跳过开头而从未计完成）时，
    它永远返回 allDone=True 且不点任何节点，脚本就停在片尾空转。
    这里从 0 号节点开始找，点回真正的未完成节点；若平台点击同一节点
    不重载课件，则把 currentTime 归零，从头真实播放。
    """
    info = node_info(lp) or {}
    first = info.get("firstUndone", -1)
    if first < 0:
        return {"ok": False, "reason": "all_menu_done", "info": info}
    mf = menu_frame(lp)
    if mf is None:
        return {"ok": False, "reason": "no_menu_frame"}
    old_src = video_state(lp).get("currentSrc") or ""
    try:
        r = mf.evaluate(CLICK_NODE_JS, first)
    except Exception as e:
        return {"ok": False, "reason": str(e)[:90]}
    log("  [%s] 回头补播：点击第 %s 个未完成节点 | %s" % (tag, first + 1, r))
    st = {}
    for _ in range(20):
        tick_wait(lp, 1)
        st = video_state(lp)
        ns = st.get("currentSrc") or ""
        if ns and ns != old_src and (st.get("ready") or 0) >= 2:
            break
    zero = None
    kj = video_frame(lp)
    if kj is not None:
        try:
            zero = kj.evaluate(REPLAY_ZERO_JS)
        except Exception as e:
            zero = {"ok": False, "reason": str(e)[:80]}
    try:
        beat(lp, tag)
    except Exception:
        pass
    return {"ok": True, "index": first, "id": r.get("id"), "zero": zero,
            "video": {"t": st.get("t"), "dur": st.get("dur"),
                      "ready": st.get("ready")}}


# ---------------------------------------------------------------------------
# 2026-11-10 第八轮：课后自测题（itemtype="test"）
#
# 实测（课程 #dc04a9「建设上下贯通、执行有力的严密组织体系」）：
#   课件菜单里第 4 个节点是 .s_point[itemtype="test"]，点开后是
#   coursewareTest_getTestInfo.action / coursewareTest_intoRedoTestPage.action，
#   没有 <video>。旧脚本遇到它只会打印「未读到 <video>，继续观察」，
#   20 分钟观察窗后重开整门课，进度永远补不满。
#   试卷 DOM：#current_allNum=题目数；第 i 题是 name="questionInput_i" 的
#     * 单选题   radio    A/B/C/D
#     * 多选题   checkbox A/B/C/D
#     * 判断题   radio    T/F
#   平台自带 handSubmit() 会把 ["questionInput_i" 勾选项] 拼成
#   "A|AB|...|T" 的 myAnswers，POST 到
#   coursewareTest_handSubmitPaperToResult.action，跳回成绩页。
#   这类自测「无分数要求」，做一次即计入进度；平台取历次最高分，
#   重做不会把已有高分改低。绝不点「确定成绩查看答案」（该操作不可逆）。
# ---------------------------------------------------------------------------
TEST_MENU_JS = r"""() => [...document.querySelectorAll('.s_point')].map((p, i) => ({
    i: i,
    id: (p.id || '').replace('s_point_', ''),
    type: (p.getAttribute('itemtype') || '').toLowerCase(),
    done: (p.getAttribute('completestate') || '0') === '1',
    cur: p.classList.contains('s_pointerct'),
    title: p.getAttribute('title') || ''
}))"""

TEST_FRAME_JS = r"""() => ({
    url: location.href,
    title: document.title || '',
    itemId: (document.getElementById('current_itemId') || {}).value || '',
    paper: !!document.getElementById('current_allNum'),
    result: !!document.querySelector('.record_submit_redo') ||
            !!document.querySelector('.comf_score'),
    score: ((document.querySelector('.record_num_this') || {}).textContent || '').trim(),
    n: parseInt((document.getElementById('current_allNum') || {}).value || '0', 10)
})"""

# 逐题作答：单选/判断勾第一项，多选勾前两项。无分数要求，答案只求"已作答"，
# 不猜正确答案、不看答案页、不伪造分数。
TEST_ANSWER_JS = r"""() => {
    const n = parseInt((document.getElementById('current_allNum') || {}).value || '0', 10);
    if (!n) return {ok:false, reason:'no_allNum'};
    const picked = [];
    for (let i = 0; i < n; i++) {
        const xs = [...document.getElementsByName('questionInput_' + i)];
        if (!xs.length) { picked.push('NULL'); continue; }
        const type = (xs[0].type || '').toLowerCase();
        let k = 1;
        if (type === 'checkbox') k = Math.min(2, xs.length);
        for (let j = 0; j < k; j++) {
            xs[j].checked = true;
            try { xs[j].dispatchEvent(new Event('change', {bubbles:true})); } catch(e) {}
        }
        picked.push(xs.slice(0, k).map(x => x.value).join(''));
    }
    return {ok:true, n:n, picked:picked,
            myAnswers: picked.join('|'),
            platform: (typeof dealUserAnswerToStr === 'function')
                      ? dealUserAnswerToStr() : null};
}"""

# handSubmit(false) 跳过「有未作答题」的 confirm 弹窗；所有题已勾，本不会弹。
TEST_SUBMIT_JS = r"""() => {
    try { handSubmit(false); return 'CALLED'; }
    catch(e) { return 'ERR:' + String(e).slice(0, 120); }
}"""

TEST_REDO_JS = r"""() => {
    try {
        if (typeof redoTestPaper === 'function') { redoTestPaper(); return 'CALLED'; }
        return 'NO_FN';
    } catch(e) { return 'ERR:' + String(e).slice(0, 120); }
}"""


def test_nodes(lp):
    """课件菜单里所有自测题节点（含已完成/未完成），不按 URL 猜 frame。"""
    mf = menu_frame(lp)
    if mf is None:
        return []
    try:
        return mf.evaluate(TEST_MENU_JS) or []
    except Exception:
        return []


def test_frame_states(lp):
    """列出所有「试卷页 / 成绩页」frame：(frame, state)。"""
    out = []
    for f in lp.frames:
        try:
            d = f.evaluate(TEST_FRAME_JS)
        except Exception:
            continue
        if isinstance(d, dict) and (d.get("paper") or d.get("result")
                                    or "coursewareTest" in (d.get("url") or "")):
            out.append((f, d))
    return out


def do_test_task(lp, tag, state, allow_click=False, force=False, depth=0):
    """一轮自测题处理。返回 'submitted' / 'already' / 'opened' / 'skipped' / None。

    state: {"done":set, "tries":dict, "clicks":dict, "last":float, "moved":set}
    allow_click: 允许点课件菜单切换节点（只在没有视频在播时为真）。
    force: 平台进度仍 <100% 且无视频已观察数分钟 -> 允许重做一次并重交。
    """
    if not TEST_ENABLED or depth > 2:
        return None
    now = time.time()
    if depth == 0:
        if now - state.get("last", 0) < 12:
            return None
        state["last"] = now

    frames = test_frame_states(lp)

    # 1) 试卷已打开 -> 逐题作答 -> 用平台自带函数提交
    pf = next(((f, d) for f, d in frames if d.get("paper")), None)
    if pf:
        f, d = pf
        iid = d.get("itemId") or "?"
        n = state["tries"].get(iid, 0)
        if iid in state["done"]:
            return "already"
        if n >= TEST_MAX:
            return "skipped"
        try:
            ans = f.evaluate(TEST_ANSWER_JS)
        except Exception as e:
            log("  [%s] 自测题作答异常: %s" % (tag, str(e)[:110]))
            return None
        if not ans.get("ok"):
            log("  [%s] 试卷未就绪: %s" % (tag, ans))
            return None
        log("  [%s] 课后自测题：共 %s 题（单选/多选/判断），逐题作答 | myAnswers=%s"
            % (tag, ans.get("n"), (ans.get("myAnswers") or "")[:110]))
        # 稍作停顿，避免"打开试卷 0 秒即交卷"这种明显不真实的轨迹
        lp.wait_for_timeout(2500)
        try:
            r = f.evaluate(TEST_SUBMIT_JS)
        except Exception as e:
            # form.submit() 会让 frame 导航，Playwright 常抛 context destroyed
            r = "NAV:" + str(e)[:70]
        lp.wait_for_timeout(6500)
        ok = any(x[1].get("result") for x in test_frame_states(lp))
        state["done"].add(iid)
        state["tries"][iid] = n + 1
        log("  [%s] 自测题已提交（%s），成绩页=%s；平台取历次最高分，不掉分"
            % (tag, r, ok))
        _move_after_test(lp, tag, state, iid)
        return "submitted"

    # 2) 成绩页：说明此前已交过卷
    rf = next(((f, d) for f, d in frames if d.get("result")), None)
    if rf:
        f, d = rf
        iid = d.get("itemId") or "?"
        n = state["tries"].get(iid, 0)
        if force and n < TEST_MAX:
            # 进度仍不到 100%：重做一次再交，重新触发平台完成上报。
            # 只做有限次，且平台保留最高分，绝不点"确定成绩查看答案"。
            state["tries"][iid] = n + 1
            try:
                r = f.evaluate(TEST_REDO_JS)
            except Exception as e:
                r = "ERR:" + str(e)[:70]
            log("  [%s] 进度复核未达标 / 自测页停滞，重做一次自测题（%s/%s）: %s"
                % (tag, n + 1, TEST_MAX, r))
            lp.wait_for_timeout(6500)
            return do_test_task(lp, tag, state, allow_click=True,
                                force=False, depth=depth + 1) or "opened"
        if iid in state["done"]:
            return "already"
        state["done"].add(iid)
        log("  [%s] 自测题已有成绩 %s 分，视为已完成；不重做、不确认成绩"
            "（确认成绩不可逆）" % (tag, d.get("score") or "?"))
        _move_after_test(lp, tag, state, iid)
        return "already"

    # 3) 没有测试 frame：只在【当前选中节点本身就是 test】时点它重载。
    #    绝不从别的位置主动跳到自测题 —— PDF/网页课件也没有 <video>，
    #    误判会把正在按在线时长计进度的节点打断。
    if not allow_click:
        return None
    cand = next((x for x in test_nodes(lp)
                 if x.get("type") == "test" and x.get("cur")), None)
    if cand is None or state["clicks"].get(cand["id"], 0) >= 2:
        return None
    mf = menu_frame(lp)
    if mf is None:
        return None
    state["clicks"][cand["id"]] = state["clicks"].get(cand["id"], 0) + 1
    try:
        r = mf.evaluate(CLICK_NODE_JS, cand["i"])
    except Exception as e:
        log("  [%s] 点开自测题节点异常: %s" % (tag, str(e)[:100]))
        return None
    log("  [%s] 点开课后自测题节点 第%s个「%s」: %s"
        % (tag, cand["i"] + 1, cand.get("title") or "-", r))
    lp.wait_for_timeout(6500)
    return do_test_task(lp, tag, state, allow_click=True,
                        force=False, depth=depth + 1) or "opened"


def _move_after_test(lp, tag, state, iid):
    """自测处理完，点回课件菜单的下一个未完成节点；每道自测只做一次。"""
    if iid in state["moved"]:
        return
    state["moved"].add(iid)
    try:
        r = click_next_node(lp, tag)
        log("  [%s] 自测后继续后续节点: %s" % (tag, r))
    except Exception as e:
        log("  [%s] 自测后切换节点异常: %s" % (tag, str(e)[:100]))


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
            log("  [%s] 50s 内未找到含 <video> 的课件 frame（可能是 PDF/网页型或慢热）；"
                "继续保活，beat/video_state 每拍仍会按 DOM 重新查找" % tag)
        else:
            log("  [%s] 视频 frame 已找到: %s" % (tag, (kj.url or "")[:110]))
        # 【课后自测题】平台若直接停在 test 节点，先处理已经打开的试卷/成绩页，
        # 避免在断点续学 / 恢复播放位置时白等 50 秒找 <video>。
        test_state = {"done": set(), "tries": {}, "clicks": {},
                      "last": 0.0, "moved": set()}
        _on_test = any(x.get("cur") and x.get("type") == "test"
                       for x in test_nodes(lp))
        if TEST_ENABLED and (test_frame_states(lp) or _on_test):
            r0 = do_test_task(lp, tag, test_state, allow_click=_on_test)
            if r0:
                log("  [%s] 打开课程时自测题处理: %s" % (tag, r0))
        # 【断点续学】平台 playFirstNode() 总从第一个节点开始播，
        # 这里主动跳到第一个未完成节点，跳过已学完的节点。
        resume_to_unfinished_node(lp, tag)
        beat(lp, tag, verbose=True)
        # 重开课程时平台不读自己保存的 videoTime，这里恢复到那个真实秒数。
        # 当前节点是「课后自测题」时没有 <video>，恢复函数会空等 50 秒，跳过。
        cur_is_test = any(x.get("cur") and x.get("type") == "test"
                          for x in test_nodes(lp))
        if cur_is_test:
            log("  [%s] 当前是课后自测题节点（无视频），跳过播放位置恢复" % tag)
        else:
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
        no_video_since = None                 # 连续读不到 <video> 的起始时间
        end_confirm = 0                       # 节点播完需连续两次确认（防 FLV 分片边界误判）
        last_dur = None                       # 上一次读到的 duration（判断 MSE 时长是否稳定）
        backfill_tries = 0                    # 本轮「回头补播未完成节点」次数
        stuck_confirm = 0                     # 连续「无后续节点且平台进度不涨」次数
        test_idle = 0                         # 连续停留在自测页且无新提交的节拍数
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
                # 【课后自测题】每 60s 检查：试卷页 -> 逐题作答并提交；
                # 无视频且菜单里有 test 节点 -> 点开它。视频在播时绝不切节点。
                test_active = False
                if TEST_ENABLED:
                    force_test = (no_video_beats >= 3) or (test_idle >= 2)
                    # 只有「当前节点就是 test」才允许点菜单重载；PDF/网页课件
                    # 同样没有 <video>，不能因为它们而跳去自测题。
                    cur_on_test = any(x.get("cur") and x.get("type") == "test"
                                      for x in test_nodes(lp))
                    tr = do_test_task(lp, tag, test_state,
                                      allow_click=bool(st.get("noVideo")) and cur_on_test,
                                      force=force_test)
                    if tr == "submitted":
                        test_idle = 0
                        log("  [%s] 自测题已提交，回主站复核平台进度..." % tag)
                        ok, pct_now = confirm_done(pg, cid, tag)
                        if ok:
                            log("  [%s] 复核通过（平台进度=%s），本门学完"
                                % (tag, pct_now if pct_now is not None else "未读到"))
                            result = "done"
                            break
                        log("  [%s] 自测已提交但平台进度仍 %s%%，继续本门其它节点"
                            % (tag, pct_now))
                        no_video_beats, no_video_pct, no_video_since = 0, None, None
                        st = video_state(lp)
                    elif tr in ("already", "opened"):
                        test_idle += 1
                    elif tr == "skipped":
                        test_idle += 1
                    else:
                        test_idle = 0
                    # 自测页做完后连续 5 个节拍仍无进展：交回通用无视频逻辑，
                    # 由它按 20 分钟观察窗决定重开本门课，避免无限空转。
                    test_active = (tr in ("submitted", "already", "opened")
                                   and test_idle < 5)
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
                    "| 视频 %.1f/%.1f s ready=%s | frame=%s"
                    % (tag, clabel,
                       np.get("done") if np else "-",
                       np.get("total") if np else "-",
                       np.get("pct") if np else "-",
                       est,
                       st.get("t", 0) or 0, st.get("dur", 0) or 0, st.get("ready"),
                       (st.get("frameUrl") or "-")[-42:]))
                # 【读不到 <video> 的兜底】2026-11-09 修复重点：
                # 旧版「3 分钟 x 2 次进度不涨（约 6 分钟）就重开整门课」，
                # 而一个节点要 26 分钟才播完 —— 重开把视频打回 0 秒，
                # 覆盖率永远停在 31.1%(≈5.3%)，形成 26 轮死循环。
                # 现在默认给 20 分钟观察窗口（CMATC_NOVIDEO_GRACE_MIN），且必须
                # 同时满足「平台进度连续两次不涨」才允许重开课程；期间 beat()
                # 每 20s 仍按 DOM 重新找视频 frame，找到即回到正常播放分支。
                if st.get("noVideo") and test_active:
                    # 自测题节点本来就没有 <video>：不进入「无视频 20 分钟观察窗」，
                    # 更不因此重开整门课（这正是旧版卡 95.6% 的表现）。
                    no_video_beats, no_video_pct, no_video_since = 0, None, None
                    log("  [%s] 当前为课后自测题节点（无 <video>），按做题流程处理中"
                        % tag)
                elif st.get("noVideo"):
                    if no_video_since is None:
                        no_video_since = time.time()
                    no_video_beats += 1
                    if no_video_beats in (1, 3, 6, 9):
                        log("  [%s] 已 %s 分钟未读到 <video>（%s frame=%s）；"
                            "真实在线时长仍在上报，继续观察，不重开课程"
                            % (tag, no_video_beats, st.get("reason", "-"),
                               (st.get("frameUrl") or "-")[-42:]))
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
                        elapsed_min = (time.time() - (no_video_since or time.time())) / 60.0
                        stalled = (pct_now is not None and no_video_pct is not None
                                   and pct_now <= no_video_pct + 0.05)
                        if stalled:
                            if elapsed_min >= NOVIDEO_GRACE_MIN:
                                log("  [%s] 连续 %.1f 分钟读不到 <video> 且平台进度 %s%% 不涨，"
                                    "才允许重开本门课重建课件链" % (tag, elapsed_min, pct_now))
                                result = "continue"
                                break
                            log("  [%s] 平台进度 %s%% 暂未涨，仍处于 %.0f 分钟观察窗口"
                                "（已 %.1f 分钟）；保持在线，等当前节点播完"
                                % (tag, pct_now, NOVIDEO_GRACE_MIN, elapsed_min))
                        elif pct_now is not None:
                            log("  [%s] 未读到视频但平台进度仍在涨 %s%% -> %s%%，保持在线"
                                % (tag,
                                   no_video_pct if no_video_pct is not None else "-",
                                   pct_now))
                        if pct_now is not None:
                            no_video_pct = pct_now
                        # 不再把计数重置为 1：让它按真实分钟线性增长，
                        # 日志「已 N 分钟未读到 <video>」才准确。
                else:
                    no_video_beats = 0
                    no_video_pct = None
                    no_video_since = None
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
                    stuck_confirm += 1
                    log("  [%s] 菜单节点全完成但平台仅 %s%%，"
                        "结算滞后确认 %s/%s 次" % (tag, pct_now, stuck_confirm, STUCK_MAX))
                    if stuck_confirm >= STUCK_MAX:
                        log("  [%s] 连续 %s 次结算滞后，结束本轮重新打开本门课核对，"
                            "不再停在片尾空转" % (tag, stuck_confirm))
                        result = "continue"
                        break
                # 【节点播完判定】2026-11-09 修订：FLV 分段播放器的 duration
                # 可能只是「已缓冲分片长度」，t 贴近 dur 不代表整段 26:27 播完。
                # 三重门槛：v.ended，或 dur>=120s 且 t>=0.9*dur 且 dur-t<3；
                # 且必须连续两次采样成立（间隔 60s）才切下一节点，避免把
                # 分片边界误判成播完而跳过节点（覆盖率永远补不满）。
                dur2, tnow2 = st.get("dur") or 0, st.get("t") or 0
                dur_stable = (last_dur is not None and abs(dur2 - last_dur) < 1.0)
                # 若 duration 每次采样都在变长，说明它只是「已缓冲分片长度」，
                # 不能当作整节点时长；此时只认 v.ended。
                end_like = bool(st.get("ended")) or (
                    dur2 >= 300 and tnow2 > 5 and (dur2 - tnow2) < 3
                    and tnow2 >= 0.95 * dur2 and dur_stable)
                last_dur = dur2
                end_confirm = end_confirm + 1 if end_like else 0
                if end_like and end_confirm == 1:
                    log("  [%s] 视频疑似播完（t=%s/%s），再观察一个节拍确认"
                        % (tag, tnow2, dur2))
                if end_confirm >= 2:
                    log("  [%s] 视频播完已连续 2 次确认（t=%s/%s），切换下一节点"
                        % (tag, tnow2, dur2))
                    r = click_next_node(lp, tag)
                    if r.get("allDone") or not r.get("clicked", True):
                        log("  [%s] 当前节点之后已无未完成节点，回主站复核平台进度..." % tag)
                        ok, pct_now = confirm_done(pg, cid, tag)
                        if ok:
                            log("  [%s] 复核通过（平台进度=%s），本门学完"
                                % (tag, pct_now if pct_now is not None else "未读到"))
                            result = "done"
                            break
                        # 【2026-11-10 修复】NEXT_NODE_JS 只往【后】找未完成节点。
                        # 平台停在最后一节、前面还有第 1 节未完成时，它永远
                        # 返回 allDone=True 且不点任何节点；旧版只打印
                        # 「继续学本门」然后停在 t=928/928 的片尾，每 2 分钟
                        # 复核一次，从 23:21 空转到 05:53 共 6.5 小时。
                        # 现在主动回头补播第一个未完成节点；补不动也要在
                        # 有限次数内结束本轮重新核对，绝不无限空转。
                        info2 = node_info(lp) or {}
                        first2 = info2.get("firstUndone", -1)
                        if first2 >= 0 and backfill_tries < BACKFILL_MAX:
                            backfill_tries += 1
                            log("  [%s] 平台 %s%% | 菜单 %s/%s 完成 | 第 %s 个节点"
                                "仍未完成 -> 回头补播（%s/%s）"
                                % (tag, pct_now, info2.get("done"),
                                   info2.get("total"), first2 + 1,
                                   backfill_tries, BACKFILL_MAX))
                            rb = click_first_unfinished_node(lp, tag)
                            log("  [%s] 补播结果: %s" % (tag, rb))
                            last_t, t_stall = -1, 0
                            last_dur, end_confirm, stuck_confirm = None, 0, 0
                            same_next, last_next_id = 0, None
                            continue
                        stuck_confirm += 1
                        log("  [%s] 无更早未完成节点或补播已达上限；平台仍为 %s%%，"
                            "无进展确认 %s/%s 次"
                            % (tag, pct_now, stuck_confirm, STUCK_MAX))
                        if stuck_confirm >= STUCK_MAX:
                            log("  [%s] 连续 %s 次无进展，结束本轮重新打开本门课核对"
                                % (tag, stuck_confirm))
                            result = "continue"
                            break
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
                    end_confirm = 0
                elif not st.get("noVideo"):
                    # 视频慢热：readyState=0 可持续 60~90 秒，这段时间不算「停滞」。
                    if (st.get("ready") or 0) < 2:
                        t_stall = 0
                        if tick % 9 == 0:
                            log("  [%s] 视频慢热加载 readyState=%s src=%s，耐心等待"
                                % (tag, st.get("ready"), st.get("src")))
                    elif st.get("t") == last_t:
                        t_stall += 1
                        # 2026-11-09：5 分钟太短，FLV 分片缓冲/慢热常被误判为
                        # 卡死而跳过未播完的节点；放宽到约 10 分钟。
                        if t_stall >= 10:
                            log("  [%s] 视频连续约 %s 分钟未推进（state=%s），尝试续播下一节点"
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
        log("ERROR: 缺少密码。用法：run_steady.bat <账号> <密码> [目标学时] [diag|dry]"
            "  或 --user U --pwd P --target 80")
        sys.exit(1)
    if os.path.exists(STOP_FLAG):
        os.remove(STOP_FLAG)
    log("=" * 72)
    log("稳态挂机启动 | 账号 %s | 目标 %s 学时 | 自主选课=%s | 单次会话上限 %.0f 分钟 | 节拍 %ss | 复核间隔 %ss | DIAG=%s | DRY=%s"
        % (USER, TARGET, AUTO_CHOOSE, DWELL_MIN, BEAT_SEC, CREDIT_EVERY, DIAG, DRY))
    log("启动参数: --user / --pwd / --target（默认 80）；本次 target=%s mode=%s"
        % (STARTUP.get("target") or "默认80", STARTUP.get("mode") or "正式挂机"))
    log("规则：一门课 100% 才换下一门；未完成则下一轮重新打开同一门继续。")
    if AUTO_CHOOSE:
        log("学时未达标且已选课程全部完成时：自动从课程中心选【未学过】的课"
            "（每轮 %d 门、累计上限 %d 门），不重选已学课程。"
            % (CHOOSE_BATCH, CHOOSE_TOTAL_MAX))
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
    chosen_total = 0       # 本次运行累计自主选课成功门数（上限保护）
    choose_stall = 0       # 连续「已选课却仍无待学课程、学时也不涨」的轮数
    last_choose_credit = None   # 上次触发自主选课时的学时，用于判断是否有进展
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

            if DRY:
                if AUTO_CHOOSE and not any(c.get("todo") for c in pool):
                    plan_n = auto_choose_courses(pg, pool, credit,
                                                 chosen_total, dry=True)
                    log("  DRY：学时 %s/%s 未达标且已选课程全部完成，"
                        "正式挂机时将自主选课 %d 门（本次未提交）"
                        % (credit, TARGET, plan_n))
                log("  DRY 只读模式：课程清单/进度统计已输出；"
                    "未打开学习页、未选课、未写任何平台数据，脚本退出。")
                break

            # 2026-11-09 修复：待学清单直接取自「我的自选课-未完成」筛选
            # （todo 标记），不再从「全部」课程里按进度挑，也不把
            # pct=None 的卡片当成未完成 —— 这是「19 门未完成」虚高的直接原因。
            finished_n = sum(1 for c in pool
                             if c.get("pct") is not None and c["pct"] >= 99.9)
            unknown_n = sum(1 for c in pool if c.get("pct") is None)
            unfinished = [c for c in pool
                          if c.get("todo")
                          and c["url"] not in skip
                          and c["url"] not in done_urls]
            log("  本轮核对: 已选 %d 门 | 平台已完成 %d 门 | 待学 %d 门"
                " | 进度未知(不学) %d 门"
                % (len(pool), finished_n, len(unfinished), unknown_n))
            if not unfinished:
                log("  课程池内课程已全部 100%% / 已完成 / 被跳过，清空记录重新核对")
                skip.clear()
                done_urls.clear()
                unfinished = [c for c in pool if c.get("todo")]
                if not unfinished:
                    # 2026-11-11 第九轮：已选课程全部 100% 但学时未达标，
                    # 不再直接退出，改为从课程中心自主选【没学过】的新课。
                    if not AUTO_CHOOSE:
                        log("  已选课程全部完成，学时 %s/%s 仍未达标；"
                            "自主选课已关闭（CMATC_AUTO_CHOOSE=0），退出。"
                            % (credit, TARGET))
                        break
                    if last_choose_credit is not None and credit > last_choose_credit:
                        choose_stall = 0        # 学时确实涨了，说明选的课在学
                    else:
                        choose_stall += 1
                    if choose_stall >= 3:
                        log("  连续 3 轮自主选课后学时仍为 %s、且始终没有待学课程，"
                            "疑似平台未结算或课程未能进入学习，停止以免空转。"
                            % credit)
                        break
                    n = auto_choose_courses(pg, pool, credit, chosen_total)
                    last_choose_credit = credit
                    if n <= 0:
                        log("  自主选课未成功（第 %d 次）；稍后重试，"
                            "连续 3 次无进展则退出" % choose_stall)
                        pg.wait_for_timeout(8000)
                        continue
                    chosen_total += n
                    log("  自主选课成功 %d 门（本次累计 %d/%d），"
                        "下一轮重新读取「我的课程」后开始学习"
                        % (n, chosen_total, CHOOSE_TOTAL_MAX))
                    pg.wait_for_timeout(3000)
                    continue
            # 有正常待学课程：说明学习在推进，清除选课停滞计数
            choose_stall = 0

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

            try:
                todo_idx = unfinished.index(cur) + 1
            except ValueError:
                todo_idx = 0
            log("  本轮只学 1 门: %s  cid=%s  (待学清单第 %d/%d 门，本次已完成 %d 门)"
                % (course_label(cur), cur.get("cid") or "-",
                   todo_idx, len(unfinished), done_count))
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
