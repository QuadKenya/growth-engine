# Access Afya: Growth & Onboarding Coordinator Agent

## 📋 Overview
This agent acts as an automated "Co-Pilot" for the Access Afya growth team. It accepts franchise applications, applies deterministic vetting rules (SOP 2025), manages the candidate's lifecycle state, and drafts localized communication (Email/WhatsApp) for human approval.

## 🏗 Architecture
The system follows a **Microservice Architecture** running locally:

*   **The Brain (Config):** Business logic is decoupled into JSON files (Rules, Thresholds, State Machine).
*   **The Body (FastAPI):** An API listener that accepts Webhooks from Google Forms.
*   **The Face (Streamlit):** A "Control Tower" dashboard for the Human Associate to review & approve drafts.
*   **The Memory (Local JSON):** A file-based database (`data/local_db.json`) that persists state, simulating a Supabase instance.

---

## 🚀 Prerequisites
*   **Python 3.9+** installed on your machine.
*   **Git** (optional, if tracking changes).
*   **VS Code** or your preferred IDE.

---

## 🛠 Installation Guide

### 1. Set Up Project Structure
Ensure your folder is organized exactly as follows:
```text
access_afya_vetting/
├── config/              # Place your .json and .md config files here
├── app/                 # Source code
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── services/
│   ├── ui/
│   └── main.py
├── data/                # Auto-created at runtime
├── requirements.txt
└── .env
```

### 2. Create Virtual Environment
Open your terminal in the project root (`access_afya_vetting/`) and run:

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configuration
Create a `.env` file in the root directory:
```bash
touch .env
```

Add the following content to `.env`:
```ini
PROJECT_NAME="Access Afya Vetting Agent"
ENVIRONMENT="development"
# Leave OPENAI_API_KEY blank to use the "Mock" drafting (Free/Offline)
OPENAI_API_KEY=""
```

---

## 🏃♂️ How to Run the Agent

You will typically run the **Dashboard** to interact with the agent. You can also run the **API** if you want to test external webhooks.

### Option 1: Run the Dashboard (Recommended)
This launches the "Control Tower" where you can simulate leads and approve drafts.

1.  Ensure your virtual environment is active.
2.  Run Streamlit:
    ```bash
    streamlit run app/ui/dashboard.py
    ```
3.  The app will open in your browser automatically (usually `http://localhost:8501`).

### Option 2: Run the API Listener
Use this if you want to send `curl` requests or connect a real Google Form webhook.

1.  Open a **new** terminal window.
2.  Activate the virtual environment.
3.  Run FastAPI:
    ```bash
    uvicorn app.main:app --reload --port 8000
    ```
4.  View Swagger Documentation at `http://localhost:8000/docs`.

---

## 🧪 Simulation Walkthrough

Once the **Streamlit Dashboard** is running:

1.  **Inject a Test Lead:**
    *   Open the sidebar on the left.
    *   Fill in the "Simulation Lab" form (Name, Profession, Financials).
    *   Click **🚀 Inject Lead**.
    *   *What happens:* The system creates a lead, scores it against `rules_engine.json`, and generates a draft.

2.  **Review the Draft:**
    *   Go to the **Inbox (Needs Action)** tab in the main view.
    *   You will see the new lead. Expand the card to see the "Proposed Message."
    *   Edit the text if needed.

3.  **Approve & "Send":**
    *   Click **✅ Approve & Send**.
    *   *What happens:* The lead status updates in `data/local_db.json`, the draft is cleared, and the lead moves to the **Pipeline Tracker** tab.

---

## 📂 Project Logic (Where to edit rules)

*   **Change Scoring Weights:** Edit `config/rules_engine.json`.
*   **Change Workflow SLAs:** Edit `config/state_machine.json`.
*   **Change Valid Locations:** Edit `config/territories.json`.
*   **Change AI Personality:** Edit `config/system_prompt.md`.

## 🐛 Troubleshooting

*   **"Module not found":** Ensure you are running commands from the root `access_afya_vetting/` folder, not inside `app/`.
*   **"FileNotFoundError":** Check that your `config/` folder contains all 5 required JSON/MD files.
*   **Database Reset:** To clear all data, simply delete the `data/local_db.json` file. It will be recreated automatically.