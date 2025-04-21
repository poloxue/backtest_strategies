import backtrader as bt


indicators = [attr for attr in dir(bt.ind) if not attr.startswith('_')]
print("Backtrader支持的内置指标:")
for idx, indicator in enumerate(sorted(indicators), 1):
    print(f"{idx}. {indicator}")

