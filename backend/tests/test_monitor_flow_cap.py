"""A flood leaves thousands of entries in the switch's table for up to a minute.

2000 connections is 4000 flow entries (one per direction); a second flood inside
the minute is 8000. analyze_flows refused anything over MAX_ANALYZE_FLOWS (5000),
so the monitor's whole poll failed -- no scores, no incident, no graph update --
until the entries aged out. The cap exists to bound what an HTTP client can ask
the server to compute; the switch's own table is not that.
"""
import pytest

from app.config import settings
from app.mininet_monitor.monitor import MininetMonitor
from app.services.analysis_pipeline import analyze_flows


def _flows(n, src="10.0.0.2"):
    return [{"src_ip": src, "dst_ip": "10.0.0.1", "src_port": 30000 + i, "dst_port": 80, "protocol": "TCP",
             "packet_count": 6, "byte_count": 440, "duration_sec": 2.0, "tcp_flags": 0, "data_source": "ovs"}
            for i in range(n)]


def test_the_api_cap_still_applies_by_default():
    with pytest.raises(ValueError, match="Too many flows; max is 5000"):
        analyze_flows(_flows(settings.max_analyze_flows + 1))


def test_the_monitor_scores_a_table_bigger_than_the_api_cap():
    flows = _flows(settings.max_analyze_flows + 1000)
    result = analyze_flows(flows, cap=settings.monitor_max_flows)
    assert "10.0.0.2" in result["predictions"]


def test_the_monitor_keeps_the_busiest_flows_past_its_own_ceiling(monkeypatch, capsys):
    monkeypatch.setattr(settings, "monitor_max_flows", 100)
    monitor = MininetMonitor(sio=None)
    flows = _flows(150)
    flows[7]["packet_count"] = 99999
    kept = monitor._cap_flows(flows)
    assert len(kept) == 100 and kept[0]["packet_count"] == 99999
    monitor._cap_flows(flows)                            # said once, not every poll
    assert capsys.readouterr().out.count("over MONITOR_MAX_FLOWS") == 1
    assert monitor._cap_flows(flows[:50]) == flows[:50]  # back under: untouched
