#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 dossen.com 宾客严重投诉问责 监控脚本
================================================================================

【用途】
  每周一至周五，自动检查 QQ 邮箱中来自 dossen.com 域名、发件人为"品质中心"、
  且主题或正文涉及"宾客严重投诉问责"的邮件。当邮件正文中"区域经理"字段为
  "王喜泽"时，通过 WorkBuddy 内置通知（可推送至微信）发送告警，消息包含门店名称
  与该邮件的反馈内容；当日未检索到符合条件的邮件时，发送"今日无问责"兜底提示。

【运行方式 —— 两种取数后端，解析内核共用】
  后端一 · IMAP 直连（自带凭证，可脱离 WorkBuddy 部署）：
    1) 准备 .env：
         QQ_MAIL_USER=你的完整邮箱地址（个人QQ邮箱: 12345@qq.com；企业邮箱: name@公司域名）
         QQ_MAIL_AUTH=邮箱密码（见下方说明）
         IMAP_HOST=imap.qq.com（个人QQ邮箱）或 imap.exmail.qq.com（腾讯企业邮箱）
       · 个人QQ邮箱：QQ_MAIL_AUTH 填「IMAP授权码」（非登录密码，邮箱设置→账户→开启IMAP后生成）
       · 腾讯企业邮箱：QQ_MAIL_AUTH 填邮箱「登录密码」；若已开启安全登录，则需填「客户端专用授权码」
         （网页端企业邮箱 设置→邮箱绑定/微信绑定 中生成）。且需在 设置→收发信设置 开启 IMAP/SMTP 服务。
    2) 运行：python dossen_complaint_monitor.py
  后端二 · qq-mail 连接器（已连接，免授权码，由 WorkBuddy 自动化调用）：
    1) 自动化先经 qq-mail 连接器 SearchMessages 拉取候选邮件，落盘为 .eml 文件；
    2) 再运行：python dossen_complaint_monitor.py --eml-dir <目录>
    解析、触发、通知逻辑与后端一完全一致。
  —— 试运行（不连 IMAP、不污染去重缓存）：
    python dossen_complaint_monitor.py --dry-run --sample 样例.eml
    python dossen_complaint_monitor.py --dry-run --eml-dir <目录> --date 2026-08-14

【无第三方依赖】仅使用 Python 标准库（imaplib / email / json / re 等）。

================================================================================
 一、邮件筛选条件（必须同时满足 A + B + C 才进入候选集）
================================================================================
  A. 发件域：发件人邮箱地址的域必须以 "dossen.com" 结尾（不区分大小写）。
  B. 发件人：发件人显示名（或地址）包含关键字 "品质中心"（可配置）。
  C. 关键字：邮件主题 或 正文（纯文本，缺失时回退到去标签的 HTML）包含
             "宾客严重投诉问责"（可配置）。

================================================================================
 二、触发规则
================================================================================
  1. 对候选邮件正文进行 HTML 表格解析：找到含"门店""区域经理""反馈内容"列的
     表格，按行拆成 item；无表格时回退正则解析整封邮件。
  2. 若某 item 的"区域经理"字段等于（或包含）目标值 "王喜泽"（可配置），
     判定为"命中"，计入待通知列表。
  3. 命中列表非空  → 为每个命中 item（即每行/每家门店）生成一条通知（也可聚合为一条，见配置）。
  4. 命中列表为空  → 视 NOMATCH_WHEN 配置发送兜底提示：
        - "target"（默认）：只要没有区域经理=王喜泽 的命中邮件，即"今日无问责"
          （即便当天存在其它区域经理的问责邮件，王喜泽 无事项，故无问责）。
        - "any"：仅当候选集整体为空（连一封问责邮件都没有）才"今日无问责"。
     ⚠ 注意去重：已通知过的邮件（按 Message-ID 缓存）不会重复通知。
  5. 非工作日（周六/周日）默认静默跳过（可用 --force 强制运行）。

================================================================================
 三、微信(WorkBuddy内置)通知内容格式与字段
