# 📞 Abra Voice Agent — India Stack
**Python + Exotel + Google TTS + Claude AI + Google Sheets**

---

## 📁 Project Structure

```
abra-voice-agent-india/
├── backend/
│   ├── main.py                  ← FastAPI server (all logic here)
│   ├── requirements.txt         ← Python dependencies
│   └── .env.example             ← Copy to .env and fill in keys
├── config/
│   └── google-credentials.json  ← Place your GCP service account here
├── dashboard/
│   └── index.html               ← Open directly in browser (no build needed)
└── setup.sh                     ← Quick setup script
```

---

## 🔑 Services You Need (All Have Free Tiers)

| Service | Used For | Sign Up |
|---|---|---|
| **Exotel** | Placing calls to Indian numbers | exotel.com |
| **Anthropic** | Claude AI brain | console.anthropic.com |
| **Google Cloud** | TTS voice + Sheets logging | console.cloud.google.com |

---

## 🛠️ Step-by-Step Setup

### Step 1 — Exotel Account
1. Sign up at https://exotel.com
2. Buy an **ExoPhone** (virtual Indian number) — ₹500–1000/month
3. Go to **Settings → API** → copy:
   - Account SID
   - API Key
   - API Token
4. Note your ExoPhone number (e.g., 08068XXXXXX)

### Step 2 — Google Cloud Setup
1. Go to https://console.cloud.google.com
2. Create a new project: **"abra-voice-agent"**
3. Enable these two APIs:
   - **Cloud Text-to-Speech API**
   - **Google Sheets API**
4. Create a **Service Account**:
   - IAM & Admin → Service Accounts → Create
   - Role: Editor
   - Download the JSON key file
5. Rename the JSON file to `google-credentials.json`
6. Place it in the `config/` folder

### Step 3 — Google Sheets
1. Create a new Google Sheet at sheets.google.com
2. Name the first tab **"Leads"**
3. Add these headers in Row 1:
   `Date | Phone | Name | Company | Interested | Callback Time | Duration | Summary`
4. Share the sheet with your **service account email** (from the JSON file) as Editor
5. Copy the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit`

### Step 4 — Anthropic API Key
1. Go to https://console.anthropic.com
2. API Keys → Create Key → copy it

### Step 5 — Environment Setup
```bash
cd backend
cp .env.example .env
# Edit .env with all your keys
```

### Step 6 — Install & Run Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 7 — Expose to Internet (for Exotel webhooks)
Exotel needs to call your server during each call. Use ngrok:
```bash
# Install ngrok: https://ngrok.com
ngrok http 8000

# Copy the https URL, e.g.: https://abc123.ngrok.io
# Paste it as BASE_URL in your .env file
# Restart the backend after updating .env
```

### Step 8 — Configure Exotel Webhooks
In your Exotel dashboard:
- **Passthru URL** (call answered): `https://YOUR_URL/webhook/call-start`
- **Status Callback**: `https://YOUR_URL/webhook/call-status`

### Step 9 — Open Dashboard
Simply open `dashboard/index.html` in your browser.
No build step, no npm, just double-click and open!

---

## 🧪 Test It

1. Open dashboard → **Make Calls** tab
2. Enter your own phone number: `+919XXXXXXXXX`
3. Click **Call Now**
4. Your phone will ring — Priya (AI) will introduce Abra Logistics
5. Have a conversation — check Google Sheets for the lead!

---

## 📋 CSV Format for Bulk Campaigns

```csv
phone
+919876543210
+918765432109
+917654321098
```

Upload via the **Bulk Campaign** section in the dashboard.
Set delay between calls (minimum 5 seconds recommended).

---

## 💰 Cost Estimate

| Service | Cost |
|---|---|
| Exotel calls | ₹0.30–0.60 per minute |
| Claude AI (claude-sonnet) | ~₹0.50 per call |
| Google TTS | Free up to 1M chars/month |
| Google Sheets | Free |
| **Total per 100 calls** | **~₹200–400** |

---

## 🚀 Production Deployment

For production (not just local testing):
1. Deploy backend on **Railway** or **Render** (free tiers available)
2. Set `BASE_URL` to your deployment URL
3. No need for ngrok in production

---

## ❓ Troubleshooting

| Problem | Fix |
|---|---|
| Call connects but no audio | Check ElevenLabs/Google TTS key |
| Webhook not firing | Check ngrok is running, BASE_URL is correct |
| Leads not in Sheets | Verify service account has Editor access to the sheet |
| "No module named X" | Run `pip install -r requirements.txt` again |
