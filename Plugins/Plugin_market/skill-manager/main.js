/**
 * Skill Manager Plugin for ChatRaw
 *
 * Manages installed skills through the Phase 1-4 backend APIs. This plugin
 * never injects skills into chat itself and never executes skill scripts.
 *
 * @version 1.0.0
 * @author ChatRaw
 * @license MIT
 */
(function(ChatRaw) {
  'use strict';

  if (!ChatRaw || !ChatRaw.ui || !ChatRaw.ui.registerToolbarButton) {
    console.error('[SkillManager] ChatRawPlugin UI API not available');
    return;
  }

  const PLUGIN_ID = 'skill-manager';
  const STYLE_ID = 'skill-manager-style';
  const ROOT_ID = 'skill-manager-root';

  const i18n = {
    en: {
      buttonLabel: 'Skill Manager',
      title: 'Skill Manager',
      subtitle: 'Manage installed skills for explicit chat activation',
      install: 'Install',
      githubUrl: 'GitHub URL',
      githubPlaceholder: 'GitHub repo, owner/repo, raw/blob SKILL.md, or tree URL',
      installGithub: 'Install from GitHub',
      uploadLocal: 'Upload local skill',
      uploadHelp: 'Accepts SKILL.md or .zip packages',
      chooseFile: 'Choose .md or .zip',
      upload: 'Upload',
      overwrite: 'Overwrite existing skill',
      refresh: 'Refresh',
      installedSkills: 'Installed skills',
      emptyList: 'No skills installed',
      selectSkill: 'Select a skill to inspect its metadata and resources.',
      enabled: 'Enabled',
      disabled: 'Disabled',
      trusted: 'Trusted',
      untrusted: 'Untrusted',
      enableAction: 'Enable',
      disableAction: 'Disable',
      trustAction: 'Trust',
      untrustAction: 'Untrust',
      securityNote: 'Third-party skills are instruction content. Review the source before enabling or trusting a skill.',
      scriptBoundaryNote: 'ChatRaw stores scripts and resources for reference only. It does not execute skill scripts or grant allowed-tools permissions.',
      trustNote: 'Trusted is governance metadata for future implicit matching. It does not execute scripts or bypass explicit activation rules.',
      source: 'Source',
      diagnostics: 'Diagnostics',
      resources: 'Resources',
      metadata: 'Metadata',
      preview: 'Preview SKILL.md',
      hidePreview: 'Hide preview',
      delete: 'Delete',
      deletingConfirm: 'Delete this skill from local storage?',
      loading: 'Loading...',
      installing: 'Installing...',
      saving: 'Saving...',
      noDiagnostics: 'No diagnostics',
      noResources: 'No resources found',
      noMetadata: 'No metadata',
      installedAt: 'Installed',
      updatedAt: 'Updated',
      license: 'License',
      fileSelected: 'Selected file',
      noFile: 'No file selected',
      retryOverwrite: 'Skill already exists. Enable overwrite and retry.',
      installSuccess: 'Skill installed',
      chatInstallSuccess: 'Skill installed from chat.',
      chatInstallFailed: 'Skill install failed.',
      chatMultipleUrls: 'I found more than one GitHub skill URL. Please send one install command with a single URL.',
      chatSkillName: 'Name',
      chatSkillDescription: 'Description',
      chatSkillSource: 'Source',
      chatSkillEnabled: 'Enabled',
      chatSkillDiagnostics: 'Diagnostics',
      chatSkillUsage: 'Use',
      updateSuccess: 'Skill updated',
      deleteSuccess: 'Skill deleted',
      loadFailed: 'Failed to load skills',
      actionFailed: 'Action failed',
      previewFailed: 'Failed to load preview',
      close: 'Close'
    },
    zh: {
      buttonLabel: 'Skill 管理器',
      title: 'Skill 管理器',
      subtitle: '管理用于聊天显式激活的本地 Skills',
      install: '安装',
      githubUrl: 'GitHub URL',
      githubPlaceholder: 'GitHub 仓库、owner/repo、raw/blob SKILL.md 或 tree URL',
      installGithub: '从 GitHub 安装',
      uploadLocal: '上传本地 Skill',
      uploadHelp: '支持 SKILL.md 或 .zip 包',
      chooseFile: '选择 .md 或 .zip',
      upload: '上传',
      overwrite: '覆盖已存在的 skill',
      refresh: '刷新',
      installedSkills: '已安装 Skills',
      emptyList: '暂无已安装 skills',
      selectSkill: '选择一个 skill 查看 metadata 和资源摘要。',
      enabled: '已启用',
      disabled: '已禁用',
      trusted: '已信任',
      untrusted: '未信任',
      enableAction: '启用',
      disableAction: '禁用',
      trustAction: '信任',
      untrustAction: '取消信任',
      securityNote: '第三方 skill 是指令内容。启用或信任前请先检查来源。',
      scriptBoundaryNote: 'ChatRaw 只把 scripts 和资源作为参考保存；不会执行 skill scripts，也不会授予 allowed-tools 权限。',
      trustNote: 'Trusted 是为未来隐式匹配准备的治理元数据；不会执行 scripts，也不会绕过显式调用规则。',
      source: '来源',
      diagnostics: '诊断',
      resources: '资源',
      metadata: 'Metadata',
      preview: '预览 SKILL.md',
      hidePreview: '隐藏预览',
      delete: '删除',
      deletingConfirm: '从本地存储删除这个 skill？',
      loading: '加载中...',
      installing: '安装中...',
      saving: '保存中...',
      noDiagnostics: '没有诊断信息',
      noResources: '没有资源',
      noMetadata: '没有 metadata',
      installedAt: '安装时间',
      updatedAt: '更新时间',
      license: '许可证',
      fileSelected: '已选择文件',
      noFile: '未选择文件',
      retryOverwrite: 'Skill 已存在。启用覆盖后重试。',
      installSuccess: 'Skill 已安装',
      chatInstallSuccess: '已从聊天安装 Skill。',
      chatInstallFailed: 'Skill 安装失败。',
      chatMultipleUrls: '我发现了多个 GitHub Skill URL。请只保留一个 URL 后再发送安装命令。',
      chatSkillName: '名称',
      chatSkillDescription: '描述',
      chatSkillSource: '来源',
      chatSkillEnabled: '启用',
      chatSkillDiagnostics: '诊断',
      chatSkillUsage: '使用',
      updateSuccess: 'Skill 已更新',
      deleteSuccess: 'Skill 已删除',
      loadFailed: '加载 skills 失败',
      actionFailed: '操作失败',
      previewFailed: '预览加载失败',
      close: '关闭'
    }
  };

  let activeSessionId = 0;
  let requestSeq = 0;
  let state = null;

  function getLang() {
    return ChatRaw.utils?.getLanguage?.() || 'en';
  }

  function t(key) {
    const lang = getLang();
    return i18n[lang]?.[key] || i18n.en[key] || key;
  }

  function showToast(message, type) {
    ChatRaw.utils?.showToast?.(message, type || 'info');
  }

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
.skill-manager-shell {
  width: 100%;
  height: min(780px, 90vh);
  margin: 0;
  color: var(--text-primary, #111827);
  background: var(--bg-primary, #ffffff);
  border: 0;
  border-radius: inherit;
  box-shadow: none;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.skill-manager-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
  background: var(--bg-primary, #ffffff);
}
.skill-manager-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 4px;
  font-size: 20px;
  line-height: 1.2;
  font-weight: 650;
}
.skill-manager-subtitle {
  margin: 0;
  color: var(--text-secondary, #64748b);
  font-size: 13px;
  line-height: 1.4;
}
.skill-manager-close,
.skill-manager-icon-button {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-color, #d1d5db);
  border-radius: 8px;
  background: var(--bg-primary, #ffffff);
  color: var(--text-secondary, #475569);
  cursor: pointer;
}
.skill-manager-close:hover,
.skill-manager-icon-button:hover {
  color: var(--text-primary, #111827);
  background: var(--bg-secondary, #f8fafc);
}
.skill-manager-body {
  min-height: 0;
  flex: 1;
  display: grid;
  grid-template-columns: minmax(310px, 360px) minmax(0, 1fr);
}
.skill-manager-sidebar {
  min-height: 0;
  border-right: 1px solid var(--border-color, #e5e7eb);
  background: var(--bg-secondary, #f8fafc);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.skill-manager-sidebar-scroll {
  min-height: 0;
  overflow: auto;
  padding: 14px;
}
.skill-manager-panel {
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 10px;
  background: var(--bg-primary, #ffffff);
  padding: 12px;
  margin-bottom: 12px;
}
.skill-manager-panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 650;
}
.skill-manager-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}
.skill-manager-label {
  font-size: 12px;
  color: var(--text-secondary, #64748b);
  font-weight: 600;
}
.skill-manager-input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border-color, #d1d5db);
  border-radius: 8px;
  background: var(--bg-primary, #ffffff);
  color: var(--text-primary, #111827);
  padding: 9px 10px;
  font-size: 13px;
}
.skill-manager-input:focus {
  outline: none;
  border-color: var(--border-focus, var(--accent-color, #111827));
  box-shadow: 0 0 0 3px hsl(var(--ring, 0 0% 0%) / 0.12);
}
.skill-manager-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.skill-manager-action-row {
  flex-wrap: nowrap;
}
.skill-manager-action-row .skill-manager-checkbox {
  min-width: 0;
}
.skill-manager-action-row .skill-manager-checkbox span {
  overflow-wrap: anywhere;
}
.skill-manager-action-row .skill-manager-button span {
  white-space: nowrap;
}
.skill-manager-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--text-secondary, #475569);
  font-size: 12px;
  line-height: 1.3;
  user-select: none;
}
.skill-manager-checkbox input {
  accent-color: var(--accent-color, #111827);
}
.skill-manager-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 34px;
  border: 1px solid var(--border-color, #d1d5db);
  border-radius: 8px;
  padding: 7px 11px;
  background: var(--bg-primary, #ffffff);
  color: var(--text-primary, #111827);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: color var(--duration-fast, 150ms) var(--ease, ease),
    background-color var(--duration-fast, 150ms) var(--ease, ease),
    border-color var(--duration-fast, 150ms) var(--ease, ease),
    transform var(--duration-fast, 150ms) var(--ease, ease);
}
.skill-manager-button:hover {
  background: var(--bg-secondary, #f8fafc);
}
.skill-manager-button-primary {
  color: var(--on-accent, #ffffff);
  border-color: var(--accent-color, #111827);
  background: var(--accent-color, #111827);
}
.skill-manager-button-primary:hover:not(:disabled) {
  border-color: var(--accent-hover, #333333);
  background: var(--accent-hover, #333333);
}
.skill-manager-button:active:not(:disabled) {
  transform: translateY(1px);
}
.skill-manager-button-danger {
  color: #b91c1c;
  border-color: rgba(185, 28, 28, 0.24);
  background: #fff7f7;
}
.skill-manager-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.skill-manager-button-primary:disabled {
  color: var(--text-muted, #6b6b6b);
  border-color: var(--border-color, #d1d5db);
  background: var(--bg-secondary, #f8fafc);
  opacity: 1;
}
.skill-manager-muted {
  color: var(--text-secondary, #64748b);
  font-size: 12px;
  line-height: 1.45;
}
.skill-manager-status {
  min-height: 18px;
  margin: 8px 0 0;
  color: var(--text-secondary, #64748b);
  font-size: 12px;
  line-height: 1.4;
}
.skill-manager-status-error {
  color: #b91c1c;
}
.skill-manager-status-success {
  color: #047857;
}
.skill-manager-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 8px 0 10px;
}
.skill-manager-list-title {
  margin: 0;
  font-size: 13px;
  font-weight: 650;
}
.skill-manager-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.skill-manager-list-item {
  width: 100%;
  text-align: left;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 10px;
  background: var(--bg-primary, #ffffff);
  padding: 10px;
  cursor: pointer;
}
.skill-manager-list-item:hover,
.skill-manager-list-item-active {
  border-color: hsl(var(--ring, 0 0% 0%) / 0.42);
  box-shadow: 0 0 0 3px hsl(var(--ring, 0 0% 0%) / 0.08);
}
.skill-manager-list-name {
  display: block;
  overflow-wrap: anywhere;
  font-size: 13px;
  font-weight: 650;
  color: var(--text-primary, #111827);
}
.skill-manager-list-badges,
.skill-manager-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.skill-manager-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 999px;
  padding: 3px 7px;
  background: var(--bg-secondary, #f8fafc);
  color: var(--text-secondary, #475569);
  font-size: 11px;
  line-height: 1.2;
  font-weight: 600;
}
.skill-manager-badge-success {
  color: #047857;
  border-color: rgba(4, 120, 87, 0.22);
  background: #ecfdf5;
}
.skill-manager-badge-warning {
  color: #9a3412;
  border-color: rgba(154, 52, 18, 0.22);
  background: #fff7ed;
}
.skill-manager-badge-danger {
  color: #b91c1c;
  border-color: rgba(185, 28, 28, 0.22);
  background: #fff7f7;
}
.skill-manager-detail {
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: 20px;
}
.skill-manager-empty[hidden],
.skill-manager-detail [hidden],
.skill-manager-shell [hidden] {
  display: none !important;
}
.skill-manager-empty {
  height: 100%;
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--text-secondary, #64748b);
  font-size: 14px;
}
.skill-manager-detail-header {
  margin-bottom: 10px;
}
.skill-manager-detail-name {
  margin: 0 0 6px;
  overflow-wrap: anywhere;
  font-size: 24px;
  line-height: 1.2;
  font-weight: 700;
}
.skill-manager-detail-description {
  margin: 0;
  color: var(--text-secondary, #475569);
  font-size: 14px;
  line-height: 1.5;
}
.skill-manager-detail-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin: 0 0 16px;
}
.skill-manager-detail-actions .skill-manager-button {
  white-space: nowrap;
}
.skill-manager-section {
  border-top: 1px solid var(--border-color, #e5e7eb);
  padding-top: 16px;
  margin-top: 16px;
}
.skill-manager-section-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 700;
}
.skill-manager-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.skill-manager-kv {
  min-width: 0;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  padding: 9px;
  background: var(--bg-secondary, #f8fafc);
}
.skill-manager-kv-key {
  display: block;
  margin-bottom: 4px;
  color: var(--text-secondary, #64748b);
  font-size: 11px;
  font-weight: 700;
}
.skill-manager-kv-value {
  display: block;
  overflow-wrap: anywhere;
  color: var(--text-primary, #111827);
  font-size: 12px;
  line-height: 1.4;
}
.skill-manager-list-plain {
  margin: 0;
  padding-left: 18px;
  color: var(--text-primary, #111827);
  font-size: 13px;
  line-height: 1.5;
}
.skill-manager-list-plain li {
  margin: 4px 0;
  overflow-wrap: anywhere;
}
.skill-manager-preview {
  display: none;
  margin-top: 12px;
}
.skill-manager-preview-visible {
  display: block;
}
.skill-manager-preview-text {
  width: 100%;
  min-height: 260px;
  box-sizing: border-box;
  resize: vertical;
  border: 1px solid var(--border-color, #d1d5db);
  border-radius: 10px;
  background: var(--bg-secondary, #f8fafc);
  color: var(--text-primary, #111827);
  padding: 12px;
  font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  white-space: pre;
}
@media (max-width: 820px) {
  .skill-manager-shell {
    width: 100%;
    height: 100vh;
    margin: 0;
    border-radius: 0;
  }
  .skill-manager-body {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(260px, 42vh) minmax(0, 1fr);
  }
  .skill-manager-sidebar {
    border-right: 0;
    border-bottom: 1px solid var(--border-color, #e5e7eb);
  }
  .skill-manager-detail {
    padding: 16px;
  }
  .skill-manager-grid {
    grid-template-columns: 1fr;
  }
}
`;
    document.head.appendChild(style);
  }

  function buildModalContent() {
    return `
<div id="${ROOT_ID}" class="skill-manager-shell">
  <div class="skill-manager-header">
    <div>
      <h1 class="skill-manager-title"><i class="ri-sparkling-2-line" aria-hidden="true"></i><span data-sm-text="title">${t('title')}</span></h1>
      <p class="skill-manager-subtitle" data-sm-text="subtitle">${t('subtitle')}</p>
    </div>
    <button class="skill-manager-close" type="button" data-sm-action="close" aria-label="${t('close')}"><i class="ri-close-line" aria-hidden="true"></i></button>
  </div>
  <div class="skill-manager-body">
    <aside class="skill-manager-sidebar">
      <div class="skill-manager-sidebar-scroll">
        <section class="skill-manager-panel">
          <h2 class="skill-manager-panel-title"><span>${t('install')}</span></h2>
          <p class="skill-manager-muted">${t('securityNote')}</p>
          <div class="skill-manager-field">
            <label class="skill-manager-label" for="skill-manager-github-url">${t('githubUrl')}</label>
            <input id="skill-manager-github-url" class="skill-manager-input" type="text" inputmode="url" autocomplete="off" placeholder="${t('githubPlaceholder')}">
          </div>
          <div class="skill-manager-row skill-manager-action-row">
            <button class="skill-manager-button skill-manager-button-primary" type="button" data-sm-action="github-install"><i class="ri-github-line" aria-hidden="true"></i><span>${t('installGithub')}</span></button>
            <label class="skill-manager-checkbox"><input type="checkbox" data-sm-field="github-overwrite"> <span>${t('overwrite')}</span></label>
          </div>
        </section>

        <section class="skill-manager-panel">
          <h2 class="skill-manager-panel-title"><span>${t('uploadLocal')}</span></h2>
          <p class="skill-manager-muted">${t('uploadHelp')}</p>
          <p class="skill-manager-muted">${t('scriptBoundaryNote')}</p>
          <div class="skill-manager-field">
            <label class="skill-manager-label" for="skill-manager-file-input">${t('chooseFile')}</label>
            <input id="skill-manager-file-input" class="skill-manager-input" type="file" accept=".md,.zip">
            <p class="skill-manager-status" data-sm-text="file-status">${t('noFile')}</p>
          </div>
          <div class="skill-manager-row skill-manager-action-row">
            <button class="skill-manager-button skill-manager-button-primary" type="button" data-sm-action="upload"><i class="ri-upload-line" aria-hidden="true"></i><span>${t('upload')}</span></button>
            <label class="skill-manager-checkbox"><input type="checkbox" data-sm-field="upload-overwrite"> <span>${t('overwrite')}</span></label>
          </div>
        </section>

        <div class="skill-manager-status" data-sm-text="status"></div>

        <div class="skill-manager-list-header">
          <h2 class="skill-manager-list-title">${t('installedSkills')}</h2>
          <button class="skill-manager-icon-button" type="button" data-sm-action="refresh" aria-label="${t('refresh')}"><i class="ri-refresh-line" aria-hidden="true"></i></button>
        </div>
        <div class="skill-manager-list" data-sm-list></div>
      </div>
    </aside>
    <main class="skill-manager-detail">
      <div class="skill-manager-empty" data-sm-empty>${t('selectSkill')}</div>
      <div data-sm-detail hidden>
        <div class="skill-manager-detail-header">
          <h2 class="skill-manager-detail-name" data-sm-text="detail-name"></h2>
          <p class="skill-manager-detail-description" data-sm-text="detail-description"></p>
          <div class="skill-manager-badges" data-sm-badges></div>
        </div>
        <div class="skill-manager-detail-actions">
          <button class="skill-manager-button" type="button" data-sm-action="toggle"></button>
          <button class="skill-manager-button" type="button" data-sm-action="trust"></button>
          <button class="skill-manager-button skill-manager-button-danger" type="button" data-sm-action="delete"><i class="ri-delete-bin-line" aria-hidden="true"></i><span>${t('delete')}</span></button>
        </div>

        <p class="skill-manager-muted" data-sm-text="trust-note">${t('trustNote')}</p>
        <p class="skill-manager-muted">${t('scriptBoundaryNote')}</p>

        <section class="skill-manager-section">
          <h3 class="skill-manager-section-title">${t('metadata')}</h3>
          <div class="skill-manager-grid" data-sm-metadata></div>
        </section>

        <section class="skill-manager-section">
          <h3 class="skill-manager-section-title">${t('source')}</h3>
          <div class="skill-manager-grid" data-sm-source></div>
        </section>

        <section class="skill-manager-section">
          <h3 class="skill-manager-section-title">${t('resources')}</h3>
          <ul class="skill-manager-list-plain" data-sm-resources></ul>
        </section>

        <section class="skill-manager-section">
          <h3 class="skill-manager-section-title">${t('diagnostics')}</h3>
          <ul class="skill-manager-list-plain" data-sm-diagnostics></ul>
        </section>

        <section class="skill-manager-section">
          <button class="skill-manager-button" type="button" data-sm-action="preview"><i class="ri-file-text-line" aria-hidden="true"></i><span>${t('preview')}</span></button>
          <div class="skill-manager-preview" data-sm-preview>
            <textarea class="skill-manager-preview-text" readonly spellcheck="false" data-sm-preview-text></textarea>
          </div>
        </section>
      </div>
    </main>
  </div>
</div>`;
  }

  function getRoot() {
    return document.getElementById(ROOT_ID);
  }

  function isActive(sessionId) {
    return state && state.sessionId === sessionId && activeSessionId === sessionId && getRoot();
  }

  function query(selector) {
    const root = getRoot();
    return root ? root.querySelector(selector) : null;
  }

  function queryAll(selector) {
    const root = getRoot();
    return root ? Array.from(root.querySelectorAll(selector)) : [];
  }

  function setText(selector, value) {
    const node = query(selector);
    if (node) node.textContent = value == null || value === '' ? '' : String(value);
  }

  function setStatus(message, type) {
    const node = query('[data-sm-text="status"]');
    if (!node) return;
    node.textContent = message || '';
    node.classList.toggle('skill-manager-status-error', type === 'error');
    node.classList.toggle('skill-manager-status-success', type === 'success');
  }

  function setBusy(isBusy) {
    queryAll('button, input').forEach((node) => {
      if (node.dataset.smAction === 'close') return;
      node.disabled = Boolean(isBusy);
    });
  }

  async function readResponse(response) {
    const contentType = response.headers.get('content-type') || '';
    let payload = null;
    if (contentType.includes('application/json')) {
      payload = await response.json().catch(() => null);
    }
    if (payload === null) {
      const text = await response.text().catch(() => '');
      payload = text ? { error: text } : {};
    }
    if (!response.ok || payload.success === false) {
      const error = new Error(payload.error || response.statusText || t('actionFailed'));
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  async function apiFetch(url, options) {
    const response = await fetch(url, options);
    return readResponse(response);
  }

  function escapeMarkdownText(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\\/g, '\\\\')
      .replace(/([`*_{}\[\]()#+\-.!|])/g, '\\$1');
  }

  function cleanUrlToken(value) {
    return String(value || '').replace(/[),.;!?，。！？、]+$/u, '');
  }

  const GITHUB_REPO_SHORTHAND_RE = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}[A-Za-z0-9])?\/[A-Za-z0-9._-]{1,100}$/;

  function normalizeGithubSkillUrl(value) {
    const cleaned = cleanUrlToken(value).trim();
    if (!cleaned) return '';
    if (GITHUB_REPO_SHORTHAND_RE.test(cleaned)) {
      return `https://github.com/${cleaned}`;
    }
    return cleaned;
  }

  function isGithubSkillUrl(value) {
    const normalized = normalizeGithubSkillUrl(value);
    if (!normalized) return false;
    try {
      const url = new URL(normalized);
      if (url.protocol !== 'https:') return false;
      const host = url.hostname.toLowerCase();
      const parts = url.pathname.split('/').filter(Boolean);
      if (host === 'raw.githubusercontent.com') {
        return /(^|\/)SKILL\.md$/i.test(url.pathname);
      }
      if (host !== 'github.com') return false;
      if (parts.length === 2) return true;
      const kind = parts[2];
      return (kind === 'blob' || kind === 'tree') && (kind === 'tree' || /(^|\/)SKILL\.md$/i.test(url.pathname));
    } catch {
      return false;
    }
  }

  function extractGithubSkillUrls(message, parsedUrl) {
    const urls = [];
    const seen = new Set();
    const addUrl = (value) => {
      const cleaned = normalizeGithubSkillUrl(value);
      if (!cleaned || seen.has(cleaned) || !isGithubSkillUrl(cleaned)) return;
      seen.add(cleaned);
      urls.push(cleaned);
    };

    const matches = String(message || '').match(/\bhttps?:\/\/[^\s<>"'`)\]]+/gi) || [];
    matches.forEach(addUrl);
    const shorthandMatches = String(message || '').match(/(?:^|[\s([<{])([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}[A-Za-z0-9])?\/[A-Za-z0-9._-]{1,100})(?=$|[\s)\]}>.,;!?，。！？、])/g) || [];
    shorthandMatches.forEach((match) => addUrl(match.trim().replace(/^[([<{]+/, '')));
    if (parsedUrl?.url) addUrl(parsedUrl.url);
    return urls;
  }

  function hasInstallIntent(message) {
    const text = String(message || '').trim();
    if (!text) return false;
    const intentText = text.replace(/\bhttps?:\/\/[^\s<>"'`)\]]+/gi, '');
    const questionLike = /(怎么|如何|怎样|能不能.*安装|可以.*安装.*吗|能.*安装.*吗|how\s+to|can\s+i|could\s+i|should\s+i|\?|？)/i;
    if (questionLike.test(intentText)) return false;
    const english = /\b(?:please\s+)?(?:reinstall|install|add)\s+(?:this\s+)?skill\b|\b(?:reinstall|install|add)\s+skill\b/i;
    const chinese = /(安装这个\s*skill|安装这个技能|重新安装这个\s*skill|重新安装这个技能|把这个\s*skill\s*装上|装上这个\s*skill|添加这个\s*skill|添加这个技能)/i;
    return english.test(text) || chinese.test(text);
  }

  function shouldOverwriteFromMessage(message) {
    return /\b(?:overwrite|reinstall)\b|覆盖|重新安装/i.test(String(message || ''));
  }

  function formatSource(source, fallbackUrl) {
    if (!source || typeof source !== 'object') return fallbackUrl || '-';
    return source.url || [source.owner, source.repo, source.ref, source.path].filter(Boolean).join('/') || fallbackUrl || '-';
  }

  function formatDiagnostics(diagnostics) {
    if (!Array.isArray(diagnostics) || diagnostics.length === 0) return '';
    return diagnostics.map(item => `  - ${escapeMarkdownText(item)}`).join('\n');
  }

  function buildInstallSuccessMessage(payload, sourceUrl) {
    const skill = payload?.skill || {};
    const diagnostics = formatDiagnostics(skill.diagnostics || payload?.diagnostics);
    const lines = [
      `**${escapeMarkdownText(t('chatInstallSuccess'))}**`,
      '',
      `- ${escapeMarkdownText(t('chatSkillName'))}: ${escapeMarkdownText(skill.name || '-')}`,
      `- ${escapeMarkdownText(t('chatSkillDescription'))}: ${escapeMarkdownText(skill.description || '-')}`,
      `- ${escapeMarkdownText(t('chatSkillSource'))}: ${escapeMarkdownText(formatSource(skill.source, sourceUrl))}`,
      `- ${escapeMarkdownText(t('chatSkillEnabled'))}: ${escapeMarkdownText(skill.enabled === false ? t('disabled') : t('enabled'))}`
    ];
    if (skill.name) {
      lines.push(`- ${escapeMarkdownText(t('chatSkillUsage'))}: ${escapeMarkdownText(`/${skill.name}`)}`);
    }
    if (diagnostics) {
      lines.push(`- ${escapeMarkdownText(t('chatSkillDiagnostics'))}:`);
      lines.push(diagnostics);
    }
    return lines.join('\n');
  }

  function buildInstallFailureMessage(error) {
    const detail = error?.message || t('actionFailed');
    return `**${escapeMarkdownText(t('chatInstallFailed'))}**\n\n${escapeMarkdownText(detail)}`;
  }

  async function handleSendIntercept(context) {
    if (!context || context.signal?.aborted) return null;

    const message = context.message || '';
    if (!hasInstallIntent(message)) return null;

    const urls = extractGithubSkillUrls(message, context.parsedUrl);
    if (urls.length === 0) return null;
    if (urls.length > 1) {
      return {
        success: true,
        handled: true,
        userMessage: message,
        assistantMessage: escapeMarkdownText(t('chatMultipleUrls')),
        clearInput: true,
        clearAttachments: true,
        clearActiveSkills: true
      };
    }

    try {
      const payload = await apiFetch('/api/skills/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: context.signal,
        body: JSON.stringify({
          source_url: urls[0],
          overwrite: shouldOverwriteFromMessage(message),
          enabled: true
        })
      });
      return {
        success: true,
        handled: true,
        userMessage: message,
        assistantMessage: buildInstallSuccessMessage(payload, urls[0]),
        clearInput: true,
        clearAttachments: true,
        clearActiveSkills: true,
        refreshSkillCatalog: true
      };
    } catch (error) {
      if (error?.name === 'AbortError') throw error;
      return {
        success: true,
        handled: true,
        userMessage: message,
        assistantMessage: buildInstallFailureMessage(error),
        clearInput: true,
        clearAttachments: true,
        clearActiveSkills: true
      };
    }
  }

  function appendBadge(container, text, className) {
    const badge = document.createElement('span');
    badge.className = `skill-manager-badge ${className || ''}`.trim();
    badge.textContent = text;
    container.appendChild(badge);
  }

  function appendListItem(list, text) {
    const item = document.createElement('li');
    item.textContent = text;
    list.appendChild(item);
  }

  function appendKeyValue(container, key, value) {
    const wrapper = document.createElement('div');
    wrapper.className = 'skill-manager-kv';

    const keyNode = document.createElement('span');
    keyNode.className = 'skill-manager-kv-key';
    keyNode.textContent = key;

    const valueNode = document.createElement('span');
    valueNode.className = 'skill-manager-kv-value';
    valueNode.textContent = value == null || value === '' ? '-' : String(value);

    wrapper.appendChild(keyNode);
    wrapper.appendChild(valueNode);
    container.appendChild(wrapper);
  }

  function sourceLabel(source) {
    if (!source || typeof source !== 'object') return 'unknown';
    if (source.type === 'github') {
      const repo = [source.owner, source.repo].filter(Boolean).join('/');
      const path = [source.ref, source.path].filter(Boolean).join(':');
      return [repo, path].filter(Boolean).join(' @ ') || source.url || 'github';
    }
    if (source.type === 'upload') return source.filename || 'upload';
    return source.type || 'unknown';
  }

  function normalizeSkills(skills) {
    return Array.isArray(skills)
      ? skills.filter((skill) => skill && typeof skill.name === 'string')
      : [];
  }

  async function loadSkills(sessionId, preferredName) {
    const requestId = ++requestSeq;
    setStatus(t('loading'));
    try {
      const data = await apiFetch('/api/skills?include_disabled=true');
      if (!isActive(sessionId) || requestId !== requestSeq) return;
      state.skills = normalizeSkills(data.skills).sort((a, b) => a.name.localeCompare(b.name));
      renderSkillList();

      const nextName = preferredName || state.selectedName || state.skills[0]?.name || '';
      if (nextName) {
        await selectSkill(nextName, sessionId);
      } else {
        state.selectedName = '';
        state.selectedDetail = null;
        renderDetail();
      }
      setStatus('');
    } catch (error) {
      if (!isActive(sessionId) || requestId !== requestSeq) return;
      console.error('[SkillManager] Failed to load skills:', error);
      setStatus(`${t('loadFailed')}: ${error.message}`, 'error');
      renderSkillList();
      renderDetail();
    }
  }

  async function selectSkill(skillName, sessionId) {
    if (!skillName || !isActive(sessionId)) return;
    state.selectedName = skillName;
    state.previewVisible = false;
    state.previewText = '';
    renderSkillList();
    renderDetail();

    const requestId = ++requestSeq;
    setStatus(t('loading'));
    try {
      const detail = await apiFetch(`/api/skills/${encodeURIComponent(skillName)}`);
      if (!isActive(sessionId) || requestId !== requestSeq) return;
      state.selectedDetail = detail;
      renderDetail();
      setStatus('');
    } catch (error) {
      if (!isActive(sessionId) || requestId !== requestSeq) return;
      console.error('[SkillManager] Failed to load skill detail:', error);
      setStatus(`${t('actionFailed')}: ${error.message}`, 'error');
      state.selectedDetail = null;
      renderDetail();
    }
  }

  function renderSkillList() {
    const list = query('[data-sm-list]');
    if (!list) return;
    list.replaceChildren();

    if (!state.skills.length) {
      const empty = document.createElement('p');
      empty.className = 'skill-manager-muted';
      empty.textContent = t('emptyList');
      list.appendChild(empty);
      return;
    }

    state.skills.forEach((skill) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'skill-manager-list-item';
      button.dataset.skillName = skill.name;
      if (skill.name === state.selectedName) {
        button.classList.add('skill-manager-list-item-active');
      }

      const name = document.createElement('span');
      name.className = 'skill-manager-list-name';
      name.textContent = skill.name;
      button.appendChild(name);

      const badges = document.createElement('span');
      badges.className = 'skill-manager-list-badges';
      appendBadge(badges, skill.enabled ? t('enabled') : t('disabled'), skill.enabled ? 'skill-manager-badge-success' : 'skill-manager-badge-warning');
      appendBadge(badges, skill.trusted ? t('trusted') : t('untrusted'), skill.trusted ? 'skill-manager-badge-success' : '');
      if (Array.isArray(skill.diagnostics) && skill.diagnostics.length) {
        appendBadge(badges, `${t('diagnostics')}: ${skill.diagnostics.length}`, 'skill-manager-badge-warning');
      }
      button.appendChild(badges);

      button.addEventListener('click', () => {
        selectSkill(skill.name, state.sessionId);
      });
      list.appendChild(button);
    });
  }

  function renderDetail() {
    const empty = query('[data-sm-empty]');
    const detail = query('[data-sm-detail]');
    const selected = state.selectedDetail;
    if (!empty || !detail) return;

    if (!selected) {
      empty.hidden = false;
      detail.hidden = true;
      empty.textContent = state.selectedName ? t('loading') : t('selectSkill');
      return;
    }

    empty.hidden = true;
    detail.hidden = false;
    setText('[data-sm-text="detail-name"]', selected.name);
    setText('[data-sm-text="detail-description"]', selected.description || '');

    const toggleButton = query('[data-sm-action="toggle"]');
    if (toggleButton) {
      toggleButton.textContent = selected.enabled ? t('disableAction') : t('enableAction');
    }
    const trustButton = query('[data-sm-action="trust"]');
    if (trustButton) {
      trustButton.textContent = selected.trusted ? t('untrustAction') : t('trustAction');
    }

    const badges = query('[data-sm-badges]');
    if (badges) {
      badges.replaceChildren();
      appendBadge(badges, selected.enabled ? t('enabled') : t('disabled'), selected.enabled ? 'skill-manager-badge-success' : 'skill-manager-badge-warning');
      appendBadge(badges, selected.trusted ? t('trusted') : t('untrusted'), selected.trusted ? 'skill-manager-badge-success' : '');
      const source = sourceLabel(selected.source);
      appendBadge(badges, source, '');
      if (Array.isArray(selected.diagnostics) && selected.diagnostics.length) {
        appendBadge(badges, `${t('diagnostics')}: ${selected.diagnostics.length}`, 'skill-manager-badge-warning');
      }
    }

    renderMetadata(selected);
    renderSource(selected.source);
    renderResources(selected.resources);
    renderDiagnostics(selected.diagnostics);
    renderPreview();
  }

  function renderMetadata(skill) {
    const container = query('[data-sm-metadata]');
    if (!container) return;
    container.replaceChildren();
    appendKeyValue(container, t('license'), skill.license || '-');
    appendKeyValue(container, t('installedAt'), skill.installed_at || '-');
    appendKeyValue(container, t('updatedAt'), skill.updated_at || '-');

    const metadata = skill.metadata && typeof skill.metadata === 'object' ? skill.metadata : {};
    const entries = Object.entries(metadata);
    if (!entries.length) {
      appendKeyValue(container, t('metadata'), t('noMetadata'));
      return;
    }
    entries.forEach(([key, value]) => {
      appendKeyValue(container, key, Array.isArray(value) ? value.join(', ') : value);
    });
  }

  function renderSource(source) {
    const container = query('[data-sm-source]');
    if (!container) return;
    container.replaceChildren();
    const sourceData = source && typeof source === 'object' ? source : {};
    const entries = Object.entries(sourceData);
    if (!entries.length) {
      appendKeyValue(container, t('source'), '-');
      return;
    }
    entries.forEach(([key, value]) => {
      appendKeyValue(container, key, typeof value === 'object' ? JSON.stringify(value) : value);
    });
  }

  function renderResources(resources) {
    const list = query('[data-sm-resources]');
    if (!list) return;
    list.replaceChildren();

    if (!resources || typeof resources !== 'object') {
      appendListItem(list, t('noResources'));
      return;
    }

    const byCategory = resources.by_category && typeof resources.by_category === 'object' ? resources.by_category : {};
    const entries = Object.entries(byCategory).filter(([, count]) => Number(count) > 0);
    if (!entries.length && !resources.count) {
      appendListItem(list, t('noResources'));
      return;
    }
    entries.forEach(([category, count]) => {
      appendListItem(list, `${category}: ${count}`);
    });
    if (resources.count) {
      appendListItem(list, `total: ${resources.count}${resources.truncated ? ' (truncated)' : ''}`);
    }
  }

  function renderDiagnostics(diagnostics) {
    const list = query('[data-sm-diagnostics]');
    if (!list) return;
    list.replaceChildren();

    if (!Array.isArray(diagnostics) || diagnostics.length === 0) {
      appendListItem(list, t('noDiagnostics'));
      return;
    }
    diagnostics.forEach((item) => appendListItem(list, String(item)));
  }

  function renderPreview() {
    const wrapper = query('[data-sm-preview]');
    const textarea = query('[data-sm-preview-text]');
    const button = query('[data-sm-action="preview"] span');
    if (!wrapper || !textarea || !button) return;
    wrapper.classList.toggle('skill-manager-preview-visible', state.previewVisible);
    textarea.value = state.previewText || '';
    button.textContent = state.previewVisible ? t('hidePreview') : t('preview');
  }

  async function installFromGithub() {
    const sessionId = state?.sessionId;
    const input = query('#skill-manager-github-url');
    const overwrite = query('[data-sm-field="github-overwrite"]');
    const url = normalizeGithubSkillUrl(input?.value?.trim());
    if (!sessionId || !url) {
      input?.focus();
      return;
    }

    setBusy(true);
    setStatus(t('installing'));
    try {
      const data = await apiFetch('/api/skills/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_url: url,
          overwrite: Boolean(overwrite?.checked),
          enabled: true
        })
      });
      if (!isActive(sessionId)) return;
      const name = data.skill?.name || state.selectedName;
      if (input) input.value = '';
      showToast(t('installSuccess'), 'success');
      await loadSkills(sessionId, name);
      if (!isActive(sessionId)) return;
      setStatus(t('installSuccess'), 'success');
    } catch (error) {
      if (!isActive(sessionId)) return;
      console.error('[SkillManager] GitHub install failed:', error);
      if (error.status === 409) {
        setStatus(t('retryOverwrite'), 'error');
      } else {
        setStatus(`${t('actionFailed')}: ${error.message}`, 'error');
      }
    } finally {
      setBusy(false);
    }
  }

  async function uploadLocalSkill() {
    const sessionId = state?.sessionId;
    const input = query('#skill-manager-file-input');
    const overwrite = query('[data-sm-field="upload-overwrite"]');
    const file = state?.pendingUploadFile || input?.files?.[0];
    if (!sessionId || !file) {
      input?.focus();
      return;
    }
    state.pendingUploadFile = file;

    const form = new FormData();
    form.append('file', file);
    form.append('overwrite', overwrite?.checked ? 'true' : 'false');
    form.append('enabled', 'true');

    setBusy(true);
    setStatus(t('installing'));
    try {
      const data = await apiFetch('/api/skills/upload', {
        method: 'POST',
        body: form
      });
      if (!isActive(sessionId)) return;
      const name = data.skill?.name || state.selectedName;
      clearUploadInput();
      showToast(t('installSuccess'), 'success');
      await loadSkills(sessionId, name);
      if (!isActive(sessionId)) return;
      setStatus(t('installSuccess'), 'success');
    } catch (error) {
      if (!isActive(sessionId)) return;
      console.error('[SkillManager] Upload failed:', error);
      if (error.status === 409) {
        setStatus(t('retryOverwrite'), 'error');
      } else {
        clearUploadInput();
        setStatus(`${t('actionFailed')}: ${error.message}`, 'error');
      }
    } finally {
      setBusy(false);
    }
  }

  function clearUploadInput(clearFile) {
    const input = query('#skill-manager-file-input');
    const fileStatus = query('[data-sm-text="file-status"]');
    if (clearFile !== false) {
      state.pendingUploadFile = null;
      if (input) input.value = '';
    }
    if (fileStatus) {
      fileStatus.textContent = state.pendingUploadFile ? `${t('fileSelected')}: ${state.pendingUploadFile.name}` : t('noFile');
    }
  }

  async function toggleSelected() {
    const skill = state.selectedDetail;
    if (!skill) return;
    await updateSelected(`/api/skills/${encodeURIComponent(skill.name)}/toggle`, {
      enabled: !skill.enabled
    });
  }

  async function trustSelected() {
    const skill = state.selectedDetail;
    if (!skill) return;
    await updateSelected(`/api/skills/${encodeURIComponent(skill.name)}/trust`, {
      trusted: !skill.trusted
    });
  }

  async function updateSelected(url, body) {
    const sessionId = state?.sessionId;
    if (!sessionId) return;
    setBusy(true);
    setStatus(t('saving'));
    try {
      const data = await apiFetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!isActive(sessionId)) return;
      const previousDetail = state.selectedDetail || {};
      const nextDetail = data.skill || previousDetail;
      if (!nextDetail.resources && previousDetail.resources) {
        nextDetail.resources = previousDetail.resources;
      }
      state.selectedDetail = nextDetail;
      const index = state.skills.findIndex((item) => item.name === state.selectedDetail.name);
      if (index >= 0) state.skills[index] = state.selectedDetail;
      renderSkillList();
      renderDetail();
      setStatus(t('updateSuccess'), 'success');
    } catch (error) {
      if (!isActive(sessionId)) return;
      console.error('[SkillManager] Update failed:', error);
      setStatus(`${t('actionFailed')}: ${error.message}`, 'error');
    } finally {
      setBusy(false);
    }
  }

  async function deleteSelected() {
    const sessionId = state?.sessionId;
    const skill = state?.selectedDetail;
    if (!sessionId || !skill) return;
    if (!window.confirm(t('deletingConfirm'))) return;

    setBusy(true);
    setStatus(t('saving'));
    try {
      const data = await apiFetch(`/api/skills/${encodeURIComponent(skill.name)}`, {
        method: 'DELETE'
      });
      if (!isActive(sessionId)) return;
      showToast(data.warning || t('deleteSuccess'), data.warning ? 'info' : 'success');
      state.selectedName = '';
      state.selectedDetail = null;
      await loadSkills(sessionId);
      if (!isActive(sessionId)) return;
      setStatus(data.warning || t('deleteSuccess'), data.warning ? 'success' : 'success');
    } catch (error) {
      if (!isActive(sessionId)) return;
      console.error('[SkillManager] Delete failed:', error);
      setStatus(`${t('actionFailed')}: ${error.message}`, 'error');
    } finally {
      setBusy(false);
    }
  }

  async function togglePreview() {
    const skill = state.selectedDetail;
    if (!skill) return;

    if (state.previewVisible) {
      state.previewVisible = false;
      renderPreview();
      return;
    }

    if (state.previewText) {
      state.previewVisible = true;
      renderPreview();
      return;
    }

    const requestId = ++requestSeq;
    setStatus(t('loading'));
    try {
      const data = await apiFetch(`/api/skills/${encodeURIComponent(skill.name)}/content`);
      if (!isActive(state.sessionId) || requestId !== requestSeq) return;
      state.previewText = data.raw_text || '';
      state.previewVisible = true;
      renderPreview();
      setStatus('');
    } catch (error) {
      if (!isActive(state.sessionId) || requestId !== requestSeq) return;
      console.error('[SkillManager] Preview failed:', error);
      setStatus(`${t('previewFailed')}: ${error.message}`, 'error');
    }
  }

  function attachEvents(sessionId) {
    const root = getRoot();
    if (!root) return false;

    const closeButton = query('[data-sm-action="close"]');
    closeButton?.addEventListener('click', () => ChatRaw.ui.closeFullscreenModal());

    query('[data-sm-action="refresh"]')?.addEventListener('click', () => loadSkills(sessionId));
    query('[data-sm-action="github-install"]')?.addEventListener('click', installFromGithub);
    query('[data-sm-action="upload"]')?.addEventListener('click', uploadLocalSkill);
    query('[data-sm-action="toggle"]')?.addEventListener('click', toggleSelected);
    query('[data-sm-action="trust"]')?.addEventListener('click', trustSelected);
    query('[data-sm-action="delete"]')?.addEventListener('click', deleteSelected);
    query('[data-sm-action="preview"]')?.addEventListener('click', togglePreview);

    const fileInput = query('#skill-manager-file-input');
    fileInput?.addEventListener('change', () => {
      state.pendingUploadFile = fileInput.files?.[0] || null;
      clearUploadInput(false);
    });

    const githubInput = query('#skill-manager-github-url');
    githubInput?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        installFromGithub();
      }
    });

    return true;
  }

  function openManager() {
    injectStyles();
    const sessionId = activeSessionId + 1;
    activeSessionId = sessionId;
    requestSeq += 1;
    state = {
      sessionId,
      skills: [],
      selectedName: '',
      selectedDetail: null,
      previewVisible: false,
      previewText: '',
      pendingUploadFile: null
    };

    ChatRaw.ui.openFullscreenModal({
      content: buildModalContent(),
      closable: true,
      onClose: () => {
        if (state?.sessionId === sessionId) {
          activeSessionId += 1;
          state = null;
        }
      }
    }, PLUGIN_ID);

    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        if (!isActive(sessionId)) return;
        if (!attachEvents(sessionId)) return;
        loadSkills(sessionId);
      });
    });
  }

  ChatRaw.ui.registerToolbarButton({
    id: 'skill-manager-open',
    icon: 'ri-sparkling-2-line',
    label: {
      en: 'Skill Manager',
      zh: 'Skill 管理器'
    },
    onClick: openManager,
    order: 30
  }, PLUGIN_ID);

  ChatRaw.hooks?.register?.('send_intercept', {
    priority: 100,
    handler: handleSendIntercept
  });

})(window.ChatRawPlugin);
