# MASTER PROMPT: AI-Powered Stock Trading Analysis Platform

You are an expert system architect tasked with designing a next-generation AI-powered stock trading analysis platform. This platform will have a CRITICAL COMPETITIVE ADVANTAGE: direct access to raw market data and custom charting infrastructure, eliminating the need for Vision AI and enabling real-time processing that is 30x faster and 500x cheaper than competitors.

## CORE REQUIREMENTS

### 1. FUNDAMENTAL ARCHITECTURE ADVANTAGE

**PRIMARY METHOD: Direct Data Processing**
- We own our charting system and control all market data
- Process raw OHLCV data, tick data, and market microstructure directly
- Calculate all indicators, patterns, and levels mathematically (no image analysis needed)
- Generate annotations with pixel-perfect coordinates from calculated data
- Real-time processing: sub-100ms from data receipt to user display

**NO VISION AI NEEDED FOR:**
- Pattern recognition (calculated from price arrays)
- Support/resistance detection (from price touch points)
- Trend analysis (mathematical calculation)
- Indicator values (direct computation)
- Chart annotations (generated from coordinates, not read from images)

**LANGUAGE AI USED FOR:**
- News sentiment analysis (text processing)
- Earnings transcript analysis (text processing)
- Social media sentiment (text processing)
- SEC filing analysis (text processing)
- Data synthesis and reasoning (combining all sources)
- Generating explanations and recommendations (natural language output)

### 2. DESIGN OBJECTIVES

Create a comprehensive system design document that includes:

**A. Technical Architecture**
- Complete data pipeline from market feeds to user display
- Real-time calculation engine (vectorized operations, <100ms latency)
- Pattern detection algorithms (50+ patterns, including emerging at 50%+ completion)
- Multi-timeframe analysis engine
- Annotation generation system (exact coordinates for drawings)
- Language AI integration for text analysis (news, sentiment, fundamentals)
- Database schema optimized for time-series data
- Scalability architecture (100k+ concurrent users)

**B. Pattern Recognition System**
- Mathematical pattern detection from price arrays (no visual interpretation)
- Support all major chart patterns: Head & Shoulders, Double/Triple Tops/Bottoms, Triangles, Wedges, Flags, Pennants, Channels, Cup & Handle, etc.
- Emerging pattern detection: identify patterns at 50-85% completion with probability scoring
- Real-time pattern monitoring: update completion percentage on every tick
- Historical pattern database: track success rates, average moves, time to targets
- Pattern validation: multi-timeframe confirmation, volume confirmation, momentum alignment

**C. Intelligent Annotation System**
- AI automatically draws on charts for EVERY analysis response
- Generate exact coordinates for all drawing elements:
  - Circles/ellipses (highlighting key points)
  - Horizontal lines (support, resistance, targets, stops)
  - Trendlines (ascending, descending, channels)
  - Rectangles (zones, consolidations, entry/exit areas)
  - Arrows (direction, breakout triggers, targets)
  - Text labels (pattern names, levels, notes)
- Color coding: green (bullish), red (bearish), blue (neutral), yellow (warning), orange (emerging)
- Dashed lines for projected/emerging patterns
- Semi-transparent zones for areas of interest

**D. Complete Trader Workflows**
- Pre-market preparation (gap analysis, watchlist generation, level identification)
- Opening range analysis
- Real-time monitoring (continuous pattern scanning, alert triggering)
- Entry analysis (optimal zones, position sizing, risk/reward calculation)
- Position management (trailing stops, profit targets, pattern invalidation warnings)
- Exit analysis (target achievement, pattern completion, momentum shifts)
- Post-market review (performance tracking, pattern success rate updates)

**E. Multi-Source Data Integration**
Design integration for:

1. **Market Data** (direct processing):
   - Real-time price/volume feeds
   - Level 2 order book (if available)
   - Options flow data
   - Dark pool prints
   - Time & sales

2. **News & Sentiment** (Language AI processing):
   - News APIs (NewsAPI, Benzinga, FMP, Alpha Vantage)
   - Sentiment analysis of headlines and articles
   - Event detection (earnings, FDA approvals, mergers, lawsuits)
   - Impact scoring (how news affects price probability)
   - Real-time news alerts with chart markers

3. **Social Media** (Language AI processing):
   - Twitter/X API (mentions, sentiment, volume)
   - Reddit API (WSB, investing, stocks subreddits)
   - StockTwits API
   - Unusual activity detection (volume spikes)
   - Influencer tracking
   - Viral post detection

