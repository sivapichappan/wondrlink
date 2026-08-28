/**
 * Regression check for lib/answer-text.ts.
 *
 * The mobile app has no test runner, and adding one means new devDependencies
 * and a lockfile rewrite — which is exactly what broke EAS bundling once
 * already (babel-preset-expo, build #31). So this is a standalone script: it
 * transpiles the one module with a throwaway esbuild and asserts against it.
 * Nothing here reaches the app bundle or package.json.
 *
 * These two functions are load-bearing. `toPlainText` produces what a patient
 * pastes into a message or hands to their oncologist, and `splitAnswer` decides
 * how every answer is laid out — including every answer already in the database,
 * none of which has a single heading in it.
 *
 *   cd mobile && node scripts/check-answer-text.mjs
 */

import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, '..', 'lib', 'answer-text.ts');
const out = mkdtempSync(join(tmpdir(), 'answer-text-'));
const bundle = join(out, 'answer-text.mjs');

try {
  execFileSync(
    'npx',
    ['--yes', 'esbuild', src, '--format=esm', `--outfile=${bundle}`, '--log-level=error'],
    { stdio: ['ignore', 'ignore', 'inherit'] },
  );
} catch {
  console.error('Could not transpile answer-text.ts (needs network for npx esbuild).');
  process.exit(1);
}

const { toPlainText, splitAnswer, stripEmoji } = await import(pathToFileURL(bundle).href);

let passed = 0;
const check = (name, fn) => {
  fn();
  passed += 1;
  console.log('  ok', name);
};

console.log('toPlainText');
check('strips heading hashes but keeps the words', () => {
  assert.equal(toPlainText('## When to call your team'), 'When to call your team');
});
check('strips bold and italic', () => {
  assert.equal(toPlainText('**Hot flashes** are *common*.'), 'Hot flashes are common.');
});
check('leaves citation markers alone', () => {
  // [1] is the answer's evidence, and whoever is showing this to a clinician
  // wants it. It is also not a link, so the link rule must not touch it.
  assert.equal(toPlainText('Letrozole lowers estrogen [1].'), 'Letrozole lowers estrogen [1].');
});
check('leaves snake_case and multiplication alone', () => {
  assert.equal(toPlainText('use max_tokens and 5 * 3 here'), 'use max_tokens and 5 * 3 here');
});
check('turns a link into label plus url', () => {
  assert.equal(
    toPlainText('See [the trial finder](https://example.org/x).'),
    'See the trial finder (https://example.org/x).',
  );
});
check('keeps bullets and their indentation', () => {
  // A blanket whitespace sweep here would flatten a nested list into a set of
  // unrelated points. Same mistake that flattened the prompt files.
  assert.equal(toPlainText('- top level\n    - nested item'), '- top level\n    - nested item');
});
check('collapses runs of blank lines to one', () => {
  assert.equal(toPlainText('a\n\n\n\nb'), 'a\n\nb');
});
check('strips inline code ticks', () => {
  assert.equal(toPlainText('run `npm test` now'), 'run npm test now');
});
check('empty in, empty out', () => {
  assert.equal(toPlainText(''), '');
});

