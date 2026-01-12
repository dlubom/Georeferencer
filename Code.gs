// ===========================================
// Cave Georeferencer - Google Apps Script Backend
// ===========================================
// This script handles the crowdsourcing API for collecting
// k=5 independent georeferencing results per cave from Tatry region.

// Configuration
const CONFIG = {
  SPREADSHEET_ID: null, // Will use active spreadsheet
  TARGET_K: 5,
  ASSIGNMENT_EXPIRY_HOURS: 24,
  SHEET_NAMES: {
    CAVES: 'CAVES',
    USERS: 'USERS',
    ASSIGNMENTS: 'ASSIGNMENTS',
    SUBMISSIONS: 'SUBMISSIONS'
  }
};

// ===========================================
// MAIN ENTRY POINT
// ===========================================

/**
 * Main POST handler for all API requests
 * Handles actions: ping, assign, submit, skip, progress
 */
function doPost(e) {
  const lock = LockService.getScriptLock();

  try {
    // Try to acquire lock (30 second timeout)
    const hasLock = lock.tryLock(30000);

    if (!hasLock) {
      return jsonResponse({
        ok: false,
        error: 'service_busy',
        message: 'Serwis jest zajęty, spróbuj ponownie za chwilę'
      });
    }

    // Parse request
    const data = JSON.parse(e.postData.contents);
    const action = data.action;

    Logger.log('API Request: ' + action);

    // Route to appropriate handler
    switch(action) {
      case 'ping':
        return jsonResponse(handlePing(data));
      case 'assign':
        return jsonResponse(handleAssign(data));
      case 'submit':
        return jsonResponse(handleSubmit(data));
      case 'skip':
        return jsonResponse(handleSkip(data));
      case 'progress':
        return jsonResponse(handleProgress(data));
      default:
        return jsonResponse({
          ok: false,
          error: 'unknown_action',
          message: 'Nieznana akcja: ' + action
        });
    }

  } catch (error) {
    Logger.log('ERROR: ' + error.toString());
    return jsonResponse({
      ok: false,
      error: 'server_error',
      message: error.toString()
    });

  } finally {
    lock.releaseLock();
  }
}

/**
 * Helper to return JSON response
 */
function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// ===========================================
// ACTION HANDLERS
// ===========================================

/**
 * PING - Update user last_seen_at
 */
function handlePing(data) {
  try {
    const userId = data.user_id;
    const displayName = data.display_name || null;

    if (!userId) {
      return { ok: false, error: 'missing_user_id', message: 'Brak user_id' };
    }

    // Update or create user
    const usersSheet = getSheet(CONFIG.SHEET_NAMES.USERS);
    const userRow = findUserRow(userId);

    const now = new Date().toISOString();

    if (userRow === null) {
      // Create new user
      usersSheet.appendRow([
        userId,
        now, // created_at
        now, // last_seen_at
        displayName,
        '' // notes
      ]);
    } else {
      // Update last_seen_at
      usersSheet.getRange(userRow, 3).setValue(now);
      if (displayName) {
        usersSheet.getRange(userRow, 4).setValue(displayName);
      }
    }

    return { ok: true };

  } catch (error) {
    return { ok: false, error: 'ping_failed', message: error.toString() };
  }
}

/**
 * ASSIGN - Get cave assignment for user
 */
