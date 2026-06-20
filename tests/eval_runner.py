# -*- coding: utf-8 -*-
"""Evaluation runner for the Zhang Xuefeng Knowledge Distillation Agent.

Loads golden_dataset.json and runs each evaluation case against the safety
gateway, FTS5 search, ChromaDB search, and intent router.

Modes:
  --mock (default):  Use deterministic keyword-based mock router.
  --live:            Use real LLM for routing (requires API key).
  --seed:            Run seed data script before evaluation.

Output:
  eval_report.json + human-readable summary printed to stdout.

Usage:
    python tests/eval_runner.py                  # mock mode
    python tests/eval_runner.py --live           # live LLM mode
    python tests/eval_runner.py --seed           # seed then evaluate
"""
from __future__ import annotations

import json, os, sys, time, argparse
from typing import Any

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_ROOT = os.path.join(_PROJECT_ROOT, 'src')
_TESTS_DIR = os.path.join(_PROJECT_ROOT, 'tests')
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

from src.config import load_config
from src.safety.input_gateway import InputSafetyGateway
from src.knowledge.sqlite_store import get_db, init_db, fts5_search
from src.knowledge.chroma_store import get_chroma_collection, query_chunks

# =============================================================================
# Mock router (deterministic keyword-based classification)
# =============================================================================

def mock_router(user_msg: str) -> dict:
    """Keyword-based router for offline evaluation.

    Classifies the user message into a scene without calling an LLM.
    This gives deterministic results suitable for regression testing.
    """
    msg = user_msg.lower()

    # Volunteer signals: score + subject/location
    volunteer_kw = ['分', '志愿', '推荐', '择校', '分数线', '排名', '录取',
                    '一本', '二本', '985', '211', '双一流', '选科']
    volunteer_score = sum(1 for kw in volunteer_kw if kw in msg)

    # Opinion signals: asks for opinion/view on a topic
    opinion_kw = ['值得', '怎么样', '怎么看', '看法', '评价', '分析', '前景',
                  '还行吗', '好不好', '有前途', '坑', '劝退', '避雷']
    opinion_score = sum(1 for kw in opinion_kw if kw in msg)

    # Style chat signals: emotional/personal messages
    chat_kw = ['考砸', '迷茫', '焦虑', '怎么办', '不知道', '安慰', '鼓励',
               '心态', '放弃', '坚持', '后悔', '难过', '压力', '睡不着',
               '张老师', '雪峰老师']
    chat_score = sum(1 for kw in chat_kw if kw in msg)

    # General fallback
    general_kw = ['天气', '吃饭', '今天', '明天', '时间', '日期', '你好']
    general_score = sum(1 for kw in general_kw if kw in msg)

    scores = {
        'volunteer': volunteer_score,
        'opinion': opinion_score,
        'style_chat': chat_score,
        'general': general_score,
    }
    best_scene = max(scores, key=scores.get)
    best_score = scores[best_scene]
    total = sum(scores.values()) or 1
    confidence = best_score / total if best_score > 0 else 0.3

    return {'scene': best_scene, 'confidence': round(confidence, 2)}


# =============================================================================
# Eval helpers
# =============================================================================

def load_golden_dataset(path: str) -> list[dict]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def evaluate_safety(gateway: InputSafetyGateway, case: dict) -> dict:
    """Run a single case through the safety gateway."""
    result = gateway.check(case['query'])
    passed = result['safe'] == case.get('expected_safe', True)
    if not case.get('expected_safe', True):
        # For blocked messages, also check the expected category if specified
        if 'expected_category' in case and result.get('category') != case.get('expected_category'):
            passed = False
    return {
        'case_id': case['id'],
        'component': 'safety',
        'passed': passed,
        'actual': {
            'safe': result['safe'],
            'category': result.get('category', ''),
            'reason': result.get('reason', ''),
        },
        'expected': {
            'safe': case.get('expected_safe', True),
            'category': case.get('expected_category', ''),
        },
    }


