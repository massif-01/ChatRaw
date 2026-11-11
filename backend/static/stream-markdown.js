/* ChatRaw's streaming and settled Markdown share the same parser. */
window.ChatRawMarkdown = (() => {
    const states = new WeakMap();
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    const escape = value => value.replace(/[&<>]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[char]);
    const base = new marked.Renderer();

    function safeDestination(href, protocols) {
        if (!href) return null;
        try {
            const url = new URL(href, document.baseURI);
            return protocols.includes(url.protocol) ? url.href : null;
        } catch {
            return null;
        }
    }

    // Protect all Markdown sinks, including the HTML/PDF export plugin.
    marked.use({ renderer: {
        html: escape,
        link(href, title, label) {
            const url = safeDestination(href, ['http:', 'https:', 'mailto:']);
            return url ? base.link.call(this, url, title, label) : label;
        },
        image(href, title, label) {
            const url = safeDestination(href, ['http:', 'https:']);
            return url ? base.image.call(this, url, title, label) : escape(label);
        }
    } });

    function html(source) {
        return source ? marked.parse(source) : '';
    }

    // Markmap emits HTML for labels independently of Marked's renderer.
    function diagramLabel(source) {
        const template = document.createElement('template');
        template.innerHTML = source;
        const allowed = new Set(['A', 'B', 'BR', 'CODE', 'DEL', 'EM', 'I', 'S', 'SPAN', 'STRONG']);
        for (const element of template.content.querySelectorAll('*')) {
            if (!allowed.has(element.tagName)) {
                element.replaceWith(document.createTextNode(element.textContent));
                continue;
            }
            const href = element.tagName === 'A' ? safeDestination(element.getAttribute('href'), ['http:', 'https:', 'mailto:']) : null;
            for (const attribute of Array.from(element.attributes)) element.removeAttribute(attribute.name);
            if (href) element.setAttribute('href', href);
        }
        return template.innerHTML;
    }

    function addReveal(slot, value) {
        const reveal = document.createElement('span');
        reveal.className = 'markdown-reveal';
        reveal.textContent = value;
        slot.append(reveal);
        reveal.addEventListener('animationend', () => {
            reveal.replaceWith(...reveal.childNodes);
            slot.normalize();
        }, { once: true });
    }

    const prose = /^(P|LI|TH|TD|H[1-6]|A|STRONG|EM|DEL|BLOCKQUOTE|SPAN)$/;

    function mount(node, animate, textSlots, parentTag) {
        if (node.nodeType === Node.TEXT_NODE && textSlots && prose.test(parentTag)) {
            const slot = document.createElement('span');
            slot.dataset.markdownText = '';
            if (animate && node.data.trim()) addReveal(slot, node.data);
            else slot.textContent = node.data;
            return { node: slot, source: node, children: [] };
        }
        const copy = node.cloneNode(false);
        const children = Array.from(node.childNodes, child => mount(child, animate, textSlots, node.nodeName));
        for (const child of children) copy.append(child.node);
        return { node: copy, source: node, children };
    }

    function sameElement(before, after) {
        return before.nodeName === after.nodeName &&
            before.attributes.length === after.attributes.length &&
            Array.from(before.attributes).every(attr => after.getAttribute(attr.name) === attr.value);
    }

    function patch(record, next, animate, textSlots, parentTag) {
        const previous = record.source;
        if (previous.isEqualNode(next)) return record;
        if (previous.nodeType === Node.TEXT_NODE && next.nodeType === Node.TEXT_NODE) {
            if (record.node.nodeType === Node.TEXT_NODE) {
                record.node.data = next.data;
            } else if (animate && next.data.startsWith(previous.data)) {
                addReveal(record.node, next.data.slice(previous.data.length));
            } else {
                record.node.textContent = next.data;
            }
            record.source = next;
            return record;
        }
        if (previous.nodeType === Node.ELEMENT_NODE && next.nodeType === Node.ELEMENT_NODE &&
            sameElement(previous, next) && record.children.every(child => child.node.parentNode === record.node)) {
            // An inline delimiter can reinterpret existing text. Reveal only new text.
            const extendsText = next.textContent.startsWith(previous.textContent);
            updateChildren(record.node, record.children, next.childNodes, animate && extendsText, textSlots);
            record.source = next;
            return record;
        }
        const replacement = mount(next, false, textSlots, parentTag);
        record.node.replaceWith(replacement.node);
        return replacement;
    }

    function updateChildren(parent, records, nodes, animate, textSlots, boundary = null) {
        for (let i = 0; i < nodes.length; i++) {
            const node = nodes[i];
            if (i < records.length) {
                records[i] = patch(records[i], node, animate, textSlots, parent.nodeName);
            } else {
                const record = mount(node, animate, textSlots, parent.nodeName);
                parent.insertBefore(record.node, boundary);
                records.push(record);
            }
        }
        for (const record of records.splice(nodes.length)) record.node.remove();
    }

    function removeBlock(element, start, end) {
        let node = start ? start.nextSibling : element.firstChild;
        while (node && node !== end) {
            const next = node.nextSibling;
            node.remove();
            node = next;
        }
    }

    function flush(element, state) {
        state.frame = null;
        const { source, live, replay } = state.next;
        const animate = live && !replay && !motion.matches;
        const tokens = marked.lexer(source);
        const links = JSON.stringify(tokens.links);

        // Reference definitions can change earlier blocks. Re-lex to resolve them,
        // but reuse unchanged rendered blocks and reconcile only changed DOM.
        for (let i = 0; i < tokens.length; i++) {
            const token = tokens[i];
            let block = state.blocks[i];
            if (block && block.raw === token.raw && block.type === token.type && state.links === links) continue;
            if (!block) {
                block = { end: document.createComment(''), nodes: [] };
                state.blocks.push(block);
                element.append(block.end);
            }
            if (block.nodes.some(record => record.node.parentNode !== element)) {
                // Older plugins may replace a live code block. Reclaim its range if the source changes.
                removeBlock(element, state.blocks[i - 1]?.end, block.end);
                block.nodes = [];
            }
            const fragment = document.createElement('template');
            fragment.innerHTML = marked.parser([token]);
            updateChildren(element, block.nodes, fragment.content.childNodes, animate, live, block.end);
            block.raw = token.raw;
            block.type = token.type;
        }
        const removed = state.blocks.splice(tokens.length);
        if (removed.length) removeBlock(element, state.blocks[state.blocks.length - 1]?.end, null);
        state.links = links;

        if (!live) {
            for (const node of element.querySelectorAll('.markdown-reveal, [data-markdown-text]')) {
                node.replaceWith(...node.childNodes);
            }
            element.normalize();
            element.removeAttribute('data-markdown-streaming');
            // A settled message can still be replaced by an ordinary after_receive hook.
            states.delete(element);
        }
        state.after?.();
    }

    function render(element, source, { live = false, replay = false } = {}, after) {
        let state = states.get(element);
        if (!state) {
            element.replaceChildren();
            state = { blocks: [], links: '', frame: null };
            states.set(element, state);
        }
        state.next = { source: source || '', live, replay };
        state.after = after;
        if (live) {
            element.setAttribute('data-markdown-streaming', '');
            if (state.frame === null) {
                state.frame = requestAnimationFrame(() => {
                    if (element.isConnected) flush(element, state);
                    else state.frame = null;
                });
            }
        } else {
            if (state.frame !== null) cancelAnimationFrame(state.frame);
            flush(element, state);
        }
    }

    return { html, render, diagramLabel };
})();
