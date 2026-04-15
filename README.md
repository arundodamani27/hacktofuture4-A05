# 🚀 Team NeuralOps — KubeHeal

## 🧠 Problem Statement / Idea

Modern cloud applications run on Kubernetes, which provides basic self-healing (like restarting pods). However, it lacks intelligence and diagnosis.

- **Problem:** Kubernetes can restart failed pods but cannot identify *why* failures occur.
- **Why important:** In large-scale systems, failures can cascade, increasing downtime and MTTR (Mean Time To Recovery).
- **Target users:** DevOps Engineers, Site Reliability Engineers (SREs), and cloud teams managing microservices.

---

## 💡 Proposed Solution

We built **KubeHeal — an AI-powered self-healing system for Kubernetes**.

- Continuously monitors pods in real-time
- Performs AI-based Root Cause Analysis (RCA)
- Decides whether to:
  - 🤖 Auto-heal
  - 🧑 Wait for human approval
- Tracks MTTR to measure recovery efficiency

### 🔥 Unique Features

- Combines monitoring + AI + remediation
- Supports both **Manual Mode** and **Autonomous Mode**
- Adds intelligence on top of Kubernetes self-healing

---

## ⚙️ Features

- 🔍 Real-time pod monitoring
- 🧠 AI-based root cause analysis (RCA)
- 🤖 Autonomous self-healing system
- 🧑 Manual intervention workflow
- 📊 MTTR tracking and visualization
- 📈 Live dashboard for system health
- ⚡ Failure injection for testing

---

## 🧰 Tech Stack

- **Frontend:** React.js
- **Backend:** FastAPI (Python)
- **Database:** None
- **APIs / Services:**
  - Kubernetes API
  - Metrics Server (CPU monitoring)
- **Tools / Libraries:**
  - Docker
  - Minikube
  - Chart.js

---

## ⚡ Project Setup Instructions

### 1️⃣ Clone Repository
```bash
git clone https://github.com/<your-username>/hacktofuture4-<team_id>.git
cd hacktofuture4-<team_id>