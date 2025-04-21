import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import backtrader as bt
import yfinance as yf
from typing import Optional
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

        self.short_ma = bt.ind.EMA(period=self.p.short_period)  # pyright: ignore
        self.long_ma = bt.ind.EMA(period=self.p.long_period)  # pyright: ignore
        self.atr = bt.ind.ATR(period=self.p.atr_period)  # pyright: ignore

        self.crossup = bt.ind.CrossUp(self.short_ma, self.long_ma)  # pyright: ignore
        self.crossdown = bt.ind.CrossDown(self.short_ma, self.long_ma)  # pyright: ignore

        self.direction = None

        self.stop_buy_order: Optional[bt.Order] = None
        self.stop_sell_order: Optional[bt.Order] = None

    def notify_trade(self, trade: bt.Trade):
        if self.position.size >= 0 and self.stop_buy_order is not None:
            self.cancel(self.stop_buy_order)
            self.stop_buy_order = None
        elif self.position.size <= 0 and self.stop_sell_order is not None:
            self.cancel(self.stop_sell_order)
            self.stop_sell_order = None

    def next(self):
        print(
            f"回测进度: {bt.num2date(self.data.datetime[0])} {self.short_ma[-1]}\r",
            end="",
        )

        current_time = self.datetime.time()
        if current_time.minute != 1 or current_time.hour != 0:
            return

        if self.crossup[-1] == 1:
            self.direction = "long"
        elif self.crossdown[-1] == 1:
            self.direction = "short"

        long_entry = self.direction == "long" and self.position.size <= 0
        short_entry = self.direction == "short" and self.position.size >= 0

        long_exit = self.crossdown[-1] == 1 and self.position.size > 0
        short_exit = self.crossup[-1] == 1 and self.position.size < 0

        max_sl_pct = 0.02
        target_percent = max_sl_pct / (3 * self.atr[-1] / self.data.close[-1])
        if long_entry:
            stop_price = self.data.close[-1] - 3 * self.atr[-1]
            order = self.order_target_percent(target=target_percent)
            if order is not None:
                self.stop_sell_order = self.sell(
                    size=order.size, exectype=bt.Order.Stop, price=stop_price
                )
        elif short_entry:
            stop_price = self.data.close[-1] + 3 * self.atr[-1]
            order = self.order_target_percent(target=-target_percent)
            if order is not None:
                self.stop_buy_order = self.buy(
                    size=order.size, exectype=bt.Order.Stop, price=stop_price
                )

        if long_exit:
            self.close()
        elif short_exit:
            self.close()


def main():
    cerebro = bt.Cerebro()

    cerebro.broker.setcommission(0.0005)
    cerebro.broker.set_slippage_perc(0.0001)
    cerebro.broker.setcash(1e6)

    data = pd.read_csv(  # pyright: ignore
        "btcusdt-1m.csv", parse_dates=["datetime"], index_col=["datetime"]
    )
    data = bt.feeds.PandasData(dataname=data)  # pyright: ignore
    cerebro.replaydata(
        data,
        timeframe=bt.TimeFrame.Minutes,  # pyright: ignore
        compression=60 * 24,
    )

    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
    cerebro.addanalyzer(bt.analyzers.SQN, _name="sqn")

    cerebro.addstrategy(MACrossStrategy)

    strats = cerebro.run()
    cerebro.plot()

    best_strategy = strats[0]

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
