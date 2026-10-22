# macOS Setup and Execution Guide



This guide walks you through setting up and running the **V2X AI + Blockchain Trust Framework** on macOS, launching both the **Eclipse SUMO GUI** (traffic simulation ground truth) and the **SOC Web Dashboard** side-by-side.



---



## 1. System Prerequisites



Ensure you have the following installed on your Mac:



- **macOS**: Apple Silicon (M1/M2/M3/M4) or Intel

- **Python**: 3.10 or 3.11 (`python3 --version`)

- **Node.js**: v18+ and npm v9+ (`node -v`, `npm -v`)

- **Eclipse SUMO**: Traffic simulator (`1.28.0` or latest)



### Installing SUMO on macOS

If not already installed, install SUMO via Homebrew or official DMG:

```bash

# Option A: Homebrew Cask

brew install --cask sumo



# Option B: Framework installer

# If installed from the official package, it is typically located at:

# /Library/Frameworks/EclipseSUMO.framework/Versions/1.28.0/EclipseSUMO

```



---



## 2. Repository Configuration



Open your terminal and navigate to the project repository:

```bash

cd /Users/yashk26/Documents/Study/ccns-project

```



### Configure `.env` File

Create or update the `.env` file in the project root:

```bash

cat << 'EOF' > .env

# SUMO Configuration

SUMO_HOME=/Library/Frameworks/EclipseSUMO.framework/Versions/1.28.0/EclipseSUMO/share/sumo

SUMO_BINARY=sumo-gui

V2X_LOG_LEVEL=INFO

EOF

```



> **Note**: If your SUMO was installed via Homebrew, set `SUMO_HOME` to Homebrew's share directory:

> ```bash

> export SUMO_HOME="/opt/homebrew/opt/sumo/share/sumo"

> ```



---



## 3. Python Virtual Environment Setup



From the repository root:



```bash

# 1. Create a virtual environment (if not already created)

python3 -m venv .venv



# 2. Activate the virtual environment

source .venv/bin/activate



# 3. Upgrade pip and install required dependencies

pip install --upgrade pip

pip install -r requirements.txt

```



---



## 4. Frontend Dashboard Setup



Install the React dashboard dependencies:



```bash

cd dashboard

npm install

cd ..

```



---



## 5. Running the Application



You will need **two terminal tabs/windows**:



### Terminal 1: Backend Server + SUMO GUI



In the project root:

```bash

# Activate virtual environment

source .venv/bin/activate



# Start FastAPI backend (which also launches the SUMO GUI window)

uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload

```



**Expected output:**

```text

INFO:ai.misbehavior_detector:Loaded detector model xgboost (14 classes)

INFO:simulation.sumo_manager:Started SUMO via TraCI on port 8813 (GUI: True)

INFO:backend.orchestrator:Connected to SUMO (scenario normal)

INFO:     Application startup complete.

INFO:     Uvicorn running on http://127.0.0.1:8000

```

> The **Eclipse SUMO GUI** native window will automatically open on your Mac desktop displaying the 4×4 grid road network and traffic simulation.



---



### Terminal 2: React Dashboard (Frontend)



Open a second terminal window or tab:

```bash

cd /Users/yashk26/Documents/Study/ccns-project/dashboard



# Start the Vite development server

npm run dev

```



**Expected output:**

```text

  VITE v8.3.1  ready in 314 ms



  ➜  Local:   http://localhost:5173/

```



Open your browser to:

[http://localhost:5173](http://localhost:5173)



---



## 6. How to Compare Ground Truth vs. Misleading Information



To analyze ground truth vs. malicious claims:



1. **Arrange Windows**:

   - Place **SUMO GUI** on the left half of your screen.

   - Place your **Browser Dashboard** (`http://localhost:5173`) on the right half.



2. **Track a Vehicle in SUMO**:

   - In SUMO GUI, press `Ctrl + F` (or menu: *Edit → Locate Vehicles*).

   - Enter a vehicle ID (e.g., `0`, `3`, or `12`) to center and follow the vehicle.

   - Observe its genuine shape, color, speed, and heading.



3. **Inject an Attack from Dashboard**:

   - In the web dashboard, go to **Control Center** (`/control`).

   - Select an attack (e.g., **Emergency Vehicle Spoofing**).

   - Pick the target vehicle ID and click **LAUNCH ATTACK**.



4. **Verify the Detection Pipeline**:

   - Click on the vehicle in the dashboard to open its details.

   - **Overview Tab**: Displays the discrepancy (`Actual: car` vs. `Claimed: ambulance`).

   - **Behavior Tab**: Graphs the claimed broadcasted speed/heading vs. actual TraCI physical ground truth.

   - **AI Analysis Tab**: View the misbehaviour probability (>95%) and triggered rule checks.

   - **Blockchain Tab**: Watch the smart contract commit evidence and revoke the certificate on-chain.



---



## 7. Running Tests & Terminal Demo



### Running Automated Tests

```bash

source .venv/bin/activate

pytest

```

All 81 tests should pass (uses built-in mock model for headless CI testing).



### Running Terminal-Only Live Demo

```bash

source .venv/bin/activate

python run_demo.py

```



---



## 8. Stopping & Shutting Down



To stop all running services:

1. In **Terminal 1**: Press `Ctrl + C` to stop Uvicorn (this automatically closes SUMO GUI).

2. In **Terminal 2**: Press `Ctrl + C` to stop the Vite development server.

3. If any port remains in use:

   ```bash

   lsof -ti:8000 | xargs kill -9

   lsof -ti:5173 | xargs kill -9

   ```
