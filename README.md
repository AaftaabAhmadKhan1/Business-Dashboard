# 🚀 Metabase to Google Sheets Automation

**Simple data fetcher that automatically uploads data from Metabase to Google Sheets**

---

## 📋 Quick Overview

This automation:
- ✅ Fetches data from Metabase/Trino using SQL queries
- ✅ Uploads directly to Google Sheets (no comparison)
- ✅ Single self-contained Jupyter notebook
- ✅ Duplicate notebook for multiple sheets
- ✅ All configuration inside the notebook

---

## 🎯 Quick Start (3 Steps)

### Step 1: Upload Files to Jupyter

1. Go to: `http://jupyter-analytics.penpencil.co/`
2. Upload these files:
   - `DataFetcher.ipynb` ⭐ (main notebook)
   - `pw-service-22bdcc39f732.json` (service account)

### Step 2: Install Packages

In Jupyter notebook cell or terminal:

```python
!pip install --user pandas gspread gspread-dataframe google-auth google-auth-oauthlib google-auth-httplib2 PyYAML
```

**Note:** The `--user` flag avoids permission errors.

### Step 3: Share Google Sheet

1. Open `pw-service-22bdcc39f732.json`
2. Copy the email from `"client_email"` line
3. Open your Google Sheet: https://docs.google.com/spreadsheets/d/14XMNROBL6PT_GYq43AVJb9e_IowOZp_ZP_IpCwmQCgs/edit
4. Click "Share" → Paste email → Set as "Editor" → Uncheck "Notify" → Share

---

## 🚀 How to Run

1. Open `DataFetcher.ipynb` in Jupyter
2. Edit the configuration in the first code cell:
   - Set your worksheet name
   - Update SQL query
   - Choose date mode
3. Run all cells (Cell → Run All)
4. Check your Google Sheet!

### For Multiple Sheets:

1. **Duplicate the notebook:**
   - Right-click `DataFetcher.ipynb` → Duplicate
   - Rename to: `Sheet2_UserActivity.ipynb`
2. **Edit configuration** in the duplicate
3. **Run all cells**

---

## ⚙️ Configuration

All configuration is in the **first code cell** of `DataFetcher.ipynb`:

```python
# ========== CONFIGURATION - EDIT THIS ========== #

# Google Sheets Settings
SPREADSHEET_ID = "14XMNROBL6PT_GYq43AVJb9e_IowOZp_ZP_IpCwmQCgs"
WORKSHEET_NAME = "Video Stats"  # Tab name in Google Sheet
SERVICE_ACCOUNT_FILE = "pw-service-22bdcc39f732.json"

# Query Settings
QUERY_NAME = "Video Stats Report"
SQL_QUERY = """
SELECT 
    glob_unique_id, 
    batch_id, 
    type_id, 
    user_id, 
    time_watched_in_sec_timestamp
FROM cdp.reports.gold_dbt_video_stats_reports_unified
WHERE date(session_date) = date '{date}'
"""

# Date Settings
DATE_MODE = 'yesterday'  # Options: 'today', 'yesterday', 'specific'
SPECIFIC_DATE = '2025-11-06'
DAYS_BACK = 1
```

### Example Queries

#### User Activity:
```python
WORKSHEET_NAME = "User Activity"
SQL_QUERY = """
SELECT user_id, COUNT(*) as sessions
FROM cdp.reports.gold_user_activity
WHERE date(session_date) = date '{date}'
GROUP BY user_id
"""
```

#### Daily Metrics:
```python
WORKSHEET_NAME = "Daily Metrics"
SQL_QUERY = """
SELECT 
    date(session_date) as date,
    COUNT(DISTINCT user_id) as users,
    SUM(time_watched_in_sec) as total_time
FROM cdp.reports.gold_dbt_video_stats_reports_unified
WHERE date(session_date) = date '{date}'
GROUP BY date(session_date)
"""
```

---

## 🔧 Customization

### Change Date Mode

Edit the configuration cell in the notebook:

```python
# Use yesterday's data (recommended)
DATE_MODE = 'yesterday'
DAYS_BACK = 1

# Use today's data
DATE_MODE = 'today'

# Use specific date
DATE_MODE = 'specific'
SPECIFIC_DATE = '2025-11-06'
```

### Change SQL Query

Edit the `SQL_QUERY` variable:

```python
SQL_QUERY = """
SELECT 
  column1,
  column2,
  COUNT(*) as total
FROM your_table
WHERE date(created_at) = date '{date}'
GROUP BY column1, column2
ORDER BY total DESC
"""
```

### Create New Sheet

1. **Duplicate the notebook:**
   - In Jupyter, right-click `DataFetcher.ipynb`
   - Select "Duplicate"
   - Rename to `MyNewSheet.ipynb`

2. **Edit configuration:**
   - Open the duplicate
   - Change `WORKSHEET_NAME` to your new tab name
   - Update `SQL_QUERY` with your query
   - Update `QUERY_NAME`