function handleAssign(data) {
  try {
    const userId = data.user_id;

    if (!userId) {
      return { ok: false, error: 'missing_user_id', message: 'Brak user_id' };
    }

    // Get caves already assigned or submitted by this user
    const userCaveIds = getCavesByUser(userId);

    // Get eligible caves (n_submissions < 5, not in userCaveIds, not disabled)
    const eligibleCaves = getEligibleCaves(userCaveIds);

    if (eligibleCaves.length === 0) {
      return {
        ok: false,
        error: 'no_caves_available',
        message: 'Wszystkie jaskinie ukończone lub przydzielone'
      };
    }

    // Select random cave from those with minimum n_submissions
    const selectedCave = selectRandomCave(eligibleCaves);

    // Create assignment
    const assignmentId = generateId('A');
    const expiresAt = new Date();
    expiresAt.setHours(expiresAt.getHours() + CONFIG.ASSIGNMENT_EXPIRY_HOURS);

    const assignmentsSheet = getSheet(CONFIG.SHEET_NAMES.ASSIGNMENTS);
    assignmentsSheet.appendRow([
      assignmentId,
      userId,
      selectedCave.cave_id,
      new Date().toISOString(), // assigned_at
      expiresAt.toISOString(),   // expires_at
      'ASSIGNED',                 // status
      getAttemptNumber(userId),   // attempt_no
      '',                         // selected_image_id (filled on submit)
      ''                          // selected_image_path (filled on submit)
    ]);

    // Increment n_open_assignments for this cave
    updateCounters(selectedCave.cave_id, { n_open_assignments: 1 });

    // Update last_assigned_at
    const cavesSheet = getSheet(CONFIG.SHEET_NAMES.CAVES);
    const caveRow = selectedCave.rowIndex;
    cavesSheet.getRange(caveRow, 7).setValue(new Date().toISOString());

    return {
      ok: true,
      assignment_id: assignmentId,
      cave_id: selectedCave.cave_id,
      target_k: CONFIG.TARGET_K,
      n_submissions: selectedCave.n_submissions,
      expires_at: expiresAt.toISOString()
    };

  } catch (error) {
    return { ok: false, error: 'assign_failed', message: error.toString() };
  }
}

/**
 * SUBMIT - Submit georeferencing result
 */
function handleSubmit(data) {
  try {
    // Validate required fields
    if (!data.assignment_id || !data.user_id || !data.cave_id) {
      return {
        ok: false,
        error: 'missing_fields',
        message: 'Brak wymaganych pól: assignment_id, user_id, cave_id'
      };
    }

    // Verify assignment exists and is not expired
    const assignmentsSheet = getSheet(CONFIG.SHEET_NAMES.ASSIGNMENTS);
    const assignmentRow = findAssignmentRow(data.assignment_id);

    if (!assignmentRow) {
      return {
        ok: false,
        error: 'assignment_not_found',
        message: 'Przydzielenie nie zostało znalezione'
      };
    }

    const assignmentData = assignmentsSheet.getRange(assignmentRow, 1, 1, 9).getValues()[0];
    const status = assignmentData[5];
    const expiresAt = new Date(assignmentData[4]);

    if (status !== 'ASSIGNED') {
      return {
        ok: false,
        error: 'assignment_already_used',
        message: 'Przydzielenie już zostało użyte'
      };
    }

    if (expiresAt < new Date()) {
      return {
        ok: false,
        error: 'assignment_expired',
        message: 'Przydzielenie wygasło'
      };
    }

    // Generate submission ID
    const submissionId = generateId('SUB');

    // Insert into SUBMISSIONS sheet (all fields from PRD)
    const submissionsSheet = getSheet(CONFIG.SHEET_NAMES.SUBMISSIONS);

    submissionsSheet.appendRow([
      // Identification
      submissionId,
      data.submitted_at || new Date().toISOString(),
      data.assignment_id,
      data.user_id,
      data.cave_id,

      // Selected plan
      data.image_id || '',
      data.image_path_original || '',
      data.image_path_upscaled || '',
      data.image_used_path || '',
      data.image_selected_index || 0,
      data.use_original || false,
      data.image_description || '',
      data.image_author || '',

      // Input configuration
      data.lat_input || 0,
      data.lon_input || 0,
      data.lat_db || 0,
      data.lon_db || 0,
      data.realScale_m || 0,
      data.declination_deg || 0,
      data.skipNorth || true,
      data.proj4def || '',

      // Points geometry
      data.points_canvas_json || '',
      data.points_orig_json || '',

      // World File results
      data.A || 0,
      data.D || 0,
      data.B || 0,
      data.E || 0,
      data.C || 0,
      data.F || 0,
      data.worldfile_ext || '',
      data.worldfile_text || '',
      data.gdal_cmd_standard || '',

      // Calculated metrics
      data.pixels_per_meter || 0,
      data.north_deg || 0,
      data.convergence_deg || 0,
      data.total_deg || 0,

      // Telemetry
      data.app_version || '',
      data.client_time_iso || '',
      data.tz || '',
      data.user_agent || '',
      data.screen_w || 0,
      data.screen_h || 0,

      // Status
      data.submit_type || 'NORMAL',
      data.skip_reason || '',
      data.freeform_comment || '',
      data.errors_json || ''
    ]);

    // Update ASSIGNMENTS status
    assignmentsSheet.getRange(assignmentRow, 6).setValue('SUBMITTED');
    assignmentsSheet.getRange(assignmentRow, 8).setValue(data.image_id || '');
    assignmentsSheet.getRange(assignmentRow, 9).setValue(data.image_used_path || '');

    // Update CAVES counters
    updateCounters(data.cave_id, {
      n_submissions: 1,
      n_open_assignments: -1
    });

    return {
      ok: true,
      submission_id: submissionId
    };

  } catch (error) {
    return { ok: false, error: 'submit_failed', message: error.toString() };
  }
}

