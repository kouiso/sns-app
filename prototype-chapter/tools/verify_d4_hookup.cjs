'use strict';

// Structural source check only; it does not render React Native or prove A5.
const fs = require('node:fs');

function verifyHookup(source, ts) {
  const tree = ts.createSourceFile('App.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  if (tree.parseDiagnostics.length) throw new Error('invalid TSX');
  let matches = 0;
  function visit(node) {
    if (ts.isJsxSelfClosingElement(node) && node.tagName.getText(tree) === 'RlsTrial') {
      const conditional = node.parent;
      if (!ts.isConditionalExpression(conditional) || conditional.whenTrue !== node ||
          conditional.condition.getText(tree) !== 'userId') {
        throw new Error('RlsTrial must be the guarded conditional branch');
      }
      let ancestor = conditional.parent;
      while (ancestor && !ts.isJsxExpression(ancestor)) ancestor = ancestor.parent;
      if (!ancestor) throw new Error('conditional must be a JSX expression');
      matches += 1;
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
  if (matches !== 1) throw new Error('one guarded RlsTrial mount is required');
  return {scope: 'TSX_STRUCTURE_NOT_RENDER_OR_INDEPENDENT_EXEC', mounts: matches};
}

module.exports = {verifyHookup};
if (require.main === module) {
  const [sourcePath, typescriptPath] = process.argv.slice(2);
  if (!sourcePath || !typescriptPath || process.argv.length !== 4) throw new Error('expected source and trusted TypeScript path');
  console.log(JSON.stringify(verifyHookup(fs.readFileSync(sourcePath, 'utf8'), require(typescriptPath))));
}
