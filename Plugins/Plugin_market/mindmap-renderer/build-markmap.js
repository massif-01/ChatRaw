/**
 * Build markmap-bundle.min.js for mindmap-renderer plugin
 * Bundles markmap-lib (Transformer) + markmap-view (Markmap) into a single IIFE
 * Output: lib/markmap-bundle.min.js, exposes window.markmap = { Transformer, Markmap }
 */
const esbuild = require('esbuild');
const path = require('path');
const fs = require('fs');

const PLUGIN_DIR = path.join(__dirname);
const LIB_DIR = path.join(PLUGIN_DIR, 'lib');
const OUT_FILE = path.join(LIB_DIR, 'markmap-bundle.min.js');

// Entry: create a virtual module that imports and re-exports
const entryContent = `
import { Transformer } from 'markmap-lib/no-plugins';
import { Markmap, loadCSS, loadJS } from 'markmap-view';

// Expose to window for plugin use
(typeof window !== 'undefined' ? window : globalThis).markmap = {
  Transformer,
  Markmap,
  loadCSS,
  loadJS
};
`;

const entryPath = path.join(PLUGIN_DIR, '_markmap-entry.mjs');
fs.writeFileSync(entryPath, entryContent);

async function build() {
  if (!fs.existsSync(LIB_DIR)) {
    fs.mkdirSync(LIB_DIR, { recursive: true });
  }

  try {
    await esbuild.build({
      entryPoints: [entryPath],
      bundle: true,
      format: 'iife',
      globalName: 'markmapBundle',
      outfile: OUT_FILE,
      minify: true,
      sourcemap: false,
      target: ['es2020'],
      platform: 'browser',
      define: {
        'process.env.NODE_ENV': '"production"'
      }
    });
    console.log('Built:', OUT_FILE);
  } finally {
    try { fs.unlinkSync(entryPath); } catch (_) {}
  }
}

build().catch(err => {
  console.error('Build failed:', err);
  process.exit(1);
});
