'use strict';

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {verifyOrigin} = require('./verify_d4_origin.cjs');

const typescriptDirectory = path.resolve(process.argv[2]);
const ts = require(
  fs.existsSync(path.join(typescriptDirectory, 'package.json'))
    ? typescriptDirectory
    : path.join(typescriptDirectory, 'typescript'),
);
const root = path.resolve(__dirname, '..');
const expectedApp = fs.readFileSync(path.join(root, 'candidates/d4-rls/app/App.tsx'), 'utf8');
const expectedTrial = fs.readFileSync(
  path.join(root, 'candidates/d4-rls/app/components/RlsTrial.tsx'),
  'utf8',
);

function digest(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function verdict(app, trial) {
  return verifyOrigin([expectedApp, expectedTrial], [app, trial], ts).verdict;
}

assert.equal(
  digest(expectedTrial),
  'bb545fb408b491fea9b20bd0a345f91eb1a4596893e23faacdee9ef7ed904961',
);
const geminiBlankLine = expectedTrial.replace(
  '      const timeout = setTimeout(() => controller.abort(), 15_000);\n      try {',
  '      const timeout = setTimeout(() => controller.abort(), 15_000);\n\n      try {',
);
assert.equal(
  digest(geminiBlankLine),
  '41616b777c2e17f66e7507a91635e87021bb1e25ae47a115244663634c7a970e',
);
assert.equal(verdict(expectedApp, geminiBlankLine), 'equivalent');

const modelImportPlacement = expectedApp
  .replace("import { RlsTrial } from './components/RlsTrial';\n", '')
  .replace(
    "import { supabaseConfiguration } from './lib/supabase';\n",
    "import { supabaseConfiguration } from './lib/supabase';\n" +
      "import { RlsTrial } from './components/RlsTrial';\n",
  );
assert.equal(verdict(modelImportPlacement, geminiBlankLine), 'equivalent');

const reorderedPredecessorImports = modelImportPlacement.replace(
  "import { StatusBar } from 'expo-status-bar';\n" +
    "import { useCallback, useEffect, useMemo, useRef, useState } from 'react';",
  "import { useCallback, useEffect, useMemo, useRef, useState } from 'react';\n" +
    "import { StatusBar } from 'expo-status-bar';",
);
assert.equal(verdict(reorderedPredecessorImports, expectedTrial), 'different');

const importOutsideLeadingBlock = expectedApp
  .replace("import { RlsTrial } from './components/RlsTrial';\n", '')
  .replace(
    "type SignedOutScreen = 'login' | 'signup' | 'confirmation' | 'reset-request';",
    "type SignedOutScreen = 'login' | 'signup' | 'confirmation' | 'reset-request';\n" +
      "import { RlsTrial } from './components/RlsTrial';",
  );
assert.equal(verdict(importOutsideLeadingBlock, expectedTrial), 'different');

const whitespaceOutsideJsx = expectedTrial.replace('const hasTrialPostIds', '\n\nconst hasTrialPostIds');
assert.equal(verdict(expectedApp, whitespaceOutsideJsx), 'equivalent');

const mutations = [
  expectedTrial.replace('import { ActivityIndicator', 'import { Image, ActivityIndicator'),
  expectedTrial.replace('export function RlsTrial', 'export default function RlsTrial'),
  expectedTrial.replace('&& new Set(trialPostIds).size === 2', '|| new Set(trialPostIds).size === 2'),
  expectedTrial.replace('制作側の準備を確認してください。', '制作側へ確認してください。'),
  expectedTrial.replace('value as Record<string, unknown>', 'value as any'),
  `${expectedTrial}\n// extra explanation\n`,
  `${expectedTrial}\n// @ts-ignore\n`,
  expectedTrial.replace('<Text style={styles.title}>', '<Text style={styles.title}> '),
];
for (const mutated of mutations) assert.equal(verdict(expectedApp, mutated), 'different');

const authBranchEdit = expectedApp.replace('if (!session) {', 'if (session) {');
assert.equal(verdict(authBranchEdit, expectedTrial), 'different');
assert.throws(
  () => verifyOrigin([expectedApp, expectedTrial], [expectedApp, 'export function {'], ts),
  /source_parse_rejected/,
);
assert.throws(
  () => verifyOrigin(['', ''], ['', ''], ts),
  /source_parse_rejected/,
);

const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'd4-origin-test-'));
try {
  const files = {
    expectedApp: path.join(temporary, 'expected-App.tsx'),
    expectedTrial: path.join(temporary, 'expected-RlsTrial.tsx'),
    actualApp: path.join(temporary, 'actual-App.tsx'),
    actualTrial: path.join(temporary, 'actual-RlsTrial.tsx'),
  };
  fs.writeFileSync(files.expectedApp, expectedApp);
  fs.writeFileSync(files.expectedTrial, expectedTrial);
  fs.writeFileSync(files.actualApp, expectedApp);
  fs.writeFileSync(files.actualTrial, geminiBlankLine);
  const result = spawnSync(process.execPath, [
    path.join(__dirname, 'verify_d4_origin.cjs'),
    files.expectedApp,
    files.expectedTrial,
    files.actualApp,
    files.actualTrial,
    typescriptDirectory,
  ], {encoding: 'utf8'});
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stderr, '');
  const receipt = JSON.parse(result.stdout);
  assert.deepEqual(Object.keys(receipt).sort(), [
    'actual_digest',
    'actual_node_count',
    'expected_digest',
    'expected_node_count',
    'file_count',
    'verdict',
  ]);
  assert.equal(receipt.verdict, 'equivalent');
  assert.equal(receipt.file_count, 2);

  fs.writeFileSync(
    files.actualTrial,
    expectedTrial.replace('制作側の準備を確認してください。', '制作側へ確認してください。'),
  );
  const different = spawnSync(process.execPath, [
    path.join(__dirname, 'verify_d4_origin.cjs'),
    files.expectedApp,
    files.expectedTrial,
    files.actualApp,
    files.actualTrial,
    typescriptDirectory,
  ], {encoding: 'utf8'});
  assert.equal(different.status, 1);
  assert.equal(JSON.parse(different.stdout).verdict, 'different');
  assert.equal(different.stdout.includes(temporary), false);

  fs.writeFileSync(files.actualTrial, '');
  const invalid = spawnSync(process.execPath, [
    path.join(__dirname, 'verify_d4_origin.cjs'),
    files.expectedApp,
    files.expectedTrial,
    files.actualApp,
    files.actualTrial,
    typescriptDirectory,
  ], {encoding: 'utf8'});
  assert.equal(invalid.status, 2);
  assert.equal(JSON.parse(invalid.stdout).verdict, 'invalid');
  assert.equal(invalid.stdout.includes(temporary), false);
} finally {
  fs.rmSync(temporary, {recursive: true, force: true});
}

console.log('19 D4 origin structure checks passed; no formal isolation claim');