================================================================================
  命中通知（每个命中 item / 每家门店一条）：
  ------------------------------------------------------------------
  【宾客严重投诉问责 · 王喜泽区域】
  门店名称：<门店名称>
  区域经理：王喜泽
  反馈内容：<反馈内容>

  —— 邮件信息 ——
  邮件主题：<主题>
  发件人：<发件人显示名 <地址>>
  接收时间：<本地时间>
  邮件ID：<Message-ID>
  ------------------------------------------------------------------

  兜底通知（无命中）：
  今日无问责（王喜泽区域 · <日期> 未检索到符合条件的宾客严重投诉问责邮件）

================================================================================
 四、无匹配时的兜底提示 与 调度策略
================================================================================
  · 文本固定为："今日无问责"，并附带日期与"符合条件"的口径说明（见上）。
  · 邮件每天 15:00–19:00 间到达（时间不固定），故采用"轮询 + 收尾"调度：
      - 轮询运行（默认，工作日下午每 15 分钟一次）：只推送"王喜泽命中"，
        不发送"今日无问责"，避免每次轮询都刷出兜底提示。
      - 收尾运行（窗口结束，加 --eod）：当日全天无王喜泽命中时，才发送
        一次"今日无问责"；若当日已发过命中通知则跳过。
  · 命中邮件按 Message-ID 去重，不会重复通知；当日标记(.state/daily_*.txt)
    保证"今日无问责"一天只发一次。

================================================================================
 可选：其它微信通道（默认关闭，走 WorkBuddy 内置）
================================================================================
  NOTIFIER 可设为：
    "workbuddy"  —— 仅输出结构化结果，由 WorkBuddy 自动化推送（默认）
    "wecom"      —— 企业微信群机器人 Webhook（填 WECOM_WEBHOOK）
    "serverchan" —— Server酱（填 SERVERCHAN_SENDKEY）
    "pushplus"   —— PushPlus（填 PUSHPLUS_TOKEN）
