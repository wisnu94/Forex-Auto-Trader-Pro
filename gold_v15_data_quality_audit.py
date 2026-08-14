"""V15 data-quality gate. Diagnostic only; never changes live trading.
Checks whether the requested XAUUSD M15 sample is sufficiently long and whether
CI is using a broker/spot source or the documented Yahoo gold-futures proxy.
"""
from __future__ import annotations
import os
from data import get_bars, YAHOO_SYMBOL_MAP

BARS=int(os.getenv('ROBUSTNESS_BARS','4608')); SYMBOL=os.getenv('ROBUSTNESS_SYMBOL','XAUUSD'); SOURCE=os.getenv('DATA_SOURCE','YAHOO').upper()

def main():
    print('='*78); print('FOREX AUTO TRADER PRO - GOLD V15 DATA QUALITY AUDIT'); print('='*78)
    print(f'Symbol={SYMBOL} requested_bars={BARS} source={SOURCE}')
    proxy=YAHOO_SYMBOL_MAP.get(SYMBOL)
    if SOURCE=='YAHOO' and SYMBOL=='XAUUSD':
        print(f'WARNING: XAUUSD is mapped to Yahoo {proxy}, a gold-futures proxy, not broker spot XAUUSD.')
    df=get_bars(SYMBOL,'M15',count=BARS,source=SOURCE)
    n=len(df); first=df['time'].iloc[0]; last=df['time'].iloc[-1]
    span_days=(last-first).total_seconds()/86400
    print(f'Loaded bars={n}'); print(f'First={first}'); print(f'Last={last}'); print(f'Span_days={span_days:.2f}')
    print(f'Bar_count_gate={"PASS" if n>=BARS else "FAIL"}')
    # This is a data-quality report, not a profitability gate.
    print('Spot-XAUUSD-source gate:', 'PASS' if SOURCE=='MT5' else 'FAIL')
    print('STATUS:', 'DATA_READY_FOR_ROBUSTNESS' if n>=BARS and SOURCE=='MT5' else 'NOT_DATA_READY')
    print('No strategy or live-trading setting changed.')
if __name__=='__main__': main()
