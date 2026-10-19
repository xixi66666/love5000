import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {localFile, validateManifest} from '../scripts/manifest.mjs';

test('reject out-of-range and non-finite subtitle timing before rendering', () => {
  for (const end of [NaN, Infinity, -1, 12]) {
    assert.throws(() => validateManifest({day: 'test', scenes: [{heading: 'demo', summary: '',
      audio: 'voice.wav', durationInFrames: 30, captions: [{text: 'hi', start: 0, end}]}]}));
  }
});
test('report assets cannot escape into sibling private directories', () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'daily-assets-'));
  fs.mkdirSync(path.join(temporary, 'report'));
  fs.writeFileSync(path.join(temporary, 'private'), 'private');
  assert.throws(() => localFile(path.join(temporary, 'report'), '../private'));
  fs.rmSync(temporary, {recursive: true, force: true});
});
