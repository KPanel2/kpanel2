#!/usr/bin/env node
/**
 * Create or update a sticky PR comment with combined frontend/backend coverage.
 *
 * Usage:
 *   node update-pr-coverage-comment.mjs --suite frontend --json path/to/result.json
 */
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const MARKER = '<!-- kpanel-coverage-report -->';
const DATA_MARKER_START = '<!-- kpanel-coverage-data';
const DATA_MARKER_END = '-->';

function parseArgs(argv) {
  const options = { suite: null, json: null };
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === '--suite') {
      options.suite = argv[index + 1];
      index += 1;
    } else if (argv[index] === '--json') {
      options.json = argv[index + 1];
      index += 1;
    }
  }
  return options;
}

function request(path, { method = 'GET', body } = {}) {
  const token = process.env.GITHUB_TOKEN;
  const repository = process.env.GITHUB_REPOSITORY;
  if (!token || !repository) {
    throw new Error('GITHUB_TOKEN and GITHUB_REPOSITORY are required');
  }

  return fetch(`https://api.github.com/repos/${repository}${path}`, {
    method,
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${token}`,
      'X-GitHub-Api-Version': '2022-11-28',
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  }).then(async (response) => {
    if (!response.ok) {
      const text = await response.text();
      throw new Error(`GitHub API ${method} ${path} failed (${response.status}): ${text}`);
    }
    if (response.status === 204) {
      return null;
    }
    return response.json();
  });
}

function parseStoredData(body) {
  const start = body.indexOf(DATA_MARKER_START);
  if (start < 0) {
    return {};
  }

  const end = body.indexOf(DATA_MARKER_END, start);
  if (end < 0) {
    return {};
  }

  const payload = body.slice(start + DATA_MARKER_START.length, end).trim();
  try {
    return JSON.parse(payload);
  } catch {
    return {};
  }
}

function formatPct(value) {
  if (value == null) {
    return 'n/a';
  }
  return `${value}%`;
}

function statusFor(result) {
  if (!result || result.parseError) {
    return '❓ Unavailable';
  }
  return result.belowThreshold
    ? `⚠️ Below ${result.threshold}%`
    : `✅ Meets ${result.threshold}%`;
}

function renderComment(data) {
  const suites = ['Frontend', 'Backend'];
  const rows = suites.map((suiteLabel) => {
    const key = suiteLabel.toLowerCase();
    const result = data[key];
    const workflowLink = result?.workflowUrl
      ? `[${suiteLabel} run](${result.workflowUrl})`
      : suiteLabel;

    return `| ${workflowLink} | ${formatPct(result?.lines)} | ${result?.threshold ?? 80}% | ${statusFor(result)} |`;
  });

  const sha = process.env.GITHUB_SHA?.slice(0, 7) ?? 'unknown';

  return [
    MARKER,
    '## 📊 Test coverage',
    '',
    'Tests must pass for merge. Coverage below 80% is reported as a warning only.',
    '',
    '| Suite | Lines | Target | Status |',
    '| --- | --- | --- | --- |',
    ...rows,
    '',
    `<sub>Updated for commit \`${sha}\` by GitHub Actions.</sub>`,
    '',
    `${DATA_MARKER_START}${JSON.stringify(data)}${DATA_MARKER_END}`,
  ].join('\n');
}

async function main() {
  const eventName = process.env.GITHUB_EVENT_NAME;
  const eventPath = process.env.GITHUB_EVENT_PATH;
  if (eventName !== 'pull_request' || !eventPath) {
    console.log('Not a pull_request event; skipping PR coverage comment.');
    return;
  }

  const event = JSON.parse(readFileSync(eventPath, 'utf8'));
  const pullNumber = event.pull_request?.number;
  if (!pullNumber) {
    console.log('No pull request number found; skipping PR coverage comment.');
    return;
  }

  const { suite, json } = parseArgs(process.argv.slice(2));
  if (!suite || !json) {
    throw new Error('Usage: update-pr-coverage-comment.mjs --suite <frontend|backend> --json <path>');
  }

  const jsonPath = resolve(json);
  if (!existsSync(jsonPath)) {
    throw new Error(`Coverage JSON not found: ${json}`);
  }

  const suiteResult = JSON.parse(readFileSync(jsonPath, 'utf8'));
  const comments = await request(`/issues/${pullNumber}/comments`);
  const existing = comments.find((comment) => comment.body?.includes(MARKER));

  const merged = existing ? parseStoredData(existing.body) : {};
  merged[suite] = suiteResult;

  const body = renderComment(merged);

  if (existing) {
    await request(`/issues/comments/${existing.id}`, {
      method: 'PATCH',
      body: { body },
    });
    console.log(`Updated coverage comment on PR #${pullNumber}`);
    return;
  }

  await request(`/issues/${pullNumber}/comments`, {
    method: 'POST',
    body: { body },
  });
  console.log(`Created coverage comment on PR #${pullNumber}`);
}

main().catch((error) => {
  console.log(`::warning::${error.message}`);
  process.exit(0);
});
