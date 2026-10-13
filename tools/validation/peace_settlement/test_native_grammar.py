"""Keep the AI trigger failure discovered by the real 1.19 compiler detectable."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/validation/diplomacy_completion'))
from check_native_grammar import inspect, parser


class NativeGrammar(unittest.TestCase):
    def test_bare_stability_trigger_is_rejected(self):
        self.assertTrue(inspect(parser.ast('ai_desire = { modifier = { stability < 0.35 } }')))

    def test_documented_stability_trigger_is_allowed(self):
        self.assertFalse(inspect(parser.ast('ai_desire = { modifier = { has_stability < 0.35 } }')))

    def test_numeric_stability_variable_remains_allowed(self):
        self.assertFalse(inspect(parser.ast('effect = { set_temp_variable = { before = stability } check_variable = { stability < 0.35 } }')))


if __name__ == '__main__': unittest.main(verbosity=2)
