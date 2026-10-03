'use strict';

// Structural source check only; it does not render React Native or prove A5.
const fs = require('node:fs');

function verifyHookup(source, ts) {
  const tree = ts.createSourceFile('App.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  if (tree.parseDiagnostics.length) throw new Error('invalid TSX');
  let matches = 0;
  function visit(node) {
    if ((ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) &&
        node.tagName.getText(tree) === 'RlsTrial') {
      const mount = ts.isJsxOpeningElement(node) ? node.parent : node;
      const conditional = mount.parent;
      if (!ts.isConditionalExpression(conditional) || conditional.whenTrue !== mount ||
          conditional.condition.getText(tree) !== 'userId') {
        throw new Error('RlsTrial must be the guarded conditional branch');
      }
      let branch = conditional;
      let ancestor = branch.parent;
      while (ancestor && !ts.isJsxExpression(ancestor)) {
        const wrapper = ts.isParenthesizedExpression(ancestor) && ancestor.expression === branch;
        const outerBranch = ts.isConditionalExpression(ancestor) &&
          (ancestor.whenTrue === branch || ancestor.whenFalse === branch);
        if (!wrapper && !outerBranch) throw new Error('mount must flow directly to a JSX child');
        branch = ancestor;
        ancestor = branch.parent;
      }
      if (!ancestor || ancestor.expression !== branch ||
          !(ts.isJsxElement(ancestor.parent) || ts.isJsxFragment(ancestor.parent))) {
        throw new Error('conditional must be a JSX child expression');
      }
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
