#!/usr/bin/env python3
"""A 股数据抓取脚本（自包含版）— 仅依赖 requests，不依赖本工程。

供 Hermes 在 A 股投研分析时获取真实数据素材。数据全部来自免费直连的公开
HTTP 接口（新浪/腾讯/东财/同花顺/百度），无需任何 API key。本脚本可独立
运行，把整个 skills 目录拷贝到其他环境即可使用。

用法:
  python fetch_data.py 600519                        # 全量数据，分析日 = 今天
  python fetch_data.py 贵州茅台 --date 2026-05-12    # 中文名 + 历史分析日
  python fetch_data.py 600519 --sections quote,kline,reports,news
  python fetch_data.py 600519 --lookback 120 --out report_data.md

数据块（--sections）:
  quote       实时行情/估值（腾讯）         kline       日K线（新浪，OHLCV）
  reports     财报三表（新浪，按已公布截断） forecast    机构一致预期（同花顺）
  news        个股新闻（东财+新浪）         global_news 财经快讯（财联社+东财）
  hot_stocks  热门强势股题材（同花顺）      lhb         龙虎榜（东财）
  lockup      限售解禁（东财）              shareholders 股东动态（东财）
  industry    行业对比（东财）              fundflow    资金流（东财，历史按分析日截断）
  concept     概念板块（百度）              northbound  北向资金（同花顺，仅实时）
  overview    概览（名称+行情）

注意:
  - 中文名经新浪 suggest 搜索解析为 6 位代码；输入 6 位代码最稳。
  - 历史分析日: 实时估值/一致预期/北向等"无历史时点值"数据会输出快照告警，
    不得当作分析日当天的事实。
  - 东财接口带节流（默认 ≥1s，可用环境变量 EM_MIN_INTERVAL 调大）。
"""

import argparse
import calendar
import datetime
import json
import os
import random
import re
import sys
import time
import urllib.parse

try:
    import requests
except ImportError:
    print(
        "[错误] 缺少依赖 requests。请先安装：pip install requests",
        file=sys.stderr,
    )
    sys.exit(2)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA})

# ── 东财防封：串行节流 + 会话复用（仅东财接口）─────────────────────────
EM_MIN_INTERVAL = float(os.environ.get("EM_MIN_INTERVAL", "1.0"))
_em_last = [0.0]


