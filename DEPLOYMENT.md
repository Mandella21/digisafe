# DigiSafe: Deployment & Hosting Guide

This guide provides step-by-step instructions to run **DigiSafe** locally and deploy it online to **Render.com** (or Railway / Docker) before your Friday deadline.

---

## 1. Local Quickstart (Testing On Your Machine)

1. Open a terminal in this project folder:
   ```bash
   cd "mini project"
   ```

2. Run the application:
   ```bash
   python -m uvicorn main:app --reload
   ```

3. Open your browser and visit:
   ```
   http://127.0.0.1:8000
   ```

4. Pre-configured demonstration accounts are already initialized:
   - **Victim Complainant**: `victim@digisafe.org` / `Victim@123`
   - **Police Officer**: `officer@police.gov.gh` / `Officer@123`
   - **System Administrator**: `admin@digisafe.org` / `Admin@123`
   *(Tip: You can also use the 1-click quick login buttons directly on the UI)*

---

## 2. Deploy Free to Render.com (Recommended - 5 Minutes)

Render provides free hosting for Python web services with HTTPS enabled out of the box.

### Step A: Push Project to GitHub
1. Initialize Git in the project directory (if not already done):
   ```bash
   git init
   git add .
   git commit -m "DigiSafe complete prototype release"
   ```
2. Create a new repository on [GitHub.com](https://github.com/new) named `digisafe`.
3. Push your code to GitHub:
   ```bash
   git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/digisafe.git
   git branch -M main
   git push -u origin main
   ```

### Step B: Launch on Render
1. Go to [dashboard.render.com](https://dashboard.render.com/) and sign up or log in.
2. Click **New +** -> **Web Service**.
3. Connect your GitHub account and select the `digisafe` repository.
4. Configure the service settings:
   - **Name**: `digisafe-knust` (or your preferred name)
   - **Region**: Frankfurt (EU) or Oregon (US)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt && python seed_data.py
     ```
   - **Start Command**:
     ```bash
     uvicorn main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type**: **Free**
5. Click **Create Web Service**.
6. Render will automatically build the container, install packages, seed the database, and assign a live public HTTPS URL (e.g., `https://digisafe-knust.onrender.com`).

---

## 3. Alternative 1-Click Deploy via Railway.app

1. Visit [railway.app](https://railway.app/) and sign in with GitHub.
2. Click **New Project** -> **Deploy from GitHub repo** -> Select `digisafe`.
3. Railway automatically detects the `Procfile` and `requirements.txt`.
4. Add a domain under **Settings** -> **Networking** -> **Generate Domain**.
5. Your app is immediately live!

---

## 4. Docker Deployment

If deploying to a VPS (Ubuntu/Debian) or Docker host:
```bash
docker build -t digisafe-app .
docker run -d -p 8000:8000 --name digisafe digisafe-app
```
Access at `http://localhost:8000`.

---

## 5. Defense & Demonstration Checklist

During your project defense with your supervisor (Prof. Frimpong Twum) and panel:
1. **Victim Workflow**:
   - Log in using `victim@digisafe.org`
   - Go to **Submit Evidence**: enter a threat message (e.g., WhatsApp threat) and optional screenshot
   - Observe instant SHA-256 digital fingerprint and ML threat score (`Critical` or `High`)
   - Go to **Tracking Dashboard** and download the **Court-Admissible PDF Report**
2. **Cryptographic Integrity & Tamper Detection (Section 4.1.8)**:
   - Switch to **Police Officer** or **Admin**
   - Click **Verify** on any case to show mathematical integrity match
   - Click **Simulate Tampering** (Section 4.1.8) on the Admin dashboard to show the panel that modifying database ciphertext immediately flags the case as `COMPROMISED` and triggers a high-severity alert!
3. **Audit Trail (Section 3.15.1)**:
   - Open `/audit` to show the chronological audit log of all logins, submissions, and integrity checks
   - Click **Export to CSV** to demonstrate compliance with digital evidence standards
