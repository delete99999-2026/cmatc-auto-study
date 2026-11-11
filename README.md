# cmatc-auto-study

在线培训平台的**稳态挂机学习脚本**：基于 Python + Playwright，单会话串行学习，按平台真实播放计时，不伪造学时、不改接口数据。

> 仅供本人在自有账号上使用，请遵守平台的相关使用规定。仓库中**不包含任何真实账号、密码或个人信息**。

---

## 一、它能做什么

- 从「我的课程 → 未完成」筛选待学课程，逐门学到 100% 再换下一门。
- 视频逐节点真实播放；支持断点续播，未完成节点从 0 秒重新补播（避免卡在 98.9%）。
- 自动完成课后自测（单选 / 多选 / 判断，无分数要求），通过平台自带提交按钮作答。
- 已选课程全部完成但学时仍未达标时，自动到课程中心选**没学过**的新课；排除依据是课程 ID、openId、完整课程名和持久化历史。
- 提供 `dry`（只读统计）和 `diag`（单课诊断）两种排查模式。
- 随时优雅停止：在目录下创建一个名为 `stop_steady.flag` 的空文件即可。

---

## 二、环境准备

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows（脚本用 `.bat` 启动） |
| 浏览器 | 本机 Microsoft Edge |
| Python | 3.11（需安装 `playwright`） |
| 其他 | 能访问目标培训平台；无需 `playwright install`，直接调用本机 Edge |

安装依赖：

```bat
pip install playwright
```

首次使用请按本机情况改两处路径：

- `run_steady.bat` 中的 `PY`：你的 `python.exe` 完整路径。
- `common.py` 中的 `EDGE`：你的 `msedge.exe` 完整路径。

---

## 三、启动方式

### 方式 A：启动器（推荐）

```bat
run_steady.bat <账号> <密码> [目标学时] [diag|dry]
```

示例：

```bat
run_steady.bat YOUR_ACCOUNT YOUR_PASSWORD 100
run_steady.bat YOUR_ACCOUNT YOUR_PASSWORD 100 dry
run_steady.bat YOUR_ACCOUNT YOUR_PASSWORD 80
```

- 不传目标学时则默认 **80**；想修满 100 学时必须显式写 `100`。
- `dry` = 只统计课程与学时、不学习不选课；`diag` = 只跑一门课做诊断。

### 方式 B：直接调用 Python

```bat
python -u steady_study_fixed.py --user YOUR_ACCOUNT --pwd YOUR_PASSWORD --target 100
python -u steady_study_fixed.py --user U --pwd P --target 100 --dry
```

### 方式 C：环境变量

| 变量 | 含义 | 默认值 |
|---|---|---|
| `CMATC_USER` | 登录账号 | **必填，无默认值** |
| `CMATC_PWD` | 登录密码 | 必填 |
| `CMATC_TARGET` | 目标学时 | `80` |
| `CMATC_AUTO_CHOOSE` | `1`=学时不足时自主选课（默认），`0`=关闭 | `1` |
| `CMATC_CHOOSE_BATCH` | 每轮最多自主选几门 | `2` |
| `CMATC_CHOOSE_MAX_PAGES` | 课程中心最多翻几页 | `12` |
| `CMATC_CHOOSE_TOTAL_MAX` | 单次运行自主选课总上限 | `20` |
| `CMATC_DO_TESTS` | `0`=关闭课后自测任务 | 默认开启 |
| `CMATC_TEST_MAX` | 进度未达标时自测最多重做次数 | `2` |
| `CMATC_BACKFILL_MAX` | 每轮最多回头补播未完成节点次数 | `2` |
| `CMATC_STUCK_MAX` | 连续几次无进展就结束本轮 | `3` |
| `CMATC_NOVIDEO_GRACE_MIN` | 无视频观察窗时长（分钟） | `20` |
| `CMATC_DIAG` / `CMATC_DRY` | 诊断 / 只读模式开关 | 关闭 |

优先级：**命令行参数 > 环境变量 > 默认值**。

CMD 里设置密码请用双引号包住整个赋值式，否则单引号会被算进密码：

```bat
set "CMATC_USER=YOUR_ACCOUNT"
set "CMATC_PWD=YOUR_PASSWORD"
```

---

## 四、运行规则与注意事项

1. **单会话**：平台是 SSO 单点登录，同一时间只允许一个学习窗口。脚本严格串行；运行时请不要在浏览器里同时打开学习页，否则会互踢。
2. **一门一门学**：某门课必须到 100% 才切换下一门，避免多门课各学一半。
3. **进度以平台为准**：脚本定期读取平台进度接口，不信任本地估计值。
4. **学时目标**：默认 80。若当前学时已超过默认值，不显式传目标会立即「已达标」退出。
5. **优雅停止**：创建 `stop_steady.flag` 后脚本会在当前节点收尾退出；停止后请删除该标记再启动。
6. **日志**：`steady_run.log`（运行日志）、`steady_requests.log`（请求记录）。

---

## 五、隐私说明（重要）

- 账号、密码、目标学时**只从启动参数或环境变量读取**，源码中不保存任何真实凭据。
- 已学 / 已选课程历史按账号隔离，文件名使用账号的 SHA256 短哈希，**不含明文账号**。
- 仓库自带的 `.gitignore` 采用「默认忽略全部、只放行源码」策略：运行日志、页面快照、登录截图、`state.json`（会话令牌）、`*_seen.txt`、历史课单等**一律不入库**。
- 脚本运行时新产生的日志会写入账号用于排查，**请勿用 `git add -f` 强制提交日志**。如要公开分享，请先清空本地运行产物。

---

## 六、文件说明

| 文件 | 作用 |
|---|---|
| `steady_study_fixed.py` | 主程序（当前使用版本） |
| `common.py` | 浏览器启动、登录、账号/密码读取 |
| `run_steady.bat` | Windows 启动器，负责解析启动参数 |
| `login.py` | 独立登录探针，可保存会话状态 |
| `steady_study.py` | 早期版本，保留作回退参考 |
| `auto_study.py`、`fast_study*.py`、`probe_*.py` | 早期探索 / 接口探测脚本 |
| `_diag_*.py` | 页面结构与接口诊断脚本 |
| `_verify_*.py` | 离线回归测试（不联网、不写平台数据） |
| `.gitignore` | 发布安全规则 |

---

## 七、回归测试

不需要联网，用项目所用 Python 解释器执行：

```bat
python -u _verify_choose.py
python -u _verify_fix.py
python -u _verify_backfill.py
python -u _verify_quiz.py
```

分别覆盖自主选课、视频 frame 识别、未完成节点补播、课后自测。全部通过时会输出 `*_SELFTEST_OK`。

---

## 八、常见问题

| 现象 | 处理 |
|---|---|
| 提示 `CMATC_USER not set` | 账号现在是必填项，请带 `--user` 或设置 `CMATC_USER` |
| 登录一直停在登录页 | 检查密码是否正确、是否误写成 `set CMATC_PWD='密码'`、是否触发验证码 |
| 浏览器被挤下线 | 平台 SSO 互踢，刷新浏览器即可；避免同时开多个学习窗口 |
| 学时没涨 / 进度卡住 | 先用 `dry` 看统计，再用 `diag` 单课定位；检查是否卡在课后自测或未完成节点 |
| 想清掉运行痕迹 | 删除 `steady_*.log`、`*_out.txt`、`*.png`、`*.html` 快照、`state.json` 等；它们本来就不入库 |
