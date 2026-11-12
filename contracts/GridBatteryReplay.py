# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re


API = "https://api.carbonintensity.org.uk/intensity"
PERIODS = 48
HALF_HOUR = timedelta(minutes=30)
CHARGE_KWH = 5
DISCHARGE_KWH = 4


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fail(message):
    raise gl.vm.UserError("[EXPECTED] " + message)


def parse_day(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Expected UTC date")
    return date.fromisoformat(value)


def day_url(day):
    return f"{API}/{day.isoformat()}T00:00Z/{(day + timedelta(days=1)).isoformat()}T00:00Z"


def interval(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:(00|30)Z", value):
        raise ValueError("Invalid interval timestamp")
    return datetime.fromisoformat(value)


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def valid_intensity(value):
    return type(value) is int and 0 <= value <= 3000


def normalize(day, reply):
    if not isinstance(reply, dict):
        raise ValueError("Invalid API response")
    rows = reply.get("data")
    if not isinstance(rows, list) or len(rows) not in (PERIODS, PERIODS + 1):
        raise ValueError("Incomplete UTC window")
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    stop = start + timedelta(days=1)
    slots = {}
    preceding_seen = False
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid observation")
        begin, end = interval(row.get("from")), interval(row.get("to"))
        if end - begin != HALF_HOUR:
            raise ValueError("Invalid interval length")
        # The API may include the interval ending exactly at the lower bound.
        if begin == start - HALF_HOUR and end == start and not preceding_seen:
            preceding_seen = True
            continue
        if begin < start or end > stop or begin in slots:
            raise ValueError("Duplicate or out-of-window observation")
        intensity = row.get("intensity")
        actual = intensity.get("actual") if isinstance(intensity, dict) else None
        if not valid_intensity(actual):
            raise ValueError("Missing or invalid actual intensity")
        slots[begin] = actual
    if len(slots) != PERIODS:
        raise ValueError("Incomplete UTC window")
    return [slots[start + i * HALF_HOUR] for i in range(PERIODS)]


def profile_for(day, vector):
    if not isinstance(vector, list) or len(vector) != PERIODS or not all(map(valid_intensity, vector)):
        raise ValueError("Invalid actual-intensity vector")
    profile = {"day": day.isoformat(), "source": day_url(day),
               "unit": "gCO2/kWh", "actual": vector}
    profile["id"] = hashlib.sha256(canonical(profile).encode("utf-8")).hexdigest()
    return profile


def acquire(day):
    def evaluate():
        try:
            response = gl.nondet.web.get(day_url(day))
            if response.status != 200 or not 1 <= len(response.body) <= 32768:
                raise ValueError("Invalid source response")
            data = json.loads(response.body.decode("utf-8"), object_pairs_hook=unique_keys)
            return profile_for(day, normalize(day, data))
        except Exception:
            raise gl.vm.UserError("[SOURCE_ERROR] Complete actual grid observations unavailable")

    def validator(result):
        if not isinstance(result, gl.vm.Return):
            return False
        try:
            return canonical(evaluate()) == canonical(result.calldata)
        except Exception:
            return False

    result = gl.vm.run_nondet_unsafe(evaluate, validator)
    try:
        if canonical(result) != canonical(profile_for(day, result["actual"])):
            raise ValueError("Substituted grid profile")
    except Exception:
        raise gl.vm.UserError("[SOURCE_ERROR] Invalid agreed grid profile")
    return result


def grid_energy(demand, move):
    return demand * DISCHARGE_KWH + (move * CHARGE_KWH if move > 0 else move * DISCHARGE_KWH)


def schedule(intensities, demand, capacity, rate):
    # Each suffix score minimizes emissions first, then total battery movement.
    suffix = [(0, 0)] + [None] * capacity
    choices = []
    for intensity, load in reversed(list(zip(intensities, demand))):
        scores, moves = [], []
        for held in range(capacity + 1):
            best, selected = None, 0
            for move in range(-min(rate, held, load), min(rate, capacity - held) + 1):
                following = suffix[held + move]
                if following is None:
                    continue
                score = (grid_energy(load, move) * intensity + following[0], abs(move) + following[1])
                if best is None or score < best:
                    best, selected = score, move
            scores.append(best)
            moves.append(selected)
        choices.append(moves)
        suffix = scores

    held = 0
    actions, charge, grid = [], [0], []
    for load, moves in zip(demand, reversed(choices)):
        move = moves[held]
        held += move
        actions.append(move)
        charge.append(held)
        grid.append(grid_energy(load, move))
    baseline = sum(load * DISCHARGE_KWH * intensity for load, intensity in zip(demand, intensities))
    optimal, movement = suffix[0]
    return {"actions": actions, "charge_quanta": charge, "grid_kwh": grid, "baseline_gco2": baseline,
            "modeled_gco2": optimal, "avoided_gco2": baseline - optimal, "moved_quanta": movement}


class GridBatteryReplay(gl.Contract):
    days: TreeMap[str, str]

    def __init__(self):
        pass

    @gl.public.write
    def capture(self, day: str) -> str:
        try:
            requested = parse_day(day)
        except ValueError:
            fail("Invalid UTC date")
        if requested >= datetime.now(timezone.utc).date():
            fail("UTC day must be complete")
        if day in self.days:
            return json.loads(self.days[day])["id"]
        profile = acquire(requested)
        self.days[day] = canonical(profile)
        return profile["id"]

    @gl.public.view
    def get_profile(self, day: str) -> dict:
        if day not in self.days:
            fail("Unknown grid day")
        return json.loads(self.days[day])

    @gl.public.view
    def plan(self, day: str, profile_id: str, demand: list[int], capacity: int, rate: int) -> dict:
        profile = self.get_profile(day)
        if profile["id"] != profile_id:
            fail("Grid profile ID mismatch")
        if len(demand) != PERIODS or any(type(load) is not int or not 0 <= load <= 16 for load in demand):
            fail("Expected 48 demand entries from zero to 16")
        if type(capacity) is not int or not 0 <= capacity <= 12 or type(rate) is not int or not 0 <= rate <= 4:
            fail("Battery capacity or rate outside bounds")
        return {"day": day, "profile_id": profile_id, **schedule(profile["actual"], demand, capacity, rate)}
