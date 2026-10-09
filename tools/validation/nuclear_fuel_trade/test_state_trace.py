"""The optional probe trace must be removable and unable to change business state."""
import unittest
import native_state_trace as trace
import model as b
from test_builder_strings import p


class StateTrace(unittest.TestCase):
    def test_original_eight_option_bodies_recover_exact_source_bytes_and_ast(self):
        raw=(b.ROOT/'events/00_Energy_events.txt').read_bytes()
        played,declaration=trace.option_overlay(raw,p)
        self.assertEqual(len(declaration['islands']),16)
        self.assertEqual(trace.strip_islands(played,declaration['islands']),raw)
        self.assertEqual(p.ast(raw),declaration['original_ast'])
        self.assertEqual(played.startswith(b'\xef\xbb\xbf'),raw.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(played.count(b'\n'),raw.count(b'\n'))

    def test_only_log_and_flag_read_conditions_are_inserted(self):
        def walk(nodes):
            for key,op,value in nodes:
                yield key
                if isinstance(value,list):yield from walk(value)
        allowed={'log','if','limit','USA','HOL','has_country_flag','else'}
        nodes=p.ast(trace.island('sell_accept.poll'))
        self.assertLessEqual(set(walk(nodes)),allowed)
        self.assertEqual(sum(key=='log' for key in walk(nodes)),21)
        self.assertEqual([key for key,op,value in nodes],['log']+['if','else']*10)
        for key,op,value in nodes:
            if key=='if':
                self.assertEqual([child for child,op,body in value],['limit','log'])
            elif key=='else':self.assertEqual([child for child,op,body in value],['log'])

    def test_mutating_and_unknown_trace_islands_fail_closed(self):
        insertion=trace.island('sell_accept.deadline')
        for bad in (insertion+' set_variable = { treasury = 999 } ',
                    insertion.replace('has_country_flag','set_country_flag'),
                    insertion.replace('yes" } else = {','yes" else = {',1)):
            with self.subTest(bad=bad[-50:]):
                with self.assertRaises(AssertionError):
                    trace.strip_islands(bad.encode(),[{'label':'sell_accept.deadline','insertion':bad}])
        with self.assertRaises(AssertionError):
            trace.strip_islands((insertion+' log = "'+trace.MARKER+' STATE stray" ').encode(),[{'label':'sell_accept.deadline','insertion':insertion}])

    def test_missing_or_duplicate_trace_island_cannot_be_silently_removed(self):
        insertion=trace.island('energy.11.a.after')
        spec=[{'label':'energy.11.a.after','insertion':insertion}]
        for raw in (b'',(insertion+insertion).encode()):
            with self.assertRaises(AssertionError):trace.strip_islands(raw,spec)

    def test_recorded_numeric_and_flag_trace_integrity_rejects_corruption(self):
        label='sell_accept.poll'
        fields={key:'0' for key in trace.STATE_FIELDS}
        fields.update(ROOT='USA',THIS='USA',FROM='HOL',USA_cash='500.00025',USA_cash_before='500',HOL_cash='499.99975',HOL_cash_before='500')
        state=trace.MARKER+' STATE '+label+' '+' '.join(k+'='+v for k,v in fields.items())
        flags=[trace.MARKER+' FLAG '+label+' actor='+tag+' flag='+flag+' present=no' for tag in ('USA','HOL') for flag in trace.FLAGS]
        valid='\n'.join([state,*flags])
        def read(text):
            errors=[]
            rows=trace.read_records(text,{label},lambda condition,message: errors.append(message) if not condition else None)
            return rows,errors
        rows,errors=read(valid+'\n'+valid)
        self.assertEqual(errors,[])
        self.assertEqual(len(rows),2,'Repeated bounded polls are separate valid state islands')
        self.assertEqual(rows[0]['cash_delta_thousand_usd_at_log_precision'],{'USA':'250.00000','HOL':'-250.00000'})
        for mutant in (valid+'\n'+flags[-1],valid.replace(trace.FLAGS[0],'unknown_flag',1),
                       valid.replace('USA_cash=500.00025','USA_cash=500.00025 USA_cash=777'),
                       valid.replace('USA_cash=500.00025','USA_cash=NaN'),
                       valid.replace('USA_cash=500.00025','USA_cash=Infinity'),
                       valid.replace('USA_cash=500.00025',''),
                       '\n'.join([state,*flags[:-1]]),valid+'\n'+trace.MARKER+' STRAY unknown'):
            with self.subTest(mutant=mutant[-80:]):self.assertTrue(read(mutant)[1])


if __name__=='__main__':unittest.main()