/**
 * SKIP - Skip cave assignment
 */
function handleSkip(data) {
  try {
    if (!data.assignment_id || !data.user_id || !data.cave_id) {
      return {
        ok: false,
        error: 'missing_fields',
        message: 'Brak wymaganych pól'
      };
    }

    // Find assignment
    const assignmentsSheet = getSheet(CONFIG.SHEET_NAMES.ASSIGNMENTS);
    const assignmentRow = findAssignmentRow(data.assignment_id);

    if (!assignmentRow) {
      return {
        ok: false,
        error: 'assignment_not_found',
        message: 'Przydzielenie nie zostało znalezione'
      };
    }

    // Update assignment status to SKIPPED
    assignmentsSheet.getRange(assignmentRow, 6).setValue('SKIPPED');

    // Decrement n_open_assignments (don't increment n_submissions for skips)
    updateCounters(data.cave_id, {
      n_open_assignments: -1
    });

    return { ok: true };

  } catch (error) {
    return { ok: false, error: 'skip_failed', message: error.toString() };
  }
}

/**
 * PROGRESS - Get global progress statistics
 */
function handleProgress(data) {
  try {
    const cavesSheet = getSheet(CONFIG.SHEET_NAMES.CAVES);
    const cavesData = cavesSheet.getDataRange().getValues();

    // Skip header row
    const caves = cavesData.slice(1);

    const total = caves.length;
    let ge_1 = 0, ge_2 = 0, ge_3 = 0, ge_4 = 0, ge_5 = 0;

    caves.forEach(row => {
      const n_submissions = row[5] || 0; // Column 6 (index 5)

      if (n_submissions >= 1) ge_1++;
      if (n_submissions >= 2) ge_2++;
      if (n_submissions >= 3) ge_3++;
      if (n_submissions >= 4) ge_4++;
      if (n_submissions >= 5) ge_5++;
    });

    const remaining_lt_5 = total - ge_5;

    return {
      ok: true,
      total: total,
      target_k: CONFIG.TARGET_K,
      ge_1: ge_1,
      ge_2: ge_2,
      ge_3: ge_3,
      ge_4: ge_4,
      ge_5: ge_5,
      remaining_lt_5: remaining_lt_5
    };

  } catch (error) {
    return { ok: false, error: 'progress_failed', message: error.toString() };
  }
}

// ===========================================
// HELPER FUNCTIONS
// ===========================================

/**
 * Get sheet by name
 */
function getSheet(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(name);

  if (!sheet) {
    throw new Error('Sheet not found: ' + name);
  }

  return sheet;
}

/**
 * Find user row by user_id
 * Returns row number or null
 */
function findUserRow(userId) {
  const usersSheet = getSheet(CONFIG.SHEET_NAMES.USERS);
  const data = usersSheet.getDataRange().getValues();

  for (let i = 1; i < data.length; i++) { // Skip header
    if (data[i][0] === userId) {
      return i + 1; // Return 1-indexed row number
    }
  }

  return null;
}

