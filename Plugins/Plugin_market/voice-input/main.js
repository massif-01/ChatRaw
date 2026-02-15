/**
 * Voice Input Plugin
 * 语音输入插件
 *
 * Speech-to-text using browser Web Speech API. Pure frontend, no backend.
 * 基于浏览器 Web Speech API 的语音转文字，纯前端无需后端。
 *
 * @version 1.0.0
 * @author ChatRaw
 * @license Apache-2.0
 */
(function(ChatRaw) {
    'use strict';

    if (!ChatRaw || !ChatRaw.hooks) {
        console.error('[VoiceInput] ChatRawPlugin not available');
        return;
    }

    if (!ChatRaw.ui || !ChatRaw.ui.registerToolbarButton) {
        console.error('[VoiceInput] ChatRawPlugin.ui API not available');
        return;
    }

    const PLUGIN_ID = 'voice-input';
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    const i18n = {
        en: {
            buttonLabel: 'Voice Input',
            notSupported: 'Speech recognition is not supported in this browser',
            startListening: 'Listening...',
            stopListening: 'Stopped',
            errorAborted: 'Speech recognition was aborted',
            errorNetwork: 'Network error. Check your connection.',
            errorNoSpeech: 'No speech detected',
            errorDenied: 'Microphone access was denied',
            errorGeneric: 'Speech recognition error'
        },
        zh: {
            buttonLabel: '语音输入',
            notSupported: '当前浏览器不支持语音识别',
            startListening: '正在聆听...',
            stopListening: '已停止',
            errorAborted: '语音识别已取消',
            errorNetwork: '网络错误，请检查连接',
            errorNoSpeech: '未检测到语音',
            errorDenied: '麦克风权限被拒绝',
            errorGeneric: '语音识别错误'
        }
    };

    function t(key) {
        const lang = ChatRaw.utils?.getLanguage?.() || 'en';
        return i18n[lang]?.[key] || i18n.en[key] || key;
    }

    function appendToInput(text) {
        const textarea = document.querySelector('.input-wrapper textarea');
        if (!textarea) return;
        const existing = textarea.value || '';
        const sep = existing && !existing.endsWith(' ') ? ' ' : '';
        textarea.value = existing + sep + text;
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
    }

    let recognition = null;
    let isListening = false;

    function getRecognitionLang() {
        const lang = ChatRaw.utils?.getLanguage?.() || 'en';
        return lang === 'zh' ? 'zh-CN' : 'en-US';
    }

    function createRecognition() {
        if (!SpeechRecognition) return null;
        const rec = new SpeechRecognition();
        rec.continuous = true;
        rec.interimResults = true;
        rec.lang = getRecognitionLang();

        rec.onresult = (event) => {
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const result = event.results[i];
                const transcript = result[0].transcript;
                if (result.isFinal) {
                    const text = transcript;
                    setTimeout(() => appendToInput(text), 0);
                }
            }
        };

        rec.onerror = (event) => {
            if (event.error === 'no-speech') return;
            if (event.error === 'not-allowed') isListening = false;
            else if (event.error === 'aborted') isListening = false;
            let msg = t('errorGeneric');
            if (event.error === 'aborted') msg = t('errorAborted');
            else if (event.error === 'network') msg = t('errorNetwork');
            else if (event.error === 'not-allowed') msg = t('errorDenied');
            setTimeout(() => {
                ChatRaw.utils?.showToast?.(msg, 'error');
                ChatRaw.ui.setButtonState('voice-input-btn', { active: false }, PLUGIN_ID);
            }, 0);
        };

        rec.onend = () => {
            if (isListening) {
                try {
                    rec.start();
                } catch (e) {
                    isListening = false;
                    setTimeout(() => {
                        ChatRaw.ui.setButtonState('voice-input-btn', { active: false }, PLUGIN_ID);
                        ChatRaw.utils?.showToast?.(t('stopListening'), 'info');
                    }, 0);
                }
            } else {
                setTimeout(() => {
                    ChatRaw.ui.setButtonState('voice-input-btn', { active: false }, PLUGIN_ID);
                }, 0);
            }
        };

        return rec;
    }

    function handleClick() {
        if (!SpeechRecognition) {
            ChatRaw.utils?.showToast?.(t('notSupported'), 'error');
            return;
        }

        if (isListening) {
            isListening = false;
            recognition.stop();
            ChatRaw.utils?.showToast?.(t('stopListening'), 'info');
            return;
        }

        if (!recognition) {
            recognition = createRecognition();
        }
        if (!recognition) {
            ChatRaw.utils?.showToast?.(t('notSupported'), 'error');
            return;
        }

        recognition.lang = getRecognitionLang();
        isListening = true;
        ChatRaw.ui.setButtonState('voice-input-btn', { active: true }, PLUGIN_ID);
        ChatRaw.utils?.showToast?.(t('startListening'), 'info');

        try {
            recognition.start();
        } catch (e) {
            isListening = false;
            ChatRaw.ui.setButtonState('voice-input-btn', { active: false }, PLUGIN_ID);
            ChatRaw.utils?.showToast?.(t('errorGeneric'), 'error');
        }
    }

    ChatRaw.ui.registerToolbarButton({
        id: 'voice-input-btn',
        icon: 'ri-mic-line',
        label: {
            en: 'Voice Input',
            zh: '语音输入'
        },
        onClick: handleClick,
        order: 15
    }, PLUGIN_ID);

})(window.ChatRawPlugin);
