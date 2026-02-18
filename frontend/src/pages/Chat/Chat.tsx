/**
 * Chat v3 — AI Assistant with agent selector, conversation persistence,
 * Decision Dashboard, expandable tool calls, and conversation history
 *
 * Features:
 * - Conversation ID persistence (multi-turn memory)
 * - 6-agent selector bar (Auto, TA, Options, Breakout, Sentiment, Portfolio)
 * - One-click Decision Dashboard with structured verdict card
 * - Tool call expansion (chip list)
 * - Conversation history sidebar (localStorage)
 * - Markdown rendering, typing indicator, quick prompts, data cards
 */

import { useMutation } from '@tanstack/react-query';
import {
    BarChart3,
    Briefcase,
    ChevronDown,
    ChevronUp,
    Clock,
    Crosshair,
    Heart,
    LayoutDashboard,
    MessageSquare,
    PanelLeft,
    PanelLeftClose,
    Send,
    Sparkles,
    Trash2,
    TrendingUp,
    User,
    Wrench,
    Zap,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { chatApi, conversationApi } from '../../api/client';
import './Chat.css';

/* eslint-disable @typescript-eslint/no-explicit-any */

interface Message {
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    agent?: string;
    tools?: string[];
    data?: Record<string, any>;
    verdict?: any;
}

interface ConversationEntry {
    id: string;
    title: string;
    timestamp: number;
    messageCount: number;
}

type AgentKey = 'auto' | 'ta' | 'options' | 'breakout' | 'sentiment' | 'portfolio';

const AGENTS: { key: AgentKey; label: string; icon: React.ReactNode }[] = [
    { key: 'auto', label: 'Auto', icon: <Zap size={13} /> },
    { key: 'ta', label: 'Technical', icon: <BarChart3 size={13} /> },
    { key: 'options', label: 'Options', icon: <TrendingUp size={13} /> },
    { key: 'breakout', label: 'Breakout', icon: <Crosshair size={13} /> },
    { key: 'sentiment', label: 'Sentiment', icon: <Heart size={13} /> },
    { key: 'portfolio', label: 'Portfolio', icon: <Briefcase size={13} /> },
];

const QUICK_PROMPTS = [
    'Analyze AAPL for swing trading',
    'What are the top movers today?',
    'Show me unusual options flow for TSLA',
    'Compare NVDA vs AMD technicals',
    'Best breakout setups this week',
    'What does the Fear & Greed index say?',
    'Explain the GEX for SPY',
    'Any insider buying signals?',
];

const HISTORY_KEY = 'mp_chat_history';
const CONV_ID_KEY = 'mp_chat_conv_id';
const MSG_PREFIX = 'mp_chat_msgs_';
const MAX_STORED_MSGS = 50;
const MAX_STORED_CONVOS = 10;

/* ─── Helpers ─── */

/** Simple markdown-to-HTML renderer for common patterns */
function renderMarkdown(text: string): string {
    let html = text
        .replace(/```([\s\S]*?)```/g, '<pre class="code-block">$1</pre>')
        .replace(/`([^`]+)`/g, '<span class="inline-code">$1</span>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`);
    html = html.replace(/\n/g, '<br/>');
    return html;
}

function getVerdictColor(verdict: string): string {
    const v = (verdict || '').toUpperCase();
    if (v.includes('STRONG_BUY')) return 'var(--accent-green)';
    if (v.includes('BUY')) return 'hsl(145, 60%, 50%)';
    if (v.includes('STRONG_SELL')) return 'var(--accent-red)';
    if (v.includes('SELL')) return 'hsl(0, 60%, 55%)';
    return 'var(--accent-amber)';
}

/* ─── DataCard Component ─── */