4. **Fundamentals** (Language AI processing):
   - SEC EDGAR filings (10-K, 10-Q, 8-K, Form 4)
   - Earnings transcripts analysis
   - Management tone detection
   - Risk factor changes
   - Insider transaction tracking
   - Analyst reports

5. **Alternative Data** (API integration):
   - App download metrics
   - Web traffic data
   - Satellite foot traffic
   - Credit card transaction trends
   - Job posting trends
   - Supply chain signals

**F. Language AI Integration Architecture**

Design how Language AI (GPT-4, Claude, etc.) is used for:

1. **News Analysis**:
   ```
   Input: Array of news articles (text)
   Process: Sentiment classification, key theme extraction, impact scoring
   Output: Structured sentiment data + trading implications
   Cost: ~$0.02 per analysis (1000 words)
   ```

2. **Earnings Analysis**:
   ```
   Input: Earnings call transcript (text)
   Process: Tone analysis, guidance extraction, concern identification
   Output: Bullish/bearish signals + key quotes
   Cost: ~$0.03 per transcript (2000 words)
   ```

3. **Social Sentiment**:
   ```
   Input: Social media posts (text)
   Process: Aggregate sentiment, theme detection, unusual activity
   Output: Sentiment score + consensus + key themes
   Cost: ~$0.01 per batch (500 posts)
   ```

4. **SEC Filing Analysis**:
   ```
   Input: Filing text (10-K, 10-Q, etc.)
   Process: Risk factor extraction, red flag detection, comparison to previous filings
   Output: Key changes + concerns + management tone
   Cost: ~$0.04 per filing (3000 words)
   ```

5. **Data Synthesis**:
   ```
   Input: All data sources (technical + news + social + fundamental + alt data)
   Process: Identify confluence, resolve conflicts, generate unified recommendation
   Output: Comprehensive analysis + confidence score + reasoning
   Cost: ~$0.05 per synthesis (complex reasoning)
   ```

**G. Real-Time Processing Pipeline**

Design the data flow:
```
MARKET DATA FEED
    ↓ (10-100 messages/second)
DATA VALIDATION & NORMALIZATION
    ↓ (5ms)
REDIS CACHE (L1)
    ↓ (sub-millisecond access)
CALCULATION ENGINE CLUSTER
    ↓ (parallel processing)
├─→ Indicator Calculations (15ms)
├─→ Pattern Detection (20ms)
├─→ Level Identification (10ms)
└─→ Alert Checking (5ms)
    ↓
ANALYSIS RESULTS CACHE
    ↓
LANGUAGE AI (when needed)
├─→ News Analysis (async)
├─→ Sentiment Check (async)
└─→ Synthesis (async)
    ↓
ANNOTATION GENERATOR
    ↓ (10ms)
WEBSOCKET BROADCAST
    ↓ (10ms)
USER INTERFACE
```

**Total Latency: <100ms for technical analysis, +2s if Language AI synthesis needed**

### 3. SPECIFIC TECHNICAL IMPLEMENTATIONS

Provide detailed specifications for:

**A. Pattern Detection Algorithm**
- Pseudo-code or actual code for detecting double bottoms, cup & handles, triangles, etc.
- Exact calculations for pattern completion percentage
- Mathematical formulas for target calculation (measured moves)
- Historical database query structure for success rates
- Confidence scoring algorithm (multiple factors weighted)

**B. Emerging Pattern Monitoring**
- How to track patterns in real-time as they form
- When to alert users (50%, 75%, 90% completion thresholds)
- How to calculate estimated time to completion
- How to identify required conditions for pattern completion

**C. Support/Resistance Algorithm**
- How to find levels from price touch points (not visual)
- Strength scoring (number of touches, volume at touches, time held)
- Dynamic vs static level identification
- Level invalidation criteria

**D. Multi-Timeframe Analysis**
- How to run parallel analysis on 1m, 5m, 15m, 1H, 4H, 1D, 1W
- Timeframe alignment scoring (how many agree)
- Conflict resolution (when timeframes disagree)
- Weighting by timeframe (higher timeframes more important)

**E. Annotation Generation**
- Input: Pattern/level data with coordinates
- Output: Drawing commands (circles, lines, boxes, arrows, labels)
- Exact coordinate calculation from bar index and price
- Color and style selection logic
- Label positioning (avoid overlaps)

