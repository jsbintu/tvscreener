# HIGH-IMPACT SPECIALIZED PROMPTS FOR AI TRADING PLATFORM

These are deep-dive prompts for the most critical sections that will yield production-ready code, algorithms, and implementations.

---

## 1. PATTERN DETECTION ENGINE (HIGHEST PRIORITY)

### Prompt: Complete Pattern Detection Implementation

```
You are building the core pattern recognition engine for a real-time stock trading platform that processes raw OHLCV data directly (no Vision AI).

REQUIREMENTS:

1. Implement complete pattern detection algorithms for these 20 patterns:
   - Double Bottom / Double Top
   - Triple Bottom / Triple Top
   - Head & Shoulders / Inverse Head & Shoulders
   - Cup & Handle / Inverse Cup & Handle
   - Ascending Triangle / Descending Triangle / Symmetrical Triangle
   - Rising Wedge / Falling Wedge
   - Bull Flag / Bear Flag
   - Pennant (Bull/Bear)
   - Rectangle / Channel
   - Rounding Bottom / Rounding Top

2. For EACH pattern, provide:
   
   A. DETECTION ALGORITHM:
   - Input: priceData (array of prices), volumeData (array of volumes), ohlcData (array of {open, high, low, close})
   - Mathematical criteria for pattern identification (not visual, use actual price comparisons)
   - Minimum data points required
   - Tolerance levels (how much variation is acceptable)
   - Volume confirmation requirements
   
   B. COMPLETION PERCENTAGE CALCULATION:
   - Algorithm to calculate exact completion percentage (0-100%)
   - Identify which pattern elements are complete vs incomplete
   - Required conditions for each completion stage (50%, 75%, 90%, 100%)
   
   C. BREAKOUT LEVEL CALCULATION:
   - Exact formula for calculating breakout/breakdown level
   - How to determine trigger price
   - Volume requirements for confirmation
   
   D. TARGET CALCULATION:
   - Measured move formula specific to this pattern
   - Multiple target levels (TP1, TP2, TP3) with probability scoring
   - Fibonacci extension levels
   
   E. STOP LOSS CALCULATION:
   - Pattern invalidation point
   - ATR-based stop placement
   - Risk percentage calculation
   
   F. CONFIDENCE SCORING:
   - Algorithm to score pattern quality (0-100)
   - Factors to consider:
     * Symmetry/proportion
     * Volume confirmation
     * Timeframe alignment
     * Trend context
     * Historical success rate
   - Weighted formula for combining factors
   
   G. HISTORICAL VALIDATION:
   - Database query structure to find similar historical patterns
   - Matching criteria (pattern dimensions, market conditions)
   - Success rate calculation from historical data

3. REAL-TIME MONITORING:
   - Algorithm to track emerging patterns (50%+ complete)
   - How to update completion percentage on each new tick
   - When to trigger alerts (thresholds)
   - How to estimate time to completion based on formation velocity
   - Pattern invalidation detection

4. MULTI-TIMEFRAME VALIDATION:
   - How to check pattern on multiple timeframes simultaneously
   - Alignment scoring (how many timeframes confirm)
   - Conflict resolution when timeframes disagree

5. CODE STRUCTURE:
   - Provide actual JavaScript/TypeScript or Python code
   - Include helper functions (findLocalMinima, findLocalMaxima, calculateSlope, etc.)
   - Use efficient algorithms (O(n) or O(n log n) complexity)
   - Include extensive comments explaining the math

6. EDGE CASES:
   - Handling noisy data
   - Dealing with gaps
   - Identifying false patterns
   - Multiple patterns overlapping

7. OUTPUT FORMAT:
   Return structured data:
   {
     pattern: 'Double Bottom',
     completion: 85,
     confidence: 82,
     coordinates: {
       low1: {index: 45, price: 150.23},
       low2: {index: 67, price: 150.15},
       neckline: {index: 56, price: 155.80}
     },
     breakoutLevel: 156.10,
     targets: [
       {level: 161.37, probability: 0.75, label: 'TP1'},
       {level: 165.50, probability: 0.45, label: 'TP2'}
     ],
     stopLoss: 149.50,
     riskReward: 3.2,
     volumeConfirmation: true,
     historicalSuccessRate: 0.78,
     remainingConditions: ['Price needs to test neckline'],
     estimatedTimeToCompletion: {bars: 8, minutes: 120}
   }

8. PERFORMANCE REQUIREMENTS:
   - Pattern detection must complete in <100ms for 500 bars of data
   - Memory efficient (process 1000 tickers simultaneously)
   - Scalable algorithm

Generate complete, production-ready code with all 20 patterns implemented.
Include unit tests for each pattern with known test cases.
```

**Why this yields great results:**
- Gets you actual working code, not just theory
- Forces specific mathematical implementations
- Covers edge cases and performance
- Includes test cases for validation
- Production-ready output

---

## 2. LANGUAGE AI INTEGRATION ARCHITECTURE

### Prompt: Complete News & Sentiment Analysis System