================================================================================
"""

import os
import re
import sys
import json
import glob
import imaplib
import email
import email.utils
import email.policy
import datetime
from html.parser import HTMLParser
from email.header import decode_header, make_header

# --------------------------------------------------------------------------- #
# 轻量 .env 加载（若脚本同级存在 .env，则自动注入环境变量；已存在的环境变量优先）
# --------------------------------------------------------------------------- #
def load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


load_dotenv()

# --------------------------------------------------------------------------- #
# 配置区（可通过环境变量/.env 覆盖；字段解析正则待用户提供样例后微调）
# --------------------------------------------------------------------------- #
CONFIG = {
    # ---- IMAP / 邮箱 ----
    # 个人QQ邮箱: imap.qq.com；腾讯企业邮箱: imap.exmail.qq.com（可用 IMAP_HOST 覆盖）
    "imap_host": os.getenv("IMAP_HOST", "imap.qq.com"),
    "imap_port": int(os.getenv("IMAP_PORT", "993")),
    "mail_user": os.getenv("QQ_MAIL_USER", ""),
    # 密码：个人QQ邮箱=IMAP授权码(非登录密码)；企业邮箱=邮箱登录密码 或 "客户端专用授权码"
    "mail_auth": os.getenv("QQ_MAIL_AUTH", ""),

    # ---- 筛选条件 ----
    "sender_domain": "dossen.com",                # 条件 A：发件域
    "sender_name_keyword": "品质中心",             # 条件 B：发件人显示名关键字
    "subject_body_keyword": "宾客严重投诉问责",     # 条件 C：主题/正文关键字

    # ---- 触发规则 ----
    "target_region_manager": "王喜泽",             # 目标区域经理
    "lookback_days": 1,                           # IMAP 拉取回溯天数（从今天00:00往前；1=当天+昨天，匹配"当日"语义）
    "nomatch_when": "target",                     # "target" | "any"（见触发规则 4）
    "aggregate": False,                           # True=多封命中合并为一条通知

    # ---- 去重 / 状态 ----
    "state_dir": os.path.join(os.path.dirname(os.path.abspath(__file__)), ".state"),
    "seen_file": "seen_message_ids.txt",

    # ---- 通知通道 ----
    "notifier": os.getenv("NOTIFIER", "workbuddy"),
    "wecom_webhook": os.getenv("WECOM_WEBHOOK", ""),
    "serverchan_sendkey": os.getenv("SERVERCHAN_SENDKEY", ""),
    "pushplus_token": os.getenv("PUSHPLUS_TOKEN", ""),

    # ---- 字段提取正则（柔性；待样例校准）----
    # 门店名称：匹配 "门店：xxx" 或 "门店名称：xxx"
    "re_store": r"门店(?:名称)?\s*[:：]\s*([^\n\r]+)",
    # 区域经理：匹配 "区域经理：xxx"
    "re_region": r"区域经理\s*[:：]\s*([^\n\r]+)",
    # 反馈内容：从 "反馈内容：xxx" 起，截到下一个已知字段或正文结尾
    "re_feedback": (
        r"反馈内容\s*[:：]\s*([\s\S]+?)"
        r"(?=\n\s*(?:区域经理|门店|处理结果|整改|备注|发件|联系|——|__)\s*[:：]|\Z)"
    ),
    # 停止标签（反馈内容截断用）
    "feedback_stop_labels": ["区域经理", "门店", "处理结果", "整改", "备注", "发件", "联系"],

    # ---- HTML 表格解析配置 ----
    "table_header_store": ["门店"],
    "table_header_region": ["区域经理"],
    "table_header_feedback": ["反馈内容"],
}

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 试运行用：可被 --date 覆盖的"当前时间"
NOW_OVERRIDE = None


def now():
    return NOW_OVERRIDE or datetime.datetime.now()


def log(msg):
    print(f"[{now():%Y-%m-%d %H:%M:%S}] {msg}", file=sys.stderr)


def load_seen(state_dir, seen_file):
    path = os.path.join(state_dir, seen_file)
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_seen(state_dir, seen_file, seen_set):
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, seen_file)
    with open(path, "w", encoding="utf-8") as f:
        for mid in sorted(seen_set):
            f.write(mid + "\n")


# --------------------------------------------------------------------------- #
# 当日标记：记录当天是否已发过"命中通知"/"无问责提示"，用于轮询+收尾去重
# --------------------------------------------------------------------------- #
def daily_flag_path(state_dir, date_str):
    return os.path.join(state_dir, f"daily_{date_str}.txt")


def read_daily_flag(state_dir, date_str):
    p = daily_flag_path(state_dir, date_str)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def write_daily_flag(state_dir, date_str, value):
    os.makedirs(state_dir, exist_ok=True)
    with open(daily_flag_path(state_dir, date_str), "w", encoding="utf-8") as f:
        f.write(value)


def is_business_day(dt=None):
    dt = dt or now()
    return dt.weekday() < 5  # 0=Mon ... 4=Fri


def decode_mime_header(value):
    """解码邮件头（如 Subject / From）中的编码字符串。"""
    if not value:
        return ""
    if isinstance(value, email.header.Header):
        value = str(value)
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def parse_from(header_val):
    """返回 (display_name, addr)。"""
    if not header_val:
        return ("", "")
    name, addr = email.utils.parseaddr(header_val)
    return (decode_mime_header(name), addr.strip().lower())


def get_body(msg):
    """返回 (plain_text, html_text)。优先纯文本。"""
    plain, html = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdisp = str(part.get("Content-Disposition") or "")
            if "attachment" in cdisp:
                continue
            try:
                payload = part.get_payload(decode=True)
            except Exception:
                continue
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if ctype == "text/plain" and not plain:
                plain = text
            elif ctype == "text/html" and not html:
                html = text
    else:
        try:
            payload = msg.get_payload(decode=True)
        except Exception:
            payload = b""
        charset = msg.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace") if payload else ""
        if msg.get_content_type() == "text/html":
            html = text
        else:
            plain = text
    return plain, html


def strip_html_tags(html):
    if not html:
        return ""
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# --------------------------------------------------------------------------- #
# HTML 表格解析（用于样例中的"宾客严重投诉问责通报"表格）
# --------------------------------------------------------------------------- #
class TableParser(HTMLParser):
    """轻量 HTML 表格解析器，返回 tables -> rows -> cells 的嵌套列表。"""

    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = None
        self.current_row = None
        self.current_cell = []
        self.in_cell = False
        self.skip_tags = {"script", "style"}
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.skip_depth += 1
            return
        if self.skip_depth > 0:
            return
        if tag == "table":
            self.current_table = []
        elif tag == "tr":
            self.current_row = []
        elif tag in ("td", "th"):
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth > 0:
            return
        if tag in ("td", "th") and self.in_cell:
            self.current_row.append("".join(self.current_cell).strip())
            self.in_cell = False
            self.current_cell = []
        elif tag == "tr":
            if self.current_table is not None:
                self.current_table.append(self.current_row)
            self.current_row = None
        elif tag == "table":
            if self.current_table is not None and len(self.current_table) > 0:
                self.tables.append(self.current_table)
            self.current_table = None

    def handle_data(self, data):
        if self.in_cell and self.skip_depth == 0:
            self.current_cell.append(data)


def normalize_header(cell):
    """把表头里的空白、HTML 实体去掉，方便匹配。"""
    if not cell:
        return ""
    return re.sub(r"\s+", "", cell).replace("&nbsp;", "").strip()


def find_header_index(row, keywords):
    """在一行表头中，找到匹配 keyword 的列索引。
    优先精确匹配（如 '门店' 精确命中 '门店' 列，而非误命中 '门店编码'），
    找不到再做子串匹配（如 '门店' 可命中 '门店名称'）。"""
    # 第一轮：精确匹配
    for i, cell in enumerate(row):
        norm = normalize_header(cell)
        for kw in keywords:
            if norm == kw:
                return i
    # 第二轮：子串匹配（兜底）
    for i, cell in enumerate(row):
        norm = normalize_header(cell)
        for kw in keywords:
            if kw in norm:
                return i
    return -1


def parse_html_tables(html):
    """解析 HTML 中所有表格。"""
    if not html:
        return []
    parser = TableParser()
    try:
        parser.feed(html)
    except Exception:
        return []
    return parser.tables


def extract_table_items(plain, html, cfg):
    """
    优先解析 HTML 表格：找到含"区域经理""门店""反馈内容"列的表格，
    每行生成一个 item；无匹配表格时回退到正则解析整封邮件。
    返回 list[dict(store, region_manager, feedback, raw_text)]。
    """
    # 表头关键词（可配置）
    store_kws = cfg.get("table_header_store", ["门店"])
    region_kws = cfg.get("table_header_region", ["区域经理"])
    feedback_kws = cfg.get("table_header_feedback", ["反馈内容"])

    tables = parse_html_tables(html)
    for table in tables:
        if not table:
            continue
        header = table[0]
        store_idx = find_header_index(header, store_kws)
        region_idx = find_header_index(header, region_kws)
        feedback_idx = find_header_index(header, feedback_kws)
        if store_idx == -1 or region_idx == -1 or feedback_idx == -1:
            continue

        items = []
        for row in table[1:]:
            # 跳过空行或汇总行（如"合计"）
            if not row or len(row) <= max(store_idx, region_idx, feedback_idx):
                continue
            if any(re.search(r"合计|总计|汇总", normalize_header(cell)) for cell in row):
                continue
            store = row[store_idx].strip() if store_idx < len(row) else ""
            region = row[region_idx].strip() if region_idx < len(row) else ""
            feedback = row[feedback_idx].strip() if feedback_idx < len(row) else ""
            if not store and not region and not feedback:
                continue
            items.append({
                "store": store,
                "region_manager": region,
                "feedback": feedback,
                "raw_text": f"门店：{store}\n区域经理：{region}\n反馈内容：{feedback}",
            })
        if items:
            return items

    # 无匹配表格：回退正则
    text = plain or strip_html_tags(html)
    store, region, feedback = extract_fields(text, cfg)
    return [{
        "store": store,
        "region_manager": region,
        "feedback": feedback,
        "raw_text": text,
    }]


def local_date_of(msg):
    """邮件 Date 头转本地 datetime。"""
    datestr = msg.get("Date")
    if not datestr:
        return datetime.datetime.now()
    try:
        dt = email.utils.parsedate_to_datetime(datestr)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return datetime.datetime.now()


def extract_fields(text, cfg):
    """从正文提取 门店名称 / 区域经理 / 反馈内容。"""
    store = ""
    region = ""
    feedback = ""

    m = re.search(cfg["re_store"], text)
    if m:
        store = m.group(1).strip()

    m = re.search(cfg["re_region"], text)
    if m:
        region = m.group(1).strip()

    m = re.search(cfg["re_feedback"], text, flags=re.S)
    if m:
        feedback = m.group(1).strip()
    return store, region, feedback


def region_matches(region_value, target):
    if not region_value:
        return False
    rv = region_value.strip()
    return rv == target or target in rv


def process_message(msg, cfg, seen):
    """
    对单封邮件执行：A/B/C 筛选 + 表格/正则解析，返回候选 item 列表。
    供 IMAP 拉取与 --dry-run 样例复用。
    """
    mid = msg.get("Message-ID", "").strip()
    subject = decode_mime_header(msg.get("Subject", ""))
    from_name, from_addr = parse_from(msg.get("From", ""))
    plain, html = get_body(msg)
    body_for_search = (plain or strip_html_tags(html))

    # ---- 条件 A：发件域 ----
    domain_ok = from_addr.endswith("@" + cfg["sender_domain"].lower()) or \
                from_addr.endswith("." + cfg["sender_domain"].lower())
    if not domain_ok:
        return []

    # ---- 条件 B：发件人含关键字 ----
    if cfg["sender_name_keyword"] not in (from_name + " " + from_addr):
        return []

    # ---- 条件 C：主题/正文含关键字 ----
    if cfg["subject_body_keyword"] not in (subject + " " + body_for_search):
        return []

    # 命中候选集：按 HTML 表格行拆成多个 item；无表格则回退正则
    items = extract_table_items(plain, html, cfg)
    out = []
    for item in items:
        out.append({
            "message_id": mid,
            "subject": subject,
            "from_name": from_name,
            "from_addr": from_addr,
            "date": local_date_of(msg).strftime("%Y-%m-%d %H:%M:%S"),
            "store": item["store"],
            "region_manager": item["region_manager"],
            "feedback": item["feedback"],
            "raw_text": item["raw_text"],
            "seen": mid in seen,
        })
    return out


def fetch_candidates(cfg, seen):
    """连接 IMAP，拉取并筛选候选邮件，返回候选 dict 列表（已过滤去重）。"""
    user = cfg["mail_user"]
    auth = cfg["mail_auth"]
    if not user or not auth:
        raise RuntimeError("缺少 QQ_MAIL_USER / QQ_MAIL_AUTH（IMAP 授权码）。")

    # 只拉取"当日"窗口：今天 00:00 往前回溯 lookback_days 天（本地时区，覆盖服务器时区偏差）
    today0 = now().replace(hour=0, minute=0, second=0, microsecond=0)
    since = today0 - datetime.timedelta(days=cfg["lookback_days"])
    since_str = since.strftime("%d-%b-%Y")

    mail = imaplib.IMAP4_SSL(cfg["imap_host"], cfg["imap_port"])
    try:
        mail.login(user, auth)
        mail.select("INBOX")
        typ, data = mail.search(None, "SINCE", since_str)
        if typ != "OK":
            return []
        uids = data[0].split()
        log(f"IMAP 拉取近 {cfg['lookback_days']} 天邮件 {len(uids)} 封，开始筛选…")

        candidates = []
        for uid in uids:
            try:
                typ, raw = mail.fetch(uid, "(RFC822)")
                if typ != "OK" or not raw or raw[0] is None:
                    continue
                msg = email.message_from_bytes(raw[0][1], policy=email.policy.default)
            except Exception as e:
                log(f"解析 uid={uid} 失败: {e}")
                continue
            candidates.extend(process_message(msg, cfg, seen))
        return candidates
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass


def build_hit_message(item):
    return (
        "【宾客严重投诉问责 · 王喜泽区域】\n"
        f"门店名称：{item['store'] or '(未解析到门店名称)'}\n"
        f"区域经理：王喜泽\n"
        f"反馈内容：{item['feedback'] or '(未解析到反馈内容)'}\n"
        "\n—— 邮件信息 ——\n"
        f"邮件主题：{item['subject']}\n"
        f"发件人：{item['from_name']} <{item['from_addr']}>\n"
        f"接收时间：{item['date']}\n"
        f"邮件ID：{item['message_id']}"
    )


def build_none_message():
    today = now().strftime("%Y-%m-%d")
    return f"今日无问责（王喜泽区域 · {today} 未检索到符合条件的宾客严重投诉问责邮件）"


def send_notification(cfg, title, content):
    """按配置通道发送。workbuddy 模式仅返回，由自动化推送。"""
    ch = cfg["notifier"]
    if ch == "workbuddy":
        return  # 结果已写入 stdout JSON，由 WorkBuddy 自动化负责推送
    elif ch == "wecom":
        import urllib.request
        payload = json.dumps({"msgtype": "text",
                              "text": {"content": f"{title}\n\n{content}"}}).encode("utf-8")
        req = urllib.request.Request(cfg["wecom_webhook"], data=payload,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
    elif ch == "serverchan":
        import urllib.request
        url = f"https://sctapi.ftqq.com/{cfg['serverchan_sendkey']}.send"
        data = urllib.parse.urlencode({"title": title, "desp": content}).encode("utf-8")
        urllib.request.urlopen(url, data=data, timeout=10).read()
    elif ch == "pushplus":
        import urllib.request
        # PushPlus 默认按 HTML 渲染，\n 不换行，转成 <br>
        html_content = content.replace("\n", "<br>")
        url = "https://www.pushplus.plus/send"
        payload = json.dumps({"token": cfg["pushplus_token"], "title": title,
                              "content": html_content}).encode("utf-8")
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
    else:
        raise ValueError(f"未知通知通道: {ch}")


def _run_trigger_logic(cands, seen, dry_run=False, eod=False):
    """命中/兜底判定与通知。

    轮询运行（eod=False，工作日下午高频轮询）：
        - 只推送「王喜泽命中」，绝不发送"今日无问责"（避免每次轮询刷屏）。
        - 命中邮件按 Message-ID 去重，不会重复通知。
    收尾运行（eod=True，窗口结束时刻）：
        - 若当日全天无王喜泽命中，才发送一次"今日无问责"。
        - 若当日已发过命中通知（daily flag=hit）或已发过无问责（flag=none），跳过。
    """
    fresh = [c for c in cands if not c["seen"]]
    hits = [c for c in fresh if region_matches(c["region_manager"], CONFIG["target_region_manager"])]

    # 记录已处理（去重），避免重复通知（试运行不落盘）
    for c in fresh:
        if c["message_id"]:
            seen.add(c["message_id"])
    if not dry_run:
        save_seen(CONFIG["state_dir"], CONFIG["seen_file"], seen)

    today_str = now().strftime("%Y-%m-%d")
    flag = read_daily_flag(CONFIG["state_dir"], today_str) if not dry_run else ""

    if hits:
        if CONFIG["aggregate"]:
            combined = "\n\n".join(build_hit_message(h) for h in hits)
            title = f"宾客严重投诉问责 · 王喜泽区域（{len(hits)} 条）"
            if not dry_run:
                send_notification(CONFIG, title, combined)
            out = {"status": "match", "count": len(hits), "message": combined, "items": hits}
        else:
            msgs = [build_hit_message(h) for h in hits]
            for m in msgs:
                if not dry_run:
                    send_notification(CONFIG, "宾客严重投诉问责 · 王喜泽区域", m)
            out = {"status": "match", "count": len(hits), "messages": msgs, "items": hits}
        log(f"命中 {len(hits)} 条，已生成通知。")
        if not dry_run:
            write_daily_flag(CONFIG["state_dir"], today_str, "hit")
        print(json.dumps(out, ensure_ascii=False, default=str))
        return

    # 无命中
    if CONFIG["nomatch_when"] == "any" and len(fresh) > 0:
        log("存在其它区域经理的问责邮件，按 nomatch_when=any 不发送无问责提示。")
        print(json.dumps({"status": "no_target_but_has_others", "count": 0,
                          "message": "（存在其它区域经理问责邮件，未触发王喜泽通知）"},
                         ensure_ascii=False, default=str))
        return

    if eod:
        if flag == "hit":
            log("当日已有命中通知，跳过无问责提示。")
            print(json.dumps({"status": "skipped_none", "reason": "already_hit_today"}, ensure_ascii=False))
            return
        if flag == "none":
            log("当日无问责提示已发送，跳过。")
            print(json.dumps({"status": "skipped_none", "reason": "already_sent"}, ensure_ascii=False))
            return
        none_msg = build_none_message()
        if not dry_run:
            send_notification(CONFIG, "今日无问责", none_msg)
        log("无命中，已生成兜底提示。")
        if not dry_run:
            write_daily_flag(CONFIG["state_dir"], today_str, "none")
        print(json.dumps({"status": "none", "count": 0, "message": none_msg},
                         ensure_ascii=False, default=str))
        return

    # 轮询运行且无命中：静默，不发任何通知（避免刷屏）
    log("轮询：当日暂未检索到王喜泽命中（静默）。")
    print(json.dumps({"status": "no_match_poll", "count": 0}, ensure_ascii=False))


def inspect_mode(cfg):
    """打印候选邮件的提取字段，便于校准正则（不发送通知）。"""
    seen = load_seen(cfg["state_dir"], cfg["seen_file"])
    cands = fetch_candidates(cfg, seen)
    print(json.dumps({
        "mode": "inspect",
        "candidate_count": len(cands),
        "candidates": [{
            "subject": c["subject"], "from": f"{c['from_name']} <{c['from_addr']}>",
            "store": c["store"], "region_manager": c["region_manager"],
            "feedback": c["feedback"],
            "region_match": region_matches(c["region_manager"], cfg["target_region_manager"]),
        } for c in cands]
    }, ensure_ascii=False, indent=2))


def load_sample_message(path):
    """载入本地样例邮件（.eml 直接解析；.html/.htm 包成带 HTML 部件的邮件）。
    统一按字节读取并用 message_from_bytes 解析，避免中文被重新编码成 \\uXXXX 转义。"""
    with open(path, "rb") as f:
        content = f.read()
    if path.lower().endswith((".eml",)):
        return email.message_from_bytes(content, policy=email.policy.default)
    # HTML 样例：构造一封最小邮件（用字节写入，避免中文转义）
    msg = email.message.EmailMessage()
    msg["From"] = "品质中心 <quality@dossen.com>"
    msg["To"] = "me@qq.com"
    msg["Subject"] = "宾客严重投诉问责通报（样例）"
    msg["Date"] = email.utils.format_datetime(now())
    msg["Message-ID"] = "<sample-local@dossen.com>"
    msg.set_content("请查看 HTML 内容")
    msg.add_alternative(content.decode("utf-8", errors="replace"), subtype="html")
    return msg


def collect_from_eml_dir(eml_dir, cfg, seen):
    """从目录下所有 .eml 文件收集候选 item（qq-mail 连接器后端用）。

    qq-mail 连接器拉取的邮件被落盘为 .eml 后，复用 process_message 执行
    A/B/C 筛选与 HTML 表格/正则解析，与 IMAP 后端完全一致。"""
    cands = []
    files = sorted(glob.glob(os.path.join(eml_dir, "*.eml")))
    log(f"从 {eml_dir} 载入 {len(files)} 个 .eml 候选邮件…")
    for fp in files:
        try:
            msg = load_sample_message(fp)
        except Exception as e:
            log(f"载入 {fp} 失败: {e}")
            continue
        cands.extend(process_message(msg, cfg, seen))
    return cands


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="强制运行（忽略非工作日跳过）")
    ap.add_argument("--inspect", action="store_true", help="仅检查并打印提取字段，不发送")
    ap.add_argument("--verbose", action="store_true", help="输出调试信息")
    ap.add_argument("--date", help="试运行：伪装当前日期 YYYY-MM-DD（如 2026-08-14）")
    ap.add_argument("--dry-run", action="store_true",
                    help="试运行：不连 IMAP、不写去重缓存，用 --sample/--eml-dir 走完整流程")
    ap.add_argument("--sample", help="试运行样例文件路径（.eml 或 .html），用于 --dry-run")
    ap.add_argument("--eml-dir", help="从指定目录下所有 .eml 文件收集候选（qq-mail 连接器后端）")
    ap.add_argument("--eod", action="store_true",
                    help="收尾运行：当日无命中时才发送一次\"今日无问责\"（轮询运行请勿加此参数）")
    args = ap.parse_args()

    if args.date:
        try:
            global NOW_OVERRIDE
            NOW_OVERRIDE = datetime.datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(json.dumps({"status": "error", "message": "日期格式应为 YYYY-MM-DD"}, ensure_ascii=False))
            sys.exit(1)
        log(f"已伪装当前日期为 {args.date}（{WEEKDAY_CN[NOW_OVERRIDE.weekday()]}）")

    # inspect：默认走 IMAP（需凭证）；若给了 --eml-dir 则改从目录检查
    if args.inspect:
        if args.eml_dir:
            seen = set()
            cands = collect_from_eml_dir(args.eml_dir, CONFIG, seen)
            print(json.dumps({
                "mode": "inspect-eml-dir", "candidate_count": len(cands),
                "candidates": [{
                    "subject": c["subject"], "from": f"{c['from_name']} <{c['from_addr']}>",
                    "store": c["store"], "region_manager": c["region_manager"],
                    "feedback": c["feedback"],
                    "region_match": region_matches(c["region_manager"], CONFIG["target_region_manager"]),
                } for c in cands]
            }, ensure_ascii=False, indent=2))
        else:
            inspect_mode(CONFIG)
        return

    # 工作日闸门（试运行 / eml-dir / 真实运行 均遵守，--force 可强制）
    if not is_business_day() and not args.force:
        log("非工作日，跳过（--force 可强制）。")
        print(json.dumps({"status": "skipped", "reason": "weekend"}, ensure_ascii=False))
        return

    # 试运行必须给出数据来源
    if args.dry_run and not (args.sample or args.eml_dir):
        print(json.dumps({"status": "error", "message": "试运行需提供 --sample 或 --eml-dir"}, ensure_ascii=False))
        sys.exit(1)

    # 收集候选：优先级 eml-dir > sample > IMAP
    seen = set() if args.dry_run else load_seen(CONFIG["state_dir"], CONFIG["seen_file"])
    if args.eml_dir:
        if not os.path.isdir(args.eml_dir):
            print(json.dumps({"status": "error", "message": f"目录不存在: {args.eml_dir}"}, ensure_ascii=False))
            sys.exit(1)
        cands = collect_from_eml_dir(args.eml_dir, CONFIG, seen)
    elif args.sample:
        if not os.path.exists(args.sample):
            print(json.dumps({"status": "error", "message": "样例文件不存在"}, ensure_ascii=False))
            sys.exit(1)
        msg = load_sample_message(args.sample)
        cands = process_message(msg, CONFIG, set())
    else:
        # 后端一：IMAP 直连（需 .env 凭证）
        try:
            cands = fetch_candidates(CONFIG, seen)
        except Exception as e:
            log(f"拉取/筛选失败: {e}")
            print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
            sys.exit(1)

    # 试运行：先打印候选预览
    if args.dry_run:
        print(json.dumps({"mode": "dry-run", "candidate_count": len(cands),
                          "candidates": [{
                              "store": c["store"], "region_manager": c["region_manager"],
                              "feedback": c["feedback"],
                              "region_match": region_matches(c["region_manager"], CONFIG["target_region_manager"]),
                          } for c in cands]}, ensure_ascii=False, indent=2, default=str))

    # 命中/兜底判定与通知（dry-run 不写 seen 缓存、不真正发送）
    _run_trigger_logic(cands, seen, dry_run=args.dry_run, eod=args.eod)


if __name__ == "__main__":
    main()