**F. Alert System**
- Real-time condition monitoring (price crosses level, pattern completes, etc.)
- Alert priority scoring
- Delivery mechanisms (push notification, email, SMS, in-app)
- Alert management (user preferences, snooze, dismiss)

**G. Language AI Prompt Engineering**
- Exact prompts for news sentiment analysis
- Prompts for earnings transcript analysis
- Prompts for data synthesis
- Response parsing (JSON structured outputs)
- Error handling and fallbacks

### 4. PERFORMANCE SPECIFICATIONS

Define concrete metrics:

**Speed:**
- Pattern recognition: <100ms target
- Full chart analysis: <150ms target
- Real-time annotation: <50ms target
- Alert triggering: <10ms target
- Multi-ticker scan (100 tickers): <5s target
- Language AI analysis: <3s target (when needed)

**Accuracy:**
- Pattern recognition: 85%+ accuracy target
- Support/resistance: ±0.3% precision target
- Breakout prediction: 70%+ success rate target
- News sentiment: 80%+ alignment with actual price impact

**Scalability:**
- Concurrent users: 100,000+
- Tickers monitored: 10,000+ actively
- Data points processed: 1M+ per second
- WebSocket connections: 100k+ active
- Database queries: 100k+ per second (with caching)

**Cost Efficiency:**
```
At 100k users:
- Direct data infrastructure: $7,000/month
- Language AI processing: $5,000/month (news/sentiment/synthesis)
- Total: $12,000/month
- Per user cost: $0.12/month

vs Pure Vision AI approach: $7,500,000/month
Savings: $7,488,000/month (99.84% cheaper)
```

### 5. ACCURACY & QUALITY ASSURANCE

Design systems for:

**A. Data Validation**
- Real-time sanity checks (price/volume reasonability)
- Circuit breaker detection
- Timestamp validation
- OHLC consistency checks

**B. Calculation Validation**
- Compare calculations to reference implementations
- Statistical validation against benchmarks
- Automated testing with known datasets

**C. Outcome Tracking**
- Track every pattern prediction vs actual outcome
- Calculate success rates by pattern type, timeframe, market condition
- Identify false positive patterns
- Continuous accuracy reporting

**D. Model Optimization**
- A/B testing of algorithm variations
- Automatic parameter tuning based on outcomes
- Pattern threshold adjustment (increase confidence for low-success patterns)
- Continuous learning from results

### 6. USER EXPERIENCE DESIGN

Design the interaction model:

**A. Proactive Intelligence**
- AI initiates alerts when opportunities arise
- Morning briefing with pre-market analysis
- Continuous monitoring with real-time notifications
- Pattern completion alerts (75%, 90% thresholds)

**B. Visual Guidance**
- Every AI response includes chart annotations
- Show exact entry zones (green boxes)
- Show stop loss levels (red lines)
- Show target levels (green dashed lines)
- Show pattern outlines (dashed colored boxes)
- Show trend lines and channels
- Highlight key candlesticks or volume bars

**C. Transparent Reasoning**
- Always explain why (show calculations)
- Cite data sources (news article, pattern history, etc.)
- Show confidence scores with reasoning
- Provide alternative scenarios when uncertain

**D. Complete Workflow Coverage**
```
8:00 AM  - Morning briefing (watchlist with annotated charts)
9:30 AM  - Opening range alerts
10:00 AM - Pattern completion alert (user clicks → full analysis ready)
11:30 AM - Entry signal (chart shows exact zone, stop, targets)
2:00 PM  - Position update (pattern progressing, adjust stop suggestion)
3:00 PM  - Target 1 hit (profit-taking recommendation)
4:00 PM  - Daily review (performance summary, tomorrow's opportunities)
```

### 7. COMPETITIVE ADVANTAGES

Explicitly highlight:

**Technical Moat:**
- 30x speed advantage (100ms vs 3000ms for Vision AI competitors)
- 500x cost advantage ($0.0001 vs $0.05 per analysis)
- 16% accuracy advantage (87% vs ~75% for Vision AI pattern recognition)
- Access to hidden data (tick data, order flow, microstructure)
- Real-time processing of every tick (not snapshot-based)

**User Value:**
- Catches opportunities before they're obvious
- Surgical precision (exact levels, not approximations)
- Complete automation (pre-market to post-market)
- Continuous learning and improvement
- Multi-source intelligence (technical + news + social + fundamental)