```
Design and implement a complete Language AI integration system for analyzing news, social media, and SEC filings in a stock trading platform.

REQUIREMENTS:

1. NEWS SENTIMENT ANALYSIS:

   A. DATA SOURCES INTEGRATION:
   - Show exact API integration for NewsAPI, Benzinga, Alpha Vantage, FMP
   - API authentication, rate limiting, error handling
   - Data normalization (different API formats → unified structure)
   
   B. LANGUAGE AI PROCESSING:
   - Exact prompt engineering for sentiment analysis
   - How to structure the API call (include actual code)
   - Response parsing (extract sentiment, score, key themes)
   - Batch processing (analyze multiple articles efficiently)
   
   C. SENTIMENT SCORING ALGORITHM:
   - How to aggregate sentiment from multiple sources
   - Weighting by source credibility
   - Time decay (recent news weighted more)
   - Conflict resolution (sources disagree)
   
   D. IMPACT PREDICTION:
   - Algorithm to predict price impact from news
   - Historical correlation analysis
   - Event classification (earnings, FDA, lawsuit, etc.)
   - Urgency scoring

2. SOCIAL MEDIA MONITORING:

   A. TWITTER/X INTEGRATION:
   - API setup and authentication
   - Query structure (hashtags, mentions, cashtags)
   - Rate limiting and cost management
   - Data filtering (remove bots, spam)
   
   B. REDDIT INTEGRATION:
   - Subreddit monitoring (r/wallstreetbets, r/stocks, r/investing)
   - Post scoring (upvotes, comments, awards)
   - Sentiment analysis of titles and bodies
   - Unusual activity detection (viral posts)
   
   C. STOCKTWITS INTEGRATION:
   - API integration
   - Sentiment classification
   - Volume tracking
   
   D. AGGREGATION ALGORITHM:
   - Combine signals from all platforms
   - Volume-weighted sentiment
   - Detect sentiment shifts
   - Identify coordinated campaigns or manipulation

3. SEC FILINGS ANALYSIS:

   A. EDGAR API INTEGRATION:
   - How to fetch filings (10-K, 10-Q, 8-K, Form 4)
   - Parsing HTML/XBRL formats
   - Section extraction (risk factors, MD&A, financials)
   
   B. LANGUAGE AI ANALYSIS:
   - Prompt for analyzing 10-K risk factors
   - Prompt for detecting changes vs previous filing
   - Prompt for management tone analysis
   - Prompt for red flag detection
   
   C. INSIDER TRADING TRACKING:
   - Parse Form 4 filings
   - Calculate net insider buying/selling
   - Identify unusual patterns
   - Score bullishness/bearishness

4. EARNINGS CALL TRANSCRIPTS:

   A. DATA SOURCE:
   - Where to get transcripts (Alpha Vantage, Seeking Alpha, etc.)
   - Real-time vs historical access
   
   B. ANALYSIS PROMPTS:
   - Extract management guidance
   - Detect tone and confidence
   - Identify concerns or risks
   - Compare to analyst expectations
   
   C. Q&A ANALYSIS:
   - Analyze analyst questions (what are they worried about?)
   - Analyze management responses (evasive vs transparent)

5. SYNTHESIS ENGINE:

   A. MULTI-SOURCE AGGREGATION:
   - Algorithm to combine technical + news + social + fundamental signals
   - Conflict resolution (sources disagree)
   - Confidence scoring
   
   B. LANGUAGE AI SYNTHESIS PROMPT:
   - Prompt that takes all data and generates unified recommendation
   - How to structure input data for the prompt
   - Expected output format
   
   C. TRADING IMPLICATIONS:
   - Algorithm to translate sentiment → trading signals
   - Risk adjustments based on news
   - Position sizing modifications

6. COST OPTIMIZATION:

   A. CACHING STRATEGY:
   - Cache news sentiment (TTL 1 hour)
   - Cache SEC filing analysis (TTL 24 hours)
   - Smart invalidation rules
   
   B. BATCH PROCESSING:
   - Group multiple analyses in single API call
   - Async processing queue
   - Priority system (breaking news = high priority)
   
   C. RATE LIMITING:
   - Handle API rate limits gracefully
   - Queue management
   - Exponential backoff

7. REAL-TIME INTEGRATION:

   A. EVENT DETECTION:
   - WebSocket or polling for breaking news
   - Instant analysis pipeline
   - Alert generation
   
   B. CHART ANNOTATION:
   - How to place news markers on charts
   - Coordinate calculation (time → x-axis position)
   - Icon selection based on news type

8. CODE IMPLEMENTATION:
   - Provide complete TypeScript/JavaScript or Python code
   - Include error handling, retries, fallbacks
   - Database schema for storing analyzed data
   - API route handlers
   - Background job processors

9. PROMPT EXAMPLES:
   Provide exact prompts for:
   - News headline sentiment
   - Full article analysis
   - Social media batch analysis
   - SEC filing comparison
   - Earnings call tone detection
   - Multi-source synthesis

10. PERFORMANCE:
    - News analysis: <3s including API call
    - Batch social analysis (100 posts): <5s
    - SEC filing analysis: <10s (large documents)
    - Cost per comprehensive analysis: <$0.15

Generate production-ready code with actual API integrations, Language AI prompts, and complete processing pipeline.
```

**Why this yields great results:**
- Actual API integration code
- Real prompts you can use immediately
- Cost optimization strategies
- Complete end-to-end pipeline
- Handles real-world complexities

---

## 3. REAL-TIME PROCESSING ENGINE

### Prompt: High-Performance Data Processing Pipeline

