'use strict';
const assert = require('node:assert/strict');
const {verifyHookup} = require('./verify_d4_hookup.cjs');
const ts = require(process.argv[2]);
const good = 'const view = <View>{recovering ? <Text /> : (userId ? <RlsTrial /> : <Text />)}</View>;';
assert.equal(verifyHookup(good, ts).mounts, 1);
// TSX parses successfully even though the conditional is literal JSX text.
const literal = 'const view = <View>userId ? <RlsTrial /> : <Text /></View>;';
assert.equal(ts.createSourceFile('x.tsx', literal, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX).parseDiagnostics.length, 0);
assert.throws(() => verifyHookup(literal, ts), /guarded conditional/);
assert.throws(() => verifyHookup('const view = <View>{other ? <RlsTrial /> : <Text />}</View>;', ts), /guarded conditional/);
assert.throws(() => verifyHookup('const view = <Text />;', ts), /one guarded/);
assert.throws(() => verifyHookup(good + good.replace('view', 'another'), ts), /one guarded/);
assert.throws(() => verifyHookup('const view = <View>{userId ? <RlsTrial /> : <Text />}<RlsTrial></RlsTrial></View>;', ts), /guarded conditional/);
assert.throws(() => verifyHookup('const view = <View>{(() => { void (userId ? <RlsTrial /> : null); return null; })()}</View>;', ts), /flow directly/);
assert.throws(() => verifyHookup('const view = <View value={userId ? <RlsTrial /> : null} />;', ts), /JSX child expression/);
assert.equal(verifyHookup('const view = <View>{userId ? <RlsTrial></RlsTrial> : <Text />}</View>;', ts).mounts, 1);
console.log('9 TSX hookup structure checks passed; no render claim');
