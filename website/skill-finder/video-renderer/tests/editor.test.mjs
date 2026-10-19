import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import test from 'node:test';
import assert from 'node:assert/strict';

const renderer = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const testRoot = path.join(renderer, '.test-tmp');
function check(change) {
  fs.mkdirSync(testRoot, {recursive: true});
  const temporary = fs.mkdtempSync(path.join(testRoot, 'skillfinder-editor-'));
  try {
    fs.cpSync(path.join(renderer, 'src'), path.join(temporary, 'src'), {recursive: true});
    change?.(temporary);
    execFileSync(process.execPath, [path.join(renderer, 'scripts/build-editor.mjs'), temporary], {cwd: renderer});
    return JSON.parse(fs.readFileSync(path.join(temporary, 'diagnostics.json'), 'utf8'));
  } finally {
    if (path.dirname(temporary) === fs.realpathSync(testRoot) && path.basename(temporary).startsWith('skillfinder-editor-')) {
      fs.rmSync(temporary, {recursive: true, force: true});
    }
  }
}
test('actual React template compiles into the embedded Remotion Player', () => {
  const result = check();
  assert.equal(result.ok, true, JSON.stringify(result.diagnostics));
});
test('source imports cannot escape into backend private files', () => {
  const result = check(project => fs.appendFileSync(path.join(project, 'src/video.tsx'),
    '\nimport privateData from "../../backend/.env";\n'));
  assert.equal(result.ok, false);
  assert.match(result.diagnostics[0].message, /只允许/);
});
test('TypeScript syntax failures include an editable source location', () => {
  const result = check(project => fs.writeFileSync(path.join(project, 'src/video.tsx'), 'export const DailyVideo = ;'));
  assert.equal(result.ok, false);
  assert.ok(result.diagnostics.some(item => item.file === 'src/video.tsx' && item.line === 1));
});
test('computed import paths cannot scan directories outside the draft', () => {
  const result = check(project => fs.appendFileSync(path.join(project, 'src/video.tsx'),
    '\nconst moduleName = "hidden"; import("../" + moduleName);\n'));
  assert.equal(result.ok, false);
  assert.match(result.diagnostics[0].message, /动态导入/);
});