function DataCard({ data }: { data: Record<string, any> }) {
    const [expanded, setExpanded] = useState(false);
    const entries = Object.entries(data);
    const preview = entries.slice(0, 4);
    const rest = entries.slice(4);

    return (
        <div className="data-card">
            <div className="data-card-grid">
                {preview.map(([k, v]) => (
                    <div key={k} className="data-card-item">
                        <span className="data-card-label">{k.replace(/_/g, ' ')}</span>
                        <span className="data-card-value">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                    </div>
                ))}
            </div>
            {rest.length > 0 && (
                <>
                    <button type="button" className="data-card-toggle" onClick={() => setExpanded(!expanded)}>
                        {expanded ? (
                            <>
                                <ChevronUp size={12} /> Hide
                            </>
                        ) : (
                            <>
                                <ChevronDown size={12} /> +{rest.length} more
                            </>
                        )}
                    </button>
                    {expanded && (
                        <div className="data-card-expanded">
                            <div className="data-card-grid">
                                {rest.map(([k, v]) => (
                                    <div key={k} className="data-card-item">
                                        <span className="data-card-label">{k.replace(/_/g, ' ')}</span>
                                        <span className="data-card-value">
                                            {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

/* ─── ToolChips Component ─── */

function ToolChips({ tools }: { tools: string[] }) {
    const [expanded, setExpanded] = useState(false);

    return (
        <span className="chat-tools-area">
            <button type="button" className="chat-tools-badge" onClick={() => setExpanded(!expanded)}>
                <Wrench size={10} /> {tools.length} tools
                {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
            </button>
            {expanded && (
                <div className="tool-chips">
                    {tools.map((t, i) => (
                        <span key={i} className="tool-chip">
                            {t}
                        </span>
                    ))}
                </div>
            )}
        </span>
    );
}

/* ─── VerdictCard Component ─── */

function VerdictCard({ data }: { data: any }) {
    if (!data?.verdict) return null;
    const color = getVerdictColor(data.verdict);
    return (
        <div className="verdict-card" style={{ borderColor: color }}>
            <div className="verdict-header">
                <span className="verdict-ticker">{data.ticker}</span>
                <span className="verdict-badge" style={{ background: color }}>
                    {data.verdict?.replace(/_/g, ' ')}
                </span>
            </div>
            {data.confidence != null && (
                <div className="verdict-confidence">
                    Confidence: <strong>{data.confidence}%</strong>
                </div>
            )}
            {data.summary && <p className="verdict-summary">{data.summary}</p>}
        </div>
    );
}

/* ─── Main Chat Component ─── */

export default function Chat() {
    const WELCOME_MSG: Message = {
        role: 'assistant',
        content:
            'Welcome to **Bubby Vision AI**! I have access to 80+ analysis tools covering technical analysis, options flow, sentiment, news, insider trades, pattern detection, and Gemini Vision AI. Select an agent or just ask away!',
        timestamp: new Date(),
    };

    // Restore persisted conversation ID (localStorage for instant paint)
    const [conversationId, setConversationId] = useState<string | undefined>(() => {
        try {
            return localStorage.getItem(CONV_ID_KEY) || undefined;
        } catch {
            return undefined;
        }
    });

    // Restore persisted messages (localStorage for instant paint, API hydrates after)
    const [messages, setMessages] = useState<Message[]>(() => {
        try {
            const savedConvId = localStorage.getItem(CONV_ID_KEY);
            if (savedConvId) {
                const savedMsgs = localStorage.getItem(MSG_PREFIX + savedConvId);
                if (savedMsgs) {
                    const parsed = JSON.parse(savedMsgs);
                    return parsed.map((m: any) => ({ ...m, timestamp: new Date(m.timestamp) }));
                }
            }
        } catch {
            /* ignore */
        }
        return [WELCOME_MSG];
    });

    const [input, setInput] = useState('');
    const [selectedAgent, setSelectedAgent] = useState<AgentKey>('auto');
    const [dashboardTicker, setDashboardTicker] = useState('');
    const [showHistory, setShowHistory] = useState(false);
    const [history, setHistory] = useState<ConversationEntry[]>(() => {
        try {
            const saved = localStorage.getItem(HISTORY_KEY);
            return saved ? JSON.parse(saved) : [];
        } catch {
            return [];
        }
    });

    // Hydrate conversation list from API on mount (overrides localStorage)
    useEffect(() => {
        conversationApi
            .list()
            .then((res) => {
                const apiConvos: ConversationEntry[] = (res.data?.conversations || []).map((c: any) => ({
                    id: c.id,
                    title: c.title,
                    timestamp: (c.timestamp || 0) * 1000,
                    messageCount: c.message_count || 0,
                }));
                if (apiConvos.length > 0) {
                    setHistory(apiConvos);
                    try {
                        localStorage.setItem(HISTORY_KEY, JSON.stringify(apiConvos));
                    } catch {
                        /* ignore */
                    }
                }
            })
            .catch(() => {
                /* API unavailable — localStorage data stands */
            });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const bottomRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Save conversation to history + persist messages (API-first, localStorage as write-through)
    const saveToHistory = useCallback((id: string, msgs: Message[]) => {
        const userMsgs = msgs.filter((m) => m.role === 'user');
        if (userMsgs.length === 0) return;
        const title = userMsgs[0].content.slice(0, 50) + (userMsgs[0].content.length > 50 ? '…' : '');

        // Write-through to localStorage for instant restore on next load
        try {
            localStorage.setItem(CONV_ID_KEY, id);
            const toStore = msgs.slice(-MAX_STORED_MSGS).map((m) => ({
                ...m,
                timestamp: m.timestamp instanceof Date ? m.timestamp.toISOString() : m.timestamp,
            }));
            localStorage.setItem(MSG_PREFIX + id, JSON.stringify(toStore));
        } catch {
            /* quota exceeded */
        }

        // Persist to backend API (fire-and-forget)
        const apiMsgs = msgs.map((m) => ({
            role: m.role,
            content: m.content,
            agent: m.agent,
            tools: m.tools,
            timestamp: m.timestamp instanceof Date ? m.timestamp.toISOString() : String(m.timestamp),
        }));
        conversationApi.saveConversation(id, title, apiMsgs).catch(() => {
            /* API down — localStorage has it */
        });

        setHistory((prev) => {
            const updated = prev.filter((h) => h.id !== id);
            const entry: ConversationEntry = {
                id,
                title,
                timestamp: Date.now(),
                messageCount: msgs.length,
            };
            const newHistory = [entry, ...updated].slice(0, MAX_STORED_CONVOS);
            try {
                localStorage.setItem(HISTORY_KEY, JSON.stringify(newHistory));
            } catch {
                /* ignore */
            }
            return newHistory;
        });
    }, []);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, []);

    // ── useMutation for chat send ──
    const chatMutation = useMutation({
        mutationFn: async ({ msg, userMsg }: { msg: string; userMsg: Message }) => {
            const agentParam = selectedAgent === 'auto' ? undefined : selectedAgent;
            const res = await chatApi.send(msg, conversationId, agentParam);
            return { d: res.data, userMsg };
        },
        onSuccess: ({ d, userMsg }) => {
            if (d?.conversation_id) setConversationId(d.conversation_id);
            const reply = d?.response || d?.message || d?.content || (typeof d === 'string' ? d : JSON.stringify(d));
            let verdict: any;
            try {
                if (typeof reply === 'string' && reply.includes('"verdict"')) {
                    const jsonMatch = reply.match(/\{[\s\S]*"verdict"[\s\S]*\}/);
                    if (jsonMatch) verdict = JSON.parse(jsonMatch[0]);
                }
            } catch {
                /* ignore */
            }
            const newMsgs: Message[] = [
                ...messages,
                userMsg,
                {
                    role: 'assistant',
                    content: reply,
                    timestamp: new Date(),
                    agent: d?.agent_used || undefined,
                    tools: d?.tools_called || undefined,
                    data: d?.data || undefined,
                    verdict,
                },
            ];
            setMessages(newMsgs.slice(1));
            if (d?.conversation_id) saveToHistory(d.conversation_id, newMsgs);
        },
        onError: () => {
            setMessages((prev) => [
                ...prev,
                {
                    role: 'assistant',
                    content: 'Sorry, I encountered an error. Please try again.',
                    timestamp: new Date(),
                },
            ]);
        },
        onSettled: () => {
            inputRef.current?.focus();
        },
    });

    const loading = chatMutation.isPending;

    const sendMessage = (text: string) => {
        const msg = text.trim();
        if (!msg || loading) return;
        const userMsg: Message = { role: 'user', content: msg, timestamp: new Date() };
        setMessages((prev) => [...prev, userMsg]);
        setInput('');
        chatMutation.mutate({ msg, userMsg });
    };

    const dashboardMutation = useMutation({
        mutationFn: async ({ ticker, userMsg }: { ticker: string; userMsg: Message }) => {
            const res = await chatApi.dashboard(ticker, conversationId);
            return { d: res.data, userMsg };
        },
        onSuccess: ({ d }) => {
            if (d?.conversation_id) setConversationId(d.conversation_id);
            const reply = d?.response || d?.message || d?.content || (typeof d === 'string' ? d : JSON.stringify(d));
            let verdict: any;
            try {
                if (typeof reply === 'string' && reply.includes('"verdict"')) {
                    const jsonMatch = reply.match(/\{[\s\S]*"verdict"[\s\S]*\}/);
                    if (jsonMatch) verdict = JSON.parse(jsonMatch[0]);
                }
            } catch {
                /* ignore */
            }
            setMessages((prev) => [
                ...prev,
                {
                    role: 'assistant',
                    content: reply,
                    timestamp: new Date(),
                    agent: d?.agent_used || 'dashboard',
                    tools: d?.tools_called || undefined,
                    data: d?.data || undefined,
                    verdict,
                },
            ]);
        },
        onError: () => {
            setMessages((prev) => [
                ...prev,
                {
                    role: 'assistant',
                    content: 'Dashboard generation failed. Please try again.',
                    timestamp: new Date(),
                },
            ]);
        },
    });

    const sendDashboard = () => {
        const ticker = dashboardTicker.trim().toUpperCase();
        if (!ticker || loading) return;
        setDashboardTicker('');
        const userMsg: Message = {
            role: 'user',
            content: `📊 Decision Dashboard for **${ticker}**`,
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMsg]);
        dashboardMutation.mutate({ ticker, userMsg });
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        sendMessage(input);
    };

    const newConversation = () => {
        setMessages([
            {
                role: 'assistant',
                content: 'New conversation started. What would you like to analyze?',
                timestamp: new Date(),
            },
        ]);
        setConversationId(undefined);
        try {
            localStorage.removeItem(CONV_ID_KEY);
        } catch {
            /* ignore */
        }
    };

    const restoreConversation = (id: string) => {
        // Try API first, fall back to localStorage
        conversationApi
            .getMessages(id)
            .then((res) => {
                const apiMsgs = (res.data?.messages || []).map((m: any) => ({
                    ...m,
                    timestamp: new Date(m.timestamp),
                }));
                if (apiMsgs.length > 0) {
                    setMessages(apiMsgs);
                    setConversationId(id);
                    try {
                        localStorage.setItem(CONV_ID_KEY, id);
                    } catch {
                        /* ignore */
                    }
                    setShowHistory(false);
                    return;
                }
                // Fallback to localStorage if API returned empty
                _restoreFromLocal(id);
            })
            .catch(() => {
                _restoreFromLocal(id);
            });
    };

    const _restoreFromLocal = (id: string) => {
        try {
            const savedMsgs = localStorage.getItem(MSG_PREFIX + id);
            if (savedMsgs) {
                const parsed = JSON.parse(savedMsgs);
                setMessages(parsed.map((m: any) => ({ ...m, timestamp: new Date(m.timestamp) })));
                setConversationId(id);
                try {
                    localStorage.setItem(CONV_ID_KEY, id);
                } catch {
                    /* ignore */
                }
                setShowHistory(false);
            }
        } catch {
            /* ignore */
        }
    };

    const deleteHistory = (id: string) => {
        // Delete from API (fire-and-forget)
        conversationApi.delete(id).catch(() => {
            /* ignore */
        });

        setHistory((prev) => {
            const updated = prev.filter((h) => h.id !== id);
            try {
                localStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
            } catch {
                /* ignore */
            }
            return updated;
        });
        // Clean up stored messages from localStorage
        try {
            localStorage.removeItem(MSG_PREFIX + id);
        } catch {
            /* ignore */
        }
        // If we just deleted the active conversation, start a new one
        if (conversationId === id) {
            newConversation();
        }
    };

    const showQuickPrompts = useMemo(() => messages.length <= 1 && !loading, [messages.length, loading]);

    return (
        <div className="page-container chat-page">
            <h1 className="page-title">
                <MessageSquare size={28} /> AI Assistant
            </h1>

            <div className="chat-layout">
                {/* Conversation History Sidebar */}
                <div className={`chat-sidebar ${showHistory ? 'chat-sidebar--open' : ''}`}>
                    <div className="sidebar-header">
                        <span>History</span>
                        <button type="button" className="sidebar-close" onClick={() => setShowHistory(false)}>
                            <PanelLeftClose size={16} />
                        </button>
                    </div>
                    <button type="button" className="sidebar-new" onClick={newConversation}>
                        + New Conversation
                    </button>
                    <div className="sidebar-list">
                        {history.map((h) => (
                            <button
                                type="button"
                                key={h.id}
                                className={`sidebar-item ${conversationId === h.id ? 'sidebar-item--active' : ''}`}
                                onClick={() => restoreConversation(h.id)}
                            >
                                <div className="sidebar-item-title">{h.title}</div>
                                <div className="sidebar-item-meta">
                                    <Clock size={10} /> {new Date(h.timestamp).toLocaleDateString()}
                                    <span>{h.messageCount} msgs</span>
                                </div>
                                <button
                                    type="button"
                                    className="sidebar-item-delete"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        deleteHistory(h.id);
                                    }}
                                >
                                    <Trash2 size={12} />
                                </button>
                            </button>
                        ))}
                        {history.length === 0 && <div className="sidebar-empty">No conversations yet</div>}
                    </div>
                </div>

                {/* Main chat area */}
                <div className="chat-container card">
                    {/* Agent Selector Bar */}
                    <div className="agent-bar">
                        <button
                            type="button"
                            className="sidebar-toggle"
                            onClick={() => setShowHistory(!showHistory)}
                            title="Conversation history"
                        >
                            <PanelLeft size={16} />
                        </button>
                        <div className="agent-pills">
                            {AGENTS.map((a) => (
                                <button
                                    type="button"
                                    key={a.key}
                                    className={`agent-pill ${selectedAgent === a.key ? 'agent-pill--active' : ''}`}
                                    onClick={() => setSelectedAgent(a.key)}
                                >
                                    {a.icon} {a.label}
                                </button>
                            ))}
                        </div>
                        {/* Dashboard trigger */}
                        <div className="dashboard-trigger">
                            <input
                                type="text"
                                className="dashboard-input"
                                placeholder="Ticker…"
                                value={dashboardTicker}
                                onChange={(e) => setDashboardTicker(e.target.value.toUpperCase())}
                                onKeyDown={(e) => e.key === 'Enter' && sendDashboard()}
                                disabled={loading}
                            />
                            <button
                                type="button"
                                className="btn btn-sm dashboard-btn"
                                onClick={sendDashboard}
                                disabled={loading || !dashboardTicker.trim()}
                                title="Generate Decision Dashboard"
                            >
                                <LayoutDashboard size={14} /> Dashboard
                            </button>
                        </div>
                    </div>

                    {/* Messages */}
                    <div className="chat-messages">
                        {messages.map((m, i) => (
                            <div key={i} className={`chat-msg chat-msg--${m.role}`}>
                                <div className="chat-msg-avatar">
                                    {m.role === 'assistant' ? <Sparkles size={16} /> : <User size={16} />}
                                </div>
                                <div className="chat-msg-bubble">
                                    <div
                                        className="chat-msg-content"
                                        dangerouslySetInnerHTML={{
                                            __html: renderMarkdown(m.content),
                                        }}
                                    />
                                    {/* Verdict Card */}
                                    {m.verdict && <VerdictCard data={m.verdict} />}
                                    {/* Expandable data card */}
                                    {m.data && typeof m.data === 'object' && Object.keys(m.data).length > 0 && (
                                        <DataCard data={m.data} />
                                    )}
                                    {/* Agent/tool metadata */}
                                    <div className="chat-msg-meta">
                                        <span className="chat-msg-time">
                                            {m.timestamp.toLocaleTimeString([], {
                                                hour: '2-digit',
                                                minute: '2-digit',
                                            })}
                                        </span>
                                        {m.agent && <span className="badge badge-blue">{m.agent}</span>}
                                        {m.tools && m.tools.length > 0 && <ToolChips tools={m.tools} />}
                                    </div>
                                </div>
                            </div>
                        ))}

                        {/* Typing indicator */}
                        {loading && (
                            <div className="chat-msg chat-msg--assistant">
                                <div className="chat-msg-avatar">
                                    <Sparkles size={16} />
                                </div>
                                <div className="chat-msg-bubble">
                                    <div className="chat-typing">
                                        <span />
                                        <span />
                                        <span />
                                    </div>
                                </div>
                            </div>
                        )}
                        <div ref={bottomRef} />
                    </div>

                    {/* Quick Prompts */}
                    {showQuickPrompts && (
                        <div className="chat-quick-prompts">
                            {QUICK_PROMPTS.map((p, i) => (
                                <button type="button" key={i} className="quick-prompt" onClick={() => sendMessage(p)}>
                                    {p}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Input */}
                    <form className="chat-input-bar" onSubmit={handleSubmit}>
                        <input
                            ref={inputRef}
                            className="chat-input"
                            type="text"
                            placeholder={`Ask Bubby Vision AI (${AGENTS.find((a) => a.key === selectedAgent)?.label} mode)…`}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            disabled={loading}
                        />
                        <button className="btn btn-primary" type="submit" disabled={loading || !input.trim()}>
                            <Send size={16} />
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}
