"""V15 Triple-MTF probe.

Canonical S80 backtest already requires H1+M15 agreement. This probe therefore
MUST NOT monkey-patch signal generation: it takes the canonical trade stream
and applies the incremental M1 confirmation to the recorded trade attribution.
No live trading changes are made.
"""
from __future__ import annotations
import os, time
import numpy as np
import pandas as pd
from backtest import backtest_strategy
from data import get_bars

BARS = int(os.getenv("ROBUSTNESS_BARS", "4608"))
SYMBOL = os.getenv("ROBUSTNESS_SYMBOL", "XAUUSD")
COST = float(os.getenv("AUDIT_COST_R", "0.10"))
BOOTSTRAP_RUNS = min(int(os.getenv("BOOTSTRAP_RUNS", "1500")), 1500)
SCORE, SL, RR = 80, 1.6, 1.6
WINDOWS = (("W1_0_50",0,.50),("W2_25_75",.25,.75),("W3_50_100",.50,1),("W4_0_60",0,.60),("W5_40_100",.40,1))
HOLDOUTS = (("HOLDOUT_40",.60,1),("HOLDOUT_30",.70,1),("HOLDOUT_25",.75,1),("HOLDOUT_50",.50,1))

def metrics(trades):
    r=np.asarray([float(t["r_multiple"]) for t in trades],dtype=float); n=len(r); wins=int(np.sum(r>0))
    gp=float(r[r>0].sum()) if np.any(r>0) else 0.; gl=float(abs(r[r<0].sum())) if np.any(r<0) else 0.
    pf=gp/gl if gl else (float("inf") if gp else 0.); net=float(r.sum())
    return {"trades":n,"wins":wins,"win_rate":wins/n*100 if n else 0.,"profit_factor":pf,"net_r":net,"expectancy_r":net/n if n else 0.,"after_cost_r":net-COST*n}

def row(label,m):
    pf="inf" if not np.isfinite(m["profit_factor"]) else f"{m['profit_factor']:.3f}"
    print(f"{label:16s} trades={m['trades']:3d} WR={m['win_rate']:6.2f}% PF={pf:>7s} After={m['after_cost_r']:7.3f}")

def window(trades,a,b,total):
    s,e=int(total*a),int(total*b)
    return [t for t in trades if s<=int(t.get("entry_index",-1))<e]

def bootstrap(values,seed=1604):
    if not values:return 0.,0.,1.
    x=np.asarray(values,dtype=float)-COST; rng=np.random.default_rng(seed); n=len(x); out=np.empty(BOOTSTRAP_RUNS)
    for start in range(0,BOOTSTRAP_RUNS,500):
        m=min(500,BOOTSTRAP_RUNS-start); idx=rng.integers(0,n,size=(m,n)); out[start:start+m]=x[idx].sum(axis=1)
    return float(np.percentile(out,5)),float(np.percentile(out,50)),float(np.mean(out<=0))

def main():
    t0=time.monotonic(); print("="*78); print("FOREX AUTO TRADER PRO - GOLD V15 TRIPLE MTF PROBE"); print("="*78)
    print(f"Symbol : {SYMBOL} | M15 | bars={BARS} | S80 | SL={SL} | RR={RR}")
    print("Incremental filter: canonical H1+M15 trades -> require recorded M1 agreement")
    print("Parameter fitting: NONE"); print("Live trading: NOT ENABLED")
    df=get_bars(SYMBOL,"M15",count=BARS,source="YAHOO")
    if len(df)<1000: raise RuntimeError(f"Insufficient bars: {len(df)}")
    canonical=backtest_strategy(df=df,ema_fast=20,ema_slow=50,atr_period=14,atr_sl_multiplier=SL,reward_risk=RR,min_score=SCORE)
    all_trades=canonical.get("trades",[])
    triple=[t for t in all_trades if t.get("signal")==t.get("mtf_m1") and t.get("mtf_h1")==t.get("signal") and t.get("mtf_m15")==t.get("signal")]
    rejected=len(all_trades)-len(triple)
    print("\nFILTER ATTRIBUTION"); print(f"Canonical H1+M15 trades : {len(all_trades)}"); print(f"Rejected by M1          : {rejected}"); print(f"Triple-MTF trades       : {len(triple)}")
    full=metrics(triple); print("\nTRIPLE-MTF FULL SAMPLE"); row("FULL",full)
    windows=[]; print("\nROLLING WINDOWS")
    for label,a,b in WINDOWS:
        x=metrics(window(triple,a,b,len(df))); x.update(candidate="S80_TRIPLE_MTF",label=label,positive=x["after_cost_r"]>0); windows.append(x); row(label,x)
    holdouts=[]; print("\nRECENT HOLDOUTS")
    for label,a,b in HOLDOUTS:
        x=metrics(window(triple,a,b,len(df))); x.update(candidate="S80_TRIPLE_MTF",label=label,positive=x["after_cost_r"]>0); holdouts.append(x); row(label,x)
    p05,p50,prob=bootstrap([float(t["r_multiple"]) for t in triple]); print("\nBOOTSTRAP COST STRESS"); print(f"P05 final R      : {p05:.3f}"); print(f"P50 final R      : {p50:.3f}"); print(f"Probability <=0  : {prob*100:.2f}%")
    wp=sum(x["positive"] for x in windows)>=4; hp=sum(x["positive"] for x in holdouts)>=3; fp=full["after_cost_r"]>0 and full["trades"]>=20; bp=p05>0 and prob<.10; ready=fp and wp and hp and bp
    print("\nTRIPLE-MTF DECISION"); print(f"Full after-cost positive + 20 trades : {'PASS' if fp else 'FAIL'}"); print(f"Windows 4/5 positive                : {'PASS' if wp else 'FAIL'}"); print(f"Holdouts 3/4 positive                : {'PASS' if hp else 'FAIL'}"); print(f"Bootstrap P05 > 0 AND Prob<=0 <10%  : {'PASS' if bp else 'FAIL'}"); print("STATUS: READY_CANDIDATE" if ready else "STATUS: REJECT_CANDIDATE"); print(f"Runtime seconds={time.monotonic()-t0:.2f}")
    pd.DataFrame([full]).assign(candidate="S80_TRIPLE_MTF",p05=p05,p50=p50,probability_nonpositive=prob,canonical_trades=len(all_trades),m1_rejected=rejected).to_csv("gold_v15_triple_mtf_full.csv",index=False)
    pd.DataFrame(windows).to_csv("gold_v15_triple_mtf_windows.csv",index=False); pd.DataFrame(holdouts).to_csv("gold_v15_triple_mtf_holdouts.csv",index=False)

if __name__=="__main__": main()
