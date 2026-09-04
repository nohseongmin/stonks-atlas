"""수집기 검정. **네트워크를 안 탄다** — 파싱과 캐시 규칙만 본다."""
import io
import zipfile

import pytest

from dump import feed

HEADER = ("open_time,open,high,low,close,volume,close_time,quote_volume,"
          "count,taker_buy_volume,taker_buy_quote_volume,ignore")
ROW1 = "1640995200000,100.0,101.0,99.0,100.5,1,1640995259999,1,1,1,1,0"
ROW2 = "1640995260000,100.5,102.0,100.0,101.5,1,1640995319999,1,1,1,1,0"


def _zip(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.csv", text)
    return buf.getvalue()


def test_parse_strips_header_when_present():
    """2022-01 부터 헤더가 생겼다."""
    rows = feed._parse(_zip(f"{HEADER}\n{ROW1}\n{ROW2}\n"))
    assert len(rows) == 2
    assert rows[0][0] == "1640995200000"


def test_parse_keeps_first_row_when_no_header():
    """2021-12 이전 파일엔 헤더가 없다. **한 봉이 조용히 사라지면 안 된다.**"""
    rows = feed._parse(_zip(f"{ROW1}\n{ROW2}\n"))
    assert len(rows) == 2
    assert rows[0][0] == "1640995200000"


def test_parse_decides_by_value_not_by_month():
    """헤더 판정은 첫 필드를 숫자로 파싱해서 한다. 월로 분기하면 언젠가 틀린다."""
    assert feed._parse(_zip(f"{HEADER}\n")) == []
    assert len(feed._parse(_zip(f"{ROW1}\n"))) == 1


def test_parse_empty_file():
    assert feed._parse(_zip("")) == []


def test_cached_writes_once(tmp_path, monkeypatch):
    """덤프 파일은 불변이다. 두 번 받으면 안 된다."""
    monkeypatch.setattr(feed, "CACHE", tmp_path)
    calls = []

    def fetch():
        calls.append(1)
        return b"payload"

    assert feed._cached("a/b.zip", fetch) == b"payload"
    assert feed._cached("a/b.zip", fetch) == b"payload"
    assert len(calls) == 1


def test_universe_at_uses_file_presence(monkeypatch):
    """**상폐된 심볼이 그 시점 유니버스에 들어가야 한다.** 이게 PIT 의 전부다."""
    monkeypatch.setattr(feed, "all_symbols", lambda: ["ALIVE", "DEAD"])
    monkeypatch.setattr(feed, "months", lambda s, i="1d":
                        ["2022-06", "2026-08"] if s == "ALIVE" else ["2022-06"])
    from datetime import date
    assert feed.universe_at(date(2022, 6, 1)) == ["ALIVE", "DEAD"]
    assert feed.universe_at(date(2026, 8, 1)) == ["ALIVE"]


def test_load_rejects_unavailable_months(monkeypatch):
    monkeypatch.setattr(feed, "months", lambda s, i="1d": ["2022-06"])
    with pytest.raises(ValueError, match="받을 월이 없다"):
        feed.load("X", "1d", ["2019-01"])


def test_non_ascii_symbols_are_encoded_not_dropped():
    """**한자 심볼이 실제로 상장돼 있다.** 걸러내면 선택편향이다."""
    assert feed._q("币安人生USDT").startswith("%")
    assert "USDT" in feed._q("币安人生USDT")
    assert feed._q("BTCUSDT") == "BTCUSDT"
    assert feed._q("a/b") == "a/b"        # 경로 구분자는 남긴다


def _metrics_zip(rows: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("m.csv", rows)
    return buf.getvalue()


def test_oi_fold_skips_bad_rows_without_desyncing():
    """**넷을 다 파싱한 뒤 한꺼번에 넣는지.**

    중간에 예외가 나면 앞의 배열만 늘어나 fmean 이 빈 리스트를 받는다.
    실측으로 354 심볼이 이 버그에서 죽었다.
    """
    from dump.oi import _fold
    good = "2024-06-03 00:00:00,X,1,100,2.0,1.5,3.0,0.6"
    bad = "2024-06-03 00:05:00,X,1,200,,1.5,3.0,0.6"     # 5번째 열이 빈칸
    v = _fold(_metrics_zip(f"{good}\n{bad}\n{good}\n"))
    assert v is not None
    assert v[0] == 100.0            # OI 는 마지막 유효행의 값
    assert v[1] == pytest.approx(2.0)


def test_oi_fold_returns_none_when_nothing_parses():
    from dump.oi import _fold
    assert _fold(_metrics_zip("2024-06-03 00:00:00,X,,,,,,\n")) is None
