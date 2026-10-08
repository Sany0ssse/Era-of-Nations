"""Native grammar and boundary checks for the actual script interpreter.

This is API grammar evidence, not an HOI4 compiler or campaign execution.
"""
import json
from _model import ast, condition, context, state, switch, variable_comparison, value, flag, ref

cases=[]
s=state()
s['entities'][1]['variables']['balance']=30
s['entities'][2]['variables']['price']=30
c=switch(context(2),1)
s['entities'][1]['variables'].update({'stored_partner':2, 'variable_probe_@2':7})
assert value(s,c,'variable_probe_@PREV') == value(s,c,'variable_probe_@stored_partner') == 7
assert value(s,c,'variable_probe_@2') == 7
assert ref(s,c,'var:stored_partner') == 2
assert flag(s,c,'flag_probe_@PREV') == 'flag_probe_@2'
assert flag(s,c,'flag_probe_@stored_partner') != 'flag_probe_@2'
assert flag(s,c,'flag_probe_@2') != 'flag_probe_@2'
cases.append('native29 VARIABLE aliases retained while scalar FLAG suffixes cannot select peer')
comparisons={
    'less_than': (False,False,True),
    'less_than_or_equals': (False,True,True),
    'greater_than': (True,False,False),
    'greater_than_or_equals': (True,True,False),
    'equals': (False,True,False),
    'not_equals': (True,False,True),
}
for comparison, expected in comparisons.items():
    for right, outcome in zip((29,30,31),expected):
        s['entities'][2]['variables']['price']=right
        source='check_variable = { var = balance value = PREV.price compare = '+comparison+' }'
        assert condition(ast(source),s,c) == outcome, (comparison,right)
        cases.append(comparison+' boundary '+str(right))

for operator, outcome in (('=',True),('<',False),('>',False)):
    assert condition(ast('check_variable = { balance '+operator+' 30 }'),s,c)==outcome
    cases.append('documented short '+operator)

assert condition(ast('check_variable = { tooltip = unused var = balance compare = equals value = 30 }'),s,c)
cases.append('full form optional tooltip and field order')

invalid=[
    'balance >= 30', 'balance <= 30', 'balance != 30', 'balance == 30',
    'var = balance value = 30 compare = invalid',
    'var = balance value = 30',
    'var = balance compare = equals',
    'value = 30 compare = equals',
    'var = balance value = 30 compare = equals compare = not_equals',
    'var > balance value = 30 compare = equals',
    'var = balance value = { nested = 30 } compare = equals',
    'var = balance value = 30 compare = equals unsupported = yes',
    '',
]
for body in invalid:
    nodes=ast('check_variable = { '+body+' }')
    try:
        variable_comparison(nodes[0][2])
    except AssertionError:
        pass
    else:
        raise AssertionError('Interpreter accepted undocumented check_variable: '+body)
    try:
        condition(nodes,s,c)
    except AssertionError:
        pass
    else:
        raise AssertionError('Execution accepted undocumented check_variable: '+body)
    cases.append('reject undocumented '+body)

print(json.dumps({'all_passed':True,'cases_passed':len(cases),'cases':cases,
    'proof_scope':'documented native check_variable grammar and scoped numeric boundary execution; no engine run'},indent=2))
