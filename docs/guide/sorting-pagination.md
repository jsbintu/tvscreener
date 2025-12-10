# Sorting & Pagination

Control the order and number of results returned.

## Sorting

### Sort by Field

```python
from tvscreener import StockScreener, StockField

ss = StockScreener()

# Largest market cap first (descending)
ss.sort_by(StockField.MARKET_CAPITALIZATION, ascending=False)

df = ss.get()
```

### Sort Ascending

```python
ss = StockScreener()

# Lowest P/E first (ascending)
ss.sort_by(StockField.PE_RATIO_TTM, ascending=True)

df = ss.get()
```

### Common Sort Fields

```python
# By market cap (largest first)
ss.sort_by(StockField.MARKET_CAPITALIZATION, ascending=False)

# Top gainers
ss.sort_by(StockField.CHANGE_PERCENT, ascending=False)

# Most active (by volume)
ss.sort_by(StockField.VOLUME, ascending=False)

# Lowest P/E
ss.sort_by(StockField.PE_RATIO_TTM, ascending=True)

# Highest dividend yield
ss.sort_by(StockField.DIVIDEND_YIELD_FY, ascending=False)

# Most oversold (lowest RSI)
ss.sort_by(StockField.RELATIVE_STRENGTH_INDEX_14, ascending=True)
```

## Pagination

### Set Range

Use `set_range(from, to)` to control which results are returned:

```python
ss = StockScreener()

# First 100 results
ss.set_range(0, 100)

df = ss.get()
```

### Pagination Examples

```python
# First 50 results
ss.set_range(0, 50)

# Results 51-100
ss.set_range(50, 100)

# Results 101-150
ss.set_range(100, 150)

# First 500 results
ss.set_range(0, 500)

# Maximum results (up to 5000)
ss.set_range(0, 5000)
```

### Default Behavior

Without `set_range()`, the default is 150 results:

```python
ss = StockScreener()
df = ss.get()
print(len(df))  # 150 (default)
```

## Combining Sort and Pagination

Get the top 100 stocks by market cap:

```python
ss = StockScreener()
ss.sort_by(StockField.MARKET_CAPITALIZATION, ascending=False)
ss.set_range(0, 100)

df = ss.get()
```

## Practical Examples

### Top 50 Gainers

```python
ss = StockScreener()
ss.where(StockField.VOLUME >= 1_000_000)  # Liquid stocks only
ss.sort_by(StockField.CHANGE_PERCENT, ascending=False)
ss.set_range(0, 50)

df = ss.get()
```

### Bottom 50 Losers

```python
ss = StockScreener()
ss.where(StockField.VOLUME >= 1_000_000)
ss.sort_by(StockField.CHANGE_PERCENT, ascending=True)
ss.set_range(0, 50)

df = ss.get()
```

### Most Active Stocks

```python
ss = StockScreener()
ss.sort_by(StockField.VOLUME, ascending=False)
ss.set_range(0, 100)

df = ss.get()
```

### All S&P 500 Stocks

```python
from tvscreener import IndexSymbol

ss = StockScreener()
ss.set_index(IndexSymbol.SP500)
ss.sort_by(StockField.MARKET_CAPITALIZATION, ascending=False)
ss.set_range(0, 500)  # S&P 500 has ~500 constituents

df = ss.get()
```

### Paginated Iteration

Process results in batches:

```python
ss = StockScreener()
ss.sort_by(StockField.MARKET_CAPITALIZATION, ascending=False)

all_results = []
batch_size = 100

for offset in range(0, 1000, batch_size):
    ss.set_range(offset, offset + batch_size)
    batch = ss.get()

    if batch.empty:
        break

    all_results.append(batch)
    print(f"Fetched {offset + len(batch)} stocks")

import pandas as pd
full_df = pd.concat(all_results, ignore_index=True)
```

## Limits

| Parameter | Min | Max | Default |
|-----------|-----|-----|---------|
| `from` | 0 | - | 0 |
| `to` | 1 | 5000 | 150 |
| Results per request | - | 5000 | 150 |
