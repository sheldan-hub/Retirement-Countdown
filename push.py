#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
退休倒计时 · Server酱微信推送脚本
适用于 GitHub Actions 定时执行，也可本地运行。

环境变量：
    SERVERCHAN_KEY  (必填) Server酱 SendKey，从 GitHub Secrets 读取
    RETIRE_DATE     (可选) 退休日期，格式 YYYY-MM-DD，默认 2036-08-30
    PUSH_TITLE_TPL  (可选) 标题模板，{days} 会被替换成剩余天数

用法：
    python3 push.py              # 正常推送
    python3 push.py --dry-run    # 只打印消息内容，不实际推送（本地测试用）
"""

import datetime
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ---------------------- 配置 ----------------------
SENDKEY = os.environ.get("SERVERCHAN_KEY", "").strip()
RETIRE_DATE = os.environ.get("RETIRE_DATE", "2036-08-30").strip()
TITLE_TPL = os.environ.get("PUSH_TITLE_TPL", "退休倒计时 · 还剩 {days} 天")
MAX_RETRY = 3          # 失败重试次数
RETRY_INTERVAL = 15    # 重试间隔（秒）
HTTP_TIMEOUT = 30      # 单次请求超时（秒）

WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

QUOTES = [
    "认真工作的日子，也是离理想生活更近的日子。",
    "倒计时减一，存款和阅历都在加一。",
    "今天的努力，是给未来退休的自己发的工资。",
    "日子不慌不忙，我们来日方长。",
    "生活明朗，万物可爱，退休可期。",
    "把每一个平凡的日子，过成通往自由的路。",
    "上班是为了下班，奋斗是为了退休，冲鸭！",
    "今天也是距离自由更近的一天，加油！",
    "时间会回答成长，成长会回答梦想。",
    "慢慢来，比较快。退休的沙滩不会跑。",
    "自由不是终点，是每一天的存款。",
    "距离沙滩、午睡和不用早起，又近了一天。",
]


# ---------------------- 工具函数 ----------------------
def log(msg):
    """带时间戳打印，GitHub Actions 日志里方便定位"""
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def calc_days():
    """计算今天到退休日的剩余天数"""
    retire = datetime.date.fromisoformat(RETIRE_DATE)
    today = datetime.date.today()
    return (retire - today).days, today, retire


def build_message(days, today, retire):
    """构造标题和 Markdown 正文"""
    weekday = WEEKDAY_CN[today.weekday()]
    quote = random.choice(QUOTES)

    title = TITLE_TPL.format(days=days)

    if days > 0:
        total_years = days / 365.25
        weeks = days // 7
        desp = (
            f"## 🏝 距离退休还有 **{days}** 天\n\n"
            f"**今天是 {today.year} 年 {today.month} 月 {today.day} 日（{weekday}）**\n\n"
            f"---\n\n"
            f"| 维度 | 数值 |\n"
            f"| --- | --- |\n"
            f"| 剩余天数 | {days} 天 |\n"
            f"| 约合年数 | {total_years:.2f} 年 |\n"
            f"| 完整周数 | {weeks} 周 |\n"
            f"| 目标日期 | {retire.isoformat()} |\n\n"
            f"---\n\n"
            f"> {quote}\n"
        )
    else:
        desp = (
            f"## 🎉 已达成退休目标！\n\n"
            f"今天是 {today.year} 年 {today.month} 月 {today.day} 日（{weekday}）\n\n"
            f"距离 {retire.isoformat()} 已过去 **{-days}** 天，恭喜自由！\n\n"
            f"> {quote}\n"
        )
    return title, desp


def send_once(title, desp):
    """调用 Server酱 推送一次，返回 (是否成功, 详情)"""
    url = f"https://sctapi.ftqq.com/{SENDKEY}.send"
    payload = urllib.parse.urlencode({"title": title, "desp": desp}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return False, f"HTTP错误 {e.code}，返回体：{body}"
    except Exception as e:
        return False, f"请求异常：{type(e).__name__}: {e}"

    if result.get("code") == 0:
        return True, "code=0"
    return False, f"接口返回：{json.dumps(result, ensure_ascii=False)}"


def send_with_retry(title, desp):
    """带重试的推送"""
    for attempt in range(1, MAX_RETRY + 1):
        ok, detail = send_once(title, desp)
        if ok:
            log(f"✅ 推送成功（第 {attempt} 次尝试）")
            return True
        log(f"❌ 第 {attempt}/{MAX_RETRY} 次失败：{detail}")
        if attempt < MAX_RETRY:
            log(f"   等待 {RETRY_INTERVAL} 秒后重试…")
            time.sleep(RETRY_INTERVAL)
    return False


# ---------------------- 主流程 ----------------------
def main():
    dry_run = "--dry-run" in sys.argv

    days, today, retire = calc_days()
    title, desp = build_message(days, today, retire)

    log(f"今天：{today.isoformat()}（{WEEKDAY_CN[today.weekday()]}）")
    log(f"退休日：{retire.isoformat()}")
    log(f"剩余天数：{days} 天")

    if dry_run:
        log("—— dry-run 模式，以下是将要推送的内容 ——")
        print(f"\n【标题】{title}\n")
        print("【正文】")
        print(desp)
        return 0

    if not SENDKEY:
        log("✗ 未设置环境变量 SERVERCHAN_KEY，无法推送")
        log("  请在 GitHub 仓库 Settings → Secrets → Actions 中添加 SERVERCHAN_KEY")
        return 1

    if not SENDKEY.startswith("SCT") and not SENDKEY.startswith("sct"):
        log(f"⚠ 警告：SendKey 格式看起来不像 Server酱 Turbo 版（通常以 SCT 开头）")

    log(f"开始推送，标题：{title}")
    ok = send_with_retry(title, desp)

    if ok:
        log(f"全部完成：距离退休还有 {days} 天")
        return 0
    log("✗ 重试后仍失败，请查看上方错误信息")
    return 1


if __name__ == "__main__":
    sys.exit(main())
