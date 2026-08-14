"""Diagnostic audit: compare canonical S80 against a long-only variant.
No live-trading settings are changed. This deliberately tests a pre-specified
hypothesis from edge attribution: STRONG_BUY was profitable while STRONG_SELL
was not. The decision is made by fixed robustness gates, not optimization.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import backtest as bt
from data import get_bars

BARS=int(os.getenv('ROBUSTNESS_BARS','4608')); SYMBOL=os.getenv('ROBUSTNESS_SYMBOL','XAUUSD'); COST=float(os.getenv('AUDIT_COST_R','0.10')); BOOT=int(os.getenv('BOOTSTRAP_RUNS','2000'))
WINDOWS=[('W1_0_50',0,.5),('W2_25_75',.25,.75),('W3_50_100',.5,1),('W4_0_60',0,.6),('W5_40_100',.4,1)]
HOLDOUTS=[('H40',.6,1),('H30',.7,1),('H25',.75,1),('H50',.5,1)]

def summary(label,trades):
 r=np.array([float(t.get('r_multiple',0)) for t in trades],dtype=float); n=len(r); w=int((r>0).sum()); gp=r[r>0].sum(); gl=abs(r[r<0].sum()); net=float(r.sum()); pf=gp/gl if gl else (999 if gp else 0)
 return {'segment':label,'trades':n,'win_rate':100*w/n if n else 0,'profit_factor':pf,'net_r':net,'after_cost_r':net-COST*n,'expectancy_r':net/n if n else 0}

def slice_trades(trades,a,b,total):
 lo,hi=int(total*a),int(total*b); return [t for t in trades if lo<=int(t.get('entry_index',t.get('index',-1)))<hi]

def boot(trades):
 r=np.array([float(t.get('r_multiple',0))-COST for t in trades],dtype=float); n=len(r)
 if not n:return (0,0,1)
 rng=np.random.default_rng(1604); vals=np.empty(BOOT)
 for s in range(0,BOOT,500):
  m=min(500,BOOT-s); vals[s:s+m]=rng.choice(r,size=(m,n),replace=True).sum(axis=1)
 return tuple(map(float,(np.percentile(vals,5),np.percentile(vals,50),np.mean(vals<=0))))

def main():
 print('='*78); print('FOREX AUTO TRADER PRO - GOLD V15 LONG-ONLY ROBUSTNESS'); print('='*78)
 df=get_bars(SYMBOL,'M15',count=BARS,source='YAHOO')
 base=bt.backtest_strategy(df=df,ema_fast=20,ema_slow=50,atr_period=14,atr_sl_multiplier=1.6,reward_risk=1.6,min_score=80)
 alltr=base.get('trades',[]); longs=[t for t in alltr if str(t.get('signal',t.get('direction',''))).upper()=='BUY']
 rows=[summary('FULL',longs)]; print(f'Canonical={len(alltr)} | Long-only={len(longs)}')
 print('\nFULL',rows[0])
 wp=[]; hp=[]
 for name,a,b in WINDOWS:
  x=summary(name,slice_trades(longs,a,b,len(df))); wp.append(x['after_cost_r']>0); print(name,x)
 for name,a,b in HOLDOUTS:
  x=summary(name,slice_trades(longs,a,b,len(df))); hp.append(x['after_cost_r']>0); print(name,x)
 p05,p50,prob=boot(longs); print(f'BOOTSTRAP P05={p05:.3f} P50={p50:.3f} Prob<=0={prob*100:.2f}%')
 passed=(rows[0]['trades']>=20 and rows[0]['after_cost_r']>0 and sum(wp)>=4 and sum(hp)>=3 and p05>0 and prob<.10)
 print('STATUS:', 'PASS_CANDIDATE' if passed else 'REJECT_CANDIDATE')
 pd.DataFrame(rows).to_csv('gold_v15_long_only_full.csv',index=False)
 print('No live-trading setting changed.')
if __name__=='__main__': main()
