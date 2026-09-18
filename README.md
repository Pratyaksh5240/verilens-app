# 🛡️ VeriLens — AI Credibility & Misinformation Screener

[![CI Pipeline](https://github.com/Pratyaksh5240/verilens-app/actions/workflows/ci.yml/badge.svg)](https://github.com/Pratyaksh5240/verilens-app/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.49.1-FF4B4B.svg)](https://streamlit.io/)
[![Tests](https://img.shields.io/badge/tests-50%20passed-success.svg)](https://github.com/Pratyaksh5240/verilens-app/tree/main/tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**VeriLens** is an open-source, decision-support platform designed to evaluate news URLs and forwarded text claims. Built with Streamlit, it combines **SSRF-hardened web extraction**, a **RoBERTa emotion classification pipeline**, an **open recognized publisher directory**, **linguistic manipulation checks**, and **live multi-source cross-corroboration via NewsAPI**.

---

## ⚠️ Important Disclaimer & Methodology Notice

> **Decision-Support Tool, Not an Automated Arbiter of Truth**  
> VeriLens produces a heuristic credibility estimate based on observable journalistic indicators (attribution, quantitative data, publisher recognition, writing neutrality, and multi-source corroboration). **It is not an automated fact-checker.** Low scores reflect a lack of verifiable corroboration or sensationalist framing, while high scores indicate adherence to formal journalistic standards. High-stakes claims (e.g. public health, legal matters, elections) should always be verified across multiple independent primary sources.

### Catalog Limitations
The recognized outlet catalog is a curated reference list based on international wire services, public broadcasters, health authorities, and verified IFCN-signatory fact-checkers. It is non-exhaustive, predominantly English-language, and presence or absence in the directory does not constitute an endorsement or final verdict.

---

## 🏛️ System Architecture

The codebase follows a modular design with complete separation of concerns and zero Streamlit dependencies in the scoring pipeline:

```text
verilens/
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions CI matrix (Python 3.11, 3.12, 3.13)
├── data/
│   └── evaluation_set.csv     # 25 labeled real-world benchmark cases (credible, unreliable, mixed)
├── tests/
│   ├── test_config.py         # Catalog lookup and configuration unit tests
│   ├── test_emotion.py        # HuggingFace pipeline, top_k=None, fallback & logging tests
│   ├── test_extraction.py     # SSRF defense, 5MB streaming size cap, article parser tests
│   ├── test_scoring.py        # Pure scoring functions & decoupled emotion verification
│   └── test_verification.py   # Title cleaning, keyphrase extraction, and NewsAPI client tests
├── .env.example               # Template for environment configuration
├── .gitignore                 # Exclusion rules for venvs, caches, secrets, and temp files
├── app.py                     # Streamlit frontend UI with rate limiting, caching & sanitization
├── config.py                  # Recognized outlet catalog, constants, regex lexicons, security limits
├── emotion.py                 # HuggingFace transformer pipeline, fallback, and audit logging
├── evaluate.py                # Standalone benchmark runner (Accuracy, Precision, Recall, F1)
├── extraction.py              # SSRF-protected HTTP client, streaming download cap, parser
├── scoring.py                 # Pure mathematical credibility scoring (zero Streamlit dependency)
├── verification.py            # NewsAPI cross-verification client and query extraction engine
├── requirements.txt           # Pinned, tested production dependencies
└── requirements-dev.txt       # Pinned development and CI dependencies
```

---

## 🚀 Key Improvements & Engineering Highlights

### 1. Security Hardening
- **SSRF Defense (`extraction.py`)**: Validates URL schemes (`http`/`https` only), resolves hostnames to IP addresses, and blocks private, loopback, link-local, multicast, and Carrier-Grade NAT ranges (RFC 1918, `127.0.0.0/8`, `169.254.0.0/16`, `::1`, `100.64.0.0/10`, `0.0.0.0/8`).
- **Safe Redirect Tracking**: Manually follows HTTP redirects (`allow_redirects=False`) for up to 5 hops, re-verifying the resolved IP address of every redirect hop before establishing a connection.
- **Streaming 5MB Response Cap**: Validates `Content-Length` upfront and streams response chunks in 8KB blocks, aborting immediately if downloaded data exceeds 5 MB. Enforces 3s connect and 7s read timeouts.
- **Per-Session Rate Limiting (`app.py`)**: Enforces a 2-second cooldown and 15 requests/minute cap to prevent proxy abuse.
- **Output Sanitization**: Escapes all third-party headlines and text snippets with `html.escape` to prevent XSS and HTML/markdown injection.

### 2. Methodological Reforms
- **Decoupled Emotion Scoring**: Emotion classification (`j-hartmann/emotion-english-distilroberta-base`) is treated as an independent editorial framing diagnostic. Anger and fear are **no longer penalized in the credibility score**, preventing legitimate disaster, crisis, or war reporting from being falsely classified as untrustworthy.
- **Defensible Publisher Directory**: Replaced the arbitrary 9-domain whitelist with an expanded, categorized catalog (Wire Services, Public Broadcasters, IFCN Fact-Checkers, Health Authorities, Major Dailies) and explicitly disclosed limitations in the UI.
- **Intelligent Query Extraction (`verification.py`)**: Decodes HTML entities, strips publication names and title separators (`|`, `-`, `—`, `::`, `•`), removes stop words and news noise words (`breaking`, `exclusive`, `reported`), and extracts capitalized proper noun sequences.
- **Audit Logging & Transparent Banners**: Logs every fallback with Python `logging` and displays a visible UI banner whenever the ML pipeline falls back to the keyword heuristic.

---

## 📊 Credibility Scoring Model

The overall credibility score ($0.0 \text{ to } 1.0$) is calculated as a composite index across five verifiable dimensions:

| Component | Max Weight | Description |
| :--- | :--- | :--- |
| **Base Contribution** | 15% | Fundamental baseline for any submitted input. |
| **Recognized Publisher Directory** | 38% | Matches domain or outlet against verified wire services, broadcasters, and newsrooms. |
| **Article Structure Quality** | 18% | Evaluates word volume, sentence structure, and journalistic formatting. |
| **Live Corroboration** | 18% | Measures multi-source reporting coverage across distinct news domains via NewsAPI. |
| **Evidence & Attribution Cues** | 18% | Rewards attribution verbs (*according to*, *said*, *reported*), quantitative data, and dates. |
| **Writing Quality (Low Manipulation)** | 20% | Rewards neutral writing; penalizes sensationalism, clickbait, and conspiracy phrasing. |
| **Debunking Contradiction Penalty** | up to -40% | Subtracted when matching coverage from fact-checkers contains debunk terms (*debunked*, *false*, *hoax*). |

### Verdict Categories
- **`Recognized Publisher Article` (85% – 100%)**: Published by an established newsroom or fact-checker with solid reporting structure.
- **`Likely Credible Reporting` (65% – 84%)**: Displays characteristic evidence cues and low manipulation risk.
- **`Unverified Claim / Needs Context` (45% – 64%)**: Language is plausible and calm, but independent corroboration or source verification is missing.
- **`Low Credibility / Verify Before Forwarding` (< 45%)**: Caution signals outweigh evidence cues. Avoid sharing without cross-checking.
- **`High Misinformation Risk`**: Related news reporting indicates the claim has been debunked or contradicted.
- **`High Manipulation Risk`**: Language displays extreme sensationalism, emotional pressure, or conspiracy framing.

---

## 🛠️ Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Pratyaksh5240/verilens-app.git
cd verilens-app
```

### 2. Create Virtual Environment

```bash
# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

Install production requirements:
```bash
pip install -r requirements.txt
```

For development, testing, and CI tooling:
```bash
pip install -r requirements-dev.txt
```

### 4. Configure NewsAPI Key

Copy the environment template:
```bash
cp .env.example .env
```

Obtain a free developer API key from [NewsAPI.org](https://newsapi.org/) and add it to `.env`:
```bash
NEWS_API_KEY=your_newsapi_key_here
```

Or set the environment variable directly:
```bash
# Windows PowerShell
$env:NEWS_API_KEY="your_newsapi_key_here"

# Linux / macOS
export NEWS_API_KEY="your_newsapi_key_here"
```

#### Streamlit Cloud Deployment Secrets
When deploying to [Streamlit Community Cloud](https://share.streamlit.io/), configure your secret in **App Settings > Secrets**:
```toml
NEWS_API_KEY = "your_actual_newsapi_key_here"
```

---

## 🏃 Running the Application

Launch the Streamlit dashboard:

```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`.

---

## 🧪 Testing & Evaluation Benchmark

### 1. Pytest Unit Test Suite
The project includes 50 automated unit tests across all modules:
```bash
pytest -v
```

Test coverage includes:
- **SSRF Defense**: Tests 10 private, loopback, link-local, and CGNAT IP ranges, non-HTTP schemes, and credential injection.
- **Size Caps**: Tests stream abort behavior on files exceeding 5MB.
- **Emotion Fallback**: Tests `top_k=None` compatibility, keyword fallback, and error logging.
- **Scoring Logic**: Verifies that emotion decoupling does not penalize disaster reporting, tests debunk penalties, and validates recognized publisher lookup.
- **Verification Engine**: Tests title separator stripping (`|`, `-`, `—`, `::`, `•`), HTML entity decoding, and non-English text resilience.

### 2. Benchmark Evaluation (`evaluate.py`)
Run the evaluation benchmark against the 25-item labeled evaluation dataset (`data/evaluation_set.csv`):
```bash
python evaluate.py
```

#### Benchmark Results
```text
=================================================================
  PERFORMANCE SUMMARY
=================================================================
Overall Accuracy:      21/25 (84.0%)
High-Fear Resilience:  7/9 (77.8%) (Disaster journalism retained high credibility)

Per-Class Breakdown:
Class          | Precision  | Recall     | F1-Score   | Support 
------------------------------------------------------------
credible       | 1.000      | 0.909      | 0.952      | 11      
unreliable     | 0.875      | 0.700      | 0.778      | 10      
mixed          | 0.571      | 1.000      | 0.727      | 4       

Confusion Matrix:
               | Pred: credible  | Pred: unreliable  | Pred: mixed 
-----------------------------------------------------------------
True: credible | 10              | 1                 | 0           
True: unreliable | 0               | 7                 | 3           
True: mixed    | 0               | 0                 | 4           
=================================================================
```

---

## 🔄 GitHub Actions CI Pipeline

The project includes continuous integration via [`.github/workflows/ci.yml`](https://github.com/Pratyaksh5240/verilens-app/blob/main/.github/workflows/ci.yml) that executes on every push and pull request:
- **Matrix Testing**: Evaluates across Python **3.11**, **3.12**, and **3.13**.
- **Code Quality**: Runs `ruff check .` and `black --check .`.
- **Test Suite**: Executes `pytest -v tests/`.
- **Benchmark Gate**: Executes `python evaluate.py`.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
