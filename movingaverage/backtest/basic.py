import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import backtrader as bt
import yfinance as yf
from yfinance.utils import attributes


# 策略逻辑
class MACrossStrategy(bt.Strategy):
    params = (
        ("short_period", 10),
        ("long_period", 20),
        ("atr_period", 14),
    )

    def __init__(self):
        self.short_ma = bt.talib.EMA(timeperiod=self.p.short_period)  # pyright: ignore
        self.long_ma = bt.ind.EMA(period=self.p.long_period)  # pyright: ignore
        self.atr = bt.ind.ATR(period=self.p.atr_period)  # pyright: ignore

        self.crossup = bt.ind.CrossUp(self.short_ma, self.long_ma)  # pyright: ignore
        self.crossdown = bt.ind.CrossDown(self.short_ma, self.long_ma)  # pyright: ignore

    def next(self):
        long_entry = self.crossup[0] == 1 and self.position.size <= 0
        short_entry = self.crossdown[0] == 1 and self.position.size >= 0

        long_exit = self.crossdown[0] == 1 and self.position.size > 0
        short_exit = self.crossup[0] == 1 and self.position.size < 0

        if long_entry:
            self.order_target_percent(target=0.99)
        elif short_entry:
            self.order_target_percent(target=-0.99)

        if long_exit:
            self.close()
        elif short_exit:
            self.close()


def main():
    cerebro = bt.Cerebro()

    cerebro.broker.setcommission(0.0005)
    cerebro.broker.set_slippage_perc(0.0001)
    cerebro.broker.setcash(1e6)

    data = yf.download(  # pyright: ignore
        tickers="BTC-USD",
        start="2020-01-01",
        interval="1d",
        multi_level_index=False,
    )
    data = bt.feeds.PandasData(dataname=data)  # pyright: ignore
    cerebro.adddata(data)  # pyright: ignore

    cerebro.addstrategy(MACrossStrategy)

    cerebro.run()
    cerebro.plot(style="candle")


if __name__ == "__main__":
    main()
