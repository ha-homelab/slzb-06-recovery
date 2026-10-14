"""Mutate synthetic backup containers without opening files or a coordinator."""
import json
from pathlib import Path
import sys

import atheris

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
with atheris.instrument_imports():
    import compare_network
    import radio_legacy


def reject_constant(value):
    raise ValueError("Non-finite JSON constants are not backup data")


@atheris.instrument_func
def test_one_input(data):
    try:
        value = json.loads(data, parse_constant=reject_constant)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return
    try:
        backup = radio_legacy.find_network_backup(value)
    except ValueError:
        return
    if backup is None:
        return
    assert isinstance(backup, dict)
    assert isinstance(backup["network_info"], dict)
    assert isinstance(backup["node_info"], dict)
    assert radio_legacy.find_network_backup({"backup": backup}) is backup
    try:
        result = compare_network.compare(backup, backup)
    except ValueError:
        return  # Recognizable backups may lack the stricter comparison fields.
    assert len(result) == 12
    assert all(result.values()), "A complete backup must compare equal to itself"


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
