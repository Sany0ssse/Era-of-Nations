"""Check literal meta exporter bindings; does not change or prove production AI."""
from copy import deepcopy
import json

from source_model import Model, Source, p


def template(exporter='[EXPORTER_TAG]', binding='[PREV.GetTag]'):
    return p.ast('BBB = { PREV = { meta_effect = { '
                 'text = { create_import = { resource = uranium amount = [IMPORT_AMOUNT] exporter = '+exporter+' } } '
                 'IMPORT_AMOUNT = "[?eon_raw_import_amount|0]" EXPORTER_TAG = "'+binding+'" debug = yes } } }')


def valid(nodes):
    model = Model(Source())
    model.effect(p.ast('set_temp_variable = { eon_raw_import_amount = 112 }')+nodes)
    assert model.native_calls == [{'create_import': 'uranium', 'amount': 112, 'importer': 'AAA', 'exporter': 'BBB'}]
    assert len(model.meta_expansions) == 1
    expansion = model.meta_expansions[0]
    assert expansion['scope'] == 'AAA'
    call = p.one(expansion['ast'], 'create_import')
    assert p.one(call, 'exporter') == 'BBB', 'Native generated exporter must be a bound literal tag, not PREV'
    assert p.one(call, 'amount') == '112'
    assert model.country().native['resource_imported@uranium'] == 0
    return model


def main():
    model = valid(template())
    mutations = [template(binding='[THIS.GetTag]'), template(exporter='PREV'),
                 template(binding='[PREV.GetName]'), template(exporter='[UNBOUND]'),
                 template(binding='[?unknown|1]')]
    for nodes in mutations:
        try: valid(nodes)
        except AssertionError: pass
        else: raise AssertionError('Incorrect/unbound exporter template was accepted')
    literal = Model(Source())
    literal.effect(p.ast('meta_effect = { text = { [COUNTRY] = { set_variable = { sample = [VALUE] } } } COUNTRY = "BBB" VALUE = 42 }'))
    assert literal.country('BBB').variables['sample'] == 42
    scoped = Model(Source())
    scoped.effect(p.ast('set_variable = { eon_raw_target = 7 } set_temp_variable = { eon_raw_target = 23 } '
                       'BBB = { set_variable = { unqualified = eon_raw_target } '
                       'set_variable = { scoped = PREV.eon_raw_target } '
                       'set_variable = { missing_scoped_temporary = PREV.nonpersistent_temp } }'))
    assert scoped.country('BBB').variables == {'unqualified': 23, 'scoped': 7, 'missing_scoped_temporary': 0}
    assert scoped.country().variables['eon_raw_target'] == 7
    factory = Model(Source())
    factory.effect(p.ast('set_temp_variable = { desired_factories = 3 } BBB = { PREV = { meta_effect = { '
                         'text = { create_import = { resource = uranium factories = [IMPORT_FACTORIES] exporter = [EXPORTER_TAG] } } '
                         'IMPORT_FACTORIES = "[?desired_factories|0]" EXPORTER_TAG = "[PREV.GetTag]" } } }'))
    assert factory.native_calls == [{'create_import': 'uranium', 'factories': 3, 'requested_native_capacity': 240,
                                     'importer': 'AAA', 'exporter': 'BBB'}]
    assert factory.country().native['resource_imported@uranium'] == 0
    invalid = ['factories = 0', 'factories = 1.5', 'factories = 1 amount = 8', 'factories = -1']
    for argument in invalid:
        try: Model(Source()).effect(p.ast('create_import = { resource = uranium '+argument+' exporter = BBB }'))
        except AssertionError: pass
        else: raise AssertionError('Invalid native factory request accepted')
    print(json.dumps({'literal_meta_exporter_fixture_verified': True, 'negative_controls': len(mutations)+len(invalid),
                      'whole_factory_request_capacity_checked': True, 'native_factory_delivery_emulated': False,
                      'native_scoped_temporary_lookup_control': True,
                      'actual_production_daily_changed_by_test': False, 'native_game_behavior_tested': False}))


if __name__ == '__main__': main()
