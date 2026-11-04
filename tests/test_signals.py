import unittest
import numpy as np
import pandas as pd
from userm.config import CONFIG
from userm.signals import _states, calculate_etf_signals
from userm.data import load_etf_master,load_quotes
from userm.validation import _events_for_symbol


class SignalTests(unittest.TestCase):
    def test_state_rules_and_warning(self):
        normal={'date':pd.Timestamp('2026-01-02'),'close':101,'rs_ratio':99,'rs_momentum':100.2,
                'ma_10':100,'ma_20':98,'ma_50':97,'rel_5':.01,'rel_10':.02,'rel_20':-.04,'rel_60':-.02,
                'ret_5':.02,'breakout_20':False,'rvol_20':1.0}
        a=normal.copy();a['close']=98;a['ma_10']=99;a['ret_5']=-.01  # L1
        b=normal.copy()                                               # L2
        c=normal|{'rs_ratio':102,'rs_momentum':100.5,'rel_20':.06,'rel_60':.05,
                  'close':107,'breakout_20':True,'rvol_20':1.3}        # L3
        d=normal|{'rs_ratio':102,'rs_momentum':99.7,'rel_20':.03,'rel_60':.02,
                  'close':105,'breakout_20':False}                     # L4
        e=normal|{'close':94,'ma_20':98,'rs_momentum':99.1,'rel_5':-.03,
                  'rel_10':-.02,'rel_20':-.03,'ret_5':-.05,'rs_ratio':98}
        df=pd.DataFrame([a,b,c,d,e]);st,events,ages,_=_states(df,CONFIG)
        self.assertEqual(st,['L1','L2','L3','L4','W'])
        self.assertTrue(all(events))

    def test_no_same_day_execution(self):
        d=pd.DataFrame({'date':pd.bdate_range('2026-03-02',periods=9), 'etf':['X']*9,
                        'group':['行业']*9,'partition':['OOS']*9,'quadrant':['LEADING']*9,
                        'new_signal':[True]+[False]*8,'stage':['L2']+['N0']*8,
                        'close':[100,101,105,106,107,108,109,110,111],
                        'benchmark_close':[100,100,101,102,103,104,105,106,107]})
        e=_events_for_symbol(d,horizons=(5,))
        self.assertEqual(len(e),1)
        self.assertAlmostEqual(e.iloc[0]['forward_5'],109/101-1)
        self.assertAlmostEqual(e.iloc[0]['peer_forward_5'],105/100-1)

    def test_prefix_invariance_no_future_lookahead(self):
        q=load_quotes('etfs');m=load_etf_master()
        full=calculate_etf_signals(q,m)
        cutoff=pd.Timestamp('2025-12-31')
        past=calculate_etf_signals(q[q.date<=cutoff],m)
        a=full[full.date<=cutoff].sort_values(['etf','date']).reset_index(drop=True)
        b=past.sort_values(['etf','date']).reset_index(drop=True)
        self.assertEqual(len(a),len(b))
        np.testing.assert_allclose(a['rs_ratio'],b['rs_ratio'],equal_nan=True,atol=1e-9)
        np.testing.assert_allclose(a['rel_20'],b['rel_20'],equal_nan=True,atol=1e-10)
        self.assertEqual(a.stage.tolist(),b.stage.tolist())

    def test_master_has_exactly_20(self):
        m=load_etf_master()
        self.assertEqual(len(m),20)
        self.assertEqual(m.etf.nunique(),20)
        self.assertEqual(m.groupby('group').size().to_dict(),{'行业':11,'科技主题':9})


if __name__=='__main__':unittest.main()