console.log('splitAnswer');
check('no headings means all lead and no sections', () => {
  // EVERY answer already stored in `messages` looks like this. The card must
  // render them exactly as it does today.
  const r = splitAnswer('Just a plain paragraph answer.');
  assert.equal(r.lead, 'Just a plain paragraph answer.');
  assert.deepEqual(r.sections, []);
});
check('a stray hash that is not a heading changes nothing', () => {
  const r = splitAnswer('Cost is about $40 # per cycle.');
  assert.equal(r.sections.length, 0);
  assert.ok(r.lead.includes('$40'));
});
check('splits lead from labelled sections', () => {
  const md = [
    'Letrozole lowers the estrogen that feeds your cancer.',
    '',
    '## What to expect',
    'Hot flashes and joint stiffness are the two most common.',
    '',
    '## When to call your team',
    '- Pain that wakes you at night',
    '- A new lump anywhere',
  ].join('\n');
  const r = splitAnswer(md);
  assert.equal(r.lead, 'Letrozole lowers the estrogen that feeds your cancer.');
  assert.equal(r.sections.length, 2);
  assert.equal(r.sections[0].label, 'What to expect');
  assert.equal(r.sections[1].label, 'When to call your team');
  assert.ok(r.sections[1].body.startsWith('- Pain'));
});
check('a truncated dangling label folds into the previous body', () => {
  // max_tokens is a hard cut. Degrading to a slightly odd sentence beats
  // rendering a heading that points at blank space.
  const r = splitAnswer('Lead.\n\n## Real section\nSome content.\n\n## Cut off here');
  assert.equal(r.sections.length, 1);
  assert.ok(r.sections[0].body.includes('Cut off here'));
});
check('a dangling label with no prior section folds into the lead', () => {
  const r = splitAnswer('Lead sentence.\n\n## Cut off');
  assert.equal(r.sections.length, 0);
  assert.ok(r.lead.includes('Cut off'));
});
check('an answer that opens with a heading has an empty lead', () => {
  const r = splitAnswer('## First thing\nBody text.');
  assert.equal(r.lead, '');
  assert.equal(r.sections.length, 1);
});
check('a sub-heading inside a section stays in the body', () => {
  const r = splitAnswer('Lead.\n\n## Section\n### Sub\nBody.');
  assert.equal(r.sections.length, 1);
  assert.ok(r.sections[0].body.includes('### Sub'));
});

rmSync(out, { recursive: true, force: true });
console.log('\nstripEmoji');

check('the emergency siren goes, the word EMERGENCY stays', () => {
  // The highest-stakes string the product sends. The backend injects the
  // pictograph (lib/llm_utils.py); the words carry the meaning and the
  // designed escalation card carries the urgency.
  assert.equal(
    stripEmoji('🚨 EMERGENCY: Fever during chemotherapy needs same-day care.'),
    'EMERGENCY: Fever during chemotherapy needs same-day care.',
  );
});

check('a warning emoji mid-paragraph leaves no double space', () => {
  assert.equal(stripEmoji('Hot flashes 💊 are common.'), 'Hot flashes are common.');
});

check('an emoji opening a line does not eat the newline', () => {
  assert.equal(
    stripEmoji('\n\n⚠️ If you notice this, call your team.'),
    '\n\nIf you notice this, call your team.',
  );
});

check('INDENTATION SURVIVES', () => {
  // The whole reason the emoji and its trailing spaces are consumed in one
  // match. A separate leading-whitespace tidy is what flattened the nested
  // examples in the prompt files, and it would do the same to a bullet list.
  assert.equal(
    stripEmoji('- top\n    - nested item\n        - deeper'),
    '- top\n    - nested item\n        - deeper',
  );
});

check('clean text is returned untouched', () => {
  const clean = '## What to expect\nEndocrine therapy lowers estrogen [1].';
  assert.equal(stripEmoji(clean), clean);
});

check('citation markers are never touched', () => {
  assert.equal(stripEmoji('Confirmed [1, 3].'), 'Confirmed [1, 3].');
});

check('empty string is safe', () => {
  assert.equal(stripEmoji(''), '');
});

check('the rendered answer path strips it too', () => {
  // splitAnswer feeds the card the patient actually reads.
  const r = splitAnswer('🚨 EMERGENCY: call now.\n\n## What to do\n- 💊 Take nothing new');
  assert.ok(!r.lead.includes('🚨'), 'lead still has an emoji');
  assert.ok(!r.sections[0].body.includes('💊'), 'section body still has an emoji');
  assert.ok(r.lead.startsWith('EMERGENCY:'));
});

console.log(`\n${passed} assertions passed`);
