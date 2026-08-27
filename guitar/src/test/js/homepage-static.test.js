import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const testDirectory = dirname(fileURLToPath(import.meta.url));
const staticDirectory = resolve(testDirectory, '../../main/resources/static');

test('首页引用的本地静态资源均已发布', () => {
  const html = readFileSync(resolve(staticDirectory, 'index.html'), 'utf8');
  const resourcePaths = Array.from(
    html.matchAll(/(?:src|href)=["'](\/(?!\/)[^"'#?]+)["']/g),
    match => match[1]
  );

  assert.ok(resourcePaths.length > 0, '首页至少应引用一个本地静态资源');

  for (const resourcePath of resourcePaths) {
    const publishedFile = resolve(staticDirectory, resourcePath.slice(1));
    assert.ok(existsSync(publishedFile), `首页引用的静态资源不存在: ${resourcePath}`);
  }
});
