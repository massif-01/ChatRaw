import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const vendor = 'backend/static/vendor';
const assets = {
    'alpinejs/3.13.3/alpine.min.js': 'alpinejs/dist/cdn.min.js',
    'collapse/3.13.3/collapse.min.js': '@alpinejs/collapse/dist/cdn.min.js',
    'marked/9.1.6/marked.min.js': 'marked/marked.min.js',
    'highlight/11.9.0/highlight.min.js': '@highlightjs/cdn-assets/highlight.min.js',
    'highlight/11.9.0/github-dark.min.css': '@highlightjs/cdn-assets/styles/github-dark.min.css',
    'papaparse/5.4.1/papaparse.min.js': 'papaparse/papaparse.min.js',
    'licenses/marked.md': 'marked/LICENSE.md',
    'licenses/highlight.txt': '@highlightjs/cdn-assets/LICENSE',
    'licenses/papaparse.txt': 'papaparse/LICENSE',
};

for (const [destination, source] of Object.entries(assets)) {
    const output = resolve(root, vendor, destination);
    const original = await readFile(resolve(root, 'node_modules', source));
    if (process.argv.includes('--write')) {
        await mkdir(dirname(output), { recursive: true });
        await writeFile(output, original);
    } else {
        assert.ok(original.equals(await readFile(output)), `Vendored bytes differ from the lockfile package: ${destination}`);
    }
}

const checksumFile = await readFile(resolve(root, vendor, 'SHA256SUMS'), 'utf8');
for (const line of checksumFile.trimEnd().split('\n')) {
    const [expected, file] = line.split('  ');
    const actual = createHash('sha256').update(await readFile(resolve(root, file))).digest('hex');
    assert.equal(actual, expected, `SHA-256 mismatch: ${file}`);
}
console.log('Frontend vendor assets verified.');
