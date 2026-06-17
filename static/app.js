(function () {
    'use strict';

    var pollTimer = null;
    var currentFilter = '';

    var $ = function (sel) { return document.querySelector(sel); };
    var $$ = function (sel) { return document.querySelectorAll(sel); };

    var statusTag = $('#status-tag');
    var statDownloaded = $('#stat-downloaded');
    var statFailed = $('#stat-failed');
    var trackInput = $('#track-input');
    var inputCount = $('#input-count');
    var btnAdd = $('#btn-add');
    var btnImportFile = $('#btn-import-file');
    var fileInput = $('#file-input');
    var btnStart = $('#btn-start');
    var btnPause = $('#btn-pause');
    var btnStop = $('#btn-stop');
    var btnRetry = $('#btn-retry');
    var btnClearDone = $('#btn-clear-done');
    var btnClearAll = $('#btn-clear-all');
    var progressBarWrap = $('#progress-bar-wrap');
    var progressBar = $('#progress-bar');
    var progressText = $('#progress-text');
    var downloadDir = $('#download-dir');
    var btnSetDir = $('#btn-set-dir');
    var workersSlider = $('#workers-slider');
    var workersVal = $('#workers-val');
    var slskStatus = $('#slsk-status');
    var queueStats = $('#queue-stats');
    var queueList = $('#queue-list');

    // ==================== LOADING SCREEN ====================

    function createLoadingScreen() {
        var el = document.createElement('div');
        el.className = 'loading-screen';
        el.id = 'loading-screen';
        el.innerHTML = '<div class="loading-text">TRACKRIP</div><div class="loading-bar"></div>';
        document.body.appendChild(el);
        return el;
    }

    function removeLoadingScreen() {
        var el = document.getElementById('loading-screen');
        if (!el) return;
        gsap.to(el, {
            opacity: 0,
            duration: 0.6,
            delay: 0.8,
            ease: 'power2.inOut',
            onComplete: function () { el.remove(); }
        });
    }

    // ==================== CURSOR TRAIL ====================

    var trailDots = [];
    var TRAIL_COUNT = 8;

    function initCursorTrail() {
        for (var i = 0; i < TRAIL_COUNT; i++) {
            var dot = document.createElement('div');
            dot.className = 'cursor-trail';
            dot.style.width = (6 - i * 0.6) + 'px';
            dot.style.height = (6 - i * 0.6) + 'px';
            document.body.appendChild(dot);
            trailDots.push({ el: dot, x: 0, y: 0 });
        }
    }

    var mx = 0, my = 0;
    document.addEventListener('mousemove', function (e) {
        mx = e.clientX;
        my = e.clientY;
    });

    function updateTrail() {
        var prevX = mx;
        var prevY = my;
        for (var i = 0; i < trailDots.length; i++) {
            var d = trailDots[i];
            var speed = 0.15 - i * 0.012;
            d.x += (prevX - d.x) * speed;
            d.y += (prevY - d.y) * speed;
            d.el.style.left = d.x + 'px';
            d.el.style.top = d.y + 'px';
            d.el.style.opacity = (0.5 - i * 0.06);
            prevX = d.x;
            prevY = d.y;
        }
        requestAnimationFrame(updateTrail);
    }

    // ==================== GSAP ENTRANCE ====================

    function initAnimations() {
        // Header
        gsap.set('.header', { opacity: 0, y: -30 });
        gsap.to('.header', { opacity: 1, y: 0, duration: 0.8, ease: 'power3.out', delay: 1 });

        // Logo glitch burst
        gsap.from('.logo', {
            x: -10,
            opacity: 0,
            duration: 0.1,
            repeat: 5,
            yoyo: true,
            delay: 1.1,
            ease: 'none'
        });

        gsap.from('.logo span', {
            scale: 1.5,
            opacity: 0,
            duration: 0.6,
            delay: 1.2,
            ease: 'back.out(2)'
        });

        // Stat pills stagger
        gsap.from('.stat-pill', {
            opacity: 0,
            x: 30,
            duration: 0.4,
            stagger: 0.1,
            delay: 1.4,
            ease: 'power2.out'
        });

        // Panels with 3D tilt
        $$('.panel').forEach(function (panel, i) {
            gsap.to(panel, {
                opacity: 1,
                y: 0,
                duration: 0.6,
                delay: 1.3 + i * 0.12,
                ease: 'power3.out'
            });

            // Subtle 3D tilt on hover
            panel.addEventListener('mousemove', function (e) {
                var rect = panel.getBoundingClientRect();
                var x = e.clientX - rect.left;
                var y = e.clientY - rect.top;
                var centerX = rect.width / 2;
                var centerY = rect.height / 2;
                var rotateX = (y - centerY) / centerY * -2;
                var rotateY = (x - centerX) / centerX * 2;
                gsap.to(panel, {
                    rotateX: rotateX,
                    rotateY: rotateY,
                    transformPerspective: 800,
                    duration: 0.4,
                    ease: 'power2.out'
                });
            });

            panel.addEventListener('mouseleave', function () {
                gsap.to(panel, {
                    rotateX: 0,
                    rotateY: 0,
                    duration: 0.6,
                    ease: 'elastic.out(1, 0.5)'
                });
            });
        });

        // Footer
        gsap.from('.footer', {
            opacity: 0,
            duration: 0.5,
            delay: 2,
            ease: 'power2.out'
        });
    }

    // ==================== GSAP QUEUE ANIMATIONS ====================

    function animateQueueItems() {
        var items = queueList.querySelectorAll('.q-item');
        items.forEach(function (item, i) {
            if (!item.dataset.animated) {
                gsap.fromTo(item,
                    { opacity: 0, x: -20, scale: 0.98 },
                    {
                        opacity: 1, x: 0, scale: 1,
                        duration: 0.35,
                        ease: 'power2.out',
                        delay: i * 0.04
                    }
                );
                item.dataset.animated = '1';
            }
        });
    }

    // ==================== GSAP MICRO-ANIMATIONS ====================

    function animateTag(el) {
        gsap.fromTo(el,
            { scale: 0.8, opacity: 0, rotateZ: -3 },
            { scale: 1, opacity: 1, rotateZ: 0, duration: 0.4, ease: 'back.out(3)' }
        );
    }

    function animatePress(el) {
        gsap.timeline()
            .to(el, { scale: 0.9, duration: 0.08, ease: 'power2.in' })
            .to(el, { scale: 1, duration: 0.3, ease: 'elastic.out(1, 0.4)' });
    }

    function animateProgress(pct) {
        gsap.to(progressBar, {
            width: pct + '%',
            duration: 0.6,
            ease: 'power2.out'
        });
    }

    function animateStatPill(el, text) {
        if (el.textContent === text) return;
        gsap.timeline()
            .to(el, { y: -8, opacity: 0, duration: 0.15, ease: 'power2.in' })
            .call(function () { el.textContent = text; })
            .to(el, { y: 0, opacity: 1, duration: 0.25, ease: 'back.out(2)' });
    }

    function flashPanel(el, color) {
        gsap.fromTo(el,
            { boxShadow: '0 0 0px ' + color },
            {
                boxShadow: '0 0 30px ' + color + ', inset 0 0 20px ' + color,
                duration: 0.4,
                yoyo: true,
                repeat: 1,
                ease: 'power2.inOut'
            }
        );
    }

    // Neon text flash on success
    function neonFlash(el) {
        gsap.fromTo(el,
            { textShadow: '0 0 0px rgba(0,255,136,0)' },
            {
                textShadow: '0 0 20px rgba(0,255,136,0.8), 0 0 40px rgba(0,255,136,0.4)',
                duration: 0.3,
                yoyo: true,
                repeat: 1,
                ease: 'power2.inOut'
            }
        );
    }

    // Shake on error
    function shakeElement(el) {
        gsap.fromTo(el,
            { x: 0 },
            {
                x: 5,
                duration: 0.06,
                repeat: 5,
                yoyo: true,
                ease: 'power2.inOut',
                onComplete: function () { gsap.set(el, { x: 0 }); }
            }
        );
    }

    // Button ripple effect
    function buttonRipple(el, color) {
        var ripple = document.createElement('span');
        ripple.style.cssText = 'position:absolute;top:50%;left:50%;width:0;height:0;border-radius:50%;background:' + color + ';transform:translate(-50%,-50%);pointer-events:none;opacity:0.4;';
        el.style.position = 'relative';
        el.style.overflow = 'hidden';
        el.appendChild(ripple);
        gsap.to(ripple, {
            width: 150,
            height: 150,
            opacity: 0,
            duration: 0.5,
            ease: 'power2.out',
            onComplete: function () { ripple.remove(); }
        });
    }

    // ==================== API ====================

    function api(method, path, body) {
        var opts = {
            method: method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (body !== undefined) opts.body = JSON.stringify(body);
        return fetch(path, opts).then(function (r) { return r.json(); });
    }

    // ==================== INPUT ====================

    trackInput.addEventListener('input', function () {
        var lines = trackInput.value.split('\n').filter(function (l) {
            return l.trim() && l.indexOf(' - ') !== -1;
        });
        inputCount.textContent = lines.length + ' строк';
    });

    // ==================== ADD TRACKS ====================

    btnAdd.addEventListener('click', function () {
        animatePress(this);
        buttonRipple(this, 'rgba(0,255,136,0.3)');
        var text = trackInput.value.trim();
        if (!text) return;
        var lines = text.split('\n').filter(function (l) {
            return l.trim() && l.indexOf(' - ') !== -1;
        });
        if (!lines.length) return;
        api('POST', '/api/add', { tracks: lines }).then(function (data) {
            neonFlash(btnAdd);
            gsap.to(trackInput, {
                opacity: 0.4,
                duration: 0.1,
                yoyo: true,
                repeat: 1,
                onComplete: function () {
                    trackInput.value = '';
                    inputCount.textContent = '0 строк';
                    gsap.set(trackInput, { opacity: 1 });
                }
            });
            flashPanel(document.querySelector('.input-panel'), 'rgba(0,255,136,0.2)');
            refresh();
        });
    });

    // ==================== FILE IMPORT ====================

    btnImportFile.addEventListener('click', function () {
        animatePress(this);
        fileInput.click();
    });

    fileInput.addEventListener('change', function () {
        var file = fileInput.files[0];
        if (!file) return;
        var reader = new FileReader();
        reader.onload = function () {
            fetch('/api/add-file', {
                method: 'POST',
                headers: { 'Content-Type': 'text/plain' },
                body: reader.result
            }).then(function () { refresh(); });
        };
        reader.readAsText(file);
        fileInput.value = '';
    });

    // ==================== CONTROLS ====================

    btnStart.addEventListener('click', function () {
        animatePress(this);
        buttonRipple(this, 'rgba(0,255,136,0.3)');
        api('POST', '/api/start').then(refresh);
    });

    btnPause.addEventListener('click', function () {
        animatePress(this);
        buttonRipple(this, 'rgba(255,170,0,0.3)');
        api('POST', '/api/pause').then(refresh);
    });

    btnStop.addEventListener('click', function () {
        animatePress(this);
        buttonRipple(this, 'rgba(255,68,102,0.3)');
        api('POST', '/api/stop').then(refresh);
    });

    btnRetry.addEventListener('click', function () {
        animatePress(this);
        api('POST', '/api/retry-failed').then(function (data) {
            if (data.retried > 0) {
                neonFlash(btnRetry);
            } else {
                shakeElement(btnRetry);
            }
            refresh();
        });
    });

    btnClearDone.addEventListener('click', function () {
        animatePress(this);
        api('POST', '/api/clear-done').then(refresh);
    });

    btnClearAll.addEventListener('click', function () {
        animatePress(this);
        if (!confirm('Очистить всю очередь?')) return;
        api('POST', '/api/clear-all').then(refresh);
    });

    // ==================== SETTINGS ====================

    btnSetDir.addEventListener('click', function () {
        animatePress(this);
        var path = downloadDir.value.trim();
        if (!path) return;
        api('POST', '/api/download-dir', { path: path }).then(function (data) {
            downloadDir.value = data.path;
            neonFlash(downloadDir);
            flashPanel(document.querySelector('.settings-panel'), 'rgba(0,255,136,0.15)');
        });
    });

    downloadDir.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') btnSetDir.click();
    });

    workersSlider.addEventListener('input', function () {
        workersVal.textContent = workersSlider.value;
        gsap.fromTo(workersVal, { scale: 1.3 }, { scale: 1, duration: 0.3, ease: 'back.out(3)' });
    });

    workersSlider.addEventListener('change', function () {
        api('POST', '/api/workers', { count: parseInt(workersSlider.value) });
    });

    // ==================== QUEUE FILTERS ====================

    $$('.filter-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            animatePress(this);
            $$('.filter-btn').forEach(function (b) { b.classList.remove('active'); });
            btn.classList.add('active');
            currentFilter = btn.getAttribute('data-filter');
            queueList.querySelectorAll('.q-item').forEach(function (item) {
                delete item.dataset.animated;
            });
            refresh();
        });
    });

    // ==================== REMOVE ITEM ====================

    function removeItem(id) {
        var el = queueList.querySelector('[data-id="' + id + '"]');
        if (el) {
            gsap.to(el, {
                opacity: 0,
                x: 40,
                height: 0,
                paddingTop: 0,
                paddingBottom: 0,
                duration: 0.35,
                ease: 'power2.in',
                onComplete: function () {
                    api('DELETE', '/api/remove/' + id).then(refresh);
                }
            });
        } else {
            api('DELETE', '/api/remove/' + id).then(refresh);
        }
    }

    // ==================== STATUS ====================

    function updateStatusTag(running, paused) {
        var was = statusTag.textContent;
        statusTag.className = 'tag';
        if (paused) {
            statusTag.textContent = 'пауза';
            statusTag.classList.add('paused');
        } else if (running) {
            statusTag.textContent = 'работает';
            statusTag.classList.add('active');
        } else {
            statusTag.textContent = 'остановлен';
        }
        if (was !== statusTag.textContent) {
            animateTag(statusTag);
        }
    }

    function updateButtons(running, paused) {
        btnStart.disabled = !running && !paused;
        btnPause.disabled = !running || paused;
        btnStop.disabled = !running && !paused;
    }

    // ==================== PROGRESS ====================

    function updateProgress(queue) {
        if (!queue) {
            gsap.to(progressBarWrap, { opacity: 0, duration: 0.2, onComplete: function () {
                progressBarWrap.style.display = 'none';
            }});
            return;
        }
        var total = queue.pending + queue.downloading + queue.done + queue.failed;
        if (total === 0) {
            gsap.to(progressBarWrap, { opacity: 0, duration: 0.2, onComplete: function () {
                progressBarWrap.style.display = 'none';
            }});
            return;
        }
        var done = queue.done + queue.failed;
        var pct = Math.round(done / total * 100);
        if (progressBarWrap.style.display === 'none') {
            progressBarWrap.style.display = '';
            gsap.fromTo(progressBarWrap, { opacity: 0, scaleY: 0 }, { opacity: 1, scaleY: 1, duration: 0.4, ease: 'back.out(2)' });
        }
        animateProgress(pct);
        progressText.textContent = done + ' / ' + total + '  (' + pct + '%)';
    }

    // ==================== RENDER QUEUE ====================

    function renderQueue(items) {
        if (!items || !items.length) {
            queueList.innerHTML = '<div class="queue-empty">Очередь пуста</div>';
            return;
        }
        var html = '';
        for (var i = 0; i < items.length; i++) {
            var item = items[i];
            var meta = '';
            if (item.status === 'done' && item.method) meta = item.method;
            else if (item.status === 'failed') meta = 'ошибка';
            else if (item.status === 'downloading') meta = 'загрузка...';
            else meta = 'ожидание';

            html += '<div class="q-item" data-id="' + item.id + '">' +
                '<div class="q-item-status ' + item.status + '"></div>' +
                '<div class="q-item-info">' +
                '<div class="q-item-query">' + esc(item.query) + '</div>' +
                '<div class="q-item-meta">' + esc(meta) + '</div>' +
                '</div>' +
                '<div class="q-item-progress">' + esc(item.progress || '') + '</div>' +
                '<button class="q-item-remove" data-id="' + item.id + '" title="Удалить">&times;</button>' +
                '</div>';
        }
        queueList.innerHTML = html;

        queueList.querySelectorAll('.q-item-remove').forEach(function (btn) {
            btn.addEventListener('click', function () {
                removeItem(this.getAttribute('data-id'));
            });
        });

        animateQueueItems();
    }

    function esc(s) {
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    // ==================== REFRESH ====================

    function refresh() {
        var qUrl = '/api/queue' + (currentFilter ? '?status=' + currentFilter : '');
        Promise.all([
            api('GET', '/api/status'),
            api('GET', qUrl),
            api('GET', '/api/download-dir'),
            api('GET', '/api/workers')
        ]).then(function (r) {
            var status = r[0], queue = r[1], dir = r[2], workers = r[3];

            updateStatusTag(status.running, status.paused);
            updateButtons(status.running, status.paused);
            animateStatPill(statDownloaded, status.stats.downloaded + ' скачано');
            animateStatPill(statFailed, status.stats.failed + ' ошибок');

            downloadDir.value = dir.path;
            workersSlider.value = workers.workers;
            workersVal.textContent = workers.workers;

            if (status.slsk_connected) {
                if (slskStatus.textContent !== 'подключён') {
                    slskStatus.textContent = 'подключён';
                    slskStatus.className = 'tag tag-sm active';
                    animateTag(slskStatus);
                }
            } else {
                if (slskStatus.textContent !== 'отключён') {
                    slskStatus.textContent = 'отключён';
                    slskStatus.className = 'tag tag-sm';
                }
            }

            updateProgress(queue);
            renderQueue(queue.items);
        });
    }

    // ==================== MINI SPEEDTEST ====================

    var stSparkData = [];
    var stSparkMax = 30;

    function formatEtaShort(sec) {
        if (!sec || sec <= 0) return '--';
        if (sec < 60) return Math.round(sec) + 'с';
        if (sec < 3600) return Math.round(sec / 60) + 'м';
        return Math.round(sec / 3600) + 'ч';
    }

    function animateStMetric(id, html) {
        var el = document.getElementById(id);
        if (!el) return;
        if (el.innerHTML !== html) {
            gsap.fromTo(el,
                { y: -2, opacity: 0.5 },
                { y: 0, opacity: 1, duration: 0.2, ease: 'power2.out',
                  onStart: function () { el.innerHTML = html; }
                }
            );
        }
    }

    function drawSparkline(data) {
        var canvas = document.getElementById('st-sparkline');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        var dpr = window.devicePixelRatio || 1;
        var w = canvas.clientWidth;
        var h = canvas.clientHeight;
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, w, h);

        if (!data.length) {
            ctx.fillStyle = '#3a3a4a';
            ctx.font = '9px "Share Tech Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText('нет данных', w / 2, h / 2 + 3);
            return;
        }

        var maxVal = Math.max.apply(null, data) || 1;
        maxVal *= 1.2;
        var pad = 4;
        var cw = w - pad * 2;
        var ch = h - pad * 2;
        var step = cw / Math.max(data.length - 1, 1);

        ctx.beginPath();
        ctx.moveTo(pad, pad + ch);
        for (var i = 0; i < data.length; i++) {
            var x = pad + i * step;
            var y = pad + ch - (data[i] / maxVal) * ch;
            ctx.lineTo(x, y);
        }
        ctx.lineTo(pad + (data.length - 1) * step, pad + ch);
        ctx.closePath();
        var grad = ctx.createLinearGradient(0, pad, 0, pad + ch);
        grad.addColorStop(0, 'rgba(255, 107, 157, 0.2)');
        grad.addColorStop(1, 'rgba(255, 107, 157, 0.01)');
        ctx.fillStyle = grad;
        ctx.fill();

        ctx.beginPath();
        for (var j = 0; j < data.length; j++) {
            var lx = pad + j * step;
            var ly = pad + ch - (data[j] / maxVal) * ch;
            if (j === 0) ctx.moveTo(lx, ly);
            else ctx.lineTo(lx, ly);
        }
        ctx.strokeStyle = '#ff6b9d';
        ctx.lineWidth = 1.5;
        ctx.lineJoin = 'round';
        ctx.shadowColor = 'rgba(255, 107, 157, 0.4)';
        ctx.shadowBlur = 4;
        ctx.stroke();
        ctx.shadowBlur = 0;

        for (var k = 0; k < data.length; k++) {
            var dx = pad + k * step;
            var dy = pad + ch - (data[k] / maxVal) * ch;
            ctx.beginPath();
            ctx.arc(dx, dy, 2, 0, Math.PI * 2);
            ctx.fillStyle = '#ff6b9d';
            ctx.fill();
        }
    }

    function pollSpeedtestMini() {
        fetch('/api/speedtest').then(function (r) { return r.json(); }).then(function (data) {
            var sp = data.speed || {};
            var tm = data.timing || {};
            var q = data.queue || {};

            var curMbps = sp.current_mbps || 0;
            var avgMbps = sp.avg_mbps || 0;
            var remaining = (q.pending || 0) + (q.downloading || 0);
            var etaSec = tm.eta_seconds || 0;
            var running = data.running;

            animateStMetric('st-current', curMbps + '<span class="st-unit">MB/s</span>');
            animateStMetric('st-avg', avgMbps + '<span class="st-unit">MB/s</span>');
            animateStMetric('st-remaining', remaining + '<span class="st-unit">треков</span>');
            animateStMetric('st-eta', formatEtaShort(etaSec) + '<span class="st-unit"></span>');

            stSparkData.push(curMbps);
            if (stSparkData.length > stSparkMax) stSparkData.shift();
            drawSparkline(stSparkData);

            var statusEl = document.getElementById('st-status');
            if (statusEl) {
                if (running) {
                    statusEl.textContent = 'загрузка... ' + curMbps + ' MB/s';
                    statusEl.className = 'speedtest-mini-status active';
                } else {
                    statusEl.textContent = remaining > 0 ? 'остановлен' : 'ожидание данных...';
                    statusEl.className = 'speedtest-mini-status';
                }
            }
        }).catch(function () {});
    }

    // ==================== INIT ====================

    var loadingEl = createLoadingScreen();
    initCursorTrail();
    updateTrail();

    window.addEventListener('load', function () {
        removeLoadingScreen();
        initAnimations();
        refresh();
        pollTimer = setInterval(refresh, 1500);
        pollSpeedtestMini();
        setInterval(pollSpeedtestMini, 2000);
    });
})();
