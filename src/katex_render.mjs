import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const katex = require(path.resolve(process.cwd(), 'frontend/node_modules/katex'));

const payload = fs.readFileSync(0, 'utf8');
const expressions = JSON.parse(payload);

const rendered = expressions.map(({ latex, displayMode }) =>
  katex.renderToString(latex, {
    displayMode: Boolean(displayMode),
    throwOnError: false,
    output: 'html',
    strict: 'ignore',
  })
);

process.stdout.write(JSON.stringify(rendered));
