#!/usr/bin/env node
/**
 * Parse coverage output, emit GitHub warnings, write job summary, and optional JSON.
 * Never fails the workflow.
 *
 * Usage:
 *   node coverage-report.mjs <summary.json|test.log> <label> [threshold] [--json-out path]
 */
import { appendFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const args = process.argv.slice(2);
const jsonOutIndex = args.indexOf('--json-out');
const jsonOutPath = jsonOutIndex >= 0 ? args[jsonOutIndex + 1] : null;
const positional = args.filter((_, index) => index !== jsonOutIndex && index !== jsonOutIndex + 1);

const [inputPath, label, thresholdArg = '80'] = positional;
const threshold = Number(thresholdArg);

function warn(message) {
  console.log(`::warning::${message}`);
}

function roundPct(value) {
  return Math.round(Number(value) * 100) / 100;
}

function parseJsonCoverage(data) {
  const lines = data.total?.lines?.pct ?? data.totals?.percent_covered ?? null;
  const statements = data.total?.statements?.pct ?? data.totals?.percent_statements_covered ?? lines;
  const branches = data.total?.branches?.pct ?? null;
  const functions = data.total?.functions?.pct ?? null;
  return { lines, statements, branches, functions };
}

function parseLogCoverage(contents) {
  const read = (name) => {
    const match = contents.match(new RegExp(`^${name}\\s+:\\s+([0-9.]+)%`, 'm'));
    return match ? Number(match[1]) : null;
  };

  return {
    lines: read('Lines'),
    statements: read('Statements'),
    branches: read('Branches'),
    functions: read('Functions'),
  };
}

function formatPct(value) {
  if (value == null || Number.isNaN(Number(value))) {
    return 'n/a';
  }
  return `${roundPct(value)}%`;
}

function buildResult(metrics) {
  const lines = metrics.lines;
  if (lines == null || Number.isNaN(Number(lines))) {
    return {
      label,
      threshold,
      belowThreshold: false,
      parseError: true,
      metrics,
    };
  }

  const roundedLines = roundPct(lines);
  return {
    label,
    threshold,
    belowThreshold: roundedLines < threshold,
    lines: roundedLines,
    statements: metrics.statements == null ? null : roundPct(metrics.statements),
    branches: metrics.branches == null ? null : roundPct(metrics.branches),
    functions: metrics.functions == null ? null : roundPct(metrics.functions),
    workflowUrl: process.env.GITHUB_SERVER_URL && process.env.GITHUB_REPOSITORY && process.env.GITHUB_RUN_ID
      ? `${process.env.GITHUB_SERVER_URL}/${process.env.GITHUB_REPOSITORY}/actions/runs/${process.env.GITHUB_RUN_ID}`
      : null,
  };
}

function writeJobSummary(result) {
  const summaryPath = process.env.GITHUB_STEP_SUMMARY;
  if (!summaryPath) {
    return;
  }

  if (result.parseError) {
    appendFileSync(
      summaryPath,
      `### ${result.label} coverage\n\nCould not parse line coverage from the test output.\n\n`,
    );
    return;
  }

  const status = result.belowThreshold
    ? `⚠️ Below recommended minimum (${result.threshold}%)`
    : `✅ Meets recommended minimum (${result.threshold}%)`;

  const rows = [
    ['Lines', formatPct(result.lines)],
    ['Statements', formatPct(result.statements)],
    ['Branches', formatPct(result.branches)],
    ['Functions', formatPct(result.functions)],
  ];

  const table = [
    `### ${result.label} coverage`,
    '',
    `| Metric | Coverage |`,
    `| --- | --- |`,
    ...rows.map(([metric, value]) => `| ${metric} | ${value} |`),
    '',
    `**Status:** ${status}`,
    '',
  ].join('\n');

  appendFileSync(summaryPath, `${table}\n`);
}

function emitWarnings(result) {
  if (result.parseError) {
    warn(`${result.label} coverage report does not include a line coverage percentage`);
    return;
  }

  if (result.belowThreshold) {
    warn(`${result.label} line coverage is ${result.lines}% (recommended minimum: ${result.threshold}%)`);
  } else {
    console.log(`${result.label} line coverage: ${result.lines}%`);
  }
}

if (!inputPath || !label) {
  warn('Coverage check skipped: missing input path or label');
  process.exit(0);
}

const absolutePath = resolve(inputPath);
if (!existsSync(absolutePath)) {
  warn(`${label} coverage report not found at ${inputPath}`);
  process.exit(0);
}

const contents = readFileSync(absolutePath, 'utf8');
let metrics;

if (inputPath.endsWith('.log')) {
  metrics = parseLogCoverage(contents);
} else {
  try {
    metrics = parseJsonCoverage(JSON.parse(contents));
  } catch {
    warn(`${label} coverage report at ${inputPath} is not valid JSON`);
    process.exit(0);
  }
}

const result = buildResult(metrics);
emitWarnings(result);
writeJobSummary(result);

if (jsonOutPath) {
  writeFileSync(jsonOutPath, `${JSON.stringify(result, null, 2)}\n`);
}