```
Design and implement a high-performance real-time data processing engine for a stock trading platform that must handle 100,000+ concurrent users and process 1M+ data points per second with sub-100ms latency.

REQUIREMENTS:

1. DATA INGESTION:

   A. WEBSOCKET CONNECTION MANAGEMENT:
   - Connect to market data providers (Polygon.io, IEX Cloud)
   - Handle authentication and reconnection
   - Message parsing and validation
   - Error handling and failover
   
   B. DATA NORMALIZATION:
   - Convert different provider formats to unified structure
   - Handle different message types (trade, quote, bar)
   - Timestamp synchronization
   - Data quality checks

2. IN-MEMORY DATA STRUCTURES:

   A. CIRCULAR BUFFERS:
   - Implement efficient circular buffer for price history
   - Fixed memory footprint (1000 bars per ticker)
   - O(1) push and get operations
   - Thread-safe for concurrent access
   
   B. PRICE/VOLUME CACHING:
   - Redis data structure design
   - Key naming convention
   - Pub/Sub architecture for distribution
   - TTL and eviction policies
   
   C. COMPUTED RESULTS CACHE:
   - Cache indicator values
   - Cache pattern detections
   - Cache support/resistance levels
   - Cache invalidation strategy

3. CALCULATION ENGINE:

   A. VECTORIZED OPERATIONS:
   - Use NumPy or typed arrays for performance
   - SIMD operations where possible
   - Batch calculations for multiple indicators
   - Parallel processing across tickers
   
   B. INCREMENTAL UPDATES:
   - Don't recalculate everything on each tick
   - Maintain running calculations (e.g., SMA uses rolling window)
   - Update only what changed
   - Dirty flag tracking
   
   C. WORKER POOL ARCHITECTURE:
   - Distribute tickers across worker processes
   - Load balancing algorithm
   - Inter-process communication
   - Fault tolerance (worker crashes)

4. PATTERN DETECTION OPTIMIZATION:

   A. INCREMENTAL PATTERN MONITORING:
   - Track patterns in progress
   - Only re-evaluate when relevant (price/volume change)
   - Completion percentage updates (not full re-detection)
   
   B. EARLY TERMINATION:
   - Skip full pattern scan if price hasn't moved significantly
   - Use heuristics to filter likely patterns
   - Detailed analysis only for high-probability candidates

5. WEBSOCKET BROADCAST:

   A. USER CONNECTION MANAGEMENT:
   - Maintain 100k+ WebSocket connections
   - User subscription model (which tickers they're watching)
   - Efficient message routing (only send relevant updates)
   
   B. MESSAGE BATCHING:
   - Batch multiple updates in single message
   - Compression (minimize bandwidth)
   - Priority queue (alerts > normal updates)
   
   C. RATE LIMITING:
   - Throttle updates per user (max 10/second)
   - Coalesce rapid updates
   - Smart debouncing

6. DATABASE INTERACTIONS:

   A. WRITE OPTIMIZATION:
   - Batch inserts (don't insert every tick)
   - Async writes (non-blocking)
   - Write aggregated bars (1min, 5min) not every tick
   
   B. READ OPTIMIZATION:
   - Connection pooling
   - Prepared statements
   - Index strategy
   - Query result caching

7. MONITORING & OBSERVABILITY:

   A. PERFORMANCE METRICS:
   - Message processing latency (p50, p95, p99)
   - Messages per second
   - CPU/memory per worker
   - WebSocket connection count
   
   B. ALERTING:
   - Alert on latency spikes
   - Alert on data feed disconnection
   - Alert on error rate increases
   
   C. DASHBOARDS:
   - Real-time throughput
   - System health
   - Cost tracking

8. SCALING STRATEGY:

   A. HORIZONTAL SCALING:
   - Add more workers for more tickers
   - Shard by ticker symbol
   - Load balancer configuration
   
   B. VERTICAL SCALING:
   - When to scale up vs out
   - Resource limits per worker
   
   C. AUTO-SCALING:
   - Metrics to trigger scaling
   - Scaling policies
   - Cost optimization

9. CODE IMPLEMENTATION:
   Provide:
   - WebSocket server setup (Node.js or Python)
   - Circular buffer implementation
   - Worker pool manager
   - Redis pub/sub implementation
   - Performance benchmarks
   - Load testing scripts

10. LATENCY BREAKDOWN:
    Show exact timing for each step:
    - Data receipt: Xms
    - Validation: Xms
    - Cache update: Xms
    - Calculations: Xms
    - Pattern detection: Xms
    - Broadcasting: Xms
    - Total: <100ms target

Generate production-ready code optimized for maximum throughput and minimum latency.
Include configuration files, deployment instructions, and monitoring setup.
```

**Why this yields great results:**
- Performance-critical system design
- Actual scaling strategies
- Production-grade code
- Handles real concurrency issues
- Includes monitoring/observability

---

## 4. ANNOTATION GENERATION SYSTEM

### Prompt: Intelligent Chart Annotation Engine

