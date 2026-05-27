/* ============================================
   SYNORPSE Sphere - Rendering Engine
   Handles the 3D particle sphere, animations,
   and state transitions
   ============================================ */

class SphereRenderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.particles = [];
        this.state = 'idle'; // idle, listening, processing, searching, generating, automation, messaging, file_creation, success, error
        this.rippleRings = [];
        this.spiralAngle = 0;
        this.rainbowHue = 0;
        this.animFrame = null;
        this.time = 0;
        this.targetColors = { r: 0, g: 212, b: 255 }; // cyan
        this.currentColors = { ...this.targetColors };
        this.baseRadius = 0;
        this.numParticles = 80;
        this.orbitParticles = [];
        this._frameCount = 0; // For idle throttling

        // Mouse tracking
        this.mouseX = 0;
        this.mouseY = 0;
        this.targetMouseX = 0;
        this.targetMouseY = 0;
        this.tiltX = 0;
        this.tiltY = 0;

        this._resize();
        this._initParticles();
        this._initOrbitParticles();
        this._setupMouseTracking();
        this.start();
    }

    _setupMouseTracking() {
        window.addEventListener('mousemove', (e) => {
            // Normalize mouse position (-1 to 1)
            this.targetMouseX = (e.clientX - this.cx) / (this.width / 2);
            this.targetMouseY = (e.clientY - this.cy) / (this.height / 2);
        });
    }

    _resize() {
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.ctx.scale(dpr, dpr);
        this.width = rect.width;
        this.height = rect.height;
        this.cx = this.width / 2;
        this.cy = this.height / 2;
        this.baseRadius = Math.min(this.width, this.height) * 0.32;
    }

    _initParticles() {
        this.particles = [];
        for (let i = 0; i < this.numParticles; i++) {
            const phi = Math.acos(2 * Math.random() - 1);
            const theta = Math.random() * Math.PI * 2;
            this.particles.push({
                phi, theta,
                radius: this.baseRadius * (0.85 + Math.random() * 0.3),
                size: 1 + Math.random() * 1.5,
                speed: 0.002 + Math.random() * 0.006,
                offset: Math.random() * Math.PI * 2,
                alpha: 0.3 + Math.random() * 0.7
            });
        }
    }

    _initOrbitParticles() {
        this.orbitParticles = [];
        for (let i = 0; i < 6; i++) {
            this.orbitParticles.push({
                angle: (Math.PI * 2 / 6) * i,
                distance: this.baseRadius * 1.4,
                speed: 0.008 + Math.random() * 0.01,
                size: 2 + Math.random() * 2,
                alpha: 0.5 + Math.random() * 0.5
            });
        }
    }

    setState(newState) {
        if (this.state === newState) return;
        this.state = newState;

        const container = document.getElementById('sphere-container');
        container.className = '';
        if (newState !== 'idle') {
            container.classList.add(`state-${newState}`);
        }

        switch (newState) {
            case 'idle':
                this.targetColors = { r: 0, g: 212, b: 255 };
                break;
            case 'listening':
                this.targetColors = { r: 0, g: 212, b: 255 };
                break;
            case 'processing':
                this.targetColors = { r: 124, g: 58, b: 237 };
                break;
            case 'searching':
                this.targetColors = { r: 56, g: 189, b: 248 };
                this.rippleRings = [];
                break;
            case 'generating':
                this.rainbowHue = 0;
                this.targetColors = { r: 236, g: 72, b: 153 };
                break;
            case 'automation':
                this.targetColors = { r: 245, g: 158, b: 11 };
                break;
            case 'messaging':
                this.targetColors = { r: 34, g: 197, b: 94 };
                break;
            case 'file_creation':
                this.targetColors = { r: 250, g: 204, b: 21 };
                this.spiralAngle = 0;
                break;
            case 'analyzing':
                this.targetColors = { r: 163, g: 230, b: 53 }; // Lime green
                break;
            case 'success':
                this.targetColors = { r: 16, g: 185, b: 129 };
                setTimeout(() => this.setState('idle'), 1500);
                break;
            case 'error':
                this.targetColors = { r: 239, g: 68, b: 68 };
                setTimeout(() => this.setState('idle'), 2000);
                break;
        }
    }

    _lerp(a, b, t) {
        return a + (b - a) * t;
    }

    _lerpColor() {
        const t = 0.04;
        this.currentColors.r = this._lerp(this.currentColors.r, this.targetColors.r, t);
        this.currentColors.g = this._lerp(this.currentColors.g, this.targetColors.g, t);
        this.currentColors.b = this._lerp(this.currentColors.b, this.targetColors.b, t);
    }

    _getSpeedMultiplier() {
        switch (this.state) {
            case 'processing': return 3.5;
            case 'searching': return 2.5;
            case 'generating': return 2.0;
            case 'automation': return 4.0;
            case 'messaging': return 2.2;
            case 'file_creation': return 1.5;
            case 'analyzing': return 3.0;
            case 'listening': return 1.8;
            case 'success': return 0.5;
            case 'error': return 2.5;
            default: return 1;
        }
    }

    _drawCore() {
        const ctx = this.ctx;
        const { r, g, b } = this.currentColors;
        const breathe = Math.sin(this.time * 0.8) * 0.08 + 1;
        const coreRadius = this.baseRadius * 0.55 * breathe;

        // Inner glow
        const innerGlow = ctx.createRadialGradient(this.cx, this.cy, 0, this.cx, this.cy, coreRadius * 1.8);
        innerGlow.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.2)`);
        innerGlow.addColorStop(0.5, `rgba(${r}, ${g}, ${b}, 0.06)`);
        innerGlow.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = innerGlow;
        ctx.beginPath();
        ctx.arc(this.cx, this.cy, coreRadius * 1.8, 0, Math.PI * 2);
        ctx.fill();

        // Core sphere gradient
        const grad = ctx.createRadialGradient(
            this.cx - coreRadius * 0.2, this.cy - coreRadius * 0.2, 0,
            this.cx, this.cy, coreRadius
        );
        grad.addColorStop(0, `rgba(${Math.min(r + 60, 255)}, ${Math.min(g + 60, 255)}, ${Math.min(b + 60, 255)}, 0.35)`);
        grad.addColorStop(0.5, `rgba(${r}, ${g}, ${b}, 0.15)`);
        grad.addColorStop(1, `rgba(${r * 0.3 | 0}, ${g * 0.3 | 0}, ${b * 0.3 | 0}, 0.05)`);

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(this.cx, this.cy, coreRadius, 0, Math.PI * 2);
        ctx.fill();

        // Rim light
        ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, 0.15)`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(this.cx, this.cy, coreRadius, 0, Math.PI * 2);
        ctx.stroke();
    }

    _drawParticles() {
        const ctx = this.ctx;
        const { r, g, b } = this.currentColors;
        const speedMul = this._getSpeedMultiplier();

        for (const p of this.particles) {
            p.theta += p.speed * speedMul;

            const x3d = p.radius * Math.sin(p.phi) * Math.cos(p.theta);
            const y3d = p.radius * Math.cos(p.phi);
            const z3d = p.radius * Math.sin(p.phi) * Math.sin(p.theta);

            const depthFactor = (z3d + p.radius) / (p.radius * 2);
            const alpha = p.alpha * (0.2 + depthFactor * 0.8);
            const size = p.size * (0.5 + depthFactor * 0.5);

            const sx = this.cx + x3d;
            const sy = this.cy + y3d;

            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha * 0.8})`;
            ctx.beginPath();
            ctx.arc(sx, sy, size, 0, Math.PI * 2);
            ctx.fill();

            // Particle glow
            if (depthFactor > 0.6) {
                ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha * 0.15})`;
                ctx.beginPath();
                ctx.arc(sx, sy, size * 3, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }

    _drawOrbitParticles() {
        const activeStates = ['processing', 'listening', 'searching', 'automation', 'messaging', 'file_creation', 'generating', 'analyzing'];
        if (!activeStates.includes(this.state)) return;

        const ctx = this.ctx;
        const { r, g, b } = this.currentColors;
        const speedMul = this._getSpeedMultiplier();
        const trailLen = this.state === 'messaging' ? 5 : 3;

        for (const op of this.orbitParticles) {
            op.angle += op.speed * speedMul;

            const x = this.cx + Math.cos(op.angle) * op.distance;
            const y = this.cy + Math.sin(op.angle) * op.distance;

            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${op.alpha * 0.8})`;
            ctx.beginPath();
            ctx.arc(x, y, op.size, 0, Math.PI * 2);
            ctx.fill();

            // Trail (longer for messaging)
            for (let t = 1; t <= trailLen; t++) {
                const trailAngle = op.angle - op.speed * speedMul * t * 3;
                const tx = this.cx + Math.cos(trailAngle) * op.distance;
                const ty = this.cy + Math.sin(trailAngle) * op.distance;
                ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${op.alpha * 0.15 / t})`;
                ctx.beginPath();
                ctx.arc(tx, ty, op.size * 0.7, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }

    // --- Searching: expanding ripple rings ---
    _drawRippleRings() {
        if (this.state !== 'searching') return;
        const ctx = this.ctx;
        const { r, g, b } = this.currentColors;

        if (Math.random() < 0.04 && this.rippleRings.length < 8) {
            this.rippleRings.push({ radius: this.baseRadius * 0.5, alpha: 0.6 });
        }

        for (let i = this.rippleRings.length - 1; i >= 0; i--) {
            const ring = this.rippleRings[i];
            ring.radius += 0.6;
            ring.alpha -= 0.006;

            if (ring.alpha <= 0) {
                this.rippleRings.splice(i, 1);
                continue;
            }

            ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${ring.alpha})`;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.arc(this.cx, this.cy, ring.radius, 0, Math.PI * 2);
            ctx.stroke();
        }
    }

    // --- Generating: rainbow hue shift on particles ---
    _applyRainbowCycle() {
        if (this.state !== 'generating') return;
        this.rainbowHue = (this.rainbowHue + 1.5) % 360;
        const h = this.rainbowHue / 60;
        const c = 200;
        const x = c * (1 - Math.abs(h % 2 - 1));
        let rr, gg, bb;
        if (h < 1) { rr = c; gg = x; bb = 0; }
        else if (h < 2) { rr = x; gg = c; bb = 0; }
        else if (h < 3) { rr = 0; gg = c; bb = x; }
        else if (h < 4) { rr = 0; gg = x; bb = c; }
        else if (h < 5) { rr = x; gg = 0; bb = c; }
        else { rr = c; gg = 0; bb = x; }
        this.targetColors = { r: rr + 55, g: gg + 55, b: bb + 55 };
    }

    // --- File Creation: spiral construction particles ---
    _drawSpiralParticles() {
        if (this.state !== 'file_creation') return;
        const ctx = this.ctx;
        const { r, g, b } = this.currentColors;
        this.spiralAngle += 0.05;

        for (let i = 0; i < 12; i++) {
            const angle = this.spiralAngle + (Math.PI * 2 / 12) * i;
            const dist = this.baseRadius * (0.6 + 0.4 * Math.sin(this.time * 2 + i));
            const x = this.cx + Math.cos(angle) * dist;
            const y = this.cy + Math.sin(angle) * dist;
            const alpha = 0.4 + 0.4 * Math.sin(this.time * 3 + i * 0.5);

            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
            ctx.beginPath();
            ctx.arc(x, y, 2, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    _render() {
        this.time += 0.016;
        this._lerpColor();
        this._applyRainbowCycle();

        // Smoothly lerp tilt based on mouse
        this.tiltX = this._lerp(this.tiltX, this.targetMouseX * 15, 0.08);
        this.tiltY = this._lerp(this.tiltY, this.targetMouseY * 15, 0.08);

        this.ctx.clearRect(0, 0, this.width, this.height);

        this.ctx.save();
        // Dynamic tilt effect
        this.ctx.translate(this.cx, this.cy);
        this.ctx.rotate(this.tiltX * Math.PI / 180);
        this.ctx.translate(-this.cx, -this.cy);

        this._drawCore();
        this._drawParticles();
        this._drawOrbitParticles();
        this._drawRippleRings();
        this._drawSpiralParticles();

        this.ctx.restore();

        this.animFrame = requestAnimationFrame(() => this._render());
    }

    start() {
        if (this.animFrame) return;
        this._render();
    }

    stop() {
        if (this.animFrame) {
            cancelAnimationFrame(this.animFrame);
            this.animFrame = null;
        }
    }
}


/* ============================================
   Chat Controller
   Handles messages, input, and bridge comms
   ============================================ */

class ChatController {
    constructor(sphere) {
        this.sphere = sphere;
        this.isOpen = false;
        this.isProcessing = false;
        this.bridge = null;

        this.panel = document.getElementById('chat-panel');
        // Start hidden to avoid any rendered chrome beneath the collapsed sphere
        this.panel.style.display = 'none';
        this.messagesEl = document.getElementById('chat-messages');
        this.inputEl = document.getElementById('chat-input');
        this.sendBtn = document.getElementById('chat-send-btn');
        this.closeBtn = document.getElementById('chat-close-btn');
        this.clearBtn = document.getElementById('chat-clear-btn');
        this.uploadBtn = document.getElementById('chat-upload-btn');
        this.sphereContainer = document.getElementById('sphere-container');

        this._bindEvents();
        this._initBridge();
    }

    _bindEvents() {
        this.sphereContainer.addEventListener('click', () => this.toggle());
        this.closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (this.bridge && this.bridge.quitApp) {
                this.bridge.quitApp();
            } else {
                this.close();
            }
        });
        this.clearBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.clearChat();
        });
        this.uploadBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (this.bridge && this.bridge.uploadDocument) {
                this.bridge.uploadDocument();
            }
        });
        this.sendBtn.addEventListener('click', () => this._send());
        this.inputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this._send();
            }
        });

        // Right-click context menu on sphere
        this.sphereContainer.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this._showContextMenu(e.clientX, e.clientY);
        });

        // Dismiss context menu on click anywhere
        document.addEventListener('click', () => this._hideContextMenu());
    }

    _showContextMenu(x, y) {
        this._hideContextMenu();
        const menu = document.createElement('div');
        menu.id = 'sphere-context-menu';
        menu.style.cssText = `
            position: fixed; left: ${x}px; top: ${y}px; z-index: 10000;
            background: rgba(20, 20, 30, 0.95); border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px; padding: 4px 0; min-width: 140px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.5); backdrop-filter: blur(12px);
            font-family: 'Inter', sans-serif; font-size: 13px;
        `;

        const exitBtn = document.createElement('div');
        exitBtn.textContent = '✕  Exit SYNORPSE';
        exitBtn.style.cssText = `
            padding: 8px 16px; color: #ef4444; cursor: pointer;
            transition: background 0.15s;
        `;
        exitBtn.addEventListener('mouseenter', () => exitBtn.style.background = 'rgba(239,68,68,0.15)');
        exitBtn.addEventListener('mouseleave', () => exitBtn.style.background = 'none');
        exitBtn.addEventListener('click', () => {
            if (this.bridge && this.bridge.quitApp) {
                this.bridge.quitApp();
            }
        });

        menu.appendChild(exitBtn);
        document.body.appendChild(menu);
    }

    _hideContextMenu() {
        const existing = document.getElementById('sphere-context-menu');
        if (existing) existing.remove();
    }

    _initBridge() {
        // QWebChannel bridge to Python
        if (typeof QWebChannel !== 'undefined') {
            new QWebChannel(qt.webChannelTransport, (channel) => {
                this.bridge = channel.objects.bridge;
                console.log('Bridge connected to Python backend');
            });
        } else {
            console.log('No QWebChannel — running in standalone mode');
        }
    }

    toggle() {
        if (this.isOpen) this.close();
        else this.open();
    }

    open() {
        this.isOpen = true;
        // Make panel render before activating open class so transitions work
        this.panel.style.display = 'flex';
        requestAnimationFrame(() => this.panel.classList.add('open'));
        this.sphere.setState('listening');
        // Tell Python to expand the window so the chat panel area is interactive
        if (this.bridge && this.bridge.expandWindow) {
            this.bridge.expandWindow();
        }
        setTimeout(() => this.inputEl.focus(), 350);
    }

    close() {
        this.isOpen = false;
        // Start collapse transition, then remove from layout to avoid any chrome rendering
        this.panel.classList.remove('open');
        this.sphere.setState('idle');
        // Tell Python to collapse the window so area below sphere is clickable
        if (this.bridge && this.bridge.collapseWindow) {
            this.bridge.collapseWindow();
        }
        // Match CSS transition duration (400ms) + small buffer, then remove display
        setTimeout(() => { this.panel.style.display = 'none'; }, 450);
    }

    clearChat() {
        // Clear UI messages
        this.messagesEl.innerHTML = '';

        // Add system message
        const sysMsg = document.createElement('div');
        sysMsg.className = 'message system';
        sysMsg.textContent = '✦ Chat history cleared';
        this.messagesEl.appendChild(sysMsg);

        // Clear backend history
        if (this.bridge) {
            this.bridge.clearHistory();
        }

        // Re-show welcome after a moment
        setTimeout(() => {
            if (this.messagesEl.children.length <= 1) {
                const welcome = document.createElement('div');
                welcome.className = 'welcome-message';
                welcome.innerHTML = `
                    <span class="welcome-icon">✦</span>
                    <span class="welcome-name">Synorpse</span>
                    Ask me anything — I can search the web, open apps, generate images, create files, and much more.
                `;
                this.messagesEl.appendChild(welcome);
            }
        }, 1500);
    }

    _send() {
        const text = this.inputEl.value.trim();
        if (!text || this.isProcessing) return;

        this.inputEl.value = '';
        this._addMessage(text, 'user');
        this._setProcessing(true);
        this.sphere.setState('processing');

        if (this.bridge) {
            this.bridge.receiveMessage(text);
        } else {
            // Standalone demo mode
            setTimeout(() => {
                this._onResponse("I'm running in **standalone mode**. Connect me to the Python backend to unlock my full capabilities! 🚀");
            }, 1200);
        }
    }

    _setProcessing(val) {
        this.isProcessing = val;
        this.sendBtn.disabled = val;
        if (val) {
            this._showTyping();
        } else {
            this._hideTyping();
        }
    }

    _addMessage(text, role, wave = false) {
        // Remove welcome if present
        const welcome = this.messagesEl.querySelector('.welcome-message');
        if (welcome) welcome.remove();

        const div = document.createElement('div');
        div.className = `message ${role}`;

        if (role === 'assistant') {
            const rendered = this._renderMarkdown(text);

            if (wave) {
                // Wave typing: wrap each character in a span and stagger opacity
                div.classList.add('wave-typing');
                div.innerHTML = '';
                const contentWrap = document.createElement('span');
                contentWrap.className = 'wave-content';
                div.appendChild(contentWrap);

                // Add copy button
                const copyBtn = document.createElement('button');
                copyBtn.className = 'copy-btn';
                copyBtn.textContent = '📋';
                copyBtn.title = 'Copy to clipboard';
                copyBtn.onclick = () => {
                    navigator.clipboard.writeText(text).then(() => {
                        copyBtn.textContent = '✅';
                        setTimeout(() => copyBtn.textContent = '📋', 1500);
                    });
                };
                div.appendChild(copyBtn);

                this.messagesEl.appendChild(div);
                this._waveReveal(contentWrap, rendered);
            } else {
                div.innerHTML = rendered;
                // Add copy button for non-wave too
                const copyBtn = document.createElement('button');
                copyBtn.className = 'copy-btn';
                copyBtn.textContent = '📋';
                copyBtn.title = 'Copy to clipboard';
                copyBtn.onclick = () => {
                    navigator.clipboard.writeText(text).then(() => {
                        copyBtn.textContent = '✅';
                        setTimeout(() => copyBtn.textContent = '📋', 1500);
                    });
                };
                div.appendChild(copyBtn);
                this.messagesEl.appendChild(div);
            }
        } else {
            div.textContent = text;
            this.messagesEl.appendChild(div);
        }

        this._scrollToBottom();
    }

    _waveReveal(container, html) {
        // Parse HTML into a temp div
        const temp = document.createElement('div');
        temp.innerHTML = html;

        // Collect all text nodes and wrap each char in a span
        const walker = document.createTreeWalker(temp, NodeFilter.SHOW_TEXT);
        const textNodes = [];
        while (walker.nextNode()) textNodes.push(walker.currentNode);

        let charIndex = 0;
        for (const textNode of textNodes) {
            const text = textNode.textContent;
            const fragment = document.createDocumentFragment();
            for (const ch of text) {
                const span = document.createElement('span');
                span.className = 'wave-char';
                span.textContent = ch;
                span.style.animationDelay = `${charIndex * 2}ms`;
                fragment.appendChild(span);
                charIndex++;
            }
            textNode.parentNode.replaceChild(fragment, textNode);
        }

        // Clone processed nodes into container
        while (temp.firstChild) {
            container.appendChild(temp.firstChild);
        }

        // Auto-scroll during animation
        const totalTime = charIndex * 2 + 200;
        const scrollInterval = setInterval(() => this._scrollToBottom(), 50);
        setTimeout(() => clearInterval(scrollInterval), totalTime);
    }

    _showTyping() {
        if (this.messagesEl.querySelector('.typing-indicator')) return;
        const typing = document.createElement('div');
        typing.className = 'typing-indicator';
        typing.innerHTML = '<span></span><span></span><span></span>';
        this.messagesEl.appendChild(typing);
        this._scrollToBottom();
    }

    _hideTyping() {
        const typing = this.messagesEl.querySelector('.typing-indicator');
        if (typing) typing.remove();
    }

    _scrollToBottom() {
        requestAnimationFrame(() => {
            this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
        });
    }

    _renderMarkdown(text) {
        let html = text
            .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
            .replace(/^[\-\*] (.+)$/gm, '<li>$1</li>')
            .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
            .replace(/\n/g, '<br>');

        html = html.replace(/((?:<li>.*?<\/li><br>?)+)/g, '<ul>$1</ul>');
        html = html.replace(/<br><\/ul>/g, '</ul>');
        html = html.replace(/<ul><br>/g, '<ul>');

        // Auto-link raw URLs (not already inside an <a> tag)
        html = html.replace(
            /(?<!href=")(?<!<a[^>]*>)(https?:\/\/[^\s<]+)/g,
            '<a href="$1" target="_blank" rel="noopener" class="auto-link">$1</a>'
        );

        return html;
    }

    // Called from Python bridge
    _onResponse(text) {
        this._setProcessing(false);

        // Try to parse JSON-structured response
        let displayText = text;
        try {
            const parsed = JSON.parse(text);
            if (parsed && parsed.response) {
                displayText = parsed.response;
            }
        } catch (_) {
            // Not JSON — use raw text as-is
        }

        this._addMessage(displayText, 'assistant', true);  // wave = true
        this.sphere.setState('success');
    }

    // Called from Python bridge
    _onError(text) {
        this._setProcessing(false);
        this._addMessage(`❌ ${text}`, 'assistant');
        this.sphere.setState('error');
    }

    // Called from Python bridge — live reasoning thoughts
    _addThinking(text) {
        // Disabled to reduce noise as requested
        console.log(`💭 Thought: ${text}`);
    }
}


/* ============================================
   Initialize on DOM ready
   ============================================ */

let sphereRenderer = null;
let chatController = null;

document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('sphere-canvas');
    sphereRenderer = new SphereRenderer(canvas);
    chatController = new ChatController(sphereRenderer);
});

// Global functions for Python bridge to call
function onAssistantResponse(text) {
    if (chatController) chatController._onResponse(text);
}

function onAssistantError(text) {
    if (chatController) chatController._onError(text);
}

function setSphereState(state) {
    if (sphereRenderer) sphereRenderer.setState(state);
}

function onThinkingUpdate(text) {
    if (chatController) chatController._addThinking(text);
}
