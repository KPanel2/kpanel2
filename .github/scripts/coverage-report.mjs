#!/usr/bin/env node
/**
 * Parse coverage output, emit GitHub warnings, write job summary, and optional JSON.
 * Never fails the workflow.
 *
 * Usage:
 *   node coverage-report.mjs <summary.json|test.log> <label> [threshold] [options]
 *
 * Options:
 *   --json-out path
 *   --diff-base ref
 *   --diff-format pytest|karma-html
 *   --diff-coverage-path path
 *   --diff-source-root path
 *   --diff-repo-path-prefix path
 */
import { appendFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { computePrCoverage, roundPct } from './pr-diff-coverage.mjs';

function parseArgs(argv) {
  const options = {
    inputPath: null,
    label: null,
    threshold: 80,
    jsonOut: null,
    diffBase: process.env.DIFF_BASE_REF ?? null,
    diffFormat: null,
    diffCoveragePath: null,
    diffSourceRoot: null,
    diffRepoPathPrefix: '',
  };

  const positional = [];
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--json-out') {
      options.jsonOut = argv[index + 1];
      index += 1;
    } else if (arg === '--diff-base') {
      options.diffBase = argv[index + 1];
      index += 1;
    } else if (arg === '--diff-format') {
      options.diffFormat = argv[index + 1];
      index += 1;
    } else if (arg === '--diff-coverage-path') {
      options.diffCoveragePath = argv[index + 1];
      index += 1;
    } else if (arg === '--diff-source-root') {
      options.diffSourceRoot = argv[index + 1];
      index += 1;
    } else if (arg === '--diff-repo-path-prefix') {
      options.diffRepoPathPrefix = argv[index + 1];
      index += 1;
    } else {
      positional.push(arg);
    }
  }

  [options.inputPath, options.label, options.threshold] = [
    positional[0] ?? null,
    positional[1] ?? null,
    Number(positional[2] ?? options.threshold),
  ];

  return options;
}

function warn(message) {
  console.log(`::warning::${message}`);
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

function formatPrCoverage(prCoverage) {
  if (!prCoverage?.available) {
    return 'n/a';
  }
  if (prCoverage.noChanges) {
    return 'No changed lines';
  }
  if (prCoverage.noCoverableChanges) {
    return 'No coverable changes';
  }
  if (prCoverage.lines == null) {
    return 'n/a';
  }
  return `${prCoverage.lines}%`;
}

function buildResult(label, threshold, metrics, prCoverage) {
  const lines = metrics.lines;
  if (lines == null || Number.isNaN(Number(lines))) {
    return {
      label,
      threshold,
      belowThreshold: false,
      parseError: true,
      metrics,
      prCoverage,
    };
  }

  const roundedLines = roundPct(lines);
  const prLines = prCoverage?.lines == null ? null : roundPct(prCoverage.lines);
  const prBelowThreshold = prLines != null && prLines < threshold;

  return {
    label,
    threshold,
    belowThreshold: roundedLines < threshold,
    lines: roundedLines,
    statements: metrics.statements == null ? null : roundPct(metrics.statements),
    branches: metrics.branches == null ? null : roundPct(metrics.branches),
    functions: metrics.functions == null ? null : roundPct(metrics.functions),
    prCoverage,
    prLines,
    prBelowThreshold,
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

  const overallStatus = result.belowThreshold
    ? `⚠️ Below recommended minimum (${result.threshold}%)`
    : `✅ Meets recommended minimum (${result.threshold}%)`;

  const prStatus = !result.prCoverage?.available
    ? 'n/a'
    : result.prCoverage.noChanges
      ? 'No changed lines in this PR'
      : result.prCoverage.noCoverableChanges
        ? 'Changed lines are not coverable'
        : result.prBelowThreshold
          ? `⚠️ Below recommended minimum (${result.threshold}%)`
          : `✅ Meets recommended minimum (${result.threshold}%)`;

  const rows = [
    ['Overall lines', formatPct(result.lines)],
    ['PR new code lines', formatPrCoverage(result.prCoverage)],
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
    `**Overall status:** ${overallStatus}`,
    `**PR new code status:** ${prStatus}`,
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
    warn(`${result.label} overall line coverage is ${result.lines}% (recommended minimum: ${result.threshold}%)`);
  } else {
    console.log(`${result.label} overall line coverage: ${result.lines}%`);
  }

  if (result.prBelowThreshold) {
    warn(
      `${result.label} PR new-code line coverage is ${result.prLines}% `
      + `(recommended minimum: ${result.threshold}%)`,
    );
  } else if (result.prLines != null) {
    console.log(`${result.label} PR new-code line coverage: ${result.prLines}%`);
  }
}

const options = parseArgs(process.argv.slice(2));
const { inputPath, label, threshold } = options;

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

let prCoverage = { available: false };
if (options.diffBase && options.diffFormat && options.diffCoveragePath) {
  prCoverage = computePrCoverage({
    baseRef: options.diffBase,
    format: options.diffFormat,
    coveragePath: options.diffCoveragePath,
    sourceRoot: options.diffSourceRoot ?? undefined,
    repoPathPrefix: options.diffRepoPathPrefix,
  });
}

const result = buildResult(label, threshold, metrics, prCoverage);
emitWarnings(result);
writeJobSummary(result);

if (options.jsonOut) {
  writeFileSync(options.jsonOut, `${JSON.stringify(result, null, 2)}\n`);
}
