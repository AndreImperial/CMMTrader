# Setup

## Local Windows

1. Create a virtual environment.
2. Install dependencies from `requirements.txt`.
3. Copy `.env.example` to `.env`.
4. Use fixture mode first.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.fixture.example .env
python -m unittest discover
python -m coach_miranda_miner doctor
python -m coach_miranda_miner scan
streamlit run app.py
```

## Safe First Run

Use:

```text
TRADING_MODE=paper
DATA_MODE=fixture
ANALYZER_MODE=rule
RENDER_CHARTS=false
```

Then move to `DATA_MODE=coinbase` when local fixture checks are healthy.
