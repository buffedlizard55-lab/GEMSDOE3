from copy import deepcopy

import pytest

from gems3.feed import age_hours, normalized, parse_leaderboard, refresh, source_text

NOW = "2026-09-25T01:00:00Z"
OLD = "2026-09-24T01:00:00Z"


def board_html():
    return '''<html><table><tr><th>Rank</th><th>Team</th><th>Participant</th><th>DW-Tversky</th></tr>
    <tr><td>#1</td><td><img src="x"></td><td><a href="/users/DARD/">DARD</a><br>2d ago</td><td>0.3049</td></tr>
    <tr><td>#18</td><td></td><td><a href="/users/extradr19/">extradr19</a><br>28min ago</td><td>0.1563</td></tr></table></html>'''


def test_leaderboard_structural_parse():
    rows = parse_leaderboard(board_html())
    assert rows == [{"rank": 1, "participant": "DARD", "score": 0.3049},
                    {"rank": 18, "participant": "extradr19", "score": 0.1563}]


@pytest.mark.parametrize("html", ["<html>Login</html>", "<table>DW-Tversky</table>",
                                  board_html().replace("0.3049", "1.5"),
                                  board_html().replace("0.3049", "0.05"),
                                  board_html().replace("#1</td>", "#18</td>")])
def test_changed_or_invalid_leaderboard_never_produces_fake_scores(html):
    with pytest.raises(ValueError):
        parse_leaderboard(html)


def test_network_failure_preserves_last_success_and_scores():
    feed = {"sources": [{"id": "leaderboard", "last_verified_at": OLD, "status": "verified"}],
            "leaderboard": {"verified_at": OLD, "leader": {"score": 0.3049}}}
    source = {"id": "leaderboard", "url": "https://example.com/", "title": "Scores"}
    previous = deepcopy(feed)

    def fail(_):
        raise TimeoutError("network blocked")

    result = refresh(feed, [source], getter=fail, now=NOW)
    assert result["sources"][0]["last_verified_at"] == OLD
    assert result["sources"][0]["last_attempt_at"] == NOW
    assert result["leaderboard"] == feed["leaderboard"]
    assert result["sources"][0]["status"] == "refresh-unavailable"
    assert result["alerts"]
    assert feed == previous


def test_quote_drift_does_not_reset_verification_clock():
    feed = {"sources": [{"id": "rules", "last_verified_at": OLD, "raw_sha256": "old"}]}
    source = {"id": "rules", "url": "https://example.com/", "title": "Rules"}
    result = refresh(feed, [source], getter=lambda _: {"status": "review-required", "raw_sha256": "new",
                     "checks": [{"matched": False}]}, now=NOW)
    record = result["sources"][0]
    assert record["content_changed"] is True
    assert record["last_verified_at"] == OLD and record["last_retrieved_at"] == NOW


def test_success_updates_scores_without_artifact_attribution():
    source = {"id": "leaderboard", "url": "https://example.com/", "title": "Scores"}
    result = refresh({}, [source], getter=lambda _: {"status": "verified", "raw_sha256": "abc",
                     "leaderboard_rows": parse_leaderboard(board_html()), "checks": []}, now=NOW)
    assert result["leaderboard"]["tracked_user"]["score"] == 0.1563
    assert "unknown" in result["leaderboard"]["artifact_mapping"]
    assert result["sources"][0]["last_verified_at"] == NOW
    assert not result["alerts"]


def test_age_requires_timezone_and_rejects_future_invalid_dates():
    assert age_hours(OLD, NOW) == 24
    assert age_hours(None, NOW) is None
    assert age_hours("nonsense", NOW) is None
    assert age_hours("2026-09-25T00:00:00", NOW) is None
    assert age_hours("2026-09-26T00:00:00Z", NOW) is None


def test_normalized_quote_matching_handles_pdf_hyphenation():
    assert normalized("three\n submissions per week") == normalized("three submissions per week")
    assert normalized("float32") != normalized("float64")


def test_pdf_disguised_login_is_rejected():
    with pytest.raises(ValueError, match="Expected PDF"):
        source_text(b"<html>Login</html>", True)
    assert "injected code" not in source_text(b"<p>Real content</p><script>injected code</script>", False)
