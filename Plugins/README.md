# ChatRaw Plugin Development Guide

[English](#english) | [中文](#中文)

---

<a name="english"></a>
## English

### Overview

ChatRaw plugins extend the functionality of the application through a lightweight JavaScript-based architecture. Plugins run in the browser and can interact with the backend through a secure proxy API.

### Plugin Structure

A plugin consists of a folder with the following files:

```
your-plugin/
├── manifest.json    # Plugin metadata (required)
├── icon.png         # Plugin icon, 128x128px (required)
├── main.js          # Plugin code (required)
└── lib/             # Local dependencies (optional)
    ├── library.min.js
    └── library.min.css
```

**Local Dependencies (lib/ directory)**: For fully offline plugins, you can bundle dependencies locally instead of loading from CDN. Files in the `lib/` directory are served via `/api/plugins/{plugin_id}/lib/{filename}`. Subdirectories are supported (e.g., `lib/fonts/`).

### manifest.json

```json
{
  "id": "your-plugin-id",
  "version": "1.0.0",
  "name": {
    "en": "Your Plugin Name",
    "zh": "你的插件名称"
  },
  "description": {
    "en": "Brief description of your plugin",
    "zh": "插件的简短描述"
  },
  "author": "Your Name",
  "homepage": "https://github.com/your-repo",
  "icon": "icon.png",
  "main": "main.js",
  "type": "document_parser",
  "hooks": ["parse_document"],
  "fileTypes": [".xlsx", ".xls"],
  "dependencies": {
    "library-name": "https://cdn.example.com/library.min.js"
  },
  "settings": [
    {
      "id": "settingId",
      "type": "select",
      "options": ["option1", "option2"],
      "default": "option1",
      "label": {
        "en": "Setting Label",
        "zh": "设置标签"
      }
    }
  ],
  "customSettings": false,
  "proxy": [
    {
      "id": "service-name",
      "name": { "en": "Service Name", "zh": "服务名称" },
      "description": { "en": "API key for service", "zh": "服务的 API 密钥" }
    }
  ]
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique plugin identifier (lowercase, hyphens allowed) |
| `version` | string | Yes | Semantic version (e.g., "1.0.0") |
| `name` | object | Yes | Plugin name in multiple languages |
| `description` | object | Yes | Plugin description in multiple languages |
| `author` | string | Yes | Author name |
| `homepage` | string | No | Project homepage URL |
| `icon` | string | Yes | Icon filename (128x128 PNG, will be displayed with rounded corners) |
| `main` | string | Yes | Main JavaScript file |
| `type` | string | Yes | Plugin type (see below) |
| `hooks` | array | Yes | List of hooks the plugin uses |
| `fileTypes` | array | No | File extensions for document_parser type. When plugin is enabled, these extensions are automatically added to the file upload dialog. |
| `dependencies` | object | No | External JS libraries (name: CDN URL) |
| `settings` | array | No | Plugin settings schema (for standard settings UI) |
| `customSettings` | boolean | No | Set to `true` for custom settings UI |
| `proxy` | array | No | External API services requiring API keys |

### Plugin Types

| Type | Description | Available Hooks |
|------|-------------|-----------------|
| `document_parser` | Parse document files | `parse_document` |
| `url_parser` | Parse web page URL to content | `parse_url`, `custom_settings` |
| `search_provider` | Web search service | `web_search`, `before_send` |
| `rag_enhancer` | Enhance RAG pipeline | `pre_embedding`, `post_retrieval`, `before_send`, `custom_settings` |
| `ui_extension` | Add UI elements | `toolbar_button`, `custom_action` |
| `message_processor` | Process messages | `before_send`, `after_receive`, `transform_input`, `transform_output` |
| `model_manager` | Manage multiple model configs | `custom_settings` |

### Available Hooks

| Hook | Description | Arguments | Return |
|------|-------------|-----------|--------|
| `parse_document` | Parse uploaded files | `(file, settings)` | `{ success, content }` |
| `parse_url` | Parse web page URL to content | `(url, html, settings)` — `html` is set in browser mode, `null` in API mode | `{ success, title?, content?, error? }` |
| `web_search` | Web search provider | `(query, settings)` | `{ success, results }` |
| `pre_embedding` | Before text embedding | `(text, settings)` | `{ success, text }` |
| `post_retrieval` | After RAG retrieval | `(results, settings)` | `{ success, results }` |
| `before_send` | Before sending message | `(body)` | `{ success, body }` |
| `after_receive` | After receiving response | `(message)` | `{ success, content }` |
| `transform_input` | Transform user input | `(message)` | `{ success, content }` |
| `transform_output` | Transform AI output | `(content)` | `{ success, content }` |
| `toolbar_button` | Add toolbar button | `(context)` | `{ icon, label, onClick }` |
| `file_preview` | Custom file preview | `(file)` | `{ success, html }` |
| `custom_action` | Custom action handler | `(action, data)` | `{ success, result }` |
| `custom_settings` | Custom settings UI | - | - |

### Settings Types

For standard settings UI (`customSettings: false`):

| Type | Description | Example |
|------|-------------|---------|
| `boolean` | Toggle switch | `{ "type": "boolean", "default": true }` |
| `string` | Text input | `{ "type": "string", "default": "" }` |
| `number` | Number input | `{ "type": "number", "default": 10, "min": 1, "max": 100 }` |
| `select` | Dropdown | `{ "type": "select", "options": ["a", "b"], "default": "a" }` |
| `password` | Password input | `{ "type": "password", "default": "" }` |

### Custom Settings UI

For complex plugins that need full control over settings UI, use `customSettings: true`.

**Scrollable Content with Fixed Footer**: If your settings UI has long content, use this structure:

```html
<div style="display:flex; flex-direction:column; height:100%; max-height:70vh;">
    <div style="flex:1; min-height:0; overflow-y:auto;">
        <!-- Your scrollable settings content -->
    </div>
    <div style="flex-shrink:0; padding:16px 24px; border-top:1px solid var(--border-color);">
        <!-- Cancel/Save buttons (fixed at bottom) -->
    </div>
</div>
```

> **Key**: `min-height:0` on the scrollable container is required - without it, flex children won't shrink below their content size and scrolling won't work.

**manifest.json:**
```json
{
  "hooks": ["before_send", "custom_settings"],
  "customSettings": true,
  "proxy": [
    {
      "id": "my-service",
      "name": { "en": "API Key", "zh": "API 密钥" }
    }
  ]
}
```

**main.js:**
```javascript
(function(ChatRaw) {
    'use strict';
    
    const PLUGIN_ID = 'my-plugin';
    const SERVICE_ID = 'my-service';
    
    // i18n support
    const i18n = {
        en: {
            apiKeyLabel: 'API Key',
            verify: 'Verify',
            verifying: 'Verifying...',
            verifySuccess: 'API Key is valid!',
            verifyFailed: 'Verification failed',
            save: 'Save',
            cancel: 'Cancel',
            settingsSaved: 'Settings saved'
        },
        zh: {
            apiKeyLabel: 'API 密钥',
            verify: '验证',
            verifying: '验证中...',
            verifySuccess: 'API Key 有效！',
            verifyFailed: '验证失败',
            save: '保存',
            cancel: '取消',
            settingsSaved: '设置已保存'
        }
    };
    
    function t(key) {
        const lang = ChatRaw.utils?.getLanguage?.() || 'en';
        return i18n[lang]?.[key] || i18n.en[key] || key;
    }
    
    // Plugin settings (local state)
    let pluginSettings = { option1: 'default' };
    
    // Load settings from backend
    async function loadSettings() {
        try {
            const res = await fetch('/api/plugins');
            if (res.ok) {
                const plugins = await res.json();
                const plugin = plugins.find(p => p.id === PLUGIN_ID);
                if (plugin?.settings_values) {
                    pluginSettings = { ...pluginSettings, ...plugin.settings_values };
                }
            }
        } catch (e) {
            console.error('Failed to load settings:', e);
        }
    }
    
    // Save settings to backend
    async function saveSettings() {
        try {
            const res = await fetch(`/api/plugins/${PLUGIN_ID}/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ settings: pluginSettings })
            });
            if (res.ok) {
                ChatRaw.utils?.showToast?.(t('settingsSaved'), 'success');
                return true;
            }
            return false;
        } catch (e) {
            return false;
        }
    }
    
    // Save API key
    async function saveApiKey(apiKey) {
        const res = await fetch('/api/plugins/api-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ service_id: SERVICE_ID, api_key: apiKey })
        });
        return res.ok;
    }
    
    // Check if API key is set
    async function checkApiKeyStatus() {
        try {
            const res = await fetch('/api/plugins/api-keys');
            if (res.ok) {
                const data = await res.json();
                return !!data.api_keys?.[SERVICE_ID];
            }
        } catch (e) {}
        return false;
    }
    
    // Verify API key by making a test request
    async function verifyApiKey(apiKey) {
        await saveApiKey(apiKey);
        
        const result = await ChatRaw.proxy.request({
            serviceId: SERVICE_ID,
            url: 'https://api.example.com/test',
            method: 'POST',
            body: { test: true }
        });
        
        if (result.success) {
            return { success: true };
        } else {
            await saveApiKey(''); // Clear invalid key
            return { success: false, error: result.error };
        }
    }
    
    // Create settings UI HTML
    function createSettingsUI() {
        return `
            <div style="padding:0;">
                <div style="padding:20px 24px; border-bottom:1px solid var(--border-color);">
                    <h3 style="margin:0 0 16px 0;">${t('apiKeyLabel')}</h3>
                    <div style="display:flex; gap:12px;">
                        <input type="password" id="my-api-key" class="input-minimal" 
                            style="flex:1; padding:10px;">
                        <button id="my-verify-btn" class="btn-primary" 
                            onclick="window._myPlugin.verifyApiKey()"
                            style="padding:10px 20px;">
                            ${t('verify')}
                        </button>
                    </div>
                    <div id="my-api-status" style="margin-top:10px;"></div>
                </div>
                
                <div style="display:flex; justify-content:flex-end; gap:12px; padding:16px 24px;">
                    <button class="btn-secondary" onclick="window._myPlugin.closeSettings()">
                        ${t('cancel')}
                    </button>
                    <button class="btn-primary" onclick="window._myPlugin.saveAllSettings()">
                        ${t('save')}
                    </button>
                </div>
            </div>
        `;
    }
    
    // Close settings modal
    function closeSettings() {
        const app = document.querySelector('[x-data]');
        if (app?._x_dataStack) {
            app._x_dataStack[0].showPluginSettings = false;
        }
    }
    
    // Save and close
    async function saveAllSettings() {
        const success = await saveSettings();
        if (success) {
            closeSettings();
        }
    }
    
    // Global API for UI event handlers
    window._myPlugin = {
        verifyApiKey: async () => {
            const input = document.getElementById('my-api-key');
            const btn = document.getElementById('my-verify-btn');
            const status = document.getElementById('my-api-status');
            
            if (!input?.value.trim()) return;
            
            btn.textContent = t('verifying');
            const result = await verifyApiKey(input.value.trim());
            
            if (result.success) {
                status.innerHTML = `<span style="color:var(--success-color);">✓ ${t('verifySuccess')}</span>`;
                input.value = '';
            } else {
                status.innerHTML = `<span style="color:var(--error-color);">✗ ${t('verifyFailed')}</span>`;
            }
            btn.textContent = t('verify');
        },
        closeSettings,
        saveAllSettings
    };
    
    // Inject UI when settings modal opens
    function setupSettingsListener() {
        window.addEventListener('plugin-settings-open', async (event) => {
            if (event.detail?.pluginId === PLUGIN_ID) {
                await loadSettings();
                setTimeout(() => {
                    const container = document.getElementById('plugin-custom-settings-area');
                    if (container) {
                        container.innerHTML = createSettingsUI();
                    }
                }, 100);
            }
        });
    }
    
    // Initialize
    loadSettings();
    setupSettingsListener();
    
})(window.ChatRawPlugin);
```

### Proxy API (for external services)

To protect API keys, use the proxy API for external service calls:

#### JSON Request Proxy

```javascript
const response = await ChatRaw.proxy.request({
    serviceId: 'your-service',  // Must match proxy.id in manifest
    url: 'https://api.example.com/endpoint',
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: { query: 'search term' }
});
```

#### File Upload Proxy

For services that require file uploads (e.g., Whisper, OCR):

```javascript
const response = await ChatRaw.proxy.upload(
    file,           // File object
    'whisper',      // service_id for API key lookup
    'https://api.openai.com/v1/audio/transcriptions',
    { model: 'whisper-1' },  // extra form fields
    'file'          // file field name (default: 'file')
);
```

The API key is stored securely on the backend and automatically added to requests.

### Utils API

Helper functions for plugin developers:

```javascript
// Load external script
await ChatRaw.utils.loadScript('https://cdn.example.com/lib.js');

// Show toast notification
ChatRaw.utils.showToast('Operation completed', 'success');

// Get current language ('en' or 'zh')
const lang = ChatRaw.utils.getLanguage();

// Translate key
const text = ChatRaw.utils.t('settings');

// Show progress indicator
ChatRaw.utils.showProgress(50, 'Processing...');

// Hide progress indicator
ChatRaw.utils.hideProgress();

// Get current chat ID
const chatId = ChatRaw.utils.getCurrentChatId();

// Get current messages
const messages = ChatRaw.utils.getMessages();

// Add a message to display
ChatRaw.utils.addMessage('assistant', 'Hello from plugin!');
```

### Toolbar Button Extension API

Plugins can add custom buttons to the input toolbar using the `ChatRawPlugin.ui` API. Buttons support active and loading states, and plugins can open a fullscreen modal for complex interactions.

#### Register a Toolbar Button

> **Important**: Toolbar buttons must be registered **immediately when your plugin script loads** (inside your IIFE), not inside a hook callback. The plugin context (`_currentLoadingPlugin`) is only available during script execution.

```javascript
ChatRawPlugin.ui.registerToolbarButton({
    id: 'my-button',           // Required: unique button ID within your plugin
    icon: 'ri-search-line',    // Required: RemixIcon class (must start with ri-)
    label: {                   // Required: multi-language tooltip
        en: 'Search',
        zh: '搜索'
    },
    onClick: async (button) => {  // Required: click handler
        // button contains current state: { id, active, loading, ... }
        console.log('Button clicked!');
    },
    order: 10                  // Optional: sort order (default: 100, lower = first)
});
```

**Icon Requirements**: All button icons **must** use [RemixIcon](https://remixicon.com/) (format: `ri-xxx-line` or `ri-xxx-fill`). Invalid icons will cause registration to fail.

#### Set Button State

```javascript
// Set active state (e.g., feature is enabled)
ChatRawPlugin.ui.setButtonState('my-button', { active: true });

// Set loading state (e.g., processing)
ChatRawPlugin.ui.setButtonState('my-button', { loading: true });

// Set multiple states at once
ChatRawPlugin.ui.setButtonState('my-button', { active: true, loading: false });

// Reset all states
ChatRawPlugin.ui.setButtonState('my-button', { active: false, loading: false });
```

#### Unregister a Button

```javascript
// Remove a button (usually not needed, automatic on plugin disable)
ChatRawPlugin.ui.unregisterToolbarButton('my-button');
```

#### Open Fullscreen Modal

```javascript
// Open a fullscreen modal with custom HTML content
ChatRawPlugin.ui.openFullscreenModal({
    content: `
        <div style="padding: 40px; text-align: center;">
            <h2>My Plugin</h2>
            <p>This is a fullscreen modal!</p>
            <button onclick="ChatRawPlugin.ui.closeFullscreenModal()" 
                    class="btn-primary" style="margin-top: 20px;">
                Close
            </button>
        </div>
    `,
    closable: true,           // Optional: allow ESC/background click to close (default: true)
    onClose: () => {          // Optional: callback when modal closes
        console.log('Modal closed');
    }
});

// Simple usage with just HTML string
ChatRawPlugin.ui.openFullscreenModal('<div>Simple content</div>');
```

#### Close Fullscreen Modal

```javascript
ChatRawPlugin.ui.closeFullscreenModal();
```

#### Button Overflow

When more than 5 plugin buttons are registered, additional buttons are automatically moved to a "More" dropdown menu.

#### Lifecycle Management

When a plugin is disabled or uninstalled:
- All toolbar buttons registered by that plugin are automatically removed
- If the plugin has an open fullscreen modal, it is automatically closed

#### Complete Example

```javascript
(function(ChatRaw) {
    'use strict';
    
    const PLUGIN_ID = 'demo-plugin';
    
    // Track toggle state
    let isEnabled = false;
    
    // Register a toggle button
    ChatRaw.ui.registerToolbarButton({
        id: 'toggle-feature',
        icon: 'ri-toggle-line',
        label: { en: 'Toggle Feature', zh: '切换功能' },
        order: 50,
        onClick: async (btn) => {
            isEnabled = !isEnabled;
            ChatRaw.ui.setButtonState('toggle-feature', { active: isEnabled }, PLUGIN_ID);
            ChatRaw.utils.showToast(isEnabled ? 'Feature enabled' : 'Feature disabled');
        }
    });
    
    // Register a button that opens a modal
    ChatRaw.ui.registerToolbarButton({
        id: 'open-panel',
        icon: 'ri-window-line',
        label: { en: 'Open Panel', zh: '打开面板' },
        order: 60,
        onClick: async (btn) => {
            ChatRaw.ui.openFullscreenModal({
                content: `
                    <div style="padding:40px; max-width:600px; margin:0 auto;">
                        <h2 style="margin-bottom:20px;">Plugin Panel</h2>
                        <p>Configure your plugin settings here.</p>
                        <button onclick="ChatRawPlugin.ui.closeFullscreenModal()" 
                                class="btn-primary" style="margin-top:20px;">
                            Close
                        </button>
                    </div>
                `,
                closable: true
            });
        }
    });
    
})(window.ChatRawPlugin);
```

### Storage API

Plugin-specific local storage (namespaced, 1MB limit per plugin).

**Important**: When calling storage methods after plugin initialization (e.g., in button click handlers, settings UI), you must pass `pluginId` as the last argument:

```javascript
const PLUGIN_ID = 'my-plugin';

// Store data - pass pluginId as third argument
ChatRaw.storage.set('lastUsed', Date.now(), PLUGIN_ID);
ChatRaw.storage.set('preferences', { theme: 'dark' }, PLUGIN_ID);

// Retrieve data - pass pluginId as third argument
const lastUsed = ChatRaw.storage.get('lastUsed', 0, PLUGIN_ID);
const prefs = ChatRaw.storage.get('preferences', {}, PLUGIN_ID);

// Remove data - pass pluginId as second argument
ChatRaw.storage.remove('lastUsed', PLUGIN_ID);

// Clear all plugin storage - pass pluginId as argument
ChatRaw.storage.clear(PLUGIN_ID);

// Get all stored data - pass pluginId as argument
const allData = ChatRaw.storage.getAll(PLUGIN_ID);
```

**Note**: The `pluginId` parameter is optional during plugin initialization (when `_currentLoadingPlugin` is set), but required when called later (e.g., in event handlers).

### Icon Requirements

- Format: PNG
- Size: 128x128 pixels
- The icon will be displayed with iOS-style rounded corners (approximately 22% corner radius)
- Use a transparent or solid background
- Keep the design simple and recognizable at small sizes

### Packaging for Distribution

To distribute your plugin:

1. **Prepare your plugin folder**:
   ```
   your-plugin/
   ├── manifest.json    # Plugin metadata
   ├── icon.png         # 128x128 PNG icon
   └── main.js          # Plugin code
   ```

2. **Create a zip file** (exclude system files):
   ```bash
   # macOS/Linux
   zip -r your-plugin.zip your-plugin/ -x "*.DS_Store" "*__MACOSX*"
   
   # Windows
   # Use File Explorer: Right-click folder → Send to → Compressed (zipped) folder
   ```

3. **Verify your package**:
   - Check zip file size (< 10MB recommended)
   - Extract and verify folder structure
   - Ensure manifest.json is valid JSON
   - Test icon displays correctly (128x128 PNG)

4. **Distribution options**:
   - **Plugin Market**: Submit to `Plugin_market` repository
   - **Local Upload**: Users drag and drop the zip file in plugin settings
   - **Direct Download**: Host on GitHub releases or your website

5. **Common issues**:
   - ❌ Zip contains nested folders: `your-plugin.zip/your-plugin/your-plugin/manifest.json`
   - ✅ Correct structure: `your-plugin.zip/your-plugin/manifest.json`
   - ❌ Files outside plugin folder
   - ✅ All files inside single plugin folder

### Advanced: Local Dependencies and CSS Loading

For plugins that need to work completely offline, you can bundle dependencies in the `lib/` directory.

**Loading CSS files** (the framework only supports JS, CSS must be loaded manually):

```javascript
function loadCSS(url) {
    return new Promise((resolve, reject) => {
        const existing = document.querySelector(`link[href="${url}"]`);
        if (existing) { resolve(); return; }
        
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = url;
        link.onload = resolve;
        link.onerror = reject;
        document.head.appendChild(link);
    });
}

// Usage with local lib
const PLUGIN_ID = 'your-plugin';
await loadCSS(`/api/plugins/${PLUGIN_ID}/lib/styles.min.css`);
```

**Loading local JS dependencies**:

```javascript
async function loadScript(url) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = url;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// Load from lib directory
await loadScript(`/api/plugins/${PLUGIN_ID}/lib/library.min.js`);
```

### Advanced: Using after_receive Hook

The `after_receive` hook allows you to modify AI responses after they are received but before display. This is useful for enhancing rendered content.

```javascript
ChatRawPlugin.hooks.register('after_receive', {
    priority: 10,  // Lower priority = runs later
    
    handler: async (message) => {
        if (!message?.content) {
            return { success: false };  // No modification
        }
        
        let content = message.content;
        
        // Example: Add custom processing
        content = processContent(content);
        
        // Return modified content
        return { success: true, content };
    }
});
```

**Important notes**:
- Return `{ success: false }` if you don't want to modify the content
- Return `{ success: true, content: '...' }` to replace the message content
- The hook receives the full message object including `role`, `content`, `thinking`, etc.
- Multiple plugins can register the same hook; the first one returning `success: true` wins

### Best Practices

1. **Keep it lightweight**: Minimize dependencies and file sizes
2. **Handle errors gracefully**: Always return proper error responses
3. **Support both languages**: Provide both English and Chinese text in i18n
4. **Test thoroughly**: Test with various file sizes and edge cases
5. **Document your plugin**: Include usage instructions in description
6. **API Key verification**: Always provide a "Verify" button for API keys
7. **Save and close**: After successful save, automatically close the settings modal
8. **Persist data properly**: 
   - Use `POST /api/plugins/{id}/settings` to save plugin settings
   - Use `POST /api/plugins/api-key` to save API keys
   - Use `POST /api/models` to save model configurations (for RAG plugins)
9. **Load data on open**: Always reload settings when the settings modal opens
10. **Custom settings listener**: Use `plugin-settings-open` event to inject custom UI
11. **Always `await` async operations**: When calling async functions (like `saveSettings()`) in event handlers, always use `await` to ensure operations complete before proceeding:

```javascript
// ❌ Wrong - data may not be saved
button.onclick = () => {
    saveSettings();  // Missing await!
    renderUI();
};

// ✅ Correct - wait for save to complete
button.onclick = async () => {
    await saveSettings();
    renderUI();
};
```

12. **Choose the right storage method**:

| Storage Method | Location | After Docker Restart | Use Case |
|----------------|----------|---------------------|----------|
| `ChatRaw.storage` | Browser localStorage | **Preserved** (independent of Docker) | Temporary preferences, UI state |
| `POST /api/plugins/{id}/settings` | Server `data/plugins/config.json` | **Preserved** (requires Docker volume) | Core configs, model data |

> **Important**: If your plugin configuration needs to persist across Docker container restarts (with volume mount), you **must** use the backend API `POST /api/plugins/{id}/settings` instead of `ChatRaw.storage`. The localStorage-based Storage API only persists in the user's browser.

13. **Offline plugins with bundled dependencies**:
    - Plugins with `lib/` directory are auto-installed on container startup
    - Online installation only downloads `main.js`, `manifest.json`, `icon.png`
    - The `lib/` directory is automatically copied from the bundled version in Docker image
    - All plugin-related requests are excluded from API rate limiting:
      - Static files: `/lib/`, `/icon`, `/main.js`
      - Plugin metadata: `/api/plugins`, `/api/plugins/*`

14. **Use Shadow DOM for style isolation**:
    - Third-party libraries (like Mermaid) may inject global CSS that pollutes other elements
    - Use Shadow DOM to completely isolate their styles:
    ```javascript
    const shadowHost = document.createElement('div');
    const shadow = shadowHost.attachShadow({ mode: 'closed' });
    shadow.innerHTML = thirdPartyContent;
    container.appendChild(shadowHost);
    ```

15. **Detect message streaming completion**:
    - Use `window.getComputedStyle()` to check typing-indicator visibility
    - Alpine.js `x-show` sets `display: none` when hidden
    ```javascript
    const typingIndicator = msg.querySelector('.typing-indicator');
    if (typingIndicator) {
        const style = window.getComputedStyle(typingIndicator);
        if (style.display !== 'none') {
            // Message is still streaming, wait
            return;
        }
    }
    ```
    - Use content stability detection (debounce ~800ms) to ensure streaming is complete

### Common Pitfalls

Watch out for these common mistakes:

1. **Wrong IIFE pattern**: Always use the parameter-passing pattern for cleaner code:

```javascript
// ❌ Wrong - direct global access
(function() {
    window.ChatRawPlugin.hooks.register(...);
})();

// ✅ Correct - pass as parameter
(function(ChatRaw) {
    if (!ChatRaw || !ChatRaw.hooks) {
        console.error('[YourPlugin] ChatRawPlugin not available');
        return;
    }
    ChatRaw.hooks.register(...);
})(window.ChatRawPlugin);
```

2. **Wrong API method names**: Use the correct method names:

```javascript
// ❌ Wrong - getLang doesn't exist
const lang = ChatRaw.utils?.getLang?.() || 'en';

// ✅ Correct - use getLanguage
const lang = ChatRaw.utils?.getLanguage?.() || 'en';
```

3. **Missing optional chaining**: Always use `?.` for potentially undefined methods:

```javascript
// ❌ Risky - may throw error if utils is undefined
ChatRaw.utils.showToast('Message', 'info');

// ✅ Safe - handles undefined gracefully
ChatRaw.utils?.showToast?.('Message', 'info');
```

4. **Missing safety check**: Always verify ChatRawPlugin is available at startup (see #1 above).

5. **Icon format for toolbar buttons**: Must use RemixIcon format (`ri-xxx-line` or `ri-xxx-fill`):

```javascript
// ❌ Wrong - will be rejected
icon: 'fa-home'        // FontAwesome
icon: 'mdi-home'       // Material Design Icons
icon: 'icon-home'      // Custom class

// ✅ Correct - RemixIcon format
icon: 'ri-home-line'   // Line style
icon: 'ri-home-fill'   // Fill style
```

6. **Registering toolbar buttons in hook callbacks**: Buttons must be registered immediately when the script loads, not inside hooks:

```javascript
// ❌ Wrong - hook callback runs after _currentLoadingPlugin is cleared
ChatRaw.hooks.register('before_send', () => {
    ChatRaw.ui.registerToolbarButton({ ... });  // Will fail!
});

// ✅ Correct - register immediately in IIFE
(function(ChatRaw) {
    // Register buttons here, during script load
    ChatRaw.ui.registerToolbarButton({ ... });  // Works!
})(window.ChatRawPlugin);
```

---

<a name="中文"></a>
## 中文

### 概述

ChatRaw 插件通过轻量级的 JavaScript 架构扩展应用功能。插件在浏览器中运行，可以通过安全的代理 API 与后端交互。

### 插件结构

一个插件由包含以下文件的文件夹组成：

```
your-plugin/
├── manifest.json    # 插件元数据（必需）
├── icon.png         # 插件图标，128x128像素（必需）
├── main.js          # 插件代码（必需）
└── lib/             # 本地依赖库（可选）
    ├── library.min.js
    └── library.min.css
```

**本地依赖 (lib/ 目录)**：对于需要完全离线运行的插件，可以将依赖库打包到本地，而不是从 CDN 加载。`lib/` 目录下的文件通过 `/api/plugins/{plugin_id}/lib/{filename}` 提供访问。支持子目录（如 `lib/fonts/`）。

### manifest.json

```json
{
  "id": "your-plugin-id",
  "version": "1.0.0",
  "name": {
    "en": "Your Plugin Name",
    "zh": "你的插件名称"
  },
  "description": {
    "en": "Brief description of your plugin",
    "zh": "插件的简短描述"
  },
  "author": "作者名称",
  "homepage": "https://github.com/your-repo",
  "icon": "icon.png",
  "main": "main.js",
  "type": "document_parser",
  "hooks": ["parse_document"],
  "fileTypes": [".xlsx", ".xls"],
  "dependencies": {
    "library-name": "https://cdn.example.com/library.min.js"
  },
  "settings": [
    {
      "id": "settingId",
      "type": "select",
      "options": ["option1", "option2"],
      "default": "option1",
      "label": {
        "en": "Setting Label",
        "zh": "设置标签"
      }
    }
  ],
  "customSettings": false,
  "proxy": [
    {
      "id": "service-name",
      "name": { "en": "Service Name", "zh": "服务名称" },
      "description": { "en": "API key for service", "zh": "服务的 API 密钥" }
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `id` | string | 是 | 唯一插件标识符（小写，可用连字符） |
| `version` | string | 是 | 语义化版本（如 "1.0.0"） |
| `name` | object | 是 | 多语言插件名称 |
| `description` | object | 是 | 多语言插件描述 |
| `author` | string | 是 | 作者名称 |
| `homepage` | string | 否 | 项目主页 URL |
| `icon` | string | 是 | 图标文件名（128x128 PNG，显示时带圆角） |
| `main` | string | 是 | 主 JavaScript 文件 |
| `type` | string | 是 | 插件类型（见下表） |
| `hooks` | array | 是 | 插件使用的钩子列表 |
| `fileTypes` | array | 否 | document_parser 类型的文件扩展名。插件启用后，这些扩展名会自动添加到文件上传对话框中。 |
| `dependencies` | object | 否 | 外部 JS 库（名称: CDN URL） |
| `settings` | array | 否 | 插件设置架构（用于标准设置 UI） |
| `customSettings` | boolean | 否 | 设为 `true` 启用自定义设置 UI |
| `proxy` | array | 否 | 需要 API Key 的外部服务 |

### 插件类型

| 类型 | 描述 | 可用钩子 |
|------|------|----------|
| `document_parser` | 解析文档文件 | `parse_document` |
| `url_parser` | 解析网页 URL 为正文 | `parse_url`, `custom_settings` |
| `search_provider` | 网络搜索服务 | `web_search`, `before_send` |
| `rag_enhancer` | 增强 RAG 流程 | `pre_embedding`, `post_retrieval`, `before_send`, `custom_settings` |
| `ui_extension` | 添加 UI 元素 | `toolbar_button`, `custom_action` |
| `message_processor` | 消息处理 | `before_send`, `after_receive`, `transform_input`, `transform_output` |
| `model_manager` | 管理多个模型配置 | `custom_settings` |

### 可用钩子列表

| 钩子 | 描述 | 参数 | 返回值 |
|------|------|------|--------|
| `parse_document` | 解析上传的文件 | `(file, settings)` | `{ success, content }` |
| `parse_url` | 解析网页 URL 为正文 | `(url, html, settings)` — 浏览器模式下有 html，API 模式下为 null | `{ success, title?, content?, error? }` |
| `web_search` | 网络搜索 | `(query, settings)` | `{ success, results }` |
| `pre_embedding` | 文本嵌入前 | `(text, settings)` | `{ success, text }` |
| `post_retrieval` | RAG 检索后 | `(results, settings)` | `{ success, results }` |
| `before_send` | 发送消息前 | `(body)` | `{ success, body }` |
| `after_receive` | 收到回复后 | `(message)` | `{ success, content }` |
| `transform_input` | 转换用户输入 | `(message)` | `{ success, content }` |
| `transform_output` | 转换 AI 输出 | `(content)` | `{ success, content }` |
| `toolbar_button` | 添加工具栏按钮 | `(context)` | `{ icon, label, onClick }` |
| `file_preview` | 自定义文件预览 | `(file)` | `{ success, html }` |
| `custom_action` | 自定义操作 | `(action, data)` | `{ success, result }` |
| `custom_settings` | 自定义设置 UI | - | - |

### 设置类型

用于标准设置 UI（`customSettings: false`）：

| 类型 | 描述 | 示例 |
|------|------|------|
| `boolean` | 开关 | `{ "type": "boolean", "default": true }` |
| `string` | 文本输入 | `{ "type": "string", "default": "" }` |
| `number` | 数字输入 | `{ "type": "number", "default": 10, "min": 1, "max": 100 }` |
| `select` | 下拉选择 | `{ "type": "select", "options": ["a", "b"], "default": "a" }` |
| `password` | 密码输入 | `{ "type": "password", "default": "" }` |

### 自定义设置 UI

对于需要完全控制设置界面的复杂插件，使用 `customSettings: true`。

**滚动内容 + 固定底部按钮**：如果设置界面内容较长，使用以下结构：

```html
<div style="display:flex; flex-direction:column; height:100%; max-height:70vh;">
    <div style="flex:1; min-height:0; overflow-y:auto;">
        <!-- 可滚动的设置内容 -->
    </div>
    <div style="flex-shrink:0; padding:16px 24px; border-top:1px solid var(--border-color);">
        <!-- 取消/保存按钮（固定在底部） -->
    </div>
</div>
```

> **关键**：滚动容器上的 `min-height:0` 是必需的——没有它，flex 子元素不会收缩到比内容更小的尺寸，滚动将无法生效。

**manifest.json:**
```json
{
  "hooks": ["before_send", "custom_settings"],
  "customSettings": true,
  "proxy": [
    {
      "id": "my-service",
      "name": { "en": "API Key", "zh": "API 密钥" }
    }
  ]
}
```

**main.js:**
```javascript
(function(ChatRaw) {
    'use strict';
    
    const PLUGIN_ID = 'my-plugin';
    const SERVICE_ID = 'my-service';
    
    // i18n 支持
    const i18n = {
        en: {
            apiKeyLabel: 'API Key',
            verify: 'Verify',
            verifying: 'Verifying...',
            verifySuccess: 'API Key is valid!',
            verifyFailed: 'Verification failed',
            save: 'Save',
            cancel: 'Cancel',
            settingsSaved: 'Settings saved'
        },
        zh: {
            apiKeyLabel: 'API 密钥',
            verify: '验证',
            verifying: '验证中...',
            verifySuccess: 'API Key 有效！',
            verifyFailed: '验证失败',
            save: '保存',
            cancel: '取消',
            settingsSaved: '设置已保存'
        }
    };
    
    function t(key) {
        const lang = ChatRaw.utils?.getLanguage?.() || 'en';
        return i18n[lang]?.[key] || i18n.en[key] || key;
    }
    
    // 插件设置（本地状态）
    let pluginSettings = { option1: 'default' };
    
    // 从后端加载设置
    async function loadSettings() {
        try {
            const res = await fetch('/api/plugins');
            if (res.ok) {
                const plugins = await res.json();
                const plugin = plugins.find(p => p.id === PLUGIN_ID);
                if (plugin?.settings_values) {
                    pluginSettings = { ...pluginSettings, ...plugin.settings_values };
                }
            }
        } catch (e) {
            console.error('加载设置失败:', e);
        }
    }
    
    // 保存设置到后端
    async function saveSettings() {
        try {
            const res = await fetch(`/api/plugins/${PLUGIN_ID}/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ settings: pluginSettings })
            });
            if (res.ok) {
                ChatRaw.utils?.showToast?.(t('settingsSaved'), 'success');
                return true;
            }
            return false;
        } catch (e) {
            return false;
        }
    }
    
    // 保存 API 密钥
    async function saveApiKey(apiKey) {
        const res = await fetch('/api/plugins/api-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ service_id: SERVICE_ID, api_key: apiKey })
        });
        return res.ok;
    }
    
    // 检查 API 密钥是否已设置
    async function checkApiKeyStatus() {
        try {
            const res = await fetch('/api/plugins/api-keys');
            if (res.ok) {
                const data = await res.json();
                return !!data.api_keys?.[SERVICE_ID];
            }
        } catch (e) {}
        return false;
    }
    
    // 通过测试请求验证 API 密钥
    async function verifyApiKey(apiKey) {
        await saveApiKey(apiKey);
        
        const result = await ChatRaw.proxy.request({
            serviceId: SERVICE_ID,
            url: 'https://api.example.com/test',
            method: 'POST',
            body: { test: true }
        });
        
        if (result.success) {
            return { success: true };
        } else {
            await saveApiKey(''); // 清除无效密钥
            return { success: false, error: result.error };
        }
    }
    
    // 创建设置 UI HTML
    function createSettingsUI() {
        return `
            <div style="padding:0;">
                <div style="padding:20px 24px; border-bottom:1px solid var(--border-color);">
                    <h3 style="margin:0 0 16px 0;">${t('apiKeyLabel')}</h3>
                    <div style="display:flex; gap:12px;">
                        <input type="password" id="my-api-key" class="input-minimal" 
                            style="flex:1; padding:10px;">
                        <button id="my-verify-btn" class="btn-primary" 
                            onclick="window._myPlugin.verifyApiKey()"
                            style="padding:10px 20px;">
                            ${t('verify')}
                        </button>
                    </div>
                    <div id="my-api-status" style="margin-top:10px;"></div>
                </div>
                
                <div style="display:flex; justify-content:flex-end; gap:12px; padding:16px 24px;">
                    <button class="btn-secondary" onclick="window._myPlugin.closeSettings()">
                        ${t('cancel')}
                    </button>
                    <button class="btn-primary" onclick="window._myPlugin.saveAllSettings()">
                        ${t('save')}
                    </button>
                </div>
            </div>
        `;
    }
    
    // 关闭设置模态框
    function closeSettings() {
        const app = document.querySelector('[x-data]');
        if (app?._x_dataStack) {
            app._x_dataStack[0].showPluginSettings = false;
        }
    }
    
    // 保存并关闭
    async function saveAllSettings() {
        const success = await saveSettings();
        if (success) {
            closeSettings();
        }
    }
    
    // 全局 API 用于 UI 事件处理
    window._myPlugin = {
        verifyApiKey: async () => {
            const input = document.getElementById('my-api-key');
            const btn = document.getElementById('my-verify-btn');
            const status = document.getElementById('my-api-status');
            
            if (!input?.value.trim()) return;
            
            btn.textContent = t('verifying');
            const result = await verifyApiKey(input.value.trim());
            
            if (result.success) {
                status.innerHTML = `<span style="color:var(--success-color);">✓ ${t('verifySuccess')}</span>`;
                input.value = '';
            } else {
                status.innerHTML = `<span style="color:var(--error-color);">✗ ${t('verifyFailed')}</span>`;
            }
            btn.textContent = t('verify');
        },
        closeSettings,
        saveAllSettings
    };
    
    // 设置模态框打开时注入 UI
    function setupSettingsListener() {
        window.addEventListener('plugin-settings-open', async (event) => {
            if (event.detail?.pluginId === PLUGIN_ID) {
                await loadSettings();
                setTimeout(() => {
                    const container = document.getElementById('plugin-custom-settings-area');
                    if (container) {
                        container.innerHTML = createSettingsUI();
                    }
                }, 100);
            }
        });
    }
    
    // 初始化
    loadSettings();
    setupSettingsListener();
    
})(window.ChatRawPlugin);
```

### 代理 API（用于外部服务）

为保护 API 密钥，请使用代理 API 调用外部服务：

#### JSON 请求代理

```javascript
const response = await ChatRaw.proxy.request({
    serviceId: 'your-service',  // 必须与 manifest 中的 proxy.id 匹配
    url: 'https://api.example.com/endpoint',
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: { query: '搜索词' }
});
```

#### 文件上传代理

用于需要文件上传的服务（如 Whisper、OCR）：

```javascript
const response = await ChatRaw.proxy.upload(
    file,           // File 对象
    'whisper',      // service_id 用于查找 API 密钥
    'https://api.openai.com/v1/audio/transcriptions',
    { model: 'whisper-1' },  // 额外的表单字段
    'file'          // 文件字段名（默认: 'file'）
);
```

API 密钥安全存储在后端，会自动添加到请求中。

### 工具 API

为插件开发者提供的辅助函数：

```javascript
// 加载外部脚本
await ChatRaw.utils.loadScript('https://cdn.example.com/lib.js');

// 显示提示消息
ChatRaw.utils.showToast('操作完成', 'success');

// 获取当前语言 ('en' 或 'zh')
const lang = ChatRaw.utils.getLanguage();

// 翻译键值
const text = ChatRaw.utils.t('settings');

// 显示进度指示器
ChatRaw.utils.showProgress(50, '处理中...');

// 隐藏进度指示器
ChatRaw.utils.hideProgress();

// 获取当前会话 ID
const chatId = ChatRaw.utils.getCurrentChatId();

// 获取当前消息列表
const messages = ChatRaw.utils.getMessages();

// 添加消息到显示
ChatRaw.utils.addMessage('assistant', '来自插件的问候！');
```

### 工具栏按钮扩展 API

插件可以使用 `ChatRawPlugin.ui` API 在输入框工具栏添加自定义按钮。按钮支持激活态和加载态，插件还可以打开全屏模态框实现复杂交互。

#### 注册工具栏按钮

> **重要提示**：工具栏按钮必须在**插件脚本加载时立即注册**（在 IIFE 内部），而不是在 hook 回调中注册。插件上下文（`_currentLoadingPlugin`）仅在脚本执行期间可用。

```javascript
ChatRawPlugin.ui.registerToolbarButton({
    id: 'my-button',           // 必填：插件内唯一的按钮 ID
    icon: 'ri-search-line',    // 必填：RemixIcon 类名（必须以 ri- 开头）
    label: {                   // 必填：多语言提示文本
        en: 'Search',
        zh: '搜索'
    },
    onClick: async (button) => {  // 必填：点击回调
        // button 包含当前状态: { id, active, loading, ... }
        console.log('按钮被点击！');
    },
    order: 10                  // 可选：排序权重（默认：100，越小越靠前）
});
```

**图标要求**：所有按钮图标**必须**使用 [RemixIcon](https://remixicon.com/)（格式：`ri-xxx-line` 或 `ri-xxx-fill`）。无效图标会导致注册失败。

#### 设置按钮状态

```javascript
// 设置激活态（如功能已开启）
ChatRawPlugin.ui.setButtonState('my-button', { active: true });

// 设置加载态（如正在处理）
ChatRawPlugin.ui.setButtonState('my-button', { loading: true });

// 同时设置多个状态
ChatRawPlugin.ui.setButtonState('my-button', { active: true, loading: false });

// 重置所有状态
ChatRawPlugin.ui.setButtonState('my-button', { active: false, loading: false });
```

#### 注销按钮

```javascript
// 移除按钮（通常不需要，插件禁用时会自动清理）
ChatRawPlugin.ui.unregisterToolbarButton('my-button');
```

#### 打开全屏模态框

```javascript
// 打开带自定义 HTML 内容的全屏模态框
ChatRawPlugin.ui.openFullscreenModal({
    content: `
        <div style="padding: 40px; text-align: center;">
            <h2>我的插件</h2>
            <p>这是一个全屏模态框！</p>
            <button onclick="ChatRawPlugin.ui.closeFullscreenModal()" 
                    class="btn-primary" style="margin-top: 20px;">
                关闭
            </button>
        </div>
    `,
    closable: true,           // 可选：是否允许 ESC/点击背景关闭（默认：true）
    onClose: () => {          // 可选：模态框关闭时的回调
        console.log('模态框已关闭');
    }
});

// 简单用法：直接传入 HTML 字符串
ChatRawPlugin.ui.openFullscreenModal('<div>简单内容</div>');
```

#### 关闭全屏模态框

```javascript
ChatRawPlugin.ui.closeFullscreenModal();
```

#### 按钮溢出处理

当注册超过 5 个插件按钮时，多余的按钮会自动折叠到「更多」下拉菜单中。

#### 生命周期管理

当插件被禁用或卸载时：
- 该插件注册的所有工具栏按钮会自动移除
- 如果该插件打开了全屏模态框，会自动关闭

#### 完整示例

```javascript
(function(ChatRaw) {
    'use strict';
    
    const PLUGIN_ID = 'demo-plugin';
    
    // 追踪开关状态
    let isEnabled = false;
    
    // 注册一个切换按钮
    ChatRaw.ui.registerToolbarButton({
        id: 'toggle-feature',
        icon: 'ri-toggle-line',
        label: { en: 'Toggle Feature', zh: '切换功能' },
        order: 50,
        onClick: async (btn) => {
            isEnabled = !isEnabled;
            ChatRaw.ui.setButtonState('toggle-feature', { active: isEnabled }, PLUGIN_ID);
            ChatRaw.utils.showToast(isEnabled ? '功能已开启' : '功能已关闭');
        }
    });
    
    // 注册一个打开模态框的按钮
    ChatRaw.ui.registerToolbarButton({
        id: 'open-panel',
        icon: 'ri-window-line',
        label: { en: 'Open Panel', zh: '打开面板' },
        order: 60,
        onClick: async (btn) => {
            ChatRaw.ui.openFullscreenModal({
                content: `
                    <div style="padding:40px; max-width:600px; margin:0 auto;">
                        <h2 style="margin-bottom:20px;">插件面板</h2>
                        <p>在此配置插件设置。</p>
                        <button onclick="ChatRawPlugin.ui.closeFullscreenModal()" 
                                class="btn-primary" style="margin-top:20px;">
                            关闭
                        </button>
                    </div>
                `,
                closable: true
            });
        }
    });
    
})(window.ChatRawPlugin);
```

### 存储 API

插件专用本地存储（命名空间隔离，每个插件限制 1MB）。

**重要**：在插件初始化完成后调用存储方法（如按钮点击处理、设置界面中），必须传递 `pluginId` 作为最后一个参数：

```javascript
const PLUGIN_ID = 'my-plugin';

// 存储数据 - pluginId 作为第三个参数
ChatRaw.storage.set('lastUsed', Date.now(), PLUGIN_ID);
ChatRaw.storage.set('preferences', { theme: 'dark' }, PLUGIN_ID);

// 获取数据 - pluginId 作为第三个参数
const lastUsed = ChatRaw.storage.get('lastUsed', 0, PLUGIN_ID);
const prefs = ChatRaw.storage.get('preferences', {}, PLUGIN_ID);

// 删除数据 - pluginId 作为第二个参数
ChatRaw.storage.remove('lastUsed', PLUGIN_ID);

// 清空所有插件存储 - pluginId 作为参数
ChatRaw.storage.clear(PLUGIN_ID);

// 获取所有存储的数据 - pluginId 作为参数
const allData = ChatRaw.storage.getAll(PLUGIN_ID);
```

**注意**：`pluginId` 参数在插件初始化期间是可选的，但在事件处理器等后续调用中是必需的。

### 图标要求

- 格式：PNG
- 尺寸：128x128 像素
- 图标将以 iOS 风格的圆角显示（约 22% 圆角半径）
- 使用透明或纯色背景
- 保持设计简洁，在小尺寸下仍可辨识

### 打包分发

分发你的插件：

1. **准备插件文件夹**：
   ```
   your-plugin/
   ├── manifest.json    # 插件元数据
   ├── icon.png         # 128x128 PNG 图标
   └── main.js          # 插件代码
   ```

2. **创建 zip 文件**（排除系统文件）：
   ```bash
   # macOS/Linux
   zip -r your-plugin.zip your-plugin/ -x "*.DS_Store" "*__MACOSX*"
   
   # Windows
   # 使用文件资源管理器：右键文件夹 → 发送到 → 压缩(zipped)文件夹
   ```

3. **验证打包结果**：
   - 检查 zip 文件大小（建议 < 10MB）
   - 解压并验证文件夹结构
   - 确保 manifest.json 是有效的 JSON
   - 测试图标显示正确（128x128 PNG）

4. **分发方式**：
   - **插件市场**：提交到 `Plugin_market` 仓库
   - **本地上传**：用户在插件设置中拖放 zip 文件
   - **直接下载**：托管在 GitHub releases 或你的网站

5. **常见问题**：
   - ❌ zip 包含嵌套文件夹：`your-plugin.zip/your-plugin/your-plugin/manifest.json`
   - ✅ 正确结构：`your-plugin.zip/your-plugin/manifest.json`
   - ❌ 文件在插件文件夹外
   - ✅ 所有文件在单个插件文件夹内

### 进阶：本地依赖和 CSS 加载

对于需要完全离线运行的插件，可以将依赖打包到 `lib/` 目录中。

**加载 CSS 文件**（框架仅支持 JS，CSS 需要手动加载）：

```javascript
function loadCSS(url) {
    return new Promise((resolve, reject) => {
        const existing = document.querySelector(`link[href="${url}"]`);
        if (existing) { resolve(); return; }
        
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = url;
        link.onload = resolve;
        link.onerror = reject;
        document.head.appendChild(link);
    });
}

// 使用本地 lib
const PLUGIN_ID = 'your-plugin';
await loadCSS(`/api/plugins/${PLUGIN_ID}/lib/styles.min.css`);
```

**加载本地 JS 依赖**：

```javascript
async function loadScript(url) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = url;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// 从 lib 目录加载
await loadScript(`/api/plugins/${PLUGIN_ID}/lib/library.min.js`);
```

### 进阶：使用 after_receive 钩子

`after_receive` 钩子允许你在 AI 响应接收后、显示前修改内容。这对于增强渲染效果非常有用。

```javascript
ChatRawPlugin.hooks.register('after_receive', {
    priority: 10,  // 优先级越低，执行越晚
    
    handler: async (message) => {
        if (!message?.content) {
            return { success: false };  // 不修改
        }
        
        let content = message.content;
        
        // 示例：添加自定义处理
        content = processContent(content);
        
        // 返回修改后的内容
        return { success: true, content };
    }
});
```

**重要说明**：
- 如果不想修改内容，返回 `{ success: false }`
- 返回 `{ success: true, content: '...' }` 来替换消息内容
- 钩子接收完整的消息对象，包括 `role`、`content`、`thinking` 等
- 多个插件可以注册同一个钩子；第一个返回 `success: true` 的生效

### 最佳实践

1. **保持轻量**：最小化依赖和文件大小
2. **优雅处理错误**：始终返回正确的错误响应
3. **支持双语**：同时提供英文和中文文本（i18n）
4. **充分测试**：测试各种文件大小和边界情况
5. **文档完善**：在描述中包含使用说明
6. **API Key 验证**：始终为 API Key 提供"验证"按钮
7. **保存后关闭**：保存成功后自动关闭设置模态框
8. **正确持久化数据**：
   - 使用 `POST /api/plugins/{id}/settings` 保存插件设置
   - 使用 `POST /api/plugins/api-key` 保存 API 密钥
   - 使用 `POST /api/models` 保存模型配置（用于 RAG 插件）
9. **打开时加载数据**：设置模态框打开时始终重新加载设置
10. **自定义设置监听器**：使用 `plugin-settings-open` 事件注入自定义 UI
11. **异步操作必须 `await`**：在事件处理函数中调用异步函数（如 `saveSettings()`）时，必须使用 `await` 确保操作完成后再继续：

```javascript
// ❌ 错误 - 数据可能未保存
button.onclick = () => {
    saveSettings();  // 缺少 await！
    renderUI();
};

// ✅ 正确 - 等待保存完成
button.onclick = async () => {
    await saveSettings();
    renderUI();
};
```

12. **选择正确的存储方式**：

| 存储方式 | 存储位置 | Docker 重启后 | 适用场景 |
|---------|---------|--------------|---------|
| `ChatRaw.storage` | 浏览器 localStorage | **保留**（与 Docker 无关） | 临时偏好、UI 状态 |
| `POST /api/plugins/{id}/settings` | 服务器 `data/plugins/config.json` | **保留**（需挂载 Docker volume） | 核心配置、模型数据 |

> **重要提示**：如果你的插件配置需要在 Docker 容器重启后保留（通过 volume 挂载），**必须**使用后端 API `POST /api/plugins/{id}/settings`，而不是 `ChatRaw.storage`。基于 localStorage 的存储 API 仅在用户浏览器中持久化。

13. **离线插件与打包依赖**：
    - 带有 `lib/` 目录的插件会在容器启动时自动安装
    - 在线安装只会下载 `main.js`、`manifest.json`、`icon.png`
    - `lib/` 目录会从 Docker 镜像中的预打包版本自动复制
    - 所有插件相关请求不受 API 请求限流影响：
      - 静态文件：`/lib/`、`/icon`、`/main.js`
      - 插件元数据：`/api/plugins`、`/api/plugins/*`

14. **使用 Shadow DOM 隔离样式**：
    - 第三方库（如 Mermaid）可能注入全局 CSS 污染其他元素
    - 使用 Shadow DOM 完全隔离其样式：
    ```javascript
    const shadowHost = document.createElement('div');
    const shadow = shadowHost.attachShadow({ mode: 'closed' });
    shadow.innerHTML = thirdPartyContent;
    container.appendChild(shadowHost);
    ```

15. **检测消息流式输出完成**：
    - 使用 `window.getComputedStyle()` 检查 typing-indicator 可见性
    - Alpine.js 的 `x-show` 隐藏时会设置 `display: none`
    ```javascript
    const typingIndicator = msg.querySelector('.typing-indicator');
    if (typingIndicator) {
        const style = window.getComputedStyle(typingIndicator);
        if (style.display !== 'none') {
            // 消息仍在流式输出，等待
            return;
        }
    }
    ```
    - 使用内容稳定性检测（防抖 ~800ms）确保流式输出完成

### 常见陷阱

开发时请注意避免以下常见错误：

1. **错误的 IIFE 模式**：始终使用参数传递模式以获得更清晰的代码：

```javascript
// ❌ 错误 - 直接访问全局变量
(function() {
    window.ChatRawPlugin.hooks.register(...);
})();

// ✅ 正确 - 作为参数传递
(function(ChatRaw) {
    if (!ChatRaw || !ChatRaw.hooks) {
        console.error('[YourPlugin] ChatRawPlugin 不可用');
        return;
    }
    ChatRaw.hooks.register(...);
})(window.ChatRawPlugin);
```

2. **错误的 API 方法名**：请使用正确的方法名：

```javascript
// ❌ 错误 - getLang 方法不存在
const lang = ChatRaw.utils?.getLang?.() || 'en';

// ✅ 正确 - 使用 getLanguage
const lang = ChatRaw.utils?.getLanguage?.() || 'en';
```

3. **缺少可选链操作符**：对于可能未定义的方法，始终使用 `?.`：

```javascript
// ❌ 有风险 - 如果 utils 未定义会报错
ChatRaw.utils.showToast('消息', 'info');

// ✅ 安全 - 优雅处理未定义情况
ChatRaw.utils?.showToast?.('消息', 'info');
```

4. **缺少安全检查**：始终在启动时验证 ChatRawPlugin 是否可用（见上方第 1 条）。

5. **工具栏按钮图标格式**：必须使用 RemixIcon 格式（`ri-xxx-line` 或 `ri-xxx-fill`）：

```javascript
// ❌ 错误 - 会被拒绝
icon: 'fa-home'        // FontAwesome
icon: 'mdi-home'       // Material Design Icons
icon: 'icon-home'      // 自定义类名

// ✅ 正确 - RemixIcon 格式
icon: 'ri-home-line'   // 线条样式
icon: 'ri-home-fill'   // 填充样式
```

6. **在 hook 回调中注册工具栏按钮**：按钮必须在脚本加载时立即注册，不能在 hook 中注册：

```javascript
// ❌ 错误 - hook 回调执行时 _currentLoadingPlugin 已被清除
ChatRaw.hooks.register('before_send', () => {
    ChatRaw.ui.registerToolbarButton({ ... });  // 会失败！
});

// ✅ 正确 - 在 IIFE 中立即注册
(function(ChatRaw) {
    // 在这里注册按钮，脚本加载期间
    ChatRaw.ui.registerToolbarButton({ ... });  // 正常工作！
})(window.ChatRawPlugin);
```

---

## License

Plugins developed for ChatRaw should be compatible with the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0).

---

Copyright © 2026 ChatRaw