/**
 * Find assignment row by assignment_id
 */
function findAssignmentRow(assignmentId) {
  const assignmentsSheet = getSheet(CONFIG.SHEET_NAMES.ASSIGNMENTS);
  const data = assignmentsSheet.getDataRange().getValues();

  for (let i = 1; i < data.length; i++) { // Skip header
    if (data[i][0] === assignmentId) {
      return i + 1;
    }
  }

  return null;
}

/**
 * Get all cave_ids assigned or submitted by this user
 */
function getCavesByUser(userId) {
  const assignmentsSheet = getSheet(CONFIG.SHEET_NAMES.ASSIGNMENTS);
  const data = assignmentsSheet.getDataRange().getValues();

  const caveIds = [];

  for (let i = 1; i < data.length; i++) { // Skip header
    if (data[i][1] === userId) { // user_id column
      caveIds.push(data[i][2]); // cave_id column
    }
  }

  return caveIds;
}

/**
 * Get eligible caves for assignment
 * Returns array of {cave_id, n_submissions, rowIndex}
 */
function getEligibleCaves(excludeCaveIds) {
  const cavesSheet = getSheet(CONFIG.SHEET_NAMES.CAVES);
  const data = cavesSheet.getDataRange().getValues();

  const eligible = [];

  for (let i = 1; i < data.length; i++) { // Skip header
    const cave_id = data[i][0];
    const n_submissions = data[i][5] || 0;
    const disabled = data[i][7] || false;

    // Check eligibility
    if (disabled) continue;
    if (n_submissions >= CONFIG.TARGET_K) continue;
    if (excludeCaveIds.includes(cave_id)) continue;

    eligible.push({
      cave_id: cave_id,
      n_submissions: n_submissions,
      rowIndex: i + 1
    });
  }

  return eligible;
}

/**
 * Select random cave from those with minimum n_submissions
 */
function selectRandomCave(caves) {
  if (caves.length === 0) {
    throw new Error('No caves available');
  }

  // Find minimum n_submissions
  const minSubmissions = Math.min(...caves.map(c => c.n_submissions));

  // Filter caves with minimum n_submissions
  const minCaves = caves.filter(c => c.n_submissions === minSubmissions);

  // Select random from this pool
  const randomIndex = Math.floor(Math.random() * minCaves.length);

  return minCaves[randomIndex];
}

/**
 * Generate unique ID with prefix
 */
function generateId(prefix) {
  const timestamp = new Date().getTime();
  const random = Math.floor(Math.random() * 10000);
  return `${prefix}_${timestamp}_${random}`;
}

/**
 * Get attempt number for user (count of all assignments)
 */
function getAttemptNumber(userId) {
  const assignmentsSheet = getSheet(CONFIG.SHEET_NAMES.ASSIGNMENTS);
  const data = assignmentsSheet.getDataRange().getValues();

  let count = 0;
  for (let i = 1; i < data.length; i++) {
    if (data[i][1] === userId) {
      count++;
    }
  }

  return count + 1;
}

/**
 * Update cave counters
 * @param {string} caveId - Cave ID
 * @param {object} changes - Object with counter changes, e.g. {n_submissions: 1, n_open_assignments: -1}
 */
function updateCounters(caveId, changes) {
  const cavesSheet = getSheet(CONFIG.SHEET_NAMES.CAVES);
  const data = cavesSheet.getDataRange().getValues();

  for (let i = 1; i < data.length; i++) { // Skip header
    if (data[i][0] === caveId) {
      const rowIndex = i + 1;

      if (changes.n_submissions !== undefined) {
        const currentValue = data[i][5] || 0;
        cavesSheet.getRange(rowIndex, 6).setValue(currentValue + changes.n_submissions);
      }

      if (changes.n_open_assignments !== undefined) {
        const currentValue = data[i][6] || 0;
        cavesSheet.getRange(rowIndex, 7).setValue(Math.max(0, currentValue + changes.n_open_assignments));
      }

      break;
    }
  }
}

