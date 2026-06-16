(function () {
    'use strict';

    var canvas = document.getElementById('bg-canvas');
    if (!canvas) return;
    var ctx = canvas.getContext('2d');

    var W, H;
    var particles = [];
    var gridLines = [];
    var mouseX = -1000;
    var mouseY = -1000;
    var frame = 0;

    var PARTICLE_COUNT = 80;
    var GRID_SPACING = 60;
    var CONNECT_DIST = 150;
    var MOUSE_RADIUS = 200;

    var neonColor = { r: 0, g: 255, b: 136 };

    function resize() {
        W = canvas.width = window.innerWidth;
        H = canvas.height = window.innerHeight;
        initGrid();
    }

    function initGrid() {
        gridLines = [];
        for (var x = 0; x <= W; x += GRID_SPACING) {
            gridLines.push({ x1: x, y1: 0, x2: x, y2: H, progress: 0, speed: 0.003 + Math.random() * 0.005, delay: Math.random() });
        }
        for (var y = 0; y <= H; y += GRID_SPACING) {
            gridLines.push({ x1: 0, y1: y, x2: W, y2: y, progress: 0, speed: 0.003 + Math.random() * 0.005, delay: Math.random() });
        }
    }

    function initParticles() {
        particles = [];
        for (var i = 0; i < PARTICLE_COUNT; i++) {
            particles.push({
                x: Math.random() * W,
                y: Math.random() * H,
                vx: (Math.random() - 0.5) * 0.4,
                vy: (Math.random() - 0.5) * 0.4,
                size: Math.random() * 2 + 0.5,
                alpha: Math.random() * 0.5 + 0.1,
                pulse: Math.random() * Math.PI * 2,
                pulseSpeed: 0.01 + Math.random() * 0.02
            });
        }
    }

    // Falling code chars (Matrix rain, subtle)
    var codeChars = '01アイウエオカキクケコサシスセソ';
    var drops = [];
    var DROP_COUNT = 20;

    function initDrops() {
        drops = [];
        for (var i = 0; i < DROP_COUNT; i++) {
            drops.push({
                x: Math.random() * W,
                y: Math.random() * H - H,
                speed: 0.5 + Math.random() * 1.5,
                chars: [],
                len: 5 + Math.floor(Math.random() * 15),
                alpha: 0.02 + Math.random() * 0.04
            });
            for (var j = 0; j < drops[i].len; j++) {
                drops[i].chars.push(codeChars[Math.floor(Math.random() * codeChars.length)]);
            }
        }
    }

    // Data stream horizontal lines
    var streams = [];
    var STREAM_COUNT = 8;

    function initStreams() {
        streams = [];
        for (var i = 0; i < STREAM_COUNT; i++) {
            streams.push({
                x: Math.random() * W,
                y: Math.random() * H,
                length: 40 + Math.random() * 120,
                speed: 1 + Math.random() * 3,
                alpha: 0.015 + Math.random() * 0.03
            });
        }
    }

    function drawGrid(t) {
        for (var i = 0; i < gridLines.length; i++) {
            var g = gridLines[i];
            g.delay -= 0.001;
            if (g.delay > 0) continue;
            g.progress = Math.min(g.progress + g.speed, 1);

            var ease = 1 - Math.pow(1 - g.progress, 3);
            var px = g.x1 + (g.x2 - g.x1) * ease;
            var py = g.y1 + (g.y2 - g.y1) * ease;

            var distToMouse = 0;
            var mx = (g.x1 + g.x2) / 2;
            var my = (g.y1 + g.y2) / 2;
            var dx = mx - mouseX;
            var dy = my - mouseY;
            distToMouse = Math.sqrt(dx * dx + dy * dy);

            var alpha = 0.04;
            if (distToMouse < MOUSE_RADIUS) {
                alpha = 0.04 + 0.12 * (1 - distToMouse / MOUSE_RADIUS);
            }

            // Pulse effect
            alpha += Math.sin(t * 0.001 + i * 0.5) * 0.01;

            ctx.beginPath();
            ctx.moveTo(g.x1, g.y1);
            ctx.lineTo(px, py);
            ctx.strokeStyle = 'rgba(' + neonColor.r + ',' + neonColor.g + ',' + neonColor.b + ',' + alpha + ')';
            ctx.lineWidth = 0.5;
            ctx.stroke();
        }
    }

    function drawParticles(t) {
        for (var i = 0; i < particles.length; i++) {
            var p = particles[i];

            p.pulse += p.pulseSpeed;
            var pulseAlpha = p.alpha + Math.sin(p.pulse) * 0.15;

            p.x += p.vx;
            p.y += p.vy;

            if (p.x < 0) p.x = W;
            if (p.x > W) p.x = 0;
            if (p.y < 0) p.y = H;
            if (p.y > H) p.y = 0;

            // Mouse repulsion
            var dmx = p.x - mouseX;
            var dmy = p.y - mouseY;
            var dmd = Math.sqrt(dmx * dmx + dmy * dmy);
            if (dmd < MOUSE_RADIUS && dmd > 0) {
                var force = (MOUSE_RADIUS - dmd) / MOUSE_RADIUS * 0.5;
                p.vx += (dmx / dmd) * force;
                p.vy += (dmy / dmd) * force;
            }

            // Dampen velocity
            p.vx *= 0.99;
            p.vy *= 0.99;

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(' + neonColor.r + ',' + neonColor.g + ',' + neonColor.b + ',' + pulseAlpha + ')';
            ctx.fill();

            // Glow
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(' + neonColor.r + ',' + neonColor.g + ',' + neonColor.b + ',' + (pulseAlpha * 0.15) + ')';
            ctx.fill();

            // Connect nearby particles
            for (var j = i + 1; j < particles.length; j++) {
                var p2 = particles[j];
                var cdx = p.x - p2.x;
                var cdy = p.y - p2.y;
                var dist = Math.sqrt(cdx * cdx + cdy * cdy);
                if (dist < CONNECT_DIST) {
                    var lineAlpha = (1 - dist / CONNECT_DIST) * 0.15;
                    ctx.beginPath();
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.strokeStyle = 'rgba(' + neonColor.r + ',' + neonColor.g + ',' + neonColor.b + ',' + lineAlpha + ')';
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        }
    }

    function drawDrops() {
        ctx.font = '10px monospace';
        for (var i = 0; i < drops.length; i++) {
            var d = drops[i];
            d.y += d.speed;
            if (d.y > H + d.len * 14) {
                d.y = -d.len * 14;
                d.x = Math.random() * W;
            }
            for (var j = 0; j < d.len; j++) {
                var charY = d.y + j * 14;
                if (charY < 0 || charY > H) continue;
                var charAlpha = d.alpha * (j / d.len);
                if (j === d.len - 1) {
                    ctx.fillStyle = 'rgba(' + neonColor.r + ',' + neonColor.g + ',' + neonColor.b + ',' + (charAlpha * 3) + ')';
                } else {
                    ctx.fillStyle = 'rgba(' + neonColor.r + ',' + neonColor.g + ',' + neonColor.b + ',' + charAlpha + ')';
                }
                // Randomly change char
                if (Math.random() < 0.02) {
                    d.chars[j] = codeChars[Math.floor(Math.random() * codeChars.length)];
                }
                ctx.fillText(d.chars[j], d.x, charY);
            }
        }
    }

    function drawStreams() {
        for (var i = 0; i < streams.length; i++) {
            var s = streams[i];
            s.x += s.speed;
            if (s.x > W + s.length) {
                s.x = -s.length;
                s.y = Math.random() * H;
            }
            var grad = ctx.createLinearGradient(s.x, s.y, s.x + s.length, s.y);
            grad.addColorStop(0, 'rgba(' + neonColor.r + ',' + neonColor.g + ',' + neonColor.b + ',0)');
            grad.addColorStop(0.5, 'rgba(' + neonColor.r + ',' + neonColor.g + ',' + neonColor.b + ',' + s.alpha + ')');
            grad.addColorStop(1, 'rgba(' + neonColor.r + ',' + neonColor.g + ',' + neonColor.b + ',0)');
            ctx.beginPath();
            ctx.moveTo(s.x, s.y);
            ctx.lineTo(s.x + s.length, s.y);
            ctx.strokeStyle = grad;
            ctx.lineWidth = 1;
            ctx.stroke();
        }
    }

    // Hexagonal pulse rings
    var rings = [];
    function spawnRing(x, y) {
        rings.push({ x: x, y: y, radius: 0, maxRadius: 80 + Math.random() * 60, alpha: 0.15, speed: 0.8 + Math.random() * 0.5 });
    }

    function drawRings() {
        for (var i = rings.length - 1; i >= 0; i--) {
            var r = rings[i];
            r.radius += r.speed;
            r.alpha *= 0.98;
            if (r.alpha < 0.002 || r.radius > r.maxRadius) {
                rings.splice(i, 1);
                continue;
            }
            ctx.beginPath();
            ctx.arc(r.x, r.y, r.radius, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(' + neonColor.r + ',' + neonColor.g + ',' + neonColor.b + ',' + r.alpha + ')';
            ctx.lineWidth = 1;
            ctx.stroke();
        }
    }

    // Occasional ring spawn
    var ringTimer = 0;

    function animate(t) {
        ctx.clearRect(0, 0, W, H);

        // Dark gradient background
        var bgGrad = ctx.createRadialGradient(W / 2, H / 2, 0, W / 2, H / 2, Math.max(W, H) * 0.7);
        bgGrad.addColorStop(0, '#0d0d18');
        bgGrad.addColorStop(1, '#050508');
        ctx.fillStyle = bgGrad;
        ctx.fillRect(0, 0, W, H);

        drawGrid(t);
        drawDrops();
        drawStreams();
        drawParticles(t);
        drawRings();

        // Spawn rings near mouse occasionally
        ringTimer++;
        if (ringTimer > 60 && mouseX > 0) {
            if (Math.random() < 0.03) {
                spawnRing(mouseX + (Math.random() - 0.5) * 40, mouseY + (Math.random() - 0.5) * 40);
                ringTimer = 0;
            }
        }

        frame++;
        requestAnimationFrame(animate);
    }

    // Mouse tracking
    document.addEventListener('mousemove', function (e) {
        mouseX = e.clientX;
        mouseY = e.clientY;
    });

    document.addEventListener('mouseleave', function () {
        mouseX = -1000;
        mouseY = -1000;
    });

    // Random ring spawns even without mouse
    setInterval(function () {
        if (Math.random() < 0.3) {
            spawnRing(Math.random() * W, Math.random() * H);
        }
    }, 3000);

    window.addEventListener('resize', resize);
    resize();
    initParticles();
    initDrops();
    initStreams();
    animate(0);
})();