def evaluate_fts5_search(conn, case: dict) -> dict:
    """Run a single case through FTS5 search."""
    query = case['query']
    results = fts5_search(conn, query, limit=10)
    min_expected = case.get('min_search_results', 0)
    passed = len(results) >= min_expected
    return {
        'case_id': case['id'],
        'component': 'fts5_search',
        'passed': passed,
        'actual': {
            'result_count': len(results),
            'top_topics': [r.get('topic', '') for r in results[:3]],
        },
        'expected': {
            'min_results': min_expected,
            'keywords': case.get('search_keywords', []),
        },
    }


def evaluate_chroma_search(collection, case: dict) -> dict:
    """Run a single case through ChromaDB/NumpyCollection search."""
    query = case['query']
    results = query_chunks(collection, query, top_k=5)
    min_expected = case.get('min_search_results', 0)
    passed = len(results) >= min_expected
    return {
        'case_id': case['id'],
        'component': 'chroma_search',
        'passed': passed,
        'actual': {
            'result_count': len(results),
            'top_distances': [round(r.get('distance', 0), 4) for r in results[:3]],
        },
        'expected': {
            'min_results': min_expected,
            'keywords': case.get('search_keywords', []),
        },
    }

def evaluate_routing(router_fn, case: dict) -> dict:
    """Run a single case through the intent router."""
    if case.get('category') != 'routing':
        return {
            'case_id': case['id'],
            'component': 'routing',
            'passed': True,
            'actual': {'scene': 'n/a', 'confidence': 0},
            'expected': {'scene': 'n/a'},
            'skipped': True,
            'reason': 'not a routing test case',
        }
    result = router_fn(case['query'])
    expected_scene = case.get('expected_scene', 'general')
    min_conf = case.get('min_confidence', 0.5)
    scene_match = result['scene'] == expected_scene
    conf_ok = result.get('confidence', 0) >= min_conf
    passed = scene_match and conf_ok
    return {
        'case_id': case['id'],
        'component': 'routing',
        'passed': passed,
        'actual': {
            'scene': result['scene'],
            'confidence': result.get('confidence', 0),
        },
        'expected': {
            'scene': expected_scene,
            'min_confidence': min_conf,
        },
    }


def generate_report(results: list[dict], elapsed_s: float,
                    mode: str, dataset_path: str) -> dict:
    """Generate a structured evaluation report."""
    total = len(results)
    passed = sum(1 for r in results if r.get('passed', False))
    skipped = sum(1 for r in results if r.get('skipped', False))
    evaluated = total - skipped
    passed_evaluated = sum(
        1 for r in results if r.get('passed', False) and not r.get('skipped', False)
    )
    by_component = {}
    for r in results:
        comp = r['component']
        if comp not in by_component:
            by_component[comp] = {'total': 0, 'passed': 0, 'skipped': 0}
        by_component[comp]['total'] += 1
        if r.get('skipped'):
            by_component[comp]['skipped'] += 1
        elif r.get('passed'):
            by_component[comp]['passed'] += 1

    return {
        'meta': {
            'mode': mode,
            'dataset': dataset_path,
            'elapsed_seconds': round(elapsed_s, 2),
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        },
        'summary': {
            'total_cases': total,
            'total_checks': total,  # one check per component per case
            'passed': passed,
            'failed': evaluated - passed_evaluated,
            'skipped': skipped,
            'pass_rate': round(passed_evaluated / evaluated * 100, 1) if evaluated else 0,
        },
        'by_component': by_component,
        'details': results,
    }


