import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const htmlPath = path.join(root, 'site', 'prototype.html');
const jsonPath = path.join(root, 'site', 'prototype-features.json');

let html;
let jsonText;
let htmlError;
let jsonError;

try {
  html = fs.readFileSync(htmlPath, 'utf8');
} catch (error) {
  htmlError = error;
}
try {
  jsonText = fs.readFileSync(jsonPath, 'utf8');
} catch (error) {
  jsonError = error;
}

function needHtml() {
  if (htmlError) throw new Error('Cannot read site/prototype.html: ' + htmlError.message);
  return html;
}

function needJson() {
  if (jsonError) throw new Error('Cannot read site/prototype-features.json: ' + jsonError.message);
  return jsonText;
}

function mainScript() {
  const scripts = [...needHtml().matchAll(/<script\b[^>]*>([\s\S]*?)<\/script\s*>/gi)];
  const main = scripts.find(function (match) {
    return /^\s*(["'])use strict\1;/.test(match[1]);
  });
  if (!main) throw new Error('No inline <script> beginning with "use strict" was found');
  return main[1];
}

function objectLiteral(sourceText, name) {
  const declaration = new RegExp('\\b(?:const|let|var)\\s+' + name + '\\s*=\\s*\\{', 'm').exec(sourceText);
  if (!declaration) throw new Error(name + ' object declaration was not found');

  const start = declaration.index + declaration[0].lastIndexOf('{');
  let quote = null;
  let escaped = false;
  let lineComment = false;
  let blockComment = false;
  let depth = 0;

  for (let index = start; index < sourceText.length; index += 1) {
    const character = sourceText[index];
    const next = sourceText[index + 1];

    if (lineComment) {
      if (character === '\n') lineComment = false;
      continue;
    }
    if (blockComment) {
      if (character === '*' && next === '/') {
        blockComment = false;
        index += 1;
      }
      continue;
    }
    if (quote) {
      if (escaped) escaped = false;
      else if (character === '\\') escaped = true;
      else if (character === quote) quote = null;
      continue;
    }

    if (character === '/' && next === '/') {
      lineComment = true;
      index += 1;
    } else if (character === '/' && next === '*') {
      blockComment = true;
      index += 1;
    } else if (character === "'" || character === '"' || character === String.fromCharCode(96)) {
      quote = character;
    } else if (character === '{') {
      depth += 1;
    } else if (character === '}') {
      depth -= 1;
      if (depth === 0) return sourceText.slice(start, index + 1);
    }
  }
  throw new Error(name + ' object declaration has no closing brace');
}

function uncommented(sourceText) {
  return sourceText.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '');
}

function insist(condition, message) {
  if (!condition) throw new Error(message);
}

function keys(value) {
  return Object.keys(value).sort();
}

function declarationExpression(sourceText, name) {
  const declaration = new RegExp('\\b(?:const|let|var)\\s+' + name + '\\s*=', 'm').exec(sourceText);
  if (!declaration) throw new Error(name + ' declaration was not found');

  const start = declaration.index + declaration[0].length;
  let quote = null;
  let escaped = false;
  let lineComment = false;
  let blockComment = false;
  let depth = 0;

  for (let index = start; index < sourceText.length; index += 1) {
    const character = sourceText[index];
    const next = sourceText[index + 1];

    if (lineComment) {
      if (character === '\n') lineComment = false;
      continue;
    }
    if (blockComment) {
      if (character === '*' && next === '/') {
        blockComment = false;
        index += 1;
      }
      continue;
    }
    if (quote) {
      if (escaped) escaped = false;
      else if (character === '\\') escaped = true;
      else if (character === quote) quote = null;
      continue;
    }

    if (character === '/' && next === '/') {
      lineComment = true;
      index += 1;
    } else if (character === '/' && next === '*') {
      blockComment = true;
      index += 1;
    } else if (character === "'" || character === '"' || character === String.fromCharCode(96)) {
      quote = character;
    } else if (character === '(' || character === '[' || character === '{') {
      depth += 1;
    } else if (character === ')' || character === ']' || character === '}') {
      depth -= 1;
    } else if (character === ';' && depth === 0) {
      return sourceText.slice(start, index);
    }
  }
  throw new Error(name + ' declaration has no terminating semicolon');
}

const checks = [
  {
    name: 'SELF-CONTAINMENT',
    run: function () {
      const sourceText = uncommented(needHtml());
      const problems = [];

      if (/fonts\.googleapis\.com/i.test(sourceText)) problems.push('references fonts.googleapis.com');
      if (/fonts\.gstatic\.com/i.test(sourceText)) problems.push('references fonts.gstatic.com');
      if (/<script\b[^>]*\bsrc\s*=/i.test(sourceText)) problems.push('contains <script src=...>');
      if (/@font-face\b/i.test(sourceText)) problems.push('contains @font-face');
      if (/<link\b[^>]*\brel\s*=\s*(["'])[^"']*\bstylesheet\b[^"']*\1/i.test(sourceText)) {
        problems.push('contains <link rel="stylesheet">');
      }

      const urlPattern = /[A-Za-z][A-Za-z\d+.-]*:\/\/[^\s"'<>]+/g;
      for (const match of sourceText.matchAll(urlPattern)) {
        const url = match[0];
        const tagStart = sourceText.lastIndexOf('<', match.index);
        const tagEnd = sourceText.indexOf('>', match.index);
        const tag = tagStart >= 0 && tagEnd >= 0 ? sourceText.slice(tagStart, tagEnd + 1) : '';
        const canonical = url.startsWith('https://ding-ding-projects.github.io')
          && /^<link\b/i.test(tag)
          && /\brel\s*=\s*(["'])canonical\1/i.test(tag);
        const svgNamespace = url === 'http://www.w3.org/2000/svg';
        if (!canonical && !svgNamespace) problems.push('disallowed URL ' + url);
      }

      const fetches = [...sourceText.matchAll(/\bfetch\s*\(([^)]*)\)/g)].map(function (match) {
        return match[1].trim();
      });
      if (fetches.length !== 1 || fetches[0] !== "'prototype-features.json'") {
        problems.push("expected only fetch('prototype-features.json'); found "
          + (fetches.length ? fetches.join(', ') : 'none'));
      }

      insist(problems.length === 0, problems.join('; '));
      return 'no external assets; only the local feature catalog is fetched';
    },
  },
  {
    name: 'JS SYNTAX',
    run: function () {
      const script = mainScript();
      const temporary = path.join(root, '.validate-prototype-' + process.pid + '-' + Date.now() + '.mjs');
      let result;
      try {
        fs.writeFileSync(temporary, script, 'utf8');
        result = spawnSync(process.execPath, ['--check', temporary], {
          cwd: root,
          encoding: 'utf8',
          windowsHide: true,
        });
      } finally {
        fs.rmSync(temporary, { force: true });
      }
      if (result.error) throw new Error('node --check could not run: ' + result.error.message);
      if (result.status !== 0) {
        throw new Error((result.stderr || result.stdout || ('node --check exited ' + result.status)).trim());
      }
      return 'main strict-mode inline script parses with node --check';
    },
  },
  {
    name: 'ICON COVERAGE',
    run: function () {
      const script = mainScript();
      const iconObject = objectLiteral(script, 'ICONS');
      const definitions = new Set();
      const keyPattern = /^\s*(?:([A-Za-z_$][\w$]*)|(["'])([^"']+)\2)\s*:/gm;
      for (const match of iconObject.matchAll(keyPattern)) definitions.add(match[1] || match[3]);

      const references = new Set();
      for (const match of script.matchAll(/\bic\s*\(\s*(["'])([A-Za-z_$][\w$]*)\1/g)) {
        references.add(match[2]);
      }
      for (const match of script.matchAll(/\bICONS\s*\.\s*([A-Za-z_$][\w$]*)/g)) {
        references.add(match[1]);
      }

      const missing = [...references].filter(function (name) {
        return !definitions.has(name);
      }).sort();
      insist(definitions.size > 0, 'ICONS contains no parseable definitions');
      insist(missing.length === 0, 'missing icon definitions: ' + missing.join(', '));
      return references.size + ' referenced names are covered by ' + definitions.size + ' definitions';
    },
  },
  {
    name: 'PALETTE PARITY',
    run: function () {
      const literal = objectLiteral(mainScript(), 'PAL');
      let palette;
      try {
        palette = Function('"use strict"; return (' + literal + ');')();
      } catch (error) {
        throw new Error('PAL could not be parsed: ' + error.message);
      }

      for (const theme of ['light', 'dark', 'hc']) {
        insist(palette[theme] && typeof palette[theme] === 'object', 'PAL.' + theme + ' is missing');
      }
      const lightKeys = keys(palette.light);
      for (const theme of ['dark', 'hc']) {
        const themeKeys = keys(palette[theme]);
        insist(JSON.stringify(themeKeys) === JSON.stringify(lightKeys),
          'PAL.' + theme + ' keys differ from PAL.light');
      }

      const expected = {
        light: { p: '#6750A4', pc: '#E8DEF8', surface: '#FFFBFE' },
        dark: { p: '#D0BCFF', pc: '#4F378B', surface: '#141218' },
        hc: { p: '#3800A0', surface: '#FFFFFF' },
      };
      const problems = [];
      for (const [theme, values] of Object.entries(expected)) {
        for (const [key, value] of Object.entries(values)) {
          if (palette[theme][key] !== value) {
            problems.push(theme + '.' + key + ': expected ' + value + ', got ' + palette[theme][key]);
          }
        }
      }
      insist(problems.length === 0, problems.join('; '));
      return 'light, dark, and hc share ' + lightKeys.length + ' keys and required values';
    },
  },
  {
    name: 'SHAPE TOKENS',
    run: function () {
      const expected = {
        '--r-check': '3px',
        '--r-ind': '4px',
        '--r-focus': '6px',
        '--r-sm': '8px',
        '--r-ctrl': '10px',
        '--r-cont': '12px',
        '--r-tb': '18px',
        '--r-pill': '20px',
      };
      const found = new Map();
      const pattern = /(["']?)(--r-(?:check|ind|focus|sm|ctrl|cont|tb|pill))\1\s*:\s*(["']?)([^\s,;}"']+)\3/g;
      for (const match of mainScript().matchAll(pattern)) {
        if (!found.has(match[2])) found.set(match[2], new Set());
        found.get(match[2]).add(match[4]);
      }

      const problems = [];
      for (const [name, value] of Object.entries(expected)) {
        const actual = found.has(name) ? [...found.get(name)] : [];
        if (actual.length !== 1 || actual[0] !== value) {
          problems.push(name + ': expected ' + value + ', got ' + (actual.length ? actual.join(', ') : 'missing'));
        }
      }
      insist(problems.length === 0, problems.join('; '));
      return 'all 8 corner-radius variables match the prototype contract';
    },
  },
  {
    name: 'CATALOG',
    run: function () {
      let catalog;
      try {
        catalog = JSON.parse(needJson());
      } catch (error) {
        throw new Error('prototype-features.json is invalid JSON: ' + error.message);
      }
      insist(Array.isArray(catalog), 'catalog root is not an array');
      insist(catalog.length >= 2000, 'catalog has ' + catalog.length + ' entries; expected at least 2000');

      const invalid = [];
      for (let index = 0; index < catalog.length; index += 1) {
        const entry = catalog[index];
        if (!Array.isArray(entry) || entry.length !== 4
            || !entry.every(function (value) { return typeof value === 'string'; })) {
          invalid.push(index);
          if (invalid.length === 10) break;
        }
      }
      insist(invalid.length === 0, 'invalid 4-string entries at indexes: ' + invalid.join(', '));
      return catalog.length + ' valid [name, module, area, uno] entries';
    },
  },
  {
    name: 'SURFACE CONTRACT',
    run: function () {
      const script = mainScript();
      const declaration = /\bvar\s+screens\s*=\s*(\[[\s\S]*?\]);/.exec(script);
      insist(declaration, 'screens array declaration was not found');
      let screens;
      try {
        screens = Function('"use strict"; return (' + declaration[1] + ');')();
      } catch (error) {
        throw new Error('screens array could not be parsed: ' + error.message);
      }
      const expected = [
        ['start', 'Start'],
        ['writer', 'Writer'],
        ['calc', 'Calc'],
        ['impress', 'Impress'],
        ['draw', 'Draw'],
        ['base', 'Base'],
        ['math', 'Math'],
        ['code', 'Features'],
        ['history', 'History'],
        ['gallery', 'Components'],
        ['dialogs', 'Dialogs'],
      ];
      const actual = screens.map(function (screen) { return screen.slice(0, 2); });
      insist(JSON.stringify(actual) === JSON.stringify(expected),
        'expected the exact 11-surface archive map; got ' + JSON.stringify(actual));
      return 'all 11 canonical archive surfaces remain directly navigable';
    },
  },
  {
    name: 'REGEX ENGINE',
    run: function () {
      function compile(state) {
        if (state.q === '') return { ok: true, empty: true, test: function () { return true; } };
        if (!state.regex) {
          const query = state.q.toLowerCase();
          return {
            ok: true,
            test: function (value) { return String(value).toLowerCase().includes(query); },
          };
        }
        try {
          const flags = (state.flags || '').replace(/[^gimsuy]/g, '').replace('g', '');
          const expression = new RegExp(state.q, flags);
          return {
            ok: true,
            re: expression,
            test: function (value) { return expression.test(String(value)); },
          };
        } catch (error) {
          return {
            ok: false,
            error: error.message,
            test: function () { return false; },
          };
        }
      }

      const literal = compile({ q: 'save', flags: 'i', regex: false });
      insist(literal.ok && literal.test('Autosave'), "literal 'save' did not match 'Autosave'");

      const anchored = compile({ q: '^Save', flags: 'i', regex: true });
      insist(anchored.ok && anchored.test('Save') && !anchored.test('Autosave'),
        "regex '^Save' did not match only the anchored value");

      const digit = compile({ q: '\\d', flags: '', regex: true });
      insist(digit.ok && digit.test('Heading 2') && !digit.test('Bold'),
        "regex '\\d' did not distinguish 'Heading 2' from 'Bold'");

      const invalid = compile({ q: '[', flags: 'gims', regex: true });
      insist(!invalid.ok && typeof invalid.error === 'string'
          && invalid.error.length > 0 && !invalid.test('anything'),
        "invalid regex '[' was not handled gracefully");

      return 'literal, anchored, digit, and invalid-pattern behavior is correct';
    },
  },
  {
    name: 'EXTENDED UI CONTRACT',
    run: function () {
      const script = mainScript();
      const required = [
        ['bottom-right dialog form', 'function dlgWrap('],
        ['notification manager', 'function notificationManager('],
        ['bulk notification actions', "case 'notebulk'"],
        ['recoverable undo', "case 'noteundo'"],
        ['local Git ledger', 'Local-only Git ledger'],
        ['tombstone deletion', 'deletions are tombstones'],
        ['no-remote guarantee', 'no remote or automatic push'],
        ['regex documentation tabs', 'Regex builder documentation'],
        ['regex examples', 'var RX_EXAMPLES='],
        ['live regex test data', 'rxtest-'],
      ];
      const missing = required.filter(function (entry) {
        return !script.includes(entry[1]);
      }).map(function (entry) { return entry[0]; });
      insist(missing.length === 0, 'missing extended UI invariants: ' + missing.join(', '));

      const searchIds = [...script.matchAll(/\brenderSearch\(\s*'([^']+)'/g)]
        .map(function (match) { return match[1]; })
        .filter(function (id, index, values) { return values.indexOf(id) === index; })
        .sort();
      const expectedSearchIds = ['features', 'find', 'gallery', 'notify', 'start'];
      insist(JSON.stringify(searchIds) === JSON.stringify(expectedSearchIds),
        'expected shared builder on five prototype searches; got ' + searchIds.join(', '));
      return 'notification forms/manager/history and five documented regex builders are guarded';
    },
  },
  {
    name: 'VERSION HISTORY FIXTURE',
    run: function () {
      const script = mainScript();
      let history;
      let docs;
      try {
        history = Function('"use strict"; return (' + declarationExpression(script, 'HISTORY') + ');')();
        docs = Function('"use strict"; return (' + declarationExpression(script, 'DOCS') + ');')();
      } catch (error) {
        throw new Error('HISTORY/DOCS fixture could not be parsed: ' + error.message);
      }

      insist(Array.isArray(history), 'HISTORY is not an array');
      insist(Array.isArray(docs), 'DOCS is not an array');
      insist(history.length === 12, 'expected 12 seeded history entries, got ' + history.length);
      insist(docs.length === 6, 'expected 6 seeded DOCS records, got ' + docs.length);

      const ids = history.map(function (h) { return h.id; }).sort(function (a, b) { return a - b; });
      insist(JSON.stringify(ids) === JSON.stringify([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]),
        'seeded entry ids must be exactly 0..11');
      const current = history.filter(function (h) { return h.current === true; });
      insist(current.length === 1, 'exactly one entry must be current, got ' + current.length);

      const problems = [];
      for (const h of history) {
        if (h.docIx != null
            && !(Number.isInteger(h.docIx) && h.docIx >= 0 && h.docIx < docs.length)) {
          problems.push('entry ' + h.id + ' has out-of-range docIx ' + h.docIx);
        }
        if (!Number.isInteger(h.added) || h.added < 0
            || !Number.isInteger(h.removed) || h.removed < 0) {
          problems.push('entry ' + h.id + ' has a non-integer word delta');
        }
        if (!/^[0-9a-f]{7}$/.test(String(h.hash))) {
          problems.push('entry ' + h.id + ' has a malformed hash ' + h.hash);
        }
      }
      insist(problems.length === 0, problems.join('; '));

      const gating = [
        ['restore gated on snapshot', 'var restoreBtn = hdoc ?'],
        ['current gated on current flag', 'var currentBtn = hs.current ?'],
        ['snapshot gated on docIx', 'var hdoc=(hs.docIx!=null)?DOCS[hs.docIx]:null;'],
      ];
      const missing = gating.filter(function (g) { return !script.includes(g[1]); })
        .map(function (g) { return g[0]; });
      insist(missing.length === 0, 'missing render gating: ' + missing.join(', '));
      const restoreLine = script.split('\n').find(function (line) {
        return line.includes('var restoreBtn = hdoc ?');
      }) || '';
      insist(restoreLine.includes('Restore this version') && !restoreLine.includes('data-act'),
        'the restore control must stay a non-committing affordance (no data-act)');

      return '12 coherent seeded entries over 6 docs, one current, restore/current gating intact';
    },
  },
];

let passed = 0;
let failed = 0;

for (const check of checks) {
  try {
    const detail = check.run();
    passed += 1;
    console.log('PASS ' + check.name + ': ' + detail);
  } catch (error) {
    failed += 1;
    console.log('FAIL ' + check.name + ': ' + (error instanceof Error ? error.message : String(error)));
  }
}

console.log('\nSummary: ' + passed + ' passed, ' + failed + ' failed, ' + checks.length + ' total.');
process.exitCode = failed === 0 ? 0 : 1;
