"""Actual ammo calculator, exact source preservation and bounded port queries."""
from copy import deepcopy
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools/validation/diplomacy_package_03"))
from _support import ast, one

REL = "common/scripted_effects/00_ammo_mechanics_effects.txt"
BASE = HERE / "fixtures" / "ammo_port_mechanics_baseline.txt"
CANDIDATE = ROOT / REL
SCRATCH = {"eon_ammo_port_ceiling", "eon_ammo_port_probe", "eon_ammo_port_searching", "eon_ammo_port_parity", "eon_ammo_port_loop_break"}

def source_body(path):
    return one(ast(path.read_text("utf-8-sig")), "count_current_consumption")



def compare(a, op, b):
    return {"=": a == b, "!=": a != b, ">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]


class Runtime:
    """Closed actual math/control AST; native queries are pure controlled inputs."""
    def __init__(self, ports=(1,), actor="POL", root="CHI", war=True, planes=0, volunteers=(), army=0,
                 majors=False, strength=1, modifier=0, num_ships=1000,
                 break_value=0, break_mode="reset"):
        self.actor, self.root, self.war = actor, root, war
        self.countries = [actor, root, "GER", "UKR", "USA", "ALB"]
        self.countries = list(dict.fromkeys(self.countries))
        self.states = {"state" + str(i): {"naval_base": 1, "portships": count} for i, count in enumerate(ports)}
        self.states["landlocked"] = {"naval_base": 0, "portships": 900}
        self.fields = {c: {} for c in self.countries}
        self.fields[actor] = {"num_ships": num_ships, "fleet_maximum_ammo_consumption": 1000,
            "num_deployed_planes": planes, "air_maximum_ammo_consumption": 320,
            "alliance_strength_ratio": strength, "land_maximum_ammo_consumption": 200,
            "num_battalions": 100, "modifier@ammo_consumption_modifier": modifier}
        self.temp = {"i": 77, "unrelated": 91, "break": break_value}
        assert break_mode in ("before", "after", "reset")
        self.break_mode = break_mode
        self.volunteers, self.army, self.majors = set(volunteers), army, majors
        self.leaders = {"field_marshal": {"is_leading_army_group": True, "num_units_offensive_combats": 9, "num_units_defensive_combats": 9},
                        "general1": {"is_leading_army_group": False, "num_units_offensive_combats": 3, "num_units_defensive_combats": 2},
                        "general2": {"is_leading_army_group": False, "num_units_offensive_combats": 0, "num_units_defensive_combats": 1}}
        self.queries = []
        self.writes = []
        self.loop_steps = 0

    def reference(self, token, stack):
        if token == "THIS": return stack[-1]
        if token == "PREV": return stack[-2]
        if token == "ROOT": return self.root
        if token == "FROM": return "ALB"
        return token

    def slot(self, token, stack):
        if "." in token:
            prefix, name = token.split(".", 1)
            return self.reference(prefix, stack), name
        return stack[-1], token

    def value(self, token, stack):
        try: return float(token)
        except ValueError: pass
        scope, name = self.slot(token, stack)
        if name in self.temp: return self.temp[name]
        if scope in self.states: return self.states[scope].get(name, 0)
        if scope in self.leaders: return self.leaders[scope].get(name, 0)
        return self.fields[scope].get(name, 0)

    def trigger(self, rows, stack, mode="AND"):
        vals = (self.trigger_node(key, op, val, stack) for key, op, val in rows)
        return any(vals) if mode == "OR" else not any(vals) if mode == "NOT" else all(vals)

    def trigger_node(self, key, op, val, stack):
        if key in ("OR", "AND", "NOT"): return self.trigger(val, stack, key)
        if key == "has_war": return self.war == (val == "yes")
        if key == "check_variable":
            if any(k == "var" for k, _, _ in val):
                operator = {"less_than": "<", "equals": "="}[one(val, "compare")]
                return compare(self.value(one(val, "var"), stack), operator, self.value(one(val, "value"), stack))
            name, operator, token = val[0]
            return compare(self.value(name, stack), operator, self.value(token, stack))
        if key == "naval_base": return compare(self.value(key, stack), op, float(val))
        if key == "ships_in_state_ports":
            state = self.reference(one(val, "state"), stack)
            scope = stack[-1]
            assert scope == self.actor, (scope, self.actor, stack)
            assert state in self.states
            size = next(row for row in val if row[0] == "size")
            self.queries.append((scope, state, size[1], self.value(size[2], stack)))
            return compare(self.states[state]["portships"], size[1], self.value(size[2], stack))
        if key in ("any_other_country", "any_enemy_country"):
            return any(self.trigger(val, stack + [country]) for country in self.countries if country != stack[-1])
        if key == "is_major": return self.majors == (val == "yes")
        if key == "has_volunteers_amount_from":
            count = next(row for row in val if row[0] == "count")
            return (self.reference(one(val, "tag"), stack), stack[-1]) in self.volunteers and compare(1, count[1], float(count[2]))
        if key == "has_army_size":
            size = one(val, "size")
            operator = next(row[1] for row in val if row[0] == "size")
            return compare(self.army, operator, float(size))
        if key == "is_leading_army_group": return self.leaders[stack[-1]][key] == (val == "yes")
        raise AssertionError((key, op, val))

    def effect(self, rows, stack):
        at = 0
        while at < len(rows):
            key, op, val = rows[at]; at += 1
            if key == "if":
                branches = [("if", val)]
                while at < len(rows) and rows[at][0] in ("else", "else_if"):
                    branches.append((rows[at][0], rows[at][2])); at += 1
                for typ, branch in branches:
                    if typ == "else" or self.trigger(one(branch, "limit"), stack):
                        self.effect([r for r in branch if r[0] != "limit"], stack); break
            elif key == "PREV": self.effect(val, stack + [stack[-2]])
            elif key in ("every_state", "every_other_country", "every_army_leader"):
                scopes = list(self.states) if key == "every_state" else [c for c in self.countries if c != stack[-1]] if key == "every_other_country" else list(self.leaders)
                limits = next((r[2] for r in val if r[0] == "limit"), [])
                for scope in scopes:
                    if self.trigger(limits, stack + [scope]): self.effect([r for r in val if r[0] != "limit"], stack + [scope])
            elif key == "while_loop_effect":
                steps = 0
                break_name = next((r[2] for r in val if r[0] == "break"), "break")
                # Native1.19.3 observed reset at entry, including nonzero input.
                if self.break_mode == "reset": self.write(break_name, 0, stack, True)
                while self.trigger(one(val, "limit"), stack):
                    if self.break_mode == "before" and self.temp.get(break_name, 0): break
                    steps += 1; self.loop_steps += 1
                    assert steps <= 102
                    self.effect([r for r in val if r[0] not in ("limit", "break")], stack)
                    if self.break_mode == "after" and self.temp.get(break_name, 0): break
            elif key in ("clamp_temp_variable", "clamp_variable"):
                name = one(val, "var"); value = self.value(name, stack)
                low, high = self.value(one(val, "min"), stack), self.value(one(val, "max"), stack)
                self.write(name, max(low, min(high, value)), stack, "temp" in key)
            elif key in ("round_temp_variable", "round_variable"):
                value = self.value(val, stack)
                rounded = float(math.floor(value + .5) if value >= 0 else math.ceil(value - .5))
                self.write(val, rounded, stack, "temp" in key)
            elif key == "modulo_temp_variable":
                name = one(val, "var")
                self.write(name, self.value(name, stack) % self.value(one(val, "value"), stack), stack, True)
            elif key in ("set_variable", "add_to_variable", "subtract_from_variable", "multiply_variable", "divide_variable",
                         "set_temp_variable", "add_to_temp_variable", "subtract_from_temp_variable", "multiply_temp_variable", "divide_temp_variable"):
                name, _, token = val[0]
                old, value = self.value(name, stack), self.value(token, stack)
                if key.startswith("set_"): result = value
                elif key.startswith("add_"): result = old + value
                elif key.startswith("subtract_"): result = old - value
                elif key.startswith("multiply_"): result = old * value
                else:
                    assert value != 0
                    result = old / value
                self.write(name, result, stack, "temp" in key)
            else: raise AssertionError((key, op, val))

    def write(self, name, value, stack, temp=False):
        scope, field = self.slot(name, stack)
        if temp: self.temp[field] = value
        else:
            self.fields[scope][field] = value
            self.writes.append((scope, field, value))

    def run(self, body): self.effect(body, [self.actor]); return self

    def persistent(self):
        return self.fields, {k: v for k, v in self.temp.items() if k not in SCRATCH}, self.writes, self.states


class AmmoPortPolicy(unittest.TestCase):
    def both(self, **kwargs):
        a, b = Runtime(**kwargs), Runtime(**kwargs)
        a.run(source_body(BASE)); b.run(source_body(CANDIDATE))
        self.assertEqual(a.persistent(), b.persistent())
        self.assertLessEqual(len(b.queries), len(a.queries))
        return a, b

    def test_01_candidate_dense_query_cost_is_bounded(self):
        m = Runtime(ports=(1000,)).run(source_body(CANDIDATE))
        self.assertLessEqual(len(m.queries), 14)

    def test_02_exhaustive_nonnegative_counts_and_sparse_cost(self):
        rows = []
        for count in list(range(301)) + [511, 512, 999, 1000, 10000, 1000000]:
            a, b = self.both(ports=(count,))
            self.assertEqual(b.temp["i"], min(count, 100) if count else 77)
            rows.append({"ships": count, "old_queries": len(a.queries), "new_queries": len(b.queries)})
        self.assertLessEqual(max(row["new_queries"] for row in rows), 14)

    def test_03_multiple_ports_order_and_foreign_root(self):
        for actor in ("POL", "GER", "UKR", "USA", "ALB"):
            a, b = self.both(ports=(0, 1, 2, 4, 8, 16, 64, 99, 100, 130), actor=actor, root="CHI")
            before = list(dict.fromkeys(q[1] for q in a.queries))
            after = list(dict.fromkeys(q[1] for q in b.queries))
            self.assertEqual(before, after)
            self.assertTrue(all(q[0] == actor for q in b.queries))

    def test_04_whole_air_land_calculator_and_modifier_matrix(self):
        for planes, army, majors, strength, modifier in itertools.product((0, 50), (0, 20), (False, True), (1, 2), (-1.5, 0, .25)):
            self.both(ports=(1, 4, 32, 100), planes=planes, army=army, majors=majors, strength=strength, modifier=modifier)

    def test_05_peace_and_volunteers_do_not_query_ports(self):
        for war, num_ships in itertools.product((False, True), (0, 1000)):
            a, b = self.both(ports=(100,), war=war, num_ships=num_ships, planes=50, army=20, volunteers=(("POL", "GER"),))
            if not war or not num_ships: self.assertEqual(b.queries, [])

    def test_06_stale_num_ships_is_not_used_to_change_inherited_cap(self):
        for num_ships in (1, 7, 10, 99, 100, 101, 1000):
            self.both(ports=(1000, 2, 1000), num_ships=num_ships)

    def test_07_negative_scope_and_off_by_one_controls_are_detected(self):
        # Physical calculations match ordinary native break0. Preserving a
        # nonzero caller break is an intentional scratch isolation change only.
        for break_value in (1, -1, 77):
            kwargs = dict(ports=(0, 1, 2, 4, 8, 16, 64, 99, 100, 130), planes=50, army=20)
            expected = Runtime(**kwargs).run(source_body(BASE))
            actual = Runtime(**kwargs, break_value=break_value).run(source_body(CANDIDATE))
            self.assertEqual(expected.fields, actual.fields)
            self.assertEqual(expected.writes, actual.writes)
            self.assertEqual(expected.states, actual.states)
            expected_temps = {k:v for k,v in expected.temp.items() if k not in SCRATCH}
            actual_temps = {k:v for k,v in actual.temp.items() if k not in SCRATCH}
            expected_temps["break"] = break_value
            self.assertEqual(expected_temps, actual_temps)
            self.assertEqual(actual.temp["break"], break_value)
        unnamed = deepcopy(source_body(CANDIDATE))
        def remove_named_property(rows):
            for key, op, val in rows:
                if key == "while_loop_effect":
                    at = next((i for i,row in enumerate(val) if row[0] == "break"), None)
                    if at is not None: val.pop(at); return True
                if isinstance(val, list) and remove_named_property(val): return True
            return False
        self.assertTrue(remove_named_property(unnamed))
        self.assertNotEqual(Runtime(ports=(16,), break_value=1).run(unnamed).temp["break"], 1)
        mutant = deepcopy(source_body(CANDIDATE))
        def mutate(rows):
            for at, (key, op, val) in enumerate(rows):
                if key == "ships_in_state_ports" and one(val, "state") == "PREV":
                    state_at = next(i for i, row in enumerate(val) if row[0] == "state")
                    val[state_at] = ("state", "=", "ROOT"); return True
                if isinstance(val, list) and mutate(val): return True
            return False
        self.assertTrue(mutate(mutant))
        with self.assertRaises(AssertionError): Runtime(ports=(9,)).run(mutant)
        bad = deepcopy(source_body(CANDIDATE))
        def off_by_one(rows):
            for at, (key, op, val) in enumerate(rows):
                if key == "subtract_from_temp_variable" and val == [("eon_ammo_port_probe", "=", "1")]:
                    rows[at] = (key, op, [("eon_ammo_port_probe", "=", "0")]); return True
                if isinstance(val, list) and off_by_one(val): return True
            return False
        self.assertTrue(off_by_one(bad))
        a, b = Runtime(ports=(2,)), Runtime(ports=(2,))
        a.run(source_body(BASE)); b.run(bad)
        self.assertNotEqual(a.persistent(), b.persistent())

    def test_08_only_exact_port_loop_span_and_five_temporaries_change(self):
        info = json.loads((HERE / "canonical_ammo_ports.json").read_text("utf-8"))
        self.assertEqual(hashlib.sha256(BASE.read_bytes()).hexdigest(), "198db754b38ffc21f317d4791822c2da7c5f7a33b9352b17c2fe7d89ba8b6feb")
        self.assertEqual(hashlib.sha256(info["candidate_span"].encode("utf-8")).hexdigest(), "3582ee408494d30624c4e08a74936849937148e017b10f0e2d8ce033ae202b8f")
        current = CANDIDATE.read_bytes()
        self.assertEqual(current.count(info["candidate_span"].encode("utf-8")), 1)
        restored = current.replace(info["candidate_span"].encode("utf-8"), info["before_span"].encode("utf-8"), 1)
        self.assertEqual(restored, BASE.read_bytes())
        self.assertEqual(hashlib.sha256(current).hexdigest(), info["candidate_sha256"])
        self.assertEqual(current.startswith(b"\xef\xbb\xbf"), BASE.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertEqual(b"\r\n" in current, b"\r\n" in BASE.read_bytes())


if __name__ == "__main__": unittest.main(verbosity=2)
