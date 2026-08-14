"""Broker-matched XAUUSD audit harness.

Expected file: data/xauusd_m15_broker.csv
Required columns: time, open, high, low, close
Optional: tick_volume, real_volume, spread
Diagnostic only. No live-trading changes.
"""
from __future__ import annotations
from pathlib import Path
import os
import pandas as pd
import backtest as bt

DATA_PATH=Path(os.getenv("BROKER_DATA_PATH","data/xauusd_m15_broker.csv"))
MIN_BARS=int(os.getenv("BROKER_MIN_BARS","20000"))
COST=float(os.getenv("AUDIT_COST_R","0.10"))

def load():
    if not DATA_PATH.exists():
        raise SystemExit(f"BROKER_DATA_MISSING: {DATA_PATH}")
    df=pd.read_csv(DATA_PATH)
    df.columns=[str(c).strip().lower() for c in df.columns]
    required=["time","open","high","low","close"]
    missing=[c for c in required if c not in df.columns]
    if missing: raise SystemExit(f"BROKER_DATA_COLUMNS_MISSING: {missing}")
    df["time"]=pd.to_datetime(df["time"],errors="coerce",utc=True)
    for c in ["open","high","low","close","tick_volume","real_volume","spread"]:
        if c in df: df[c]=pd.to_numeric(df[c],errors="coerce")
    df=df.dropna(subset=required).sort_values("time").drop_duplicates("time").reset_index(drop=True)
    invalid=((df.high<df.low)|(df.high<df.open)|(df.high<df.close)|(df.low>df.open)|(df.low>df.close))
    if invalid.any(): raise SystemExit(f"BROKER_DATA_INVALID_OHLC: {int(invalid.sum())}")
    if "tick_volume" not in df: df["tick_volume"]=0
    if "real_volume" not in df: df["real_volume"]=0
    if "spread" not in df: df["spread"]=0
    return df

def stats(label,trades):
    r=[float(t.get("r_multiple",0)) for t in trades]; n=len(r); wins=sum(x>0 for x in r); gp=sum(x for x in r if x>0); gl=abs(sum(x for x in r if x<0)); net=sum(r)
    return label,n,round(100*wins/n,2) if n else 0,round(gp/gl,3) if gl else 0,round(net-COST*n,4)

def main():
    df=load(); first,last=df.time.iloc[0],df.time.iloc[-1]; span=(last-first).total_seconds()/86400
    print("="*78); print("FOREX AUTO TRADER PRO - BROKER XAUUSD CSV AUDIT"); print("="*78)
    print(f"File={DATA_PATH} bars={len(df)} first={first} last={last} span_days={span:.2f}")
    print(f"Minimum-bar gate ({MIN_BARS})={'PASS' if len(df)>=MIN_BARS else 'FAIL'}")
    result=bt.backtest_strategy(df=df,ema_fast=20,ema_slow=50,atr_period=14,atr_sl_multiplier=1.6,reward_risk=1.6,min_score=80)
    trades=result.get("trades",[]); print("Baseline S80:",stats("ALL",trades))
    print("BUY:",stats("BUY",[t for t in trades if t.get("signal")=="BUY"]))
    print("SELL:",stats("SELL",[t for t in trades if t.get("signal")=="SELL"]))
    print("No live-trading setting changed.")
if __name__=="__main__": main()
