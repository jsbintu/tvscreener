# Styled Output

Display results with TradingView-style formatting.

## Overview

Use `beautify()` to display results with colored formatting:

```python
from tvscreener import StockScreener, beautify

ss = StockScreener()
df = ss.get()

beautify(df)
```

## Features

- **Colored changes**: Green for positive, red for negative
- **Formatted numbers**: Currency symbols, percentages, large numbers
- **Aligned columns**: Clean tabular display
- **Terminal-friendly**: Works in most terminal emulators

## Installation

Styled output requires the `rich` library:

```bash
pip install rich
```

## Basic Usage

```python
from tvscreener import StockScreener, StockField, beautify

ss = StockScreener()
ss.select(
    StockField.NAME,
    StockField.PRICE,
    StockField.CHANGE_PERCENT,
    StockField.VOLUME,
    StockField.MARKET_CAPITALIZATION
)
ss.set_range(0, 20)

df = ss.get()
beautify(df)
```

Output shows:
- Price in currency format ($XXX.XX)
- Change % in green/red with percentage symbol
- Volume with K/M/B suffixes
- Market cap with B/T suffixes

## Column Formatting

The `beautify()` function automatically detects and formats:

| Column Type | Format Example |
|-------------|----------------|
| Price/Currency | $150.25 |
| Change % | +2.5% (green) / -1.2% (red) |
| Volume | 1.5M |
| Market Cap | 2.5T |
| P/E Ratio | 25.3 |
| Percentages | 15.2% |

## Jupyter Notebooks

In Jupyter, `beautify()` displays as a styled HTML table:

```python
from tvscreener import StockScreener, beautify

ss = StockScreener()
df = ss.get()
beautify(df)  # Renders as styled HTML in Jupyter
```

## Customization

### Limit Rows

```python
beautify(df, max_rows=10)
```

### Select Columns

```python
beautify(df[['name', 'close', 'change']])
```

## Without beautify()

Standard pandas display:

```python
ss = StockScreener()
df = ss.get()
print(df)  # Plain pandas output
```

Or use pandas styling:

```python
df.style.format({
    'close': '${:.2f}',
    'change': '{:+.2f}%',
    'volume': '{:,.0f}'
})
```

## Terminal Colors

For best results, use a terminal that supports ANSI colors:

- **Windows**: Windows Terminal, PowerShell
- **macOS**: Terminal, iTerm2
- **Linux**: Most terminal emulators

If colors don't display correctly:

```python
# Force plain text output
import os
os.environ['NO_COLOR'] = '1'
```

## Streaming with Styled Output

```python
from tvscreener import StockScreener, StockField, beautify

ss = StockScreener()
ss.set_range(0, 10)

for df in ss.stream(interval=5):
    print("\033[2J\033[H")  # Clear terminal
    beautify(df)
```

## Export to HTML

Save styled output as HTML:

```python
from tvscreener import StockScreener

ss = StockScreener()
df = ss.get()

# Using pandas
html = df.to_html()
with open('screener.html', 'w') as f:
    f.write(html)
```
