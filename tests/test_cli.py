import pytest

from bsp.cli import main


def test_price_command_prints_call_and_put(capsys):
    assert main(["price", "--spot", "42", "--strike", "40", "--days", "182.5", "--vol", "0.2",
                 "--rate", "0.1"]) == 0
    out = capsys.readouterr().out
    assert "call: 4.76" in out and "put: 0.81" in out


def test_unknown_topic_is_a_usage_error():
    with pytest.raises(SystemExit):
        main(["report", "nope"])
