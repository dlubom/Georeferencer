# Backend Deployment Guide

Complete step-by-step instructions for deploying the Cave Georeferencer crowdsourcing backend.

## Prerequisites

- Google account with access to Google Sheets and Apps Script
- Code.gs and ImportCaves.gs files (already created in this project)

---

## Step 1: Create Google Sheet

1. Go to [Google Sheets](https://sheets.google.com)
2. Click **"Blank"** to create a new spreadsheet
3. Rename it to: **"Cave Georeferencer - Crowdsourcing Database"**
4. Note the Spreadsheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit
   ```
   Example: `1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t`

---

## Step 2: Open Apps Script Editor

1. In the Google Sheet, click **Extensions → Apps Script**
2. This opens the Apps Script editor in a new tab
3. You should see a default `Code.gs` file with a placeholder function

---

## Step 3: Add Script Files

### Create Code.gs

1. Delete the default code in `Code.gs`
2. Copy the entire contents of your local `Code.gs` file
3. Paste into the Apps Script editor
4. Click the **Save** icon (💾) or press `Ctrl+S` (Cmd+S on Mac)

### Create ImportCaves.gs

1. Click the **+** icon next to "Files" in the left sidebar
2. Select **"Script"**
3. Name it: `ImportCaves`
4. Copy the entire contents of your local `ImportCaves.gs` file
5. Paste into the new script file
6. Click **Save**

Your project should now have two files:
- `Code.gs` (main backend)
- `ImportCaves.gs` (data import helper)

---

## Step 4: Run Setup Functions

### 4.1 Initialize Sheet Structure

1. In the Apps Script editor, select `Code.gs` from the file list
2. In the function dropdown (top toolbar), select **`setupSheets`**
3. Click **Run** (▶️ button)
4. **First-time authorization:**
   - A dialog will appear: "Authorization required"
   - Click **"Review permissions"**
   - Select your Google account
   - Click **"Advanced"** (if warning appears)
   - Click **"Go to Cave Georeferencer (unsafe)"** (this is your own script, it's safe)
   - Click **"Allow"**
5. Wait for execution to complete (check the "Execution log" at the bottom)
6. You should see: `✅ Sheet structure created successfully`

**Verify:** Go back to your Google Sheet. You should now see 4 tabs:
- `CAVES` (blue header)
- `USERS` (green header)
- `ASSIGNMENTS` (yellow header)
- `SUBMISSIONS` (red header)

### 4.2 Import Tatry Caves Data

1. Select `ImportCaves.gs` from the file list
2. In the function dropdown, select **`importTatryCavesFromURL`**
3. Click **Run** (▶️ button)
4. Wait for execution (this may take 10-30 seconds as it fetches data from GitHub)
5. Check the execution log for:
   ```
   Fetching data from GitHub...
   Data fetched, processing...
   ✅ SUCCESS!
   Imported X Tatry caves
   Skipped Y non-Tatry or invalid caves
   ```

**Verify:** Go to the `CAVES` tab in your Google Sheet. You should see rows of Tatry caves with columns:
- cave_id
- name
- region
- lat
- lon
- n_submissions (all zeros initially)
- n_open_assignments (all zeros initially)
- last_assigned_at (empty initially)
- disabled (all FALSE)
- disabled_reason (empty)

**Expected result:** Approximately 50-100 Tatry caves imported (exact number depends on the data source).

### 4.3 Optional: Verify Import Stats

1. In `ImportCaves.gs`, select **`showCaveStats`** from the dropdown
2. Click **Run**
3. Check the execution log for a summary:
   ```
   === CAVE DATABASE STATS ===
   Total caves: X

   By region:
     Tatry: X
     Tatrzański Park Narodowy: X
     ...

   By submission count:
     0 submissions: X caves
     1-2 submissions: 0 caves
     3-4 submissions: 0 caves
     5+ submissions: 0 caves
   ```

---

## Step 5: Deploy as Web App

### 5.1 Create Deployment

1. In the Apps Script editor, click **Deploy → New deployment**
2. Click the **gear icon** (⚙️) next to "Select type"
3. Select **"Web app"**
4. Fill in the settings:
   - **Description:** `Cave Georeferencer API v1`
   - **Execute as:** `Me (your-email@gmail.com)`
   - **Who has access:** `Anyone` ⚠️ **Important!** Select "Anyone" to allow unauthenticated access
5. Click **Deploy**
6. **Authorization (if prompted):**
   - Click **"Authorize access"**
   - Select your Google account
   - Click **"Advanced"** → **"Go to Cave Georeferencer (unsafe)"**
   - Click **"Allow"**

### 5.2 Copy Deployment URL

After deployment, you'll see a dialog with the **Web app URL**:

```
https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID_HERE/exec
```

**IMPORTANT:** Copy this entire URL! You'll need it in the next step.

Example:
```
https://script.google.com/macros/s/AKfycbxAbC123dEf456GhI789JkL012MnO345PqR678StU901VwX/exec
```

Click **Done**.

---

## Step 6: Update Frontend with API URL

### 6.1 Update index.html

1. Open `index.html` in your code editor
2. Find this line (around line 803):
   ```javascript
   API_ENDPOINT: 'https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec',
   ```
3. Replace `YOUR_DEPLOYMENT_ID` with your actual deployment URL from Step 5.2:
   ```javascript
   API_ENDPOINT: 'https://script.google.com/macros/s/AKfycbxAbC123dEf456GhI789JkL012MnO345PqR678StU901VwX/exec',
   ```
4. Save the file

### 6.2 Open index.html in Browser

1. Open `index.html` in a web browser (double-click the file, or use a local server)
2. Open the browser console (F12 → Console tab)
3. Check for any errors

### 6.3 Verify Connection

In the browser console, you should see:
```
Generated new user ID: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
```

If you see network errors like:
```
❌ API call failed: HTTP 404
```

Then the API_ENDPOINT URL is incorrect. Double-check Step 6.1.

---

## Step 7: Test the API

### 7.1 Test in Apps Script Console

Before testing in the browser, verify the API works directly:

1. In Apps Script editor, select `Code.gs`
2. In the function dropdown, select **`testApi`**
3. Click **Run**
4. Check the execution log for:
   ```
   Ping result: {"ok":true}
   Progress result: {"ok":true,"total":X,"target_k":5,"ge_1":0,"ge_2":0,...}
   ```

If you see errors, check the execution log for details.

### 7.2 Test in Browser Console

1. Open `index.html` in browser
2. Open browser console (F12)
3. Wait for the page to load (caves data should load)
4. Run this command in the console:
   ```javascript
   refreshProgress()
   ```
5. You should see:
   - The progress bar update at the top of the sidebar
   - Console log: `Progress result: {...}`
   - No error messages

### 7.3 Test Assignment Flow

1. Click the **"🎲 Daj mi jaskinię"** button
2. You should see:
   - Button changes to "⏳ Przydzielanie..."
   - After 1-2 seconds, a toast notification: "Przydzielono: [Cave Name]"
   - The cave is auto-selected
   - Image list is populated
   - Assignment info panel appears

**Verify in Google Sheet (ASSIGNMENTS tab):**
- A new row should appear with:
  - assignment_id (e.g., `A_1234567890_1234`)
  - your user_id (UUID)
  - cave_id
  - assigned_at (timestamp)
  - expires_at (timestamp +24h)
  - status: `ASSIGNED`

**Verify in Google Sheet (CAVES tab):**
- The assigned cave's `n_open_assignments` should be `1`
- The `last_assigned_at` should have a timestamp

### 7.4 Test Full Workflow

1. **Assign:** Click "Daj mi jaskinię"
2. **Load:** Click "Załaduj Plan z GitHub"
3. **Georeference:** Click the 3-5 points on the plan
4. **Submit:** Click "📤 Wyślij do Google Sheets"
5. **Confirm:** In the modal, click "✅ Wyślij"

**Expected result:**
- Toast notification: "✅ Wysłano pomyślnie!"
- Assignment panel clears
- Canvas clears
- Progress bar updates

**Verify in Google Sheet (SUBMISSIONS tab):**
- A new row with ~48 columns of data
- submission_id, cave_id, user_id, World File parameters (A-F), etc.

**Verify in Google Sheet (ASSIGNMENTS tab):**
- The assignment status changed from `ASSIGNED` to `SUBMITTED`

**Verify in Google Sheet (CAVES tab):**
- The cave's `n_submissions` incremented to `1`
- The cave's `n_open_assignments` decremented to `0`

---

## Step 8: Test Error Handling

### 8.1 Test Assignment Expiry

1. In Google Sheet, go to **ASSIGNMENTS** tab
2. Manually edit the `expires_at` column to a date in the past (e.g., `2024-01-01T00:00:00Z`)
3. Refresh `index.html` in browser
4. Expected: Toast notification "Przydzielenie wygasło" or assignment is cleared

### 8.2 Test No Caves Available

1. In Google Sheet, go to **CAVES** tab
2. Temporarily set all caves' `n_submissions` to `5`
3. Refresh `index.html` in browser
4. Click "Daj mi jaskinię"
5. Expected: Toast notification "🎉 Wszystkie jaskinie ukończone! Dziękujemy!"
6. **Reset:** Set all `n_submissions` back to `0` using `resetAllCounters()` function in Apps Script

### 8.3 Test Network Failure Fallback

1. In `index.html`, temporarily change `API_ENDPOINT` to an invalid URL (e.g., add `INVALID` to the end)
2. Complete a georeferencing workflow
3. Click "Wyślij do Google Sheets"
4. Expected: Error dialog asking "Czy chcesz pobrać dane jako JSON?"
5. Click "OK" → A JSON file should download
6. **Reset:** Change `API_ENDPOINT` back to the correct URL

---

## Step 9: Deploy Frontend

### Option A: GitHub Pages (Recommended)

1. Create a GitHub repository for the project (if not already created)
2. Push all files to the repository:
   ```bash
   git init
   git add index.html debug.html Code.gs ImportCaves.gs GEOREFERENCER.md PRD.md DEPLOYMENT.md
   git commit -m "Initial commit - Cave Georeferencer Crowdsourcing"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/Georeferencer.git
   git push -u origin main
   ```
3. Enable GitHub Pages:
   - Go to repository Settings → Pages
   - Source: **Deploy from a branch**
   - Branch: **main** / **root**
   - Click **Save**
4. Wait 1-2 minutes for deployment
5. Access your app at:
   ```
   https://YOUR_USERNAME.github.io/Georeferencer/index.html
   ```

### Option B: Local Testing

1. Start a local HTTP server in the project directory:
   ```bash
   # Python 3
   python -m http.server 8000

   # Python 2
   python -m SimpleHTTPServer 8000

   # Node.js (install: npm install -g http-server)
   http-server -p 8000
   ```
2. Open browser to: `http://localhost:8000/index.html`

**Why use a server?** Opening `index.html` directly (`file://`) may cause CORS issues when fetching from GitHub or calling the API.

---

## Step 10: Monitor Usage

### View Execution Logs

1. In Apps Script editor, click **Executions** (left sidebar, clock icon)
2. View all API calls, errors, and execution times
3. Click any execution to see detailed logs

### View Live Data

1. Open the Google Sheet
2. Keep it open in a tab while users submit
3. Watch new rows appear in real-time:
   - **USERS:** New users
   - **ASSIGNMENTS:** New assignments and status changes
   - **SUBMISSIONS:** New submissions
   - **CAVES:** Counter updates

### Export Data for Analysis

1. In Google Sheet, select the **SUBMISSIONS** tab
2. Click **File → Download → Comma Separated Values (.csv)**
3. Analyze in Python, R, Excel, etc.

---

## Troubleshooting

### Issue: "Authorization required" on every API call

**Cause:** Deployment setting is "Execute as: User accessing the web app" instead of "Me"

**Fix:**
1. Deploy → Manage deployments
2. Click the pencil icon to edit
3. Change "Execute as" to **"Me"**
4. Click **Deploy**

### Issue: API returns 404 Not Found

**Cause:** Incorrect API_ENDPOINT URL

**Fix:**
1. In Apps Script, click **Deploy → Manage deployments**
2. Copy the **Web app URL** from the active deployment
3. Update `API_ENDPOINT` in `index.html`

### Issue: API returns 403 Forbidden

**Cause:** Deployment "Who has access" is not set to "Anyone"

**Fix:**
1. Deploy → Manage deployments
2. Edit deployment
3. Change "Who has access" to **"Anyone"**
4. Deploy

### Issue: CORS errors in browser console

**Cause:** Opening `index.html` directly as `file://` or local server issue

**Fix:**
1. Use a local HTTP server (see Step 9, Option B)
2. Or deploy to GitHub Pages

### Issue: Assignment returns "no_caves_available" immediately

**Cause:** No caves in CAVES sheet, or all have n_submissions >= 5

**Fix:**
1. Run `importTatryCavesFromURL()` to import caves
2. Or run `resetAllCounters()` to reset submission counts

### Issue: Submission fails with "assignment_not_found"

**Cause:** Assignment expired or was cleared

**Fix:**
1. Get a new assignment by clicking "Daj mi jaskinię"
2. Check `expires_at` in ASSIGNMENTS sheet (should be +24h from now)

### Issue: Progress bar shows 0% even after submissions

**Cause:** Cache issue or API not updating

**Fix:**
1. Click the 🔄 icon next to "Postęp Globalny"
2. Or refresh the page
3. Check CAVES sheet to verify `n_submissions` values are updating

---

## Production Checklist

Before announcing to contributors:

- [ ] Backend deployed and tested
- [ ] Frontend deployed to GitHub Pages (or similar)
- [ ] Test full workflow (assign → load → georeference → submit → next)
- [ ] Test skip workflow
- [ ] Test progress display updates
- [ ] Test with multiple users in different browsers (incognito mode for separate user IDs)
- [ ] Verify no cave is assigned twice to same user
- [ ] Verify assignment expiry (24h) works
- [ ] Verify counters update correctly (n_submissions, n_open_assignments)
- [ ] Document API_ENDPOINT in PRD.md
- [ ] Update GEOREFERENCER.md with contributor instructions
- [ ] Prepare a brief tutorial video or screenshots

---

## Next Steps

1. ✅ Complete deployment following this guide
2. Update `PRD.md` with the deployment URL
3. Update `GEOREFERENCER.md` with contributor guide
4. Test with 2-3 people before announcing widely
5. Monitor the first 10-20 submissions for issues
6. Fix any bugs discovered during testing
7. Announce to 50 contributors

---

## Support

If you encounter issues not covered in this guide:

1. Check the Apps Script execution log for detailed error messages
2. Check the browser console (F12) for frontend errors
3. Verify all URLs are correct (API_ENDPOINT, GitHub raw URLs)
4. Test with `testApi()` function in Apps Script
5. Test with `curl` or Postman:
   ```bash
   curl -X POST \
     -H "Content-Type: application/json" \
     -d '{"action":"ping","user_id":"test-123"}' \
     YOUR_API_ENDPOINT_HERE
   ```

Expected response:
```json
{"ok":true}
```

---

## File Checklist

Ensure you have all required files:

- ✅ `index.html` (production frontend with crowdsourcing)
- ✅ `debug.html` (debug frontend with manual selection)
- ✅ `Code.gs` (backend API)
- ✅ `ImportCaves.gs` (data import helper)
- ✅ `GEOREFERENCER.md` (documentation)
- ✅ `PRD.md` (requirements)
- ✅ `DEPLOYMENT.md` (this file)

Good luck with the deployment! 🚀
