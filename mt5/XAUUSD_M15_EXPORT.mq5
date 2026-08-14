//+------------------------------------------------------------------+
//| XAUUSD_M15_EXPORT.mq5                                            |
//| Exports broker-native XAUUSD M15 history for V15 validation.     |
//| No trading operations are performed.                             |
//+------------------------------------------------------------------+
#property script_show_inputs

input string InpSymbol = "XAUUSD";
input int    InpBars   = 50000;
input string InpFile   = "xauusd_m15_broker.csv";

void OnStart()
{
   string symbol = InpSymbol;
   if(!SymbolSelect(symbol, true))
   {
      Print("SYMBOL_SELECT_FAILED: ", symbol);
      return;
   }

   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int copied = CopyRates(symbol, PERIOD_M15, 0, InpBars, rates);
   if(copied <= 0)
   {
      Print("COPY_RATES_FAILED: ", symbol, " error=", GetLastError());
      return;
   }

   string filename = InpFile;
   int handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      Print("FILE_OPEN_FAILED: ", filename, " error=", GetLastError());
      return;
   }

   FileWrite(handle, "time", "open", "high", "low", "close", "tick_volume", "real_volume", "spread");

   for(int i = 0; i < copied; i++)
   {
      FileWrite(
         handle,
         TimeToString(rates[i].time, TIME_DATE|TIME_SECONDS),
         DoubleToString(rates[i].open, 8),
         DoubleToString(rates[i].high, 8),
         DoubleToString(rates[i].low, 8),
         DoubleToString(rates[i].close, 8),
         (long)rates[i].tick_volume,
         (long)rates[i].real_volume,
         (int)rates[i].spread
      );
   }

   FileClose(handle);
   Print("EXPORT_OK symbol=", symbol, " timeframe=M15 bars=", copied, " file=", filename);
   Print("FILE_LOCATION: terminal Common\\Files or terminal Files depending on your MT5 setup.");
}
