#!/bin/bash

# List of tickers to test
TICKERS="SPY,QQQ,IAU,GLD,BNO,TLT,CPER,DBA,EUO,UUP,USDU"

echo "Running Turtle Signal check for: $TICKERS"
echo "--------------------------------------------------"

python3 turtle_signal.py "$TICKERS"