3. **Run all cells**

---

## 🕒 Schedule Automation (Optional)

To run your notebook automatically:

### Option 1: Use Jupyter's Built-in Scheduler

Convert notebook to script and schedule it:

```bash
# Convert notebook to Python script
jupyter nbconvert --to script DataFetcher.ipynb

# Schedule with cron (in terminal)
crontab -e

# Add this line:
0 9 * * * cd /path/to/Database_Automation && python DataFetcher.py >> automation.log 2>&1
```

### Option 2: Use Papermill

```python
# Install papermill
!pip install --user papermill

# Run notebook with papermill
import papermill as pm
pm.execute_notebook('DataFetcher.ipynb', 'output.ipynb')
```

---

## 📊 Output Format

Each Google Sheet tab will have:

```
Row 1: Report Name
Row 2: Query Date: 2025-11-06
Row 3: Generated: 2025-11-06 09:00:15
Row 4: Total Records: 1234
Row 5: [empty]
Row 6: [Headers - Bold, Blue Background]
Row 7+: [Your Data]
```

---

## 📝 Check Output

All output is shown directly in the notebook cells. You can also check:

```bash
# If you scheduled it as a script
tail -50 automation.log

# Monitor real-time
tail -f automation.log
```

---

## 🐛 Troubleshooting

### Error: Permission denied (pip install)

**Solution:** Use `--user` flag:
```bash
pip install --user package-name
```

### Error: Permission denied (Google Sheets)

**Solution:**
1. Open `pw-service-22bdcc39f732.json`
2. Find `client_email` value
3. Share Google Sheet with that email (Editor access)

### Error: Module 'python_utils_common' not found

**Solution:** Check path in the notebook setup cell:
```python
sys.path.append('/home/jovyan/shared/python_utils/')
```
If the path is different in your environment, update it accordingly.

### Error: No data returned

**Solution:**
1. Check if data exists for the date
2. Try different date mode:
   ```yaml
   date_settings:
     mode: 'specific'
     specific_date: '2025-08-29'  # Use date with known data
   ```

### Error: Spreadsheet not found

**Solution:**
1. Verify spreadsheet ID in config
2. Ensure sheet is shared with service account
3. Check if you can open the sheet manually

---

## 🔐 Create Service Account (If Needed)

If you don't have `pw-service-22bdcc39f732.json`:

1. Go to: https://console.cloud.google.com/
2. Create/Select project
3. Enable APIs:
   - Google Sheets API
   - Google Drive API
4. Create Service Account:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "Service Account"
   - Fill in name and details
5. Create JSON Key:
   - Click on service account
   - Go to "Keys" tab
   - "Add Key" → "Create new key" → JSON
   - Download file
6. Share your Google Sheet with the service account email

---

## 📁 Project Files

```
Database Automation/
│
├── DataFetcher.ipynb            ⭐ Main notebook (duplicate for new sheets)
├── pw-service-22bdcc39f732.json   Service account credentials
├── README.md                      This guide
└── requirements.txt               Package dependencies

After duplication, you might have:
├── DataFetcher.ipynb
├── Sheet2_UserActivity.ipynb
├── Sheet3_DailyMetrics.ipynb
└── Sheet4_ContentPerf.ipynb
```

---

## 📋 Quick Commands Reference

```bash
# Install packages (run once)
pip install --user pandas gspread gspread-dataframe google-auth google-auth-oauthlib google-auth-httplib2

# In Jupyter:
# 1. Open DataFetcher.ipynb
# 2. Edit configuration (first cell)
# 3. Run all cells (Cell → Run All)

# To duplicate for new sheet:
# Right-click notebook → Duplicate → Rename → Edit config → Run
```

---

## ✅ Success Checklist

- [ ] Files uploaded to Jupyter
- [ ] Packages installed with `--user` flag
- [ ] Service account JSON file present
- [ ] Google Sheet shared with service account email
- [ ] Config files have correct spreadsheet ID
- [ ] Test run successful (no errors)
- [ ] Google Sheet tabs updated with data
- [ ] Cron job scheduled (optional)

---

## 🎉 You're Ready!

**Open `DataFetcher.ipynb` and run all cells to get started!**

Your automation will:
1. Fetch data from Metabase/Trino based on your SQL query
2. Upload to your specified Google Sheets tab
3. Format everything nicely with headers and metadata
4. Show all output directly in the notebook

**For multiple sheets:** Just duplicate the notebook and edit the configuration!

**Support:** All output is shown in the notebook cells. Check for error messages there.

---

**Version:** 2.0  
**Last Updated:** November 6, 2025  
**Google Sheet:** https://docs.google.com/spreadsheets/d/14XMNROBL6PT_GYq43AVJb9e_IowOZp_ZP_IpCwmQCgs/edit
