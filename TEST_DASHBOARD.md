# Quick Test Instructions for Dashboard

## ✅ Installation Complete!

All dependencies have been installed successfully.

## 🚀 Run the Dashboard

### Method 1: Double-click the batch file
```
run_dashboard.bat
```

### Method 2: Run from terminal
```bash
cd "c:\Users\Aaftaab Ahmad Khan\Documents\Database Automation"
python dashboard_app.py
```

## 🌐 Access the Dashboard

Once running, open your browser and go to:
**http://localhost:8050**

## 📋 What to Expect

You'll see:
1. **Header** with title and last updated time
2. **Filters Section** with:
   - Date range picker
   - Batch name dropdown
   - Exam category dropdown
   - Refresh data button
3. **Summary Cards** showing:
   - Total Enrollment
   - Last 7 Days count
   - Total Revenue
   - Average Order Value
4. **Charts**:
   - Overall Enrollment Batchwise (Bar chart)
   - Last 7 Days Enrollment (Time series)
   - Enrollment by Exam (Pie chart)
   - Batch Eligibility (Donut chart)
5. **Data Table** with first 50 records

## 🔄 Testing Steps

1. **Start the dashboard**
2. **Wait for data to load** (may take 10-30 seconds on first run)
3. **Try the filters**:
   - Select a date range
   - Choose specific batches
   - Filter by exam categories
4. **Click "Refresh Data"** to reload from Google Sheets
5. **Interact with charts** (hover, zoom, pan)

## 🐛 If You See "No data available"

This means the dashboard is working, but:
- The Google Sheet might be empty
- The worksheet name doesn't match
- Service account doesn't have access

**Solution**: Update these settings in `dashboard_app.py`:
```python
SPREADSHEET_ID = "14XMNROBL6PT_GYq43AVJb9e_IowOZp_ZP_IpCwmQCgs"
WORKSHEET_NAME = "Batch Enrollment"  # ← Change this to your actual worksheet name
```

## 📸 Screenshot Checklist

Before deploying to Vercel, verify:
- ✅ Dashboard loads without errors
- ✅ Filters work correctly
- ✅ Charts display data
- ✅ Table shows records
- ✅ Refresh button reloads data
- ✅ Responsive design (try resizing browser)

## ⏭️ Next Steps

Once you've verified everything works locally:

1. **Test with real data** from your Google Sheet
2. **Deploy to Vercel** (see README_DASHBOARD.md)
3. **Set up daily automation** (see README_DASHBOARD.md)

## 🎉 You're Ready!

Your Python dashboard is fully functional and ready for deployment!
