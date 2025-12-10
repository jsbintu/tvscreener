# Streaming

Get real-time updates with the streaming feature.

## Overview

Use `stream()` to receive continuous updates as data changes:

```python
from tvscreener import StockScreener, StockField

ss = StockScreener()
ss.select(StockField.NAME, StockField.PRICE, StockField.CHANGE_PERCENT)
ss.set_range(0, 10)

for df in ss.stream(interval=5):
    print(df[['name', 'close', 'change']])
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `interval` | int | 10 | Seconds between updates |

## Basic Example

Stream top 10 gainers every 5 seconds:

```python
ss = StockScreener()
ss.where(StockField.VOLUME >= 1_000_000)
ss.sort_by(StockField.CHANGE_PERCENT, ascending=False)
ss.set_range(0, 10)
ss.select(
    StockField.NAME,
    StockField.PRICE,
    StockField.CHANGE_PERCENT,
    StockField.VOLUME
)

for df in ss.stream(interval=5):
    print("\n--- Update ---")
    print(df[['name', 'close', 'change', 'volume']])
```

## Stopping the Stream

### Keyboard Interrupt

Press `Ctrl+C` to stop:

```python
try:
    for df in ss.stream(interval=5):
        print(df)
except KeyboardInterrupt:
    print("Stream stopped")
```

### After N Updates

```python
count = 0
max_updates = 10

for df in ss.stream(interval=5):
    count += 1
    print(f"Update {count}: {len(df)} rows")

    if count >= max_updates:
        break
```

### Conditional Stop

```python
for df in ss.stream(interval=5):
    # Stop if any stock drops more than 10%
    if (df['change'] < -10).any():
        print("Alert: Stock dropped >10%!")
        break
```

## Practical Examples

### Price Alert

Monitor for price changes:

```python
ss = StockScreener()
ss.symbols = {
    "query": {"types": []},
    "tickers": ["NASDAQ:AAPL", "NASDAQ:MSFT", "NASDAQ:GOOGL"]
}
ss.select(StockField.NAME, StockField.PRICE, StockField.CHANGE_PERCENT)

target_price = {"AAPL": 200, "MSFT": 450, "GOOGL": 180}

for df in ss.stream(interval=10):
    for _, row in df.iterrows():
        symbol = row['name']
        price = row['close']
        if symbol in target_price and price >= target_price[symbol]:
            print(f"ALERT: {symbol} reached ${price:.2f}!")
```

### Volume Spike Detection

```python
ss = StockScreener()
ss.where(StockField.VOLUME >= 1_000_000)
ss.sort_by(StockField.RELATIVE_VOLUME, ascending=False)
ss.set_range(0, 20)
ss.select(
    StockField.NAME,
    StockField.PRICE,
    StockField.VOLUME,
    StockField.RELATIVE_VOLUME
)

for df in ss.stream(interval=30):
    # Filter for unusual volume (3x average)
    spikes = df[df['Relative Volume'] > 3]
    if not spikes.empty:
        print("\n=== VOLUME SPIKES ===")
        print(spikes[['name', 'close', 'volume', 'Relative Volume']])
```

### RSI Monitor

Watch for oversold conditions:

```python
ss = StockScreener()
ss.set_index(IndexSymbol.SP500)
ss.where(StockField.RELATIVE_STRENGTH_INDEX_14 < 30)
ss.select(
    StockField.NAME,
    StockField.PRICE,
    StockField.RELATIVE_STRENGTH_INDEX_14,
    StockField.CHANGE_PERCENT
)

for df in ss.stream(interval=60):  # Check every minute
    if not df.empty:
        print(f"\n{len(df)} oversold S&P 500 stocks:")
        print(df[['name', 'close', 'RSI']])
    else:
        print("No oversold stocks currently")
```

## With Jupyter Notebooks

For Jupyter, use IPython display:

```python
from IPython.display import clear_output, display

ss = StockScreener()
ss.set_range(0, 10)

for df in ss.stream(interval=5):
    clear_output(wait=True)
    display(df)
```

## Interval Recommendations

| Use Case | Interval |
|----------|----------|
| High-frequency monitoring | 1-5 seconds |
| Active trading | 5-15 seconds |
| General monitoring | 30-60 seconds |
| End-of-day review | 300+ seconds |

!!! warning "Rate Limiting"
    Very short intervals may hit TradingView's rate limits. Use intervals of at least 5 seconds.

## Best Practices

1. **Limit results**: Use `set_range(0, 50)` or less for faster updates
2. **Select only needed fields**: Reduces data transfer
3. **Use appropriate intervals**: Balance freshness vs. API load
4. **Handle errors**: Wrap in try/except for network issues
5. **Clean up**: Always have a way to stop the stream
