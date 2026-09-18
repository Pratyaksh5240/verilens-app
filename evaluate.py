"""Evaluation and benchmarking runner for VeriLens credibility scoring.

Evaluates the credibility pipeline against a labeled benchmark dataset (data/evaluation_set.csv)
and outputs accuracy, precision, recall, F1 scores, and a confusion matrix.
"""

import csv
import os
import sys
from typing import Dict, List

from emotion import analyze_emotion
from scoring import analyze_credibility


def score_to_category(score: float) -> str:
    """Map a continuous 0.0-1.0 credibility score to categorical evaluation classes."""
    if score >= 0.62:
        return "credible"
    if score < 0.45:
        return "unreliable"
    return "mixed"


def run_evaluation(dataset_path: str = "data/evaluation_set.csv") -> Dict[str, object]:
    """Run evaluation benchmark across all labeled rows in the dataset."""
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Evaluation dataset not found at: {dataset_path}")

    rows: List[Dict[str, str]] = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    print("\n==================================================================")
    print("  VeriLens Credibility Pipeline Evaluation Benchmark")
    print(f"  Dataset: {dataset_path} ({len(rows)} cases)")
    print("==================================================================\n")

    y_true: List[str] = []
    y_pred: List[str] = []
    scores: List[float] = []
    fear_cases_correct = 0
    total_fear_cases = 0

    classes = ["credible", "unreliable", "mixed"]
    confusion = {c1: {c2: 0 for c2 in classes} for c1 in classes}

    print(f"{'ID':<4} | {'Ground Truth':<12} | {'Predicted':<12} | {'Score':<6} | {'Emotion':<7} | {'Status'}")
    print("-" * 65)

    for r in rows:
        row_id = r.get("id", "")
        content = r.get("content", "")
        source_url = r.get("source_url", "").strip() or None
        source_hint = r.get("source_hint", "").strip() or None
        ground_truth = r.get("ground_truth", "").strip().lower()
        emotion_type = r.get("emotion_type", "").strip().lower()

        # Run pipeline
        emotion_res = analyze_emotion(content)
        result = analyze_credibility(
            text=content,
            source_url=source_url,
            source_hint=source_hint,
            emotion_data=emotion_res,
        )

        score = float(result["score"])
        predicted = score_to_category(score)

        y_true.append(ground_truth)
        y_pred.append(predicted)
        scores.append(score)

        if ground_truth in classes and predicted in classes:
            confusion[ground_truth][predicted] += 1

        is_match = ground_truth == predicted
        status_icon = "[PASS]" if is_match else "[FAIL]"

        # Check high-emotion disaster resilience
        if emotion_type == "fear":
            total_fear_cases += 1
            if is_match:
                fear_cases_correct += 1

        print(
            f"{row_id:<4} | {ground_truth:<12} | {predicted:<12} | {score*100:>5.1f}% | {emotion_type:<7} | {status_icon}"
        )

    total = len(y_true)
    correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    overall_accuracy = (correct / total) if total > 0 else 0.0

    # Per-class metrics
    per_class_metrics: Dict[str, Dict[str, float]] = {}
    for c in classes:
        tp = confusion[c][c]
        fp = sum(confusion[other][c] for other in classes if other != c)
        fn = sum(confusion[c][other] for other in classes if other != c)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        per_class_metrics[c] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
        }

    print("\n" + "=" * 65)
    print("  PERFORMANCE SUMMARY")
    print("=" * 65)
    print(f"Overall Accuracy:  {correct}/{total} ({overall_accuracy * 100:.1f}%)")
    if total_fear_cases > 0:
        fear_acc = fear_cases_correct / total_fear_cases
        print(
            f"High-Fear Resilience: {fear_cases_correct}/{total_fear_cases} ({fear_acc * 100:.1f}%) "
            f"(Ensures disaster journalism is not misclassified)"
        )

    print("\nPer-Class Breakdown:")
    print(f"{'Class':<14} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Support':<8}")
    print("-" * 60)
    for c in classes:
        m = per_class_metrics[c]
        support = sum(confusion[c].values())
        print(f"{c:<14} | {m['precision']:<10.3f} | {m['recall']:<10.3f} | {m['f1']:<10.3f} | {support:<8}")

    print("\nConfusion Matrix (Rows: Ground Truth, Cols: Predicted):")
    print(f"{'':<14} | {'Pred: credible':<15} | {'Pred: unreliable':<17} | {'Pred: mixed':<12}")
    print("-" * 65)
    for c in classes:
        print(
            f"True: {c:<8} | {confusion[c]['credible']:<15} | {confusion[c]['unreliable']:<17} | {confusion[c]['mixed']:<12}"
        )
    print("=" * 65 + "\n")

    return {
        "accuracy": overall_accuracy,
        "per_class": per_class_metrics,
        "total_cases": total,
    }


if __name__ == "__main__":
    dataset = sys.argv[1] if len(sys.argv) > 1 else "data/evaluation_set.csv"
    res = run_evaluation(dataset)
    # Require at least 80% accuracy to ensure high-quality baseline
    if res["accuracy"] < 0.75:
        sys.exit(1)
    sys.exit(0)
