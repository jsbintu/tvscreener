# Changelog

All notable changes to tvscreener.

## [0.1.0] - 2024

### Added

- **Pythonic Comparison Operators** - Use `>`, `<`, `>=`, `<=`, `==`, `!=` directly on fields
  ```python
  ss.where(StockField.PRICE > 100)
  ss.where(StockField.VOLUME >= 1_000_000)
  ```

- **Range Methods** - `between()` and `not_between()` for range filtering
  ```python
  ss.where(StockField.PE_RATIO_TTM.between(10, 25))
  ss.where(StockField.RSI.not_between(30, 70))
  ```

- **List Methods** - `isin()` and `not_in()` for list matching
  ```python
  ss.where(StockField.SECTOR.isin(['Technology', 'Healthcare']))
  ```

- **Fluent API** - All methods return `self` for chaining
  ```python
  df = StockScreener().select(...).where(...).sort_by(...).get()
  ```

- **Index Filtering** - Filter by index constituents
  ```python
  ss.set_index(IndexSymbol.SP500)
  ```

- **Select All** - Retrieve all ~3,500 fields
  ```python
  ss.select_all()
  ```

- **Time Intervals** - Use indicators on multiple timeframes
  ```python
  rsi_1h = StockField.RSI.with_interval('60')
  ```

- **All 6 Screeners** - Stock, Crypto, Forex, Bond, Futures, Coin

### Changed

- Improved type safety with Field enums
- Better error messages for invalid field types

### Backward Compatibility

- Legacy `where(field, operator, value)` syntax still supported
- All existing code continues to work

---

## [0.0.x] - Previous Versions

Initial releases with basic screening functionality.

### Features

- Basic screener classes
- Filter by field and operator
- Select specific fields
- Sorting and pagination
- Streaming updates
- Styled output with `beautify()`
