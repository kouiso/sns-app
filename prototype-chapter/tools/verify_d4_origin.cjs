'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const SOURCE_LIMIT = 1024 * 1024;

class OriginVerificationError extends Error {
  constructor(code) {
    super(code);
    this.name = 'OriginVerificationError';
  }
}

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function loadTypeScript(moduleDirectory) {
  if (!path.isAbsolute(moduleDirectory)) throw new OriginVerificationError('typescript_path_rejected');
  const stat = fs.lstatSync(moduleDirectory);
  if (!stat.isDirectory()) throw new OriginVerificationError('typescript_path_rejected');
  const packageDirectory = fs.existsSync(path.join(moduleDirectory, 'package.json'))
    ? moduleDirectory
    : path.join(moduleDirectory, 'typescript');
  return require(packageDirectory);
}

function readSource(sourcePath) {
  const stat = fs.lstatSync(sourcePath);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size === 0 || stat.size > SOURCE_LIMIT) {
    throw new OriginVerificationError('source_rejected');
  }
  return fs.readFileSync(sourcePath, 'utf8');
}

function countNodes(tree, ts) {
  let count = 0;
  function visit(node) {
    count += 1;
    ts.forEachChild(node, visit);
  }
  visit(tree);
  return count;
}

function isMovableRlsTrialImport(node, tree, ts) {
  if (!ts.isImportDeclaration(node) || node.modifiers?.length || node.attributes) return false;
  const clause = node.importClause;
  const bindings = clause?.namedBindings;
  const element = bindings && ts.isNamedImports(bindings) && bindings.elements.length === 1
    ? bindings.elements[0]
    : undefined;
  if (!clause || clause.isTypeOnly || clause.name || !element || element.isTypeOnly ||
      element.propertyName || element.name.text !== 'RlsTrial' ||
      !ts.isStringLiteral(node.moduleSpecifier) ||
      node.moduleSpecifier.text !== './components/RlsTrial') return false;
  const source = tree.text;
  const leading = ts.getLeadingCommentRanges(source, node.getFullStart()) ?? [];
  const trailing = ts.getTrailingCommentRanges(source, node.end) ?? [];
  return leading.length === 0 && trailing.length === 0;
}

function normalizePermittedImportPlacement(tree, ts) {
  let leadingImportCount = 0;
  while (leadingImportCount < tree.statements.length &&
         ts.isImportDeclaration(tree.statements[leadingImportCount])) {
    leadingImportCount += 1;
  }
  const leading = tree.statements.slice(0, leadingImportCount);
  const movable = leading.filter((node) => isMovableRlsTrialImport(node, tree, ts));
  if (movable.length !== 1) return tree;
  const reordered = [
    ...leading.filter((node) => node !== movable[0]),
    movable[0],
    ...tree.statements.slice(leadingImportCount),
  ];
  return ts.factory.updateSourceFile(tree, reordered);
}

// TypeScript's printer is used as an AST-derived normal form. It removes
// formatting trivia while retaining syntax, literals, JSX text, and comments.
// The one narrow placement allowance matches the chapter's instruction to add
// the exact RlsTrial import anywhere inside the existing leading import block.
function normalizeSource(source, ts) {
  const tree = ts.createSourceFile(
    'source.tsx',
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  if (tree.parseDiagnostics.length !== 0 || tree.statements.length === 0) {
    throw new OriginVerificationError('source_parse_rejected');
  }
  const printer = ts.createPrinter({
    newLine: ts.NewLineKind.LineFeed,
    removeComments: false,
  });
  const normalizedTree = normalizePermittedImportPlacement(tree, ts);
  return {normal: printer.printFile(normalizedTree), nodeCount: countNodes(tree, ts)};
}

function summarize(sources, ts) {
  if (!Array.isArray(sources) || sources.length !== 2) {
    throw new OriginVerificationError('source_set_rejected');
  }
  const normalized = sources.map((source) => normalizeSource(source, ts));
  return {
    digest: sha256(normalized.map(({normal}, index) => `${index}\0${normal}`).join('\0')),
    nodeCount: normalized.reduce((total, item) => total + item.nodeCount, 0),
  };
}

function verifyOrigin(expectedSources, actualSources, ts) {
  const expected = summarize(expectedSources, ts);
  const actual = summarize(actualSources, ts);
  return {
    verdict: expected.digest === actual.digest ? 'equivalent' : 'different',
    file_count: 2,
    expected_node_count: expected.nodeCount,
    actual_node_count: actual.nodeCount,
    expected_digest: expected.digest,
    actual_digest: actual.digest,
  };
}

module.exports = {
  OriginVerificationError,
  normalizeSource,
  verifyOrigin,
};

if (require.main === module) {
  const args = process.argv.slice(2);
  if (args.length !== 5) {
    process.stdout.write(`${JSON.stringify({
      verdict: 'invalid',
      file_count: 0,
      expected_node_count: 0,
      actual_node_count: 0,
      expected_digest: sha256(''),
      actual_digest: sha256(''),
    })}\n`);
    process.exitCode = 2;
  } else {
    try {
      const [expectedApp, expectedTrial, actualApp, actualTrial, typescriptDirectory] = args;
      const ts = loadTypeScript(typescriptDirectory);
      const result = verifyOrigin(
        [readSource(expectedApp), readSource(expectedTrial)],
        [readSource(actualApp), readSource(actualTrial)],
        ts,
      );
      process.stdout.write(`${JSON.stringify(result)}\n`);
      process.exitCode = result.verdict === 'equivalent' ? 0 : 1;
    } catch {
      process.stdout.write(`${JSON.stringify({
        verdict: 'invalid',
        file_count: 0,
        expected_node_count: 0,
        actual_node_count: 0,
        expected_digest: sha256(''),
        actual_digest: sha256(''),
      })}\n`);
      process.exitCode = 2;
    }
  }
}
