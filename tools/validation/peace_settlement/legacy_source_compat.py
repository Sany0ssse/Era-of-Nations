"""Restore exactly two owned annex guards before old whole-source assertions.

The preceding SHA pins all unrelated current bytes, including existing energy
and embargo fixes. Missing, partial, moved, duplicate and foreign edits reject.
This is a test projection, never an in-game source rewrite.
"""
import hashlib
BASE_SHA='5202e99948854e04958a0aded1b7fb43a70cfcd43a74f45da653cf2474ca1aeb'
GUARD=b'\t\t\t\t\t# A mutually accepted peace must not trigger historical forced annexation.\n\t\t\t\t\tNOT = {\n\t\t\t\t\t\tAND = {\n\t\t\t\t\t\t\tROOT = { has_country_flag = eon_consensual_peace@FROM }\n\t\t\t\t\t\t\tFROM = { has_country_flag = eon_consensual_peace@ROOT }\n\t\t\t\t\t\t}\n\t\t\t\t\t}\n'
ANCHORS=(b'\t\t\t\t\tNOT = { has_global_flag = chechen_war_ended }\n',b'\t\t\t\t\tROOT = { has_country_flag = annex_on_peace_conference@FROM }\n')
def restore_consensual_annex_guards(data):
    assert isinstance(data,bytes),'Expected exact source bytes'
    assert data.count(GUARD)==2,'Exactly two owned annex guards must be present'
    original=data
    for anchor in ANCHORS:
        current=anchor+GUARD
        assert original.count(current)==1,'Annex guard moved or partial'
        original=original.replace(current,anchor)
    assert GUARD not in original
    assert hashlib.sha256(original).hexdigest()==BASE_SHA,'Unowned legacy bytes changed'
    inverse=original
    for anchor in ANCHORS:
        assert inverse.count(anchor)==1
        inverse=inverse.replace(anchor,anchor+GUARD)
    assert inverse==data,'Exact inverse does not reconstruct current source'
    return original