// ===========================================
// ADMIN / SETUP FUNCTIONS
// ===========================================

/**
 * Initialize spreadsheet with headers
 * Run this once to create the sheet structure
 */
function setupSheets() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // Create CAVES sheet
  let sheet = ss.getSheetByName(CONFIG.SHEET_NAMES.CAVES);
  if (!sheet) {
    sheet = ss.insertSheet(CONFIG.SHEET_NAMES.CAVES);
  }
  sheet.clear();
  sheet.appendRow([
    'cave_id',
    'name',
    'region',
    'lat',
    'lon',
    'n_submissions',
    'n_open_assignments',
    'last_assigned_at',
    'disabled',
    'disabled_reason'
  ]);
  sheet.getRange(1, 1, 1, 10).setFontWeight('bold').setBackground('#4285f4').setFontColor('white');

  // Create USERS sheet
  sheet = ss.getSheetByName(CONFIG.SHEET_NAMES.USERS);
  if (!sheet) {
    sheet = ss.insertSheet(CONFIG.SHEET_NAMES.USERS);
  }
  sheet.clear();
  sheet.appendRow([
    'user_id',
    'created_at',
    'last_seen_at',
    'display_name',
    'notes'
  ]);
  sheet.getRange(1, 1, 1, 5).setFontWeight('bold').setBackground('#34a853').setFontColor('white');

  // Create ASSIGNMENTS sheet
  sheet = ss.getSheetByName(CONFIG.SHEET_NAMES.ASSIGNMENTS);
  if (!sheet) {
    sheet = ss.insertSheet(CONFIG.SHEET_NAMES.ASSIGNMENTS);
  }
  sheet.clear();
  sheet.appendRow([
    'assignment_id',
    'user_id',
    'cave_id',
    'assigned_at',
    'expires_at',
    'status',
    'attempt_no',
    'selected_image_id',
    'selected_image_path'
  ]);
  sheet.getRange(1, 1, 1, 9).setFontWeight('bold').setBackground('#fbbc04').setFontColor('black');

  // Create SUBMISSIONS sheet
  sheet = ss.getSheetByName(CONFIG.SHEET_NAMES.SUBMISSIONS);
  if (!sheet) {
    sheet = ss.insertSheet(CONFIG.SHEET_NAMES.SUBMISSIONS);
  }
  sheet.clear();
  sheet.appendRow([
    // Identification
    'submission_id', 'submitted_at', 'assignment_id', 'user_id', 'cave_id',
    // Selected plan
    'image_id', 'image_path_original', 'image_path_upscaled', 'image_used_path',
    'image_selected_index', 'use_original', 'image_description', 'image_author',
    // Input configuration
    'lat_input', 'lon_input', 'lat_db', 'lon_db', 'realScale_m', 'declination_deg',
    'skipNorth', 'proj4def',
    // Points geometry
    'points_canvas_json', 'points_orig_json',
    // World File results
    'A', 'D', 'B', 'E', 'C', 'F', 'worldfile_ext', 'worldfile_text', 'gdal_cmd_standard',
    // Calculated metrics
    'pixels_per_meter', 'north_deg', 'convergence_deg', 'total_deg',
    // Telemetry
    'app_version', 'client_time_iso', 'tz', 'user_agent', 'screen_w', 'screen_h',
    // Status
    'submit_type', 'skip_reason', 'freeform_comment', 'errors_json'
  ]);
  sheet.getRange(1, 1, 1, 48).setFontWeight('bold').setBackground('#ea4335').setFontColor('white');

  Logger.log('✅ Sheet structure created successfully');
}

/**
 * Test function - call this to verify API is working
 */
function testApi() {
  // Test ping
  const pingResult = handlePing({
    user_id: 'test-user-123',
    display_name: 'Test User'
  });
  Logger.log('Ping result: ' + JSON.stringify(pingResult));

  // Test progress
  const progressResult = handleProgress({});
  Logger.log('Progress result: ' + JSON.stringify(progressResult));
}