```
Design and implement a complete chart annotation system that automatically generates visual markup (lines, boxes, arrows, labels) from pattern detection and analysis results.

REQUIREMENTS:

1. COORDINATE SYSTEM:

   A. TIME-TO-X CONVERSION:
   - Algorithm to convert bar index → x-axis pixel coordinate
   - Handle different chart zoom levels
   - Handle different timeframes (1m, 5m, 1H, 1D)
   - Handle gaps (weekends, holidays, after-hours)
   
   B. PRICE-TO-Y CONVERSION:
   - Algorithm to convert price → y-axis pixel coordinate
   - Handle log scale vs linear scale
   - Handle different price ranges
   - Auto-scaling considerations

2. DRAWING PRIMITIVES:

   A. HORIZONTAL LINES:
   - Draw support/resistance levels
   - Draw target levels
   - Draw stop loss levels
   - Label placement algorithm (avoid overlaps)
   - Line style (solid, dashed, dotted)
   - Color selection rules
   
   B. TRENDLINES:
   - Draw from point A to point B
   - Extend beyond data (project into future)
   - Parallel channel drawing
   - Regression lines
   
   C. RECTANGLES/BOXES:
   - Entry zones (green semi-transparent)
   - Stop zones (red semi-transparent)
   - Consolidation areas
   - Pattern outlines
   
   D. CIRCLES/ELLIPSES:
   - Highlight key points (swing highs/lows)
   - Mark pattern pivots
   - Size based on importance
   
   E. ARROWS:
   - Direction indicators
   - Breakout triggers
   - Target projections
   - Entry/exit signals
   
   F. TEXT LABELS:
   - Pattern names
   - Level values ($150.23)
   - Percentage moves (+5.2%)
   - Annotations and notes

3. INTELLIGENT PLACEMENT:

   A. OVERLAP AVOIDANCE:
   - Algorithm to detect label overlaps
   - Automatic repositioning
   - Priority system (most important labels stay)
   
   B. VISIBILITY OPTIMIZATION:
   - Don't place labels over active price action
   - Prefer empty areas
   - Adjust on zoom/pan
   
   C. CLUSTERING:
   - Group related annotations
   - Visual hierarchy

4. PATTERN-SPECIFIC ANNOTATIONS:

   For each pattern type, define exact annotation rules:
   
   A. DOUBLE BOTTOM:
   - Circle both lows (green)
   - Horizontal line at neckline (blue)
   - Dashed line at target (green)
   - Red line at stop
   - Yellow box highlighting pattern area
   - Label: "Double Bottom - 85% Complete"
   
   B. CUP & HANDLE:
   - Outline the cup (blue curve)
   - Rectangle around handle (yellow)
   - Breakout arrow
   - Measured move projection
   
   [Include all 20 patterns...]

5. DYNAMIC UPDATES:

   A. REAL-TIME CHANGES:
   - Update annotations as pattern evolves
   - Move completion percentage label
   - Extend trendlines as new data arrives
   - Remove invalidated patterns
   
   B. ANIMATION:
   - Smooth transitions when moving annotations
   - Fade in/out effects
   - Highlight new annotations briefly
   
   C. PERSISTENCE:
   - Save annotation state
   - Restore on chart reload
   - History of annotations (undo/redo)

6. USER INTERACTION:

   A. ANNOTATION MODES:
   - Auto mode (AI draws everything)
   - Manual mode (user can draw)
   - Hybrid mode (AI + user)
   
   B. EDITING:
   - Click to edit annotation
   - Drag to move
   - Delete annotations
   - Lock annotations
   
   C. LAYERS:
   - Separate layers for different annotation types
   - Toggle visibility by layer
   - Z-order management

7. MULTI-TIMEFRAME ANNOTATIONS:

   A. SYNCHRONIZATION:
   - Same pattern on different timeframes
   - Visual indicators of timeframe alignment
   - Highlight where timeframes agree
   
   B. CONTEXT SWITCHING:
   - Preserve annotations when changing timeframes
   - Adapt annotation density to zoom level

8. NEWS & EVENT MARKERS:

   A. EVENT ICONS:
   - Earnings: 📊
   - News: 📰
   - Economic data: 📈
   - FDA: 💊
   - Custom icons for event types
   
   B. PLACEMENT:
   - On chart at event time
   - Above/below price action
   - Tooltip on hover
   - Link to full details

9. PERFORMANCE:

   A. RENDERING OPTIMIZATION:
   - Canvas vs SVG decision
   - Culling (don't draw off-screen annotations)
   - LOD (level of detail based on zoom)
   - Batched drawing operations
   
   B. MEMORY MANAGEMENT:
   - Limit total annotations
   - Remove old/irrelevant annotations
   - Efficient data structures

10. CODE IMPLEMENTATION:

    Provide complete code:
    - Annotation data structure (JSON format)
    - Rendering engine (Canvas or SVG)
    - Coordinate conversion functions
    - Label placement algorithm
    - Pattern-specific annotation generators
    - Update/remove/edit functions
    
    Include TypeScript interfaces:
    ```typescript
    interface Annotation {
      id: string;
      type: 'line' | 'rectangle' | 'circle' | 'arrow' | 'label';
      coordinates: {...};
      style: {...};
      metadata: {...};
    }
    ```

11. INTEGRATION:

    A. FROM PATTERN DETECTION:
    ```javascript
    const pattern = detectDoubleBottom(...);
    const annotations = generateAnnotations(pattern);
    drawOnChart(annotations);
    ```
    
    B. WEBSOCKET UPDATES:
    - Send annotation commands to frontend
    - Efficient serialization
    - Incremental updates (only changed annotations)

Generate production-ready annotation system with all drawing primitives, intelligent placement, and real-time updates.
Include examples for all 20 patterns.
```

**Why this yields great results:**
- Visual system is complex and critical
- Need actual rendering code
- Covers UX details (overlap avoidance, etc.)
- Integration with pattern detection
- Performance considerations

---

## 5. DATABASE SCHEMA & QUERY OPTIMIZATION

### Prompt: Complete Database Architecture

