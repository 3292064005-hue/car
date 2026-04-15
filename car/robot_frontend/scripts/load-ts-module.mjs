import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import ts from 'typescript';

const nativeRequire = createRequire(import.meta.url);
const FRONTEND_ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const SRC_ROOT = path.join(FRONTEND_ROOT, 'src');
const cache = new Map();

function resolveCandidate(basePath) {
  const candidates = [
    basePath,
    `${basePath}.ts`,
    `${basePath}.tsx`,
    `${basePath}.js`,
    `${basePath}.mjs`,
    path.join(basePath, 'index.ts'),
    path.join(basePath, 'index.tsx'),
    path.join(basePath, 'index.js'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
      return candidate;
    }
  }
  return null;
}

function resolveSpecifier(specifier, fromFile) {
  if (specifier.startsWith('@/')) {
    const resolved = resolveCandidate(path.join(SRC_ROOT, specifier.slice(2)));
    if (!resolved) throw new Error(`cannot resolve alias import ${specifier} from ${fromFile}`);
    return { type: 'local', path: resolved };
  }
  if (specifier.startsWith('./') || specifier.startsWith('../')) {
    const resolved = resolveCandidate(path.resolve(path.dirname(fromFile), specifier));
    if (!resolved) throw new Error(`cannot resolve relative import ${specifier} from ${fromFile}`);
    return { type: 'local', path: resolved };
  }
  return { type: 'external', path: specifier };
}

export function loadTsModule(moduleRelativePath) {
  const entryPath = path.resolve(FRONTEND_ROOT, moduleRelativePath);
  return loadResolvedModule(entryPath);
}

function loadResolvedModule(filePath) {
  if (cache.has(filePath)) {
    return cache.get(filePath).exports;
  }
  const source = fs.readFileSync(filePath, 'utf8').replaceAll('import.meta.env', 'globalThis.__IMPORT_META_ENV__');
  const transpiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.ReactJSX,
      esModuleInterop: true,
    },
    fileName: filePath,
    reportDiagnostics: false,
  }).outputText;
  const module = { exports: {} };
  cache.set(filePath, module);
  const sandbox = {
    module,
    exports: module.exports,
    require: (specifier) => {
      const resolved = resolveSpecifier(specifier, filePath);
      if (resolved.type === 'external') {
        return nativeRequire(resolved.path);
      }
      return loadResolvedModule(resolved.path);
    },
    console,
    process,
    Buffer,
    setTimeout,
    clearTimeout,
    global,
    globalThis: { ...global, __IMPORT_META_ENV__: {} },
    __dirname: path.dirname(filePath),
    __filename: filePath,
  };
  vm.runInNewContext(transpiled, sandbox, { filename: filePath });
  return module.exports;
}
