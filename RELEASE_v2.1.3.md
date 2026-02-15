# ChatRaw v2.1.3

## Highlights

### Mindmap Renderer Plugin
- **Rendering fix**: Correct SVG namespace (`createElementNS`), container layout, Markmap data pipeline
- **Format support**: JSON (title/children, center/branches, root/data), Markdown headings, Mermaid mindmap
- **Download**: Top-right SVG export button (avoids tainted canvas; use PNG converters if needed)

### Enhanced Export Plugin
- Export button now displays correctly (sync injection + polling fallback)
- Plugin main.js cache: `Cache-Control: no-cache` for fresh updates

### Voice Input Plugin
- Web Speech API for speech-to-text in the input toolbar

### Plugin Market & UI
- 2-column grid layout, search bar
- Info popover for plugin details
- Compact toggle switches (36×20)
- Wider settings modals
- Local install: drag-and-drop zip upload

### Developer Docs
- Mindmap renderer example (MutationObserver, SVG export, createElementNS)
- index.json registration for plugin market

## Docker

```bash
docker pull massif01/chatraw:v2.1.3
# or
docker pull massif01/chatraw:latest
```

**Platforms**: linux/amd64, linux/arm64
