"""V15 edge attribution audit. Diagnostic only; no live-trading changes."""
from __future__ import annotations
import os
import pandas as pd
import backtest as bt
from data import get_bars
BARS=int(os.getenv('ROBUSTNESS_BARS','4608')); SYMBOL=os.getenv('ROBUSTNESS_SYMBOL','XAUUSD'); COST=float(os.getenv('AUDIT_COST_R','0.10'))
def stats(name,trades):
 r=[float(t.get('r_multiple',0.0)) for t in trades]; n=len(r); w=sum(x>0 for x in r); gp=sum(x for x in r if x>0); gl=abs(sum(x for x in r if x<0)); net=sum(r)
 return {'segment':name,'trades':n,'win_rate':round(100*w/n,2) if n else 0.0,'profit_factor':round(gp/gl,3) if gl else (999.0 if gp else 0.0),'net_r':round(net,4),'after_cost_r':round(net-COST*n,4),'expectancy_r':round(net/n,4) if n else 0.0}
def main():
 print('='*78); print('FOREX AUTO TRADER PRO - GOLD V15 EDGE ATTRIBUTION'); print('='*78)
 df=get_bars(SYMBOL,'M15',count=BARS,source='YAHOO')
 result=bt.backtest_strategy(df=df,ema_fast=20,ema_slow=50,atr_period=14,atr_sl_multiplier=1.6,reward_risk=1.6,min_score=80)
 trades=result.get('trades',[]); print(f'Canonical trades={len(trades)}')
 rows=[stats('ALL',trades)]
 for direction in ['BUY','SELL']:
  rows.append(stats(direction,[t for t in trades if str(t.get('signal',t.get('direction',''))).upper()==direction]))
 for key in ['score','score_bucket','adx_regime','trend','mtf_status']:
  groups={str(t.get(key,'UNKNOWN')) for t in trades}
  if len(groups)>1 and len(groups)<12:
   for g in sorted(groups): rows.append(stats(f'{key}={g}',[t for t in trades if str(t.get(key,'UNKNOWN'))==g]))
 out=pd.DataFrame(rows); print(out.to_string(index=False)); out.to_csv('gold_v15_edge_attribution.csv',index=False); pd.DataFrame(trades).to_csv('gold_v15_edge_trades.csv',index=False); print('No live-trading setting changed.')
if __name__=='__main__': main()
