import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { evaluateCoverageThresholds } from './coverage-report.mjs';

describe('coverage-report thresholds', () => {
  const prCoverage = { available: true, noChanges: false, noCoverableChanges: false };

  it('passes when overall and PR coverage meet thresholds', () => {
    const result = evaluateCoverageThresholds({
      lines: 92,
      prLines: 95,
      prCoverage,
      failThreshold: 80,
      prWarnThreshold: 90,
    });

    assert.equal(result.belowFailThreshold, false);
    assert.equal(result.prBelowFailThreshold, false);
    assert.equal(result.prBelowWarnThreshold, false);
    assert.equal(result.shouldFail, false);
    assert.equal(result.shouldWarnPr, false);
  });

  it('fails when overall coverage is below 80%', () => {
    const result = evaluateCoverageThresholds({
      lines: 79.5,
      prLines: 95,
      prCoverage,
      failThreshold: 80,
      prWarnThreshold: 90,
    });

    assert.equal(result.belowFailThreshold, true);
    assert.equal(result.shouldFail, true);
  });

  it('fails when PR new-code coverage is below 80%', () => {
    const result = evaluateCoverageThresholds({
      lines: 90,
      prLines: 75,
      prCoverage,
      failThreshold: 80,
      prWarnThreshold: 90,
    });

    assert.equal(result.prBelowFailThreshold, true);
    assert.equal(result.shouldFail, true);
    assert.equal(result.shouldWarnPr, false);
  });

  it('warns but does not fail when PR new-code coverage is between 80% and 90%', () => {
    const result = evaluateCoverageThresholds({
      lines: 90,
      prLines: 85,
      prCoverage,
      failThreshold: 80,
      prWarnThreshold: 90,
    });

    assert.equal(result.prBelowFailThreshold, false);
    assert.equal(result.prBelowWarnThreshold, true);
    assert.equal(result.shouldFail, false);
    assert.equal(result.shouldWarnPr, true);
  });

  it('ignores PR thresholds when diff coverage is unavailable', () => {
    const result = evaluateCoverageThresholds({
      lines: 90,
      prLines: 50,
      prCoverage: { available: false },
      failThreshold: 80,
      prWarnThreshold: 90,
    });

    assert.equal(result.prBelowFailThreshold, false);
    assert.equal(result.prBelowWarnThreshold, false);
    assert.equal(result.shouldFail, false);
  });
});
