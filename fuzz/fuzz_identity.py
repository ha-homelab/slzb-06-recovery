"""Exercise address and hardware identity guards; no network or serial access."""
import json
from pathlib import Path
import sys
import urllib.parse

import atheris

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
with atheris.instrument_imports():
    import esp32_core
    import slzb

MAC = "02:00:00:00:00:10"


@atheris.instrument_func
def test_one_input(data):
    text = data.decode("utf-8", errors="replace")
    for validate in (esp32_core.normalize_mac, esp32_core.validate_port, slzb.validate_base_url):
        try:
            result = validate(text)
        except ValueError:
            continue
        assert isinstance(result, str)
        assert validate(result) == result
        if validate is slzb.validate_base_url:
            parsed = urllib.parse.urlsplit(result)
            assert parsed.scheme in ("http", "https") and parsed.hostname
    try:
        state = json.loads(data)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return
    if not isinstance(state, dict):
        return
    try:
        slzb.validate_identity(state, MAC)
    except ValueError:
        return
    assert state["hwRev"] == "SLZB-06"
    assert state["ethMac"].lower() == MAC


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
