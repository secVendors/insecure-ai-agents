import os
import requests
import numpy as np
import pandas as pd
import json
from typing import Optional
from tqdm import tqdm
from tabulate import tabulate
from datasets import load_dataset


def guard_score(prompt: str) -> dict:
    """Makes requests to the Lakera Guard API for flagged status and detailed results."""
    lakera_client = requests.Session()
    lakera_client.headers.update({
        'Authorization': f'Bearer {os.getenv("LAKERA_GUARD_API_KEY")}'
    })

    try:
        # First call to the guard endpoint to determine if the content is flagged
        guard_response = lakera_client.post(
            "https://api.lakera.ai/v2/guard",
            json={"messages": [{"role": "user", "content": prompt}]}
        )
        guard_data = guard_response.json()
        is_flagged = guard_data.get("flagged", False)

        # If the prompt was flagged, make a second call to /guard/results for more details
        results_data = []
        if guard_response.status_code == 200:
            results_response = lakera_client.post(
                "https://api.lakera.ai/v2/guard/results",
                json={"messages": [{"role": "user", "content": prompt}]}
            )
            if results_response.status_code == 200:
                results_data = results_response.json().get("results", [])

        return {"flagged": is_flagged, "results": results_data}
    except Exception as e:
        print(f"Error occurred: {e}")
        return {"flagged": False, "results": []}  # Return default structure in case of failure


def get_highest_severity(results, detector_prefix):
    """Finds the highest severity result for a given detector type."""
    # Levels are sorted by severity, with l1 being the highest severity
    severity_order = ["l1_confident", "l2_likely", "l3_possible", "l4_unsure", "l5_unlikely"]
    highest_severity = "l5_unlikely"  # Start with the least severe result

    for res in results:
        if res["detector_type"].startswith(detector_prefix):
            result = res["result"]
            if severity_order.index(result) < severity_order.index(highest_severity):
                highest_severity = result

    return highest_severity


def eval_guard(df: pd.DataFrame, max_size: Optional[int] = None):
    """Computes detection metrics on the input DataFrame for the /guard endpoint and prints incorrect results."""

    predictions, labels = [], []
    incorrect_results = []

    max_size = max_size if max_size is not None else len(df)

    # Evaluate the first prompt and print out the response
    first_prompt = df.iloc[0]["prompt"]
    expected_label = df.iloc[0]["label"]

    # Make a request for the first prompt
    try:
        response = guard_score(first_prompt)
        is_flagged = response.get("flagged", False)

        # Print details for the first prompt
        print("First Prompt being sent to Lakera Guard:")
        print(f"Prompt: {first_prompt}")
        print(f"Lakera Guard Response: {'True' if is_flagged else 'False'}\n")

        # Record the result for the first prompt
        predictions.append(is_flagged)
        labels.append(expected_label)

        # Track incorrect results for future inspection
        if is_flagged != expected_label:
            incorrect_results.append({
                "prompt": first_prompt,
                "expected_label": expected_label,
                "predicted_flagged": is_flagged,
                "results": response.get("results", [])
            })

    except Exception as e:
        print(f"Error occurred: {e}")

    # Iterate over the dataset with a progress bar (starting from the second prompt)
    for _, row in tqdm(df.head(max_size).iloc[1:].iterrows(), total=max_size-1, desc="Evaluating prompts"):
        prompt = row.text
        expected_label = row.label
        response = guard_score(prompt)
        is_flagged = response.get("flagged", False)

        predictions.append(is_flagged)
        labels.append(expected_label)

        # Track incorrect results for future inspection
        if is_flagged != expected_label:
            incorrect_results.append({
                "prompt": prompt,
                "expected_label": expected_label,
                "predicted_flagged": is_flagged,
                "results": response.get("results", [])
            })

    predictions = np.array(predictions)
    labels = np.array(labels)

    false_positives = np.sum((predictions == 1) & (labels == 0))
    false_negatives = np.sum((predictions == 0) & (labels == 1))
    total_prompts = len(predictions)

    accuracy = np.mean(predictions == labels)
    false_positive_rate = (false_positives / (false_positives + np.sum(labels == 0))) if np.sum(labels == 0) > 0 else 0

    # Create and print evaluation metrics as a formatted table using tabulate
    metrics_data = [
        ["Total Prompts Sent", total_prompts],
        ["Accuracy", f"{accuracy * 100:.2f}%"],
        ["False Positive Rate", f"{false_positive_rate * 100:.2f}%"],
        ["Total False Positives", false_positives],
        ["Total False Negatives", false_negatives]
    ]

    print("\nEvaluation Metrics:")
    print(tabulate(metrics_data, headers=["Metric", "Value"], tablefmt="pretty", colalign=("left", "left")))

    # Print the incorrect results as a formatted table using tabulate
    if incorrect_results:
        table_data = []
        for result in incorrect_results:
            # Get the highest severity level for each relevant detector type
            prompt_attack_result = get_highest_severity(result["results"], "prompt_attack")
            moderated_content_result = get_highest_severity(result["results"], "moderated_content")
            pii_result = get_highest_severity(result["results"], "pii")
            unknown_links_result = get_highest_severity(result["results"], "unknown_links")

            # Add the row data
            table_data.append([
                result['prompt'],
                'True' if result['expected_label'] == 1 else 'False',
                'True' if result['predicted_flagged'] else 'False',
                prompt_attack_result,
                moderated_content_result,
                pii_result,
                unknown_links_result
            ])

        headers = ["Prompt", "Expected Response", "Lakera Guard Response", "Prompt Attacks", "Moderated Content", "PII", "Unknown Links"]
        print("\nIncorrect Results:")
        print(tabulate(table_data, headers=headers, tablefmt="pretty", colalign=("left", "left", "left", "left", "left", "left", "left")))
    else:
        print("\nNo incorrect results found.")


def load_and_test_dataset():
    ds_name = "Lakera/gandalf_ignore_instructions"

    data = load_dataset(ds_name)
    df = pd.DataFrame(data["test"])
    df["label"] = 1

    for _, row in df.head(5).iterrows():
        print(row.text)

    eval_guard(df, max_size=100)


def main():
    load_and_test_dataset()


if __name__ == '__main__':
    main()
