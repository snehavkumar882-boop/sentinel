
"""Evaluate Sentinel's Phase 4 semantic retrieval quality."""

import sys
from pathlib import Path
from time import perf_counter

# Add the project root to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.knowledge.knowledge_base import KnowledgeBase


EVALUATION_CASES = [
    {
        "name": "Database connection pool saturation",
        "query": "database connection pool saturation",
        "relevant_sources": {
            "runbooks/RUNBOOK-DB-002-connection-pool-saturation.md",
            "historical_incidents/INC-2024-03-12-connection-pool-exhaustion.md",
        },
    },
    {
        "name": "High API 5xx error rate",
        "query": "high API 5xx error rate",
        "relevant_sources": {
            "runbooks/RUNBOOK-API-001-high-5xx-rate.md",
        },
    },
    {
        "name": "Memory exhaustion",
        "query": "memory exhaustion and out of memory",
        "relevant_sources": {
            "historical_incidents/INC-2023-07-19-memory-leak-oom.md",
            "runbooks/RUNBOOK-INFRA-003-cpu-memory-exhaustion.md",
        },
    },
    {
        "name": "Upstream payment gateway timeout",
        "query": "upstream payment gateway timeout",
        "relevant_sources": {
            "historical_incidents/INC-2023-10-04-upstream-gateway-timeout.md",
        },
    },
    {
        "name": "Unrelated payroll query",
        "query": "employee payroll tax filing",
        "relevant_sources": set(),
    },
]


def main() -> None:
    kb = KnowledgeBase()

    print("=" * 75)
    print("SENTINEL RAG EVALUATION")
    print("=" * 75)

    print("\nKnowledge Base Status")
    print(kb.get_status())

    operational_cases = [
        case for case in EVALUATION_CASES
        if case["relevant_sources"]
    ]

    top1_hits = 0
    successful_queries = 0
    relevant_results = 0
    total_results = 0
    rejected_distractors = 0
    total_latency_ms = 0.0

    print("\nQUERY RESULTS")

    for case in EVALUATION_CASES:
        start = perf_counter()
        results = kb.search(case["query"], top_k=5)
        latency_ms = (perf_counter() - start) * 1000
        total_latency_ms += latency_ms

        expected = case["relevant_sources"]

        matching_results = [
            result for result in results
            if result["source_path"] in expected
        ]

        if expected:
            if matching_results:
                successful_queries += 1

            relevant_results += len(matching_results)
            total_results += len(results)

            if results and results[0]["source_path"] in expected:
                top1_hits += 1

        elif not results:
            rejected_distractors += 1

        print("\n" + "-" * 75)
        print("Case:", case["name"])
        print("Query:", case["query"])
        print("Latency:", round(latency_ms, 2), "ms")
        print("Results returned:", len(results))
        print("Relevant results:", len(matching_results))

        for rank, result in enumerate(results, start=1):
            is_relevant = result["source_path"] in expected

            print(
                f"{rank}. "
                f"{'RELEVANT' if is_relevant else 'OTHER'} | "
                f"{result['title']} | "
                f"{result['section']} | "
                f"similarity={result['similarity']:.4f}"
            )
            print("   Source:", result["source_path"])

    query_count = len(operational_cases)

    top1_rate = top1_hits / query_count if query_count else 0
    retrieval_rate = (
        successful_queries / query_count if query_count else 0
    )
    precision_at_5 = (
        relevant_results / total_results if total_results else 0
    )

    distractor_count = len(EVALUATION_CASES) - query_count
    distractor_rate = (
        rejected_distractors / distractor_count
        if distractor_count else 0
    )

    average_latency = total_latency_ms / len(EVALUATION_CASES)

    print("\n" + "=" * 75)
    print("EVALUATION SUMMARY")
    print("=" * 75)

    print(f"Operational queries: {query_count}")
    print(f"Top-1 hit rate: {top1_rate:.2%}")
    print(f"Top-5 retrieval success rate: {retrieval_rate:.2%}")
    print(f"Relevant-result precision@5: {precision_at_5:.2%}")
    print(f"Distractor rejection rate: {distractor_rate:.2%}")
    print(f"Average query latency: {average_latency:.2f} ms")

    print("\nTOP-K BEHAVIOUR")

    test_query = "database connection pool saturation"

    for k in (1, 3, 5):
        results = kb.search(test_query, top_k=k)
        print(f"top_k={k}: {len(results)} results returned")

    print("\nEvaluation complete.")
    print(
        "Note: This is a small, manually labelled internal evaluation "
        "set, not a general benchmark."
    )


if __name__ == "__main__":
    main()

