#!/usr/bin/env node
/**
 * Compute line coverage for lines changed in the current PR/branch.
 */
import { execSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

export function roundPct(value) {
  return Math.round(Number(value) * 100) / 100;
}

export function parseGitDiff(diffText) {
  const changed = new Map();
  let currentFile = null;
  let newLineNum = 0;

  for (const line of diffText.split('\n')) {
    if (line.startsWith('+++ b/')) {
      currentFile = line.slice(6);
      if (!changed.has(currentFile)) {
        changed.set(currentFile, new Set());
      }
      continue;
    }

    if (!currentFile) {
      continue;
    }

    if (line.startsWith('@@')) {
      const match = line.match(/@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      if (match) {
        newLineNum = Number.parseInt(match[1], 10);
      }
      continue;
    }

    if (line.startsWith('+') && !line.startsWith('+++')) {
      changed.get(currentFile).add(newLineNum);
      newLineNum += 1;
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      continue;
    } else if (line.startsWith(' ')) {
      newLineNum += 1;
    }
  }

  return changed;
}

export function getChangedLines(baseRef) {
  if (!baseRef) {
    return new Map();
  }

  try {
    const diff = execSync(`git diff -U0 ${baseRef}...HEAD`, {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    });
    return parseGitDiff(diff);
  } catch {
    return new Map();
  }
}

export function loadPytestCoverage(coveragePath, repoPathPrefix) {
  const data = JSON.parse(readFileSync(resolve(coveragePath), 'utf8'));
  const map = new Map();

  for (const [file, info] of Object.entries(data.files ?? {})) {
    const normalized = `${repoPathPrefix}${file}`.replace(/\\/g, '/');
    const executed = new Set(info.executed_lines ?? []);
    const missing = new Set(info.missing_lines ?? []);
    const coverable = new Set([...executed, ...missing]);
    map.set(normalized, { executed, coverable });
  }

  return map;
}

function walkHtmlFiles(directory) {
  const files = [];
  for (const entry of readdirSync(directory)) {
    const fullPath = join(directory, entry);
    const stats = statSync(fullPath);
    if (stats.isDirectory()) {
      files.push(...walkHtmlFiles(fullPath));
    } else if (entry.endsWith('.html') && entry !== 'index.html' && !entry.endsWith('.css')) {
      files.push(fullPath);
    }
  }
  return files;
}

function karmaHtmlToSourcePath(reportPath, coverageRoot, sourceRoot) {
  const relHtml = relative(coverageRoot, reportPath).replace(/\\/g, '/');
  const relSource = relHtml.replace(/\.html$/, '');
  return `${sourceRoot}/${relSource}`.replace(/\\/g, '/');
}

export function parseKarmaHtmlFile(html) {
  const covered = new Set();
  const coverable = new Set();

  const lineNumbers = [...html.matchAll(/name='L(\d+)'/g)]
    .map((match) => Number.parseInt(match[1], 10));
  const statuses = [...html.matchAll(/cline-any cline-(yes|no|neutral)/g)]
    .map((match) => match[1]);

  const count = Math.min(lineNumbers.length, statuses.length);
  for (let index = 0; index < count; index += 1) {
    const line = lineNumbers[index];
    const status = statuses[index];
    if (status === 'yes' || status === 'no') {
      coverable.add(line);
      if (status === 'yes') {
        covered.add(line);
      }
    }
  }

  return { covered, coverable };
}

export function loadKarmaHtmlCoverage(coverageRoot, sourceRoot) {
  const map = new Map();
  const absoluteCoverageRoot = resolve(coverageRoot);
  if (!existsSync(absoluteCoverageRoot)) {
    return map;
  }

  for (const htmlPath of walkHtmlFiles(absoluteCoverageRoot)) {
    const html = readFileSync(htmlPath, 'utf8');
    if (!html.includes('Code coverage report for')) {
      continue;
    }

    const sourcePath = karmaHtmlToSourcePath(htmlPath, absoluteCoverageRoot, sourceRoot);
    map.set(sourcePath, parseKarmaHtmlFile(html));
  }

  return map;
}

export function computePrDiffCoverage(changedLines, coverageByFile) {
  let changedCoverable = 0;
  let coveredChanged = 0;
  let changedTotal = 0;

  for (const [, lines] of changedLines) {
    for (const line of lines) {
      changedTotal += 1;
    }
  }

  if (changedTotal === 0) {
    return {
      available: true,
      noChanges: true,
      lines: null,
      changedLines: 0,
      coveredChangedLines: 0,
      coverableChangedLines: 0,
    };
  }

  for (const [file, lines] of changedLines) {
    const coverage = coverageByFile.get(file);
    if (!coverage) {
      continue;
    }

    for (const line of lines) {
      if (!coverage.coverable.has(line)) {
        continue;
      }

      changedCoverable += 1;
      if (coverage.covered.has(line)) {
        coveredChanged += 1;
      }
    }
  }

  if (changedCoverable === 0) {
    return {
      available: true,
      noChanges: false,
      lines: null,
      changedLines: changedTotal,
      coveredChangedLines: 0,
      coverableChangedLines: 0,
      noCoverableChanges: true,
    };
  }

  return {
    available: true,
    noChanges: false,
    lines: roundPct((coveredChanged / changedCoverable) * 100),
    changedLines: changedTotal,
    coveredChangedLines: coveredChanged,
    coverableChangedLines: changedCoverable,
  };
}

export function computePrCoverage({ baseRef, format, coveragePath, sourceRoot, repoPathPrefix }) {
  if (!baseRef) {
    return { available: false, reason: 'no_base_ref' };
  }

  const changedLines = getChangedLines(baseRef);
  let coverageByFile;

  if (format === 'pytest') {
    coverageByFile = loadPytestCoverage(coveragePath, repoPathPrefix ?? '');
  } else if (format === 'karma-html') {
    coverageByFile = loadKarmaHtmlCoverage(coveragePath, sourceRoot);
  } else {
    return { available: false, reason: 'unsupported_format' };
  }

  return computePrDiffCoverage(changedLines, coverageByFile);
}
