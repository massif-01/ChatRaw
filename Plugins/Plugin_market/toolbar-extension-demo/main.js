/**
 * Toolbar Extension Demo Plugin
 * 工具栏扩展 DEMO 插件
 * 
 * This plugin demonstrates the new UI Extension API:
 * 本插件展示新版 UI 扩展 API 的使用方法：
 * 
 * - Register toolbar buttons / 注册工具栏按钮
 * - Button active/loading states / 按钮激活态/加载态
 * - Open fullscreen modal / 打开全屏模态框
 * - Plugin lifecycle management / 插件生命周期管理
 * 
 * @version 1.0.0
 * @author ChatRaw
 * @license Apache-2.0
 */
(function(ChatRaw) {
    'use strict';
    
    // Safety check
    if (!ChatRaw || !ChatRaw.hooks) {
        console.error('[ToolbarDemo] ChatRawPlugin not available');
        return;
    }
    
    // Check UI API availability
    if (!ChatRaw.ui || !ChatRaw.ui.registerToolbarButton) {
        console.error('[ToolbarDemo] ChatRawPlugin.ui API not available');
        return;
    }
    
    console.log('[ToolbarDemo] ChatRawPlugin.ui is available:', !!ChatRaw.ui);
    
    const PLUGIN_ID = 'toolbar-extension-demo';
    
    // --- Internationalization ---
    const i18n = {
        en: {
            demoButton: 'Demo Button',
            loadingDemo: 'Loading Demo',
            modalDemo: 'Modal Demo',
            modalTitle: 'Fullscreen Modal Demo',
            modalDescription: 'This is a fullscreen modal opened by a plugin. You can put any custom HTML content here.',
            closeButton: 'Close',
            toggleActive: 'Toggle Active State',
            simulateLoading: 'Simulate Loading (3s)',
            openModal: 'Open Fullscreen Modal',
            currentState: 'Current State',
            activeState: 'Active',
            inactiveState: 'Inactive',
            loadingState: 'Loading...',
            idleState: 'Idle',
            instructions: 'Instructions',
            instruction1: 'Click the first button in toolbar to toggle active state',
            instruction2: 'Click the second button to simulate a 3-second loading operation',
            instruction3: 'Click the third button to open this fullscreen modal',
            instruction4: 'Press ESC or click outside to close this modal',
            apiDocs: 'API Documentation',
            apiDocLink: 'See Plugins/README.md for complete API documentation'
        },
        zh: {
            demoButton: '演示按钮',
            loadingDemo: '加载演示',
            modalDemo: '模态框演示',
            modalTitle: '全屏模态框演示',
            modalDescription: '这是由插件打开的全屏模态框，你可以在这里放置任意自定义 HTML 内容。',
            closeButton: '关闭',
            toggleActive: '切换激活态',
            simulateLoading: '模拟加载 (3秒)',
            openModal: '打开全屏模态框',
            currentState: '当前状态',
            activeState: '激活',
            inactiveState: '未激活',
            loadingState: '加载中...',
            idleState: '空闲',
            instructions: '使用说明',
            instruction1: '点击工具栏第一个按钮，切换按钮激活状态',
            instruction2: '点击第二个按钮，模拟 3 秒的加载操作',
            instruction3: '点击第三个按钮，打开此全屏模态框',
            instruction4: '按 ESC 或点击外部区域关闭模态框',
            apiDocs: 'API 文档',
            apiDocLink: '完整 API 文档请参阅 Plugins/README.md'
        }
    };
    
    function t(key) {
        const lang = ChatRaw.utils?.getLanguage?.() || 'en';
        return i18n[lang]?.[key] || i18n.en[key] || key;
    }
    
    // --- State tracking ---
    let isButton1Active = false;
    let isButton2Loading = false;
    
    // --- Button click handlers ---
    
    // Button 1: Toggle active state
    function handleButton1Click() {
        isButton1Active = !isButton1Active;
        ChatRaw.ui.setButtonState('demo-toggle', {
            active: isButton1Active
        }, PLUGIN_ID);
        
        ChatRaw.utils?.showToast?.(
            isButton1Active ? t('activeState') : t('inactiveState'),
            'info'
        );
    }
    
    // Button 2: Simulate loading operation
    async function handleButton2Click() {
        if (isButton2Loading) return;
        
        isButton2Loading = true;
        ChatRaw.ui.setButtonState('demo-loading', {
            loading: true
        }, PLUGIN_ID);
        
        // Simulate async operation
        await new Promise(resolve => setTimeout(resolve, 3000));
        
        isButton2Loading = false;
        ChatRaw.ui.setButtonState('demo-loading', {
            loading: false
        }, PLUGIN_ID);
        
        ChatRaw.utils?.showToast?.('✅ ' + t('idleState'), 'success');
    }
    
    // Button 3: Open fullscreen modal
    function handleButton3Click() {
        const lang = ChatRaw.utils?.getLanguage?.() || 'en';
        
        const modalContent = `
            <div style="
                max-width: 600px;
                margin: 0 auto;
                padding: 40px 20px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            ">
                <h1 style="
                    font-size: 28px;
                    font-weight: 600;
                    margin-bottom: 16px;
                    color: var(--text-primary, #1a1a1a);
                ">
                    <i class="ri-window-line" style="margin-right: 8px;"></i>
                    ${t('modalTitle')}
                </h1>
                
                <p style="
                    font-size: 16px;
                    color: var(--text-secondary, #666);
                    margin-bottom: 32px;
                    line-height: 1.6;
                ">
                    ${t('modalDescription')}
                </p>
                
                <!-- Current State Display -->
                <div style="
                    background: var(--bg-secondary, #f5f5f5);
                    border-radius: 12px;
                    padding: 20px;
                    margin-bottom: 24px;
                ">
                    <h3 style="
                        font-size: 14px;
                        font-weight: 600;
                        color: var(--text-secondary, #666);
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                        margin-bottom: 12px;
                    ">${t('currentState')}</h3>
                    
                    <div style="display: flex; gap: 24px; flex-wrap: wrap;">
                        <div>
                            <span style="color: var(--text-secondary, #666);">${t('toggleActive')}:</span>
                            <strong style="
                                color: ${isButton1Active ? 'var(--primary, #4F46E5)' : 'var(--text-primary, #1a1a1a)'};
                                margin-left: 8px;
                            ">${isButton1Active ? t('activeState') : t('inactiveState')}</strong>
                        </div>
                        <div>
                            <span style="color: var(--text-secondary, #666);">${t('simulateLoading')}:</span>
                            <strong style="
                                color: ${isButton2Loading ? 'var(--warning, #f59e0b)' : 'var(--text-primary, #1a1a1a)'};
                                margin-left: 8px;
                            ">${isButton2Loading ? t('loadingState') : t('idleState')}</strong>
                        </div>
                    </div>
                </div>
                
                <!-- Instructions -->
                <div style="
                    background: var(--bg-secondary, #f5f5f5);
                    border-radius: 12px;
                    padding: 20px;
                    margin-bottom: 24px;
                ">
                    <h3 style="
                        font-size: 14px;
                        font-weight: 600;
                        color: var(--text-secondary, #666);
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                        margin-bottom: 12px;
                    ">${t('instructions')}</h3>
                    
                    <ol style="
                        margin: 0;
                        padding-left: 20px;
                        color: var(--text-primary, #1a1a1a);
                        line-height: 1.8;
                    ">
                        <li>${t('instruction1')}</li>
                        <li>${t('instruction2')}</li>
                        <li>${t('instruction3')}</li>
                        <li>${t('instruction4')}</li>
                    </ol>
                </div>
                
                <!-- API Docs Link -->
                <div style="
                    background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
                    border-radius: 12px;
                    padding: 20px;
                    margin-bottom: 32px;
                    color: white;
                ">
                    <h3 style="
                        font-size: 14px;
                        font-weight: 600;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                        margin-bottom: 8px;
                        opacity: 0.9;
                    ">${t('apiDocs')}</h3>
                    <p style="margin: 0; opacity: 0.95;">${t('apiDocLink')}</p>
                </div>
                
                <!-- Close Button -->
                <button onclick="ChatRawPlugin.ui.closeFullscreenModal()" style="
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 8px;
                    width: 100%;
                    padding: 14px 24px;
                    font-size: 16px;
                    font-weight: 500;
                    color: white;
                    background: var(--primary, #4F46E5);
                    border: none;
                    border-radius: 10px;
                    cursor: pointer;
                    transition: all 0.2s;
                " onmouseover="this.style.opacity='0.9'" onmouseout="this.style.opacity='1'">
                    <i class="ri-close-line"></i>
                    ${t('closeButton')}
                </button>
            </div>
        `;
        
        ChatRaw.ui.openFullscreenModal({
            content: modalContent,
            closable: true,
            onClose: () => {
                console.log('[ToolbarDemo] Modal closed');
            }
        }, PLUGIN_ID);
    }
    
    // --- Register buttons immediately on load ---
    // Note: Buttons are registered when plugin script loads (not via hook)
    // The _currentLoadingPlugin context is available during script execution
    
    console.log('[ToolbarDemo] Plugin loaded, registering buttons...');
    console.log('[ToolbarDemo] _currentLoadingPlugin:', window.ChatRawPlugin?._currentLoadingPlugin);
    
    // Register Button 1: Toggle active state
    const result1 = ChatRaw.ui.registerToolbarButton({
        id: 'demo-toggle',
        icon: 'ri-checkbox-circle-line',
        label: {
            en: 'Toggle Active',
            zh: '切换激活态'
        },
        onClick: handleButton1Click,
        order: 100
    }, PLUGIN_ID);
    console.log('[ToolbarDemo] Button 1 registered:', result1);
    
    // Register Button 2: Loading demo
    const result2 = ChatRaw.ui.registerToolbarButton({
        id: 'demo-loading',
        icon: 'ri-time-line',
        label: {
            en: 'Loading Demo',
            zh: '加载演示'
        },
        onClick: handleButton2Click,
        order: 101
    }, PLUGIN_ID);
    console.log('[ToolbarDemo] Button 2 registered:', result2);
    
    // Register Button 3: Open modal
    const result3 = ChatRaw.ui.registerToolbarButton({
        id: 'demo-modal',
        icon: 'ri-layout-grid-line',
        label: {
            en: 'Open Modal',
            zh: '打开模态框'
        },
        onClick: handleButton3Click,
        order: 102
    }, PLUGIN_ID);
    console.log('[ToolbarDemo] Button 3 registered:', result3);
    
    console.log('[ToolbarDemo] 3 demo buttons registered');
    console.log('[ToolbarDemo] All results:', result1, result2, result3);
    
})(window.ChatRawPlugin);
