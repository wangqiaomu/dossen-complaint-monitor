# 免费云端版：GitHub Actions 监控（无需服务器 / 无需电脑常开）

把邮件监控脚本交给 GitHub 的免费定时任务（Actions）运行。GitHub 每次到点临时拉起一台
Linux 虚拟机执行脚本，跑完即销毁——**不花钱、不占你电脑**。

---

## 一、准备（3 样东西，全部免费）

1. **GitHub 账号**（免费，无需绑卡）
   - 新建一个仓库（**建议设为 Public**，Actions 时长无限；Private 每月 2000 分钟也够用，
     且代码不含任何密码，密钥都在仓库 Settings 里加密存储，公开也安全）。

2. **企业邮箱 IMAP 凭证**
   - 登录网页企业邮箱 `exmail.qq.com` → 设置 → 收发信设置，开启 **IMAP/SMTP**。
   - 凭证 = 邮箱**登录密码**；若已开启安全登录，则用「**客户端专用授权码**」
     （设置 → 邮箱绑定 / 微信绑定中生成）。

3. **PushPlus 推送 Token**（免费微信推送）
   - 打开 `pushplus.plus` → 微信扫码登录 → 复制「Token」。
   - （备选：企业微信群机器人 Webhook，填 `WECOM_WEBHOOK` 并把 `NOTIFIER` 设 `wecom`）

---

## 二、上传文件到仓库

把下面两个文件放进仓库根目录（保持相对路径，工作流按此路径调用）：

```
你的仓库/
├── dossen_complaint_monitor.py        # 监控脚本（用本仓库根目录那份，已支持 IMAP 直连 + pushplus）
└── .github/workflows/dossen-monitor.yml   # 本说明同级目录已提供
```

> 仓库里只需这两个文件，无需 `.env`（密钥走 GitHub Secrets）。

---

## 三、配置密钥（Settings → Secrets and variables → Actions → New repository secret）

| 密钥名 | 值 | 说明 |
|---|---|---|
| `QQ_MAIL_USER` | 你的完整企业邮箱地址 | 如 `wangxize@dossen.com` |
| `QQ_MAIL_AUTH` | 邮箱密码 / 客户端专用授权码 | 见上文第 2 步 |
| `IMAP_HOST` | `imap.exmail.qq.com` | 企业邮箱；个人 QQ 邮箱填 `imap.qq.com` |
| `NOTIFIER` | `pushplus` | 推送通道 |
| `PUSHPLUS_TOKEN` | 你的 PushPlus Token | 见上文第 3 步 |

> 若用企业微信机器人：把 `NOTIFIER` 设 `wecom`，并加 `WECOM_WEBHOOK` 密钥（无需 `PUSHPLUS_TOKEN`）。

---

## 四、运行逻辑（与本地版一致）

- **轮询**（工作日下午每 5 分钟，北京时间 15:00–19:50）：一旦检索到「区域经理 = 王喜泽」
  的问责邮件，**立即实时推送**门店名 + 反馈内容；无命中则静默，不刷屏。
- **收尾**（北京时间 19:54 之后那次运行）：若当天从未命中王喜泽，才发一次「今日无问责」。
- 按 **Message-ID 去重**，同一封邮件不会重复通知；跨次运行的去重缓存由 Actions Cache 持久化。

---

## 五、先测一次（不推送）

仓库页 → **Actions** → 选 `dossen-complaint-monitor` → **Run workflow** →
`mode` 填 `test` → 运行。它会连 IMAP 拉取候选邮件并打印提取到的「门店 / 区域经理 / 反馈内容」，
用于核对表头解析是否正确（确认 `区域经理` 列能正确识别「王喜泽」）。
如需改表头关键词，改脚本里 `table_header_store / table_header_region / table_header_feedback`。

---

## 六、正式启用

`test` 验证无误后，定时任务会在**下一个工作日 15:00（北京）**自动开始轮询。
无需任何手动操作，GitHub 自动跑。

---

## 七、注意事项

- **免费额度**：Private 仓库每月 2000 分钟；本任务工作日约 60 次/天 × ~1 分钟 ≈ 1300 分钟/月，
  在额度内；设为 Public 则完全无限制。
- **定时精度**：GitHub 定时任务偶尔漂移几分钟（不影响 5 分钟轮询语义）；19:55 收尾已留 19:54 缓冲。
- **休眠**：仓库若 **60 天无任何提交/活动**，定时任务会被 GitHub 自动暂停。保持仓库一点活跃
  （如偶尔手动 Run 一次、或加个无关提交）即可常驻。
- **非工作日**：脚本自身跳过周六周日，定时也限制在 `1-5`。
- 之前 WorkBuddy 里的两个本地自动化请保持 **PAUSED**，避免与云端重复推送。
