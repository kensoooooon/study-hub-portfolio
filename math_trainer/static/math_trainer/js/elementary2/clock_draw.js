// 1) シングル時計：キャンバス中心＆安全パディングで半径を決める
function drawSingleClock(stage, hour, minute) {
    stage.removeAllChildren();

    const W = stage.canvas.width;
    const H = stage.canvas.height;
    const pad = Math.min(W, H) * 0.08;         // ← はみ出し防止の安全マージン（5〜8%で微調整可）
    const cx  = W / 2;
    const cy  = H / 2;
    const r   = Math.min(W, H) / 2 - pad;

    drawSingleClockOnPosition(stage, hour, minute, cx, cy, r);
    stage.update();
}

// 2) ダブル時計：左右の“セル”を計算し、その中で半径を決める
function drawDoubleClock(stage, hour1, minute1, hour2, minute2) {
    stage.removeAllChildren();

    const W = stage.canvas.width;
    const H = stage.canvas.height;
    const pad = Math.min(W, H) * 0.08;         // 外周のマージン
    const gap = Math.min(W, H) * 0.08;         // 2つの時計のあいだの隙間
    const usableW = W - pad * 2;
    const cellW = (usableW - gap) / 2;

    // 2つのセルの中で、縦横どちらにも収まる最大半径をとる
    const r = Math.min(cellW, H - pad * 2) / 2 - pad * 0.5;
    const cy = H / 2;
    const cx1 = pad + cellW / 2;
    const cx2 = W - pad - cellW / 2;

    drawSingleClockOnPosition(stage, hour1, minute1, cx1, cy, r);
    drawSingleClockOnPosition(stage, hour2, minute2, cx2, cy, r);
    stage.update();
}

// 3) 実描画：数字/目盛/針を “半径に対する比率” で描く
function drawSingleClockOnPosition(stage, hour, minute, centerX, centerY, radius) {
    const borderW   = Math.max(2, Math.round(radius * 0.025)); // 外枠の線幅
    const majorTick = Math.max(10, Math.round(radius * 0.11)); // 5分刻みの目盛長
    const minorTick = Math.max(4,  Math.round(radius * 0.04)); // 1分刻みの目盛長
    const fontSize  = Math.max(10, Math.round(radius * 0.13)); // 数字のサイズ

    // 文字盤の外枠
    const circle = new createjs.Shape();
    circle.graphics
        .setStrokeStyle(borderW, 'round', 'round')
        .beginStroke("#000")
        .drawCircle(centerX, centerY, radius);
    stage.addChild(circle);

    // 数字（1〜12）
    for (let i = 1; i <= 12; i++) {
        const angle = (i - 3) * (Math.PI * 2) / 12;
        const x = centerX + (radius - majorTick - borderW * 1.5) * Math.cos(angle);
        const y = centerY + (radius - majorTick - borderW * 1.5) * Math.sin(angle);
        const text = new createjs.Text(i.toString(), `${fontSize}px Arial`, "#000");
        text.textAlign = "center";
        text.textBaseline = "middle";
        text.x = x; text.y = y;
        stage.addChild(text);
    }

    // 目盛り（60本）
    for (let i = 0; i < 60; i++) {
        const angle = (i - 15) * (Math.PI * 2) / 60;
        const len = (i % 5 === 0) ? majorTick : minorTick;

        const sx = centerX + (radius - borderW / 2) * Math.cos(angle);
        const sy = centerY + (radius - borderW / 2) * Math.sin(angle);
        const ex = centerX + (radius - len)          * Math.cos(angle);
        const ey = centerY + (radius - len)          * Math.sin(angle);

        const tick = new createjs.Shape();
        tick.graphics
        .setStrokeStyle(i % 5 === 0 ? borderW : Math.max(1, borderW - 1))
        .beginStroke("#000")
        .moveTo(sx, sy).lineTo(ex, ey);
        stage.addChild(tick);
    }

    // 針（角度は従来どおり／長さは半径比）
    const hourAngle   = ((hour % 12) + minute / 60) * (Math.PI * 2) / 12 - Math.PI / 2;
    const minuteAngle =  (minute      * (Math.PI * 2) / 60)          - Math.PI / 2;

    const hourLen = radius * 0.62;
    const minLen  = radius * 0.88;

    const shortHand = new createjs.Shape();
    shortHand.graphics
        .setStrokeStyle(Math.max(3, borderW))
        .beginStroke("#000")
        .moveTo(centerX, centerY)
        .lineTo(centerX + hourLen * Math.cos(hourAngle),
                centerY + hourLen * Math.sin(hourAngle));
    stage.addChild(shortHand);

    const longHand = new createjs.Shape();
    longHand.graphics
        .setStrokeStyle(Math.max(2, borderW - 1))
        .beginStroke("#000")
        .moveTo(centerX, centerY)
        .lineTo(centerX + minLen * Math.cos(minuteAngle),
                centerY + minLen * Math.sin(minuteAngle));
    stage.addChild(longHand);

    // 中心キャップ
    const cap = new createjs.Shape();
    cap.graphics.beginFill("#000").drawCircle(centerX, centerY, Math.max(3, borderW));
    stage.addChild(cap);
}
