"""Current-time helpers for memory extraction and time-aware retrieval."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime, timedelta

WEEKDAYS_ZH = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")

_WEEKDAY_CHAR = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}

_NEXT_WEEKDAY_RE = re.compile(r"下(?:个)?(?:星期|周|礼拜)([一二三四五六日天])")
_THIS_WEEKDAY_RE = re.compile(r"(?:这|本)个?(?:星期|周|礼拜)([一二三四五六日天])")
_NEXT_MONTH_RE = re.compile(r"下个月|下月")
_PREV_MONTH_RE = re.compile(r"上个月|上月")
_THIS_MONTH_RE = re.compile(r"这个月|本月")
_DAY_AFTER_RE = re.compile(r"后天")
_DAY_BEFORE_RE = re.compile(r"前天")
_TOMORROW_RE = re.compile(r"明天|明日")
_YESTERDAY_RE = re.compile(r"昨天|昨日")
_TODAY_RE = re.compile(r"今天|今日")


def format_date(d: date) -> str:
    return f"{d.year}年{d.month}月{d.day}日"


def format_month(year: int, month: int) -> str:
    return f"{year}年{month}月"


def format_date_weekday(now: datetime | None = None) -> str:
    dt = now or datetime.now()
    return f"{format_date(dt.date())} {WEEKDAYS_ZH[dt.weekday()]}"


def format_clock_stamp(now: datetime | None = None) -> str:
    dt = now or datetime.now()
    return f"{format_date_weekday(dt)} {dt.strftime('%H:%M')}"


def format_extract_now(now: datetime | None = None) -> str:
    return f"【当前时间】{format_clock_stamp(now)}"


def _shift_month(d: date, delta: int) -> tuple[int, int]:
    month_index = d.year * 12 + (d.month - 1) + delta
    year, month0 = divmod(month_index, 12)
    return year, month0 + 1


def _this_week_date(now: datetime, weekday: int) -> date:
    return now.date() + timedelta(days=weekday - now.weekday())


def _next_week_date(now: datetime, weekday: int) -> date:
    return _this_week_date(now, weekday) + timedelta(days=7)


def expand_relative_time(text: str, now: datetime | None = None) -> str:
    """Replace relative date words with absolute dates matching extractor format."""
    dt = now or datetime.now()
    if not text:
        return ""

    def repl_next_weekday(match: re.Match[str]) -> str:
        return format_date(_next_week_date(dt, _WEEKDAY_CHAR[match.group(1)]))

    def repl_this_weekday(match: re.Match[str]) -> str:
        return format_date(_this_week_date(dt, _WEEKDAY_CHAR[match.group(1)]))

    out = text
    replacements: list[tuple[re.Pattern[str], object]] = [
        (_NEXT_WEEKDAY_RE, repl_next_weekday),
        (_THIS_WEEKDAY_RE, repl_this_weekday),
        (_NEXT_MONTH_RE, lambda _m: format_month(*_shift_month(dt.date(), 1))),
        (_PREV_MONTH_RE, lambda _m: format_month(*_shift_month(dt.date(), -1))),
        (_THIS_MONTH_RE, lambda _m: format_month(dt.year, dt.month)),
        (_DAY_AFTER_RE, lambda _m: format_date(dt.date() + timedelta(days=2))),
        (_DAY_BEFORE_RE, lambda _m: format_date(dt.date() + timedelta(days=-2))),
        (_TOMORROW_RE, lambda _m: format_date(dt.date() + timedelta(days=1))),
        (_YESTERDAY_RE, lambda _m: format_date(dt.date() + timedelta(days=-1))),
        (_TODAY_RE, lambda _m: format_date(dt.date())),
    ]
    for pattern, repl in replacements:
        out = pattern.sub(repl, out)  # type: ignore[arg-type]
    return out


def relative_dates_in(text: str, now: datetime | None = None) -> list[date]:
    """Day-level dates implied by relative words in the original query."""
    dt = now or datetime.now()
    blob = text or ""
    found: list[date] = []
    seen: set[date] = set()

    def add(value: date) -> None:
        if value not in seen:
            seen.add(value)
            found.append(value)

    for match in _NEXT_WEEKDAY_RE.finditer(blob):
        add(_next_week_date(dt, _WEEKDAY_CHAR[match.group(1)]))
    for match in _THIS_WEEKDAY_RE.finditer(blob):
        add(_this_week_date(dt, _WEEKDAY_CHAR[match.group(1)]))
    if _DAY_AFTER_RE.search(blob):
        add(dt.date() + timedelta(days=2))
    if _DAY_BEFORE_RE.search(blob):
        add(dt.date() + timedelta(days=-2))
    if _TOMORROW_RE.search(blob):
        add(dt.date() + timedelta(days=1))
    if _YESTERDAY_RE.search(blob):
        add(dt.date() + timedelta(days=-1))
    if _TODAY_RE.search(blob):
        add(dt.date())
    return found


def relative_months_in(text: str, now: datetime | None = None) -> list[str]:
    """Month strings implied by 这个月 / 下个月 / 上个月."""
    dt = now or datetime.now()
    blob = text or ""
    out: list[str] = []
    if _NEXT_MONTH_RE.search(blob):
        out.append(format_month(*_shift_month(dt.date(), 1)))
    if _PREV_MONTH_RE.search(blob):
        out.append(format_month(*_shift_month(dt.date(), -1)))
    if _THIS_MONTH_RE.search(blob):
        out.append(format_month(dt.year, dt.month))
    return out


def build_time_aware_query(
    text: str,
    now: datetime | None = None,
    *,
    include_clock: bool = True,
) -> str:
    """Expanded user text plus today's date/weekday (and clock for vector queries)."""
    dt = now or datetime.now()
    expanded = expand_relative_time((text or "").strip(), dt)
    stamp = format_clock_stamp(dt) if include_clock else format_date_weekday(dt)
    if not expanded:
        return stamp
    if stamp in expanded:
        return expanded
    if not include_clock and format_date_weekday(dt) in expanded:
        return expanded
    return f"{expanded} {stamp}"


def memory_time_fts_queries(
    now: datetime | None = None,
    extra_dates: Iterable[date] | None = None,
    extra_months: Iterable[str] | None = None,
) -> list[str]:
    """Compact date/month strings for separate memory FTS MATCH calls (no clock)."""
    dt = now or datetime.now()
    queries: list[str] = []
    for value in (dt.date(), *(extra_dates or ())):
        item = format_date(value)
        if item not in queries:
            queries.append(item)
    for month in extra_months or ():
        if month and month not in queries:
            queries.append(month)
    return queries


def clock_match_needles(now: datetime | None = None, query: str = "") -> list[str]:
    """Distinctive date/weekday strings a time-aware knowledge hit should mention."""
    dt = now or datetime.now()
    needles: list[str] = [
        format_date(dt.date()),
        f"{dt.month}月{dt.day}日",
        format_month(dt.year, dt.month),
        WEEKDAYS_ZH[dt.weekday()],
    ]
    for value in relative_dates_in(query, dt):
        needles.append(format_date(value))
        needles.append(f"{value.month}月{value.day}日")
    needles.extend(relative_months_in(query, dt))
    seen: list[str] = []
    for item in needles:
        if item and item not in seen:
            seen.append(item)
    return seen


def mentions_query_clock(
    text: str,
    now: datetime | None = None,
    query: str = "",
) -> bool:
    blob = text or ""
    return any(needle in blob for needle in clock_match_needles(now, query))


def cache_day_key(now: datetime | None = None) -> str:
    dt = now or datetime.now()
    return dt.date().isoformat()
