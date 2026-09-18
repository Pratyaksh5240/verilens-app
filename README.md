# 🛡️ VeriLens

VeriLens is a professional-grade, AI-assisted misinformation and credibility screening application built with Streamlit. It analyzes news article URLs and text claims using SSRF-hardened web scraping, an emotion-classification pipeline, recognized newsroom directory matching, linguistic manipulation checks, and live NewsAPI cross-verification.

---

## ⚠️ Important Disclaimer & Methodology Notice

> **Decision-Support Tool, Not an Automated Arbiter of Truth**  
> VeriLens provides a heuristic credibility estimate based on observable journalistic indicators (attribution, quantitative data, publisher recognition, writing neutrality, and multi-source corroboration). It is **not** a substitute for professional fact-checking. High-stakes claims (e.g. public health, legal, national security) should always be verified across multiple independent primary sources.

### Catalog Limitations
The recognized outlet directory is a curated reference list based on international wire services, public broadcasters, and verified IFCN-signatory fact-checkers. It is non-exhaustive, predominantly English-language, and presence or absence in the directory does not constitute an endorsement or final verdict.

---

## 🏛️ Architecture & Project Structure

The codebase is split into single-responsibility, fully unit-tested modules:

```text
verilens/
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions CI: ruff + black + pytest matrix
├── data/
│   └── evaluation_set.csv     # 25 labeled real-world evaluation benchmark cases
├── tests/
│   ├── test_config.py         # Catalog lookups and configuration constants
│   ├── test_emotion.py        # Emotion inference, top_k=None, fallback & logging
│   ├── test_extraction.py     # SSRF defense, 5MB streaming limit, article parsing
│   ├── test_scoring.py        # Pure scoring functions & decoupled emotion verification
│   └── test_verification.py   # Headline cleaning, keyphrase extraction, NewsAPI client
├── .env.example               # Environment variable configuration template
├── .gitignore                 # Excludes venvs, caches, secrets, and temp directories
├── app.py                     # Streamlit UI, rate limiting, caching & presentation
├── config.py                  # Recognized outlet catalog, constants, regex lexicons
├── emotion.py                 # HuggingFace RoBERTa pipeline, fallback & audit logging
├── evaluate.py                # Standalone benchmark runner (accuracy, precision, recall, F1)
├── extraction.py              # SSRF-protected HTTP client, streaming size cap, article parser
├── scoring.py                 # Pure mathematical credibility scoring pipeline
├── verification.py            # NewsAPI cross-verification and query extraction engine
├── requirements.txt           # Pinned, tested production dependencies
└── requirements-dev.txt       # Development and CI test dependencies
```

---

## 🚀 Key Improvements & Hardening Pass

### 1. Security Hardening
- **SSRF Defense**: Validates URL schemes (`http`/`https` only), resolves hostnames, and rejects all private, loopback, link-local, multicast, and carrier-grade NAT IP ranges (RFC 1918, `127.0.0.0/8`, `169.254.0.0/16`, `::1`, `100.64.0.0/10`).
- **Safe Redirect Tracking**: Manually follows HTTP redirects up to 5 hops, re-verifying the resolved IP of each redirect hop before connecting.
- **Streaming 5MB Response Cap**: Streams HTTP response chunks and aborts immediately if page content exceeds 5MB. Enforces 3s connect and 7s read timeouts.
- **Session Rate Limiting**: Enforces a 2-second cooldown and 15 requests/minute cap to prevent proxy abuse.
- **Output Sanitization**: Escapes all third-party headlines and text snippets before rendering to prevent HTML/markdown injection.

### 2. Methodological Reforms
- **Decoupled Emotion Scoring**: Emotion classification (`j-hartmann/emotion-english-distilroberta-base`) is treated as an independent editorial framing diagnostic. Anger and fear are **no longer penalized in the credibility score**, preventing legitimate disaster, crisis, or war reporting from being falsely classified as untrustworthy.
- **Defensible Publisher Directory**: Replaced the 9-domain binary whitelist with a categorized directory (Wire Services, Public Broadcasters, IFCN Fact-Checkers, Major Dailies) and explicitly disclosed limitations in the UI.
- **Intelligent Query Extraction**: Decodes HTML entities, strips publication names and title separators (`|`, `-`, `—`, `::`, `•`), and extracts high-information proper nouns instead of naive token slicing.
- **Audit Logging & Transparent Banners**: Logs every fallback with Python `logging` and displays a visible UI banner whenever the ML pipeline falls back to the keyword heuristic.

---

## 🛠️ Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Pratyaksh5240/verilens-app.git
cd verilens-app
```
*(Note: The repository URL points to `Pratyaksh5240/verilens-app`, the active repository owner.)*

### 2. Environment Setup

Create and activate a virtual environment:

```bash
# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

Install pinned dependencies:

```bash
pip install -r requirements.txt
```

For development and running tests:

```bash
pip install -r requirements-dev.txt
```

### 3. Configure API Keys

Copy the `.env.example` file:

```bash
cp .env.example .env
```

Obtain a free API key from [NewsAPI.org](https://newsapi.org/) and add it:

```bash
# In your .env file:
NEWS_API_KEY=your_newsapi_key_here
```

Or set the environment variable directly:

```bash
# Windows PowerShell
$env:NEWS_API_KEY="your_key_here"

# Linux / macOS
export NEWS_API_KEY="your_key_here"
```

#### Streamlit Cloud Deployment Secrets
If deploying to [Streamlit Community Cloud](https://share.streamlit.io/), configure your key in **App Settings > Secrets**:

```toml
NEWS_API_KEY = "your_actual_newsapi_key_here"
```

---

## 🏃 Running the Application

Launch the Streamlit app:

```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501`.

---

## 🧪 Testing & Evaluation

### Run Pytest Suite
Run the 50 unit tests covering scoring, extraction, emotion fallback, and query construction:

```bash
pytest -v
```

### Run Evaluation Benchmark
Run the evaluation script against the 25-item labeled evaluation dataset (`data/evaluation_set.csv`):

```bash
python evaluate.py
```

The script evaluates accuracy, precision, recall, F1 score, and high-fear disaster resilience, outputting a confusion matrix.

---

## 📜 License

MIT License. See LICENSE for details.
