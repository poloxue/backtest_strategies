# pip install backtrader
# pip install https://github.com/poloxue/findata.git
import backtrader as bt
import pandas as pd
import matplotlib.pyplot as plt

from collections import defaultdict

from findata import data_ccxt


class MovingAverageStrategy(bt.Strategy):
    params = (
        ("short_period", 10),
        ("long_period", 20),
        ("atr_period", 14),
        ("rsi_period", 14),
    )

    def __init__(self):
        if self.p.short_period >= self.p.long_period:
            raise bt.errors.StrategySkipError

        self.indicators = {}
        for data in self.datas:
            self.indicators[data] = {
                "short_ma": bt.indicators.EMA(data, period=self.p.short_period),  # pyright: ignore
                "long_ma": bt.indicators.EMA(data, period=self.p.long_period),  # pyright: ignore
                "atr": bt.indicators.ATR(data, period=self.p.atr_period),  # pyright: ignore
                "rsi": bt.indicators.RSI(data, period=self.p.rsi_period),  # pyright: ignore
            }
        self.count = len(self.datas)
        self.orders = defaultdict(list)

    def notify_order(self, order: bt.Order):
        if order.status in [
            order.Completed,
            order.Canceled,
            order.Expired,
            order.Rejected,
            order.Margin,
        ]:
            self.orders[order.data].remove(order)

    def cancel_orders(self, data):
        for order in self.orders[data]:
            self.cancel(order)  

    def next(self):
        for data in self.datas:
            pos = self.getposition(data)
            if not pos.size:
                self.cancel_orders(data)

            close = data.close
            indicator = self.indicators[data]
            short_ma = indicator["short_ma"]
            long_ma = indicator["long_ma"]
            atr = indicator["atr"]
            rsi = indicator["rsi"]
            order_value = (
                min(0.02 / (3 * atr[0] / close[0]), 2)
                / self.count
                * self.broker.getvalue()
            )
            volume = order_value / close[0]
            if close[0] > short_ma[0] > long_ma[0] and rsi[0] < 70 and pos.size <= 0:
                if pos.size < 0:
                    self.orders[data].append(self.close(data))
                stop_price = close[0] - 3 * atr[0]
                self.orders[data].append(self.buy(data, volume))
                self.orders[data].append(
                    self.sell(data, volume, exectype=bt.Order.Stop, price=stop_price)
                )
            elif close[0] < short_ma[0] < long_ma[0] and rsi[0] > 30 and pos.size >= 0:
                if pos.size > 0:
                    self.orders[data].append(self.close(data))
                stop_price = close[0] + 3 * atr[0]
                self.orders[data].append(self.sell(data, volume))
                self.orders[data].append(
                    self.buy(data, volume, exectype=bt.Order.Stop, price=stop_price)
                )


def print_stats(strategy):
    final_value = strategy[0].broker.getvalue()

    analyzers = strategy[0].analyzers
    sharpe_ratio = analyzers.sharpe_ratio.get_analysis()["sharperatio"]
    max_drawdown = analyzers.drawdown.get_analysis()["max"]["drawdown"]
    print(f"""
    \r最终净值: {final_value}
    \r夏普比率: {sharpe_ratio}
    \r最大回撤: {max_drawdown}
    """)


def main():
    stats = []

    cerebro = bt.Cerebro()
    cerebro.broker.setcommission(0.0005)
    cerebro.broker.setcash(1e6)

    symbols = ["BTC/USDT", "ETH/USDT"]
    # symbols = ["ADA/USDT", "SOL/USDT", "BNB/USDT"]
    for symbol in symbols:
        data = data_ccxt.download(
            symbol,
            start_date="2022-01-01",
            end_date="2025-04-05",
            exchange_name="binance",
            interval="4h",
        )
        cerebro.adddata(bt.feeds.PandasData(dataname=data))  # pyright: ignore

    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="returns")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe_ratio")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.SQN, _name="sqn")
    cerebro.addstrategy(MovingAverageStrategy, short_period=10, long_period=20)
    # cerebro.run()
    # cerebro.plot()
    # return

    strat = cerebro.run()
    if strat:
        analyzers = strat[0].analyzers
        sharpe_ratio = analyzers.sharpe_ratio.get_analysis()["sharperatio"]
        max_drawdown = analyzers.drawdown.get_analysis()["max"]["drawdown"]
        sqn = analyzers.sqn.get_analysis()["sqn"]
        stats.append(
            {
                "final_value": strat[0].broker.getvalue(),
                "sharpe_ratio": sharpe_ratio,
                "max_drawdown": max_drawdown,
                "sqn": sqn,
                "strategy": strat,
            }
        )

    short_period = strat[0].params.short_period
    long_period = strat[0].params.long_period
    print(f"short_period:{short_period}, long_period:{long_period}")

    print_stats(strat)

    returns = strat[0].analyzers.returns.get_analysis()
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
