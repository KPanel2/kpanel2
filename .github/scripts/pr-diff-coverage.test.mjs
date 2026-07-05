import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  computePrDiffCoverage,
  loadPytestCoverage,
  parseGitDiff,
  parseKarmaHtmlFile,
  roundPct,
} from './pr-diff-coverage.mjs';

describe('pr-diff-coverage', () => {
  it('parses added lines from a git diff', () => {
    const diff = [
      'diff --git a/frontend/src/app/foo.ts b/frontend/src/app/foo.ts',
      '--- a/frontend/src/app/foo.ts',
      '+++ b/frontend/src/app/foo.ts',
      '@@ -1 +1,3 @@',
      '+const covered = true;',
      '+const uncovered = false;',
      '+const neutral = 1;',
    ].join('\n');

    const changed = parseGitDiff(diff);
    assert.deepEqual([...changed.get('frontend/src/app/foo.ts')], [1, 2, 3]);
  });

  it('computes PR coverage from changed coverable lines', () => {
    const changed = new Map([
      ['frontend/src/app/foo.ts', new Set([1, 2, 3])],
    ]);
    const coverage = new Map([
      ['frontend/src/app/foo.ts', {
        covered: new Set([1, 3]),
        coverable: new Set([1, 2, 3]),
      }],
    ]);

    const result = computePrDiffCoverage(changed, coverage);
    assert.equal(result.lines, roundPct((2 / 3) * 100));
    assert.equal(result.coverableChangedLines, 3);
    assert.equal(result.coveredChangedLines, 2);
  });

  it('computes PR coverage from pytest coverage json', () => {
    const changed = new Map([
      ['backend/app/foo.py', new Set([10, 11, 12])],
    ]);
    const coverage = loadPytestCoverage(
      fileURLToPath(new URL('./fixtures/pytest-coverage.json', import.meta.url)),
      'backend/',
    );

    const result = computePrDiffCoverage(changed, coverage);
    assert.equal(result.lines, roundPct((2 / 3) * 100));
    assert.equal(result.coverableChangedLines, 3);
    assert.equal(result.coveredChangedLines, 2);
  });

  it('parses karma html line coverage', () => {
    const html = `
      <a name='L10'></a>
      <a name='L11'></a>
      <span class="cline-any cline-yes">2x</span>
      <span class="cline-any cline-no">0x</span>
    `;

    const parsed = parseKarmaHtmlFile(html);
    assert.equal(parsed.covered.has(10), true);
    assert.equal(parsed.coverable.has(11), true);
    assert.equal(parsed.covered.has(11), false);
  });
});