**Business Economics:**
- Can profitably serve users at $5-10/month
- High margins (>95% gross margin)
- Scalable (costs grow linearly, not exponentially)
- Network effects (more users = better models)

### 8. IMPLEMENTATION ROADMAP

Provide a 16-week plan:

**Phase 1: Foundation (Weeks 1-4)**
- Data ingestion pipeline
- Real-time calculation engine
- Basic pattern recognition (10 major patterns)
- Database schema and infrastructure
- Testing framework

**Phase 2: Intelligence (Weeks 5-8)**
- Advanced pattern recognition (50+ patterns)
- Emerging pattern detection
- Multi-timeframe analysis
- Language AI integration (news, sentiment)
- Auto-annotation system

**Phase 3: Workflows (Weeks 9-12)**
- Alert system
- Complete trader workflows
- Entry/exit analysis
- Position management
- Performance tracking

**Phase 4: Integration & Optimization (Weeks 13-16)**
- Alternative data integration
- Accuracy optimization
- Performance tuning
- Load testing
- Beta user testing

### 9. TECHNICAL STACK RECOMMENDATIONS

Specify:

**Frontend:**
- Framework: Next.js 14+ / React 18+
- Charting: Custom WebGL engine OR TradingView Lightweight Charts
- Real-time: WebSocket connections
- State management: Zustand or Jotai
- Styling: Tailwind CSS

**Backend:**
- Primary: Node.js (Express/Fastify) for API and WebSocket servers
- Compute: Python for calculation engine (NumPy, Pandas for vectorization)
- Cache: Redis for real-time data and pub/sub
- Database: PostgreSQL + TimescaleDB for time-series
- Streaming: Apache Kafka for event processing
- Language AI: Anthropic Claude API and/or OpenAI GPT-4 API

**Infrastructure:**
- Cloud: AWS or GCP (multi-region)
- Container: Docker + Kubernetes
- CDN: Cloudflare
- Monitoring: Datadog or New Relic
- Logging: ELK stack or Loki

**Data Sources:**
- Market Data: Polygon.io, IEX Cloud, or direct exchange feeds
- News: NewsAPI, Benzinga, Financial Modeling Prep
- Social: Twitter API, Reddit API, StockTwits
- Fundamentals: SEC EDGAR, Alpha Vantage, FMP
- Alternative: Various APIs as needed

### 10. OUTPUT FORMAT

Generate a comprehensive markdown document that includes:

1. **Executive Overview** - High-level summary of advantages and approach
2. **Technical Architecture** - Complete system design with diagrams
3. **Direct Data Processing** - Detailed explanation of primary analysis path
4. **Language AI Integration** - How text/news/sentiment analysis works
5. **Pattern Recognition Engine** - Algorithms and implementations
6. **Real-Time Processing Pipeline** - Data flow and latency analysis
7. **Multi-Source Intelligence** - Integration of technical + news + social + fundamental
8. **Annotation System** - How AI draws on charts
9. **Complete Workflows** - Pre-market to post-market automation
10. **Performance Specifications** - Concrete metrics and targets
11. **Quality Assurance** - Validation, testing, outcome tracking
12. **Cost Analysis** - Detailed cost breakdown and comparison
13. **Competitive Analysis** - Why competitors can't replicate
14. **Implementation Roadmap** - 16-week plan with milestones
15. **Technical Stack** - Specific technology recommendations
16. **Code Examples** - Pseudo-code or actual code for key algorithms

### 11. CRITICAL SUCCESS FACTORS

Emphasize throughout:

**Speed:** Sub-100ms real-time processing (30x faster than Vision AI)
**Precision:** Exact values, not visual estimates ($150.23 vs "~$150")
**Intelligence:** Multi-layer analysis (5 layers: patterns, technical, price action, momentum, context)
**Automation:** Complete workflow coverage (not just analysis, but guidance)
**Learning:** Continuous improvement from outcome tracking
**Scalability:** Handle 100k+ users without degradation
**Economics:** 500x cost advantage enables aggressive pricing

### 12. SPECIFIC SCENARIOS TO ADDRESS

Show how the system handles:

**Scenario A: User asks "What do you see?"**
- Run full analysis (<100ms)
- Detect all patterns (completed and emerging)
- Calculate all levels (support, resistance, targets)
- Identify momentum conditions
- Check news/sentiment (Language AI, async)
- Generate annotated chart with:
  - Pattern outlines (dashed colored boxes)
  - Key levels (horizontal lines)
  - Entry zones (green rectangles)
  - Stop loss (red line)
  - Targets (green dashed lines)
  - News markers (if relevant events)