```
Design a complete database schema and query optimization strategy for a real-time stock trading platform that must:
- Store 10,000+ tickers × 7 timeframes × historical data
- Handle 100k+ inserts per second
- Support sub-10ms query response times
- Maintain pattern history and outcomes
- Track user data and alerts

REQUIREMENTS:

1. TIME-SERIES DATA STORAGE:

   A. MARKET DATA TABLES:
   - Design schema for OHLCV data
   - Partitioning strategy (by time, by ticker?)
   - Index strategy
   - Compression settings
   - Retention policies (how long to keep data)
   
   B. TIMESCALEDB OPTIMIZATION:
   - Hypertable configuration
   - Continuous aggregates (pre-compute 5min, 15min, 1H from 1min data)
   - Compression policies
   - Data retention policies
   
   C. EXAMPLE QUERIES WITH EXECUTION PLANS:
   - Get last 100 bars for pattern analysis
   - Get data for multiple tickers in parallel
   - Aggregate to higher timeframe
   - Historical pattern search

2. PATTERN HISTORY:

   A. SCHEMA DESIGN:
   ```sql
   CREATE TABLE pattern_history (
     id SERIAL PRIMARY KEY,
     ticker VARCHAR(10),
     pattern_type VARCHAR(50),
     timeframe VARCHAR(5),
     detected_at TIMESTAMPTZ,
     completion_pct INTEGER,
     confidence INTEGER,
     breakout_level NUMERIC,
     target_level NUMERIC,
     stop_level NUMERIC,
     outcome VARCHAR(20), -- 'success', 'failure', 'invalidated', 'pending'
     outcome_price NUMERIC,
     outcome_date TIMESTAMPTZ,
     bars_to_outcome INTEGER,
     pattern_data JSONB, -- Full pattern details
     -- What else should be tracked?
   );
   ```
   
   B. INDEXES:
   - Which columns to index?
   - Composite indexes?
   - Partial indexes?
   
   C. QUERIES:
   - Find all historical patterns for a ticker
   - Calculate success rate by pattern type
   - Find similar patterns (JSONB querying)
   - Performance analysis

3. USER DATA:

   A. USERS TABLE:
   - Authentication info
   - Subscription tier
   - Preferences
   - Usage tracking
   
   B. WATCHLISTS:
   - User's monitored tickers
   - Custom annotations
   - Notes and tags
   
   C. TRADING HISTORY:
   - Trades taken (entries, exits)
   - P&L tracking
   - Performance metrics

4. ALERTS SYSTEM:

   A. ALERTS TABLE:
   ```sql
   CREATE TABLE alerts (
     id SERIAL PRIMARY KEY,
     user_id INTEGER,
     ticker VARCHAR(10),
     alert_type VARCHAR(50), -- 'price', 'pattern', 'volume', 'news'
     condition JSONB, -- Alert condition
     triggered_at TIMESTAMPTZ,
     status VARCHAR(20), -- 'active', 'triggered', 'expired', 'deleted'
     -- What else?
   );
   ```
   
   B. EFFICIENT CHECKING:
   - How to check 1M+ alerts on each tick without table scans?
   - Index strategy
   - Caching active alerts in Redis
   - Background job to process triggered alerts

5. ANALYSIS CACHE:

   A. REDIS STRUCTURE:
   - Key naming convention
   - Data structure selection (hash, sorted set, string?)
   - TTL settings
   - Memory eviction policies
   
   B. WHAT TO CACHE:
   - Latest 1000 bars per ticker/timeframe
   - Computed indicators
   - Pattern detections
   - Support/resistance levels
   - News sentiment
   
   C. CACHE INVALIDATION:
   - When to invalidate
   - Selective invalidation
   - Cache warming

6. QUERY OPTIMIZATION:

   A. COMMON QUERIES:
   For each, provide:
   - SQL query
   - Execution plan analysis
   - Index recommendations
   - Query rewrite if needed
   
   Example queries:
   - Get last 100 bars
   - Get bars between timestamps
   - Find patterns with >80% confidence
   - Calculate win rate for pattern type
   - Find tickers with pending alerts
   - Get user's watchlist with latest prices
   
   B. BULK OPERATIONS:
   - Batch inserts (how to structure)
   - Batch updates
   - Efficient pagination
   
   C. ANALYTICAL QUERIES:
   - Pattern success rate over time
   - Best performing patterns by market regime
   - Correlation analysis

7. WRITE OPTIMIZATION:

   A. BATCH INSERTS:
   - Buffer size
   - Flush frequency
   - Error handling
   
   B. UPSERT STRATEGY:
   - When to use INSERT vs UPDATE
   - Conflict resolution
   
   C. ASYNC WRITES:
   - Queue architecture
   - Durability guarantees
   - Failure recovery

8. BACKUP & RECOVERY:

   A. BACKUP STRATEGY:
   - Full backup frequency
   - Incremental backups
   - Point-in-time recovery
   
   B. DISASTER RECOVERY:
   - RTO (Recovery Time Objective)
   - RPO (Recovery Point Objective)
   - Replication setup

9. MIGRATIONS:

   A. SCHEMA CHANGES:
   - Zero-downtime migration strategy
   - Backward compatibility
   - Rollback plan
   
   B. DATA MIGRATIONS:
   - Moving data between tables
   - Transforming data
   - Validation

10. CODE IMPLEMENTATION:

    Provide:
    - Complete SQL schema (DDL)
    - Migration scripts
    - Query examples with explanations
    - ORM/query builder setup (Prisma, TypeORM, etc.)
    - Connection pooling configuration
    - Monitoring queries (slow query log, etc.)

11. PERFORMANCE BENCHMARKS:

    Show expected performance:
    - Insert rate: X rows/second
    - Query response: Xms for Y rows
    - Concurrent queries: Support Z simultaneous
    - Memory usage: X GB for Y tickers

Generate complete production-ready database schema with all tables, indexes, queries, and optimization strategies.
Include migration scripts and performance testing queries.
```

**Why this yields great results:**
- Database is critical bottleneck
- Need actual schema and indexes
- Query optimization is complex
- Real performance testing needed
- Covers scaling challenges

---

## 6. ALERT SYSTEM ARCHITECTURE

### Prompt: Intelligent Alert & Notification Engine

