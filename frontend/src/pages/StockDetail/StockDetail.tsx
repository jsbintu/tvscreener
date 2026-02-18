/**
 * StockDetail v2 — The Main Event
 *
 * Full stock analysis page with 14 data panels:
 * 1. Price Header (live WebSocket + Alpaca)
 * 2. TradingView Chart (widget embed)
 * 3. Technical Analysis (26-indicator summary)
 * 4. Financials (revenue, margins, P/E, FCF)
 * 5. Options Flow (combined QuantData + OptionStrats)
 * 6. IV Surface (rank, skew, term structure)
 * 7. Greek Exposure (GEX/DEX/VEX)
 * 8. Combined News (Finnhub + QuantData)
 * 9. Sentiment (F&G + Finnhub + Reddit)
 * 10. SEC Filings (10-K, 10-Q, 8-K)
 * 11. Insider Trades (SEC Form 4)
 * 12. Analyst Ratings (PT + consensus)
 * 13. Strategy Builder (OptionStrats iframe)
 * 14. External Links
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
    Activity,
    AlertTriangle,
    Anchor,
    ArrowLeft,
    BarChart2,
    BarChart3,
    Bell,
    BookOpen,
    Box,
    Briefcase,
    Calendar,
    ChevronDown,
    ChevronUp,
    Clock,
    Compass,
    Crosshair,
    DollarSign,
    ExternalLink,
    Eye,
    FileText,
    Gauge,
    GitBranch,
    Globe,
    Layers,
    Link2,
    MessageCircle,
    Mic,
    Newspaper,
    Radio,
    Search,
    Shield,
    Target,
    TrendingDown,
    TrendingUp,
    Users,
    Zap,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { analysisApi, marketApi, stockApi } from '../../api/client';
import PatternChart from '../../components/Charts/PatternChart';
import TradingViewChart from '../../components/Charts/TradingViewChart';
import OptionStratsEmbed from '../../components/Embeds/OptionStratsEmbed';
import {
    CoachingPanel,
    GamificationPanel,
    GhostChartPanel,
    OpeningRangePanel,
    OptimizerPanel,
} from '../../components/Phase4';
import { usePanelState } from '../../hooks/usePanelState';
import { useLivePrice } from '../../hooks/useWebSocket';
import { formatCompact, formatCurrency, formatDate, formatPercent, priceColorClass, timeAgo } from '../../utils/format';
import './StockDetail.css';

/* eslint-disable @typescript-eslint/no-explicit-any */

interface PanelProps {
    title: string;
    icon: React.ReactNode;
    loading: boolean;
    children: React.ReactNode;
    defaultOpen?: boolean;
    panelId?: string;
    badge?: string;
    badgeColor?: string;
    /** Callback fired whenever the panel opens or closes — use for query lazy-loading */
    onOpenChange?: (isOpen: boolean) => void;
}

/** Collapsible data panel with optional localStorage persistence */
function Panel({
    title,
    icon,
    loading,
    children,
    defaultOpen = true,
    panelId,
    badge,
    badgeColor,
    onOpenChange,
}: PanelProps) {
    // Use persistent state if panelId is provided, otherwise ephemeral
    const [persistOpen, persistToggle] = usePanelState(panelId || '__ephemeral__', defaultOpen);
    const [ephemeralOpen, setEphemeralOpen] = useState(defaultOpen);

    const open = panelId ? persistOpen : ephemeralOpen;
    const handleToggle = () => {
        if (panelId) {
            persistToggle();
        } else {
            setEphemeralOpen((o) => !o);
        }
        onOpenChange?.(!open);
    };

    // Fire onOpenChange on mount so parent knows initial state
    const mountedRef = useRef(false);
    useEffect(() => {
        if (!mountedRef.current) {
            mountedRef.current = true;
            onOpenChange?.(open);
        }
    }, [open, onOpenChange]);

    return (
        <div className="card panel-card">
            <button type="button" className="card-header panel-toggle" onClick={handleToggle}>
                <span className="card-title">
                    {icon} {title}
                    {badge && (
                        <span className={`badge badge-${badgeColor || 'blue'}`} style={{ marginLeft: 8 }}>
                            {badge}
                        </span>
                    )}
                </span>
                {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
            {open && (
                <div className="panel-body">
                    {loading ? <div className="skeleton" style={{ height: 100 }} /> : children}
                </div>
            )}
        </div>
    );
}

/** Section divider for grouping panels by category */
function SectionDivider({ label }: { label: string }) {
    return (
        <div className="section-divider">
            <span className="section-divider-label">{label}</span>
        </div>
    );
}

/** Render a key-value grid from a record */
function KVGrid({ data, max = 20 }: { data: Record<string, any>; max?: number }) {
    const entries = Object.entries(data).slice(0, max);
    if (!entries.length) return <div className="text-muted">No data available</div>;
    return (
        <div className="kv-grid">
            {entries.map(([key, val]) => (
                <div key={key} className="kv-item">
                    <span className="kv-label">{key.replace(/_/g, ' ')}</span>
                    <span className="kv-value">
                        {typeof val === 'number'
                            ? Math.abs(val) > 1000
                                ? formatCompact(val)
                                : val.toFixed(2)
                            : String(val ?? '—')}
                    </span>
                </div>
            ))}
        </div>
    );
}

/** Toggle button to add/remove a ticker from the pattern scan watchlist */
function WatchPatternBtn({ ticker }: { ticker: string }) {
    const qc = useQueryClient();
    const { data: wlRaw } = useQuery({
        queryKey: ['patternWatchlist'],
        queryFn: () => marketApi.getPatternWatchlist(),
        staleTime: 60_000,
    });
    const watchlist: string[] = wlRaw?.data?.watchlist ?? [];
    const isWatching = watchlist.includes(ticker.toUpperCase());

    const toggle = useMutation({
        mutationFn: () => marketApi.managePatternWatchlist([ticker.toUpperCase()], isWatching ? 'remove' : 'add'),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['patternWatchlist'] }),
    });

    return (
        <button
            type="button"
            className={`watch-pattern-btn ${isWatching ? 'watching' : ''}`}
            onClick={() => toggle.mutate()}
            disabled={toggle.isPending}
            title={isWatching ? 'Stop scanning patterns' : 'Add to pattern scanner'}
        >
            <Eye size={14} />
            {isWatching ? 'Watching' : 'Watch Patterns'}
        </button>
    );
}