- Provide structured text response explaining findings

**Scenario B: User asks "Where should I enter?"**
- Identify current pattern stage
- Calculate optimal entry zone (exact price range)
- Calculate stop loss (pattern invalidation + ATR-based)
- Calculate targets (measured move + Fibonacci extensions)
- Calculate position size (1% risk rule)
- Assess risk/reward ratio
- Check historical success rate for this setup
- Verify timeframe alignment
- Check news/sentiment for conflicts
- DRAW all levels on chart with exact coordinates
- Provide recommendation with confidence score

**Scenario C: Pattern 60% complete (early detection)**
- Real-time monitoring detects emerging pattern
- Calculate exact completion percentage (60%)
- Identify remaining requirements (price needs $X, volume needs Y%)
- Estimate time to completion (based on formation velocity)
- Calculate breakout trigger level
- Query historical similar patterns (success rate)
- DRAW dashed pattern outline on chart
- DRAW arrow at trigger level
- Send proactive alert: "Emerging pattern detected - 60% complete"
- Suggest alert placement for breakout trigger

**Scenario D: Multiple data sources conflict**
- Technical analysis: Bullish (double bottom forming)
- News sentiment: Bearish (negative earnings report)
- Social sentiment: Neutral (mixed opinions)
- Resolution:
  - Weight by reliability (technical patterns most reliable)
  - Assess news impact (is it already priced in?)
  - Check timeframe (news short-term, pattern longer-term)
  - Provide multiple scenarios:
    - Scenario 1 (60% probability): Pattern succeeds despite news
    - Scenario 2 (30% probability): News derails pattern
    - Scenario 3 (10% probability): Extended consolidation
- Recommend: Wait for confirmation or reduce position size

**Scenario E: Real-time pattern monitoring**
- User is watching AAPL, pattern is 75% complete
- Every tick updates completion percentage
- At 80%: Update annotation, highlight increasing probability
- At 85%: Send alert "Pattern approaching completion"
- At 90%: Send alert "Pattern ready to break - prepare entry"
- At 95% + volume surge: Send alert "Breakout imminent!"
- When breakout occurs: Send alert "Breakout confirmed - entry signal"
- THROUGHOUT: Chart annotations update in real-time

### 13. FINAL REQUIREMENTS

The document must be:

✅ **Comprehensive** - Cover all aspects from architecture to implementation
✅ **Technical** - Include specific algorithms, code examples, formulas
✅ **Practical** - Provide actionable specifications, not just theory
✅ **Detailed** - Enough detail that a development team could implement
✅ **Focused** - Emphasize direct data processing, NOT Vision AI
✅ **Cost-Conscious** - Show cost advantages at every level
✅ **User-Centric** - Design for trader workflows and needs
✅ **Scalable** - Architecture must handle 100k+ users
✅ **Accurate** - Include validation and quality assurance
✅ **Complete** - Cover data ingestion through user interface

### 14. KEY MESSAGES TO REINFORCE

Throughout the document, reinforce:

1. **Direct data processing is the core advantage** - Not Vision AI
2. **Language AI is for text analysis only** - News, sentiment, fundamentals
3. **Real-time processing is 30x faster** - Sub-100ms vs 3+ seconds
4. **Cost is 500x lower** - $0.0001 vs $0.05 per analysis
5. **Accuracy is 16% higher** - Mathematical precision vs visual estimation
6. **AI draws on charts automatically** - Every response includes annotations
7. **Complete workflow automation** - Pre-market to post-market
8. **Multi-source intelligence** - Technical + news + social + fundamental
9. **Continuous learning** - Track outcomes, improve accuracy
10. **Impossible to replicate** - Competitors need 18-24 months to rebuild

---

## DELIVERABLE

Generate a comprehensive system design document (20,000+ words) that a technical team could use to build this platform. Include architecture diagrams (in text/ASCII), code examples, database schemas, API specifications, cost breakdowns, implementation timeline, and everything needed to go from concept to production.

The document should make it crystal clear that:
- We DON'T need Vision AI for chart analysis (we process raw data)
- We DO need Language AI for text analysis (news, sentiment, etc.)
- Our direct data approach is faster, cheaper, and more accurate
- This creates an unbeatable competitive advantage

Make it detailed, technical, practical, and actionable.
