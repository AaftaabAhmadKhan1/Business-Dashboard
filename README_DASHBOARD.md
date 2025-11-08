# Batch Enrollment Dashboard

Interactive Python dashboard built with Plotly Dash, connected to Google Sheets.

## 🎯 Features

- ✅ **Data Filters**: Date range, Batch name, Exam category
- ✅ **Overall Enrollment Batchwise**: Bar chart showing top 15 batches
- ✅ **Last 7 Days Enrollment**: Time series trend chart
- ✅ **Exam Distribution**: Pie chart showing enrollment by exam category
- ✅ **Batch Eligibility**: Donut chart with batch types (Only_base_batch, etc.)
- ✅ **Summary Cards**: Total enrollment, Last 7 days, Revenue metrics
- ✅ **Detailed Data Table**: First 50 records with all details
- ✅ **Auto-refresh**: Button to reload data from Google Sheets

## 📦 Installation

### Step 1: Install Dependencies

```bash
pip install -r requirements_dashboard.txt
```

### Step 2: Verify Service Account File

Make sure `pw-service-22bdcc39f732.json` is in the same directory.

### Step 3: Run Locally

```bash
python dashboard_app.py
```

Dashboard will open at: **http://localhost:8050**

## 🚀 Deploy to Vercel

### Step 1: Install Vercel CLI

```bash
npm install -g vercel
```

### Step 2: Login to Vercel

```bash
vercel login
```

### Step 3: Deploy

```bash
cd "c:\Users\Aaftaab Ahmad Khan\Documents\Database Automation"
vercel
```

Follow the prompts:
- Set up and deploy? **Y**
- Which scope? Select your account
- Link to existing project? **N**
- Project name? **batch-enrollment-dashboard**
- Directory? **./** (current directory)
- Override settings? **N**

### Step 4: Add Service Account Credentials

After deployment, add the service account JSON as environment variable:

1. Go to Vercel Dashboard: https://vercel.com/dashboard
2. Select your project
3. Go to **Settings** → **Environment Variables**
4. Add variable:
   - **Name**: `SERVICE_ACCOUNT_JSON`
   - **Value**: Paste entire contents of `pw-service-22bdcc39f732.json`
   - **Environments**: Production, Preview, Development

### Step 5: Update Code for Environment Variable (Optional)

If using environment variables, modify `dashboard_app.py`:

```python
import os
import json

# Load service account from environment variable
if os.getenv('SERVICE_ACCOUNT_JSON'):
    service_account_info = json.loads(os.getenv('SERVICE_ACCOUNT_JSON'))
    creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
else:
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
```

### Step 6: Redeploy

```bash
vercel --prod
```

## 🔄 Automatic Daily Updates at 9 AM

### Option 1: Vercel Cron Jobs (Recommended)

Create `vercel.json` with cron configuration:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "dashboard_app.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "dashboard_app.py"
    }
  ],
  "crons": [
    {
      "path": "/api/refresh",
      "schedule": "0 9 * * *"
    }
  ]
}
```

### Option 2: External Cron Service

Use services like:
- **Cron-job.org**: Free cron service
- **EasyCron**: Scheduled HTTP requests
- **GitHub Actions**: Workflow to trigger refresh

Example GitHub Actions workflow:

```yaml
name: Daily Dashboard Refresh
on:
  schedule:
    - cron: '0 9 * * *'  # 9 AM UTC daily

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Dashboard Refresh
        run: |
          curl -X GET https://your-vercel-app.vercel.app/?refresh=true
```

## 📊 Dashboard Components

### Summary Cards
- **Total Enrollment**: Count of all enrollments in selected period
- **Last 7 Days**: Recent enrollment count
- **Total Revenue**: Sum of net_amount
- **Average Order Value**: Mean net_amount

### Charts
1. **Overall Enrollment Batchwise**: Horizontal bar chart (top 15)
2. **Last 7 Days Trend**: Line chart with multiple batches
3. **Exam Distribution**: Donut chart by exam category
4. **Batch Eligibility**: Donut chart showing Only_base_batch, etc.

### Filters
- Date range picker
- Multi-select dropdown for batches
- Multi-select dropdown for exam categories
- Refresh button to reload data

## 🎨 Customization

### Colors
Primary: `#1976D2` (Blue)
Secondary: `#FF9800` (Orange)
Success: `#4CAF50` (Green)
Purple: `#9C27B0`

### Update Spreadsheet ID
Change in `dashboard_app.py`:
```python
SPREADSHEET_ID = "your-spreadsheet-id"
WORKSHEET_NAME = "your-worksheet-name"
```

## 🐛 Troubleshooting

### Error: Module not found
```bash
pip install -r requirements_dashboard.txt
```

### Error: Service account authentication failed
- Verify `pw-service-22bdcc39f732.json` exists
- Check if service account has access to the Google Sheet

### Dashboard not loading data
- Click "Refresh Data" button
- Check browser console for errors
- Verify spreadsheet ID and worksheet name

### Vercel deployment fails
- Check `vercel.json` syntax
- Ensure all files are committed
- Check build logs in Vercel dashboard

## 📝 Files Created

- `dashboard_app.py` - Main dashboard application
- `requirements_dashboard.txt` - Python dependencies
- `vercel.json` - Vercel deployment configuration
- `README_DASHBOARD.md` - This file

## 🔐 Security Notes

⚠️ **IMPORTANT**: Do not commit `pw-service-22bdcc39f732.json` to public repositories!

Add to `.gitignore`:
```
pw-service-22bdcc39f732.json
*.json
!vercel.json
```

## 📞 Support

Dashboard connects to Google Sheet ID: `14XMNROBL6PT_GYq43AVJb9e_IowOZp_ZP_IpCwmQCgs`

For issues, check:
1. Service account has Viewer/Editor access to sheet
2. Worksheet name matches exactly
3. Data columns match expected format

---

**Enjoy your interactive dashboard! 🎉**
