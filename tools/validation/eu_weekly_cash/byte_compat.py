"""Exact inverse of the single approved EU annual-to-weekly calculation.

Only historical byte guards use this projection. Behavior tests execute current
source. Missing, duplicate or altered calculation bytes fail; unrelated bytes
are returned intact for the caller's full historical comparison.
"""
import hashlib

SOURCE_PATH = 'common/scripted_effects/00_money_system.txt'
ORIGINAL = (
    '\t\tset_variable = {\n'
    '\t\t\tEU_subsidies = {\n'
    '\t\t\t\tvalue = THIS.EU_natural_subsidies\n'
    '\t\t\t\tadd = THIS.EU_growth_subsidies\n'
    '\t\t\t\tadd = THIS.EU_admin_subsidies\n'
    '\t\t\t\tadd = THIS.EU_global_exp_subsidies\n'
    '\t\t\t\tmultiply = 0.019\n'
    '\t\t\t}\n'
    '\t\t}\n'
)
CURRENT = (
    '\t\tset_variable = {\n'
    '\t\t\tEU_subsidies = {\n'
    '\t\t\t\tvalue = THIS.EU_natural_subsidies\n'
    '\t\t\t\tadd = THIS.EU_growth_subsidies\n'
    '\t\t\t\tadd = THIS.EU_admin_subsidies\n'
    '\t\t\t\tadd = THIS.EU_global_exp_subsidies\n'
    '\t\t\t}\n'
    '\t\t}\n'
    '\t\tdivide_variable = { EU_subsidies = 52 }\n'
)
ORIGINAL_SHA256 = '07dc77e51c074a22d2ab57a879f632f5f2ae59430fd47d92d748f67694168575'
CURRENT_SHA256 = '6f76d0783b7a5315e584dde71212fd123e9dfc57a4ea17d9c6f6112c2bb2ad7c'


def restore_weekly_subsidy(path, raw):
    if path != SOURCE_PATH:
        return raw
    for body, digest in ((ORIGINAL, ORIGINAL_SHA256), (CURRENT, CURRENT_SHA256)):
        if hashlib.sha256(body.encode('utf-8')).hexdigest() != digest:
            raise AssertionError('EU weekly subsidy projection catalog changed')
    current, original = CURRENT, ORIGINAL
    if isinstance(raw, bytes):
        current, original = current.encode('utf-8'), original.encode('utf-8')
    if raw.count(current) != 1:
        raise AssertionError('One exact current EU weekly subsidy calculation required')
    return raw.replace(current, original, 1)
