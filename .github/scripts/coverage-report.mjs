#!/usr/bin/env node
/**
 * Parse coverage output, emit GitHub warnings/errors, write job summary, and optional JSON.
 * Fails the workflow when overall or PR new-code line coverage is below --fail-threshold.
 * Emits a warning when PR new-code coverage is below --pr-warn-threshold.
 *
 * Usage:
 *   node coverage-report.mjs <summary.json|test.log> <label> [fail-threshold] [options]
 *
 * Options:
 *   --json-out path
 *   --fail-threshold N        (default: positional arg or 80)
 *   --pr-warn-threshold N     (default: 90)
 *   --diff-base ref
 *   --diff-format pytest|karma-html
 *   --diff-coverage-path path
 *   --diff-source-root path
 *   --diff-repo-path-prefix path
 */
import { appendFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { computePrCoverage, roundPct } from './pr-diff-coverage.mjs';

function parseArgs(argv) {
  const options = {
    inputPath: null,
    label: null,
    failThreshold: 80,
    prWarnThreshold: 90,
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
    } else if (arg === '--fail-threshold') {
      options.failThreshold = Number(argv[index + 1]);
      index += 1;
    } else if (arg === '--pr-warn-threshold') {
      options.prWarnThreshold = Number(argv[index + 1]);
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

  let positionalFailThreshold;
  [options.inputPath, options.label, positionalFailThreshold] = [
    positional[0] ?? null,
    positional[1] ?? null,
    positional[2] ?? null,
  ];

  if (positionalFailThreshold != null && !Number.isNaN(Number(positionalFailThreshold))) {
    options.failThreshold = Number(positionalFailThreshold);
  }

  return options;
}

export function evaluateCoverageThresholds({
  lines,
  prLines,
  prCoverage,
  failThreshold,
  prWarnThreshold,
}) {
  const roundedLines = lines == null ? null : roundPct(lines);
  const roundedPrLines = prLines == null ? null : roundPct(prLines);
  const prApplicable = Boolean(
    prCoverage?.available
    && !prCoverage.noChanges
    && !prCoverage.noCoverableChanges
    && roundedPrLines != null,
  );

  const belowFailThreshold = roundedLines != null && roundedLines < failThreshold;
  const prBelowFailThreshold = prApplicable && roundedPrLines < failThreshold;
  const prBelowWarnThreshold = prApplicable && roundedPrLines < prWarnThreshold;

  return {
    belowFailThreshold,
    prBelowFailThreshold,
    prBelowWarnThreshold,
    shouldFail: belowFailThreshold || prBelowFailThreshold,
    shouldWarnPr: prBelowWarnThreshold && !prBelowFailThreshold,
  };
}

function warn(message) {
  console.log(`::warning::${message}`);
}

function error(message) {
  console.log(`::error::${message}`);
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

function buildResult(label, failThreshold, prWarnThreshold, metrics, prCoverage) {
  const lines = metrics.lines;
  if (lines == null || Number.isNaN(Number(lines))) {
    return {
      label,
      failThreshold,
      prWarnThreshold,
      threshold: failThreshold,
      belowThreshold: false,
      belowFailThreshold: false,
      parseError: true,
      metrics,
      prCoverage,
    };
  }

  const roundedLines = roundPct(lines);
  const prLines = prCoverage?.lines == null ? null : roundPct(prCoverage.lines);
  const thresholds = evaluateCoverageThresholds({
    lines: roundedLines,
    prLines,
    prCoverage,
    failThreshold,
    prWarnThreshold,
  });

  return {
    label,
    failThreshold,
    prWarnThreshold,
    threshold: failThreshold,
    belowThreshold: thresholds.belowFailThreshold,
    belowFailThreshold: thresholds.belowFailThreshold,
    parseError: false,
    lines: roundedLines,
    statements: metrics.statements == null ? null : roundPct(metrics.statements),
    branches: metrics.branches == null ? null : roundPct(metrics.branches),
    functions: metrics.functions == null ? null : roundPct(metrics.functions),
    prCoverage,
    prLines,
    prBelowThreshold: thresholds.prBelowFailThreshold,
    prBelowFailThreshold: thresholds.prBelowFailThreshold,
    prBelowWarnThreshold: thresholds.prBelowWarnThreshold,
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

  const overallStatus = result.belowFailThreshold
    ? `❌ Below minimum (${result.failThreshold}%) — fails CI`
    : `✅ Meets minimum (${result.failThreshold}%)`;

  const prStatus = !result.prCoverage?.available
    ? 'n/a'
    : result.prCoverage.noChanges
      ? 'No changed lines in this PR'
      : result.prCoverage.noCoverableChanges
        ? 'Changed lines are not coverable'
        : result.prBelowFailThreshold
          ? `❌ Below minimum (${result.failThreshold}%) — fails CI`
          : result.prBelowWarnThreshold
            ? `⚠️ Below recommended (${result.prWarnThreshold}%)`
            : `✅ Meets recommended (${result.prWarnThreshold}%)`;

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

function emitCoverageMessages(result) {
  if (result.parseError) {
    warn(`${result.label} coverage report does not include a line coverage percentage`);
    return false;
  }

  let failed = false;

  if (result.belowFailThreshold) {
    error(
      `${result.label} overall line coverage is ${result.lines}% `
      + `(minimum: ${result.failThreshold}%)`,
    );
    failed = true;
  } else {
    console.log(`${result.label} overall line coverage: ${result.lines}%`);
  }

  if (result.prBelowFailThreshold) {
    error(
      `${result.label} PR new-code line coverage is ${result.prLines}% `
      + `(minimum: ${result.failThreshold}%)`,
    );
    failed = true;
  } else if (result.prBelowWarnThreshold) {
    warn(
      `${result.label} PR new-code line coverage is ${result.prLines}% `
      + `(recommended: ${result.prWarnThreshold}%)`,
    );
  } else if (result.prLines != null) {
    console.log(`${result.label} PR new-code line coverage: ${result.prLines}%`);
  }

  return failed;
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  const { inputPath, label, failThreshold, prWarnThreshold } = options;

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
    try {
      prCoverage = computePrCoverage({
        baseRef: options.diffBase,
        format: options.diffFormat,
        coveragePath: options.diffCoveragePath,
        sourceRoot: options.diffSourceRoot ?? undefined,
        repoPathPrefix: options.diffRepoPathPrefix,
      });
    } catch (error) {
      warn(`${label} PR diff coverage failed: ${error.message}`);
    }
  }

  const result = buildResult(label, failThreshold, prWarnThreshold, metrics, prCoverage);
  const failed = emitCoverageMessages(result);
  writeJobSummary(result);

  if (options.jsonOut) {
    writeFileSync(options.jsonOut, `${JSON.stringify(result, null, 2)}\n`);
  }

  if (failed) {
    process.exit(1);
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
