# Windows Setup and Execution Guide



This guide walks you through setting up and running the **V2X AI + Blockchain Trust Framework** on Windows 10/11, launching both the **Eclipse SUMO GUI** (traffic simulation ground truth) and the **SOC Web Dashboard** side-by-side.



---



## 1. System Prerequisites



Ensure you have the following installed on Windows:



1. **Python 3.10 or 3.11**:

   - Download from [python.org](https://www.python.org/downloads/).

   - ⚠️ **Important**: During installation, check the box **"Add python.exe to PATH"**.

2. **Node.js (v18+ LTS) & npm**:

   - Download and install from [nodejs.org](https://nodejs.org/).

3. **Eclipse SUMO (v1.28.0 or later)**:

   - You can use the provided installer `sumo.msi` included in this repository root, or download from the [Eclipse SUMO website](https://sumo.dlr.de/docs/Downloads.php).

   - Run the installer and complete the setup.

   - Default install path is usually:

     `C:\Program Files (x86)\Eclipse\Sumo` or `C:\Program Files\Eclipse\Sumo`



---



## 2. Environment Variables Setup (SUMO)



You must ensure Windows knows where SUMO is located:



### Option A: Using PowerShell (Run as Administrator)

```powershell

[System.Environment]::SetEnvironmentVariable('SUMO_HOME', 'C:\Program Files (x86)\Eclipse\Sumo', 'User')

[System.Environment]::SetEnvironmentVariable('PATH', $env:PATH + ';C:\Program Files (x86)\Eclipse\Sumo\bin', 'User')

```



### Option B: Using Windows GUI

1. Press `Win + R`, type `sysdm.cpl`, and hit **Enter**.

2. Go to the **Advanced** tab and click **Environment Variables**.

3. Under **User variables**:

   - Click **New...**:

     - Variable name: `SUMO_HOME`

     - Variable value: `C:\Program Files (x86)\Eclipse\Sumo` (verify your actual installation path).

   - Select the `Path` variable, click **Edit...**, then **New**:

     - Add `C:\Program Files (x86)\Eclipse\Sumo\bin`.

4. Click **OK** to save.



---



## 3. Project Configuration (`.env`)



In the project root directory, create or edit the `.env` file:



```ini

# SUMO Configuration for Windows

SUMO_HOME=C:\Program Files (x86)\Eclipse\Sumo

SUMO_BINARY=sumo-gui

V2X_LOG_LEVEL=INFO

```

*(If installed under `C:\Program Files\Eclipse\Sumo`, update the path accordingly).*



---



## 4. Python Virtual Environment Setup



Open **PowerShell** or **Command Prompt (CMD)** in the project root:



### In PowerShell:

```powershell

# If PowerShell script execution is restricted, run this once:

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser



# 1. Create a virtual environment

python -m venv .venv



# 2. Activate virtual environment

.\.venv\Scripts\Activate.ps1



# 3. Upgrade pip and install dependencies

python -m pip install --upgrade pip

pip install -r requirements.txt

```



### In Command Prompt (CMD):

```cmd

python -m venv .venv

.\.venv\Scripts\activate.bat

python -m pip install --upgrade pip

pip install -r requirements.txt

```



---



## 5. Frontend Dashboard Setup



Install the React dashboard dependencies:



```powershell

cd dashboard

npm install

cd ..

```



---



## 6. Running the Application



You will need **two separate terminal windows**:



### Terminal 1: Backend Server + SUMO GUI



Open PowerShell in the project root:

```powershell

# Activate virtual environment

.\.venv\Scripts\Activate.ps1



# Start FastAPI backend server

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

> The native **Eclipse SUMO GUI** window will pop up on your desktop showing the 4×4 traffic network and live moving vehicles.



---



### Terminal 2: React Dashboard (Frontend)



Open a second PowerShell window in the project root:

```powershell

cd dashboard

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



## 7. How to Compare Ground Truth vs. Misleading Information



1. **Arrange Windows**:

   - Snap **SUMO GUI** to the left half of your screen (`Win + Left Arrow`).

   - Snap your **Browser Dashboard** to the right half (`Win + Right Arrow`).



2. **Locate a Vehicle in SUMO**:

   - In the SUMO GUI window, press `Ctrl + F` (or menu: *Edit → Locate Vehicles*).

   - Enter a vehicle ID (e.g. `0`, `2`, or `5`) to focus the camera on it.

   - Observe its true visual vehicle type, lane position, speed, and heading.



3. **Inject an Attack from Dashboard**:

   - In the browser dashboard, navigate to **Control Center** (`http://localhost:5173/control`).

   - Select an attack (e.g. **Emergency Vehicle Spoofing**).

   - Select your target vehicle ID and click **LAUNCH ATTACK**.



4. **Analyze the Results**:

   - In the dashboard, click on the vehicle:

     - **Overview**: Shows mismatch (`Actual: car` vs. `Claimed: ambulance`).

     - **Behavior**: Compares raw broadcast speed/heading against SUMO TraCI ground truth.

     - **AI Analysis**: Displays XGBoost misbehaviour probability (>95%) and triggered sensor/physics rules.

     - **Blockchain**: View the smart contract's evidence commit and certificate revocation.



---



## 8. Running Automated Tests & Terminal Demo



### Automated Test Suite (Pytest)

```powershell

.\.venv\Scripts\Activate.ps1

pytest

```

All 81 tests should pass (runs headless using mock traffic model).



### Terminal-Only Live Demo

```powershell

.\.venv\Scripts\Activate.ps1

python run_demo.py

```



---



## 9. Stopping & Shutting Down



1. In **Terminal 1**: Press `Ctrl + C` to stop Uvicorn (this automatically terminates SUMO GUI).

2. In **Terminal 2**: Press `Ctrl + C` to stop Vite.

3. If ports remain occupied in Windows:

   ```powershell

   # Find process ID on port 8000 or 5173

   Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force

   Get-Process -Id (Get-NetTCPConnection -LocalPort 5173).OwningProcess | Stop-Process -Force

   ```
