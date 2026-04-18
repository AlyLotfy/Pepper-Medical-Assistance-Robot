import requests
import time
import csv
import os
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
import os as _os
def _load_env():
    import pathlib
    for p in pathlib.Path(__file__).parents:
        ef = p / ".env"
        if ef.exists():
            for line in open(ef):
                line=line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k,_,v=line.partition("=")
                    _os.environ.setdefault(k.strip(),v.strip())
            break
_load_env()

CLAUDE_API_KEY = _os.environ.get("CLAUDE_API_KEY", "")
CLAUDE_MODEL   = _os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
CLAUDE_URL     = "https://api.anthropic.com/v1/messages"

CSV_FILE    = "claude_benchmark_data.csv"
REPORT_FILE = "claude_performance_report.txt"

# Simulated patient prompts to test the AI's speed on different lengths of text
TEST_PROMPTS = [
    "Hello.",
    "What are the visiting hours?",
    "I have a severe headache and my blood pressure is high.",
    "Book an appointment with Doctor Ahmed in the cardiology department.",
    "Can you give me health tips for managing diabetes and hypertension at home?",
    "Where is the bathroom?",
    "I am feeling dizzy and nauseous, what should I do?",
    "Tell me about the pediatric services available in this hospital.",
    "How do I check in for my 3:00 PM appointment?",
    "Thank you for your help."
]

SYSTEM_PROMPT = "You are Pepper, a medical robot. Keep answers short (under 40 words)."

# ==========================================
# 1. TESTING FUNCTION
# ==========================================
def test_claude_api(prompt):
    """Sends a request to Claude Haiku and returns the latency in seconds."""
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 100,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}]
    }

    start_time = time.time()
    try:
        response = requests.post(CLAUDE_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        latency = time.time() - start_time
        return latency, True
    except requests.exceptions.RequestException as e:
        latency = time.time() - start_time
        print(f"[ERROR] Request failed: {e}")
        return latency, False

# ==========================================
# 2. RUN TEST SUITE
# ==========================================
def run_benchmark():
    print("====================================================")
    print("   STARTING CLAUDE HAIKU API BENCHMARK")
    print("====================================================\n")

    with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "Prompt", "Word_Count", "Latency_Sec", "Success"])

        for prompt in TEST_PROMPTS:
            print(f"Testing: '{prompt}'")
            latency, success = test_claude_api(prompt)
            word_count = len(prompt.split())

            writer.writerow([
                datetime.now().strftime("%H:%M:%S"),
                prompt,
                word_count,
                round(latency, 3),
                "Yes" if success else "No"
            ])

            print(f" -> Latency: {latency:.3f} seconds\n")
            time.sleep(2)  # Small pause to avoid rate limits

    print(f"[INFO] Raw data saved to {CSV_FILE}")

# ==========================================
# 3. GENERATE REPORT
# ==========================================
def generate_report():
    print("\n[INFO] Generating Performance Report...")

    total_requests = 0
    successful_requests = 0
    latencies = []

    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_requests += 1
            if row["Success"] == "Yes":
                successful_requests += 1
                latencies.append(float(row["Latency_Sec"]))

    if not latencies:
        print("[ERROR] No successful data to generate a report.")
        return

    avg_latency = sum(latencies) / len(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)
    success_rate = (successful_requests / total_requests) * 100

    with open(REPORT_FILE, mode='w', encoding='utf-8') as out_f:
        out_f.write("====================================================\n")
        out_f.write("   CLAUDE HAIKU AI LATENCY EVALUATION REPORT\n")
        out_f.write("====================================================\n\n")
        out_f.write("1. TEST OVERVIEW\n")
        out_f.write(f"- Model: {CLAUDE_MODEL}\n")
        out_f.write(f"- Total Simulated Queries: {total_requests}\n")
        out_f.write(f"- Successful API Calls: {successful_requests}\n")
        out_f.write(f"- Reliability Rate: {success_rate:.2f}%\n\n")
        out_f.write("2. RESPONSE TIME METRICS (SECONDS)\n")
        out_f.write(f"- Average Latency (TAT): {avg_latency:.3f} s\n")
        out_f.write(f"- Fastest Response:      {min_latency:.3f} s\n")
        out_f.write(f"- Slowest Response:      {max_latency:.3f} s\n\n")
        out_f.write("Note: These metrics isolate the AI processing time and exclude\n")
        out_f.write("audio transcription and network transfer overhead from the robot.\n")
        out_f.write("====================================================\n")

    print(f"[SUCCESS] Formal report generated at: {REPORT_FILE}")
    print("\n=== FINAL RESULTS ===")
    print(f"Average: {avg_latency:.3f}s | Min: {min_latency:.3f}s | Max: {max_latency:.3f}s")

if __name__ == "__main__":
    run_benchmark()
    generate_report()