```
Design and implement a complete alert system for a stock trading platform that can handle 1M+ active alerts, check them on every tick (1M+ checks/second), and deliver notifications via multiple channels.

REQUIREMENTS:

1. ALERT TYPES:

   Define schema and logic for:
   
   A. PRICE ALERTS:
   - Price crosses above/below level
   - Price enters/exits range
   - Percentage move (up/down X%)
   - Multi-leg conditions (if price > X AND volume > Y)
   
   B. PATTERN ALERTS:
   - Pattern completion threshold (75%, 90%, 95%)
   - Breakout confirmation
   - Pattern invalidation
   - New pattern detected
   
   C. TECHNICAL ALERTS:
   - Indicator crossover (MACD, moving averages)
   - RSI overbought/oversold
   - Volume surge
   - Divergence detected
   
   D. NEWS ALERTS:
   - Breaking news for ticker
   - Sentiment shift
   - Unusual social media volume
   - SEC filing posted
   
   E. FUNDAMENTAL ALERTS:
   - Earnings date approaching
   - Insider buying/selling
   - Analyst upgrade/downgrade

2. ALERT CREATION:

   A. USER INTERFACE:
   - Alert builder (point and click on chart)
   - Advanced conditions (boolean logic)
   - Alert templates (common setups)
   
   B. DATA MODEL:
   ```typescript
   interface Alert {
     id: string;
     userId: string;
     ticker: string;
     type: 'price' | 'pattern' | 'technical' | 'news' | 'fundamental';
     conditions: {
       // Structure for storing complex conditions
       operator: 'AND' | 'OR';
       rules: Array<{
         field: string;
         operator: '>' | '<' | '=' | 'crosses_above' | 'crosses_below';
         value: number | string;
       }>;
     };
     notificationChannels: ('push' | 'email' | 'sms' | 'in_app')[];
     priority: 'low' | 'medium' | 'high' | 'critical';
     expiresAt?: Date;
     triggeredAt?: Date;
     status: 'active' | 'triggered' | 'expired' | 'deleted';
   }
   ```

3. EFFICIENT ALERT CHECKING:

   A. IN-MEMORY INDEX:
   - Load active alerts into Redis
   - Group by ticker (only check relevant alerts)
   - Sort by price level (binary search for price alerts)
   
   B. CHECKING ALGORITHM:
   ```
   On new tick for AAPL:
   1. Get all active alerts for AAPL from Redis (O(1))
   2. Filter by alert type (price alerts check first, they're fastest)
   3. Evaluate conditions:
      - Price alerts: Compare current price vs threshold
      - Pattern alerts: Check pattern status from cache
      - Technical alerts: Check indicator values from cache
   4. For triggered alerts:
      - Mark as triggered
      - Queue notification
      - Update database (async)
   ```
   
   C. OPTIMIZATION:
   - Don't evaluate all conditions if early termination possible
   - Cache alert evaluation results briefly (don't re-check same alert for 5 seconds)
   - Batch database updates

4. NOTIFICATION DELIVERY:

   A. PUSH NOTIFICATIONS:
   - Firebase Cloud Messaging integration
   - Apple Push Notification Service
   - Message formatting
   - Deep linking (open app to specific chart)
   
   B. EMAIL:
   - Email service provider (SendGrid, AWS SES)
   - Template system
   - Rate limiting (don't spam user)
   - Unsubscribe handling
   
   C. SMS:
   - Twilio integration
   - Character limit handling
   - Cost management (SMS is expensive)
   
   D. IN-APP:
   - WebSocket delivery
   - Notification center UI
   - Read/unread tracking
   - Notification history

5. SMART ALERT FEATURES:

   A. ALERT GROUPING:
   - Combine similar alerts ("3 patterns completed on your watchlist")
   - Batch notifications (don't send 10 separate notifications in 1 minute)
   
   B. PRIORITY SYSTEM:
   - Critical alerts bypass grouping/batching
   - User can set importance per alert
   - Smart priority inference (breakout on big position = critical)
   
   C. ALERT CHAINS:
   - "When alert A triggers, create alert B"
   - Example: Pattern completion → Create entry alert → Create stop loss alert
   
   D. CONDITIONAL EXPIRATION:
   - Expire after trigger
   - Expire after date
   - Expire if condition becomes impossible

6. USER MANAGEMENT:

   A. ALERT LIMITS:
   - Free tier: 10 alerts
   - Pro tier: 100 alerts
   - Enterprise: Unlimited
   - Enforcement logic
   
   B. ALERT PRIORITIZATION:
   - If user hits limit, which alerts to keep?
   - User can mark "favorites"
   - Auto-delete old triggered alerts
   
   C. PREFERENCES:
   - Notification channels per alert type
   - Quiet hours (don't send notifications at night)
   - Frequency limits (max X notifications per hour)

7. ANALYTICS & INSIGHTS:

   A. ALERT EFFECTIVENESS:
   - Track which alerts lead to profitable trades
   - Suggest alert improvements
   - "Your pattern alerts have 78% accuracy"
   
   B. USAGE PATTERNS:
   - Most common alert types
   - Average trigger time
   - False alarm rate

8. SCALABILITY:

   A. DISTRIBUTED CHECKING:
   - Shard alerts across multiple workers
   - Each worker handles subset of tickers
   - Load balancing
   
   B. QUEUE ARCHITECTURE:
   - Alert evaluation queue
   - Notification delivery queue
   - Dead letter queue for failures
   
   C. RATE LIMITING:
   - Per-user notification limits
   - Global system limits
   - Backpressure handling

9. RELIABILITY:

   A. FAILURE HANDLING:
   - Retry logic for failed notifications
   - Fallback channels (if push fails, try email)
   - Alert audit log
   
   B. MONITORING:
   - Alert check latency
   - Notification delivery success rate
   - Queue depth
   - Error rates
   
   C. TESTING:
   - Alert test mode (doesn't actually trigger)
   - Simulation (backtest alert on historical data)

10. CODE IMPLEMENTATION:

    Provide complete code for:
    - Alert creation/update/delete API
    - Alert checking engine
    - Notification delivery system
    - Redis indexing structure
    - Database queries
    - Background workers
    
    Include:
    - TypeScript interfaces
    - API route handlers
    - Worker processes
    - Testing utilities

11. PERFORMANCE:

    Target metrics:
    - Check 1M alerts in <5 seconds per tick
    - Notification delivery: <1 second from trigger
    - 99.9% delivery success rate
    - Support 100k concurrent users with alerts

Generate production-ready alert system with all components, from user creation through notification delivery.
Include monitoring, testing, and scaling strategies.
```

**Why this yields great results:**
- Alert system is user-facing and critical
- Complex distributed systems problems
- Need actual queuing/notification code
- Scaling challenges
- Multiple integration points

---

## 7. BACKTESTING ENGINE

### Prompt: Complete Backtesting & Strategy Validation System

```
Design and implement a comprehensive backtesting engine that can test pattern-based trading strategies on historical data to validate accuracy and calculate expected returns.

REQUIREMENTS:

1. BACKTESTING FRAMEWORK:

   A. STRATEGY DEFINITION:
   ```typescript
   interface TradingStrategy {
     name: string;
     
     // Entry rules
     entryConditions: {
       patterns: string[]; // e.g., ['double_bottom', 'cup_and_handle']
       minConfidence: number; // e.g., 80
       minCompletion: number; // e.g., 85
       requiredIndicators?: {
         rsi?: {min?: number, max?: number};
         macd?: {histogram: '>' | '<', value: number};
         volume?: {comparison: '>' | '<', multiplier: number};
       };
       timeframes: string[]; // Must match on these timeframes
       minTimeframeAlignment: number; // e.g., 3 out of 5
     };
     
     // Entry execution
     entry: {
       type: 'market' | 'limit' | 'stop';
       priceOffset?: number; // For limit orders
       maxSlippage?: number;
     };
     
     // Position sizing
     positionSizing: {
       method: 'fixed_percent' | 'risk_based' | 'kelly';
       riskPerTrade: number; // e.g., 0.01 for 1%
       maxPositionSize: number; // e.g., 0.20 for 20% of portfolio
     };
     
     // Stop loss
     stopLoss: {
       method: 'pattern_based' | 'atr' | 'percentage' | 'fixed';
       value: number; // ATR multiple, percentage, or fixed price
       trailing?: {
         enabled: boolean;
         method: 'percentage' | 'atr';
         value: number;
       };
     };
     
     // Take profit
     takeProfit: {
       targets: Array<{
         level: number; // Price or R-multiple
         exitPercentage: number; // Percent of position to exit
       }>;
       method: 'pattern_target' | 'r_multiple' | 'percentage' | 'fixed';
     };
     
     // Time-based exit
     maxHoldTime?: number; // Exit after X bars
     minHoldTime?: number; // Don't exit before X bars
   }
   ```
   
   B. BACKTEST CONFIGURATION:
   - Ticker(s) to test
   - Date range
   - Initial capital
   - Commission structure
   - Slippage model
   - Bar size (1D, 4H, 1H, etc.)

2. HISTORICAL DATA LOADING:

   A. EFFICIENT DATA ACCESS:
   - Load data for entire backtest period
   - Pre-calculate indicators
   - Pre-run pattern detection
   - Cache results
   
   B. DATA QUALITY:
   - Handle missing data
   - Handle splits/dividends
   - Survivorship bias correction (if testing multiple stocks)

3. SIMULATION ENGINE:

   A. BAR-BY-BAR SIMULATION:
   ```javascript
   function runBacktest(strategy, data, config) {
     const portfolio = initPortfolio(config.initialCapital);
     const trades = [];
     
     for (let i = 0; i < data.length; i++) {
       const bar = data[i];
       
       // Check existing positions
       portfolio.positions.forEach(position => {
         // Check stop loss
         if (checkStopLoss(position, bar)) {
           closeTrade(position, bar, 'stop_loss');
         }
         
         // Check take profit
         if (checkTakeProfit(position, bar)) {
           closeTrade(position, bar, 'take_profit');
         }
         
         // Check time exit
         if (checkTimeExit(position, bar)) {
           closeTrade(position, bar, 'time_exit');
         }
         
         // Update trailing stop
         updateTrailingStop(position, bar);
       });
       
       // Check for new entries
       if (shouldEnter(strategy, data, i)) {
         const entry = executeEntry(strategy, bar, portfolio);
         if (entry) {
           portfolio.positions.push(entry);
           trades.push(entry);
         }
       }
       
       // Update portfolio value
       portfolio.equity = calculateEquity(portfolio, bar);
       portfolio.equityCurve.push({
         date: bar.date,
         equity: portfolio.equity
       });
     }
     
     return {
       trades: trades,
       metrics: calculateMetrics(trades, portfolio),
       equityCurve: portfolio.equityCurve
     };
   }
   ```
   
   B. REALISTIC EXECUTION:
   - Simulate market orders (fill at open of next bar)
   - Simulate limit orders (fill if price reached)
   - Simulate slippage
   - Simulate commission
   - Can't use future data (look-ahead bias prevention)

4. PATTERN-BASED ENTRY LOGIC:

   A. PATTERN DETECTION IN BACKTEST:
   - Run pattern detection as of each bar
   - Use only data available at that time
   - Track pattern completion percentage historically
   
   B. ENTRY DECISION:
   ```javascript
   function shouldEnter(strategy, data, currentIndex) {
     // Get pattern detections as of this bar
     const patterns = detectPatternsHistorical(
       data.slice(0, currentIndex + 1)
     );
     
     // Filter by strategy criteria
     const validPatterns = patterns.filter(p => 
       strategy.entryConditions.patterns.includes(p.type) &&
       p.confidence >= strategy.entryConditions.minConfidence &&
       p.completion >= strategy.entryConditions.minCompletion
     );
     
     if (validPatterns.length === 0) return false;
     
     // Check indicator conditions
     if (strategy.entryConditions.requiredIndicators) {
       if (!checkIndicators(data, currentIndex, strategy.entryConditions.requiredIndicators)) {
         return false;
       }
     }
     
     // Check timeframe alignment
     if (strategy.entryConditions.timeframes.length > 1) {
       const alignment = checkTimeframeAlignment(
         data,
         currentIndex,
         strategy.entryConditions.timeframes
       );
       if (alignment < strategy.entryConditions.minTimeframeAlignment) {
         return false;
       }
     }
     
     return true;
   }
   ```

5. POSITION SIZING:

   A. RISK-BASED SIZING:
   ```javascript
   function calculatePositionSize(strategy, entry, stop, portfolio) {
     const riskAmount = portfolio.equity * strategy.positionSizing.riskPerTrade;
     const riskPerShare = entry - stop;
     const shares = riskAmount / riskPerShare;
     
     // Cap at max position size
     const maxShares = (portfolio.equity * strategy.positionSizing.maxPositionSize) / entry;
     
     return Math.min(shares, maxShares);
   }
   ```
   
   B. KELLY CRITERION:
   - Use historical win rate and avg R
   - Calculate optimal position size
   - Apply fractional Kelly (e.g., 0.25 * Kelly)

6. EXIT LOGIC:

   A. STOP LOSS CALCULATION:
   ```javascript
   function calculateStopLoss(strategy, pattern, entry, atr) {
     switch (strategy.stopLoss.method) {
       case 'pattern_based':
         return pattern.stopLevel; // From pattern detection
       
       case 'atr':
         return entry - (atr * strategy.stopLoss.value);
       
       case 'percentage':
         return entry * (1 - strategy.stopLoss.value);
       
       case 'fixed':
         return strategy.stopLoss.value;
     }
   }
   ```
   
   B. TRAILING STOP:
   - Update stop as profit increases
   - Lock in gains
   - Protect against reversal
   
   C. TAKE PROFIT TARGETS:
   - Multiple targets with partial exits
   - Pattern-based targets (measured move)
   - R-multiple targets (2R, 3R, 5R)

7. PERFORMANCE METRICS:

   Calculate and report:
   
   A. RETURN METRICS:
   - Total return
   - CAGR (Compound Annual Growth Rate)
   - Monthly returns
   - Best/worst month
   
   B. RISK METRICS:
   - Maximum drawdown
   - Average drawdown
   - Drawdown duration
   - Volatility (standard deviation of returns)
   - Sharpe ratio
   - Sortino ratio
   - Calmar ratio
   
   C. TRADE METRICS:
   - Total trades
   - Win rate
   - Average win / Average loss
   - Profit factor
   - Expectancy
   - Average holding time
   - Largest win / Largest loss
   
   D. R-MULTIPLE ANALYSIS:
   - Average R (reward / risk)
   - Distribution of R-multiples
   - Percentage of trades hitting 1R, 2R, 3R, etc.
   
   E. PATTERN-SPECIFIC METRICS:
   - Win rate by pattern type
   - Average R by pattern
   - Best/worst patterns
   - Pattern frequency

8. MONTE CARLO SIMULATION:

   A. TRADE RANDOMIZATION:
   - Shuffle trade order
   - Run 1000+ simulations
   - Calculate distribution of outcomes
   
   B. CONFIDENCE INTERVALS:
   - 95% confidence interval for CAGR
   - Worst-case scenario
   - Best-case scenario
   - Probability of ruin

9. OPTIMIZATION:

   A. PARAMETER OPTIMIZATION:
   - Grid search over parameter ranges
   - Find optimal:
     * minConfidence
     * minCompletion
     * stopLoss value
     * takeProfit targets
   
   B. WALK-FORWARD ANALYSIS:
   - Optimize on in-sample data
   - Test on out-of-sample data
   - Prevent overfitting
   
   C. ROBUSTNESS TESTING:
   - Test across different market regimes
   - Test on different tickers
   - Test different timeframes

10. VISUALIZATION:

    A. EQUITY CURVE:
    - Portfolio value over time
    - Drawdown periods highlighted
    - Benchmark comparison (SPY)
    
    B. TRADE DISTRIBUTION:
    - Histogram of returns
    - Win/loss chart
    - R-multiple distribution
    
    C. METRICS DASHBOARD:
    - Summary statistics
    - Trade list with details
    - Pattern breakdown

11. CODE IMPLEMENTATION:

    Provide complete backtesting engine:
    - Data loading and caching
    - Simulation engine
    - Position management
    - Metrics calculation
    - Reporting and visualization
    
    Include:
    - TypeScript/Python classes
    - Example strategies
    - Test cases
    - CLI interface

12. VALIDATION:

    A. KNOWN-GOOD TESTS:
    - Test with known winning strategy
    - Verify metrics match expected
    
    B. EDGE CASE HANDLING:
    - No trades taken
    - Only winning trades
    - Only losing trades
    - Extreme volatility
    
    C. BIAS CHECKING:
    - Look-ahead bias detection
    - Survivorship bias check

Generate production-ready backtesting engine that can validate pattern strategies and provide comprehensive performance analysis.
```

**Why this yields great results:**
- Critical for validating your patterns
- Complex simulation logic
- Realistic execution modeling
- Comprehensive metrics
- Prevents overfitting

---

## SUMMARY: Which Prompts to Use First

**Immediate Priority (Build These First):**
1. ✅ **Pattern Detection Engine** - Core functionality
2. ✅ **Real-Time Processing Engine** - Performance critical
3. ✅ **Database Schema** - Foundation for everything

**High Priority (Build These Next):**
4. ✅ **Annotation Generation System** - User-facing, differentiator
5. ✅ **Language AI Integration** - News/sentiment analysis
6. ✅ **Alert System** - User engagement driver

**Important (Build After MVP):**
7. ✅ **Backtesting Engine** - Validate accuracy, build trust

**Each prompt will yield:**
- Production-ready code
- Specific algorithms
- Performance benchmarks
- Test cases
- Integration examples
- Edge case handling

**Use these prompts with Claude, GPT-4, or any advanced AI to generate complete, working implementations of each subsystem.**