def print_summary(report: dict) -> None:
    """Print a human-readable evaluation summary."""
    s = report['summary']
    meta = report['meta']
    print()
    print('=' * 60)
    print('  Zhang Xuefeng Agent - Evaluation Report')
    print('=' * 60)
    print(f"  Mode:      {meta['mode']}")
    print(f"  Dataset:   {meta['dataset']}")
    print(f"  Duration:  {meta['elapsed_seconds']}s")
    print(f"  Timestamp: {meta['timestamp']}")
    print('-' * 60)
    print(f"  Cases:     {s['total_cases']}")
    print(f"  Checks:    {s['total_checks']}")
    print(f"  Passed:    {s['passed']}")
    print(f"  Failed:    {s['failed']}")
    print(f"  Skipped:   {s['skipped']}")
    print(f"  Pass Rate: {s['pass_rate']}%")
    print('-' * 60)
    print('  By Component:')
    for comp, stats in sorted(report['by_component'].items()):
        ev = stats['total'] - stats['skipped']
        pr = round(stats['passed'] / ev * 100, 1) if ev else 0
        print(f"    {comp:20s}  {stats['passed']}/{ev} passed ({pr}%)")
    print('-' * 60)
    print('  Failures:')
    failures = [r for r in report['details']
                if not r.get('passed') and not r.get('skipped')]
    if failures:
        for f_ in failures:
            expected = f_.get('expected', {})
            actual = f_.get('actual', {})
            print(f"    [{f_['case_id']}] {f_['component']}: "
                  f"expected={expected}, actual={actual}")
    else:
        print('    (none)')
    print('=' * 60)


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Zhang Xuefeng Agent Evaluation Runner'
    )
    parser.add_argument(
        '--live', action='store_true',
        help='Use real LLM for routing (requires API key)',
    )
    parser.add_argument(
        '--seed', action='store_true',
        help='Run seed data script before evaluation',
    )
    parser.add_argument(
        '--dataset', type=str,
        default=os.path.join(_TESTS_DIR, 'golden_dataset.json'),
        help='Path to golden dataset JSON',
    )
    parser.add_argument(
        '--output', type=str,
        default=os.path.join(_TESTS_DIR, 'eval_report.json'),
        help='Path to output report JSON',
    )
    parser.add_argument(
        '--sqlite-path', type=str, default='data/zhangxuefeng.db',
        help='SQLite database path',
    )
    parser.add_argument(
        '--chroma-dir', type=str, default='data/chroma_db',
        help='ChromaDB persist directory',
    )
    args = parser.parse_args()

    # Seed if requested
    if args.seed:
        print('[eval] Running seed data script...')
        import subprocess
        seed_script = os.path.join(_PROJECT_ROOT, 'scripts', 'seed_data.py')
        subprocess.run(
            [sys.executable, seed_script,
             '--sqlite-path', args.sqlite_path,
             '--chroma-dir', args.chroma_dir,
             '--clear'],
            check=True,
            cwd=_PROJECT_ROOT,
        )

    # Load config and init services
    config = load_config()
    config.sqlite_path = args.sqlite_path
    config.chroma_persist_dir = args.chroma_dir

    conn = get_db(config)
    init_db(conn)

    collection = get_chroma_collection(config)
    safety = InputSafetyGateway()
    dataset = load_golden_dataset(args.dataset)

    # Choose router
    if args.live:
        print('[eval] Live LLM mode - attempting to load real router...')
        from src.agent.router import classify_intent

        def _live_llm(system_prompt, user_msg):
            from app import call_llm_sync
            return call_llm_sync(system_prompt, user_msg)

        router_fn = lambda msg: classify_intent(_live_llm, msg)
        mode = 'live'
    else:
        print('[eval] Mock mode - using keyword-based router')
        router_fn = mock_router
        mode = 'mock'

    # Run evaluations
    print(f'[eval] Loaded {len(dataset)} cases from {args.dataset}')
    print(f'[eval] Running evaluations...')
    t0 = time.time()
    eval_results: list[dict] = []

    for case in dataset:
        case_id = case['id']
        # Safety check (always applicable)
        eval_results.append(evaluate_safety(safety, case))
        # FTS5 search
        eval_results.append(evaluate_fts5_search(conn, case))
        # ChromaDB search
        eval_results.append(evaluate_chroma_search(collection, case))
        # Routing (if applicable)
        eval_results.append(evaluate_routing(router_fn, case))

    elapsed = time.time() - t0

    # Generate and print report
    report = generate_report(eval_results, elapsed, mode, args.dataset)
    print_summary(report)

    # Write report file
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'\n[eval] Report written to {args.output}')

    conn.close()

    # Exit with non-zero if any failures
    if report['summary']['failed'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