def em_get(url, params=None, headers=None, timeout=15):
    """东财统一请求入口：自动节流，避免批量抓取被封 IP。"""
    wait = EM_MIN_INTERVAL - (time.time() - _em_last[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        return SESSION.get(url, params=params, headers=headers, timeout=timeout)
    finally:
        _em_last[0] = time.time()


# ── 标的解析 ─────────────────────────────────────────────────────────
def market_prefix(code):
    """6 位代码 → 市场前缀（腾讯/新浪用）。92 开头属北交所新号段。"""
    if code.startswith("92"):
        return "bj"
    if code.startswith(("6", "9")):
        return "sh"
    if code.startswith("8"):
        return "bj"
    return "sz"


def normalize_code(raw):
    """校验并规整 6 位 A 股代码；拒绝港股/美股。"""
    s = raw.strip().lower()
    s = re.sub(r"\.(sh|sz|bj)$", "", s)
    s = re.sub(r"^(sh|sz|bj)", "", s)
    if not re.fullmatch(r"\d{6}", s):
        raise ValueError(f"无效的 A 股代码: {raw!r}（需要 6 位数字，如 600519）")
    return s


def resolve_ticker(user_input):
    """中文名/带前缀/6 位代码 → 6 位代码。中文名走新浪 suggest 搜索。"""
    s = user_input.strip()
    if re.fullmatch(r"(sh|sz|bj)?\d{6}", s.lower().replace(".", "")):
        return normalize_code(s)
    # 中文名：新浪 suggest 搜索
    url = "https://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key=" + urllib.parse.quote(s)
    try:
        r = SESSION.get(url, timeout=12)
        r.encoding = "gbk"
        m = re.search(r'="(.*)"', r.text)
        if not m or not m.group(1):
            raise ValueError(f"找不到股票 '{s}'：请输入 6 位代码或完整名称")
        matches = []
        for row in m.group(1).split(";"):
            if not row:
                continue
            parts = row.split(",")
            if len(parts) >= 4 and re.fullmatch(r"\d{6}", parts[2]):
                matches.append((parts[0], parts[2], parts[3]))
        if not matches:
            raise ValueError(f"找不到股票 '{s}'")
        # 精确名优先，其次唯一子串
        exact = [m for m in matches if m[0] == s]
        pool = exact or matches
        if len(pool) == 1:
            return pool[0][1]
        cands = ", ".join(f"{n}({c})" for n, c, _ in pool[:8])
        raise ValueError(f"'{s}' 匹配到多只股票: {cands}，请输入完整名称或 6 位代码")
    except requests.RequestException as e:
        raise ValueError(f"名称搜索失败（网络/接口不可达）: {e}")


# ── 各数据块实现 ─────────────────────────────────────────────────────
def fetch_quote(code, curr_date=None):
    """腾讯实时行情/估值。返回文本；历史分析日会附快照告警。"""
    out = []
    if curr_date and curr_date < datetime.date.today().isoformat():
        out.append("⚠️ 快照告警：实时估值与行情只有\"此刻\"的值，"
                   f"不是 {curr_date} 当天的数据，不得当作分析日当天的事实。\n")
    url = "https://qt.gtimg.cn/q=" + market_prefix(code) + code
    r = SESSION.get(url, timeout=12)
    r.encoding = "gbk"
    for line in r.text.strip().split(";"):
        if '"' not in line:
            continue
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        def f(idx, default=0.0):
            try:
                return float(vals[idx]) if vals[idx] else default
            except (ValueError, IndexError):
                return default
        out.append(f"Name: {vals[1]}")
        out.append(f"Code: {vals[2]}")
        out.append(f"Price: {vals[3]}")
        out.append(f"Last Close: {vals[4]}")
        out.append(f"Open: {vals[5]}")
        out.append(f"Change: {f(32)}%")
        out.append(f"High: {f(33)}")
        out.append(f"Low: {f(34)}")
        out.append(f"Turnover Rate: {f(38)}%")
        out.append(f"PE (TTM): {f(39)}")
        out.append(f"PE (Static): {f(52)}")
        out.append(f"PB: {f(46)}")
        out.append(f"Market Cap (100M CNY): {f(44)}")
        out.append(f"Float Market Cap (100M CNY): {f(45)}")
        out.append(f"Limit Up: {f(47)}")
        out.append(f"Limit Down: {f(48)}")
    return "\n".join(out) if out else f"腾讯行情未返回数据（{code}）"


def fetch_kline(code, start_date, end_date):
    """新浪日 K 线（OHLCV）。"""
    url = ("http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
           "CN_MarketData.getKLineData")
    params = {"symbol": market_prefix(code) + code, "scale": "240",
              "ma": "no", "datalen": "800"}
    r = SESSION.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data:
        return "K线数据为空（非交易时段或代码无效）"
    start_dt = datetime.date.fromisoformat(start_date)
    end_dt = datetime.date.fromisoformat(end_date)
    rows = []
    for item in data:
        d = item["day"]
        if start_dt <= datetime.date.fromisoformat(d) <= end_dt:
            rows.append(f"{d},{item['open']},{item['high']},{item['low']},"
                        f"{item['close']},{item['volume']}")
    if not rows:
        return f"{start_date} 至 {end_date} 区间内无 K 线数据"
    head = f"# K线 {code} {start_date} ~ {end_date}（{len(rows)} 条，新浪）\n"
    head += "Date,Open,High,Low,Close,Volume\n"
    return head + "\n".join(rows)


def _report_deadline(report_date):
    """报告期（月末）→ 法定披露截止日：一季报/三季报 1 个月、半年报 2 个月、年报 4 个月。"""
    lag = {3: 1, 6: 2, 9: 1, 12: 4}.get(report_date.month, 4)
    m = report_date.month + lag
    y = report_date.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    return datetime.date(y, m, calendar.monthrange(y, m)[1])


def _report_available(report_date, publish_date, update_time, curr_date):
    """按分析日判断某期财报是否已公布（未来函数防护，语义同工程版）。

    - 公告日(publish_date, YYYYMMDD)严格早于分析日，或入库时间(update_time,
      unix秒, 北京时间)早于分析日当天 → 已公布；
    - 两个日期都缺失或晚于报告期一年以上（原始日期被后续报表改写丢失）→
      按法定披露截止日判断；
    - 其余情况（如逾期公司）一律视为未公布，宁可晚放不可早放。
    """
    rd = report_date
    cd = datetime.date.fromisoformat(curr_date)
    published = None
    if publish_date:
        try:
            p = datetime.datetime.strptime(str(publish_date), "%Y%m%d").date()
            if p > rd:  # 上市前的数据（公告日不晚于报告期）不可信
                published = p
        except ValueError:
            pass
    updated = None
    if update_time:
        try:
            updated = (datetime.datetime.fromtimestamp(
                int(update_time), tz=datetime.timezone(datetime.timedelta(hours=8))
            ).date())
        except (ValueError, TypeError, OSError):
            pass
    year_later = (datetime.date(rd.year + 1, rd.month, rd.day)
                  if not (rd.month == 2 and rd.day == 29)
                  else datetime.date(rd.year + 1, 2, 28))
    original_lost = ((published is None or published >= year_later) and
                     (updated is None or updated >= year_later))
    return ((published is not None and published < cd) or
            (updated is not None and updated < cd) or
            (original_lost and _report_deadline(rd) < cd))


def fetch_reports(code, curr_date, max_periods=4):
    """新浪财报三表（资产负债表/利润表/现金流量表），按已公布截断。

    输出转置表格：科目 × 最近 N 期，便于横向对比。
    """
    prefix = "sh" if code.startswith("6") else "sz"
    url = ("https://quotes.sina.cn/cn/api/openapi.php/"
           "CompanyFinanceService.getFinanceReport2022")
    out = []
    for label, source in [("资产负债表", "fzb"), ("利润表", "lrb"), ("现金流量表", "llb")]:
        try:
            params = {"paperCode": prefix + code, "source": source, "type": "0",
                      "page": "1", "num": "40"}
            r = SESSION.get(url, params=params,
                            headers={"User-Agent": UA, "Referer": "https://finance.sina.com.cn/"},
                            timeout=15)
            d = r.json()
            report_list = (d.get("result", {}).get("data", {}).get("report_list") or {})
            periods = []
            for report_date, payload in report_list.items():
                if not isinstance(payload, dict):
                    continue
                rd = datetime.date.fromisoformat(report_date)
                if rd > datetime.date.fromisoformat(curr_date):
                    continue
                if not _report_available(rd, payload.get("publish_date"),
                                         payload.get("update_time"), curr_date):
                    continue
                fields = {}
                parent = None
                for item in payload.get("data") or []:
                    if not isinstance(item, dict) or not item.get("item_title"):
                        continue
                    title = item["item_title"]
                    if item.get("item_display") != "缩进":
                        parent = title
                    elif parent:
                        title = f"{parent}-{title}"
                    if title in fields:
                        title = f"{title}({len(fields)})"
                    fields[title] = item.get("item_value")
                periods.append((report_date, fields))
            periods.sort(key=lambda x: x[0], reverse=True)
            periods = periods[:max_periods]
            if not periods:
                out.append(f"\n## {label}（{code}）：截至 {curr_date} 无已公布数据")
                continue
            out.append(f"\n## {label}（{code}，最近 {len(periods)} 期，按已公布截断）")
            headers = ["科目"] + [p[0] for p in periods]
            out.append("| " + " | ".join(headers) + " |")
            out.append("|" + "---|" * len(headers))
            all_keys = []
            for _, fields in periods:
                for k in fields:
                    if k not in all_keys:
                        all_keys.append(k)
            for k in all_keys:
                row = [k] + [str(p[1].get(k, "")) for _, p in zip(periods, periods)]
                # 用字段索引对应期次
                row = [k]
                for _, fields in periods:
                    row.append(str(fields.get(k, "")))
                out.append("| " + " | ".join(row) + " |")
        except Exception as e:  # noqa: BLE001
            out.append(f"\n## {label}（{code}）：[数据获取失败] {type(e).__name__}: {e}")
    return "\n".join(out)


def _parse_html_tables(html):
    """极简 HTML 表格解析（不依赖 pandas/bs4）：返回 [{title, headers, rows}].

    每个表格 dict: title(caption 文本, 可为空), headers(list[str]), rows。
    表格无 <th> 时 headers 取首行，rows 从第二行开始。
    """
    tables = []
    for tbl_match in re.finditer(r"<table[^>]*>(.*?)</table>", html, re.S | re.I):
        body = tbl_match.group(1)
        cap_m = re.search(r"<caption[^>]*>(.*?)</caption>", body, re.S | re.I)
        title = ""
        if cap_m:
            title = re.sub(r"<[^>]+>", "", cap_m.group(1))
            title = re.sub(r"\s+", " ", title).strip()
        rows = []
        for tr_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", body, re.S | re.I):
            cells = []
            for cell_match in re.finditer(r"<t[dh][^>]*>(.*?)</t[dh]>",
                                          tr_match.group(1), re.S | re.I):
                txt = re.sub(r"<[^>]+>", "", cell_match.group(1))
                txt = re.sub(r"&nbsp;?", " ", txt)
                txt = re.sub(r"\s+", " ", txt).strip()
                cells.append(txt)
            if any(cells):
                rows.append(cells)
        if not rows:
            continue
        first = rows[0]
        # 是否首行是表头（含年度/机构/均值等列名）
        head_kw = ("年度", "均值", "最小值", "机构数", "预测")
        is_header = any(any(k in c for k in head_kw) for c in first)
        if is_header:
            tables.append({"title": title, "headers": first, "rows": rows[1:]})
        else:
            tables.append({"title": title, "headers": [], "rows": rows})
    return tables


def fetch_forecast(code, curr_date):
    """机构一致预期：同花顺 F10 worth 页的每股收益/净利润预测汇总表。

    仅当前一致预期（无历史时点值），历史分析日附快照告警。
    """
    out = []
    if curr_date and curr_date < datetime.date.today().isoformat():
        out.append("⚠️ 快照告警：一致预期是\"当前\"的机构预测汇总，"
                   f"不是 {curr_date} 当天的数据，不得当作分析日当天的事实。\n")
    url = f"https://basic.10jqka.com.cn/new/{code}/worth.html"
    r = SESSION.get(url, headers={"Referer": "https://basic.10jqka.com.cn/"}, timeout=15)
    r.encoding = "gbk"
    tables = _parse_html_tables(r.text)
    if not tables:
        return "\n".join(out) + f"同花顺 worth 页无表格数据（{code}）"
    found = False
    for tbl in tables:
        head_text = (tbl["title"] + " " + " ".join(tbl["headers"])
                     + (" " + " ".join(tbl["rows"][0]) if tbl["rows"] else ""))
        # 每股收益预测表（单位：元）
        if "每股收益" in head_text and "均值" in head_text:
            found = True
            out.append("## 一致预期 · 每股收益（元，同花顺）")
            out.append("年度 | 预测机构数 | 最小值 | 均值 | 最大值 | 行业平均")
            out.append("--- | --- | --- | --- | --- | ---")
            for row in tbl["rows"]:
                if len(row) >= 6 and re.fullmatch(r"\d{4}", row[0].strip()):
                    out.append(" | ".join(row[:6]))
            out.append("")
        # 净利润预测表（单位：亿元）
        elif "净利润" in head_text and "均值" in head_text:
            found = True
            out.append("## 一致预期 · 净利润（亿元，同花顺）")
            out.append("年度 | 预测机构数 | 最小值 | 均值 | 最大值 | 行业平均")
            out.append("--- | --- | --- | --- | --- | ---")
            for row in tbl["rows"]:
                if len(row) >= 6 and re.fullmatch(r"\d{4}", row[0].strip()):
                    out.append(" | ".join(row[:6]))
            out.append("")
    if not found:
        return "\n".join(out) + f"同花顺 worth 页未找到预测表（{code}）"
    return "\n".join(out)


def fetch_hot_stocks(curr_date):
    """热门强势股题材：同花顺涨停/强势股事件库（编辑人工标注题材原因）。

    按日期取数（需近期交易日，历史太久返回空）。
    """
    out = [f"# 热门强势股题材（{curr_date}）",
           "# Source: 同花顺 涨停事件库（人工标注题材）", ""]
    url = ("http://zx.10jqka.com.cn/event/api/getharden/"
           f"date/{curr_date}/orderby/date/orderway/desc/charset/GBK/")
    r = SESSION.get(url, timeout=10)
    data = r.json()
    if data.get("errocode", 0) != 0:
        return "\n".join(out) + f"同花顺接口错误: {data.get('errormsg', 'unknown')}"
    rows = data.get("data") or []
    if not rows:
        return ("\n".join(out) + f"{curr_date} 无热股数据"
                "（可能非交易日，或该日期超出接口保留窗口）")
    for row in rows:
        code = row.get("code", "")
        name = row.get("name", "")
        reason = row.get("reason", "")
        out.append(f"- {code} {name} | 题材: {reason or '无标注'}")
    # 题材频率 TOP
    from collections import Counter
    all_tags = []
    for row in rows:
        for t in str(row.get("reason", "")).split("+"):
            t = t.strip()
            if t:
                all_tags.append(t)
    if all_tags:
        cnt = Counter(all_tags)
        out.append("\n## 题材热度 TOP15")
        for tag, n in cnt.most_common(15):
            out.append(f"  {tag}: {n} 只")
    return "\n".join(out)


def fetch_shareholders(code, curr_date):
    """股东动态：十大股东 + 十大流通股东 + 最新股东户数（东财 datacenter）。

    十大股东/流通股东按报告期（END_DATE）截断到分析日；股东户数只有最新
    一期（RPT_HOLDERNUMLATEST），历史分析日附告警。
    """
    suffix = "SH" if code.startswith("6") else ("BJ" if code.startswith(("8", "4", "92")) else "SZ")
    secucode = f"{code}.{suffix}"
    lines = [f"# 股东动态 | {code} | {curr_date}", "# Source: 东财 datacenter", ""]
    today = datetime.date.today().isoformat()

    def _fmt(v, nd=2):
        """数字字段规范化显示（去长尾小数），非数字原样返回。"""
        try:
            return f"{float(v):.{nd}f}"
        except (ValueError, TypeError):
            return str(v) if v not in (None, "") else ""

    def _cut(data):
        # 按分析日截断并按 END_DATE 降序
        kept = []
        for row in data:
            end = str(row.get("END_DATE", ""))[:10]
            if not end or end <= curr_date:
                kept.append(row)
        kept.sort(key=lambda x: str(x.get("END_DATE", "")), reverse=True)
        return kept

    try:
        data = _eastmoney_datacenter(
            "RPT_F10_EH_HOLDERS", f'(SECUCODE="{secucode}")',
            page_size=80, sort_columns="END_DATE,HOLDER_RANK", sort_types="-1,1")
        data = _cut(data)
        if data:
            end = str(data[0].get("END_DATE", ""))[:10]
            lines.append(f"## 十大股东（报告期 {end}）")
            lines.append("排名 | 股东 | 持股比例% | 变动")
            for row in data[:10]:
                rank = row.get("HOLDER_RANK", "")
                name = row.get("HOLDER_NAME", "")
                ratio = _fmt(row.get("HOLD_NUM_RATIO"))
                change = row.get("HOLD_NUM_CHANGE", "")
                lines.append(f"  {rank} | {name} | {ratio} | {change}")
        else:
            lines.append("## 十大股东：无数据")
    except Exception as e:  # noqa: BLE001
        lines.append(f"[十大股东获取失败] {type(e).__name__}: {e}")

    try:
        data = _eastmoney_datacenter(
            "RPT_F10_EH_FREEHOLDERS", f'(SECUCODE="{secucode}")',
            page_size=80, sort_columns="END_DATE,HOLDER_RANK", sort_types="-1,1")
        data = _cut(data)
        if data:
            end = str(data[0].get("END_DATE", ""))[:10]
            lines.append(f"\n## 十大流通股东（报告期 {end}）")
            lines.append("排名 | 股东 | 流通持股比例% | 变动")
            for row in data[:10]:
                rank = row.get("HOLDER_RANK", "")
                name = row.get("HOLDER_NAME", "")
                ratio = _fmt(row.get("FREE_HOLDNUM_RATIO"))
                change = row.get("HOLD_NUM_CHANGE", "")
                lines.append(f"  {rank} | {name} | {ratio} | {change}")
        else:
            lines.append("\n## 十大流通股东：无数据")
    except Exception as e:  # noqa: BLE001
        lines.append(f"\n[十大流通股东获取失败] {type(e).__name__}: {e}")

    try:
        data = _eastmoney_datacenter(
            "RPT_HOLDERNUMLATEST", f'(SECUCODE="{secucode}")',
            page_size=1, sort_columns="END_DATE", sort_types="-1")
        if data:
            row = data[0]
            end = str(row.get("END_DATE", ""))[:10]
            lines.append(f"\n## 股东户数（最新一期 {end}）")
            if curr_date < today:
                lines.append("⚠️ 快照告警：股东户数只有\"最新一期\"，"
                             f"不是 {curr_date} 当天的数据，不得当作分析日当天的事实。")
            hnum = row.get("HOLDER_NUM", "")
            pre = row.get("PRE_HOLDER_NUM", "")
            ratio = _fmt(row.get("HOLDER_NUM_RATIO"))
            reason = row.get("CHANGE_REASON", "")
            lines.append(f"  股东户数: {hnum} | 上期: {pre} | 变化: {ratio}%")
            if reason:
                lines.append(f"  变动原因: {reason}")
            # 户均持股变化率（INTERVAL_CHRATE，>0 表示筹码集中）
            ich = row.get("INTERVAL_CHRATE", "")
            if ich not in ("", None):
                try:
                    v = float(ich)
                    sig = "筹码集中(看多)" if v > 0 else ("筹码分散(看空)" if v < 0 else "持平")
                    lines.append(f"  户均持股变化: {v:.2f}%（{sig}）")
                except (ValueError, TypeError):
                    pass
        else:
            lines.append("\n## 股东户数：无数据")
    except Exception as e:  # noqa: BLE001
        lines.append(f"\n[股东户数获取失败] {type(e).__name__}: {e}")

    return "\n".join(lines)


def fetch_news(code, start_date, end_date):
    """个股新闻：东财搜索为主，新浪兜底。按时间窗口过滤。"""
    articles = []
    source_label = ""
    # 东财搜索
    try:
        url = "https://search-api-web.eastmoney.com/search/jsonp"
        inner = {
            "uid": "", "keyword": code, "type": ["cmsArticleWebOld"],
            "client": "web", "clientType": "web", "clientVersion": "curr",
            "param": {"cmsArticleWebOld": {
                "searchScope": "default", "sort": "default", "pageIndex": 1,
                "pageSize": 20, "preTag": "", "postTag": ""}},
        }
        resp = em_get(url, params={"cb": "callback",
                                   "param": json.dumps(inner, ensure_ascii=False), "_": "1"},
                      headers={"Referer": "https://so.eastmoney.com/"}, timeout=15)
        text = resp.text
        text = text[text.index("(") + 1: text.rindex(")")]
        data = json.loads(text)
        for item in data.get("result", {}).get("cmsArticleWebOld", []):
            articles.append({"title": item.get("title", ""),
                             "content": item.get("content", ""),
                             "time": item.get("date", ""),
                             "source": item.get("mediaName", "东方财富"),
                             "url": item.get("url", "")})
        source_label = "东方财富"
    except Exception as e:  # noqa: BLE001
        articles = []
    # 新浪兜底
    if not articles:
        try:
            url = (f"https://vip.stock.finance.sina.com.cn/corp/view/"
                   f"vCB_AllNewsStock.php?symbol={market_prefix(code)}{code}&Page=1")
            resp = SESSION.get(url, headers={"Referer": "https://finance.sina.com.cn/"}, timeout=15)
            resp.encoding = "gb2312"
            rows = re.findall(
                r"(\d{4}-\d{2}-\d{2})\s*(?:&nbsp;)*(\d{2}:\d{2})\s*(?:&nbsp;)*"
                r"<a[^>]+href='([^']+)'[^>]*>([^<]+)</a>", resp.text)
            for date_str, time_str, link, title in rows[:20]:
                articles.append({"title": title.strip(), "content": "",
                                 "time": f"{date_str} {time_str}",
                                 "source": "新浪财经", "url": link})
            source_label = "新浪财经"
        except Exception as e:  # noqa: BLE001
            pass
    if not articles:
        return f"{code} 无相关新闻（东财/新浪均未取到）"
    start_dt = datetime.date.fromisoformat(start_date)
    end_dt = datetime.date.fromisoformat(end_date)
    out = []
    for art in articles:
        try:
            pub = datetime.date.fromisoformat(art["time"][:10])
            if not (start_dt <= pub <= end_dt):
                continue
        except ValueError:
            pass
        title = art["title"]
        content = (art.get("content") or "")[:300]
        src = art.get("source") or source_label
        out.append(f"### {title} (source: {src})")
        if content:
            out.append(content + ("..." if len(art.get("content") or "") > 300 else ""))
        if art.get("url"):
            out.append(f"Link: {art['url']}")
        out.append("")
    if not out:
        return f"{code} 在 {start_date}~{end_date} 区间无新闻"
    return f"## {code} 新闻 {start_date} ~ {end_date}:\n\n" + "\n".join(out)


def fetch_global_news(curr_date, look_back_days=7, limit=10):
    """财经快讯：财联社 + 东财 7x24。"""
    all_news = []
    try:
        r = SESSION.get("https://www.cls.cn/nodeapi/telegraphList",
                        params={"rn": str(limit), "page": "1"},
                        headers={"Referer": "https://www.cls.cn/"}, timeout=10)
        d = r.json()
        for item in d.get("data", {}).get("roll_data", []):
            title = item.get("title", "") or item.get("brief", "")
            content = item.get("content", "") or item.get("brief", "")
            ctime = item.get("ctime", "")
            pub = ""
            if ctime:
                try:
                    pub = datetime.datetime.fromtimestamp(int(ctime)).strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError, OSError):
                    pub = str(ctime)
            all_news.append({"title": title, "content": content, "time": pub,
                             "source": "CLS Wire"})
    except Exception as e:  # noqa: BLE001
        pass
    try:
        params = {"client": "web", "biz": "web_724", "fastColumn": "102",
                  "sortEnd": "", "pageSize": str(limit),
                  "req_trace": str(uuid4())}
        r = em_get("https://np-weblist.eastmoney.com/comm/web/getFastNewsList",
                   params=params, headers={"Referer": "https://kuaixun.eastmoney.com/"},
                   timeout=10)
        d = r.json()
        for item in d.get("data", {}).get("fastNewsList", []):
            all_news.append({"title": item.get("title", ""),
                             "content": (item.get("summary", "") or "")[:200],
                             "time": item.get("showTime", ""),
                             "source": "Eastmoney Global"})
    except Exception as e:  # noqa: BLE001
        pass
    if not all_news:
        return "财经快讯获取失败（财联社/东财均不可达）"
    seen, unique = set(), []
    for n in all_news:
        if n["title"] not in seen:
            seen.add(n["title"])
            unique.append(n)
    out = []
    for n in unique[:limit]:
        out.append(f"### {n['title']} (source: {n['source']})")
        if n.get("content"):
            out.append(n["content"][:300])
        out.append("")
    return "## 财经快讯（财联社/东财）\n\n" + "\n".join(out)


def _eastmoney_datacenter(report_name, filter_str, page_size=50,
                          sort_columns="", sort_types="-1"):
    """东财数据中心统一查询（龙虎榜/解禁）。"""
    params = {"reportName": report_name, "columns": "ALL", "filter": filter_str,
              "pageNumber": "1", "pageSize": str(page_size),
              "sortColumns": sort_columns, "sortTypes": sort_types,
              "source": "WEB", "client": "WEB"}
    r = em_get("https://datacenter-web.eastmoney.com/api/data/v1/get",
               params=params, timeout=15)
    d = r.json()
    if d and d.get("result") and d["result"].get("data"):
        return d["result"]["data"]
    return []


def fetch_lhb(code, trade_date, look_back_days=30):
    """龙虎榜：上榜记录 + 最近一次买卖席位 TOP5 + 机构动向。"""
    end_dt = datetime.date.fromisoformat(trade_date)
    start_dt = end_dt - datetime.timedelta(days=look_back_days)
    lines = [f"# 龙虎榜数据 | {code} | {trade_date}（近{look_back_days}日）"]
    data = []
    try:
        data = _eastmoney_datacenter(
            "RPT_DAILYBILLBOARD_DETAILSNEW",
            filter_str=(f"(TRADE_DATE>='{start_dt.isoformat()}')"
                        f"(TRADE_DATE<='{trade_date}')(SECURITY_CODE=\"{code}\")"),
            page_size=50, sort_columns="TRADE_DATE", sort_types="-1")
        if not data:
            lines.append(f"\n近{look_back_days}日未上龙虎榜。")
        else:
            lines.append(f"\n## 上榜记录（{len(data)} 次）")
            lines.append("日期 | 原因 | 净买入(万) | 换手率")
            for row in data:
                net = round((row.get("BILLBOARD_NET_AMT") or 0) / 10000, 1)
                turn = round(float(row.get("TURNOVERRATE") or 0), 2)
                lines.append(f"  {str(row.get('TRADE_DATE', ''))[:10]} "
                             f"| {row.get('EXPLANATION', '')} | {net:.0f} | {turn:.2f}%")
    except Exception as e:  # noqa: BLE001
        lines.append(f"\n龙虎榜列表查询失败: {e}")
    buy_data = sell_data = []
    try:
        if data:
            latest = str(data[0].get("TRADE_DATE", ""))[:10]
            lines.append(f"\n## 最近上榜席位明细（{latest}）")
            buy_data = _eastmoney_datacenter(
                "RPT_BILLBOARD_DAILYDETAILSBUY",
                filter_str=f"(TRADE_DATE='{latest}')(SECURITY_CODE=\"{code}\")",
                page_size=10, sort_columns="BUY", sort_types="-1")
            if buy_data:
                lines.append("\n### 买入席位 TOP5")
                lines.append("营业部 | 买入(万) | 卖出(万) | 净额(万)")
                for row in buy_data[:5]:
                    lines.append(f"  {row.get('OPERATEDEPT_NAME', '')} "
                                 f"| {round((row.get('BUY') or 0)/10000, 1):.0f} "
                                 f"| {round((row.get('SELL') or 0)/10000, 1):.0f} "
                                 f"| {round((row.get('NET') or 0)/10000, 1):.0f}")
            sell_data = _eastmoney_datacenter(
                "RPT_BILLBOARD_DAILYDETAILSSELL",
                filter_str=f"(TRADE_DATE='{latest}')(SECURITY_CODE=\"{code}\")",
                page_size=10, sort_columns="SELL", sort_types="-1")
            if sell_data:
                lines.append("\n### 卖出席位 TOP5")
                lines.append("营业部 | 买入(万) | 卖出(万) | 净额(万)")
                for row in sell_data[:5]:
                    lines.append(f"  {row.get('OPERATEDEPT_NAME', '')} "
                                 f"| {round((row.get('BUY') or 0)/10000, 1):.0f} "
                                 f"| {round((row.get('SELL') or 0)/10000, 1):.0f} "
                                 f"| {round((row.get('NET') or 0)/10000, 1):.0f}")
    except Exception as e:  # noqa: BLE001
        lines.append(f"\n席位明细查询失败: {e}")
    try:
        inst_buy = sum((row.get("BUY") or 0) for row in (buy_data or [])
                       if str(row.get("OPERATEDEPT_CODE", "")) == "0")
        inst_sell = sum((row.get("SELL") or 0) for row in (sell_data or [])
                        if str(row.get("OPERATEDEPT_CODE", "")) == "0")
        if inst_buy or inst_sell:
            lines.append(f"\n## 机构动向")
            lines.append(f"  机构买入 {inst_buy/1e4:.0f} 万 | 卖出 {inst_sell/1e4:.0f} 万 "
                         f"| 净额 {(inst_buy-inst_sell)/1e4:.0f} 万")
    except Exception:  # noqa: BLE001
        pass
    return "\n".join(lines)


def fetch_lockup(code, trade_date, forward_days=90):
    """限售解禁：历史记录 + 未来待解禁。"""
    lines = [f"# 限售解禁日历 | {code} | {trade_date}"]
    try:
        hist = _eastmoney_datacenter("RPT_LIFT_STAGE",
                                     filter_str=f'(SECURITY_CODE="{code}")',
                                     page_size=15, sort_columns="FREE_DATE", sort_types="-1")
        if hist:
            lines.append(f"\n## 个股解禁记录（共 {len(hist)} 批）")
            lines.append("解禁时间 | 类型 | 解禁数量 | 占比")
            for row in hist:
                lines.append(f"  {str(row.get('FREE_DATE', ''))[:10]} "
                             f"| {row.get('LIMITED_STOCK_TYPE', '')} "
                             f"| {row.get('FREE_SHARES_NUM', '')} "
                             f"| {row.get('FREE_RATIO', '')}")
        else:
            lines.append("\n无历史解禁记录。")
    except Exception as e:  # noqa: BLE001
        lines.append(f"\n个股解禁查询失败: {e}")
    try:
        end = (datetime.date.fromisoformat(trade_date)
               + datetime.timedelta(days=forward_days)).isoformat()
        up = _eastmoney_datacenter(
            "RPT_LIFT_STAGE",
            filter_str=(f'(SECURITY_CODE="{code}")'
                        f"(FREE_DATE>='{trade_date}')(FREE_DATE<='{end}')"),
            page_size=20, sort_columns="FREE_DATE", sort_types="1")
        if up:
            lines.append(f"\n## 未来 {forward_days} 天待解禁")
            for row in up:
                lines.append(f"  {str(row.get('FREE_DATE', ''))[:10]} "
                             f"| {row.get('LIMITED_STOCK_TYPE', '')} "
                             f"| 数量 {row.get('FREE_SHARES_NUM', '')} "
                             f"| 占比 {row.get('FREE_RATIO', '')}")
        else:
            lines.append(f"\n未来 {forward_days} 天无待解禁。")
    except Exception as e:  # noqa: BLE001
        lines.append(f"\n解禁日历查询失败: {e}")
    return "\n".join(lines)


def fetch_industry(code, trade_date, top_n=20):
    """行业板块强弱排名（东财 push2）。"""
    lines = [f"# 行业横向对比 | {code} | {trade_date}"]
    try:
        params = {"pn": "1", "pz": "100", "po": "1", "np": "1", "fltt": "2",
                  "invt": "2", "fs": "m:90+t:2",
                  "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207"}
        r = em_get("https://push2.eastmoney.com/api/qt/clist/get",
                   params=params, timeout=15)
        items = (r.json().get("data") or {}).get("diff") or []
        if items:
            lines.append(f"\n## 全行业表现（东财 {len(items)} 个行业）")
            lines.append("排名 | 行业 | 涨跌幅 | 上涨 | 下跌 | 领涨股")
            for i, item in enumerate(items):
                lines.append(f"  {i+1}. {item.get('f14', '')} "
                             f"| {item.get('f3', 0)}% | {item.get('f104', 0)} "
                             f"| {item.get('f105', 0)} | {item.get('f140', '')}")
                if i >= top_n * 2 - 1:
                    lines.append(f"  ...（展示涨跌前 {top_n}）")
                    break
        else:
            lines.append("\n行业数据获取为空。")
    except Exception as e:  # noqa: BLE001
        lines.append(f"\n行业对比查询失败: {e}")
    return "\n".join(lines)


def fetch_fundflow(code, curr_date, include_history=True):
    """个股资金流向：东财 push2 分钟级 + push2his 历史日线（按分析日截断）。"""
    secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    historical = curr_date < datetime.date.today().isoformat()
    lines = [f"# 资金流向 | {code} | {curr_date}", "# Source: 东财 push2", ""]
    if historical:
        lines.append(f"（分析日期 {curr_date} 早于今天，已略去实时分钟资金流——"
                     f"那是今天的盘中数据，不是 {curr_date} 当天的。）\n")
    try:
        klines = []
        if not historical:
            r = em_get("https://push2.eastmoney.com/api/qt/stock/fflow/kline/get",
                       params={"secid": secid, "klt": 1,
                               "fields1": "f1,f2,f3,f7",
                               "fields2": "f51,f52,f53,f54,f55,f56,f57"},
                       timeout=10)
            klines = (r.json().get("data") or {}).get("klines") or []
        if klines:
            lines.append("## 实时分钟（主力/大单/超大单 净流入，万元）")
            for line in klines[-10:]:
                p = line.split(",")
                if len(p) >= 6:
                    lines.append(f"  {p[0]}: 主力={float(p[1])/1e4:.0f} "
                                 f"大单={float(p[4])/1e4:.0f} 超大单={float(p[5])/1e4:.0f}")
            last = klines[-1].split(",")
            if len(last) >= 2:
                main_net = float(last[1])
                sig = "净流入(看多)" if main_net > 0 else ("净流出(看空)" if main_net < 0 else "持平")
                lines.append(f"\n收盘: 主力净流入={main_net/1e4:.0f}万元（{sig}）")
        else:
            lines.append("无实时资金流（非交易时段或节假日）")
    except Exception as e:  # noqa: BLE001
        lines.append(f"[实时资金流获取失败] {type(e).__name__}: {e}")
    if include_history:
        try:
            hist_limit = 20
            if historical:
                gap = (datetime.date.today()
                       - datetime.date.fromisoformat(curr_date)).days
                hist_limit = min(500, 20 + int(gap * 0.7) + 20)
            r = em_get("https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
                       params={"secid": secid, "lmt": hist_limit, "klt": 101,
                               "fields1": "f1,f2,f3,f7",
                               "fields2": "f51,f52,f53,f54,f55,f56,f57"},
                       timeout=10)
            hist = (r.json().get("data") or {}).get("klines") or []
            if historical:
                hist = [k for k in hist if k.split(",")[0][:10] <= curr_date][-20:]
            if hist:
                lines.append(f"\n## 历史日线资金流（近 {len(hist)} 个交易日"
                             + (f"，截至 {curr_date}" if historical else "") + "）")
                lines.append("Date | 主力(万) | 大单(万) | 中单(万) | 小单(万) | 超大单(万)")
                for line in hist:
                    p = line.split(",")
                    if len(p) >= 6:
                        lines.append(f"  {p[0]} | {float(p[1])/1e4:.0f} "
                                     f"| {float(p[4])/1e4:.0f} | {float(p[3])/1e4:.0f} "
                                     f"| {float(p[2])/1e4:.0f} | {float(p[5])/1e4:.0f}")
            else:
                lines.append(f"\n## 历史资金流：{curr_date} 及之前未能取到"
                             "（接口只提供从今天回溯的窗口，分析日过早可能超出范围）")
        except Exception as e:  # noqa: BLE001
            lines.append(f"[历史资金流获取失败] {type(e).__name__}: {e}")
    return "\n".join(lines)


def fetch_concept(code):
    """概念/行业/地域板块归属（百度股市通）。"""
    url = "https://finance.pae.baidu.com/api/getrelatedblock"
    params = {"stock": json.dumps([{"code": code, "market": "ab", "type": "stock"}],
                                  ensure_ascii=False),
              "finClientType": "pc"}
    headers = {"Host": "finance.pae.baidu.com",
               "Accept": "application/vnd.finance-web.v1+json",
               "Origin": "https://gushitong.baidu.com",
               "Referer": "https://gushitong.baidu.com/"}
    try:
        r = SESSION.get(url, params=params, headers=headers, timeout=10)
        d = r.json()
        if str(d.get("ResultCode", -1)) != "0":
            return f"百度接口错误: ResultCode={d.get('ResultCode')} {d.get('ResultMsg', '')}"
        result = d.get("Result", {})
        if isinstance(result, dict) and result.get("code") == 403:
            return (f"百度 PAE 风控拦截（hit risk），{code} 的概念板块本次取不到。"
                    "该接口对 requests 的 TLS 指纹有风控，需浏览器指纹伪装才能稳定取数。")
        categories = result.get(code, [])
        if not categories:
            return f"{code} 无概念板块数据"
        lines = [f"# 概念/行业/地域板块 | {code}",
                 f"# Source: 百度股市通", ""]
        tags = []
        for cat in categories:
            cat_name = cat.get("name", "")
            items = cat.get("list") or []
            if not items:
                continue
            lines.append(f"## {cat_name}")
            for item in items:
                desc = item.get("describe", "")
                suffix = f"（{desc}）" if desc else ""
                lines.append(f"  {item.get('name', '')}{suffix}: {item.get('ratio', '')}")
                if cat_name == "概念":
                    tags.append(item.get("name", ""))
        if tags:
            lines.append(f"\nConcept tags: {' / '.join(tags)}")
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return f"概念板块获取失败: {type(e).__name__}: {e}"


def fetch_northbound(curr_date):
    """北向资金实时（同花顺 hsgt）。无历史时点值，历史分析日附告警。"""
    lines = [f"# 北向资金（沪深股通）| {curr_date}",
             "# Source: 同花顺 hsgtApi（仅实时快照，无历史日度）", ""]
    if curr_date < datetime.date.today().isoformat():
        lines.append("历史分析已略去实时北向资金：上游仅提供当前快照，"
                     "不能作为分析日当天的事实。")
        return "\n".join(lines)
    try:
        r = SESSION.get("https://data.hexin.cn/market/hsgtApi/method/dayChart/",
                        headers={"Host": "data.hexin.cn",
                                 "Referer": "https://data.hexin.cn/"}, timeout=10)
        d = r.json()
        times, hgt, sgt = d.get("time", []), d.get("hgt", []), d.get("sgt", [])
        if not times:
            return "\n".join(lines) + "\n无实时数据（非交易时段或节假日）"
        lines.append("## 实时（累计净买入，亿元）")
        for i in range(max(0, len(times) - 10), len(times)):
            h = hgt[i] if i < len(hgt) else "N/A"
            s = sgt[i] if i < len(sgt) else "N/A"
            lines.append(f"  {times[i]}: HGT={h} SGT={s}")
        hgt_close = float(hgt[-1]) if hgt else 0
        sgt_close = float(sgt[-1]) if sgt else 0
        total = hgt_close + sgt_close
        sig = "净流入(看多)" if total > 0 else ("净流出(看空)" if total < 0 else "持平")
        lines.append(f"\n收盘: HGT(沪股通)={hgt_close:.2f}亿 SGT(深股通)={sgt_close:.2f}亿 "
                     f"Total={total:.2f}亿（{sig}）")
    except Exception as e:  # noqa: BLE001
        lines.append(f"[北向资金获取失败] {type(e).__name__}: {e}")
    return "\n".join(lines)


# ── 主流程 ──────────────────────────────────────────────────────────
def parse_args():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ticker", help="6 位 A 股代码或中文名，如 600519 / 贵州茅台")
    ap.add_argument("--date", default=None, help="分析日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--lookback", type=int, default=60,
                    help="K线/新闻回溯天数（默认 60）")
    ap.add_argument("--sections", default=None,
                    help="逗号分隔的数据块，默认全部。可选：quote,kline,reports,"
                         "forecast,news,global_news,hot_stocks,lhb,lockup,"
                         "shareholders,industry,fundflow,concept,northbound,overview")
    ap.add_argument("--out", default=None, help="输出文件路径（默认 stdout）")
    return ap.parse_args()


def uuid4():
    import uuid
    return uuid.uuid4()


def main():
    args = parse_args()
    try:
        code = resolve_ticker(args.ticker)
    except ValueError as e:
        print(f"[错误] {e}", file=sys.stderr)
        sys.exit(2)

    if args.date:
        try:
            dt = datetime.date.fromisoformat(args.date)
        except ValueError:
            print(f"[错误] 日期格式应为 YYYY-MM-DD: {args.date!r}", file=sys.stderr)
            sys.exit(2)
    else:
        dt = datetime.date.today()
    if dt > datetime.date.today():
        print(f"[错误] 分析日期不能晚于今天: {dt}", file=sys.stderr)
        sys.exit(2)

    wanted = [s.strip() for s in args.sections.split(",") if s.strip()] if args.sections else None

    def sec(key, title, fn):
        if wanted is not None and key not in wanted:
            return None
        try:
            body = fn()
        except Exception as e:  # noqa: BLE001
            body = f"[数据获取失败] {type(e).__name__}: {e}"
        return f"## {title}\n\n{body}"

    start = (dt - datetime.timedelta(days=args.lookback)).isoformat()
    d = dt.isoformat()
    blocks = [
        sec("overview", "概览（名称+行情）", lambda: fetch_quote(code, d)),
        sec("quote", "实时行情/估值（腾讯）", lambda: fetch_quote(code, d)),
        sec("kline", f"K线（新浪，近 {args.lookback} 天）",
            lambda: fetch_kline(code, start, d)),
        sec("reports", "财报三表（新浪，按已公布截断）",
            lambda: fetch_reports(code, d)),
        sec("forecast", "机构一致预期（同花顺）",
            lambda: fetch_forecast(code, d)),
        sec("news", "个股新闻（东财/新浪）",
            lambda: fetch_news(code, start, d)),
        sec("global_news", "财经快讯（财联社/东财）",
            lambda: fetch_global_news(d, args.lookback, 10)),
        sec("hot_stocks", "热门强势股题材（同花顺）",
            lambda: fetch_hot_stocks(d)),
        sec("lhb", "龙虎榜（东财）", lambda: fetch_lhb(code, d, 30)),
        sec("lockup", "限售解禁（东财）", lambda: fetch_lockup(code, d, 90)),
        sec("shareholders", "股东动态（东财）",
            lambda: fetch_shareholders(code, d)),
        sec("industry", "行业对比（东财）", lambda: fetch_industry(code, d, 20)),
        sec("fundflow", "资金流向（东财）", lambda: fetch_fundflow(code, d, True)),
        sec("concept", "概念板块（百度）", lambda: fetch_concept(code)),
        sec("northbound", "北向资金（同花顺）", lambda: fetch_northbound(d)),
    ]
    blocks = [b for b in blocks if b is not None]

    header = (f"# A股数据素材：{code}\n\n"
              f"- 分析日期: {d}\n"
              f"- 回溯窗口: {args.lookback} 天\n"
              f"- 抓取时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
              f"- 数据源: 新浪/腾讯/东财/同花顺/百度（免费直连，无 API key）\n"
              f"- 历史日期注意: 实时估值/北向等无历史时点值的数据块自带快照告警，"
              f"不得当作分析日当天事实\n\n")
    output = header + "\n\n".join(blocks)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"[完成] 已写入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()
