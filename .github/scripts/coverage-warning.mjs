#!/usr/bin/env node
/**
 * Emit a GitHub Actions warning when coverage is below the threshold.
 * Never fails the workflow — test steps are responsible for pass/fail.
 *
 * Usage:
 *   node coverage-warning.mjs <summary.json|test.log> <label> [threshold]
 */
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const [inputPath, label, thresholdArg = '80'] = process.argv.slice(2);
const threshold = Number(thresholdArg);

if (!inputPath || !label) {
  console.log('::warning::Coverage check skipped: missing input path or label');
  process.exit(0);
}

const absolutePath = resolve(inputPath);
if (!existsSync(absolutePath)) {
  console.log(`::warning::${label} coverage report not found at ${inputPath}`);
  process.exit(0);
}

function warn(message) {
  console.log(`::warning::${message}`);
}

function reportCoverage(pct) {
  const rounded = Math.round(Number(pct) * 100) / 100;
  if (Number.isNaN(rounded)) {
    warn(`${label} coverage percentage could not be parsed`);
    return;
  }

  if (rounded < threshold) {
    warn(`${label} line coverage is ${rounded}% (recommended minimum: ${threshold}%)`);
  } else {
    console.log(`${label} line coverage: ${rounded}%`);
  }
}

function parseJsonCoverage(data) {
  return data.total?.lines?.pct ?? data.totals?.percent_covered ?? null;
}

function parseLogCoverage(contents) {
  const match = contents.match(/^Lines\s+:\s+([0-9.]+)%/m);
  return match ? Number(match[1]) : null;
}

const contents = readFileSync(absolutePath, 'utf8');

if (inputPath.endsWith('.log')) {
  const pct = parseLogCoverage(contents);
  if (pct == null) {
    warn(`${label} test log does not include a line coverage summary`);
    process.exit(0);
  }
  reportCoverage(pct);
  process.exit(0);
}

try {
  const data = JSON.parse(contents);
  const pct = parseJsonCoverage(data);
  if (pct == null) {
    warn(`${label} coverage report does not include a line coverage percentage`);
    process.exit(0);
  }
  reportCoverage(pct);
} catch {
  warn(`${label} coverage report at ${inputPath} is not valid JSON`);
}
