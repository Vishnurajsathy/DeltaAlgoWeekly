# Delta Weekly Options Selling Bot

This project is a Python-based, fully-automatic BTC/USDT weekly option-selling bot designed for the Delta Exchange. It features dynamic hedging, per-minute monitoring, OI/IV analytics, and a real-time dashboard.

This repository is being actively developed by an AI software engineer.

## Getting Started

Follow these instructions to get the bot up and running on your local machine for development and testing purposes.

### Prerequisites

- Python 3.9+
- A Delta Exchange account with API keys.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd delta_weekly_bot
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure your secrets:**
    -   Navigate to the `config` directory.
    -   Make a copy of `secrets.example.yaml` and rename it to `secrets.yaml`.
    -   Edit `secrets.yaml` and add your Delta Exchange API key and secret.
    ```yaml
    delta:
      api_key: "YOUR_API_KEY"
      api_secret: "YOUR_API_SECRET"
    ```

## Usage

To run the bot, execute the main application file from the project's root directory:

```bash
python src/app.py
```

The bot will start, load the configuration, and begin its main trading loop. You can monitor its activity through the console logs and the JSON log file specified in `config/default.yaml`.

### Dry Run Mode

For safety and testing, you can run the bot in a "dry run" mode where it will not execute any live trades. To enable this, set `dry_run: true` in `config/default.yaml`:

```yaml
# config/default.yaml
general:
  dry_run: true
  # ... other settings
```

## Project Structure

The repository is organized as follows:

-   `config/`: Contains all configuration files (`default.yaml`, `secrets.yaml`).
-   `src/`: The main application source code.
    -   `app.py`: The main entrypoint of the application.
    -   `analytics/`: Modules for calculating IV, greeks, OI, etc.
    -   `broker/`: Abstraction layer for interacting with the exchange API.
    -   `core/`: Core components like the state machine and event system.
    -   `data/`: Pydantic models for data structures and the API client wrapper.
    -   `strategy/`: The core trading logic, including entry, hedging, and adjustment rules.
    -   `ui/`: The real-time dashboard (e.g., Streamlit app).
    -   `utils/`: Helper modules for configuration, logging, etc.
-   `tests/`: Contains all tests (unit, integration, e2e).
-   `notebooks/`: Jupyter notebooks for research and backtesting.
-   `requirements.txt`: A list of Python packages required for the project.
