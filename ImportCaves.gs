// ===========================================
// IMPORT TATRY CAVES DATA
// ===========================================
// This script imports Tatry caves from caves_transformed.jsonl into the CAVES sheet
// Run this once after setupSheets() to populate the database

/**
 * Import Tatry caves from JSON data
 * You'll need to manually paste the filtered JSONL data or use the import function below
 */
function importTatryCavesManual() {
  // INSTRUCTIONS:
  // 1. Go to: https://raw.githubusercontent.com/dlubom/Polish-Cave-Data-Scraper/refs/heads/main/caves_transformed.jsonl
  // 2. Copy the entire file content
  // 3. Paste it into the jsonlData variable below (between the backticks)
  // 4. Run this function

  const jsonlData = `
PASTE_JSONL_DATA_HERE
`;

  importTatryCaves(jsonlData);
}

/**
 * Process and import caves from JSONL string
 */
function importTatryCaves(jsonlData) {
  const cavesSheet = getSheet('CAVES');
  const lines = jsonlData.trim().split('\n');

  const tatryCaves = [];
  const tatryRegions = ['Tatry', 'Tat', 'Wysokie Tatry', 'Zachodnie Tatry', 'Tatrzański Park Narodowy'];

  let imported = 0;
  let skipped = 0;

  for (let line of lines) {
    if (!line.trim()) continue;

    try {
      const cave = JSON.parse(line);

      // Check if Tatry region
      const isTatry = cave.region && tatryRegions.some(r => cave.region.includes(r));

      // Only import if: Tatry + has coordinates (plan images optional)
      if (isTatry && cave.latitude && cave.longitude) {
        // Use inventory_number as cave_id (more stable, won't be converted to number)
        // Fallback to cave_id if inventory_number is missing
        const caveId = cave.inventory_number || cave.cave_id;

        tatryCaves.push([
          caveId,
          cave.name,
          cave.region,
          cave.latitude,
          cave.longitude,
          0,  // n_submissions (initial)
          0,  // n_open_assignments (initial)
          '', // last_assigned_at (empty initially)
          false, // disabled
          ''  // disabled_reason
        ]);
        imported++;
      } else {
        skipped++;
      }

    } catch (e) {
      Logger.log('Error parsing line: ' + e.toString());
      skipped++;
    }
  }

  // Batch insert (more efficient than appendRow in loop)
  if (tatryCaves.length > 0) {
    cavesSheet.getRange(
      cavesSheet.getLastRow() + 1,
      1,
      tatryCaves.length,
      10
    ).setValues(tatryCaves);
  }

  Logger.log(`✅ Import complete: ${imported} caves imported, ${skipped} skipped`);
  Logger.log(`Total Tatry caves in database: ${tatryCaves.length}`);

  return {
    imported: imported,
    skipped: skipped,
    total: tatryCaves.length
  };
}

/**
 * Alternative: Import from URL using UrlFetchApp
 * This is the easiest method - just run this function!
 */
function importTatryCavesFromURL() {
  const url = 'https://raw.githubusercontent.com/dlubom/Polish-Cave-Data-Scraper/refs/heads/main/caves_transformed.jsonl';

  try {
    Logger.log('Fetching data from GitHub...');
    const response = UrlFetchApp.fetch(url);
    const jsonlData = response.getContentText();

    Logger.log('Data fetched, processing...');
    const result = importTatryCaves(jsonlData);

    Logger.log('✅ SUCCESS!');
    Logger.log(`Imported ${result.imported} Tatry caves`);
    Logger.log(`Skipped ${result.skipped} non-Tatry or invalid caves`);

    return result;

  } catch (error) {
    Logger.log('❌ ERROR: ' + error.toString());
    Logger.log('Try using importTatryCavesManual() instead');
    throw error;
  }
}

/**
 * Quick stats about imported caves
 */
function showCaveStats() {
  const cavesSheet = getSheet('CAVES');
  const data = cavesSheet.getDataRange().getValues();

  const caves = data.slice(1); // Skip header

  Logger.log('=== CAVE DATABASE STATS ===');
  Logger.log(`Total caves: ${caves.length}`);

  // Count by region
  const regionCounts = {};
  caves.forEach(row => {
    const region = row[2] || 'Unknown';
    regionCounts[region] = (regionCounts[region] || 0) + 1;
  });

  Logger.log('\nBy region:');
  Object.entries(regionCounts).forEach(([region, count]) => {
    Logger.log(`  ${region}: ${count}`);
  });

  // Count by submission status
  const submissionCounts = {
    '0': 0,
    '1-2': 0,
    '3-4': 0,
    '5+': 0
  };

  caves.forEach(row => {
    const n = row[5] || 0;
    if (n === 0) submissionCounts['0']++;
    else if (n <= 2) submissionCounts['1-2']++;
    else if (n <= 4) submissionCounts['3-4']++;
    else submissionCounts['5+']++;
  });

  Logger.log('\nBy submission count:');
  Object.entries(submissionCounts).forEach(([range, count]) => {
    Logger.log(`  ${range} submissions: ${count} caves`);
  });
}

/**
 * Reset all counters to zero (useful for testing)
 */
function resetAllCounters() {
  const cavesSheet = getSheet('CAVES');
  const data = cavesSheet.getDataRange().getValues();

  for (let i = 1; i < data.length; i++) { // Skip header
    cavesSheet.getRange(i + 1, 6).setValue(0); // n_submissions
    cavesSheet.getRange(i + 1, 7).setValue(0); // n_open_assignments
    cavesSheet.getRange(i + 1, 8).setValue(''); // last_assigned_at
  }

  Logger.log('✅ All counters reset to zero');
}

/**
 * Helper to get sheet (copy from Code.gs)
 */
function getSheet(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(name);
  if (!sheet) {
    throw new Error('Sheet not found: ' + name);
  }
  return sheet;
}
