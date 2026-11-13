/* Browser-side Agent bindings, run replay, and interaction state. */
window.ChatRawAgents = (() => {
    const ids = new Set(['hermes', 'codex', 'claude', 'pi', 'deepseek']);
    const terminal = new Set(['completed', 'failed', 'cancelled', 'interrupted']);
    const segment = encodeURIComponent;
    const chatPath = chat => '/api/chats/' + segment(chat) + '/agent';
    const runPath = run => '/api/agents/runs/' + segment(run);
    const pendingKey = chat => 'chatraw-agent-admission:' + chat;
    const draftKey = chat => 'chatraw-agent-draft:' + chat;
    const attachmentRefs = files => files.map(({ attachment_id }) => ({ attachment_id }));

    function saveDraft(chat, text, attachments) {
        if (text || attachments.length) sessionStorage.setItem(draftKey(chat), JSON.stringify({ text, attachments }));
        else sessionStorage.removeItem(draftKey(chat));
    }

    const words = {
        en: {
            remove: 'Remove', openChats: 'Open chats', chatShort: 'Chat', agentMode: 'Chat mode', ordinary: 'Ordinary chat', agentPlugins: 'Manage Agent plugins',
            mode: 'Agent and workspace', managed: 'Managed workspace', workspace: 'Workspace', apply: 'Apply',
            newBinding: 'Start a new chat with this selection? This chat keeps its current Agent and workspace.',
            bindingFailed: 'Could not load this chat’s mode. Reload the chat before sending.',
            busy: 'A run is active. Your draft will stay here.', bindingLocked: 'A run is active in this chat. Stop it or wait for it to finish before deleting the chat.',
            admissionUnknown: 'Agent receipt is unconfirmed. Your draft is still here.',
            verify: 'Check request status', rejected: 'The Agent did not receive the request. You can send it again.',
            noReady: 'Agent unavailable', noFiles: 'This Agent does not accept this attachment type.',
            attach: 'Attach files', attachments: 'Attachments', compact: 'Compress Agent context',
            noCompact: 'This Agent does not support context compression.', run: 'Agent run',
            queued: 'Queued', running: 'Running', waiting_input: 'Waiting for answers', waiting_approval: 'Waiting for approval',
            stopping: 'Stopping', completed: 'Completed', failed: 'Failed', cancelled: 'Cancelled',
            interrupted: 'Interrupted', unknown: 'Status unconfirmed', reconnecting: 'Connection interrupted. Reconnecting…',
            model: 'Model', provider: 'Provider', reasoning: 'Reasoning', reasoning_effort: 'Reasoning effort',
            nativeDefault: 'Agent default', updatePlugin: 'Update plugin',
            settingsUnavailable: 'Could not load editable settings. Check the execution service and retry.',
            noEditableSettings: 'This Agent has no browser-editable settings.',
            check: 'Check Agent', checking: 'Checking…', ready: 'Ready', unconfigured: 'Configuration needed', unavailable: 'Unavailable',
            program: 'Program', protocol: 'Protocol', authentication: 'Authentication', model_request: 'Model request',
            passed: 'Passed', not_checked: 'Not checked', hostSettings: 'Executable, authentication, and project access are managed on the execution host.',
            details: 'Run details', tools: 'Tools', artifacts: 'Files from this run', usage: 'Usage',
            detailsLoading: 'Loading run details…', detailsEmpty: 'No additional details for this run.',
            detailsPending: 'No additional details yet.',
            detailsReconnecting: 'Could not load all run details. Reconnecting…',
            detailsUnavailable: 'Could not load run details. Reload the chat to try again.',
            inputTokens: 'Input tokens', outputTokens: 'Output tokens', cost: 'Cost',
            question: 'Question', approval: 'Approval', plan: 'Plan review', answer: 'Answer',
            custom: 'Write an answer', recommended: 'Recommended', decision: 'Select a decision',
            submit: 'Send response', cancelRequest: 'Cancel request', accepted: 'Response accepted',
            expired: 'Request expired', invalidated: 'Request is no longer active', answered: 'Answered',
            replyUnknown: 'Response status is unconfirmed. Checking the current request.',
            tool: 'Tool', command: 'Command', host: 'Host', paths: 'Paths',
            keepDraft: 'Finish uploading before sending.', uploadFailed: 'Could not attach the file.'
        },
        zh: {
            remove: '移除', openChats: '打开聊天列表', chatShort: '聊天', agentMode: '聊天模式', ordinary: '普通聊天', agentPlugins: '管理 Agent 插件',
            mode: 'Agent 和工作目录', managed: '独立工作目录', workspace: '工作目录', apply: '应用',
            newBinding: '使用此选择创建新聊天？当前聊天会保留原有的 Agent 和工作目录。',
            bindingFailed: '无法读取此聊天的模式。请重新载入聊天后再发送。',
            busy: '任务仍在执行，草稿会保留在这里。', bindingLocked: '此聊天有未结束的任务。请先停止任务或等待任务结束，再删除聊天。',
            admissionUnknown: 'Agent 是否已接收请求仍待核实，草稿已保留。',
            verify: '核实请求状态', rejected: 'Agent 未接收此请求，可以重新发送。',
            noReady: 'Agent 当前不可用', noFiles: '此 Agent 不支持该附件类型。',
            attach: '添加附件', attachments: '附件', compact: '压缩 Agent 上下文',
            noCompact: '此 Agent 不支持压缩上下文。', run: 'Agent 任务',
            queued: '排队中', running: '执行中', waiting_input: '等待回答', waiting_approval: '等待审批',
            stopping: '正在停止', completed: '已完成', failed: '失败', cancelled: '已取消',
            interrupted: '已中断', unknown: '状态待核实', reconnecting: '连接中断，正在重新连接…',
            model: '模型', provider: '服务商', reasoning: '推理', reasoning_effort: '推理强度',
            nativeDefault: 'Agent 默认值', updatePlugin: '更新插件',
            settingsUnavailable: '无法读取可编辑设置。请检查执行服务后重试。',
            noEditableSettings: '此 Agent 没有可在浏览器中修改的设置。',
            check: '检查 Agent', checking: '正在检查…', ready: '就绪', unconfigured: '需要配置', unavailable: '不可用',
            program: '程序', protocol: '协议', authentication: '认证', model_request: '模型请求',
            passed: '通过', not_checked: '未检查', hostSettings: '可执行程序、认证和项目访问权限由执行主机管理。',
            details: '任务详情', tools: '工具', artifacts: '本次任务生成的文件', usage: '用量',
            detailsLoading: '正在加载任务详情…', detailsEmpty: '本轮没有额外详情。',
            detailsPending: '暂无额外详情。',
            detailsReconnecting: '未能加载全部任务详情，正在重新连接…',
            detailsUnavailable: '无法加载任务详情，请重新载入聊天后重试。',
            inputTokens: '输入 token', outputTokens: '输出 token', cost: '费用',
            question: '问题', approval: '审批', plan: '计划确认', answer: '回答',
            custom: '填写自定义答案', recommended: '建议选项', decision: '选择处理方式',
            submit: '提交回复', cancelRequest: '取消请求', accepted: '已接收回复',
            expired: '请求已过期', invalidated: '请求已失效', answered: '已回答',
            replyUnknown: '回复结果待核实，正在查询当前请求。',
            tool: '工具', command: '命令', host: '主机', paths: '路径',
            keepDraft: '请等待附件上传完成。', uploadFailed: '无法添加附件。'
        }
    };

    function errorMessage(body, fallback) {
        const detail = body?.message || body?.error?.message || body?.detail?.message || body?.error || body?.detail;
        return typeof detail === 'string' && detail ? detail : fallback;
    }

    class RequestError extends Error {
        constructor(response, body) {
            super(errorMessage(body, response.statusText));
            this.status = response.status;
        }
    }

    async function request(url, { method = 'GET', body, signal } = {}) {
        const response = await fetch(url, {
            method, signal,
            ...(body instanceof FormData ? { body } : body === undefined ? {} : {
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new RequestError(response, data);
        return data;
    }

    async function stream(run, signal, onOpen, onEvent) {
        const response = await fetch(runPath(run.id) + '/events?after=' + run.seq, { signal });
        if (!response.ok) throw new RequestError(response, await response.json().catch(() => ({})));
        onOpen();
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        try {
            while (!signal.aborted) {
                const { value, done } = await reader.read();
                buffer += decoder.decode(value, { stream: !done });
                const lines = buffer.split('\n');
                buffer = done ? '' : lines.pop();
                for (const line of lines) {
                    if (line.trim() && onEvent(JSON.parse(line)) === false) return;
                }
                if (done) return;
            }
        } finally {
            await reader.cancel().catch(() => {});
        }
    }

    function retryDelay(ms, signal) {
        return new Promise(resolve => {
            if (signal.aborted) return resolve();
            const finish = () => {
                clearTimeout(timer);
                signal.removeEventListener('abort', finish);
                resolve();
            };
            const timer = setTimeout(finish, ms);
            signal.addEventListener('abort', finish, { once: true });
        });
    }

    function requestId() {
        return Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
    }

    const settingTypes = new Set(['string', 'integer', 'number', 'boolean']);
    const settingInputValue = (schema, value) => value == null ? '' :
        (schema.enum ? JSON.stringify(value) : String(value));

    function newInteraction(data) {
        return {
            data, open: false, outcome: '', answerSummary: '', submitting: false, sent: false,
            uncertain: false, error: '', decision: '',
            answers: (data.questions || []).map(question => ({ question_id: question.id, option_ids: [], text: '', custom: false }))
        };
    }

    function updateInteraction(run, data) {
        let interaction = run.interactions.find(item => item.data.interaction_id === data.interaction_id);
        if (!interaction) {
            run.interactions.push(newInteraction(data));
            interaction = run.interactions[run.interactions.length - 1];
        } else {
            interaction.data = data;
        }
        return interaction;
    }

    function applySnapshot(run, snapshot) {
        run.status = snapshot.status;
        run.error = snapshot.error?.message || '';
        run.authoritySeq = snapshot.last_seq;
        for (const item of run.interactions) item.open = false;
        for (const data of snapshot.interactions) updateInteraction(run, data).open = true;
        run.authorized = true;
    }

    function applyEvent(run, event) {
        if (event.schema_version !== 1 || event.run_id !== run.id || event.session_id !== run.session ||
            !Number.isInteger(event.seq)) throw new Error('Invalid Agent event');
        if (event.seq <= run.seq) return true;
        if (event.seq !== run.seq + 1) throw new Error('Missing Agent events');
        const { data, type } = event;
        const authoritative = event.seq > run.authoritySeq;
        run.seq = event.seq;
        switch (type) {
        case 'status':
            if (authoritative) {
                run.status = data.status;
                run.reason = data.reason || '';
            }
            break;
        case 'text_delta':
            run.content += data.text;
            run.hasText = true;
            run.replaying = event.seq <= run.replayThrough;
            break;
        case 'reasoning_delta':
            run.reasoning += data.text;
            break;
        case 'tool_started':
        case 'tool_updated':
        case 'tool_completed': {
            const index = run.tools.findIndex(tool => tool.tool_call_id === data.tool_call_id);
            const tool = { ...run.tools[index], ...data };
            if (index < 0) run.tools.push(tool);
            else run.tools[index] = tool;
            break;
        }
        case 'interaction_requested': {
            const item = updateInteraction(run, data);
            if (authoritative) item.open = true;
            break;
        }
        case 'interaction_resolved': {
            const item = run.interactions.find(interaction => interaction.data.interaction_id === data.interaction_id);
            if (item) {
                if (authoritative) item.open = false;
                item.outcome = data.outcome;
                item.answerSummary = data.answer_summary || '';
            }
            break;
        }
        case 'artifact':
            if (!run.artifacts.some(artifact => artifact.artifact_id === data.artifact_id)) run.artifacts.push(data);
            break;
        case 'usage':
            run.usage = data;
            break;
        case 'error':
            run.error = data.message;
            break;
        case 'done':
            if (Object.prototype.hasOwnProperty.call(data, 'final_text')) {
                run.content = data.final_text;
                run.hasText = true;
            }
            run.error = data.error?.message || run.error;
            run.status = data.status;
            run.done = true;
            run.authorized = false;
            for (const item of run.interactions) item.open = false;
            return false;
        }
        return true;
    }

    function create() {
        const observers = new Map();
        const drafts = new Map();
        const submissions = new Map();
        let catalogRequest = 0;
        let healthRequest = 0;
        let navigation = 0;

        return {
            agentCatalog: [],
            agentCatalogError: '',
            agentRegistered: [],
            agentBinding: null,
            agentBindingError: '',
            agentViewLoading: false,
            agentMenu: false,
            agentMenuBusy: false,
            agentMenuChoice: '',
            agentProjectChoice: '',
            agentWorkspaces: [],
            agentWorkspaceError: '',
            agentRuns: [],
            agentAdmission: null,
            agentSubmitBusy: false,
            agentAttachments: [],
            agentUploads: 0,
            agentHealth: null,
            agentChecking: false,
            agentHealthError: '',
            agentSettingValues: {},
            agentSettingsSaving: false,
            agentSettingsError: '',
            agentSettingsLoading: false,
            agentInteraction: null,
            agentClock: Date.now(),

            at(key) {
                return words[this.lang]?.[key] || words.en[key] || key;
            },

            registerAgent(id) {
                const plugin = this.installedPlugins.find(item => item.id === id);
                const script = document.currentScript;
                if (!ids.has(id) || plugin?.agent?.id !== id ||
                    !script || new URL(script.src).pathname !== '/api/plugins/' + segment(id) + '/main.js') return false;
                if (!this.agentRegistered.includes(id)) this.agentRegistered.push(id);
                return true;
            },

            unregisterAgent(id) {
                this.agentRegistered = this.agentRegistered.filter(agent => agent !== id);
            },

            get agentId() {
                return this.agentBinding?.agent_id || null;
            },

            get agentInfo() {
                return this.agentCatalog.find(agent => agent.id === this.agentId);
            },

            get selectableAgents() {
                return this.agentCatalog.filter(agent => agent.installed && agent.enabled && this.agentRegistered.includes(agent.id));
            },

            get activeAgentRun() {
                const id = this.agentBinding?.active_run_id;
                return this.agentRuns.find(run => run.id === id && !run.done);
            },

            get agentBlocked() {
                return this.agentViewLoading || !!this.agentBindingError || !!this.agentAdmission ||
                    !!this.agentBinding?.active_run_id || this.agentSubmitBusy || this.agentUploads > 0;
            },

            get canSendAgent() {
                const agent = this.agentInfo;
                return !!agent?.enabled && agent.availability !== 'unconfigured' && agent.availability !== 'unavailable';
            },

            get showAgentStop() {
                return !!this.activeAgentRun && !!this.agentInfo?.capabilities?.cancel;
            },

            get canSendMessage() {
                return !!this.inputMessage.trim() && !this.agentBlocked && !this.agentMenuBusy &&
                    (!this.agentId || this.canSendAgent);
            },

            agentName(id) {
                const names = { hermes: 'Hermes', codex: 'Codex CLI', claude: 'Claude Code', pi: 'Pi', deepseek: 'DeepSeek Harness' };
                const plugin = this.installedPlugins.find(item => item.id === id);
                return this.getLocalizedText(plugin?.name, names[id] || this.at('ordinary'));
            },

            agentButtonName(id) {
                if (!id) return this.isMobileView ? this.at('chatShort') : this.at('ordinary');
                if (id === 'deepseek' && this.isMobileView) return 'DeepSeek';
                return this.agentName(id);
            },

            agentErrorMessage(body, fallback) {
                return errorMessage(body, fallback);
            },

            async loadAgentCatalog() {
                const id = ++catalogRequest;
                try {
                    const { agents } = await request('/api/agents');
                    if (id !== catalogRequest) return;
                    this.agentCatalog = agents.filter(agent => ids.has(agent.id));
                    this.agentCatalogError = '';
                } catch (error) {
                    if (id !== catalogRequest) return;
                    this.agentCatalogError = error.message || this.at('noReady');
                }
            },

            async openAgentMenu() {
                if (this.agentMenu) {
                    this.closeAgentMenu();
                    return;
                }
                this.closeCompletionMenu();
                this.showPluginMoreMenu = false;
                this.agentMenuChoice = this.agentId || '';
                const workspace = this.agentBinding?.workspace;
                this.agentProjectChoice = workspace?.kind === 'project' ? workspace.id : '';
                this.agentMenu = true;
                this.$nextTick(() => this.$refs.agentModePanel?.querySelector('input:checked')?.focus());
                this.loadAgentCatalog();
                try {
                    const { workspaces } = await request('/api/agents/workspaces');
                    this.agentWorkspaces = workspaces;
                    this.agentWorkspaceError = '';
                } catch (error) {
                    this.agentWorkspaceError = error.message;
                }
            },

            closeAgentMenu(restoreFocus = false) {
                this.agentMenu = false;
                if (restoreFocus) this.$refs.agentModeButton?.focus();
            },

            async applyAgentMode() {
                if (this.agentMenuBusy || this.agentViewLoading || this.agentBindingError || this.isGenerating) return;
                const id = this.agentMenuChoice || null;
                const project = id ? this.agentProjectChoice : '';
                const workspace = project ? { kind: 'project', id: project } : { kind: 'managed' };
                const old = this.agentBinding?.workspace;
                if (this.agentId === id && (old?.kind === 'project' ? old.id : '') === project) {
                    this.closeAgentMenu(true);
                    return;
                }
                let chat = this.currentChatId;
                const initialText = chat ? '' : this.inputMessage;
                const create = !chat || this.messages.length > 0 || this.agentBinding?.last_run_id || this.agentBlocked;
                if (chat && create && !confirm(this.at('newBinding'))) return;

                const nav = navigation;
                this.agentMenuBusy = true;
                try {
                    if (create) {
                        chat = (await request('/api/chats', { method: 'POST' })).id;
                        if (nav !== navigation) return;
                    }
                    await request(chatPath(chat), { method: 'PUT', body: { agent_id: id, workspace } });
                    if (nav !== navigation) return;
                    this.closeAgentMenu();
                    await Promise.all([this.loadChats(), this.selectChat(chat, true)]);
                    if (initialText && this.currentChatId === chat && !this.inputMessage) this.setComposerValue(initialText);
                } catch (error) {
                    if (nav === navigation) {
                        this.showToast(error.message, 'error');
                        if (error.status === 409 && chat === this.currentChatId) await this.selectChat(chat, true);
                        else if (create) await this.loadChats();
                    }
                } finally {
                    this.agentMenuBusy = false;
                }
            },

            persistAgentDraft(text = this.inputMessage) {
                if (this.agentId && this.agentBinding.chat_id === this.currentChatId) {
                    saveDraft(this.currentChatId, text, this.agentAttachments);
                }
            },

            rememberAgentDraft() {
                this.persistAgentDraft();
                drafts.set(this.currentChatId, {
                    text: this.inputMessage, attachments: [...this.agentAttachments],
                    document: this.attachedDocument, url: this.parsedUrl, urlTitle: this.parsedUrlTitle,
                    image: this.uploadedImage, imageBase64: this.uploadedImageBase64
                });
            },

            forgetAgentDraft(chat) {
                drafts.delete(chat);
                submissions.delete(chat);
                sessionStorage.removeItem(draftKey(chat));
                sessionStorage.removeItem(pendingKey(chat));
            },

            changeAgentView(chat) {
                const nav = ++navigation;
                for (const controller of observers.values()) controller.abort();
                observers.clear();
                this.closeAgentInteraction();
                this.closeAgentMenu();
                this.agentRuns = [];
                this.agentBinding = null;
                this.agentBindingError = '';
                this.agentViewLoading = !!chat;
                this.agentSubmitBusy = false;
                this.agentUploads = 0;
                this.agentAdmission = chat ? JSON.parse(sessionStorage.getItem(pendingKey(chat)) || 'null') : null;
                const draft = drafts.get(chat) || (chat && JSON.parse(sessionStorage.getItem(draftKey(chat)) || 'null'));
                this.agentAttachments = draft?.attachments || [];
                this.attachedDocument = draft?.document || null;
                this.parsedUrl = draft?.url || null;
                this.parsedUrlTitle = draft?.urlTitle || '';
                this.uploadedImage = draft?.image || null;
                this.uploadedImageBase64 = draft?.imageBase64 || '';
                this.showUrlInput = false;
                this.closeCompletionMenu();
                this.setComposerValue(draft?.text || '');
                return nav;
            },

            async loadAgentView(chat, nav) {
                try {
                    const binding = await request(chatPath(chat));
                    if (nav !== navigation) return;
                    if (binding.chat_id !== chat || !Object.prototype.hasOwnProperty.call(binding, 'agent_id')) {
                        throw new Error('Invalid Agent binding');
                    }
                    this.agentBinding = binding;
                } catch (error) {
                    if (nav === navigation) this.agentBindingError = this.at('bindingFailed');
                }
            },

            resumeAgentView(nav) {
                if (nav !== navigation) return;
                this.agentViewLoading = false;
                const binding = this.agentBinding;
                if (!binding?.agent_id) return;
                const runId = binding.active_run_id || binding.last_run_id;
                if (runId) this.showAgentRun(runId, { primary: true, restoring: true });
                if (this.agentAdmission) this.checkAgentAdmission();
            },

            showAgentRun(runId, { primary = false, restoring = true } = {}) {
                let run = this.agentRuns.find(item => item.id === runId);
                if (!run) {
                    this.agentRuns.push({
                        id: runId, chat: this.currentChatId, session: this.agentBinding.session_id, seq: 0,
                        authoritySeq: 0, replayThrough: 0, replaying: restoring, status: '',
                        content: '', hasText: false, reasoning: '', tools: [], interactions: [], artifacts: [],
                        usage: null, error: '', reason: '', done: false, connecting: true,
                        disconnected: false, authorized: false, stopPending: false, primary
                    });
                    run = this.agentRuns[this.agentRuns.length - 1];
                }
                if (primary) {
                    run.primary = true;
                    if (!this.messages.some(msg => msg.role === 'assistant' && msg.run_id === runId)) {
                        this.messages.push({ role: 'assistant', run_id: runId, content: '' });
                    }
                }
                if (!run.done && !observers.has(runId)) {
                    const controller = new AbortController();
                    observers.set(runId, controller);
                    this.observeAgentRun(run, restoring, controller);
                }
                return run;
            },

            async observeAgentRun(run, restoring, controller) {
                const { signal } = controller;
                let backoff = 300;
                let firstSnapshot = true;
                try {
                    while (!signal.aborted && !run.done) {
                        const before = run.seq;
                        try {
                            const snapshot = await request(runPath(run.id), { signal });
                            if (signal.aborted) return;
                            if (snapshot.run_id !== run.id || snapshot.chat_id !== run.chat || snapshot.session_id !== run.session ||
                                snapshot.last_seq < run.seq) throw new Error('Invalid Agent run snapshot');
                            applySnapshot(run, snapshot);
                            if (firstSnapshot && restoring) run.replayThrough = snapshot.last_seq;
                            firstSnapshot = false;
                            run.connecting = false;
                            await stream(run, signal, () => { run.disconnected = false; }, event => {
                                if (signal.aborted) return false;
                                const previous = run.seq;
                                const keepReading = applyEvent(run, event);
                                if (run.seq !== previous && event.type !== 'text_delta' && event.type !== 'reasoning_delta') {
                                    this.$nextTick(() => this.followStream());
                                }
                                return keepReading;
                            });
                            if (run.done) {
                                if (this.agentBinding?.active_run_id === run.id) {
                                    this.agentBinding.active_run_id = null;
                                    this.loadChats();
                                }
                                return;
                            }
                        } catch (error) {
                            if (signal.aborted) return;
                            run.error = error.message;
                        }
                        if (signal.aborted) return;
                        run.authorized = false;
                        run.disconnected = true;
                        backoff = run.seq > before ? 300 : Math.min(2 * backoff, 8000);
                        await retryDelay(backoff, signal);
                    }
                } finally {
                    if (observers.get(run.id) === controller) observers.delete(run.id);
                }
            },

            getMessageRun(message) {
                if (!message.run_id || message.role !== 'assistant') return null;
                return this.agentRuns.find(run => run.id === message.run_id) || null;
            },

            messageText(message) {
                const run = this.getMessageRun(message);
                return run?.hasText && (run.primary || run.done) ? run.content : message.content;
            },

            messageLive(message) {
                const run = this.getMessageRun(message);
                return !!(message.streaming || (run?.primary && !run.done));
            },

            openRunDetails(event, runId) {
                if (event.currentTarget.open && this.agentId) this.showAgentRun(runId);
            },

            runDetailsStatus(message) {
                const run = this.getMessageRun(message);
                if (!run) return this.at(this.agentId ? 'detailsLoading' : 'detailsUnavailable');
                if (run.disconnected) return this.at('detailsReconnecting');
                // A terminal snapshot can arrive before tools and resolved interactions are replayed.
                if (!run.done && (!run.authorized || run.seq < run.authoritySeq || terminal.has(run.status))) {
                    return this.at('detailsLoading');
                }
                const hasDetails = run.reasoning.trim() || run.tools.length ||
                    run.interactions.some(item => !item.open) || this.hasRunUsage(run);
                return hasDetails ? '' : this.at(run.done ? 'detailsEmpty' : 'detailsPending');
            },

            hasRunUsage(run) {
                const usage = run.usage;
                return usage?.input_tokens != null || usage?.output_tokens != null || usage?.cost != null;
            },

            get agentAttachmentAccept() {
                const capabilities = this.agentInfo?.capabilities;
                if (capabilities?.files) return null;
                return capabilities?.limits?.image_mime_types?.join(',') || 'image/*';
            },

            async uploadAgentAttachments(event) {
                const files = Array.from(event.target.files);
                event.target.value = '';
                const chat = this.currentChatId;
                const nav = navigation;
                if (!chat || this.agentBlocked) return;
                const caps = this.agentInfo?.capabilities || {};
                this.agentUploads++;
                try {
                    for (const file of files) {
                        if (nav !== navigation) return;
                        const mimeTypes = caps.limits?.image_mime_types;
                        const supported = file.type.startsWith('image/')
                            ? caps.images && (!mimeTypes || mimeTypes.includes(file.type))
                            : caps.files;
                        if (!supported) {
                            this.showToast(file.name + ' — ' + this.at('noFiles'), 'error');
                            continue;
                        }
                        const data = new FormData();
                        data.append('chat_id', chat);
                        data.append('file', file);
                        try {
                            const attachment = await request('/api/agents/attachments', { method: 'POST', body: data });
                            if (nav === navigation) {
                                this.agentAttachments.push(attachment);
                                this.persistAgentDraft();
                            }
                        } catch (error) {
                            if (nav === navigation) this.showToast(error.message || this.at('uploadFailed'), 'error');
                        }
                    }
                } finally {
                    if (nav === navigation) this.agentUploads--;
                }
            },

            removeAgentAttachment(id) {
                this.agentAttachments = this.agentAttachments.filter(item => item.attachment_id !== id);
                this.persistAgentDraft();
            },

            async sendAgentRun(operation = 'message') {
                if (this.agentUploads) return this.showToast(this.at('keepDraft'));
                if (this.agentBlocked) return this.showToast(this.at('busy'));
                const binding = this.agentBinding;
                const chat = this.currentChatId;
                if (!binding?.session_id || !this.canSendAgent) {
                    return this.showToast(this.agentInfo?.reason || this.at('noReady'), 'error');
                }
                if (operation === 'compact' && !this.agentInfo.capabilities?.compact) return this.showToast(this.at('noCompact'));

                const nav = navigation;
                const message = this.inputMessage;
                const files = [...this.agentAttachments];
                const attachments = attachmentRefs(files);
                if (operation === 'message' && !message.trim()) return;
                const submission = { message, attachments, operation, files };
                const admission = { id: requestId(), submission };
                sessionStorage.setItem(pendingKey(chat), JSON.stringify(admission));
                this.agentAdmission = admission;
                this.agentSubmitBusy = true;
                submissions.set(chat, submission);
                const url = operation === 'compact'
                    ? '/api/agents/sessions/' + segment(binding.session_id) + '/compact'
                    : '/api/agents/runs';
                const body = operation === 'compact' ? { client_request_id: admission.id } : {
                    chat_id: chat, client_request_id: admission.id, message, attachments
                };
                const controller = new AbortController();
                const timeout = setTimeout(() => controller.abort(), 20000);
                try {
                    const run = await request(url, { method: 'POST', body, signal: controller.signal });
                    if (!run.run_id) throw new Error(this.at('admissionUnknown'));
                    this.acceptAgentAdmission(chat, admission.id, run, nav);
                } catch (error) {
                    if (nav === navigation) await this.checkAgentAdmission(error);
                } finally {
                    clearTimeout(timeout);
                    if (nav === navigation) this.agentSubmitBusy = false;
                }
            },

            acceptAgentAdmission(chat, id, run, nav) {
                if (!run?.run_id) return;
                const stored = JSON.parse(sessionStorage.getItem(pendingKey(chat)) || 'null');
                if (stored?.id !== id) return;
                sessionStorage.removeItem(pendingKey(chat));
                const inFlight = submissions.has(chat);
                const submission = submissions.get(chat) || stored.submission;
                submissions.delete(chat);
                const current = nav === navigation;
                if (current) this.rememberAgentDraft();
                const draft = drafts.get(chat) || JSON.parse(sessionStorage.getItem(draftKey(chat)) || 'null');
                if (submission?.operation === 'message' && draft?.text === submission.message &&
                    JSON.stringify(attachmentRefs(draft.attachments)) === JSON.stringify(submission.attachments)) {
                    draft.text = '';
                    draft.attachments = [];
                    saveDraft(chat, '', []);
                    if (current) {
                        this.setComposerValue('');
                        this.agentAttachments = [];
                    }
                }
                if (!current) {
                    if (this.currentChatId === chat) this.selectChat(chat, true);
                    return;
                }
                this.agentAdmission = null;
                this.agentBinding.last_run_id = run.run_id;
                this.agentBinding.active_run_id = run.run_id;
                if (submission?.operation === 'message' && !this.messages.some(msg => msg.role === 'user' && msg.run_id === run.run_id)) {
                    this.messages.push({ role: 'user', run_id: run.run_id, content: submission.message, attachments: submission.files });
                }
                this.showAgentRun(run.run_id, { primary: true, restoring: !inFlight });
                this.$nextTick(() => this.scrollToBottom());
                this.loadChats();
            },

            async checkAgentAdmission(postError = null) {
                const admission = this.agentAdmission;
                if (!admission || admission.checking) return;
                const chat = this.currentChatId;
                const nav = navigation;
                admission.checking = true;
                try {
                    const query = new URLSearchParams({ chat_id: chat, client_request_id: admission.id });
                    const data = await request('/api/agents/runs?' + query);
                    if (nav !== navigation || this.agentAdmission?.id !== admission.id) return;
                    if (data.admission === 'accepted' && data.run?.run_id) {
                        if (!submissions.has(chat)) await this.loadMessages(chat);
                        if (nav === navigation) this.acceptAgentAdmission(chat, admission.id, data.run, nav);
                    } else if (data.admission === 'not_found' && !this.agentSubmitBusy) {
                        sessionStorage.removeItem(pendingKey(chat));
                        submissions.delete(chat);
                        this.agentAdmission = null;
                        this.showToast(this.at('rejected'));
                    } else if (data.admission === 'not_found' && postError) {
                        sessionStorage.removeItem(pendingKey(chat));
                        submissions.delete(chat);
                        this.agentAdmission = null;
                        this.showToast(postError.message || this.at('rejected'), 'error');
                    }
                } catch (error) {
                    if (nav === navigation) this.showToast(error.message || this.at('admissionUnknown'), 'error');
                } finally {
                    admission.checking = false;
                }
            },

            async stopAgentRun() {
                const run = this.activeAgentRun;
                if (!run || run.stopPending || run.status === 'stopping' || !this.agentInfo?.capabilities?.cancel) return;
                run.stopPending = true;
                try {
                    const response = await request(runPath(run.id) + '/cancel', { method: 'POST' });
                    if (!run.done && response.status === 'stopping') run.status = 'stopping';
                } catch (error) {
                    this.showToast(error.message, 'error');
                } finally {
                    run.stopPending = false;
                }
            },

            artifactUrl(id) {
                return '/api/agents/artifacts/' + segment(id);
            },

            openAgentInteraction(run, interaction) {
                this.agentClock = Date.now();
                this.agentInteraction = { run, interaction };
                this.$nextTick(() => {
                    const dialog = this.$refs.agentDialog;
                    if (this.agentInteraction && !dialog.open) dialog.showModal();
                });
            },

            closeAgentInteraction() {
                const dialog = this.$refs.agentDialog;
                if (dialog?.open) dialog.close();
                this.agentInteraction = null;
            },

            interactionStatus(item, run) {
                if (item.outcome) return this.at(item.outcome);
                if (item.error) return item.error;
                if (item.data.expires_at && Date.parse(item.data.expires_at) <= this.agentClock) return this.at('expired');
                if (item.uncertain) return this.at('replyUnknown');
                if (item.sent) return this.at('accepted');
                if (!item.open) return this.at('invalidated');
                if (run?.status === 'stopping' || run?.status === 'unknown') return this.at(run.status);
                if (run?.disconnected) return this.at('reconnecting');
                return '';
            },

            interactionActionable(run, item, now = this.agentClock) {
                return item.open && run.authorized && !run.disconnected && run.seq >= run.authoritySeq &&
                    !run.done && !terminal.has(run.status) && run.status !== 'stopping' && run.status !== 'unknown' &&
                    !run.stopPending && !item.submitting && !item.sent && !item.uncertain &&
                    !(item.data.expires_at && Date.parse(item.data.expires_at) <= now);
            },

            questionAnswer(item, id) {
                return item.answers.find(answer => answer.question_id === id);
            },

            selectQuestionOption(item, question, id, checked) {
                const answer = this.questionAnswer(item, question.id);
                if (question.type === 'single') {
                    answer.option_ids = [id];
                    answer.custom = false;
                    answer.text = '';
                } else {
                    answer.option_ids = checked
                        ? [...answer.option_ids, id]
                        : answer.option_ids.filter(option => option !== id);
                }
            },

            selectQuestionCustom(item, question, checked) {
                const answer = this.questionAnswer(item, question.id);
                answer.custom = checked;
                if (question.type === 'single') answer.option_ids = [];
                if (!checked) answer.text = '';
            },

            interactionReply(item) {
                if (item.data.kind === 'approval') {
                    return item.decision ? { decision_id: item.decision } : null;
                }
                const answers = [];
                for (const question of item.data.questions) {
                    const draft = this.questionAnswer(item, question.id);
                    const text = question.type === 'text' || draft.custom ? draft.text : '';
                    if (draft.custom && !text.trim()) return null;
                    if (!draft.option_ids.length && !text.trim()) {
                        if (question.required) return null;
                        continue;
                    }
                    const answer = { question_id: question.id, option_ids: [...draft.option_ids] };
                    if (text.trim()) answer.text = text;
                    answers.push(answer);
                }
                return { answers };
            },

            async verifyAgentInteraction(run, item) {
                item.uncertain = true;
                const snapshot = await request(runPath(run.id)).catch(() => null);
                if (snapshot && snapshot.last_seq >= run.seq) applySnapshot(run, snapshot);
            },

            async submitAgentInteraction(run, item, cancel = false) {
                if (!this.interactionActionable(run, item, Date.now()) || (cancel && !item.data.allow_cancel)) return;
                const body = cancel ? { cancelled: true } : this.interactionReply(item);
                if (!body) return;
                item.submitting = true;
                item.error = '';
                try {
                    const receipt = await request(runPath(run.id) + '/interactions/' + segment(item.data.interaction_id) + '/reply',
                        { method: 'POST', body });
                    if (receipt.status === 'unknown' || receipt.status === 'dispatching') {
                        await this.verifyAgentInteraction(run, item);
                    } else {
                        item.sent = true;
                    }
                } catch (error) {
                    if (error.status === 409) {
                        item.open = false;
                        item.error = error.message || this.at('invalidated');
                    } else if (!error.status || error.status >= 500) {
                        await this.verifyAgentInteraction(run, item);
                    } else {
                        item.error = error.message;
                    }
                } finally {
                    item.submitting = false;
                }
            },

            get agentSettingsSchema() {
                return this.agentCatalog.find(agent => agent.id === this.currentPluginSettings?.id)?.settings_schema || null;
            },

            get agentSettingFields() {
                const schema = this.agentSettingsSchema;
                return Object.entries(schema?.properties || {})
                    .filter(([, field]) => !field.readOnly && (settingTypes.has(field.type) || field.enum?.length))
                    .map(([name, field]) => ({
                        ...field, name, required: (schema.required || []).includes(name)
                    }));
            },

            get agentModelSuggestions() {
                return (this.agentHealth?.models || []).flatMap(model => {
                    if (typeof model === 'string') return [{ id: model, label: model }];
                    return typeof model?.id === 'string' ? [{ id: model.id, label: model.name || model.id }] : [];
                });
            },

            async openAgentSettings(plugin) {
                this.agentSettingValues = {};
                this.agentSettingsError = '';
                this.agentSettingsLoading = true;
                await this.loadAgentCatalog();
                if (this.currentPluginSettings !== plugin) return;
                for (const field of this.agentSettingFields) {
                    const saved = plugin.settings_values?.[field.name];
                    this.agentSettingValues[field.name] = settingInputValue(field, saved);
                }
                this.agentSettingsLoading = false;
            },

            async saveAgentSettings() {
                const plugin = this.currentPluginSettings;
                if (!plugin?.agent || !this.agentSettingsSchema || this.agentSettingsSaving || this.agentSettingsLoading) return;
                const values = {};
                for (const field of this.agentSettingFields) {
                    const raw = this.agentSettingValues[field.name];
                    if (raw === undefined || raw === '') continue;
                    if (field.enum) values[field.name] = JSON.parse(raw);
                    else if (field.type === 'boolean') values[field.name] = raw === 'true';
                    else if (field.type === 'integer' || field.type === 'number') values[field.name] = Number(raw);
                    else if (raw.trim()) values[field.name] = raw.trim();
                }
                this.agentSettingsSaving = true;
                this.agentSettingsError = '';
                try {
                    const data = await request('/api/plugins/' + segment(plugin.id) + '/settings', {
                        method: 'POST', body: { settings: values }
                    });
                    if (!data.success) throw new Error(errorMessage(data, this.t('saveFailed')));
                    const installed = this.installedPlugins.find(item => item.id === plugin.id);
                    if (installed) installed.settings_values = values;
                    if (this.currentPluginSettings === plugin) this.showPluginSettings = false;
                    this.showToast(this.t('settingsSaved'), 'success');
                    this.loadAgentCatalog();
                } catch (error) {
                    if (this.currentPluginSettings === plugin) this.agentSettingsError = error.message || this.t('saveFailed');
                } finally {
                    this.agentSettingsSaving = false;
                }
            },

            resetAgentHealth() {
                healthRequest++;
                this.agentHealth = null;
                this.agentChecking = false;
                this.agentHealthError = '';
            },

            async checkAgentHealth(id) {
                const check = ++healthRequest;
                this.agentHealth = null;
                this.agentHealthError = '';
                this.agentChecking = true;
                try {
                    const data = await request('/api/agents/' + segment(id) + '/health');
                    if (check === healthRequest) {
                        this.agentHealth = data;
                        this.loadAgentCatalog();
                    }
                } catch (error) {
                    if (check === healthRequest) this.agentHealthError = error.message;
                } finally {
                    if (check === healthRequest) this.agentChecking = false;
                }
            },

            initAgentUI() {
                // Keep expiry controls current even while an upstream waits silently.
                setInterval(() => {
                    if (this.agentInteraction || this.activeAgentRun?.interactions.some(item => item.open && item.data.expires_at)) {
                        this.agentClock = Date.now();
                    }
                }, 1000);
                this.loadAgentCatalog();
            }
        };
    }

    return { create };
})();
