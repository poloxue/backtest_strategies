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
        if self.p.short_period >= self.p.long_period:
            raise bt.StrategySkipError()

        self.short_ma = bt.talib.EMA(timeperiod=self.p.short_period)  # pyright: ignore
        self.long_ma = bt.ind.EMA(period=self.p.long_period)  # pyright: ignore
        self.atr = bt.ind.ATR(period=self.p.atr_period)  # pyright: ignore

        self.crossup = bt.ind.CrossUp(self.short_ma, self.long_ma)  # pyright: ignore
        self.crossdown = bt.ind.CrossDown(self.short_ma, self.long_ma)  # pyright: ignore

        self.stop_order = None

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

    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
    cerebro.addanalyzer(bt.analyzers.SQN, _name="sqn")

    cerebro.optstrategy(
        MACrossStrategy,
        short_period=range(5, 50, 5),
        long_period=range(20, 200, 10),
    )

    opt_returns = cerebro.run(optreturn=False)

    best_strategy = None
    for ret in opt_returns:
        if len(ret):
            if best_strategy is None:
                best_strategy = ret[0]
            else:
                best_sqn = best_strategy.analyzers.sqn.get_analysis()["sqn"]
                sqn = ret[0].analyzers.sqn.get_analysis()["sqn"]
                if best_sqn < sqn:
                    best_strategy = ret[0]

    if best_strategy is None:
        return

    short_period = best_strategy.params.short_period
    long_period = best_strategy.params.long_period
    sharpe_ratio = best_strategy.analyzers.sharpe.get_analysis()["sharperatio"]
    max_drawdown = best_strategy.analyzers.drawdown.get_analysis()["max"]["drawdown"]
    sqn = best_strategy.analyzers.sqn.get_analysis()["sqn"]
    final_value = best_strategy.broker.getvalue()

    print(f"参数组合：short_period {short_period}, long_period {long_period}")  # pyright: ignore
    print(f"夏普比率：{sharpe_ratio}")
    print(f"最大回撤：{max_drawdown}")
    print(f"SQN：{sqn}")
    print(f"最终净值：{final_value}")

    returns = best_strategy.analyzers.getbyname("timereturn").get_analysis()
    returns_series = pd.Series(returns)
    net_value = (1 + returns_series).cumprod()
    ax = net_value.plot(title="Returns", figsize=(12, 5))

    end_value = net_value.iloc[-1]
    end_index = net_value.index[-1]

    ax.text(
        end_index,
        end_value,
        f"End: {end_value:.2f}",
        ha="right",
        va="top",
        bbox=dict(facecolor="white", alpha=0.8),
    )

    plt.show()


if __name__ == "__main__":
    main()
