"""Optional read-only native state islands; stripping them restores exact bytes.

The islands only read variables/flags and write log lines. They never change a
country variable, event queue, AI policy, clock or outcome assertion.
"""
import hashlib
import re
from decimal import Decimal


MARKER = 'EON_PRIVATE_FUEL_STATE'
P = 'eon_nuclear_fuel_trade_'
NS = 'eon_private_fuel_probe'
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]|[=<>!]+|[^\s{}=<>!#"]+')
OPTION_NAMES = ('energy.1.a', 'energy.1.b', 'energy.10.a', 'energy.10.b',
                'energy.2.a', 'energy.3.a', 'energy.11.a', 'energy.12.a')
VARIABLES = (('cash', 'treasury'), ('stock', 'var_reactor_material_stockpile'),
             ('cash_before', NS+'_cash_before'), ('expected_cash', NS+'_wait_expected_cash'),
             ('expected_stock', NS+'_wait_expected_stock'), ('phase', P+'phase'),
             ('partner', P+'partner'), ('cash_escrow', P+'cash_escrow'),
             ('fuel_escrow', P+'fuel_escrow'), ('total', P+'total'),
             ('actual_total', NS+'_actual_total'), ('quantity', P+'quantity'),
             ('wait_attempts', NS+'_wait_attempts'))
FLAGS = (P+'reserved', 'currently_considering_an_offer', P+'outgoing', P+'incoming', P+'live')
NUMERIC_FIELDS = {tag+'_'+field for tag in ('USA','HOL') for field,var in VARIABLES}
STATE_FIELDS = NUMERIC_FIELDS|{'ROOT','THIS','FROM'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def island(label):
    """Declared read-only state and flag logs, including native execution frame."""
    assert re.fullmatch(r'[A-Za-z0-9_.]+', label), label
    fields = ['ROOT=[ROOT.GetTag]', 'THIS=[THIS.GetTag]', 'FROM=[FROM.GetTag]']
    for tag in ('USA', 'HOL'):
        for field, var in VARIABLES:
            fields.append(tag+'_'+field+'=[?'+tag+'.'+var+'|8]')
    result = ' log = "'+MARKER+' STATE '+label+' '+' '.join(fields)+'" '
    for tag in ('USA', 'HOL'):
        for flag in FLAGS:
            prefix = MARKER+' FLAG '+label+' actor='+tag+' flag='+flag+' present='
            result += ('if = { limit = { '+tag+' = { has_country_flag = '+flag+' } } '
                       'log = "'+prefix+'yes" } else = { log = "'+prefix+'no" } ')
    return result


def read_records(text, labels, require):
    """Read diagnostic state without accepting duplicate/unknown/nonfinite values."""
    rows=[]
    for line_index,line in enumerate(text.splitlines(),1):
        if MARKER not in line:continue
        flag=re.search(re.escape(MARKER)+r' FLAG ([A-Za-z0-9_.]+) actor=(USA|HOL) flag=([A-Za-z_]+) present=(yes|no)\s*$',line)
        if flag:
            require(bool(rows) and rows[-1]['label']==flag[1],'Flag trace has no matching state island')
            require(flag[3] in FLAGS,'Unknown native flag trace '+flag[3])
            if rows and rows[-1]['label']==flag[1]:
                fields=rows[-1].setdefault('flags',{}).setdefault(flag[2],{})
                require(flag[3] not in fields,'Duplicate native flag trace '+flag[1]+' '+flag[2]+' '+flag[3])
                fields[flag[3]]=flag[4]=='yes'
            continue
        match=re.search(re.escape(MARKER)+r' STATE ([A-Za-z0-9_.]+) (.*)',line)
        require(bool(match),'Undeclared or malformed native state trace')
        if not match:continue
        label=match[1];require(label in labels,'Undeclared native state trace label '+label)
        pairs=re.findall(r'([A-Za-z_]+)=([^ ]+)',match[2]);fields=dict(pairs)
        require(len(fields)==len(pairs),'Duplicate native state fields '+label)
        require(set(fields)==STATE_FIELDS,'Missing/unexpected native state fields '+label)
        row={'label':label,'line_index':line_index,'fields':fields,'line':line}
        try:
            numeric={key:Decimal(fields[key]) for key in NUMERIC_FIELDS}
            require(all(value.is_finite() for value in numeric.values()),'Nonfinite native state trace '+label)
            row['cash_delta_thousand_usd_at_log_precision']={tag:str((numeric[tag+'_cash']-numeric[tag+'_cash_before'])*Decimal(1000000)) for tag in ('USA','HOL')}
        except (KeyError,ValueError,ArithmeticError):
            require(False,'Invalid numeric native state trace '+label)
        rows.append(row)
    for row in rows:
        require(all(set(row.get('flags',{}).get(tag,{}))==set(FLAGS) for tag in ('USA','HOL')),'Incomplete actual flag trace '+row['label'])
    return rows


def option_overlay(raw, parser):
    """Insert exact byte islands at the start/end of each original option body."""
    text = raw.decode('utf-8')
    tokens = [m for m in TOKEN.finditer(text) if not m[0].startswith('#')]
    edits = []; found = []
    for index, token in enumerate(tokens):
        if token[0] != 'option' or index+2 >= len(tokens):
            continue
        if (tokens[index+1][0], tokens[index+2][0]) != ('=', '{'):
            continue
        level = 1; cursor = index+3; name = None
        while cursor < len(tokens) and level:
            value = tokens[cursor][0]
            if level == 1 and value == 'name' and tokens[cursor+1][0] == '=':
                name = tokens[cursor+2][0].strip('"')
            if value == '{': level += 1
            elif value == '}': level -= 1
            cursor += 1
        assert not level, 'Unclosed original option'
        if name not in OPTION_NAMES:
            continue
        found.append(name)
        for position, suffix in ((tokens[index+2].end(), 'before'),
                                 (tokens[cursor-1].start(), 'after')):
            label = name+'.'+suffix; insertion = island(label)
            edits.append((position, {'label': label, 'insertion': insertion}))
    assert sorted(found) == sorted(OPTION_NAMES), ('Ambiguous original options', found)
    played = text
    for position, spec in sorted(edits, key=lambda item: item[0], reverse=True):
        played = played[:position]+spec['insertion']+played[position:]
    played = played.encode('utf-8')
    specs = [spec for position, spec in edits]
    stripped = strip_islands(played, specs)
    assert stripped == raw, 'Trace did not recover original source bytes'
    assert parser.ast(stripped) == parser.ast(raw), 'Trace changed original option AST'
    return played, {'source': 'events/00_Energy_events.txt',
                    'original_sha256': sha(raw), 'played_sha256': sha(played),
                    'original_ast': parser.ast(raw), 'islands': specs,
                    'exact_byte_recovery': True}


def strip_islands(raw, specs):
    """Fail closed on missing, duplicated or unexpected executable trace text."""
    result = raw
    for spec in specs:
        expected = island(spec['label'])
        assert spec['insertion'] == expected, 'Changed read-only trace declaration'
        needle = expected.encode('utf-8')
        assert result.count(needle) == 1, 'Missing/duplicated trace island '+spec['label']
        result = result.replace(needle, b'', 1)
    assert MARKER.encode('ascii') not in result, 'Undeclared trace island remains'
    return result
