import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';
import {build} from 'esbuild';

const renderer = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const project = path.resolve(process.argv[2]);
const sourceRoot = path.join(project, 'src');
const reportFile = path.join(project, 'diagnostics.json');
const files = fs.readdirSync(sourceRoot).filter(name => /\.tsx?$/.test(name)).map(name => path.join(sourceRoot, name));
const diagnostics = [];
const allowedPackages = /^(react(?:\/jsx(?:-dev)?-runtime)?|react-dom(?:\/client)?|remotion|@remotion\/player)$/;
for (const filename of files) {
  const text = fs.readFileSync(filename, 'utf8');
  const info = ts.preProcessFile(text, true, true);
  const ast = ts.createSourceFile(filename, text, ts.ScriptTarget.Latest, true);
  const inspect = node => {
    if (ts.isCallExpression(node) && (node.expression.kind === ts.SyntaxKind.ImportKeyword
      || ts.isIdentifier(node.expression) && node.expression.text === 'require')) {
      if (node.arguments.length !== 1 || !ts.isStringLiteral(node.arguments[0])) diagnostics.push({
        file: `src/${path.basename(filename)}`, line: ast.getLineAndCharacterOfPosition(node.pos).line + 1,
        column: 1, message: '动态导入必须使用固定字符串，并限定在模板目录或允许的库内。',
      });
    }
    if (ts.isPropertyAccessExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'require') {
      diagnostics.push({file: `src/${path.basename(filename)}`, line: 1, column: 1, message: '模板不支持 require.context 等目录扫描。'});
    }
    ts.forEachChild(node, inspect);
  };
  inspect(ast);
  for (const reference of [...info.importedFiles, ...info.referencedFiles, ...info.typeReferenceDirectives]) {
    const name = reference.fileName;
    const local = name.startsWith('.');
    const relative = path.relative(sourceRoot, path.resolve(path.dirname(filename), name));
    if ((!local && !allowedPackages.test(name)) || (local && (relative.startsWith('..') || path.isAbsolute(relative)))) {
      diagnostics.push({file: `src/${path.basename(filename)}`, line: 1, column: 1,
        message: '只允许模板目录内的文件，以及 React、Remotion 和 Player 导入。'});
    }
  }
}
if (!diagnostics.length) {
  const config = JSON.parse(fs.readFileSync(path.join(renderer, 'tsconfig.json'), 'utf8'));
  const {options} = ts.convertCompilerOptionsFromJson(config.compilerOptions, project);
  options.typeRoots = [path.join(renderer, 'node_modules/@types')];
  const host = ts.createCompilerHost(options);
  host.resolveModuleNames = (names, containingFile) => names.map(name =>
    ts.resolveModuleName(name, containingFile, options, ts.sys).resolvedModule
      ?? ts.resolveModuleName(name, path.join(renderer, 'src/index.ts'), options, ts.sys).resolvedModule);
  const program = ts.createProgram(files, options, host);
  for (const item of ts.getPreEmitDiagnostics(program).slice(0, 30)) {
    const position = item.file?.getLineAndCharacterOfPosition(item.start ?? 0);
    diagnostics.push({file: item.file ? `src/${path.basename(item.file.fileName)}` : 'template',
      line: position ? position.line + 1 : 1, column: position ? position.character + 1 : 1,
      message: ts.flattenDiagnosticMessageText(item.messageText, '\n').slice(0, 600)});
  }
}
if (!diagnostics.length) {
  try {
    await build({entryPoints: [path.join(sourceRoot, 'editor-preview.tsx')], bundle: true,
      outfile: path.join(project, 'preview/app.js'), format: 'iife', platform: 'browser',
      jsx: 'automatic', minify: true, nodePaths: [path.join(renderer, 'node_modules')],
      define: {'process.env.NODE_ENV': '"production"'}, logLevel: 'silent'});
  } catch (error) {
    for (const item of (error.errors ?? []).slice(0, 20)) diagnostics.push({
      file: item.location ? `src/${path.basename(item.location.file)}` : 'template',
      line: item.location?.line ?? 1, column: (item.location?.column ?? 0) + 1,
      message: item.text.slice(0, 600),
    });
    if (!diagnostics.length) diagnostics.push({file: 'template', line: 1, column: 1, message: '模板打包未完成。'});
  }
}
fs.writeFileSync(reportFile, JSON.stringify({ok: diagnostics.length === 0, diagnostics}));