export default function StockDetail() {
    const { ticker } = useParams<{ ticker: string }>();
    const queryClient = useQueryClient();

    // ── TanStack Query helpers ──
    const ex = (res: any) => res?.data ?? null;
    const exArr = (res: any) => {
        const d = ex(res);
        return Array.isArray(d) ? d : d?.data || d?.results || [];
    };

    const enabled = !!ticker;

    // ── Tiered query freshness ──
    // Intervals aligned with backend cache TTLs for optimal data accuracy
    const qLive = { enabled, retry: 1, refetchInterval: 15_000, staleTime: 10_000 }; // 15s — price-sensitive
    const qActive = { enabled, retry: 1, refetchInterval: 60_000, staleTime: 30_000 }; // 60s — active market data
    const qNews = { enabled, retry: 1, refetchInterval: 120_000, staleTime: 60_000 }; // 2min — news/social
    const qSlow = { enabled, retry: 1, refetchInterval: 300_000, staleTime: 120_000 }; // 5min — fundamentals
    const qStatic = { enabled, retry: 1, refetchInterval: 900_000, staleTime: 300_000 }; // 15min — rare/computational

    // ── Panel-group lazy-loading flags ──
    // Queries gated behind these won't fire until their panel section opens.
    const [financialsOpen, setFinancialsOpen] = useState(true);
    const [optionsOpen, setOptionsOpen] = useState(true);
    const [sentimentOpen, setSentimentOpen] = useState(true);
    const [researchOpen, setResearchOpen] = useState(true);
    const [patternsOpen, setPatternsOpen] = useState(true);
    const [advancedOpen, setAdvancedOpen] = useState(false);

    // Memoized callbacks for Panel onOpenChange
    const onFinancialsChange = useCallback((o: boolean) => setFinancialsOpen(o), []);
    const onOptionsChange = useCallback((o: boolean) => setOptionsOpen(o), []);
    const onSentimentChange = useCallback((o: boolean) => setSentimentOpen(o), []);
    const onResearchChange = useCallback((o: boolean) => setResearchOpen(o), []);
    const onPatternsChange = useCallback((o: boolean) => setPatternsOpen(o), []);
    const onAdvancedChange = useCallback((o: boolean) => setAdvancedOpen(o), []);

    // ── Core queries ──
    const { data: stockRaw, isLoading: loading } = useQuery({
        queryKey: ['stock', ticker, 'core'],
        queryFn: () => stockApi.getStock(ticker!),
        ...qLive,
    });
    const stock = ex(stockRaw);

    const { data: techRaw } = useQuery({
        queryKey: ['stock', ticker, 'technical'],
        queryFn: () => marketApi.getTechnical(ticker!),
        ...qLive,
    });
    const technical = ex(techRaw);

    const { data: finRaw } = useQuery({
        queryKey: ['stock', ticker, 'financials'],
        queryFn: () => stockApi.getFinancials(ticker!),
        ...qSlow,
        enabled: enabled && financialsOpen,
    });
    const financials = ex(finRaw);

    const { data: flowRaw } = useQuery({
        queryKey: ['stock', ticker, 'flow'],
        queryFn: () => marketApi.getCombinedFlow(ticker!),
        ...qLive,
        enabled: enabled && optionsOpen,
    });
    const flow = exArr(flowRaw);

    const { data: ivRaw } = useQuery({
        queryKey: ['stock', ticker, 'iv'],
        queryFn: () => marketApi.getIV(ticker!),
        ...qLive,
        enabled: enabled && optionsOpen,
    });
    const iv = ex(ivRaw);

    const { data: expRaw } = useQuery({
        queryKey: ['stock', ticker, 'exposure'],
        queryFn: () => marketApi.getExposure(ticker!),
        ...qLive,
        enabled: enabled && optionsOpen,
    });
    const exposure = ex(expRaw);

    const { data: newsRaw } = useQuery({
        queryKey: ['stock', ticker, 'news'],
        queryFn: () => marketApi.getCombinedNews(ticker!, 15),
        ...qNews,
        enabled: enabled && sentimentOpen,
    });
    const news = exArr(newsRaw);

    const { data: sentRaw } = useQuery({
        queryKey: ['stock', ticker, 'sentiment'],
        queryFn: () => marketApi.getSentiment(ticker!),
        ...qActive,
        enabled: enabled && sentimentOpen,
    });
    const sentiment = ex(sentRaw);

    const { data: filRaw } = useQuery({
        queryKey: ['stock', ticker, 'filings'],
        queryFn: () => marketApi.getFilings(ticker!),
        ...qSlow,
        enabled: enabled && researchOpen,
    });
    const filings = exArr(filRaw);

    const { data: insRaw } = useQuery({
        queryKey: ['stock', ticker, 'insider'],
        queryFn: () => stockApi.getInsiderTransactions(ticker!),
        ...qSlow,
        enabled: enabled && researchOpen,
    });
    const insider = exArr(insRaw);

    const { data: analRaw } = useQuery({
        queryKey: ['stock', ticker, 'analyst'],
        queryFn: () => stockApi.getAnalyst(ticker!),
        ...qSlow,
        enabled: enabled && researchOpen,
    });
    const analyst = ex(analRaw);

    const { data: linksRaw } = useQuery({
        queryKey: ['stock', ticker, 'links'],
        queryFn: () => stockApi.getTickerLinks(ticker!),
        ...qStatic,
    });
    const links = ex(linksRaw);

    // ── OpenBB Enhanced Data (Phase 9) ──
    const { data: instRaw } = useQuery({
        queryKey: ['stock', ticker, 'institutional'],
        queryFn: () => analysisApi.getInstitutionalOwnership(ticker!),
        ...qStatic,
        enabled: enabled && financialsOpen,
    });
    const institutional = ex(instRaw);

    const { data: obDivRaw } = useQuery({
        queryKey: ['stock', ticker, 'dividends'],
        queryFn: () => analysisApi.getDividendHistory(ticker!),
        ...qStatic,
        enabled: enabled && financialsOpen,
    });
    const obDividends = ex(obDivRaw);

    const { data: ecoRaw } = useQuery({
        queryKey: ['economic-calendar'],
        queryFn: () => analysisApi.getEconomicCalendar(7),
        staleTime: 1000 * 60 * 15, // 15 min
    });
    const ecoCalendar = ex(ecoRaw);

    // ── OpenBB News Wire (Bloomberg-grade) ──
    const { data: worldNewsRaw } = useQuery({
        queryKey: ['world-news'],
        queryFn: () => analysisApi.getWorldNews(30),
        staleTime: 1000 * 60 * 5, // 5 min
    });
    const worldNews = ex(worldNewsRaw);

    // ── Breakout ──
    const {
        data: brkRaw,
        isLoading: breakoutLoading,
        isError: breakoutError,
    } = useQuery({
        queryKey: ['stock', ticker, 'breakout'],
        queryFn: () => marketApi.getBreakoutFull(ticker!),
        ...qLive,
    });
    const breakout = ex(brkRaw);

    // ── Extended data ──
    const { data: ptRaw } = useQuery({
        queryKey: ['stock', ticker, 'priceTarget'],
        queryFn: () => marketApi.getPriceTarget(ticker!),
        ...qActive,
    });
    const priceTarget = ex(ptRaw);

    const { data: eeRaw } = useQuery({
        queryKey: ['stock', ticker, 'earningsEst'],
        queryFn: () => marketApi.getEarningsEstimates(ticker!),
        ...qActive,
        enabled: enabled && researchOpen,
    });
    const earningsEst = ex(eeRaw);

    const { data: fundRaw } = useQuery({
        queryKey: ['stock', ticker, 'fundamentals'],
        queryFn: () => marketApi.getBasicFundamentals(ticker!),
        ...qSlow,
        enabled: enabled && financialsOpen,
    });
    const fundamentals = ex(fundRaw);

    const { data: isRaw } = useQuery({
        queryKey: ['stock', ticker, 'insiderSent'],
        queryFn: () => marketApi.getInsiderSentiment(ticker!),
        ...qActive,
        enabled: enabled && researchOpen,
    });
    const insiderSent = ex(isRaw);

    const { data: caRaw } = useQuery({
        queryKey: ['stock', ticker, 'corpActions'],
        queryFn: () => marketApi.getCorporateActions(ticker!),
        ...qSlow,
        enabled: enabled && researchOpen,
    });
    const corpActions = exArr(caRaw);

    const { data: patRaw } = useQuery({
        queryKey: ['stock', ticker, 'patterns'],
        queryFn: () => marketApi.getPatterns(ticker!),
        ...qActive,
        enabled: enabled && patternsOpen,
    });
    const patterns = ex(patRaw);

    const { data: confRaw } = useQuery({
        queryKey: ['stock', ticker, 'confluence'],
        queryFn: () => marketApi.getPatternConfluence(ticker!),
        ...qActive,
        enabled: enabled && patternsOpen,
    });
    const confluence = ex(confRaw);

    const { data: fibRaw } = useQuery({
        queryKey: ['stock', ticker, 'fibonacci'],
        queryFn: () => marketApi.getFibonacci(ticker!),
        ...qActive,
        enabled: enabled && patternsOpen,
    });
    const fibonacci = ex(fibRaw);

    const { data: chRaw } = useQuery({
        queryKey: ['stock', ticker, 'chartHealth'],
        queryFn: () => marketApi.getChartHealth(ticker!),
        ...qActive,
        enabled: enabled && patternsOpen,
    });
    const chartHealth = ex(chRaw);

    const { data: oiRaw } = useQuery({
        queryKey: ['stock', ticker, 'oiPatterns'],
        queryFn: () => marketApi.getOiPatterns(ticker!),
        ...qLive,
        enabled: enabled && optionsOpen,
    });
    const oiPatterns = ex(oiRaw);

    const { data: gexRaw } = useQuery({
        queryKey: ['stock', ticker, 'gexDetailed'],
        queryFn: () => marketApi.getGexDetailed(ticker!),
        ...qLive,
        enabled: enabled && optionsOpen,
    });
    const gexDetailed = ex(gexRaw);

    // Phase 7b: Options Analytics (audit — previously orphaned)
    const { data: mpRaw } = useQuery({
        queryKey: ['stock', ticker, 'maxPain'],
        queryFn: () => marketApi.getMaxPain(ticker!),
        ...qLive,
        enabled: enabled && optionsOpen,
    });
    const maxPain = ex(mpRaw);
    const { data: pcrRaw } = useQuery({
        queryKey: ['stock', ticker, 'pcr'],
        queryFn: () => marketApi.getPCR(ticker!),
        ...qLive,
        enabled: enabled && optionsOpen,
    });
    const pcr = ex(pcrRaw);
    const { data: ivAnalRaw } = useQuery({
        queryKey: ['stock', ticker, 'ivAnalysis'],
        queryFn: () => marketApi.getIVAnalysis(ticker!),
        ...qLive,
        enabled: enabled && optionsOpen,
    });
    const ivAnalysis = ex(ivAnalRaw);
    const { data: smRaw } = useQuery({
        queryKey: ['stock', ticker, 'smartMoney'],
        queryFn: () => marketApi.getSmartMoney(ticker!),
        ...qLive,
        enabled: enabled && optionsOpen,
    });
    const smartMoney = ex(smRaw);
    const { data: unusualIntRaw } = useQuery({
        queryKey: ['stock', ticker, 'unusualInternal'],
        queryFn: () => marketApi.getUnusualInternal(ticker!),
        ...qLive,
        enabled: enabled && optionsOpen,
    });
    const unusualInternal = ex(unusualIntRaw);
    const { data: taRaw } = useQuery({
        queryKey: ['stock', ticker, 'taIndicators'],
        queryFn: () => marketApi.getIndicators(ticker!),
        ...qLive,
        enabled: enabled && patternsOpen,
    });
    const taIndicators = ex(taRaw);

    const { data: hgRaw } = useQuery({
        queryKey: ['stock', ticker, 'higherGreeks'],
        queryFn: () => marketApi.getHigherGreeks(ticker!),
        ...qLive,
        enabled: enabled && optionsOpen,
    });
    const higherGreeks = ex(hgRaw);

    const { data: myfRaw } = useQuery({
        queryKey: ['stock', ticker, 'multiYearFin'],
        queryFn: () => marketApi.getMultiYearFinancials(ticker!),
        ...qSlow,
        enabled: enabled && financialsOpen,
    });
    const multiYearFin = ex(myfRaw);

    const { data: qfRaw } = useQuery({
        queryKey: ['stock', ticker, 'quarterlyFin'],
        queryFn: () => marketApi.getQuarterlyFinancials(ticker!),
        ...qSlow,
        enabled: enabled && financialsOpen,
    });
    const quarterlyFin = ex(qfRaw);

    const { data: wsbRaw } = useQuery({
        queryKey: ['stock', ticker, 'wsbDD'],
        queryFn: () => marketApi.getWsbDD(ticker!),
        ...qNews,
        enabled: enabled && sentimentOpen,
    });
    const wsbDD = exArr(wsbRaw);

    const { data: etRaw } = useQuery({
        queryKey: ['stock', ticker, 'earningsTranscript'],
        queryFn: () => marketApi.getEarningsTranscript(ticker!),
        ...qSlow,
        enabled: enabled && researchOpen,
    });
    const earningsTranscript = ex(etRaw);

    const { data: poRaw } = useQuery({
        queryKey: ['stock', ticker, 'patternOutcomes'],
        queryFn: () => marketApi.getPatternOutcomes(ticker!),
        ...qStatic,
        enabled: enabled && patternsOpen,
    });
    const patternOutcomes = ex(poRaw);

    const { data: pbRaw } = useQuery({
        queryKey: ['stock', ticker, 'patternBacktest'],
        queryFn: () => marketApi.backtestPatterns(ticker!),
        ...qStatic,
        enabled: enabled && patternsOpen,
    });
    const patternBacktest = ex(pbRaw);

    const { data: paRaw } = useQuery({
        queryKey: ['stock', ticker, 'patternAlerts'],
        queryFn: () => marketApi.getPatternAlerts(ticker!),
        ...qStatic,
        enabled: enabled && patternsOpen,
    });
    const patternAlerts = exArr(paRaw);

    // ── Questrade Enriched Quote ──
    const { data: eqRaw } = useQuery({
        queryKey: ['stock', ticker, 'enrichedQuote'],
        queryFn: () => marketApi.getEnrichedQuote(ticker!),
        ...qLive,
    });
    const enrichedQuote = ex(eqRaw);

    // ── Tier 2: Advanced Analytics ──
    const { data: avwapRaw } = useQuery({
        queryKey: ['stock', ticker, 'avwap'],
        queryFn: () => analysisApi.getAnchoredVwap(ticker!),
        ...qActive,
        enabled: enabled && advancedOpen,
    });
    const avwap = ex(avwapRaw);

    const { data: vpRaw } = useQuery({
        queryKey: ['stock', ticker, 'volumeProfile'],
        queryFn: () => analysisApi.getVolumeProfile(ticker!),
        ...qActive,
        enabled: enabled && advancedOpen,
    });
    const volumeProfile = ex(vpRaw);

    const { data: msRaw } = useQuery({
        queryKey: ['stock', ticker, 'marketStructure'],
        queryFn: () => analysisApi.getMarketStructure(ticker!),
        ...qActive,
        enabled: enabled && advancedOpen,
    });
    const marketStructure = ex(msRaw);

    const { data: czRaw } = useQuery({
        queryKey: ['stock', ticker, 'consolidation'],
        queryFn: () => analysisApi.getConsolidationZones(ticker!),
        ...qActive,
        enabled: enabled && advancedOpen,
    });
    const consolidationZones = ex(czRaw);

    const { data: lzRaw } = useQuery({
        queryKey: ['stock', ticker, 'liquidity'],
        queryFn: () => analysisApi.getLiquidityZones(ticker!),
        ...qActive,
        enabled: enabled && advancedOpen,
    });
    const liquidityZones = ex(lzRaw);

    const { data: mtpRaw } = useQuery({
        queryKey: ['stock', ticker, 'multiTarget'],
        queryFn: () => analysisApi.getMultiTargetTP(ticker!),
        ...qActive,
        enabled: enabled && advancedOpen,
    });
    const multiTargetTP = ex(mtpRaw);

    const { data: gtRaw } = useQuery({
        queryKey: ['stock', ticker, 'googleTrends'],
        queryFn: () => analysisApi.getGoogleTrends(ticker!),
        ...qNews,
        enabled: enabled && sentimentOpen,
    });
    const googleTrends = ex(gtRaw);

    const { data: stRaw } = useQuery({
        queryKey: ['stock', ticker, 'stockTwits'],
        queryFn: () => analysisApi.getStockTwits(ticker!),
        ...qNews,
        enabled: enabled && sentimentOpen,
    });
    const stockTwits = ex(stRaw);

    const { data: acRaw } = useQuery({
        queryKey: ['stock', ticker, 'alertChains'],
        queryFn: () => analysisApi.getTickerChains(ticker!),
        ...qStatic,
    });
    const alertChains = exArr(acRaw);

    const { data: adRaw } = useQuery({
        queryKey: ['accuracyDashboard'],
        queryFn: () => analysisApi.getAccuracyDashboard(),
        ...qStatic,
    });
    const accuracyDash = ex(adRaw);

    const { data: ccRaw } = useQuery({
        queryKey: ['confidenceCalibration'],
        queryFn: () => analysisApi.getConfidenceCalibration(),
        ...qStatic,
    });
    const calibration = ex(ccRaw);

    const { data: wfRaw } = useQuery({
        queryKey: ['stock', ticker, 'walkForward'],
        queryFn: () => analysisApi.walkForwardBacktest(ticker!),
        ...qStatic,
        enabled: enabled && advancedOpen,
    });
    const walkForward = ex(wfRaw);

    const { data: mcRaw } = useQuery({
        queryKey: ['stock', ticker, 'monteCarlo'],
        queryFn: () => analysisApi.monteCarloBacktest(ticker!),
        ...qStatic,
        enabled: enabled && advancedOpen,
    });
    const monteCarlo = ex(mcRaw);

    const { data: ssRaw } = useQuery({
        queryKey: ['stock', ticker, 'sentimentSynthesis'],
        queryFn: () => analysisApi.getSentimentSynthesis(ticker!),
        ...qActive,
        enabled: enabled && sentimentOpen,
    });
    const sentimentSynth = ex(ssRaw);

    const { data: corrRaw } = useQuery({
        queryKey: ['stock', ticker, 'correlation'],
        queryFn: () => analysisApi.getCorrelationMatrix([ticker!, 'SPY', 'QQQ']),
        ...qActive,
        enabled: enabled && advancedOpen,
    });
    const correlation = ex(corrRaw);

    const { data: svRaw } = useQuery({
        queryKey: ['stock', ticker, 'socialVolume'],
        queryFn: () => analysisApi.getSocialVolume(ticker!),
        ...qActive,
        enabled: enabled && sentimentOpen,
    });
    const socialVolume = ex(svRaw);

    const { data: mktStatusRaw } = useQuery({
        queryKey: ['marketStatus'],
        queryFn: () => marketApi.getMarketStatus(),
        ...qStatic,
    });
    const marketStatus = ex(mktStatusRaw);

    const { data: briefRaw } = useQuery({
        queryKey: ['briefing', 'latest'],
        queryFn: () => marketApi.getLatestBriefing(),
        ...qStatic,
    });
    const briefing = ex(briefRaw);

    const { data: journalRaw } = useQuery({
        queryKey: ['journal', 'latest'],
        queryFn: () => marketApi.getLatestJournal(),
        ...qStatic,
    });
    const journal = ex(journalRaw);

    const { data: divRaw } = useQuery({
        queryKey: ['dividendCalendar'],
        queryFn: () => marketApi.getDividendCalendar(),
        ...qStatic,
    });
    const dividends = ex(divRaw);

    const { data: perfRaw } = useQuery({
        queryKey: ['portfolioPerformance'],
        queryFn: () => marketApi.getPortfolioPerformance(),
        ...qStatic,
    });
    const portfolio = ex(perfRaw);

    // ── Gap Closure: Pattern Accuracy, Exit Analysis, Recent Outcomes ──
    const { data: paQdbRaw } = useQuery({
        queryKey: ['patternAccuracyQDB'],
        queryFn: () => analysisApi.getPatternAccuracyQDB(undefined, ticker!),
        ...qStatic,
    });
    const patternAccuracyQDB = ex(paQdbRaw);

    const { data: exitRaw } = useQuery({
        queryKey: ['stock', ticker, 'exitAnalysis'],
        queryFn: () => analysisApi.getExitAnalysis(ticker!),
        ...qStatic,
        enabled: enabled && advancedOpen,
    });
    const exitAnalysis = ex(exitRaw);

    const { data: roRaw } = useQuery({
        queryKey: ['recentOutcomes'],
        queryFn: () => analysisApi.getRecentOutcomes(20),
        ...qStatic,
    });
    const recentOutcomes = ex(roRaw);

    // ── Vision (on-demand, still manual) ──
    const [visionAnalysis, setVisionAnalysis] = useState<any>(null);
    const [visionNarration, setVisionNarration] = useState<any>(null);
    const [visionLoading, setVisionLoading] = useState(false);
    const [chartMode, setChartMode] = useState<'tv' | 'pattern'>('tv');

    const { price: livePrice, connected } = useLivePrice(ticker || null);

    const price = livePrice?.price ?? stock?.price ?? stock?.close ?? null;
    const change = stock?.change ?? null;
    const changePercent = stock?.change_percent ?? stock?.perf ?? null;

    if (!ticker) return <div className="empty-state">No ticker selected</div>;

    return (
        <div className="page-container stock-detail">
            <Link to="/" className="back-link">
                <ArrowLeft size={16} /> Back to Dashboard
            </Link>

            {/* ── 1. Price Header ── */}
            <div className="stock-header">
                <div className="stock-header-left">
                    <h1 className="stock-ticker">{ticker}</h1>
                    <div className="stock-name">{stock?.name || stock?.company_name || ''}</div>
                    <div className="stock-badges">
                        {connected && <span className="badge badge-green">● LIVE</span>}
                        {stock?.sector && <span className="badge badge-blue">{stock.sector}</span>}
                        <WatchPatternBtn ticker={ticker!} />
                    </div>
                </div>
                <div className="stock-header-right">
                    <div className="stock-price">{formatCurrency(price)}</div>
                    <div className={`stock-change ${priceColorClass(changePercent)}`}>
                        {changePercent != null && changePercent > 0 ? (
                            <TrendingUp size={16} />
                        ) : (
                            <TrendingDown size={16} />
                        )}
                        {formatCurrency(change)} ({formatPercent(changePercent)})
                    </div>
                    {stock?.volume && <div className="stock-volume">Vol: {formatCompact(stock.volume)}</div>}
                </div>
            </div>

            {/* ── 2. Chart (TradingView / PatternChart toggle) ── */}
            <div className="chart-section">
                <div className="chart-mode-toggle">
                    <button
                        type="button"
                        className={`pill ${chartMode === 'tv' ? 'pill--active' : ''}`}
                        onClick={() => setChartMode('tv')}
                    >
                        TradingView
                    </button>
                    <button
                        type="button"
                        className={`pill ${chartMode === 'pattern' ? 'pill--active' : ''}`}
                        onClick={() => setChartMode('pattern')}
                    >
                        📐 Pattern Chart
                    </button>
                </div>
                {chartMode === 'tv' ? (
                    <div className="chart-container">
                        <TradingViewChart ticker={ticker} height={520} />
                    </div>
                ) : (
                    <PatternChart ticker={ticker!} height={620} />
                )}
            </div>

            {/* ── Two-Column Grid ── */}
            <div className="detail-grid">
                {/* ── LEFT COLUMN ── */}
                <div className="detail-col">
                    <SectionDivider label="Core Market Data" />
                    {/* 3. Technical Analysis */}
                    <Panel
                        panelId="sd-technical-analysis"
                        title="Technical Analysis"
                        icon={<BarChart3 size={14} />}
                        loading={loading}
                        badge={technical?.recommendation || undefined}
                        badgeColor={
                            technical?.recommendation === 'BUY' || technical?.recommendation === 'STRONG_BUY'
                                ? 'green'
                                : technical?.recommendation === 'SELL' || technical?.recommendation === 'STRONG_SELL'
                                  ? 'red'
                                  : 'amber'
                        }
                    >
                        {technical ? <KVGrid data={technical} max={12} /> : <div className="text-muted">No data</div>}
                    </Panel>

                    {/* 4. Financials */}
                    <Panel
                        panelId="sd-financials"
                        title="Financials"
                        icon={<DollarSign size={14} />}
                        loading={loading}
                        onOpenChange={onFinancialsChange}
                    >
                        {financials ? (
                            <KVGrid data={financials} max={16} />
                        ) : (
                            <div className="text-muted">No financial data</div>
                        )}
                    </Panel>

                    <SectionDivider label="Options & Derivatives" />
                    {/* 5. Options Flow */}
                    <Panel
                        panelId="sd-options-flow"
                        title="Options Flow"
                        icon={<Activity size={14} />}
                        loading={loading}
                        badge={flow.length ? `${flow.length}` : undefined}
                        onOpenChange={onOptionsChange}
                    >
                        {flow.length > 0 ? (
                            <div className="flow-table-wrapper">
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Type</th>
                                            <th>Strike</th>
                                            <th>Exp</th>
                                            <th>Premium</th>
                                            <th>Side</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {flow.slice(0, 15).map((f: any, i: number) => (
                                            <tr key={i}>
                                                <td>
                                                    <span
                                                        className={`badge badge-${
                                                            f.option_type === 'CALL' || f.type === 'CALL'
                                                                ? 'green'
                                                                : 'red'
                                                        }`}
                                                    >
                                                        {f.option_type || f.type || '—'}
                                                    </span>
                                                </td>
                                                <td>{formatCurrency(f.strike)}</td>
                                                <td>{f.expiration || f.exp || '—'}</td>
                                                <td>{formatCompact(f.premium || f.total_premium)}</td>
                                                <td>{f.side || f.trade_type || '—'}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <div className="text-muted">No flow data</div>
                        )}
                    </Panel>

                    {/* 6. IV Surface */}
                    <Panel
                        panelId="sd-implied-volatility"
                        title="Implied Volatility"
                        icon={<Gauge size={14} />}
                        loading={loading}
                    >
                        {iv ? <KVGrid data={iv} max={10} /> : <div className="text-muted">No IV data</div>}
                    </Panel>

                    {/* 7. Greek Exposure */}
                    <Panel
                        panelId="sd-greek-exposure"
                        title="Greek Exposure"
                        icon={<Shield size={14} />}
                        loading={loading}
                        defaultOpen={false}
                    >
                        {exposure ? (
                            <KVGrid data={exposure} max={12} />
                        ) : (
                            <div className="text-muted">No exposure data</div>
                        )}
                    </Panel>

                    {/* 7b. Options Analytics (Max Pain, PCR, IV Analysis) */}
                    <Panel
                        panelId="sd-options-analytics"
                        title="Options Analytics"
                        icon={<Crosshair size={14} />}
                        loading={loading}
                        badge={pcr?.sentiment ? pcr.sentiment.replace('_', ' ') : undefined}
                        badgeColor={
                            pcr?.sentiment === 'bullish' || pcr?.sentiment === 'slightly_bullish'
                                ? 'green'
                                : pcr?.sentiment === 'bearish' || pcr?.sentiment === 'slightly_bearish'
                                  ? 'red'
                                  : 'amber'
                        }
                    >
                        {maxPain || pcr || ivAnalysis || smartMoney || unusualInternal ? (
                            <div className="kv-grid">
                                {maxPain?.max_pain != null && (
                                    <>
                                        <div className="kv-item">
                                            <span className="kv-label">Max Pain</span>
                                            <span className="kv-value">{formatCurrency(maxPain.max_pain)}</span>
                                        </div>
                                        <div className="kv-item">
                                            <span className="kv-label">Distance</span>
                                            <span
                                                className={`kv-value ${maxPain.distance_pct > 0 ? 'text-green' : 'text-red'}`}
                                            >
                                                {maxPain.distance_pct > 0 ? '+' : ''}
                                                {maxPain.distance_pct}%
                                            </span>
                                        </div>
                                    </>
                                )}
                                {pcr && (
                                    <>
                                        <div className="kv-item">
                                            <span className="kv-label">P/C Vol Ratio</span>
                                            <span className="kv-value">{pcr.volume_ratio}</span>
                                        </div>
                                        <div className="kv-item">
                                            <span className="kv-label">P/C OI Ratio</span>
                                            <span className="kv-value">{pcr.oi_ratio}</span>
                                        </div>
                                    </>
                                )}
                                {ivAnalysis && (
                                    <>
                                        <div className="kv-item">
                                            <span className="kv-label">IV Rank</span>
                                            <span
                                                className={`kv-value ${
                                                    ivAnalysis.iv_rank > 80
                                                        ? 'text-red'
                                                        : ivAnalysis.iv_rank > 50
                                                          ? 'text-amber'
                                                          : 'text-green'
                                                }`}
                                            >
                                                {ivAnalysis.iv_rank}%
                                            </span>
                                        </div>
                                        <div className="kv-item">
                                            <span className="kv-label">IV Percentile</span>
                                            <span className="kv-value">{ivAnalysis.iv_percentile}%</span>
                                        </div>
                                        <div className="kv-item">
                                            <span className="kv-label">Current IV</span>
                                            <span className="kv-value">{formatPercent(ivAnalysis.current_iv)}</span>
                                        </div>
                                        {ivAnalysis.iv_skew?.label && (
                                            <div className="kv-item">
                                                <span className="kv-label">IV Skew</span>
                                                <span className="kv-value">
                                                    {ivAnalysis.iv_skew.label.replace(/_/g, ' ')}
                                                </span>
                                            </div>
                                        )}
                                        {/* ── IV Term Structure ── */}
                                        {ivAnalysis.term_structure?.classification && (
                                            <>
                                                <div
                                                    style={{
                                                        gridColumn: '1 / -1',
                                                        borderTop: '1px solid rgba(255,255,255,0.08)',
                                                        margin: '6px 0',
                                                        paddingTop: '8px',
                                                    }}
                                                >
                                                    <span
                                                        style={{
                                                            fontSize: '0.72rem',
                                                            fontWeight: 600,
                                                            textTransform: 'uppercase',
                                                            letterSpacing: '0.06em',
                                                            color: 'var(--text-secondary, #a0aec0)',
                                                        }}
                                                    >
                                                        Term Structure
                                                    </span>
                                                </div>
                                                <div className="kv-item">
                                                    <span className="kv-label">Curve</span>
                                                    <span
                                                        className={`kv-value ${
                                                            ivAnalysis.term_structure.classification === 'backwardation'
                                                                ? 'text-red'
                                                                : ivAnalysis.term_structure.classification ===
                                                                    'contango'
                                                                  ? 'text-green'
                                                                  : 'text-amber'
                                                        }`}
                                                    >
                                                        {ivAnalysis.term_structure.classification}
                                                    </span>
                                                </div>
                                                {ivAnalysis.term_structure.front_iv != null && (
                                                    <div className="kv-item">
                                                        <span className="kv-label">Front IV</span>
                                                        <span className="kv-value">
                                                            {formatPercent(ivAnalysis.term_structure.front_iv)}
                                                        </span>
                                                    </div>
                                                )}
                                                {ivAnalysis.term_structure.back_iv != null && (
                                                    <div className="kv-item">
                                                        <span className="kv-label">Back IV</span>
                                                        <span className="kv-value">
                                                            {formatPercent(ivAnalysis.term_structure.back_iv)}
                                                        </span>
                                                    </div>
                                                )}
                                                {/* Visual term structure chart */}
                                                {ivAnalysis.term_structure.points?.length > 1 &&
                                                    (() => {
                                                        const pts = ivAnalysis.term_structure.points;
                                                        const maxIV = Math.max(...pts.map((p: { iv: number }) => p.iv));
                                                        return (
                                                            <div style={{ gridColumn: '1 / -1', marginTop: '4px' }}>
                                                                <div
                                                                    style={{
                                                                        display: 'flex',
                                                                        alignItems: 'flex-end',
                                                                        gap: '3px',
                                                                        height: '48px',
                                                                    }}
                                                                >
                                                                    {pts.map(
                                                                        (
                                                                            p: {
                                                                                expiry: string;
                                                                                iv: number;
                                                                                days_to_expiry: number;
                                                                            },
                                                                            i: number,
                                                                        ) => (
                                                                            <div
                                                                                key={p.expiry}
                                                                                title={`${p.expiry}: ${(p.iv * 100).toFixed(1)}% (${p.days_to_expiry}d)`}
                                                                                style={{
                                                                                    flex: 1,
                                                                                    display: 'flex',
                                                                                    flexDirection: 'column',
                                                                                    alignItems: 'center',
                                                                                    gap: '2px',
                                                                                }}
                                                                            >
                                                                                <span
                                                                                    style={{
                                                                                        fontSize: '0.6rem',
                                                                                        color: 'var(--text-secondary, #a0aec0)',
                                                                                    }}
                                                                                >
                                                                                    {(p.iv * 100).toFixed(0)}%
                                                                                </span>
                                                                                <div
                                                                                    style={{
                                                                                        width: '100%',
                                                                                        maxWidth: '28px',
                                                                                        height: `${Math.max(6, (p.iv / maxIV) * 40)}px`,
                                                                                        borderRadius: '3px 3px 0 0',
                                                                                        background:
                                                                                            i === 0
                                                                                                ? 'var(--accent, #0ea5e9)'
                                                                                                : i === pts.length - 1
                                                                                                  ? 'var(--accent-vivid, #8b5cf6)'
                                                                                                  : 'rgba(255,255,255,0.15)',
                                                                                        transition: 'height 0.3s ease',
                                                                                    }}
                                                                                />
                                                                                <span
                                                                                    style={{
                                                                                        fontSize: '0.55rem',
                                                                                        color: 'var(--text-muted, #718096)',
                                                                                    }}
                                                                                >
                                                                                    {p.days_to_expiry}d
                                                                                </span>
                                                                            </div>
                                                                        ),
                                                                    )}
                                                                </div>
                                                            </div>
                                                        );
                                                    })()}
                                                {ivAnalysis.term_structure.interpretation && (
                                                    <div
                                                        style={{
                                                            gridColumn: '1 / -1',
                                                            fontSize: '0.7rem',
                                                            color: 'var(--text-secondary, #a0aec0)',
                                                            fontStyle: 'italic',
                                                            marginTop: '2px',
                                                        }}
                                                    >
                                                        {ivAnalysis.term_structure.interpretation}
                                                    </div>
                                                )}
                                            </>
                                        )}
                                    </>
                                )}
                                {smartMoney && (
                                    <>
                                        <div className="kv-item">
                                            <span className="kv-label">Smart Money</span>
                                            <span
                                                className={`kv-value ${
                                                    smartMoney.score >= 70
                                                        ? 'text-green'
                                                        : smartMoney.score >= 40
                                                          ? 'text-amber'
                                                          : 'text-red'
                                                }`}
                                            >
                                                {smartMoney.score}/100
                                            </span>
                                        </div>
                                        {smartMoney.positioning && (
                                            <div className="kv-item">
                                                <span className="kv-label">Positioning</span>
                                                <span className="kv-value">
                                                    {smartMoney.positioning.replace(/_/g, ' ')}
                                                </span>
                                            </div>
                                        )}
                                    </>
                                )}
                                {unusualInternal && Array.isArray(unusualInternal) && unusualInternal.length > 0 && (
                                    <div className="kv-item">
                                        <span className="kv-label">Unusual Contracts</span>
                                        <span className="kv-value" style={{ color: 'var(--accent-amber)' }}>
                                            {unusualInternal.length} flagged
                                        </span>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-muted">No options analytics data</div>
                        )}
                    </Panel>
                </div>

                {/* ── RIGHT COLUMN ── */}
                <div className="detail-col">
                    <SectionDivider label="Research & Analysis" />
                    {/* Questrade Intelligence */}
                    {enrichedQuote && (
                        <Panel
                            panelId="sd-questrade-intelligence"
                            title="Questrade Intelligence"
                            icon={<Zap size={14} />}
                            loading={loading}
                            badge={
                                enrichedQuote.isHalted
                                    ? 'HALTED'
                                    : enrichedQuote.institutional_flag
                                      ? 'INST'
                                      : undefined
                            }
                            badgeColor={enrichedQuote.isHalted ? 'red' : 'amber'}
                        >
                            <KVGrid
                                data={{
                                    VWAP: enrichedQuote.VWAP ? formatCurrency(enrichedQuote.VWAP) : '—',
                                    'Avg Trade Size': enrichedQuote.averageTradeSize ?? '—',
                                    Tick: enrichedQuote.tick ?? '—',
                                    'PE Ratio': enrichedQuote.pe?.toFixed(2) ?? '—',
                                    EPS: enrichedQuote.eps ? `$${enrichedQuote.eps.toFixed(2)}` : '—',
                                    Dividend: enrichedQuote.dividend ? `$${enrichedQuote.dividend.toFixed(2)}` : '—',
                                    Yield: enrichedQuote.yield_pct ? `${enrichedQuote.yield_pct.toFixed(2)}%` : '—',
                                    'Market Cap': enrichedQuote.marketCap
                                        ? formatCompact(enrichedQuote.marketCap)
                                        : '—',
                                    Sector: enrichedQuote.sector ?? '—',
                                    Industry: enrichedQuote.industry ?? '—',
                                    '52wk Position':
                                        enrichedQuote.position_52wk_pct != null
                                            ? `${enrichedQuote.position_52wk_pct.toFixed(1)}%`
                                            : '—',
                                    'Vol vs Avg':
                                        enrichedQuote.volume_vs_avg != null
                                            ? `${enrichedQuote.volume_vs_avg.toFixed(1)}x`
                                            : '—',
                                    Institutional: enrichedQuote.institutional_flag ? '✅ Detected' : '—',
                                }}
                                max={14}
                            />
                        </Panel>
                    )}

                    {/* TA Engine Indicators (25+ indicators) */}
                    <Panel
                        panelId="sd-ta-indicators"
                        title="TA Indicators"
                        icon={<Activity size={14} />}
                        loading={loading}
                        defaultOpen={false}
                        badge={taIndicators?.supertrend_direction ?? undefined}
                        badgeColor={
                            taIndicators?.supertrend_direction === 'up'
                                ? 'green'
                                : taIndicators?.supertrend_direction === 'down'
                                  ? 'red'
                                  : 'amber'
                        }
                    >
                        {taIndicators ? (
                            <div className="kv-grid">
                                {/* Trend */}
                                {taIndicators.sma_20 != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">SMA 20</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.sma_20)}</span>
                                    </div>
                                )}
                                {taIndicators.sma_50 != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">SMA 50</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.sma_50)}</span>
                                    </div>
                                )}
                                {taIndicators.sma_200 != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">SMA 200</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.sma_200)}</span>
                                    </div>
                                )}
                                {taIndicators.ema_8 != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">EMA 8</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.ema_8)}</span>
                                    </div>
                                )}
                                {taIndicators.ema_21 != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">EMA 21</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.ema_21)}</span>
                                    </div>
                                )}
                                {/* MACD */}
                                {taIndicators.macd_line != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">MACD</span>
                                        <span
                                            className={`kv-value ${taIndicators.macd_line > 0 ? 'text-green' : 'text-red'}`}
                                        >
                                            {taIndicators.macd_line.toFixed(3)}
                                        </span>
                                    </div>
                                )}
                                {taIndicators.macd_histogram != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">MACD Hist</span>
                                        <span
                                            className={`kv-value ${taIndicators.macd_histogram > 0 ? 'text-green' : 'text-red'}`}
                                        >
                                            {taIndicators.macd_histogram.toFixed(3)}
                                        </span>
                                    </div>
                                )}
                                {/* Momentum */}
                                {taIndicators.rsi_14 != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">RSI (14)</span>
                                        <span
                                            className={`kv-value ${taIndicators.rsi_14 > 70 ? 'text-red' : taIndicators.rsi_14 < 30 ? 'text-green' : ''}`}
                                        >
                                            {taIndicators.rsi_14.toFixed(1)}
                                        </span>
                                    </div>
                                )}
                                {taIndicators.stoch_k != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">Stoch %K</span>
                                        <span className="kv-value">{taIndicators.stoch_k.toFixed(1)}</span>
                                    </div>
                                )}
                                {taIndicators.williams_r != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">Williams %R</span>
                                        <span
                                            className={`kv-value ${taIndicators.williams_r > -20 ? 'text-red' : taIndicators.williams_r < -80 ? 'text-green' : ''}`}
                                        >
                                            {taIndicators.williams_r.toFixed(1)}
                                        </span>
                                    </div>
                                )}
                                {taIndicators.cci != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">CCI (20)</span>
                                        <span
                                            className={`kv-value ${taIndicators.cci > 100 ? 'text-red' : taIndicators.cci < -100 ? 'text-green' : ''}`}
                                        >
                                            {taIndicators.cci.toFixed(1)}
                                        </span>
                                    </div>
                                )}
                                {taIndicators.roc != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">ROC (12)</span>
                                        <span
                                            className={`kv-value ${taIndicators.roc > 0 ? 'text-green' : 'text-red'}`}
                                        >
                                            {taIndicators.roc.toFixed(2)}
                                        </span>
                                    </div>
                                )}
                                {taIndicators.tsi != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">TSI</span>
                                        <span
                                            className={`kv-value ${taIndicators.tsi > 0 ? 'text-green' : 'text-red'}`}
                                        >
                                            {taIndicators.tsi.toFixed(1)}
                                        </span>
                                    </div>
                                )}
                                {taIndicators.ultimate_oscillator != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">Ult Osc</span>
                                        <span className="kv-value">{taIndicators.ultimate_oscillator.toFixed(1)}</span>
                                    </div>
                                )}
                                {/* Volatility */}
                                {taIndicators.atr_14 != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">ATR (14)</span>
                                        <span className="kv-value">{taIndicators.atr_14.toFixed(2)}</span>
                                    </div>
                                )}
                                {taIndicators.bb_width != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">BB Width</span>
                                        <span className="kv-value">{taIndicators.bb_width.toFixed(4)}</span>
                                    </div>
                                )}
                                {taIndicators.keltner_upper != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">KC Upper</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.keltner_upper)}</span>
                                    </div>
                                )}
                                {taIndicators.keltner_lower != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">KC Lower</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.keltner_lower)}</span>
                                    </div>
                                )}
                                {taIndicators.donchian_upper != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">DC Upper</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.donchian_upper)}</span>
                                    </div>
                                )}
                                {taIndicators.donchian_lower != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">DC Lower</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.donchian_lower)}</span>
                                    </div>
                                )}
                                {/* Volume */}
                                {taIndicators.mfi != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">MFI (14)</span>
                                        <span
                                            className={`kv-value ${taIndicators.mfi > 80 ? 'text-red' : taIndicators.mfi < 20 ? 'text-green' : ''}`}
                                        >
                                            {taIndicators.mfi.toFixed(1)}
                                        </span>
                                    </div>
                                )}
                                {taIndicators.cmf != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">CMF (20)</span>
                                        <span
                                            className={`kv-value ${taIndicators.cmf > 0 ? 'text-green' : 'text-red'}`}
                                        >
                                            {taIndicators.cmf.toFixed(3)}
                                        </span>
                                    </div>
                                )}
                                {taIndicators.force_index != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">Force Idx</span>
                                        <span
                                            className={`kv-value ${taIndicators.force_index > 0 ? 'text-green' : 'text-red'}`}
                                        >
                                            {formatCompact(taIndicators.force_index)}
                                        </span>
                                    </div>
                                )}
                                {taIndicators.relative_volume != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">Rel Vol</span>
                                        <span
                                            className={`kv-value ${taIndicators.relative_volume > 1.5 ? 'text-amber' : ''}`}
                                        >
                                            {taIndicators.relative_volume.toFixed(2)}x
                                        </span>
                                    </div>
                                )}
                                {/* Overlays */}
                                {taIndicators.ichimoku_a != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">Ichi Span A</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.ichimoku_a)}</span>
                                    </div>
                                )}
                                {taIndicators.ichimoku_b != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">Ichi Span B</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.ichimoku_b)}</span>
                                    </div>
                                )}
                                {taIndicators.psar != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">PSAR</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.psar)}</span>
                                    </div>
                                )}
                                {taIndicators.supertrend != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">Supertrend</span>
                                        <span
                                            className={`kv-value ${taIndicators.supertrend_direction === 'up' ? 'text-green' : 'text-red'}`}
                                        >
                                            {formatCurrency(taIndicators.supertrend)} (
                                            {taIndicators.supertrend_direction})
                                        </span>
                                    </div>
                                )}
                                {/* Strength */}
                                {taIndicators.adx != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">ADX</span>
                                        <span className={`kv-value ${taIndicators.adx > 25 ? 'text-amber' : ''}`}>
                                            {taIndicators.adx.toFixed(1)}
                                        </span>
                                    </div>
                                )}
                                {taIndicators.aroon_up != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">Aroon ↑/↓</span>
                                        <span className="kv-value">
                                            {taIndicators.aroon_up.toFixed(0)}/
                                            {taIndicators.aroon_down?.toFixed(0) ?? '—'}
                                        </span>
                                    </div>
                                )}
                                {taIndicators.squeeze_on != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">Squeeze</span>
                                        <span
                                            className={`kv-value ${taIndicators.squeeze_on ? 'text-amber' : 'text-green'}`}
                                        >
                                            {taIndicators.squeeze_on ? '🔴 ON' : '⚪ OFF'}
                                        </span>
                                    </div>
                                )}
                                {/* Finta Unique Indicators */}
                                {taIndicators.kama != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">KAMA</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.kama)}</span>
                                    </div>
                                )}
                                {taIndicators.zlema != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">ZLEMA</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.zlema)}</span>
                                    </div>
                                )}
                                {taIndicators.hma != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">HMA</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.hma)}</span>
                                    </div>
                                )}
                                {taIndicators.frama != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">FRAMA</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.frama)}</span>
                                    </div>
                                )}
                                {taIndicators.ppo != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">PPO</span>
                                        <span
                                            className={`kv-value ${taIndicators.ppo > 0 ? 'text-green' : 'text-red'}`}
                                        >
                                            {taIndicators.ppo.toFixed(3)}
                                        </span>
                                    </div>
                                )}
                                {taIndicators.awesome_oscillator != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">Awesome Osc</span>
                                        <span
                                            className={`kv-value ${taIndicators.awesome_oscillator > 0 ? 'text-green' : 'text-red'}`}
                                        >
                                            {taIndicators.awesome_oscillator.toFixed(2)}
                                        </span>
                                    </div>
                                )}
                                {taIndicators.pivot != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">Pivot</span>
                                        <span className="kv-value">{formatCurrency(taIndicators.pivot)}</span>
                                    </div>
                                )}
                                {taIndicators.pivot_r1 != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">R1</span>
                                        <span className="kv-value text-red">
                                            {formatCurrency(taIndicators.pivot_r1)}
                                        </span>
                                    </div>
                                )}
                                {taIndicators.pivot_s1 != null && (
                                    <div className="kv-item">
                                        <span className="kv-label">S1</span>
                                        <span className="kv-value text-green">
                                            {formatCurrency(taIndicators.pivot_s1)}
                                        </span>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-muted">No indicator data</div>
                        )}
                    </Panel>

                    {/* Higher-Order Greeks (2nd/3rd order) */}
                    {higherGreeks && (
                        <Panel
                            panelId="sd-higher-greeks"
                            title="Higher Greeks"
                            icon={<TrendingUp size={14} />}
                            loading={loading}
                            defaultOpen={false}
                        >
                            <div className="kv-grid">
                                <div className="kv-item">
                                    <span className="kv-label">Charm (ΔDecay)</span>
                                    <span
                                        className={`kv-value ${(higherGreeks.charm ?? 0) < 0 ? 'text-red' : 'text-green'}`}
                                    >
                                        {higherGreeks.charm?.toFixed(6) ?? '—'}
                                    </span>
                                </div>
                                <div className="kv-item">
                                    <span className="kv-label">Vanna (Δ/σ)</span>
                                    <span
                                        className={`kv-value ${(higherGreeks.vanna ?? 0) > 0 ? 'text-green' : 'text-red'}`}
                                    >
                                        {higherGreeks.vanna?.toFixed(6) ?? '—'}
                                    </span>
                                </div>
                                <div className="kv-item">
                                    <span className="kv-label">Vomma (Volga)</span>
                                    <span className="kv-value">{higherGreeks.vomma?.toFixed(4) ?? '—'}</span>
                                </div>
                                <div className="kv-item">
                                    <span className="kv-label">Veta (ν/T)</span>
                                    <span className="kv-value">{higherGreeks.veta?.toFixed(4) ?? '—'}</span>
                                </div>
                                <div className="kv-item">
                                    <span className="kv-label">Color (Γ/T)</span>
                                    <span className="kv-value">{higherGreeks.color?.toFixed(8) ?? '—'}</span>
                                </div>
                                <div className="kv-item">
                                    <span className="kv-label">Speed (Γ/S)</span>
                                    <span className="kv-value">{higherGreeks.speed?.toFixed(8) ?? '—'}</span>
                                </div>
                                <div className="kv-item">
                                    <span className="kv-label">Ultima</span>
                                    <span className="kv-value">{higherGreeks.ultima?.toFixed(4) ?? '—'}</span>
                                </div>
                                <div className="kv-item">
                                    <span className="kv-label">Zomma (Γ/σ)</span>
                                    <span className="kv-value">{higherGreeks.zomma?.toFixed(6) ?? '—'}</span>
                                </div>
                            </div>
                        </Panel>
                    )}

                    <SectionDivider label="Sentiment & Social" />
                    {/* 8. News */}
                    <Panel
                        panelId="sd-news-feed"
                        title="News Feed"
                        icon={<Newspaper size={14} />}
                        loading={loading}
                        badge={news.length ? `${news.length}` : undefined}
                    >
                        {news.length > 0 ? (
                            <div className="news-list">
                                {news.slice(0, 10).map((n: any, i: number) => (
                                    <a
                                        key={i}
                                        className="news-item"
                                        href={n.url || '#'}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                    >
                                        <div className="news-headline">{n.headline || n.title || ''}</div>
                                        <div className="news-meta">
                                            <span>{n.source || ''}</span>
                                            <span>{timeAgo(n.datetime || n.date || n.published_at || '')}</span>
                                            <ExternalLink size={12} />
                                        </div>
                                    </a>
                                ))}
                            </div>
                        ) : (
                            <div className="text-muted">No news</div>
                        )}
                    </Panel>

                    {/* 9. Sentiment */}
                    <Panel panelId="sd-sentiment" title="Sentiment" icon={<Gauge size={14} />} loading={loading}>
                        {sentiment ? (
                            <KVGrid data={sentiment} max={8} />
                        ) : (
                            <div className="text-muted">No sentiment data</div>
                        )}
                    </Panel>

                    <SectionDivider label="Research & Fundamentals" />
                    {/* 10. SEC Filings */}
                    <Panel
                        panelId="sd-sec-filings"
                        title="SEC Filings"
                        icon={<FileText size={14} />}
                        loading={loading}
                        defaultOpen={false}
                    >
                        {filings.length > 0 ? (
                            <div className="filings-list">
                                {filings.slice(0, 10).map((f: any, i: number) => (
                                    <a
                                        key={i}
                                        className="filing-item"
                                        href={f.url || f.link || '#'}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                    >
                                        <span className="badge badge-amber">{f.form_type || f.type || '—'}</span>
                                        <span className="filing-date">{formatDate(f.filed_date || f.date || '')}</span>
                                        <span className="filing-desc">{f.description || f.title || ''}</span>
                                        <ExternalLink size={12} />
                                    </a>
                                ))}
                            </div>
                        ) : (
                            <div className="text-muted">No filings</div>
                        )}
                    </Panel>

                    {/* 11. Insider Trades */}
                    <Panel
                        panelId="sd-insider-trades"
                        title="Insider Trades"
                        icon={<Users size={14} />}
                        loading={loading}
                        defaultOpen={false}
                    >
                        {insider.length > 0 ? (
                            <div className="flow-table-wrapper">
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Name</th>
                                            <th>Type</th>
                                            <th>Shares</th>
                                            <th>Value</th>
                                            <th>Date</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {insider.slice(0, 10).map((t: any, i: number) => (
                                            <tr key={i}>
                                                <td>{t.name || t.insider_name || '—'}</td>
                                                <td>
                                                    <span
                                                        className={`badge badge-${
                                                            (t.transaction_type || t.type || '')
                                                                .toLowerCase()
                                                                .includes('buy')
                                                                ? 'green'
                                                                : 'red'
                                                        }`}
                                                    >
                                                        {t.transaction_type || t.type || '—'}
                                                    </span>
                                                </td>
                                                <td>{formatCompact(t.shares || t.quantity)}</td>
                                                <td>{formatCurrency(t.value || t.total_value)}</td>
                                                <td>{formatDate(t.date || t.filing_date || '')}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <div className="text-muted">No insider trades</div>
                        )}
                    </Panel>

                    {/* 12. Analyst Ratings */}
                    <Panel
                        panelId="sd-analyst-ratings"
                        title="Analyst Ratings"
                        icon={<Target size={14} />}
                        loading={loading}
                    >
                        {analyst ? (
                            <KVGrid data={analyst} max={10} />
                        ) : (
                            <div className="text-muted">No analyst data</div>
                        )}
                    </Panel>

                    {/* 14. External Links */}
                    <Panel
                        panelId="sd-quick-links"
                        title="Quick Links"
                        icon={<Link2 size={14} />}
                        loading={loading}
                        defaultOpen={false}
                    >
                        {links ? (
                            <div className="links-grid">
                                {Object.entries(links).map(([name, url]) => (
                                    <a
                                        key={name}
                                        className="link-chip"
                                        href={url as string}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                    >
                                        {name.replace(/_/g, ' ')} <ExternalLink size={12} />
                                    </a>
                                ))}
                            </div>
                        ) : (
                            <div className="text-muted">No links</div>
                        )}
                    </Panel>

                    {/* 15. Institutional Ownership (OpenBB) */}
                    <Panel
                        panelId="sd-institutional-ownership"
                        title="Institutional Ownership"
                        icon={<Briefcase size={14} />}
                        loading={loading}
                        defaultOpen={false}
                        badge={institutional?.holders?.length ? `${institutional.holders.length} holders` : undefined}
                        badgeColor="blue"
                    >
                        {institutional?.holders?.length ? (
                            <div className="institutional-panel">
                                <div className="kv-grid" style={{ marginBottom: 12 }}>
                                    <div className="kv-item">
                                        <span className="kv-label">Total Holders Found</span>
                                        <span className="kv-value">{institutional.total_count}</span>
                                    </div>
                                    <div className="kv-item">
                                        <span className="kv-label">Source</span>
                                        <span className="kv-value">{institutional.source}</span>
                                    </div>
                                </div>
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Institution</th>
                                            <th style={{ textAlign: 'right' }}>Shares</th>
                                            <th style={{ textAlign: 'right' }}>Value</th>
                                            <th style={{ textAlign: 'right' }}>Weight %</th>
                                            <th style={{ textAlign: 'right' }}>Change</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {institutional.holders.map((h: any, i: number) => (
                                            <tr key={i}>
                                                <td style={{ fontWeight: 500 }}>{h.name}</td>
                                                <td style={{ textAlign: 'right' }}>
                                                    {h.shares ? formatCompact(h.shares) : '—'}
                                                </td>
                                                <td style={{ textAlign: 'right' }}>
                                                    {h.value ? formatCurrency(h.value) : '—'}
                                                </td>
                                                <td style={{ textAlign: 'right' }}>
                                                    {h.weight_pct != null ? formatPercent(h.weight_pct / 100) : '—'}
                                                </td>
                                                <td
                                                    style={{ textAlign: 'right' }}
                                                    className={
                                                        h.change_pct > 0
                                                            ? 'text-green'
                                                            : h.change_pct < 0
                                                              ? 'text-red'
                                                              : ''
                                                    }
                                                >
                                                    {h.change_pct != null
                                                        ? `${h.change_pct > 0 ? '+' : ''}${h.change_pct.toFixed(1)}%`
                                                        : '—'}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <div className="text-muted">No institutional ownership data available</div>
                        )}
                    </Panel>

                    {/* 16. Dividend History (OpenBB) */}
                    <Panel
                        panelId="sd-dividend-history"
                        title="Dividend History"
                        icon={<DollarSign size={14} />}
                        loading={loading}
                        defaultOpen={false}
                        badge={
                            obDividends?.trailing_annual_dividend
                                ? `$${obDividends.trailing_annual_dividend}/yr`
                                : undefined
                        }
                        badgeColor="green"
                    >
                        {obDividends?.dividends?.length ? (
                            <div className="dividend-panel">
                                <div className="kv-grid" style={{ marginBottom: 12 }}>
                                    <div className="kv-item">
                                        <span className="kv-label">Trailing Annual Div</span>
                                        <span className="kv-value text-green">
                                            ${obDividends.trailing_annual_dividend}
                                        </span>
                                    </div>
                                    <div className="kv-item">
                                        <span className="kv-label">Last Dividend</span>
                                        <span className="kv-value">${obDividends.last_dividend}</span>
                                    </div>
                                    <div className="kv-item">
                                        <span className="kv-label">Total Records</span>
                                        <span className="kv-value">{obDividends.total_records}</span>
                                    </div>
                                </div>
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Ex-Date</th>
                                            <th>Pay Date</th>
                                            <th style={{ textAlign: 'right' }}>Amount</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {obDividends.dividends.map((d: any, i: number) => (
                                            <tr key={i}>
                                                <td>{d.ex_date ? formatDate(new Date(d.ex_date)) : '—'}</td>
                                                <td>{d.pay_date ? formatDate(new Date(d.pay_date)) : '—'}</td>
                                                <td style={{ textAlign: 'right', color: 'var(--color-green)' }}>
                                                    ${d.amount.toFixed(4)}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <div className="text-muted">No dividend history available</div>
                        )}
                    </Panel>

                    {/* 17. Economic Calendar (OpenBB) */}
                    <Panel
                        panelId="sd-economic-calendar"
                        title="Economic Calendar"
                        icon={<Calendar size={14} />}
                        loading={!ecoCalendar}
                        defaultOpen={false}
                        badge={ecoCalendar?.events?.length ? `${ecoCalendar.events.length} events` : undefined}
                        badgeColor="amber"
                    >
                        {ecoCalendar?.events?.length ? (
                            <div className="eco-calendar-panel">
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Date</th>
                                            <th>Event</th>
                                            <th style={{ textAlign: 'center' }}>Imp.</th>
                                            <th style={{ textAlign: 'right' }}>Forecast</th>
                                            <th style={{ textAlign: 'right' }}>Previous</th>
                                            <th style={{ textAlign: 'right' }}>Actual</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {ecoCalendar.events.map((ev: any, i: number) => (
                                            <tr key={i}>
                                                <td style={{ whiteSpace: 'nowrap' }}>
                                                    {ev.date ? formatDate(new Date(ev.date)) : '—'}
                                                </td>
                                                <td
                                                    style={{
                                                        fontWeight: 500,
                                                        maxWidth: 260,
                                                        overflow: 'hidden',
                                                        textOverflow: 'ellipsis',
                                                    }}
                                                >
                                                    {ev.event}
                                                </td>
                                                <td style={{ textAlign: 'center' }}>
                                                    <span
                                                        style={{
                                                            display: 'inline-block',
                                                            width: 10,
                                                            height: 10,
                                                            borderRadius: '50%',
                                                            backgroundColor:
                                                                ev.importance === 'high'
                                                                    ? 'var(--color-red)'
                                                                    : ev.importance === 'medium'
                                                                      ? 'var(--color-amber)'
                                                                      : 'var(--color-green)',
                                                        }}
                                                        title={ev.importance}
                                                    />
                                                </td>
                                                <td style={{ textAlign: 'right' }}>
                                                    {ev.forecast != null ? ev.forecast : '—'}
                                                </td>
                                                <td style={{ textAlign: 'right' }}>
                                                    {ev.previous != null ? ev.previous : '—'}
                                                </td>
                                                <td
                                                    style={{
                                                        textAlign: 'right',
                                                        fontWeight: ev.actual != null ? 600 : 400,
                                                    }}
                                                >
                                                    {ev.actual != null ? ev.actual : '—'}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <div className="text-muted">No upcoming economic events</div>
                        )}
                    </Panel>

                    {/* 18. World News Wire (OpenBB — Bloomberg-style) */}
                    <Panel
                        panelId="sd-market-news-wire"
                        title="Market News Wire"
                        icon={<Globe size={14} />}
                        loading={!worldNews}
                        defaultOpen={false}
                        badge={worldNews?.articles?.length ? `${worldNews.articles.length} articles` : undefined}
                        badgeColor="blue"
                    >
                        {worldNews?.articles?.length ? (
                            <div
                                className="news-wire-panel"
                                style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
                            >
                                {worldNews.articles.slice(0, 20).map((article: any, i: number) => (
                                    <div
                                        key={i}
                                        style={{
                                            padding: '10px 14px',
                                            borderRadius: 8,
                                            background: 'var(--glass-bg, rgba(255,255,255,0.04))',
                                            border: '1px solid var(--glass-border, rgba(255,255,255,0.08))',
                                        }}
                                    >
                                        <div
                                            style={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'flex-start',
                                                gap: 12,
                                            }}
                                        >
                                            <div style={{ flex: 1 }}>
                                                <a
                                                    href={article.url}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    style={{
                                                        color: 'var(--text-primary)',
                                                        fontWeight: 600,
                                                        fontSize: '0.9rem',
                                                        textDecoration: 'none',
                                                    }}
                                                >
                                                    {article.title}
                                                </a>
                                                {article.summary && (
                                                    <p
                                                        style={{
                                                            color: 'var(--text-muted)',
                                                            fontSize: '0.8rem',
                                                            margin: '4px 0 0',
                                                            lineHeight: 1.4,
                                                            display: '-webkit-box',
                                                            WebkitLineClamp: 2,
                                                            WebkitBoxOrient: 'vertical',
                                                            overflow: 'hidden',
                                                        }}
                                                    >
                                                        {article.summary}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                        <div
                                            style={{
                                                display: 'flex',
                                                gap: 12,
                                                marginTop: 6,
                                                fontSize: '0.75rem',
                                                color: 'var(--text-muted)',
                                            }}
                                        >
                                            {article.source && (
                                                <span style={{ color: 'var(--color-blue)' }}>{article.source}</span>
                                            )}
                                            {article.published && <span>{timeAgo(new Date(article.published))}</span>}
                                            {article.symbols?.length > 0 && (
                                                <span style={{ color: 'var(--color-amber)' }}>
                                                    {article.symbols.slice(0, 5).join(', ')}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                ))}
                                {worldNews.provider && (
                                    <div
                                        style={{
                                            fontSize: '0.7rem',
                                            color: 'var(--text-muted)',
                                            textAlign: 'right',
                                            paddingTop: 4,
                                        }}
                                    >
                                        via {worldNews.provider} • OpenBB
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-muted">
                                No global news available — check OpenBB provider configuration
                            </div>
                        )}
                    </Panel>
                </div>
            </div>

            {/* ── 15. Breakout Analysis (full width) ── */}
            <div className="breakout-section">
                <h2 className="section-title">
                    <Zap size={16} /> Breakout Analysis
                    {breakout && (
                        <span
                            className={`badge badge-${
                                breakout.conviction_score >= 75
                                    ? 'green'
                                    : breakout.conviction_score >= 50
                                      ? 'amber'
                                      : 'red'
                            }`}
                            style={{ marginLeft: 8 }}
                        >
                            {breakout.recommendation?.action || breakout.stage}
                        </span>
                    )}
                </h2>

                {/* Loading skeleton */}
                {breakoutLoading && !breakout && (
                    <div className="breakout-grid">
                        <div className="card breakout-gauge-card">
                            <div className="skeleton skeleton-circle" style={{ width: 140, height: 140 }} />
                            <div className="skeleton" style={{ width: 100, height: 22, borderRadius: 12 }} />
                        </div>
                        <div className="card" style={{ padding: 20 }}>
                            {[...Array(6)].map((_, i) => (
                                <div
                                    key={i}
                                    className="skeleton"
                                    style={{ height: 14, marginBottom: 12, width: `${80 - i * 8}%` }}
                                />
                            ))}
                        </div>
                        <div className="card" style={{ padding: 20 }}>
                            <div className="skeleton" style={{ height: 18, width: '40%', marginBottom: 16 }} />
                            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                {[...Array(5)].map((_, i) => (
                                    <div
                                        key={i}
                                        className="skeleton"
                                        style={{ width: 52, height: 26, borderRadius: 100 }}
                                    />
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {/* Error state */}
                {breakoutError && !breakout && (
                    <div className="breakout-error">
                        <AlertTriangle size={20} />
                        <span>Breakout analysis unavailable</span>
                        <button
                            type="button"
                            className="btn btn-ghost"
                            onClick={() => {
                                // Assuming `queryClient` and `ticker` are available in this scope.
                                // If not, you would need to add `import { useQueryClient } from '@tanstack/react-query';`
                                // and `const queryClient = useQueryClient();` at the top of your component function.
                                queryClient.refetchQueries({ queryKey: ['stock', ticker, 'breakout'] });
                            }}
                        >
                            Retry
                        </button>
                    </div>
                )}

                {breakout && (
                    <>
                        {/* Failed Breakout Warning */}
                        {breakout.failed_breakout && (
                            <div className="breakout-alert breakout-alert-danger">
                                <AlertTriangle size={16} />
                                <div>
                                    <strong>Failed Breakout Detected</strong>
                                    <div className="breakout-alert-detail">
                                        {breakout.failed_breakout.action} — Vol ratio:{' '}
                                        {breakout.failed_breakout.volume_ratio}x
                                        {breakout.failed_breakout.severity === 'high' && ' (HIGH SEVERITY)'}
                                    </div>
                                </div>
                            </div>
                        )}

                        <div className="breakout-grid">
                            {/* Conviction Gauge */}
                            <div
                                className={`card breakout-gauge-card ${breakout.conviction_score >= 75 ? 'gauge-glow-green' : breakout.conviction_score >= 50 ? 'gauge-glow-amber' : ''}`}
                            >
                                <div className="breakout-gauge">
                                    <svg
                                        viewBox="0 0 120 120"
                                        className="gauge-svg"
                                        aria-labelledby="conviction-gauge-title"
                                    >
                                        \r
                                        <title id="conviction-gauge-title">Conviction score gauge</title>
                                        <circle
                                            cx="60"
                                            cy="60"
                                            r="52"
                                            fill="none"
                                            stroke="hsla(0 0% 100% / 0.06)"
                                            strokeWidth="8"
                                        />
                                        <circle
                                            cx="60"
                                            cy="60"
                                            r="52"
                                            fill="none"
                                            stroke={
                                                breakout.conviction_score >= 75
                                                    ? 'var(--accent-green)'
                                                    : breakout.conviction_score >= 50
                                                      ? 'var(--accent-amber)'
                                                      : 'var(--accent-red)'
                                            }
                                            strokeWidth="8"
                                            strokeLinecap="round"
                                            strokeDasharray={`${(breakout.conviction_score / 100) * 327} 327`}
                                            transform="rotate(-90 60 60)"
                                            style={{ transition: 'stroke-dasharray 0.6s ease' }}
                                        />
                                        <text
                                            x="60"
                                            y="55"
                                            textAnchor="middle"
                                            fill="var(--text-primary)"
                                            fontSize="28"
                                            fontWeight="700"
                                            fontFamily="var(--font-mono)"
                                        >
                                            {breakout.conviction_score}
                                        </text>
                                        <text
                                            x="60"
                                            y="72"
                                            textAnchor="middle"
                                            fill="var(--text-muted)"
                                            fontSize="10"
                                            fontWeight="500"
                                        >
                                            CONVICTION
                                        </text>
                                    </svg>
                                </div>
                                <div className="breakout-stage">
                                    <span className="breakout-stage-label">Stage</span>
                                    <span
                                        className={`badge badge-${
                                            breakout.stage === 'breakout' || breakout.stage === 'confirmation'
                                                ? 'green'
                                                : breakout.stage === 'pre_breakout'
                                                  ? 'amber'
                                                  : 'blue'
                                        }`}
                                    >
                                        {(breakout.stage || '').replace(/_/g, ' ').toUpperCase()}
                                    </span>
                                </div>
                                {breakout.breakout_level && (
                                    <div className="breakout-level">
                                        <span className="kv-label">Breakout Level</span>
                                        <span className="kv-value">{formatCurrency(breakout.breakout_level)}</span>
                                    </div>
                                )}
                                {breakout.historical_win_rate != null && (
                                    <div className="breakout-level">
                                        <span className="kv-label">Historical Win Rate</span>
                                        <span className="kv-value">{breakout.historical_win_rate}%</span>
                                    </div>
                                )}
                            </div>

                            {/* Scoring Breakdown */}
                            <div className="card breakout-scoring-card">
                                <div className="card-header">
                                    <span className="card-title">Scoring Breakdown</span>
                                </div>
                                <div className="scoring-bars">
                                    {breakout.scoring &&
                                        Object.entries(breakout.scoring).map(
                                            ([key, val]: [string, any], idx: number) => {
                                                const maxMap: Record<string, number> = {
                                                    volume: 20,
                                                    pattern: 15,
                                                    trend: 10,
                                                    multi_tf: 15,
                                                    options: 15,
                                                    candle: 10,
                                                    institutional: 10,
                                                    sector: 5,
                                                };
                                                const max = maxMap[key] || 20;
                                                const pct = Math.min((val / max) * 100, 100);
                                                return (
                                                    <div
                                                        key={key}
                                                        className="score-bar-row score-bar-animate"
                                                        style={{ animationDelay: `${idx * 60}ms` }}
                                                    >
                                                        <span className="score-bar-label">
                                                            {key.replace(/_/g, ' ')}
                                                        </span>
                                                        <div className="score-bar-track">
                                                            <div
                                                                className="score-bar-fill"
                                                                style={{
                                                                    width: `${pct}%`,
                                                                    background:
                                                                        pct >= 80
                                                                            ? 'var(--accent-green)'
                                                                            : pct >= 50
                                                                              ? 'var(--accent-amber)'
                                                                              : 'var(--accent-blue)',
                                                                }}
                                                            />
                                                        </div>
                                                        <span className="score-bar-value">
                                                            {val}/{max}
                                                        </span>
                                                    </div>
                                                );
                                            },
                                        )}
                                </div>
                            </div>

                            {/* Precursors + Signals */}
                            <div className="card breakout-signals-card">
                                <div className="card-header">
                                    <span className="card-title">
                                        Precursors
                                        <span className="badge badge-blue" style={{ marginLeft: 8 }}>
                                            {breakout.precursor_count || 0}/15
                                        </span>
                                    </span>
                                </div>
                                <div className="precursor-chips">
                                    {(breakout.precursors || []).map((p: any, idx: number) => (
                                        <span
                                            key={p.id}
                                            className="precursor-chip precursor-chip-animate"
                                            style={{ animationDelay: `${idx * 40}ms` }}
                                            title={p.description}
                                        >
                                            {p.id}
                                        </span>
                                    ))}
                                    {(!breakout.precursors || breakout.precursors.length === 0) && (
                                        <span className="text-muted" style={{ fontSize: 13 }}>
                                            No active precursors
                                        </span>
                                    )}
                                </div>

                                {/* Options Confirmation */}
                                {breakout.options_confirmation && (
                                    <div className="breakout-sub-signal">
                                        <div className="breakout-sub-title">Options Confirmation</div>
                                        <div className="breakout-sub-row">
                                            <span
                                                className={`badge badge-${
                                                    breakout.options_confirmation.verdict === 'STRONGLY_CONFIRMED'
                                                        ? 'green'
                                                        : breakout.options_confirmation.verdict === 'CONFIRMED'
                                                          ? 'amber'
                                                          : 'red'
                                                }`}
                                            >
                                                {breakout.options_confirmation.verdict}
                                            </span>
                                            <span className="score-bar-value">
                                                {breakout.options_confirmation.confirmation_score}/100
                                            </span>
                                        </div>
                                        {breakout.options_confirmation.risk_flags?.length > 0 && (
                                            <div className="breakout-risk-flags">
                                                {breakout.options_confirmation.risk_flags.map(
                                                    (f: string, i: number) => (
                                                        <div key={i} className="risk-flag">
                                                            ⚠ {f}
                                                        </div>
                                                    ),
                                                )}
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Institutional Activity */}
                                {breakout.institutional_activity &&
                                    breakout.institutional_activity.signal_count > 0 && (
                                        <div className="breakout-sub-signal">
                                            <div className="breakout-sub-title">Institutional Activity</div>
                                            <div className="breakout-sub-row">
                                                <span
                                                    className={`badge badge-${
                                                        breakout.institutional_activity.intent?.includes('strong')
                                                            ? 'green'
                                                            : breakout.institutional_activity.intent === 'accumulation'
                                                              ? 'amber'
                                                              : 'blue'
                                                    }`}
                                                >
                                                    {(breakout.institutional_activity.intent || '')
                                                        .replace(/_/g, ' ')
                                                        .toUpperCase()}
                                                </span>
                                                <span className="score-bar-value">
                                                    Score: {breakout.institutional_activity.institutional_score}/100
                                                </span>
                                            </div>
                                        </div>
                                    )}
                            </div>
                        </div>

                        {/* Recommendation */}
                        {breakout.recommendation && (
                            <div
                                className={`breakout-recommendation breakout-rec-${
                                    breakout.recommendation.action === 'BUY'
                                        ? 'buy'
                                        : breakout.recommendation.action === 'EXIT/REDUCE'
                                          ? 'exit'
                                          : breakout.recommendation.action === 'WATCHLIST'
                                            ? 'watch'
                                            : 'pass'
                                }`}
                            >
                                <div className="breakout-rec-action">{breakout.recommendation.action}</div>
                                <div className="breakout-rec-reason">{breakout.recommendation.reason}</div>
                                {breakout.recommendation.entry && (
                                    <div className="breakout-rec-levels">
                                        Entry: {formatCurrency(breakout.recommendation.entry)}
                                        {breakout.recommendation.stop && (
                                            <> · Stop: {formatCurrency(breakout.recommendation.stop)}</>
                                        )}
                                        {breakout.recommendation.target && (
                                            <> · Target: {formatCurrency(breakout.recommendation.target)}</>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* ── 16. Fundamentals & Targets ── */}
            <Panel
                panelId="sd-fundamentals-targets"
                title="Fundamentals & Targets"
                icon={<Target size={16} />}
                loading={loading}
            >
                {priceTarget && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Price Target Consensus</h4>
                        <div className="pt-grid">
                            {['targetLow', 'targetMedian', 'targetMean', 'targetHigh'].map((k) => {
                                const val = priceTarget[k] ?? priceTarget[k.replace('target', 'target_')];
                                const label = k.replace('target', '').toLowerCase();
                                return val != null ? (
                                    <div key={k} className="pt-card">
                                        <div className="pt-label">{label}</div>
                                        <div className="pt-value">{formatCurrency(val)}</div>
                                    </div>
                                ) : null;
                            })}
                        </div>
                    </div>
                )}
                {earningsEst && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Earnings Estimates</h4>
                        <KVGrid data={typeof earningsEst === 'object' ? earningsEst : {}} max={8} />
                    </div>
                )}
                {fundamentals && typeof fundamentals === 'object' && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Key Metrics</h4>
                        <KVGrid data={fundamentals?.metric || fundamentals} max={12} />
                    </div>
                )}
                {insiderSent && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Insider Sentiment (MSPR)</h4>
                        <KVGrid data={typeof insiderSent === 'object' ? insiderSent : {}} max={6} />
                    </div>
                )}
                {corpActions.length > 0 && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Corporate Actions</h4>
                        <div className="corp-actions-list">
                            {corpActions.slice(0, 6).map((ca: any, i: number) => (
                                <div key={i} className="corp-action-chip">
                                    <span
                                        className={`badge badge-${ca.type === 'dividend' ? 'green' : ca.type === 'split' ? 'blue' : 'amber'}`}
                                    >
                                        {ca.type || 'action'}
                                    </span>
                                    <span>
                                        {ca.description ||
                                            ca.summary ||
                                            `${ca.type} — ${formatDate(ca.date || ca.ex_date || '')}`}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
                {!priceTarget &&
                    !earningsEst &&
                    !fundamentals &&
                    !insiderSent &&
                    corpActions.length === 0 &&
                    !multiYearFin &&
                    !quarterlyFin &&
                    !earningsTranscript && <div className="text-muted">No fundamental data available</div>}
                {multiYearFin && typeof multiYearFin === 'object' && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Multi-Year Financials (Annual)</h4>
                        <div className="fin-table-wrap">
                            <table className="fin-table">
                                <thead>
                                    <tr>
                                        <th>Year</th>
                                        {Object.keys(multiYearFin.years?.[0] || multiYearFin[0] || {})
                                            .filter((k) => k !== 'year' && k !== 'period')
                                            .slice(0, 5)
                                            .map((k) => (
                                                <th key={k}>{k.replace(/_/g, ' ')}</th>
                                            ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {(multiYearFin.years || (Array.isArray(multiYearFin) ? multiYearFin : []))
                                        .slice(0, 5)
                                        .map((row: any, i: number) => (
                                            <tr key={i}>
                                                <td className="fin-period">{row.year || row.period || `Y${i + 1}`}</td>
                                                {Object.entries(row)
                                                    .filter(([k]) => k !== 'year' && k !== 'period')
                                                    .slice(0, 5)
                                                    .map(([k, v]: [string, any]) => (
                                                        <td key={k} className="fin-num">
                                                            {typeof v === 'number'
                                                                ? Math.abs(v) > 1000
                                                                    ? formatCompact(v)
                                                                    : v.toFixed(2)
                                                                : String(v ?? '—')}
                                                        </td>
                                                    ))}
                                            </tr>
                                        ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
                {quarterlyFin && typeof quarterlyFin === 'object' && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Quarterly Financials</h4>
                        <div className="fin-table-wrap">
                            <table className="fin-table">
                                <thead>
                                    <tr>
                                        <th>Quarter</th>
                                        {Object.keys(quarterlyFin.quarters?.[0] || quarterlyFin[0] || {})
                                            .filter((k) => k !== 'quarter' && k !== 'period')
                                            .slice(0, 5)
                                            .map((k) => (
                                                <th key={k}>{k.replace(/_/g, ' ')}</th>
                                            ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {(quarterlyFin.quarters || (Array.isArray(quarterlyFin) ? quarterlyFin : []))
                                        .slice(0, 8)
                                        .map((row: any, i: number) => (
                                            <tr key={i}>
                                                <td className="fin-period">
                                                    {row.quarter || row.period || `Q${i + 1}`}
                                                </td>
                                                {Object.entries(row)
                                                    .filter(([k]) => k !== 'quarter' && k !== 'period')
                                                    .slice(0, 5)
                                                    .map(([k, v]: [string, any]) => (
                                                        <td key={k} className="fin-num">
                                                            {typeof v === 'number'
                                                                ? Math.abs(v) > 1000
                                                                    ? formatCompact(v)
                                                                    : v.toFixed(2)
                                                                : String(v ?? '—')}
                                                        </td>
                                                    ))}
                                            </tr>
                                        ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
                {earningsTranscript && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Earnings Transcript</h4>
                        <div className="transcript-preview">
                            {typeof earningsTranscript === 'string' ? (
                                earningsTranscript.slice(0, 600) + (earningsTranscript.length > 600 ? '…' : '')
                            ) : earningsTranscript.transcript ? (
                                `${String(earningsTranscript.transcript).slice(0, 600)}…`
                            ) : (
                                <KVGrid data={earningsTranscript} max={6} />
                            )}
                        </div>
                    </div>
                )}
                {wsbDD.length > 0 && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">WSB Due Diligence</h4>
                        <div className="dd-list">
                            {wsbDD.slice(0, 8).map((post: any, i: number) => (
                                <a
                                    key={i}
                                    href={post.url || post.permalink || '#'}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="dd-item"
                                >
                                    <span className="dd-title">{post.title || 'DD Post'}</span>
                                    <span className="dd-meta">
                                        {post.score != null && <span>↑{post.score}</span>}
                                        {post.num_comments != null && <span>{post.num_comments} comments</span>}
                                        {post.created_utc && (
                                            <span>{timeAgo(new Date(post.created_utc * 1000).toISOString())}</span>
                                        )}
                                    </span>
                                </a>
                            ))}
                        </div>
                    </div>
                )}
            </Panel>

            {/* ── 17. Pattern Analysis ── */}
            <Panel
                panelId="sd-pattern-analysis"
                title="Pattern Analysis"
                icon={<Crosshair size={16} />}
                loading={loading}
                badge={patterns?.summary?.total_patterns != null ? String(patterns.summary.total_patterns) : undefined}
                badgeColor="purple"
            >
                {patterns && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Active Patterns</h4>
                        <div className="pattern-chips">
                            {(patterns.candlestick_patterns || []).slice(0, 8).map((p: any, i: number) => (
                                <span
                                    key={`c${i}`}
                                    className={`pattern-chip ${p.direction === 'bullish' ? 'bullish' : p.direction === 'bearish' ? 'bearish' : ''}`}
                                >
                                    {p.name || p.pattern || 'pattern'}
                                </span>
                            ))}
                            {(patterns.chart_patterns || []).slice(0, 6).map((p: any, i: number) => (
                                <span
                                    key={`ch${i}`}
                                    className={`pattern-chip ${p.direction === 'bullish' ? 'bullish' : p.direction === 'bearish' ? 'bearish' : ''}`}
                                >
                                    {p.name || p.pattern || 'chart'}
                                </span>
                            ))}
                            {(patterns.volume_patterns || []).slice(0, 4).map((p: any, i: number) => (
                                <span key={`v${i}`} className="pattern-chip">
                                    {p.name || p.pattern || 'volume'}
                                </span>
                            ))}
                        </div>
                    </div>
                )}
                {confluence && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Confluence Score</h4>
                        <div className="confluence-display">
                            <div
                                className={`confluence-score ${(confluence.confluence_score ?? 0) >= 70 ? 'high' : (confluence.confluence_score ?? 0) >= 40 ? 'mid' : 'low'}`}
                            >
                                {confluence.confluence_score ?? confluence.score ?? '—'}
                            </div>
                            <div className="confluence-label">
                                {confluence.direction || confluence.bias || 'Neutral'}
                            </div>
                        </div>
                    </div>
                )}
                {fibonacci && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Fibonacci Levels</h4>
                        <div className="fib-grid">
                            {Object.entries(fibonacci.retracement_levels || fibonacci.levels || fibonacci || {})
                                .slice(0, 6)
                                .map(([level, val]: [string, any]) => (
                                    <div key={level} className="fib-row">
                                        <span className="fib-level">{level}</span>
                                        <span className="fib-price">
                                            {typeof val === 'number' ? formatCurrency(val) : String(val)}
                                        </span>
                                    </div>
                                ))}
                        </div>
                    </div>
                )}
                {chartHealth && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Chart Health</h4>
                        <div className="health-grid">
                            {['trend', 'momentum', 'volume', 'volatility', 'structure'].map((dim) => {
                                const val = chartHealth[dim] ?? chartHealth[`${dim}_score`] ?? null;
                                return val != null ? (
                                    <div key={dim} className="health-item">
                                        <div className="health-dim">{dim}</div>
                                        <div className="health-bar-track">
                                            <div
                                                className="health-bar-fill"
                                                style={{
                                                    width: `${Math.min(100, val)}%`,
                                                    background:
                                                        val >= 70
                                                            ? 'var(--accent-green)'
                                                            : val >= 40
                                                              ? 'var(--accent-amber)'
                                                              : 'var(--accent-red)',
                                                }}
                                            />
                                        </div>
                                        <div className="health-val">{val}</div>
                                    </div>
                                ) : null;
                            })}
                        </div>
                    </div>
                )}
                {!patterns && !confluence && !fibonacci && !chartHealth && (
                    <div className="text-muted">No pattern data available</div>
                )}
                {patternOutcomes && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Pattern Outcomes</h4>
                        <div className="outcome-summary">
                            <span className="price-up">✓ {patternOutcomes.successes ?? 0}</span>
                            <span className="price-down">✗ {patternOutcomes.failures ?? 0}</span>
                            <span>Active: {patternOutcomes.active ?? 0}</span>
                            <span>
                                Win Rate: <strong>{patternOutcomes.success_rate_pct ?? '—'}%</strong>
                            </span>
                        </div>
                    </div>
                )}
                {patternBacktest && typeof patternBacktest === 'object' && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Pattern Backtest</h4>
                        <KVGrid data={patternBacktest.summary || patternBacktest} max={8} />
                    </div>
                )}
                {patternAlerts.length > 0 && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Recent Alerts</h4>
                        <div className="alert-feed">
                            {patternAlerts.slice(0, 6).map((alert: any, i: number) => (
                                <div
                                    key={i}
                                    className={`alert-item ${alert.type === 'failure' ? 'alert-failure' : 'alert-new'}`}
                                >
                                    <Bell size={12} />
                                    <span>{alert.pattern || alert.name || 'Alert'}</span>
                                    <span className="text-muted">{alert.type || ''}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </Panel>

            {/* ── 18. Options Intelligence (GEX + OI) ── */}
            <Panel
                panelId="sd-options-intelligence"
                title="Options Intelligence"
                icon={<Layers size={16} />}
                loading={loading}
            >
                {gexDetailed && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Gamma / Delta / Vanna Exposure</h4>
                        <div className="gex-summary-grid">
                            {[
                                { label: 'Net GEX', key: 'total_gex', color: 'var(--accent-blue)' },
                                { label: 'Net DEX', key: 'total_dex', color: 'var(--accent-purple)' },
                                { label: 'Net VEX', key: 'total_vex', color: 'var(--accent-amber)' },
                                { label: 'GEX Flip', key: 'gex_flip_point', color: 'var(--text-secondary)' },
                            ].map((item) => {
                                const val = gexDetailed[item.key] ?? null;
                                return (
                                    <div key={item.key} className="gex-metric-card">
                                        <div className="gex-metric-label">{item.label}</div>
                                        <div className="gex-metric-value" style={{ color: item.color }}>
                                            {val != null
                                                ? Math.abs(val) > 1000
                                                    ? formatCompact(val)
                                                    : val.toFixed(2)
                                                : '—'}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                        {gexDetailed.dealer_positioning && (
                            <div className="dealer-pos">
                                Dealer Positioning: <strong>{gexDetailed.dealer_positioning}</strong>
                            </div>
                        )}
                    </div>
                )}
                {oiPatterns && (
                    <div className="fund-section">
                        <h4 className="fund-section-title">Open Interest Patterns</h4>
                        <div className="oi-walls">
                            {oiPatterns.call_wall && (
                                <div className="oi-wall-item">
                                    <span className="oi-wall-label">Call Wall</span>
                                    <span className="oi-wall-value price-up">
                                        {formatCurrency(oiPatterns.call_wall)}
                                    </span>
                                </div>
                            )}
                            {oiPatterns.put_wall && (
                                <div className="oi-wall-item">
                                    <span className="oi-wall-label">Put Wall</span>
                                    <span className="oi-wall-value price-down">
                                        {formatCurrency(oiPatterns.put_wall)}
                                    </span>
                                </div>
                            )}
                            {oiPatterns.max_pain && (
                                <div className="oi-wall-item">
                                    <span className="oi-wall-label">Max Pain</span>
                                    <span className="oi-wall-value">{formatCurrency(oiPatterns.max_pain)}</span>
                                </div>
                            )}
                            {oiPatterns.pc_ratio != null && (
                                <div className="oi-wall-item">
                                    <span className="oi-wall-label">P/C Ratio</span>
                                    <span
                                        className={`oi-wall-value ${oiPatterns.pc_ratio > 1 ? 'price-down' : 'price-up'}`}
                                    >
                                        {oiPatterns.pc_ratio.toFixed(2)}
                                    </span>
                                </div>
                            )}
                        </div>
                        {oiPatterns.concentration && typeof oiPatterns.concentration === 'object' && (
                            <KVGrid data={oiPatterns.concentration} max={6} />
                        )}
                    </div>
                )}
                {!gexDetailed && !oiPatterns && (
                    <div className="text-muted">No options intelligence data available</div>
                )}
            </Panel>

            {/* ── 19. AI Chart Analysis ── */}
            <Panel
                panelId="sd-ai-chart-analysis"
                title="AI Chart Analysis"
                icon={<Eye size={16} />}
                loading={loading}
                defaultOpen={false}
            >
                <div className="vision-actions">
                    <button
                        type="button"
                        className="btn btn-outline"
                        disabled={visionLoading}
                        onClick={async () => {
                            if (!ticker) return;
                            setVisionLoading(true);
                            try {
                                const [analysisRes, narrateRes] = await Promise.allSettled([
                                    marketApi.analyzeChart(ticker),
                                    marketApi.narrateChart(ticker),
                                ]);
                                if (analysisRes.status === 'fulfilled') setVisionAnalysis(analysisRes.value.data);
                                if (narrateRes.status === 'fulfilled') setVisionNarration(narrateRes.value.data);
                            } finally {
                                setVisionLoading(false);
                            }
                        }}
                    >
                        <Eye size={14} /> {visionLoading ? 'Analyzing…' : 'Analyze Chart with AI'}
                    </button>
                </div>
                {visionAnalysis && (
                    <div className="fund-section" style={{ marginTop: 16 }}>
                        <h4 className="fund-section-title">Chart Analysis</h4>
                        <div className="vision-text">
                            {typeof visionAnalysis === 'string'
                                ? visionAnalysis
                                : visionAnalysis.analysis ||
                                  visionAnalysis.summary ||
                                  JSON.stringify(visionAnalysis, null, 2)}
                        </div>
                    </div>
                )}
                {visionNarration && (
                    <div className="fund-section" style={{ marginTop: 16 }}>
                        <h4 className="fund-section-title">Candle Narration</h4>
                        <div className="vision-text">
                            {typeof visionNarration === 'string'
                                ? visionNarration
                                : visionNarration.narration ||
                                  visionNarration.text ||
                                  JSON.stringify(visionNarration, null, 2)}
                        </div>
                    </div>
                )}
                {!visionAnalysis && !visionNarration && !visionLoading && (
                    <div className="text-muted" style={{ marginTop: 12 }}>
                        Click the button above to run direct-data chart analysis and narration.
                    </div>
                )}
            </Panel>

            {/* ═══════════════════════════════════════════════
               Phase 4: AI Coaching · Opening Range · Ghost Charts
                         Optimizer · Gamification
               ═══════════════════════════════════════════════ */}

            <SectionDivider label="Advanced Tools" />
            <CoachingPanel />
            <OpeningRangePanel ticker={ticker} />
            <GhostChartPanel ticker={ticker} />
            <OptimizerPanel />
            <GamificationPanel />

            {/* ═══════════════════════════════════════════════
               Alt Data: Google Trends · StockTwits · WSB · Earnings
               ═══════════════════════════════════════════════ */}

            {/* ── 25. Google Trends ── */}
            <Panel
                panelId="sd-google-trends"
                title="Google Trends"
                icon={<Search size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={googleTrends?.trend_direction || undefined}
                onOpenChange={onSentimentChange}
                badgeColor={
                    googleTrends?.trend_direction === 'rising'
                        ? 'green'
                        : googleTrends?.trend_direction === 'falling'
                          ? 'red'
                          : 'blue'
                }
            >
                {googleTrends ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                            <div className="kv-item">
                                <span className="kv-label">Current Interest</span>
                                <span className="kv-value">
                                    {googleTrends.current_interest ?? googleTrends.interest ?? '—'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Trend Direction</span>
                                <span
                                    className={`kv-value ${googleTrends.trend_direction === 'rising' ? 'price-up' : googleTrends.trend_direction === 'falling' ? 'price-down' : ''}`}
                                    style={{ textTransform: 'capitalize' }}
                                >
                                    {googleTrends.trend_direction || 'Neutral'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Spike Detected</span>
                                <span className={`kv-value ${googleTrends.spike_detected ? 'price-up' : ''}`}>
                                    {googleTrends.spike_detected ? '⚡ Yes' : 'No'}
                                </span>
                            </div>
                        </div>
                        {googleTrends.related_queries && googleTrends.related_queries.length > 0 && (
                            <div style={{ marginTop: 12 }}>
                                <h4 className="fund-section-title">Related Queries</h4>
                                <div className="alert-feed">
                                    {googleTrends.related_queries.slice(0, 5).map((q: any, i: number) => (
                                        <div key={i} className="alert-item">
                                            <Search size={12} />
                                            <span>{typeof q === 'string' ? q : q.query || q.title || ''}</span>
                                            {q.value && <span className="text-muted">{q.value}</span>}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-muted">No Google Trends data available</div>
                )}
            </Panel>

            {/* ── 26. StockTwits Sentiment ── */}
            <Panel
                panelId="sd-stocktwits-sentiment"
                title="StockTwits Sentiment"
                icon={<MessageCircle size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={stockTwits?.sentiment || undefined}
                badgeColor={
                    stockTwits?.sentiment === 'Bullish' ? 'green' : stockTwits?.sentiment === 'Bearish' ? 'red' : 'blue'
                }
                onOpenChange={onSentimentChange}
            >
                {stockTwits ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                            <div className="kv-item">
                                <span className="kv-label">Sentiment</span>
                                <span
                                    className={`kv-value ${stockTwits.sentiment === 'Bullish' ? 'price-up' : stockTwits.sentiment === 'Bearish' ? 'price-down' : ''}`}
                                >
                                    {stockTwits.sentiment || 'Neutral'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Bull %</span>
                                <span className="kv-value price-up">
                                    {stockTwits.bull_pct?.toFixed(1) ?? stockTwits.bullish_pct?.toFixed(1) ?? '—'}%
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Bear %</span>
                                <span className="kv-value price-down">
                                    {stockTwits.bear_pct?.toFixed(1) ?? stockTwits.bearish_pct?.toFixed(1) ?? '—'}%
                                </span>
                            </div>
                        </div>
                        {stockTwits.volume && (
                            <div className="text-muted" style={{ marginTop: 8, fontSize: '0.8rem' }}>
                                Message Volume:{' '}
                                {typeof stockTwits.volume === 'number'
                                    ? stockTwits.volume.toLocaleString()
                                    : stockTwits.volume}
                                {stockTwits.watchers && ` | Watchers: ${stockTwits.watchers.toLocaleString()}`}
                            </div>
                        )}
                        {stockTwits.messages &&
                            Array.isArray(stockTwits.messages) &&
                            stockTwits.messages.length > 0 && (
                                <div style={{ marginTop: 12 }}>
                                    <h4 className="fund-section-title">Recent Messages</h4>
                                    <div className="alert-feed">
                                        {stockTwits.messages.slice(0, 4).map((msg: any, i: number) => (
                                            <div key={i} className="alert-item">
                                                <MessageCircle size={12} />
                                                <span style={{ flex: 1 }}>
                                                    {msg.body?.slice(0, 120) || msg.text?.slice(0, 120) || ''}
                                                </span>
                                                {msg.sentiment && (
                                                    <span
                                                        className={`badge badge-${msg.sentiment === 'Bullish' ? 'green' : msg.sentiment === 'Bearish' ? 'red' : 'blue'}`}
                                                        style={{ fontSize: '0.6rem' }}
                                                    >
                                                        {msg.sentiment}
                                                    </span>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                    </div>
                ) : (
                    <div className="text-muted">No StockTwits data available</div>
                )}
            </Panel>

            {/* ── 27. WSB Due Diligence ── */}
            <Panel
                panelId="sd-wsb-due-diligence"
                title="WSB Due Diligence"
                icon={<Zap size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={wsbDD.length > 0 ? `${wsbDD.length} posts` : undefined}
                badgeColor="amber"
                onOpenChange={onSentimentChange}
            >
                {wsbDD.length > 0 ? (
                    <div className="fund-section">
                        <div className="alert-feed">
                            {wsbDD.slice(0, 6).map((post: any, i: number) => (
                                <div key={i} className="alert-item">
                                    <Zap size={12} />
                                    <span style={{ flex: 1, fontWeight: 500 }}>
                                        {post.title || post.headline || 'DD Post'}
                                    </span>
                                    {post.score != null && (
                                        <span className="badge badge-blue" style={{ fontSize: '0.6rem' }}>
                                            ↑ {post.score}
                                        </span>
                                    )}
                                    {post.created && (
                                        <span className="text-muted" style={{ fontSize: '0.7rem' }}>
                                            {new Date(post.created).toLocaleDateString()}
                                        </span>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="text-muted">No WSB due diligence posts found</div>
                )}
            </Panel>

            {/* ── 28. Earnings Transcript ── */}
            <Panel
                panelId="sd-earnings-transcript"
                title="Earnings Transcript"
                icon={<Mic size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={earningsTranscript?.quarter || undefined}
                badgeColor="purple"
                onOpenChange={onResearchChange}
            >
                {earningsTranscript ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', marginBottom: 12 }}>
                            {earningsTranscript.quarter && (
                                <div className="kv-item">
                                    <span className="kv-label">Quarter</span>
                                    <span className="kv-value">{earningsTranscript.quarter}</span>
                                </div>
                            )}
                            {earningsTranscript.date && (
                                <div className="kv-item">
                                    <span className="kv-label">Date</span>
                                    <span className="kv-value">
                                        {new Date(earningsTranscript.date).toLocaleDateString()}
                                    </span>
                                </div>
                            )}
                        </div>
                        {earningsTranscript.summary && (
                            <div className="vision-text" style={{ marginBottom: 12 }}>
                                {earningsTranscript.summary}
                            </div>
                        )}
                        {earningsTranscript.key_points && Array.isArray(earningsTranscript.key_points) && (
                            <div>
                                <h4 className="fund-section-title">Key Points</h4>
                                <ul style={{ margin: 0, paddingLeft: 16 }}>
                                    {earningsTranscript.key_points.map((pt: string, i: number) => (
                                        <li
                                            key={i}
                                            style={{
                                                marginBottom: 4,
                                                color: 'var(--text-secondary)',
                                                fontSize: '0.85rem',
                                            }}
                                        >
                                            {pt}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                        {earningsTranscript.tone && (
                            <div className="text-muted" style={{ marginTop: 8, fontSize: '0.8rem' }}>
                                Tone: <strong>{earningsTranscript.tone}</strong>
                                {earningsTranscript.guidance && ` | Guidance: ${earningsTranscript.guidance}`}
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-muted">No earnings transcript data available</div>
                )}
            </Panel>

            {/* ── 29. Pattern Alerts ── */}
            <Panel
                panelId="sd-pattern-alerts"
                title="Pattern Alerts"
                icon={<Bell size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={patternAlerts.length > 0 ? `${patternAlerts.length}` : undefined}
                badgeColor="amber"
                onOpenChange={onPatternsChange}
            >
                {patternAlerts.length > 0 ? (
                    <div className="fund-section">
                        <div className="alert-feed">
                            {patternAlerts.slice(0, 8).map((alert: any, i: number) => (
                                <div key={i} className="alert-item">
                                    <Bell size={12} />
                                    <span style={{ flex: 1, fontWeight: 500 }}>
                                        {alert.pattern || alert.name || alert.type || 'Alert'}
                                    </span>
                                    {alert.direction && (
                                        <span
                                            className={`badge badge-${alert.direction === 'bullish' ? 'green' : alert.direction === 'bearish' ? 'red' : 'blue'}`}
                                            style={{ fontSize: '0.6rem' }}
                                        >
                                            {alert.direction}
                                        </span>
                                    )}
                                    {alert.confidence != null && (
                                        <span className="text-muted" style={{ fontSize: '0.7rem' }}>
                                            {typeof alert.confidence === 'number'
                                                ? `${(alert.confidence * 100).toFixed(0)}%`
                                                : alert.confidence}
                                        </span>
                                    )}
                                    {alert.timestamp && (
                                        <span className="text-muted" style={{ fontSize: '0.7rem' }}>
                                            {new Date(alert.timestamp).toLocaleDateString()}
                                        </span>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="text-muted">No active pattern alerts</div>
                )}
            </Panel>

            {/* ── 30. Alert Chains ── */}
            <Panel
                panelId="sd-alert-chains"
                title="Alert Chains"
                icon={<Link2 size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={alertChains.length > 0 ? `${alertChains.length} chains` : undefined}
                badgeColor="purple"
            >
                {alertChains.length > 0 ? (
                    <div className="fund-section">
                        {alertChains.slice(0, 5).map((chain: any, i: number) => (
                            <div
                                key={i}
                                style={{
                                    marginBottom: 12,
                                    padding: '8px 10px',
                                    borderRadius: 6,
                                    background: 'rgba(255,255,255,0.03)',
                                    border: '1px solid var(--border)',
                                }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                                    <Link2 size={13} />
                                    <strong style={{ fontSize: '0.85rem' }}>
                                        {chain.name || chain.pattern || `Chain ${i + 1}`}
                                    </strong>
                                    {chain.status && (
                                        <span
                                            className={`badge badge-${chain.status === 'active' ? 'green' : chain.status === 'triggered' ? 'amber' : 'blue'}`}
                                            style={{ fontSize: '0.6rem' }}
                                        >
                                            {chain.status}
                                        </span>
                                    )}
                                </div>
                                {chain.stages && Array.isArray(chain.stages) && (
                                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                                        {chain.stages.map((stage: any, j: number) => (
                                            <span
                                                key={j}
                                                className={`badge badge-${stage.triggered ? 'green' : 'blue'}`}
                                                style={{ fontSize: '0.6rem' }}
                                            >
                                                {stage.type || stage.label || `Stage ${j + 1}`}
                                                {stage.price != null && ` @ $${stage.price.toFixed(2)}`}
                                            </span>
                                        ))}
                                    </div>
                                )}
                                {chain.entry_price != null && (
                                    <div className="text-muted" style={{ fontSize: '0.75rem', marginTop: 4 }}>
                                        Entry: ${chain.entry_price?.toFixed(2)}
                                        {chain.stop_price != null && ` | Stop: $${chain.stop_price.toFixed(2)}`}
                                        {chain.target_price != null && ` | Target: $${chain.target_price.toFixed(2)}`}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-muted">No alert chains configured for {ticker}</div>
                )}
            </Panel>

            {/* ═══════════════════════════════════════════════
               Analytics: Accuracy · Calibration · Backtesting
               ═══════════════════════════════════════════════ */}

            {/* ── 31. Accuracy Dashboard ── */}
            <Panel
                panelId="sd-accuracy-dashboard"
                title="Accuracy Dashboard"
                icon={<BarChart3 size={16} />}
                loading={loading}
                defaultOpen={false}
                onOpenChange={onPatternsChange}
                badge={
                    accuracyDash?.overall_win_rate != null
                        ? `${(accuracyDash.overall_win_rate * 100).toFixed(0)}%`
                        : undefined
                }
                badgeColor={
                    accuracyDash?.overall_win_rate > 0.55
                        ? 'green'
                        : accuracyDash?.overall_win_rate > 0.45
                          ? 'blue'
                          : 'red'
                }
            >
                {accuracyDash ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                            <div className="kv-item">
                                <span className="kv-label">Win Rate</span>
                                <span
                                    className={`kv-value ${accuracyDash.overall_win_rate > 0.5 ? 'price-up' : 'price-down'}`}
                                >
                                    {(accuracyDash.overall_win_rate * 100).toFixed(1)}%
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Total Predictions</span>
                                <span className="kv-value">{accuracyDash.total_predictions ?? '—'}</span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Avg PnL</span>
                                <span
                                    className={`kv-value ${(accuracyDash.avg_pnl || 0) > 0 ? 'price-up' : 'price-down'}`}
                                >
                                    {accuracyDash.avg_pnl != null ? `${(accuracyDash.avg_pnl * 100).toFixed(2)}%` : '—'}
                                </span>
                            </div>
                        </div>
                        {accuracyDash.by_pattern && Object.keys(accuracyDash.by_pattern).length > 0 && (
                            <div style={{ marginTop: 12 }}>
                                <h4 className="fund-section-title">By Pattern</h4>
                                <div className="alert-feed">
                                    {Object.entries(accuracyDash.by_pattern)
                                        .slice(0, 6)
                                        .map(([name, stats]: [string, any]) => (
                                            <div key={name} className="alert-item">
                                                <BarChart3 size={12} />
                                                <span style={{ flex: 1 }}>{name}</span>
                                                <span
                                                    className={`badge badge-${(stats.win_rate || 0) > 0.5 ? 'green' : 'red'}`}
                                                    style={{ fontSize: '0.6rem' }}
                                                >
                                                    {((stats.win_rate || 0) * 100).toFixed(0)}% ({stats.count || 0})
                                                </span>
                                            </div>
                                        ))}
                                </div>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-muted">No accuracy data available yet</div>
                )}
            </Panel>

            {/* ── 32. Confidence Calibration ── */}
            <Panel
                panelId="sd-confidence-calibration"
                title="Confidence Calibration"
                icon={<Target size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={calibration?.assessment || undefined}
                badgeColor={calibration?.assessment === 'well_calibrated' ? 'green' : 'amber'}
                onOpenChange={onPatternsChange}
            >
                {calibration ? (
                    <div className="fund-section">
                        {calibration.buckets && Array.isArray(calibration.buckets) && (
                            <div className="alert-feed">
                                {calibration.buckets.map((b: any, i: number) => (
                                    <div key={i} className="alert-item" style={{ justifyContent: 'space-between' }}>
                                        <span style={{ fontWeight: 500 }}>
                                            {b.range || b.label || `${b.min || 0}–${b.max || 100}%`}
                                        </span>
                                        <span className="text-muted">
                                            Predicted:{' '}
                                            {b.predicted != null ? `${(b.predicted * 100).toFixed(0)}%` : '—'}
                                        </span>
                                        <span
                                            className={`badge badge-${Math.abs((b.actual || 0) - (b.predicted || 0)) < 0.1 ? 'green' : 'amber'}`}
                                            style={{ fontSize: '0.6rem' }}
                                        >
                                            Actual: {b.actual != null ? `${(b.actual * 100).toFixed(0)}%` : '—'}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        )}
                        {calibration.assessment && (
                            <div
                                className="text-muted"
                                style={{ marginTop: 8, fontSize: '0.8rem', textTransform: 'capitalize' }}
                            >
                                Assessment: <strong>{calibration.assessment.replace(/_/g, ' ')}</strong>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-muted">Insufficient data for calibration</div>
                )}
            </Panel>

            {/* ── 33. Walk-Forward Backtest ── */}
            <Panel
                panelId="sd-walk-forward-backtest"
                title="Walk-Forward Backtest"
                icon={<Activity size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={walkForward?.overfitting_assessment || undefined}
                badgeColor={
                    walkForward?.overfitting_assessment === 'low'
                        ? 'green'
                        : walkForward?.overfitting_assessment === 'moderate'
                          ? 'amber'
                          : 'red'
                }
                onOpenChange={onAdvancedChange}
            >
                {walkForward ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                            <div className="kv-item">
                                <span className="kv-label">In-Sample Return</span>
                                <span
                                    className={`kv-value ${(walkForward.in_sample_return || 0) > 0 ? 'price-up' : 'price-down'}`}
                                >
                                    {walkForward.in_sample_return != null
                                        ? `${(walkForward.in_sample_return * 100).toFixed(1)}%`
                                        : '—'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Out-of-Sample Return</span>
                                <span
                                    className={`kv-value ${(walkForward.out_of_sample_return || 0) > 0 ? 'price-up' : 'price-down'}`}
                                >
                                    {walkForward.out_of_sample_return != null
                                        ? `${(walkForward.out_of_sample_return * 100).toFixed(1)}%`
                                        : '—'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Overfitting Risk</span>
                                <span className="kv-value" style={{ textTransform: 'capitalize' }}>
                                    {walkForward.overfitting_assessment || '—'}
                                </span>
                            </div>
                        </div>
                        {walkForward.folds && Array.isArray(walkForward.folds) && (
                            <div style={{ marginTop: 12 }}>
                                <h4 className="fund-section-title">Folds</h4>
                                <div className="alert-feed">
                                    {walkForward.folds.map((fold: any, i: number) => (
                                        <div key={i} className="alert-item">
                                            <Activity size={12} />
                                            <span>{fold.label || `Fold ${i + 1}`}</span>
                                            <span
                                                className={`badge badge-${(fold.return || 0) > 0 ? 'green' : 'red'}`}
                                                style={{ fontSize: '0.6rem' }}
                                            >
                                                {fold.return != null ? `${(fold.return * 100).toFixed(1)}%` : '—'}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-muted">Walk-forward data unavailable (VectorBT required)</div>
                )}
            </Panel>

            {/* ── 34. Monte Carlo Simulation ── */}
            <Panel
                panelId="sd-monte-carlo-simulation"
                title="Monte Carlo Simulation"
                icon={<TrendingUp size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={
                    monteCarlo?.median_return != null ? `${(monteCarlo.median_return * 100).toFixed(0)}%` : undefined
                }
                badgeColor={(monteCarlo?.median_return || 0) > 0 ? 'green' : 'red'}
                onOpenChange={onAdvancedChange}
            >
                {monteCarlo ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                            <div className="kv-item">
                                <span className="kv-label">Median Return</span>
                                <span
                                    className={`kv-value ${(monteCarlo.median_return || 0) > 0 ? 'price-up' : 'price-down'}`}
                                >
                                    {monteCarlo.median_return != null
                                        ? `${(monteCarlo.median_return * 100).toFixed(1)}%`
                                        : '—'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">5th Percentile</span>
                                <span className="kv-value price-down">
                                    {monteCarlo.pct_5 != null ? `${(monteCarlo.pct_5 * 100).toFixed(1)}%` : '—'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">95th Percentile</span>
                                <span className="kv-value price-up">
                                    {monteCarlo.pct_95 != null ? `${(monteCarlo.pct_95 * 100).toFixed(1)}%` : '—'}
                                </span>
                            </div>
                        </div>
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', marginTop: 8 }}>
                            <div className="kv-item">
                                <span className="kv-label">Max Drawdown (Median)</span>
                                <span className="kv-value price-down">
                                    {monteCarlo.median_max_drawdown != null
                                        ? `${(monteCarlo.median_max_drawdown * 100).toFixed(1)}%`
                                        : '—'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Simulations</span>
                                <span className="kv-value">
                                    {monteCarlo.n_simulations?.toLocaleString() || '1,000'}
                                </span>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="text-muted">Monte Carlo data unavailable (VectorBT required)</div>
                )}
            </Panel>

            {/* ═══════════════════════════════════════════════
               Signals: Sentiment · Correlation · Social Volume
               ═══════════════════════════════════════════════ */}

            {/* ── 35. Sentiment Synthesis ── */}
            <Panel
                panelId="sd-sentiment-synthesis"
                title="Sentiment Synthesis"
                icon={<Radio size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={sentimentSynth?.verdict || sentimentSynth?.signal || undefined}
                onOpenChange={onSentimentChange}
                badgeColor={
                    (sentimentSynth?.verdict || sentimentSynth?.signal || '').toLowerCase().includes('bull')
                        ? 'green'
                        : (sentimentSynth?.verdict || sentimentSynth?.signal || '').toLowerCase().includes('bear')
                          ? 'red'
                          : 'blue'
                }
            >
                {sentimentSynth ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                            <div className="kv-item">
                                <span className="kv-label">Verdict</span>
                                <span className="kv-value" style={{ textTransform: 'capitalize', fontWeight: 600 }}>
                                    {sentimentSynth.verdict || sentimentSynth.signal || '—'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Confidence</span>
                                <span className="kv-value">
                                    {sentimentSynth.confidence != null
                                        ? `${(sentimentSynth.confidence * 100).toFixed(0)}%`
                                        : '—'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Conflicts</span>
                                <span
                                    className={`kv-value ${sentimentSynth.conflicts?.length > 0 ? 'price-down' : 'price-up'}`}
                                >
                                    {sentimentSynth.conflicts?.length > 0
                                        ? `${sentimentSynth.conflicts.length} ⚠️`
                                        : 'None ✓'}
                                </span>
                            </div>
                        </div>
                        {sentimentSynth.reasoning && (
                            <div className="vision-text" style={{ marginTop: 12 }}>
                                {sentimentSynth.reasoning}
                            </div>
                        )}
                        {sentimentSynth.signals && Array.isArray(sentimentSynth.signals) && (
                            <div style={{ marginTop: 12 }}>
                                <h4 className="fund-section-title">Signal Sources</h4>
                                <div className="alert-feed">
                                    {sentimentSynth.signals.map((sig: any, i: number) => (
                                        <div key={i} className="alert-item">
                                            <Radio size={12} />
                                            <span style={{ flex: 1 }}>{sig.source || sig.name}</span>
                                            <span
                                                className={`badge badge-${sig.sentiment === 'bullish' ? 'green' : sig.sentiment === 'bearish' ? 'red' : 'blue'}`}
                                                style={{ fontSize: '0.6rem', textTransform: 'capitalize' }}
                                            >
                                                {sig.sentiment || sig.signal}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-muted">Sentiment synthesis unavailable</div>
                )}
            </Panel>

            {/* ── 36. Correlation Matrix ── */}
            <Panel
                panelId="sd-panel-35"
                title={`Correlation (${ticker} vs SPY/QQQ)`}
                icon={<BarChart3 size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={correlation?.pairs?.[0]?.strength || undefined}
                badgeColor={correlation?.pairs?.[0]?.strength === 'strong' ? 'green' : 'amber'}
            >
                {correlation?.pairs ? (
                    <div className="fund-section">
                        <div className="alert-feed">
                            {correlation.pairs.map((pair: any, i: number) => (
                                <div key={i} className="alert-item" style={{ justifyContent: 'space-between' }}>
                                    <span style={{ fontWeight: 500 }}>
                                        {pair.ticker_a} ↔ {pair.ticker_b}
                                    </span>
                                    <span className={`kv-value ${pair.correlation > 0 ? 'price-up' : 'price-down'}`}>
                                        {pair.correlation?.toFixed(4)}
                                    </span>
                                    <span
                                        className={`badge badge-${pair.strength === 'strong' ? 'green' : pair.strength === 'moderate' ? 'amber' : 'red'}`}
                                        style={{ fontSize: '0.6rem', textTransform: 'capitalize' }}
                                    >
                                        {pair.strength}
                                    </span>
                                </div>
                            ))}
                        </div>
                        {correlation.data_points && (
                            <div className="text-muted" style={{ marginTop: 8, fontSize: '0.8rem' }}>
                                Based on {correlation.data_points} data points
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-muted">Correlation data unavailable</div>
                )}
            </Panel>

            {/* ── 37. Social Volume Spikes ── */}
            <Panel
                panelId="sd-social-volume-spikes"
                title="Social Volume Spikes"
                icon={<Users size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={socialVolume?.spike_detected ? '⚡ SPIKE' : undefined}
                badgeColor={socialVolume?.spike_detected ? 'red' : undefined}
                onOpenChange={onSentimentChange}
            >
                {socialVolume ? (
                    <div className="fund-section">
                        {['reddit', 'twitter'].map((src) => {
                            const d = socialVolume[src];
                            if (!d || d.data_points === 0) return null;
                            return (
                                <div key={src} style={{ marginBottom: 12 }}>
                                    <h4 className="fund-section-title" style={{ textTransform: 'capitalize' }}>
                                        {src}
                                    </h4>
                                    <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
                                        <div className="kv-item">
                                            <span className="kv-label">Latest</span>
                                            <span className="kv-value">
                                                {d.latest_mentions?.toLocaleString() ?? '—'}
                                            </span>
                                        </div>
                                        <div className="kv-item">
                                            <span className="kv-label">Mean</span>
                                            <span className="kv-value">{d.mean_mentions ?? '—'}</span>
                                        </div>
                                        <div className="kv-item">
                                            <span className="kv-label">Z-Score</span>
                                            <span className={`kv-value ${d.z_score > 2 ? 'price-up' : ''}`}>
                                                {d.z_score ?? '—'}
                                            </span>
                                        </div>
                                        <div className="kv-item">
                                            <span className="kv-label">Spike</span>
                                            <span className={`kv-value ${d.spike ? 'price-up' : ''}`}>
                                                {d.spike ? `⚡ ${d.spike_severity}` : 'Normal'}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                        {!socialVolume.reddit?.data_points && !socialVolume.twitter?.data_points && (
                            <div className="text-muted">No social volume data (Finnhub API key required)</div>
                        )}
                    </div>
                ) : (
                    <div className="text-muted">Social volume data unavailable</div>
                )}
            </Panel>

            {/* ═══════════════════════════════════════════════
               Advanced: Greeks · Market · Briefing · Journal · Dividends · Portfolio
               ═══════════════════════════════════════════════ */}

            {/* ── 38. Higher-Order Greeks ── */}
            <Panel
                panelId="sd-higher-order-greeks"
                title="Higher-Order Greeks"
                icon={<Activity size={16} />}
                loading={loading}
                defaultOpen={false}
                badge="2nd/3rd Order"
                onOpenChange={onOptionsChange}
            >
                {higherGreeks ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
                            {['charm', 'vanna', 'vomma', 'speed', 'color', 'ultima', 'zomma', 'veta'].map(
                                (greek) =>
                                    higherGreeks[greek] != null && (
                                        <div key={greek} className="kv-item">
                                            <span className="kv-label" style={{ textTransform: 'capitalize' }}>
                                                {greek}
                                            </span>
                                            <span className="kv-value">
                                                {typeof higherGreeks[greek] === 'number'
                                                    ? higherGreeks[greek].toFixed(6)
                                                    : String(higherGreeks[greek])}
                                            </span>
                                        </div>
                                    ),
                            )}
                        </div>
                        {higherGreeks.expiry_days && (
                            <div className="text-muted" style={{ marginTop: 8, fontSize: '0.8rem' }}>
                                Calculated for {higherGreeks.expiry_days} DTE, {higherGreeks.option_type || 'call'}
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-muted">Higher-order Greeks unavailable</div>
                )}
            </Panel>

            {/* ── 39. Market Status ── */}
            <Panel
                panelId="sd-market-status"
                title="Market Status"
                icon={<Clock size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={marketStatus?.status || undefined}
                badgeColor={
                    marketStatus?.status === 'open'
                        ? 'green'
                        : marketStatus?.status === 'pre' || marketStatus?.status === 'post'
                          ? 'amber'
                          : 'red'
                }
            >
                {marketStatus ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                            <div className="kv-item">
                                <span className="kv-label">Status</span>
                                <span className="kv-value" style={{ textTransform: 'capitalize', fontWeight: 600 }}>
                                    {marketStatus.status || '—'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Exchange</span>
                                <span className="kv-value">{marketStatus.exchange || 'NYSE'}</span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Next Event</span>
                                <span className="kv-value">
                                    {marketStatus.next_event || marketStatus.next_open || '—'}
                                </span>
                            </div>
                        </div>
                        {marketStatus.message && (
                            <div className="text-muted" style={{ marginTop: 8, fontSize: '0.8rem' }}>
                                {marketStatus.message}
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-muted">Market status unavailable</div>
                )}
            </Panel>

            {/* ── 40. Morning Briefing ── */}
            <Panel
                panelId="sd-morning-briefing"
                title="Morning Briefing"
                icon={<Briefcase size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={briefing?.date || undefined}
            >
                {briefing ? (
                    <div className="fund-section">
                        {briefing.summary && (
                            <div className="vision-text" style={{ marginBottom: 12 }}>
                                {briefing.summary}
                            </div>
                        )}
                        {briefing.watchlist_alerts &&
                            Array.isArray(briefing.watchlist_alerts) &&
                            briefing.watchlist_alerts.length > 0 && (
                                <div>
                                    <h4 className="fund-section-title">Watchlist Alerts</h4>
                                    <div className="alert-feed">
                                        {briefing.watchlist_alerts.slice(0, 8).map((alert: any, i: number) => (
                                            <div key={i} className="alert-item">
                                                <Bell size={12} />
                                                <span style={{ flex: 1 }}>
                                                    {alert.ticker}: {alert.message || alert.alert}
                                                </span>
                                                <span
                                                    className={`badge badge-${alert.type === 'breakout' ? 'green' : alert.type === 'warning' ? 'red' : 'blue'}`}
                                                    style={{ fontSize: '0.6rem' }}
                                                >
                                                    {alert.type || 'info'}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                    </div>
                ) : (
                    <div className="text-muted">No morning briefing available yet</div>
                )}
            </Panel>

            {/* ── 41. Trading Journal ── */}
            <Panel
                panelId="sd-trading-journal"
                title="Trading Journal"
                icon={<BookOpen size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={journal?.date || undefined}
            >
                {journal ? (
                    <div className="fund-section">
                        {journal.narrative && (
                            <div className="vision-text" style={{ marginBottom: 12 }}>
                                {journal.narrative}
                            </div>
                        )}
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
                            <div className="kv-item">
                                <span className="kv-label">Trades</span>
                                <span className="kv-value">{journal.total_trades ?? '—'}</span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Win Rate</span>
                                <span
                                    className={`kv-value ${(journal.win_rate || 0) > 0.5 ? 'price-up' : 'price-down'}`}
                                >
                                    {journal.win_rate != null ? `${(journal.win_rate * 100).toFixed(0)}%` : '—'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Day P&L</span>
                                <span className={`kv-value ${(journal.pnl || 0) > 0 ? 'price-up' : 'price-down'}`}>
                                    {journal.pnl != null ? formatCurrency(journal.pnl) : '—'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Best Trade</span>
                                <span className="kv-value price-up">{journal.best_trade || '—'}</span>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="text-muted">No trading journal entry for today</div>
                )}
            </Panel>

            {/* ── 42. Dividend Calendar ── */}
            <Panel
                panelId="sd-dividend-calendar"
                title="Dividend Calendar"
                icon={<Calendar size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={dividends && Array.isArray(dividends) ? `${dividends.length}` : undefined}
                badgeColor="green"
            >
                {dividends && Array.isArray(dividends) && dividends.length > 0 ? (
                    <div className="fund-section">
                        <div className="alert-feed">
                            {dividends.slice(0, 10).map((div: any, i: number) => (
                                <div key={i} className="alert-item" style={{ justifyContent: 'space-between' }}>
                                    <span style={{ fontWeight: 500 }}>{div.ticker || div.symbol}</span>
                                    <span className="text-muted">{div.ex_date || div.date || '—'}</span>
                                    <span className="kv-value price-up">
                                        {div.amount != null
                                            ? formatCurrency(div.amount)
                                            : div.yield != null
                                              ? `${(div.yield * 100).toFixed(2)}%`
                                              : '—'}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="text-muted">No upcoming dividends for your holdings</div>
                )}
            </Panel>

            {/* ── 43. Portfolio Performance ── */}
            <Panel
                panelId="sd-portfolio-performance"
                title="Portfolio Performance"
                icon={<DollarSign size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={
                    portfolio?.total_return != null
                        ? `${portfolio.total_return > 0 ? '+' : ''}${(portfolio.total_return * 100).toFixed(1)}%`
                        : undefined
                }
                badgeColor={(portfolio?.total_return || 0) > 0 ? 'green' : 'red'}
            >
                {portfolio ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
                            <div className="kv-item">
                                <span className="kv-label">Unrealized P&L</span>
                                <span
                                    className={`kv-value ${(portfolio.unrealized_pnl || 0) > 0 ? 'price-up' : 'price-down'}`}
                                >
                                    {portfolio.unrealized_pnl != null ? formatCurrency(portfolio.unrealized_pnl) : '—'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Realized P&L</span>
                                <span
                                    className={`kv-value ${(portfolio.realized_pnl || 0) > 0 ? 'price-up' : 'price-down'}`}
                                >
                                    {portfolio.realized_pnl != null ? formatCurrency(portfolio.realized_pnl) : '—'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Dividends</span>
                                <span className="kv-value price-up">
                                    {portfolio.dividend_income != null
                                        ? formatCurrency(portfolio.dividend_income)
                                        : '—'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Commissions</span>
                                <span className="kv-value price-down">
                                    {portfolio.commissions != null ? formatCurrency(portfolio.commissions) : '—'}
                                </span>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="text-muted">Portfolio performance data unavailable (Questrade login required)</div>
                )}
            </Panel>

            {/* ── 20. Anchored VWAP ── */}
            <Panel
                panelId="sd-anchored-vwap"
                title="Anchored VWAP"
                icon={<Anchor size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={
                    avwap?.current_deviation
                        ? `${avwap.current_deviation > 0 ? '+' : ''}${avwap.current_deviation.toFixed(2)}σ`
                        : undefined
                }
                badgeColor={avwap?.current_deviation > 0 ? 'green' : 'red'}
                onOpenChange={onAdvancedChange}
            >
                {avwap ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
                            <div className="kv-item">
                                <span className="kv-label">VWAP</span>
                                <span className="kv-value">{formatCurrency(avwap.current_vwap)}</span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">+1σ Band</span>
                                <span className="kv-value price-up">{formatCurrency(avwap.upper_band_1)}</span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">-1σ Band</span>
                                <span className="kv-value price-down">{formatCurrency(avwap.lower_band_1)}</span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Deviation</span>
                                <span className={`kv-value ${avwap.current_deviation > 0 ? 'price-up' : 'price-down'}`}>
                                    {avwap.current_deviation?.toFixed(3)}σ
                                </span>
                            </div>
                        </div>
                        {avwap.upper_band_2 && (
                            <div className="text-muted" style={{ marginTop: 8, fontSize: '0.8rem' }}>
                                ±2σ Bands: {formatCurrency(avwap.upper_band_2)} / {formatCurrency(avwap.lower_band_2)}
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-muted">No AVWAP data available</div>
                )}
            </Panel>

            {/* ── 21. Volume Profile ── */}
            <Panel
                panelId="sd-volume-profile"
                title="Volume Profile"
                icon={<BarChart2 size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={volumeProfile?.poc_price ? `POC: ${formatCurrency(volumeProfile.poc_price)}` : undefined}
                badgeColor="purple"
                onOpenChange={onAdvancedChange}
            >
                {volumeProfile ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                            <div className="kv-item">
                                <span className="kv-label">Point of Control</span>
                                <span className="kv-value" style={{ color: 'var(--accent-purple)' }}>
                                    {formatCurrency(volumeProfile.poc_price)}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Value Area High</span>
                                <span className="kv-value price-up">
                                    {formatCurrency(volumeProfile.value_area_high)}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Value Area Low</span>
                                <span className="kv-value price-down">
                                    {formatCurrency(volumeProfile.value_area_low)}
                                </span>
                            </div>
                        </div>
                        {volumeProfile.high_volume_nodes && volumeProfile.high_volume_nodes.length > 0 && (
                            <div style={{ marginTop: 12 }}>
                                <h4 className="fund-section-title">High Volume Nodes</h4>
                                <div className="alert-feed">
                                    {volumeProfile.high_volume_nodes.slice(0, 5).map((node: any, i: number) => (
                                        <div key={i} className="alert-item alert-new">
                                            <BarChart2 size={12} />
                                            <span>{formatCurrency(node.price || node)}</span>
                                            {node.volume && (
                                                <span className="text-muted">{formatCompact(node.volume)} vol</span>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-muted">No volume profile data available</div>
                )}
            </Panel>

            {/* ── 22. Market Structure ── */}
            <Panel
                panelId="sd-market-structure"
                title="Market Structure"
                icon={<GitBranch size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={marketStructure?.trend || undefined}
                badgeColor={
                    marketStructure?.trend === 'uptrend'
                        ? 'green'
                        : marketStructure?.trend === 'downtrend'
                          ? 'red'
                          : 'blue'
                }
                onOpenChange={onAdvancedChange}
            >
                {marketStructure ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                            <div className="kv-item">
                                <span className="kv-label">Trend</span>
                                <span
                                    className={`kv-value ${marketStructure.trend === 'uptrend' ? 'price-up' : marketStructure.trend === 'downtrend' ? 'price-down' : ''}`}
                                    style={{ textTransform: 'capitalize' }}
                                >
                                    {marketStructure.trend || 'Neutral'}
                                </span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Swing Highs</span>
                                <span className="kv-value">{marketStructure.swing_highs?.length ?? 0}</span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Swing Lows</span>
                                <span className="kv-value">{marketStructure.swing_lows?.length ?? 0}</span>
                            </div>
                        </div>
                        {marketStructure.events && marketStructure.events.length > 0 && (
                            <div style={{ marginTop: 12 }}>
                                <h4 className="fund-section-title">Structure Events (BOS / CHoCH)</h4>
                                <div className="alert-feed">
                                    {marketStructure.events.slice(-6).map((evt: any, i: number) => (
                                        <div
                                            key={i}
                                            className={`alert-item ${evt.type === 'BOS' ? 'alert-new' : 'alert-failure'}`}
                                        >
                                            <GitBranch size={12} />
                                            <span>
                                                {evt.type}: {formatCurrency(evt.price)}
                                            </span>
                                            <span className="text-muted">{evt.direction || ''}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-muted">No market structure data available</div>
                )}
            </Panel>

            {/* ── 23. Consolidation & Liquidity Zones ── */}
            <Panel
                panelId="sd-consolidation-liquidity-zones"
                title="Consolidation & Liquidity Zones"
                icon={<Box size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={consolidationZones?.zones?.length ? `${consolidationZones.zones.length} zones` : undefined}
                badgeColor="amber"
                onOpenChange={onAdvancedChange}
            >
                <div className="fund-section">
                    {consolidationZones?.zones && consolidationZones.zones.length > 0 ? (
                        <>
                            <h4 className="fund-section-title">Consolidation Zones</h4>
                            <div className="alert-feed">
                                {consolidationZones.zones.slice(0, 5).map((zone: any, i: number) => (
                                    <div key={i} className={`alert-item ${zone.active ? 'alert-new' : ''}`}>
                                        <Box size={12} />
                                        <span>
                                            {formatCurrency(zone.low)} — {formatCurrency(zone.high)}
                                        </span>
                                        <span className="text-muted">
                                            {zone.bars} bars{zone.active ? ' (active)' : ''}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </>
                    ) : (
                        <div className="text-muted">No consolidation zones detected</div>
                    )}
                </div>
                <div className="fund-section" style={{ marginTop: 12 }}>
                    {liquidityZones?.zones && liquidityZones.zones.length > 0 ? (
                        <>
                            <h4 className="fund-section-title">Liquidity Zones (S/R Magnets)</h4>
                            <div className="alert-feed">
                                {liquidityZones.zones.slice(0, 5).map((zone: any, i: number) => (
                                    <div key={i} className="alert-item">
                                        <Layers size={12} />
                                        <span>{formatCurrency(zone.price)}</span>
                                        <span className="text-muted">{formatCompact(zone.volume)} vol</span>
                                    </div>
                                ))}
                            </div>
                        </>
                    ) : (
                        <div className="text-muted">No liquidity zones detected</div>
                    )}
                </div>
            </Panel>

            {/* ── 24. Multi-Target Take Profit ── */}
            <Panel
                panelId="sd-multi-target-take-profit"
                title="Multi-Target Take Profit"
                icon={<Compass size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={multiTargetTP?.direction || undefined}
                badgeColor={multiTargetTP?.direction === 'bullish' ? 'green' : 'red'}
                onOpenChange={onAdvancedChange}
            >
                {multiTargetTP ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', marginBottom: 12 }}>
                            <div className="kv-item">
                                <span className="kv-label">Current Price</span>
                                <span className="kv-value">{formatCurrency(multiTargetTP.current_price)}</span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Stop Loss</span>
                                <span className="kv-value price-down">{formatCurrency(multiTargetTP.stop_loss)}</span>
                            </div>
                        </div>
                        <div className="alert-feed">
                            {(multiTargetTP.targets || []).map((tp: any, i: number) => (
                                <div key={i} className="alert-item alert-new">
                                    <Target size={12} />
                                    <span style={{ fontWeight: 600 }}>{tp.level}</span>
                                    <span className="price-up">{formatCurrency(tp.price)}</span>
                                    <span className="text-muted">Fib {tp.fib}</span>
                                    <span className="text-muted">R:R {tp.rr_ratio}x</span>
                                    <span className="badge badge-blue" style={{ fontSize: '0.65rem' }}>
                                        {tp.probability}%
                                    </span>
                                </div>
                            ))}
                        </div>
                        <div className="text-muted" style={{ marginTop: 8, fontSize: '0.8rem' }}>
                            Swing Range: {formatCurrency(multiTargetTP.swing_range)} | High:{' '}
                            {formatCurrency(multiTargetTP.recent_high)} | Low:{' '}
                            {formatCurrency(multiTargetTP.recent_low)}
                        </div>
                    </div>
                ) : (
                    <div className="text-muted">No take-profit data available</div>
                )}
            </Panel>

            {/* ── 25. Pattern Accuracy (QuestDB) ── */}
            <Panel
                panelId="sd-pattern-accuracy-questdb"
                title="Pattern Accuracy (QuestDB)"
                icon={<Target size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={patternAccuracyQDB?.win_rate ? `${patternAccuracyQDB.win_rate}% WR` : undefined}
                badgeColor={patternAccuracyQDB?.win_rate > 50 ? 'green' : 'red'}
            >
                {patternAccuracyQDB ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 12 }}>
                            <div className="kv-item">
                                <span className="kv-label">Total Evaluated</span>
                                <span className="kv-value">{patternAccuracyQDB.total}</span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Wins</span>
                                <span className="kv-value price-up">{patternAccuracyQDB.wins}</span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Losses</span>
                                <span className="kv-value price-down">{patternAccuracyQDB.losses}</span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Win Rate</span>
                                <span
                                    className={`kv-value ${patternAccuracyQDB.win_rate > 50 ? 'price-up' : 'price-down'}`}
                                >
                                    {patternAccuracyQDB.win_rate}%
                                </span>
                            </div>
                        </div>
                        <div className="alert-feed">
                            {(patternAccuracyQDB.patterns || []).slice(0, 10).map((p: any, i: number) => (
                                <div key={i} className="alert-item">
                                    <Activity size={12} />
                                    <span style={{ fontWeight: 600, minWidth: 120 }}>{p.pattern}</span>
                                    <span className={p.win_rate > 50 ? 'price-up' : 'price-down'}>
                                        {p.win_rate}% WR
                                    </span>
                                    <span className="text-muted">{p.total} trades</span>
                                    <span className="text-muted">Avg P&L: {p.avg_pnl_pct}%</span>
                                    <span className="text-muted">Avg MFE: {p.avg_mfe_pct}%</span>
                                </div>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="text-muted">No pattern accuracy data yet — outcomes persist after evaluation</div>
                )}
            </Panel>

            {/* ── 26. Exit Analysis ── */}
            <Panel
                panelId="sd-exit-analysis"
                title="Exit Analysis"
                icon={<GitBranch size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={exitAnalysis?.actionable_count ? `${exitAnalysis.actionable_count} actionable` : undefined}
                badgeColor={exitAnalysis?.actionable_count > 0 ? 'orange' : 'green'}
                onOpenChange={onAdvancedChange}
            >
                {exitAnalysis ? (
                    <div className="fund-section">
                        <div className="kv-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: 12 }}>
                            <div className="kv-item">
                                <span className="kv-label">Current Price</span>
                                <span className="kv-value">{formatCurrency(exitAnalysis.current_price)}</span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Active Patterns</span>
                                <span className="kv-value">{exitAnalysis.active_patterns}</span>
                            </div>
                            <div className="kv-item">
                                <span className="kv-label">Actionable</span>
                                <span
                                    className={`kv-value ${exitAnalysis.actionable_count > 0 ? 'price-down' : 'price-up'}`}
                                >
                                    {exitAnalysis.actionable_count}
                                </span>
                            </div>
                        </div>
                        {exitAnalysis.narrative && (
                            <div
                                style={{
                                    padding: '8px 12px',
                                    background: 'var(--glass-bg)',
                                    borderRadius: 8,
                                    marginBottom: 12,
                                    fontSize: '0.85rem',
                                    lineHeight: 1.5,
                                    borderLeft: '3px solid var(--accent-primary)',
                                }}
                            >
                                {exitAnalysis.narrative}
                            </div>
                        )}
                        <div className="alert-feed">
                            {(exitAnalysis.exit_signals || []).map((s: any, i: number) => (
                                <div
                                    key={i}
                                    className={`alert-item ${s.verdict === 'TARGET_HIT' ? 'alert-new' : s.verdict === 'STOP_TRIGGERED' ? 'alert-resolved' : ''}`}
                                >
                                    {s.verdict === 'TARGET_HIT' ? (
                                        <TrendingUp size={12} />
                                    ) : s.verdict === 'STOP_TRIGGERED' ? (
                                        <TrendingDown size={12} />
                                    ) : (
                                        <Clock size={12} />
                                    )}
                                    <span style={{ fontWeight: 600 }}>{s.pattern}</span>
                                    <span
                                        className={`badge ${s.verdict === 'TARGET_HIT' ? 'badge-green' : s.verdict === 'STOP_TRIGGERED' ? 'badge-red' : 'badge-blue'}`}
                                        style={{ fontSize: '0.65rem' }}
                                    >
                                        {s.verdict}
                                    </span>
                                    {s.pnl_pct !== undefined && (
                                        <span className={s.pnl_pct >= 0 ? 'price-up' : 'price-down'}>
                                            {s.pnl_pct > 0 ? '+' : ''}
                                            {s.pnl_pct}%
                                        </span>
                                    )}
                                    <span className="text-muted">
                                        Target: {formatCurrency(s.target)} | Stop: {formatCurrency(s.stop_loss)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="text-muted">No active exit signals for this ticker</div>
                )}
            </Panel>

            {/* ── 27. Recent Outcomes ── */}
            <Panel
                panelId="sd-recent-outcomes"
                title="Recent Outcomes"
                icon={<BarChart3 size={16} />}
                loading={loading}
                defaultOpen={false}
                badge={recentOutcomes?.outcomes?.length ? `${recentOutcomes.outcomes.length} recent` : undefined}
            >
                {recentOutcomes?.outcomes?.length ? (
                    <div className="alert-feed">
                        {recentOutcomes.outcomes.map((o: any, i: number) => (
                            <div
                                key={i}
                                className={`alert-item ${o.outcome === 'success' ? 'alert-new' : o.outcome === 'failed' ? 'alert-resolved' : ''}`}
                            >
                                {o.outcome === 'success' ? (
                                    <TrendingUp size={12} />
                                ) : o.outcome === 'failed' ? (
                                    <TrendingDown size={12} />
                                ) : (
                                    <Clock size={12} />
                                )}
                                <span style={{ fontWeight: 600, minWidth: 50 }}>{o.ticker}</span>
                                <span className="text-muted">{o.pattern}</span>
                                <span
                                    className={`badge ${o.outcome === 'success' ? 'badge-green' : o.outcome === 'failed' ? 'badge-red' : 'badge-blue'}`}
                                    style={{ fontSize: '0.65rem' }}
                                >
                                    {o.outcome}
                                </span>
                                <span className={o.pnl_pct >= 0 ? 'price-up' : 'price-down'}>
                                    {o.pnl_pct > 0 ? '+' : ''}
                                    {o.pnl_pct}%
                                </span>
                                <span className="text-muted">{o.bars_held} bars</span>
                                {o.resolved_at && (
                                    <span className="text-muted" style={{ fontSize: '0.7rem' }}>
                                        {timeAgo(o.resolved_at)}
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-muted">No recent outcomes — patterns will appear after evaluation</div>
                )}
            </Panel>

            {/* ── 13. Strategy Builder (full width) ── */}
            <div className="strategy-section">
                <h2 className="section-title">
                    <Shield size={16} /> Strategy Builder
                </h2>
                <OptionStratsEmbed ticker={ticker} strategy="optimizer" height={600} />
            </div>
        </div>
    );
}
