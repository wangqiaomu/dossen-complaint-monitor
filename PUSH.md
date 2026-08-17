# 把仓库推到 GitHub 并配密钥（你只需做这两段）

本地仓库已 `git commit` 完成，包含：
```
.github/workflows/dossen-monitor.yml   定时工作流
dossen_complaint_monitor.py             监控脚本
README.md                              部署说明
.gitignore
```

---

## 第一段：把仓库推到 GitHub

### 方式 A（最简单）：用 GitHub CLI
1. 安装 gh：https://cli.github.com （Windows 装好后在 Git Bash 里用）
2. 登录：`gh auth login`（选 GitHub.com，按提示浏览器授权）
3. 推送并建仓库（在 `dossen-complaint-monitor` 目录里执行）：
   ```bash
   cd dossen-complaint-monitor
   gh repo create dossen-complaint-monitor --public --source=. --push
   ```
   > 想要私有仓库就把 `--public` 改成 `--private`（免费额度 2000 分钟/月，本任务约 1300 分钟，够用）。

### 方式 B（不用 gh）：用 Personal Access Token
1. 在 https://github.com/new 网页上新建一个**空仓库**，名字 `dossen-complaint-monitor`（不要勾 README）。
2. 生成 Token：GitHub 右上角头像 → Settings → Developer settings →
   Personal access tokens → Tokens (classic) → Generate new token，勾 `repo` 权限，复制 token。
3. 在 `dossen-complaint-monitor` 目录里执行：
   ```bash
   cd dossen-complaint-monitor
   git remote add origin https://github.com/<你的用户名>/dossen-complaint-monitor.git
   git push -u origin HEAD
   ```
   > 用户名填你的 GitHub 用户名；密码处粘贴刚才的 Token（不是账号密码）。

推送成功后，进仓库 → Actions 标签应能看到 `dossen-complaint-monitor` 工作流。

---

## 第二段：填 3 类密钥（核心，敏感信息只在网页填，不要发给任何人）

仓库页 → **Settings → Secrets and variables → Actions → New repository secret**，
逐个添加（Name / Value）：

| Name | Value（填你自己的） |
|---|---|
| `QQ_MAIL_USER` | 完整企业邮箱，如 `wangxize@dossen.com` |
| `QQ_MAIL_AUTH` | 企业邮箱**登录密码**，或「客户端专用授权码」 |
| `IMAP_HOST` | `imap.exmail.qq.com`（个人 QQ 邮箱填 `imap.qq.com`） |
| `NOTIFIER` | `pushplus` |
| `PUSHPLUS_TOKEN` | 你的 PushPlus Token（pushplus.plus 扫码登录后复制） |

> 企业微信机器人备选：把 `NOTIFIER` 设 `wecom`，加一个 `WECOM_WEBHOOK` 密钥，不用 `PUSHPLUS_TOKEN`。

---

## 先测一次（不推送微信）

仓库页 → **Actions** → 选 `dossen-complaint-monitor` → **Run workflow** →
`mode` 填 `test` → 运行。它会连 IMAP 拉候选邮件并打印提取到的
「门店 / 区域经理 / 反馈内容」，用来确认能正确识别「王喜泽」那一行。
test 模式**不会**发微信。

确认无误后，下个工作日 15:00（北京）起自动轮询，命中即推微信，
19:54 后若当天无命中则发一次「今日无问责」。

---

## 注意
- 仓库若 **60 天无活动**，GitHub 会暂停定时任务；偶尔手动 Run 一次即可常驻。
- 之前 WorkBuddy 里的两个本地自动化请保持 **PAUSED**，避免重复推送。
