import ast
from datetime import date, datetime, timedelta, timezone
import itertools
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "contracts/GridBatteryReplay.py"
DAY = date(2025, 1, 14)


@pytest.fixture
def core():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    tree.body = [node for node in tree.body if not isinstance(node, ast.ClassDef)
                 and not (isinstance(node, ast.ImportFrom) and node.module == "genlayer")]
    ns = {}
    exec(compile(tree, str(SOURCE), "exec"), ns)
    return ns


def source_rows(vector):
    first = datetime(2025, 1, 14, tzinfo=timezone.utc)

    def fmt(value):
        return value.strftime("%Y-%m-%dT%H:%MZ")

    return [{"from": fmt(first + timedelta(minutes=30 * i)),
             "to": fmt(first + timedelta(minutes=30 * (i + 1))),
             "intensity": {"actual": value, "forecast": 999}}
            for i, value in enumerate(vector)]


@pytest.mark.parametrize("change", ["missing", "duplicate", "null", "boolean", "gap", "outside"])
def test_rejects_incomplete_or_inauthentic_intervals(core, change):
    rows = source_rows([100] * 48)
    if change == "missing":
        rows.pop()
    elif change == "duplicate":
        rows[-1] = rows[0]
    elif change == "null":
        rows[3]["intensity"]["actual"] = None
    elif change == "boolean":
        rows[3]["intensity"]["actual"] = True
    elif change == "gap":
        rows[3]["to"] = rows[5]["to"]
    else:
        rows[-1] = {"from": "2025-01-15T00:00Z", "to": "2025-01-15T00:30Z", "intensity": {"actual": 5}}
    with pytest.raises(ValueError):
        core["normalize"](DAY, {"data": rows})


def test_canonical_order_discards_only_the_preceding_boundary_row(core):
    vector = list(range(48))
    rows = source_rows(vector)
    rows.insert(0, {"from": "2025-01-13T23:30Z", "to": "2025-01-14T00:00Z"})
    assert core["normalize"](DAY, {"data": list(reversed(rows))}) == vector


def test_validators_refetch_and_reject_a_changed_actual_value(core):
    rows = source_rows([100] * 48)
    calls = []

    def get(url):
        calls.append(url)
        return SimpleNamespace(status=200, body=json.dumps({"data": rows}).encode())

    def run(leader, validator):
        result = leader()
        assert validator(SimpleNamespace(calldata=result))
        forged = core["profile_for"](DAY, [101] + [100] * 47)
        assert not validator(SimpleNamespace(calldata=forged))
        rows[0]["intensity"]["actual"] = None
        assert not validator(SimpleNamespace(calldata=result))
        return result

    core["gl"] = SimpleNamespace(
        nondet=SimpleNamespace(web=SimpleNamespace(get=get)),
        vm=SimpleNamespace(Return=SimpleNamespace, UserError=ValueError, run_nondet_unsafe=run),
    )
    assert core["acquire"](DAY)["actual"] == [100] * 48
    assert calls == [core["day_url"](DAY)] * 4


def test_schedule_matches_exhaustive_reference(core):
    for intensity in itertools.product((0, 40, 100), repeat=4):
        for demand in ((1, 1, 1, 1), (0, 1, 0, 2), (2, 0, 2, 2)):
            candidates = []
            for actions in itertools.product(range(-2, 3), repeat=4):
                held, emissions = 0, 0
                for load, move, value in zip(demand, actions, intensity):
                    held += move
                    if not 0 <= held <= 2 or move < -load:
                        break
                    emissions += value * (4 * load + (5 if move > 0 else 4) * move)
                else:
                    if held == 0:
                        candidates.append((emissions, sum(map(abs, actions)), actions))
            result = core["schedule"](intensity, demand, 2, 2)
            assert (result["modeled_gco2"], result["moved_quanta"], tuple(result["actions"])) == min(candidates)


def test_direct_capture_and_resource_bounds(direct_vm, direct_deploy):
    contract = direct_deploy(str(SOURCE))
    direct_vm.warp("2025-01-15T00:00:00Z")
    with direct_vm.expect_revert("UTC day must be complete"):
        contract.capture("2025-01-15")
    rows = source_rows([50] + [200] * 47)
    direct_vm.mock_web(r"https://api\.carbonintensity\.org\.uk/intensity/.*", {
        "response": {"status": 200, "headers": {}, "body": json.dumps({"data": rows}).encode()}, "method": "GET",
    })
    id = contract.capture("2025-01-14")
    assert contract.capture("2025-01-14") == id
    assert contract.get_profile("2025-01-14")["actual"] == [50] + [200] * 47
    result = contract.plan("2025-01-14", id, [1] * 48, 1, 1)
    assert result["avoided_gco2"] == 550 and result["moved_quanta"] == 2
    assert result["charge_quanta"][0] == result["charge_quanta"][-1] == 0
    with direct_vm.expect_revert("Grid profile ID mismatch"):
        contract.plan("2025-01-14", "wrong", [1] * 48, 1, 1)
    with direct_vm.expect_revert("Expected 48 demand entries"):
        contract.plan("2025-01-14", id, [1] * 47, 1, 1)
