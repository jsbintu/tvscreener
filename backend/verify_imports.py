"""
Bubby Vision — Full Import Verification
Tests that every engine, tool set, and route module imports cleanly.
"""
import sys
import traceback

results = []

def test_import(label, import_fn):
    try:
        import_fn()
        results.append(("PASS", label))
        print(f"  PASS {label}")
    except Exception as e:
        results.append(("FAIL", label, str(e)))
        print(f"  FAIL {label}")
        traceback.print_exc()

print("=" * 60)
print("BUBBY VISION — FULL IMPORT VERIFICATION")
print("=" * 60)

# -- Engines --
print("\n-- Engines --")
test_import("data_engine",        lambda: __import__("app.engines.data_engine", fromlist=["DataEngine"]))
test_import("ta_engine",          lambda: __import__("app.engines.ta_engine", fromlist=["TAEngine"]))
test_import("options_engine",     lambda: __import__("app.engines.options_engine", fromlist=["OptionsEngine"]))
test_import("risk_engine",        lambda: __import__("app.engines.risk_engine", fromlist=["RiskEngine"]))
test_import("breakout_engine",    lambda: __import__("app.engines.breakout_engine", fromlist=["BreakoutEngine"]))
test_import("pattern_engine",     lambda: __import__("app.engines.pattern_engine", fromlist=["PatternEngine"]))
test_import("vision_engine",      lambda: __import__("app.engines.vision_engine", fromlist=["VisionEngine"]))
test_import("chart_engine",       lambda: __import__("app.engines.chart_engine", fromlist=["ChartEngine"]))
test_import("accuracy_engine",    lambda: __import__("app.engines.accuracy_engine", fromlist=["AccuracyEngine"]))
test_import("backtest_engine",    lambda: __import__("app.engines.backtest_engine", fromlist=["BacktestEngine"]))
test_import("alert_engine",       lambda: __import__("app.engines.alert_engine", fromlist=["AlertEngine"]))
test_import("alert_chain_engine", lambda: __import__("app.engines.alert_chain_engine", fromlist=["AlertChainEngine"]))
test_import("trends_engine",      lambda: __import__("app.engines.trends_engine", fromlist=["TrendsEngine"]))
test_import("coaching_engine",    lambda: __import__("app.engines.coaching_engine", fromlist=["CoachingEngine"]))
test_import("opening_range_engine", lambda: __import__("app.engines.opening_range_engine", fromlist=["OpeningRangeEngine"]))
test_import("ghost_chart_engine", lambda: __import__("app.engines.ghost_chart_engine", fromlist=["GhostChartEngine"]))
test_import("optimizer_engine",   lambda: __import__("app.engines.optimizer_engine", fromlist=["OptimizerEngine"]))

# -- Agent Tools --
print("\n-- Agent Tools --")
test_import("tools (ALL_TOOLS)",  lambda: __import__("app.agents.tools", fromlist=["ALL_TOOLS"]))
test_import("prompts",            lambda: __import__("app.agents.prompts", fromlist=["SYSTEM_PROMPT"]))

# -- Routes --
print("\n-- Routes --")
test_import("routes (main)",      lambda: __import__("app.routes", fromlist=["data_router"]))
test_import("routes_market",      lambda: __import__("app.routes_market", fromlist=["market_router"]))

# -- Tasks --
print("\n-- Tasks --")
test_import("celery_app",         lambda: __import__("app.tasks.celery_app", fromlist=["celery_app"]))
test_import("optimizer_tasks",    lambda: __import__("app.tasks.optimizer_tasks", fromlist=["run_weekly_optimization"]))

# -- Config + Models --
print("\n-- Config + Models --")
test_import("config",             lambda: __import__("app.config", fromlist=["get_settings"]))
test_import("models",             lambda: __import__("app.models", fromlist=["OHLCV"]))

# -- Summary --
print("\n" + "=" * 60)
passed = sum(1 for r in results if r[0] == "PASS")
failed = sum(1 for r in results if r[0] == "FAIL")
print(f"RESULTS: {passed} passed, {failed} failed out of {len(results)} total")
if failed:
    print("\nFAILURES:")
    for r in results:
        if r[0] == "FAIL":
            print(f"  FAIL {r[1]}: {r[2]}")
    sys.exit(1)
else:
    print("ALL IMPORTS CLEAN")
    sys.exit(0)
