"""
Batch Enrollment Dashboard
Interactive dashboard with filters and visualizations
Deployable on Vercel
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, dcc, html, Input, Output, State, callback
import dash
import dash_bootstrap_components as dbc
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import io
import base64
import time
import os
import json

# ========================================================================================================
# CONFIGURATION
# ========================================================================================================

SPREADSHEET_ID = "14XMNROBL6PT_GYq43AVJb9e_IowOZp_ZP_IpCwmQCgs"
WORKSHEET_NAMES = ["Foundation Data", "CUET UG Data"]  # List of all worksheets to load
SERVICE_ACCOUNT_FILE = "pw-service-22bdcc39f732.json"

# Global cache
DATA_CACHE = None
CACHE_TIMESTAMP = None
CACHE_DURATION = 300  # 5 minutes

# ========================================================================================================
# DATA LOADING FUNCTION (OPTIMIZED)
# ========================================================================================================

def get_google_credentials():
    """Get Google credentials from file or environment variable"""
    # Try to get credentials from environment variable (for Vercel)
    creds_json = os.getenv('GOOGLE_CREDENTIALS')
    if creds_json:
        try:
            creds_dict = json.loads(creds_json)
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            return Credentials.from_service_account_info(creds_dict, scopes=scope)
        except Exception as e:
            print(f"Error loading credentials from environment: {e}")
    
    # Fallback to local file (for local development)
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        return Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
    
    raise Exception("No Google credentials found. Set GOOGLE_CREDENTIALS environment variable or provide service account file.")

def load_data_from_sheets(force_refresh=False):
    """Load data from Google Sheets (all worksheets) with caching for performance"""
    global DATA_CACHE, CACHE_TIMESTAMP
    
    # Check cache
    current_time = time.time()
    if not force_refresh and DATA_CACHE is not None:
        if CACHE_TIMESTAMP is not None and (current_time - CACHE_TIMESTAMP) < CACHE_DURATION:
            print(f"✓ Using cached data")
            return DATA_CACHE.copy()
    
    print(f"⟳ Loading fresh data from all sheets...")
    start_time = time.time()
    
    try:
        creds = get_google_credentials()
        client = gspread.authorize(creds)
        
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        
        all_dfs = []
        for worksheet_name in WORKSHEET_NAMES:
            print(f"  Loading {worksheet_name}...")
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
                
                # Get all values to find the correct header row
                data = worksheet.get_all_values()
                
                # Find where the actual data starts (skip metadata rows)
                header_row = 0
                for i, row in enumerate(data):
                    if row and any(col in str(row).lower() for col in ['batchid', '_id', 'name', 'converteddate']):
                        header_row = i
                        print(f"    Found header at row {header_row + 1}")
                        break
                
                # Create DataFrame from the correct header row
                sheet_df = pd.DataFrame(data[header_row + 1:], columns=data[header_row])
                print(f"    Loaded {len(sheet_df)} rows from {worksheet_name}")
                
                # Clean column names
                sheet_df.columns = sheet_df.columns.str.strip()
                
                # Handle column name variations
                if 'batch_name' in sheet_df.columns and 'name' not in sheet_df.columns:
                    sheet_df['name'] = sheet_df['batch_name']
                if 'exam_2' in sheet_df.columns and 'Exam_2' not in sheet_df.columns:
                    sheet_df['Exam_2'] = sheet_df['exam_2']
                elif 'exam' in sheet_df.columns and 'Exam_2' not in sheet_df.columns:
                    sheet_df['Exam_2'] = sheet_df['exam']
                
                all_dfs.append(sheet_df)
                
            except Exception as e:
                print(f"    Error loading {worksheet_name}: {e}")
                continue
        
        # Combine all dataframes
        if not all_dfs:
            print("  No data loaded from any sheet!")
            return pd.DataFrame(columns=[
                '_id', 'batchid', 'plan', 'converteddate', 'name', 'net_amount', 
                'coupondiscount', 'couponcode', 'couponid', 'donationamount', 
                'Exam_2', 'order_type', 'batch_eligibility', 'startdate', 'ADD_ON_STORE',
                'leader_fin', 'type_2'
            ])
        
        df = pd.concat(all_dfs, ignore_index=True)
        print(f"  Combined {len(df)} total rows from {len(all_dfs)} sheets")
        print(f"  Columns found: {list(df.columns)[:10]}...")  # Show first 10 columns
        
        # Convert date columns with proper handling
        if 'converteddate' in df.columns:
            df['converteddate'] = pd.to_datetime(df['converteddate'], errors='coerce')
            print(f"  Converted 'converteddate' to datetime")
        if 'startdate' in df.columns:
            df['startdate'] = pd.to_datetime(df['startdate'], errors='coerce')
        
        # Convert numeric columns and optimize data types for memory
        numeric_cols = ['net_amount', 'coupondiscount', 'donationamount', 'ADD_ON_STORE']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                # Use float32 instead of float64 to save memory
                df[col] = df[col].astype('float32')
        
        # Optimize string columns - convert to category dtype for repeated values
        string_cols = ['name', 'plan', 'Exam_2', 'order_type', 'batch_eligibility', 
                      'couponcode', 'couponid', 'leader_fin', 'type_2']
        for col in string_cols:
            if col in df.columns and df[col].dtype == 'object':
                # Convert to category if column has less than 50% unique values
                if df[col].nunique() / len(df) < 0.5:
                    df[col] = df[col].astype('category')
        
        # Remove empty rows
        df = df.dropna(how='all')
        
        # Remove rows with NaT dates if converteddate is required
        if 'converteddate' in df.columns:
            before_count = len(df)
            df = df[df['converteddate'].notna()]
            if before_count != len(df):
                print(f"  Removed {before_count - len(df)} rows with invalid dates")
        
        # Handle empty data
        if len(df) == 0:
            print(f"⚠ Warning: No data found")
            return pd.DataFrame(columns=[
                '_id', 'batchid', 'plan', 'converteddate', 'name', 'net_amount', 
                'coupondiscount', 'couponcode', 'couponid', 'donationamount', 
                'Exam_2', 'order_type', 'batch_eligibility', 'startdate', 'ADD_ON_STORE',
                'leader_fin', 'type_2'
            ])
        
        # Cache the data
        DATA_CACHE = df.copy()
        CACHE_TIMESTAMP = current_time
        
        load_time = time.time() - start_time
        print(f"✓ Loaded {len(df)} rows in {load_time:.2f}s")
        if 'converteddate' in df.columns:
            print(f"  Date range: {df['converteddate'].min()} to {df['converteddate'].max()}")
        if 'name' in df.columns:
            print(f"  Unique batches: {df['name'].nunique()}")
        if 'Exam_2' in df.columns:
            print(f"  Unique exams: {df['Exam_2'].nunique()}")
        
        return df
    
    except Exception as e:
        print(f"✗ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=[
            '_id', 'batchid', 'plan', 'converteddate', 'name', 'net_amount', 
            'coupondiscount', 'couponcode', 'couponid', 'donationamount', 
            'Exam_2', 'order_type', 'batch_eligibility', 'startdate', 'ADD_ON_STORE',
            'leader_fin', 'type_2'
        ])

# ========================================================================================================
# INITIALIZE APP
# ========================================================================================================

app = Dash(__name__, 
            title="Batch Enrollment Dashboard", 
            suppress_callback_exceptions=True,
            external_stylesheets=[dbc.themes.BOOTSTRAP],
            external_scripts=['https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js'])
server = app.server  # For Vercel deployment

# Load initial data only in local development, not in serverless
try:
    if os.getenv('VERCEL'):
        print("Running on Vercel - data will be loaded on first request")
        df = pd.DataFrame()  # Empty dataframe for initialization
    else:
        print("Running locally - loading data now")
        df = load_data_from_sheets()
except Exception as e:
    print(f"Warning: Could not load initial data: {e}")
    df = pd.DataFrame()

# ========================================================================================================
# LAYOUT
# ========================================================================================================

app.layout = html.Div([
    # Header
    html.Div([
        html.H1("📊 Batch Enrollment Dashboard", 
                style={'textAlign': 'center', 'color': '#1976D2', 'marginBottom': '10px'}),
        html.P(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
               style={'textAlign': 'center', 'color': '#666', 'fontSize': '14px'}),
    ], style={'backgroundColor': '#f5f5f5', 'padding': '20px', 'marginBottom': '20px'}),
    
    # Filters Section
    html.Div([
        html.H3("🔍 Filters", style={'color': '#1976D2', 'marginBottom': '15px'}),
        
        html.Div([
            # Date Range Filter
            html.Div([
                html.Label("Date Range:", style={'fontWeight': 'bold', 'marginBottom': '5px'}),
                dcc.DatePickerRange(
                    id='date-filter',
                    start_date=df['converteddate'].min() if 'converteddate' in df.columns else datetime.now() - timedelta(days=30),
                    end_date=df['converteddate'].max() if 'converteddate' in df.columns else datetime.now(),
                    display_format='YYYY-MM-DD',
                    style={'width': '100%'}
                ),
            ], style={'width': '18%', 'display': 'inline-block', 'marginRight': '2%'}),
            
            # Batch Name Filter with Checkboxes
            html.Div([
                html.Label("Batch Name:", style={'fontWeight': 'bold', 'marginBottom': '5px'}),
                html.Div([
                    dcc.Input(
                        id='batch-search',
                        type='text',
                        placeholder='🔍 Search batches...',
                        style={'width': '100%', 'padding': '8px', 'border': '1px solid #ccc', 'borderRadius': '4px'}
                    ),
                    html.Div([
                        dcc.Checklist(
                            id='batch-filter',
                            options=[{'label': f' {name}', 'value': name} for name in sorted(df['name'].unique()) if pd.notna(name)] if 'name' in df.columns else [],
                            value=[],
                            inline=False,
                            style={'maxHeight': '150px', 'overflowY': 'auto', 'padding': '10px', 'backgroundColor': 'white'}
                        ),
                    ], id='batch-dropdown', style={'display': 'none', 'position': 'absolute', 'zIndex': '1000', 
                                                     'border': '1px solid #ccc', 'borderRadius': '4px', 
                                                     'backgroundColor': 'white', 'width': '100%', 'marginTop': '2px'}),
                ], style={'position': 'relative'}),
            ], style={'width': '18%', 'display': 'inline-block', 'marginRight': '2%'}),
            
            # Exam Category Filter with Checkboxes
            html.Div([
                html.Label("Exam Category:", style={'fontWeight': 'bold', 'marginBottom': '5px'}),
                html.Div([
                    dcc.Input(
                        id='exam-search',
                        type='text',
                        placeholder='🔍 Search exams...',
                        style={'width': '100%', 'padding': '8px', 'border': '1px solid #ccc', 'borderRadius': '4px'}
                    ),
                    html.Div([
                        dcc.Checklist(
                            id='exam-filter',
                            options=[{'label': f' {exam}', 'value': exam} for exam in sorted(df['Exam_2'].unique()) if pd.notna(exam)] if 'Exam_2' in df.columns else [],
                            value=[],
                            inline=False,
                            style={'maxHeight': '150px', 'overflowY': 'auto', 'padding': '10px', 'backgroundColor': 'white'}
                        ),
                    ], id='exam-dropdown', style={'display': 'none', 'position': 'absolute', 'zIndex': '1000', 
                                                    'border': '1px solid #ccc', 'borderRadius': '4px', 
                                                    'backgroundColor': 'white', 'width': '100%', 'marginTop': '2px'}),
                ], style={'position': 'relative'}),
            ], style={'width': '18%', 'display': 'inline-block', 'marginRight': '2%'}),
            
            # Plan Filter with Checkboxes
            html.Div([
                html.Label("Plan:", style={'fontWeight': 'bold', 'marginBottom': '5px'}),
                html.Div([
                    dcc.Input(
                        id='plan-search',
                        type='text',
                        placeholder='🔍 Search plans...',
                        style={'width': '100%', 'padding': '8px', 'border': '1px solid #ccc', 'borderRadius': '4px'}
                    ),
                    html.Div([
                        dcc.Checklist(
                            id='plan-filter',
                            options=[{'label': f' {plan}', 'value': plan} for plan in sorted(df['plan'].unique()) if pd.notna(plan) and str(plan).strip() != ''] if 'plan' in df.columns else [],
                            value=[],
                            inline=False,
                            style={'maxHeight': '150px', 'overflowY': 'auto', 'padding': '10px', 'backgroundColor': 'white'}
                        ),
                    ], id='plan-dropdown', style={'display': 'none', 'position': 'absolute', 'zIndex': '1000', 
                                                    'border': '1px solid #ccc', 'borderRadius': '4px', 
                                                    'backgroundColor': 'white', 'width': '100%', 'marginTop': '2px'}),
                ], style={'position': 'relative'}),
            ], style={'width': '18%', 'display': 'inline-block', 'marginRight': '2%'}),
            
            # Action Buttons
            html.Div([
                html.Label("Actions:", style={'fontWeight': 'bold', 'marginBottom': '5px'}),
                html.Button(' Reset Filters', id='reset-button', n_clicks=0,
                           style={'width': '100%', 'padding': '10px', 'backgroundColor': '#FF9800', 
                                  'color': 'white', 'border': 'none', 'borderRadius': '5px', 
                                  'cursor': 'pointer', 'fontWeight': 'bold'}),
            ], style={'width': '18%', 'display': 'inline-block'}),
        ], style={'marginBottom': '20px'}),
    ], style={'backgroundColor': 'white', 'padding': '20px', 'marginBottom': '20px', 'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'}),
    
    # Summary Cards
    html.Div(id='summary-cards', style={'marginBottom': '20px'}),
    
    # Charts Section
    html.Div([
        # Overall Enrollment Batchwise
        html.Div([
            html.Div([
                html.H3("📈 Overall Enrollment Batchwise", style={'color': '#1976D2', 'display': 'inline-block', 'marginRight': '10px'}),
                html.Button('📥 Export Excel', id='export-overall-btn', n_clicks=0,
                           style={'padding': '5px 15px', 'backgroundColor': '#4CAF50', 'color': 'white', 
                                  'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 
                                  'fontSize': '12px', 'fontWeight': 'bold'}),
                dcc.Download(id='download-overall'),
            ], style={'marginBottom': '15px'}),
            dcc.Graph(id='overall-enrollment-chart'),
        ], style={'backgroundColor': 'white', 'padding': '20px', 'marginBottom': '20px', 
                  'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'}),
        
        # Last 7 Days Enrollment
        html.Div([
            html.Div([
                html.H3("📅 Last 7 Days Enrollment Batchwise", style={'color': '#1976D2', 'display': 'inline-block', 'marginRight': '10px'}),
                html.Button('📥 Export Excel', id='export-last7-btn', n_clicks=0,
                           style={'padding': '5px 15px', 'backgroundColor': '#4CAF50', 'color': 'white', 
                                  'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 
                                  'fontSize': '12px', 'fontWeight': 'bold'}),
                dcc.Download(id='download-last7'),
            ], style={'marginBottom': '15px'}),
            dcc.Graph(id='last-7-days-chart'),
        ], style={'backgroundColor': 'white', 'padding': '20px', 'marginBottom': '20px', 
                  'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'}),
        
        # Revenue Trend (Last 7 Days)
        html.Div([
            html.Div([
                html.H3("💰 Revenue Trend (Last 7 Days)", style={'color': '#1976D2', 'display': 'inline-block', 'marginRight': '10px'}),
                html.Button('📥 Export Excel', id='export-revenue-trend-btn', n_clicks=0,
                           style={'padding': '5px 15px', 'backgroundColor': '#4CAF50', 'color': 'white', 
                                  'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 
                                  'fontSize': '12px', 'fontWeight': 'bold'}),
                dcc.Download(id='download-revenue-trend'),
            ], style={'marginBottom': '15px'}),
            dcc.Graph(id='revenue-trend-chart'),
        ], style={'backgroundColor': 'white', 'padding': '20px', 'marginBottom': '20px', 
                  'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'}),
        
        # Additional Charts Row
        html.Div([
            # Exam Distribution
            html.Div([
                html.Div([
                    html.H3("🎯 Enrollment by Exam", style={'color': '#1976D2', 'fontSize': '18px', 'display': 'inline-block', 'marginRight': '10px'}),
                    html.Button('📥', id='export-exam-dist-btn', n_clicks=0,
                               style={'padding': '5px 10px', 'backgroundColor': '#4CAF50', 'color': 'white', 
                                      'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 
                                      'fontSize': '12px', 'fontWeight': 'bold'}),
                    dcc.Download(id='download-exam-dist'),
                ], style={'marginBottom': '10px'}),
                dcc.Graph(id='exam-distribution-chart'),
            ], style={'width': '48%', 'display': 'inline-block', 'backgroundColor': 'white', 
                      'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)', 
                      'marginRight': '2%'}),
            
            # Revenue by Exam
            html.Div([
                html.Div([
                    html.H3("💰 Revenue by Exam", style={'color': '#1976D2', 'fontSize': '18px', 'display': 'inline-block', 'marginRight': '10px'}),
                    html.Button('📥', id='export-revenue-exam-btn', n_clicks=0,
                               style={'padding': '5px 10px', 'backgroundColor': '#4CAF50', 'color': 'white', 
                                      'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 
                                      'fontSize': '12px', 'fontWeight': 'bold'}),
                    dcc.Download(id='download-revenue-exam'),
                ], style={'marginBottom': '10px'}),
                dcc.Graph(id='revenue-chart'),
            ], style={'width': '48%', 'display': 'inline-block', 'backgroundColor': 'white', 
                      'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'}),
        ], style={'marginBottom': '20px'}),
        
        # Detailed Table
        html.Div([
            html.Div([
                html.H3("📋 Detailed Enrollment Data", style={'color': '#1976D2', 'display': 'inline-block', 'marginRight': '10px'}),
                html.Button('📥 Export Full Data', id='export-table-btn', n_clicks=0,
                           style={'padding': '5px 15px', 'backgroundColor': '#4CAF50', 'color': 'white', 
                                  'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 
                                  'fontSize': '12px', 'fontWeight': 'bold', 'marginRight': '10px'}),
                html.Button('📸 Download Screenshot', id='screenshot-table-btn', n_clicks=0,
                           style={'padding': '5px 15px', 'backgroundColor': '#2196F3', 'color': 'white', 
                                  'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 
                                  'fontSize': '12px', 'fontWeight': 'bold'}),
                dcc.Download(id='download-table'),
            ], style={'marginBottom': '15px'}),
            html.Div(id='data-table'),
        ], style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px', 
                  'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'}, id='table-container'),
    ]),
    
    # Footer
    html.Div([
        html.P("Dashboard auto-updates daily at 9 AM IST | Data refreshed from Google Sheets",
               style={'textAlign': 'center', 'color': '#666', 'fontSize': '12px', 'marginTop': '20px'}),
    ]),
    
    # Hidden div to store filtered data for exports
    html.Div(id='filtered-data-store', style={'display': 'none'}),
    
    # Store for dropdown states
    dcc.Store(id='batch-dropdown-state', data={'open': False}),
    dcc.Store(id='exam-dropdown-state', data={'open': False}),
    dcc.Store(id='plan-dropdown-state', data={'open': False}),
    
], style={'fontFamily': 'Arial, sans-serif', 'padding': '20px', 'backgroundColor': '#f5f5f5'})

# ========================================================================================================
# CLIENTSIDE CALLBACKS FOR DROPDOWN BLUR
# ========================================================================================================

# Close dropdown when clicking outside - Batch
app.clientside_callback(
    """
    function(n_clicks) {
        setTimeout(function() {
            const searchInput = document.getElementById('batch-search');
            const dropdown = document.getElementById('batch-dropdown');
            
            if (searchInput && dropdown) {
                searchInput.addEventListener('focus', function() {
                    dropdown.style.display = 'block';
                });
                
                document.addEventListener('click', function(e) {
                    if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
                        dropdown.style.display = 'none';
                    }
                });
            }
        }, 100);
        return window.dash_clientside.no_update;
    }
    """,
    Output('batch-dropdown-state', 'data'),
    Input('batch-search', 'id')
)

# Close dropdown when clicking outside - Exam
app.clientside_callback(
    """
    function(n_clicks) {
        setTimeout(function() {
            const searchInput = document.getElementById('exam-search');
            const dropdown = document.getElementById('exam-dropdown');
            
            if (searchInput && dropdown) {
                searchInput.addEventListener('focus', function() {
                    dropdown.style.display = 'block';
                });
                
                document.addEventListener('click', function(e) {
                    if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
                        dropdown.style.display = 'none';
                    }
                });
            }
        }, 100);
        return window.dash_clientside.no_update;
    }
    """,
    Output('exam-dropdown-state', 'data'),
    Input('exam-search', 'id')
)

# Close dropdown when clicking outside - Plan
app.clientside_callback(
    """
    function(n_clicks) {
        setTimeout(function() {
            const searchInput = document.getElementById('plan-search');
            const dropdown = document.getElementById('plan-dropdown');
            
            if (searchInput && dropdown) {
                searchInput.addEventListener('focus', function() {
                    dropdown.style.display = 'block';
                });
                
                document.addEventListener('click', function(e) {
                    if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
                        dropdown.style.display = 'none';
                    }
                });
            }
        }, 100);
        return window.dash_clientside.no_update;
    }
    """,
    Output('plan-dropdown-state', 'data'),
    Input('plan-search', 'id')
)

# ========================================================================================================
# CALLBACKS
# ========================================================================================================

# Update batch filter options based on search
@callback(
    Output('batch-filter', 'options'),
    Input('batch-search', 'value')
)
def update_batch_options(search_value):
    temp_df = load_data_from_sheets(force_refresh=False)
    all_batches = sorted(temp_df['name'].unique()) if 'name' in temp_df.columns else []
    all_batches = [b for b in all_batches if pd.notna(b)]
    
    # If search is None or empty, show all
    if not search_value or search_value.strip() == '':
        return [{'label': f' {name}', 'value': name} for name in all_batches]
    
    # Filter based on search
    search_lower = search_value.strip().lower()
    filtered = [b for b in all_batches if search_lower in b.lower()]
    return [{'label': f' {name}', 'value': name} for name in filtered]

# Update exam filter options based on search
@callback(
    Output('exam-filter', 'options'),
    Input('exam-search', 'value')
)
def update_exam_options(search_value):
    temp_df = load_data_from_sheets(force_refresh=False)
    all_exams = sorted(temp_df['Exam_2'].unique()) if 'Exam_2' in temp_df.columns else []
    all_exams = [e for e in all_exams if pd.notna(e)]
    
    # If search is None or empty, show all
    if not search_value or search_value.strip() == '':
        return [{'label': f' {exam}', 'value': exam} for exam in all_exams]
    
    # Filter based on search
    search_lower = search_value.strip().lower()
    filtered = [e for e in all_exams if search_lower in e.lower()]
    return [{'label': f' {exam}', 'value': exam} for exam in filtered]

# Update plan filter options based on search
@callback(
    Output('plan-filter', 'options'),
    Input('plan-search', 'value')
)
def update_plan_options(search_value):
    temp_df = load_data_from_sheets(force_refresh=False)
    all_plans = sorted(temp_df['plan'].unique()) if 'plan' in temp_df.columns else []
    # Filter out NaN, None, empty string, and 'None' string values
    all_plans = [p for p in all_plans if pd.notna(p) and str(p).strip() != '' and str(p).strip().lower() != 'none']
    
    # If search is None or empty, show all
    if not search_value or search_value.strip() == '':
        return [{'label': f' {plan}', 'value': plan} for plan in all_plans]
    
    # Filter based on search
    search_lower = search_value.strip().lower()
    filtered = [p for p in all_plans if search_lower in str(p).lower()]
    return [{'label': f' {plan}', 'value': plan} for plan in filtered]
    return [{'label': f' {plan}', 'value': plan} for plan in filtered]

# Toggle batch dropdown visibility
@callback(
    Output('batch-dropdown', 'style'),
    Input('batch-search', 'value')
)
def update_batch_dropdown(search_value):
    # Show dropdown when there's any text or empty (to trigger search update)
    if search_value is not None:
        return {'display': 'block', 'position': 'absolute', 'zIndex': '1000', 
                'border': '1px solid #ccc', 'borderRadius': '4px', 
                'backgroundColor': 'white', 'width': '100%', 'marginTop': '2px'}
    return {'display': 'none', 'position': 'absolute', 'zIndex': '1000', 
            'border': '1px solid #ccc', 'borderRadius': '4px', 
            'backgroundColor': 'white', 'width': '100%', 'marginTop': '2px'}

# Toggle exam dropdown visibility
@callback(
    Output('exam-dropdown', 'style'),
    Input('exam-search', 'value')
)
def update_exam_dropdown(search_value):
    # Show dropdown when there's any text or empty (to trigger search update)
    if search_value is not None:
        return {'display': 'block', 'position': 'absolute', 'zIndex': '1000', 
                'border': '1px solid #ccc', 'borderRadius': '4px', 
                'backgroundColor': 'white', 'width': '100%', 'marginTop': '2px'}
    return {'display': 'none', 'position': 'absolute', 'zIndex': '1000', 
            'border': '1px solid #ccc', 'borderRadius': '4px', 
            'backgroundColor': 'white', 'width': '100%', 'marginTop': '2px'}

# Toggle plan dropdown visibility
@callback(
    Output('plan-dropdown', 'style'),
    Input('plan-search', 'value')
)
def update_plan_dropdown(search_value):
    # Show dropdown when there's any text or empty (to trigger search update)
    if search_value is not None:
        return {'display': 'block', 'position': 'absolute', 'zIndex': '1000', 
                'border': '1px solid #ccc', 'borderRadius': '4px', 
                'backgroundColor': 'white', 'width': '100%', 'marginTop': '2px'}
    return {'display': 'none', 'position': 'absolute', 'zIndex': '1000', 
            'border': '1px solid #ccc', 'borderRadius': '4px', 
            'backgroundColor': 'white', 'width': '100%', 'marginTop': '2px'}

# Reset all filters
@callback(
    [Output('batch-filter', 'value'),
     Output('exam-filter', 'value'),
     Output('plan-filter', 'value'),
     Output('batch-search', 'value'),
     Output('exam-search', 'value'),
     Output('plan-search', 'value')],
    Input('reset-button', 'n_clicks'),
    prevent_initial_call=True
)
def reset_filters(n_clicks):
    if n_clicks > 0:
        return [], [], [], '', '', ''
    return [], [], [], '', '', ''

@callback(
    [Output('summary-cards', 'children'),
     Output('overall-enrollment-chart', 'figure'),
     Output('last-7-days-chart', 'figure'),
     Output('revenue-trend-chart', 'figure'),
     Output('exam-distribution-chart', 'figure'),
     Output('revenue-chart', 'figure'),
     Output('data-table', 'children'),
     Output('filtered-data-store', 'children')],
    [Input('date-filter', 'start_date'),
     Input('date-filter', 'end_date'),
     Input('batch-filter', 'value'),
     Input('exam-filter', 'value'),
     Input('plan-filter', 'value')]
)
def update_dashboard(start_date, end_date, batch_filter, exam_filter, plan_filter):
    # Load data (cached) - combines all sheets
    global df
    df = load_data_from_sheets(force_refresh=False)
    
    print(f"DEBUG: Loaded {len(df)} rows")
    if 'converteddate' in df.columns and not df.empty:
        print(f"DEBUG: Date range in data: {df['converteddate'].min()} to {df['converteddate'].max()}")
    if 'name' in df.columns and not df.empty:
        print(f"DEBUG: Sample batch names: {df['name'].head(3).tolist()}")
        print(f"DEBUG: Total unique batches: {df['name'].nunique()}")
    if 'Exam_2' in df.columns and not df.empty:
        print(f"DEBUG: Unique exams: {sorted(df['Exam_2'].unique())[:5]}")
    
    # Filter data
    filtered_df = df.copy()
    
    if 'converteddate' in filtered_df.columns:
        print(f"DEBUG: Filtering by dates: {start_date} to {end_date}")
        filtered_df = filtered_df[(filtered_df['converteddate'] >= start_date) & 
                                  (filtered_df['converteddate'] <= end_date)]
        print(f"DEBUG: After date filter: {len(filtered_df)} rows")
    
    if batch_filter and len(batch_filter) > 0 and 'name' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['name'].isin(batch_filter)]
        print(f"DEBUG: After batch filter: {len(filtered_df)} rows")
    
    if exam_filter and len(exam_filter) > 0 and 'Exam_2' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['Exam_2'].isin(exam_filter)]
        print(f"DEBUG: After exam filter: {len(filtered_df)} rows")
    
    if plan_filter and len(plan_filter) > 0 and 'plan' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['plan'].isin(plan_filter)]
    
    # Calculate metrics
    total_enrollment = len(filtered_df)
    last_7_days_df = filtered_df[filtered_df['converteddate'] >= (pd.Timestamp(end_date) - pd.Timedelta(days=7))] if 'converteddate' in filtered_df.columns else filtered_df
    last_7_days_count = len(last_7_days_df)
    
    total_revenue = filtered_df['net_amount'].sum() if 'net_amount' in filtered_df.columns else 0
    
    # Convert to Crores
    total_revenue_cr = total_revenue / 10000000  # 1 Crore = 10 Million
    
    # Summary Cards
    summary_cards = html.Div([
        # Total Enrollment Card
        html.Div([
            html.H4("Total Enrollment", style={'color': '#666', 'fontSize': '14px', 'marginBottom': '5px'}),
            html.H2(f"{total_enrollment:,}", style={'color': '#1976D2', 'margin': '0'}),
        ], style={'width': '30%', 'display': 'inline-block', 'backgroundColor': 'white', 
                  'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)', 
                  'marginRight': '5%', 'textAlign': 'center'}),
        
        # Last 7 Days Card
        html.Div([
            html.H4("Last 7 Days", style={'color': '#666', 'fontSize': '14px', 'marginBottom': '5px'}),
            html.H2(f"{last_7_days_count:,}", style={'color': '#FF9800', 'margin': '0'}),
        ], style={'width': '30%', 'display': 'inline-block', 'backgroundColor': 'white', 
                  'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)', 
                  'marginRight': '5%', 'textAlign': 'center'}),
        
        # Total Revenue Card
        html.Div([
            html.H4("Total Revenue", style={'color': '#666', 'fontSize': '14px', 'marginBottom': '5px'}),
            html.H2(f"₹{total_revenue_cr:.2f} Cr", style={'color': '#4CAF50', 'margin': '0'}),
        ], style={'width': '30%', 'display': 'inline-block', 'backgroundColor': 'white', 
                  'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)', 
                  'textAlign': 'center'}),
    ])
    
    # Chart 1: Overall Enrollment Batchwise
    if 'name' in filtered_df.columns:
        batch_enrollment = filtered_df['name'].value_counts().head(15).sort_values(ascending=True)
        fig1 = go.Figure(go.Bar(
            x=batch_enrollment.values,
            y=batch_enrollment.index,
            orientation='h',
            marker=dict(color='#1976D2'),
            text=batch_enrollment.values,
            textposition='outside'
        ))
        fig1.update_layout(
            title="Top 15 Batches by Enrollment",
            xaxis_title="Number of Enrollments",
            yaxis_title="Batch Name",
            height=450,
            showlegend=False,
            margin=dict(t=60, b=50, l=150, r=100)
        )
    else:
        fig1 = go.Figure()
        fig1.add_annotation(text="No data available", showarrow=False)
    
    # Chart 2: Last 7 Days Enrollment
    if 'converteddate' in last_7_days_df.columns:
        # Group by date only (overall, not by batch)
        last_7_trend = last_7_days_df.groupby('converteddate').size().reset_index(name='count')
        # Format dates without time
        last_7_trend['date_display'] = last_7_trend['converteddate'].dt.strftime('%d %b %Y')
        
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=last_7_trend['date_display'],
            y=last_7_trend['count'],
            mode='lines+markers+text',
            name='Total Enrollments',
            line=dict(color='#1976D2', width=3),
            marker=dict(size=10, color='#1976D2'),
            text=last_7_trend['count'],
            textposition='top center',
            textfont=dict(size=12, color='#1976D2', family='Arial Black'),
            fill='tozeroy',
            fillcolor='rgba(25, 118, 210, 0.1)'
        ))
        fig2.update_layout(
            title='Daily Enrollment Trend (Last 7 Days)',
            xaxis_title='Date',
            yaxis_title='Total Enrollments',
            height=500,
            hovermode='x unified',
            showlegend=False,
            margin=dict(t=60, b=100, l=80, r=80),
            xaxis=dict(
                tickangle=-45,
                tickmode='auto',
                automargin=True,
                type='category',
                range=[-0.5, len(last_7_trend)-0.5]
            ),
            yaxis=dict(
                rangemode='tozero'
            )
        )
    else:
        fig2 = go.Figure()
        fig2.add_annotation(text="No data available", showarrow=False)
    
    # Chart 2.5: Revenue Trend (Last 7 Days)
    if 'converteddate' in last_7_days_df.columns and 'net_amount' in last_7_days_df.columns:
        revenue_trend = last_7_days_df.groupby('converteddate')['net_amount'].sum().reset_index()
        revenue_trend['net_amount_cr'] = revenue_trend['net_amount'] / 10000000  # Convert to Crores
        # Format dates without time
        revenue_trend['date_display'] = revenue_trend['converteddate'].dt.strftime('%d %b %Y')
        
        fig2_5 = go.Figure()
        fig2_5.add_trace(go.Scatter(
            x=revenue_trend['date_display'],
            y=revenue_trend['net_amount_cr'],
            mode='lines+markers+text',
            name='Daily Revenue',
            line=dict(color='#4CAF50', width=3),
            marker=dict(size=10, color='#4CAF50'),
            text=[f"₹{val:.2f} Cr" for val in revenue_trend['net_amount_cr']],
            textposition='top center',
            textfont=dict(size=12, color='#4CAF50', family='Arial Black'),
            fill='tozeroy',
            fillcolor='rgba(76, 175, 80, 0.1)'
        ))
        fig2_5.update_layout(
            title='Daily Revenue Trend (Last 7 Days)',
            xaxis_title='Date',
            yaxis_title='Revenue (₹ Cr)',
            height=500,
            hovermode='x unified',
            yaxis=dict(
                tickformat='.2f', 
                tickprefix='₹', 
                ticksuffix=' Cr',
                rangemode='tozero'
            ),
            margin=dict(t=60, b=100, l=80, r=80),
            xaxis=dict(
                tickangle=-45,
                tickmode='auto',
                automargin=True,
                type='category',
                range=[-0.5, len(revenue_trend)-0.5]
            )
        )
    else:
        fig2_5 = go.Figure()
        fig2_5.add_annotation(text="No revenue data available", showarrow=False)
    
    # Chart 3: Exam Distribution
    if 'Exam_2' in filtered_df.columns:
        exam_dist = filtered_df['Exam_2'].value_counts()
        fig3 = go.Figure(go.Pie(
            labels=exam_dist.index,
            values=exam_dist.values,
            hole=0.4,
            marker=dict(colors=px.colors.qualitative.Set3)
        ))
        fig3.update_layout(
            height=300, 
            showlegend=True,
            margin=dict(t=50, b=30, l=50, r=50)
        )
    else:
        fig3 = go.Figure()
        fig3.add_annotation(text="No data available", showarrow=False)
    
    # Chart 4: Revenue by Exam
    if 'Exam_2' in filtered_df.columns and 'net_amount' in filtered_df.columns:
        revenue_by_exam = filtered_df.groupby('Exam_2')['net_amount'].sum().sort_values(ascending=False).head(10)
        revenue_by_exam_cr = revenue_by_exam / 10000000  # Convert to Crores
        
        fig4 = go.Figure(go.Bar(
            x=revenue_by_exam_cr.values,
            y=revenue_by_exam_cr.index,
            orientation='h',
            marker=dict(color='#4CAF50'),
            text=[f"₹{val:.2f} Cr" for val in revenue_by_exam_cr.values],
            textposition='outside'
        ))
        fig4.update_layout(
            title="Top 10 Exams by Revenue",
            xaxis_title="Revenue (₹ Cr)",
            yaxis_title="Exam Category",
            height=300,
            showlegend=False,
            margin=dict(t=50, b=40, l=120, r=100)
        )
    else:
        fig4 = go.Figure()
        fig4.add_annotation(text="No revenue data available", showarrow=False)
    
    # Data Table - Aggregated by Batch
    if 'name' in filtered_df.columns:
        # Aggregate data by batch
        agg_dict = {
            'Exam_2': 'first',  # Get exam category (assuming same batch = same exam)
        }
        
        # Add revenue aggregation if column exists
        if 'net_amount' in filtered_df.columns:
            agg_dict['net_amount'] = 'sum'
        
        # Add other useful columns
        if 'order_type' in filtered_df.columns:
            agg_dict['order_type'] = lambda x: f"{sum(x=='PRIMARY')} Primary, {sum(x=='UPGRADE')} Upgrade"
        
        if 'leader_fin' in filtered_df.columns:
            agg_dict['leader_fin'] = 'first'
        
        # Group by batch name and aggregate
        table_df = filtered_df.groupby('name').agg(agg_dict).reset_index()
        
        # Add enrollment count
        enrollment_counts = filtered_df.groupby('name').size().reset_index(name='Total Enrollments')
        table_df = table_df.merge(enrollment_counts, on='name', how='left')
        
        # Reorder columns
        cols_order = ['name', 'Total Enrollments']
        if 'Exam_2' in table_df.columns:
            cols_order.append('Exam_2')
        if 'net_amount' in table_df.columns:
            # Convert revenue to Crores
            table_df['net_amount'] = table_df['net_amount'] / 10000000
            cols_order.append('net_amount')
            table_df = table_df.rename(columns={'net_amount': 'Total Revenue (₹ Cr)'})
        if 'leader_fin' in table_df.columns:
            cols_order.append('leader_fin')
        if 'order_type' in table_df.columns:
            cols_order.append('order_type')
        
        # Rename columns for display
        table_df = table_df.rename(columns={
            'name': 'Batch Name',
            'Exam_2': 'Exam Category',
            'leader_fin': 'Leader',
            'order_type': 'Order Types'
        })
        
        # Keep only available columns
        display_cols = [col for col in cols_order if col in table_df.columns or 
                       col.replace('_', ' ').title() in table_df.columns]
        
        # Get final column names
        final_cols = []
        for col in cols_order:
            if col in table_df.columns:
                final_cols.append(col)
            else:
                renamed = col.replace('_', ' ').title()
                if renamed in table_df.columns:
                    final_cols.append(renamed)
        
        if len(final_cols) > 0:
            table_df = table_df[[c for c in table_df.columns if c in ['Batch Name', 'Total Enrollments', 'Exam Category', 'Total Revenue (₹ Cr)', 'Leader', 'Order Types']]]
            
            # Sort by Total Enrollments descending
            table_df = table_df.sort_values('Total Enrollments', ascending=False)
            
            # Format revenue if present
            if 'Total Revenue (₹ Cr)' in table_df.columns:
                table_df['Total Revenue (₹ Cr)'] = table_df['Total Revenue (₹ Cr)'].apply(lambda x: f"₹{x:.2f} Cr" if pd.notna(x) else "₹0")
        
        # Calculate totals for the footer row
        total_enrollments = table_df['Total Enrollments'].sum() if 'Total Enrollments' in table_df.columns else 0
        total_revenue_sum = filtered_df['net_amount'].sum() / 10000000 if 'net_amount' in filtered_df.columns else 0
        
        # Create footer cells based on actual column order
        footer_cells = []
        for col in table_df.columns:
            if col == 'Batch Name':
                footer_cells.append(html.Td('TOTAL', style={'padding': '12px', 'fontWeight': 'bold', 'backgroundColor': '#E3F2FD', 'borderTop': '2px solid #1976D2'}))
            elif col == 'Total Enrollments':
                footer_cells.append(html.Td(f"{total_enrollments:,}", style={'padding': '12px', 'fontWeight': 'bold', 'backgroundColor': '#E3F2FD', 'borderTop': '2px solid #1976D2'}))
            elif col == 'Total Revenue (₹ Cr)':
                footer_cells.append(html.Td(f"₹{total_revenue_sum:.2f} Cr", style={'padding': '12px', 'fontWeight': 'bold', 'backgroundColor': '#E3F2FD', 'borderTop': '2px solid #1976D2'}))
            else:
                footer_cells.append(html.Td('', style={'padding': '12px', 'backgroundColor': '#E3F2FD', 'borderTop': '2px solid #1976D2'}))
        
        table = html.Table([
            html.Thead(html.Tr([html.Th(col, style={'padding': '12px', 'backgroundColor': '#1976D2', 
                                                      'color': 'white', 'fontWeight': 'bold', 'textAlign': 'left'}) 
                                for col in table_df.columns])),
            html.Tbody([
                html.Tr([
                    html.Td(str(table_df.iloc[i][col]), style={'padding': '10px', 'borderBottom': '1px solid #ddd', 'textAlign': 'left'}) 
                    for col in table_df.columns
                ], style={'backgroundColor': '#f9f9f9' if i % 2 == 0 else 'white'}) 
                for i in range(len(table_df))
            ]),
            # Add Total row at the bottom with dynamic positioning
            html.Tfoot(html.Tr(footer_cells))
        ], style={'width': '100%', 'borderCollapse': 'collapse'})
        
        data_table = html.Div([
            table,
            html.P(f"Showing {len(table_df)} batches with total of {len(filtered_df):,} enrollments", 
                   style={'marginTop': '10px', 'color': '#666', 'fontSize': '12px'})
        ])
    else:
        data_table = html.P("No data available")
    
    return summary_cards, fig1, fig2, fig2_5, fig3, fig4, data_table, filtered_df.to_json(date_format='iso', orient='split')

# Export callbacks
@callback(
    Output('download-overall', 'data'),
    Input('export-overall-btn', 'n_clicks'),
    State('filtered-data-store', 'children'),
    prevent_initial_call=True
)
def export_overall(n_clicks, filtered_data_json):
    if n_clicks > 0 and filtered_data_json:
        filtered_df = pd.read_json(filtered_data_json, orient='split')
        if 'name' in filtered_df.columns:
            export_df = filtered_df['name'].value_counts().reset_index()
            export_df.columns = ['Batch Name', 'Enrollment Count']
            return dcc.send_data_frame(export_df.to_excel, 
                                      f"Overall_Enrollment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", 
                                      index=False, sheet_name='Overall Enrollment')
    return None

@callback(
    Output('download-last7', 'data'),
    Input('export-last7-btn', 'n_clicks'),
    State('filtered-data-store', 'children'),
    State('date-filter', 'end_date'),
    prevent_initial_call=True
)
def export_last7(n_clicks, filtered_data_json, end_date):
    if n_clicks > 0 and filtered_data_json:
        filtered_df = pd.read_json(filtered_data_json, orient='split')
        
        # Ensure converteddate is datetime
        if 'converteddate' in filtered_df.columns:
            filtered_df['converteddate'] = pd.to_datetime(filtered_df['converteddate'])
        
        last_7_days_df = filtered_df[filtered_df['converteddate'] >= (pd.Timestamp(end_date) - pd.Timedelta(days=7))] if 'converteddate' in filtered_df.columns else filtered_df
        
        if 'converteddate' in last_7_days_df.columns and len(last_7_days_df) > 0:
            # Group by date only (overall)
            export_df = last_7_days_df.groupby('converteddate').size().reset_index(name='Total Enrollments')
            export_df['converteddate'] = export_df['converteddate'].dt.strftime('%Y-%m-%d')
            export_df.columns = ['Date', 'Total Enrollments']
            return dcc.send_data_frame(export_df.to_excel, 
                                      f"Last_7_Days_Enrollment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", 
                                      index=False, sheet_name='Last 7 Days')
    return None

@callback(
    Output('download-revenue-trend', 'data'),
    Input('export-revenue-trend-btn', 'n_clicks'),
    State('filtered-data-store', 'children'),
    State('date-filter', 'end_date'),
    prevent_initial_call=True
)
def export_revenue_trend(n_clicks, filtered_data_json, end_date):
    if n_clicks > 0 and filtered_data_json:
        filtered_df = pd.read_json(filtered_data_json, orient='split')
        
        # Ensure converteddate is datetime
        if 'converteddate' in filtered_df.columns:
            filtered_df['converteddate'] = pd.to_datetime(filtered_df['converteddate'])
        
        last_7_days_df = filtered_df[filtered_df['converteddate'] >= (pd.Timestamp(end_date) - pd.Timedelta(days=7))] if 'converteddate' in filtered_df.columns else filtered_df
        
        if 'converteddate' in last_7_days_df.columns and 'net_amount' in last_7_days_df.columns and len(last_7_days_df) > 0:
            export_df = last_7_days_df.groupby('converteddate')['net_amount'].sum().reset_index()
            export_df['net_amount'] = export_df['net_amount'] / 10000000  # Convert to Crores
            export_df['converteddate'] = export_df['converteddate'].dt.strftime('%Y-%m-%d')
            export_df.columns = ['Date', 'Revenue (₹ Cr)']
            return dcc.send_data_frame(export_df.to_excel, 
                                      f"Revenue_Trend_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", 
                                      index=False, sheet_name='Revenue Trend')
    return None

@callback(
    Output('download-exam-dist', 'data'),
    Input('export-exam-dist-btn', 'n_clicks'),
    State('filtered-data-store', 'children'),
    prevent_initial_call=True
)
def export_exam_dist(n_clicks, filtered_data_json):
    if n_clicks > 0 and filtered_data_json:
        filtered_df = pd.read_json(filtered_data_json, orient='split')
        if 'Exam_2' in filtered_df.columns:
            export_df = filtered_df['Exam_2'].value_counts().reset_index()
            export_df.columns = ['Exam Category', 'Enrollment Count']
            return dcc.send_data_frame(export_df.to_excel, 
                                      f"Exam_Distribution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", 
                                      index=False, sheet_name='Exam Distribution')
    return None

@callback(
    Output('download-revenue-exam', 'data'),
    Input('export-revenue-exam-btn', 'n_clicks'),
    State('filtered-data-store', 'children'),
    prevent_initial_call=True
)
def export_revenue_exam(n_clicks, filtered_data_json):
    if n_clicks > 0 and filtered_data_json:
        filtered_df = pd.read_json(filtered_data_json, orient='split')
        if 'Exam_2' in filtered_df.columns and 'net_amount' in filtered_df.columns and len(filtered_df) > 0:
            export_df = filtered_df.groupby('Exam_2')['net_amount'].sum().reset_index()
            export_df['net_amount'] = export_df['net_amount'] / 10000000  # Convert to Crores
            export_df.columns = ['Exam Category', 'Revenue (₹ Cr)']
            export_df = export_df.sort_values('Revenue (₹ Cr)', ascending=False)
            return dcc.send_data_frame(export_df.to_excel, 
                                      f"Revenue_by_Exam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", 
                                      index=False, sheet_name='Revenue by Exam')
    return None

@callback(
    Output('download-table', 'data'),
    Input('export-table-btn', 'n_clicks'),
    State('filtered-data-store', 'children'),
    prevent_initial_call=True
)
def export_table(n_clicks, filtered_data_json):
    if n_clicks > 0 and filtered_data_json:
        filtered_df = pd.read_json(filtered_data_json, orient='split')
        
        if 'name' in filtered_df.columns:
            # Aggregate data by batch
            agg_dict = {}
            
            if 'Exam_2' in filtered_df.columns:
                agg_dict['Exam_2'] = 'first'
            
            if 'net_amount' in filtered_df.columns:
                agg_dict['net_amount'] = 'sum'
            
            if 'leader_fin' in filtered_df.columns:
                agg_dict['leader_fin'] = 'first'
            
            # Group by batch name
            export_df = filtered_df.groupby('name').agg(agg_dict).reset_index()
            
            # Add enrollment count
            enrollment_counts = filtered_df.groupby('name').size().reset_index(name='Total Enrollments')
            export_df = export_df.merge(enrollment_counts, on='name', how='left')
            
            # Add order type counts
            if 'order_type' in filtered_df.columns:
                order_primary = filtered_df[filtered_df['order_type'] == 'PRIMARY'].groupby('name').size().reset_index(name='Primary Orders')
                order_upgrade = filtered_df[filtered_df['order_type'] == 'UPGRADE'].groupby('name').size().reset_index(name='Upgrade Orders')
                export_df = export_df.merge(order_primary, on='name', how='left')
                export_df = export_df.merge(order_upgrade, on='name', how='left')
                export_df['Primary Orders'] = export_df['Primary Orders'].fillna(0).astype(int)
                export_df['Upgrade Orders'] = export_df['Upgrade Orders'].fillna(0).astype(int)
            
            # Rename columns
            export_df = export_df.rename(columns={
                'name': 'Batch Name',
                'Exam_2': 'Exam Category',
                'net_amount': 'Total Revenue (₹ Cr)',
                'leader_fin': 'Leader'
            })
            
            # Convert revenue to Crores
            if 'Total Revenue (₹ Cr)' in export_df.columns:
                export_df['Total Revenue (₹ Cr)'] = export_df['Total Revenue (₹ Cr)'] / 10000000
            
            # Reorder columns
            cols_order = ['Batch Name', 'Total Enrollments', 'Exam Category', 'Total Revenue (₹ Cr)', 
                         'Primary Orders', 'Upgrade Orders', 'Leader']
            final_cols = [col for col in cols_order if col in export_df.columns]
            export_df = export_df[final_cols]
            
            # Sort by Total Enrollments
            export_df = export_df.sort_values('Total Enrollments', ascending=False)
            
            # Add total row at the bottom
            total_row = {}
            for col in export_df.columns:
                if col == 'Batch Name':
                    total_row[col] = 'TOTAL'
                elif col == 'Total Enrollments':
                    total_row[col] = export_df['Total Enrollments'].sum()
                elif col == 'Total Revenue (₹ Cr)':
                    total_row[col] = export_df['Total Revenue (₹ Cr)'].sum()
                elif col == 'Primary Orders':
                    total_row[col] = export_df['Primary Orders'].sum() if 'Primary Orders' in export_df.columns else ''
                elif col == 'Upgrade Orders':
                    total_row[col] = export_df['Upgrade Orders'].sum() if 'Upgrade Orders' in export_df.columns else ''
                else:
                    total_row[col] = ''
            
            # Append total row to dataframe
            export_df = pd.concat([export_df, pd.DataFrame([total_row])], ignore_index=True)
            
            return dcc.send_data_frame(export_df.to_excel, 
                                      f"Batch_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", 
                                      index=False, sheet_name='Batch Summary')
        else:
            return dcc.send_data_frame(filtered_df.to_excel, 
                                      f"Full_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx", 
                                      index=False, sheet_name='Data')
    return None

# Screenshot callback using clientside callback
app.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks > 0) {
            const element = document.getElementById('table-container');
            if (element) {
                // Use html2canvas library to capture screenshot
                if (typeof html2canvas !== 'undefined') {
                    html2canvas(element, {
                        backgroundColor: '#ffffff',
                        scale: 2,
                        logging: false
                    }).then(canvas => {
                        // Convert canvas to blob and download
                        canvas.toBlob(function(blob) {
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            const timestamp = new Date().toISOString().slice(0,19).replace(/:/g,'-');
                            a.download = 'Table_Screenshot_' + timestamp + '.png';
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            window.URL.revokeObjectURL(url);
                        });
                    });
                } else {
                    alert('Screenshot feature requires html2canvas library. Please install it to use this feature.');
                }
            }
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output('screenshot-table-btn', 'n_clicks'),
    Input('screenshot-table-btn', 'n_clicks'),
    prevent_initial_call=True
)

# ========================================================================================================
# RUN APP
# ========================================================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)
