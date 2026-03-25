"""Cup Heroes — Gacha Drop Rate Simulator (English).

Interactive card-pack economics tool embedded via Streamlit Custom Components v2.
Translated from the original French HTML simulator.
"""

import streamlit as st

_HTML = """\
<header>
  <h1>🎴 Cup Heroes — Gacha Drop Rate Simulator</h1>
  <p>Pool: 18 Pragmatic + 9 Cool + 3 Iconic + 1 Joker = 31 items &nbsp;|&nbsp;
     <strong id="header-dpp" style="color:var(--orange)">10</strong> draws/pack &nbsp;|&nbsp;
     458 copies for max (Lv10) &nbsp;|&nbsp; 80 💎 = €1</p>
  <div class="joker-note">🃏 <strong>Joker Hero = universal consumable</strong> —
    Upgrades ANY hero card. Most precious item → lowest drop rate of all.</div>
</header>

<div class="container">

<!-- ══ CONTROLS ══ -->
<div class="controls">
  <div class="ctrl-label">⚙ Individual Drop Rates</div>
  <div class="control-grid">
    <div class="cg">
      <label>Pragmatic <span class="badge bp">×18 cards</span></label>
      <input type="range" id="r-prag" class="prag" min="0.5" max="8" step="0.1" value="4.6">
      <div class="val" style="color:var(--pragmatic)"><span id="v-prag">4.6</span>% / card → <span id="t-prag">82.8</span>% tier</div>
    </div>
    <div class="cg">
      <label>Cool <span class="badge bc">×9 cards</span></label>
      <input type="range" id="r-cool" class="cool" min="0.5" max="8" step="0.1" value="1.5">
      <div class="val" style="color:var(--cool)"><span id="v-cool">1.5</span>% / card → <span id="t-cool">13.5</span>% tier</div>
    </div>
    <div class="cg">
      <label>Iconic <span class="badge bi">×3 cards</span></label>
      <input type="range" id="r-icon" class="icon" min="0.1" max="6" step="0.1" value="1.0">
      <div class="val" style="color:var(--iconic)"><span id="v-icon">1.0</span>% / card → <span id="t-icon">3.0</span>% tier</div>
    </div>
    <div class="cg">
      <label>🃏 Joker <span class="badge bj">×1 — must be &lt; Iconic</span></label>
      <input type="range" id="r-jok" class="jok" min="0.05" max="3" step="0.05" value="0.7">
      <div class="val" style="color:var(--joker)"><span id="v-jok">0.70</span>%</div>
    </div>
  </div>

  <!-- Draws per pack slider -->
  <div style="margin-top:20px;padding-top:18px;border-top:1px solid var(--border);">
    <div class="ctrl-label" style="margin-bottom:10px;">🎲 Draws per Pack</div>
    <div style="display:flex;align-items:center;gap:18px;flex-wrap:wrap;">
      <div style="flex:1;min-width:200px;">
        <input type="range" id="r-dpp" class="dpp" min="1" max="100" step="1" value="10" style="width:100%;cursor:pointer;">
      </div>
      <div style="font-size:22px;font-weight:800;color:var(--orange);min-width:80px;">
        <span id="v-dpp">10</span> <span style="font-size:13px;font-weight:500;color:var(--dim)">draws / pack</span>
      </div>
      <div style="font-size:12px;color:var(--dim);max-width:300px;line-height:1.6;">
        Currently: <strong style="color:var(--orange)"><span id="dpp-cost-note">€18.75 / draw</span></strong><br>
        Average cost per draw at selected price.
      </div>
    </div>
  </div>

  <div class="jw" id="jw">⚠ Joker (<span id="warn-jok">—</span>%) ≥ Iconic (<span id="warn-icon">—</span>%) — Joker must be rarer since it's universal.</div>

  <div class="totals-bar">
    <div class="tc"><div class="tl">TOTAL</div><div class="tv" id="sum-total">100.0%</div></div>
    <div class="tc"><div class="tl">TIER PRAGMATIC</div><div class="tv" style="color:var(--pragmatic)" id="tier-prag">82.8%</div></div>
    <div class="tc"><div class="tl">TIER COOL</div><div class="tv" style="color:var(--cool)" id="tier-cool">13.5%</div></div>
    <div class="tc"><div class="tl">TIER ICONIC (×3)</div><div class="tv" style="color:var(--iconic)" id="tier-icon">3.0%</div></div>
    <div class="tc"><div class="tl">JOKER (wildcard)</div><div class="tv" style="color:var(--joker)" id="tier-joker">0.70%</div></div>
  </div>

  <!-- Price + Presets -->
  <div style="margin-top:18px;">
    <div class="ctrl-label" style="margin-bottom:10px;">💎 Pack Price</div>
    <div class="price-row" id="price-row">
      <button class="price-btn" data-price="100">100 💎 = €1.25</button>
      <button class="price-btn" data-price="200">200 💎 = €2.50</button>
      <button class="price-btn" data-price="400">400 💎 = €5.00</button>
      <button class="price-btn" data-price="800">800 💎 = €10.00</button>
      <button class="price-btn" data-price="1000">1,000 💎 = €12.50</button>
      <button class="price-btn hot active" data-price="1500">1,500 💎 = €18.75 ★</button>
      <div class="sep"></div>
      <button class="preset-btn" id="preset-b" title="Balanced Scenario B">Preset B — Balanced</button>
      <button class="preset-btn" id="preset-1500" title="Recommended rates for 1500 diamond pack">Preset 1500 💎 Recommended</button>
    </div>
  </div>
</div>

<!-- ══ INSIGHTS ══ -->
<div id="insights"></div>

<!-- ══ UPGRADE TABLES ══ -->
<div class="st">Progression Cost per Card (current config)</div>
<div class="rg">

  <div class="card">
    <div class="ct"><span class="dot" style="background:var(--iconic)"></span>Iconic <span style="color:var(--dim);font-weight:400;font-size:11px">— <span class="lbl-icon">1.0</span>% / card (3 cards)</span></div>
    <div class="cs">Most powerful cards. Main monetization driver.</div>
    <table class="mt"><thead><tr><th>Level</th><th>Copies</th><th>Med. Packs</th><th>Med. Cost</th><th>90th pct Cost</th></tr></thead><tbody id="tb-iconic"></tbody></table>
    <p class="pct-note">90th pct: 10% of players spend more for the same result.</p>
  </div>

  <div class="card">
    <div class="ct"><span class="dot" style="background:var(--cool)"></span>Cool <span style="color:var(--dim);font-weight:400;font-size:11px">— <span class="lbl-cool">1.5</span>% / card (9 cards)</span></div>
    <div class="cs">Mid tier. Must remain significantly more accessible than Iconic.</div>
    <table class="mt"><thead><tr><th>Level</th><th>Copies</th><th>Med. Packs</th><th>Med. Cost</th><th>90th pct Cost</th></tr></thead><tbody id="tb-cool"></tbody></table>
    <p class="pct-note">90th pct: 10% of players spend more for the same result.</p>
  </div>

  <div class="card">
    <div class="ct"><span class="dot" style="background:var(--pragmatic)"></span>Pragmatic <span style="color:var(--dim);font-weight:400;font-size:11px">— <span class="lbl-prag">4.6</span>% / card (18 cards)</span></div>
    <div class="cs">Base tier. Frequent but 18 in pool → measured progression.</div>
    <table class="mt"><thead><tr><th>Level</th><th>Copies</th><th>Med. Packs</th><th>Med. Cost</th><th>90th pct Cost</th></tr></thead><tbody id="tb-prag"></tbody></table>
    <p class="pct-note">90th pct: 10% of players spend more for the same result.</p>
  </div>

  <div class="card" style="border-color:rgba(201,127,255,.3)">
    <div class="ct"><span class="dot" style="background:var(--joker)"></span>🃏 Joker Hero <span style="color:var(--dim);font-weight:400;font-size:11px">— <span class="lbl-jok">0.70</span>% (wildcard)</span></div>
    <div class="cs" style="color:var(--joker);opacity:.8">Universal consumable. Each Joker = +1 upgrade on the card of your choice.</div>
    <table class="jt"><thead><tr><th style="text-align:left">Joker Target</th><th>Med. Packs</th><th>Med. Cost</th><th>90th pct Cost</th></tr></thead><tbody id="tb-joker"></tbody></table>
    <p class="pct-note" style="color:rgba(201,127,255,.6)">Joker = flexible currency. Key metric: how many per session / month.</p>
  </div>

</div>

<!-- ══ CHART ══ -->
<div class="st">Cumulative Cost Curve — Iconic / Cool / Pragmatic (median)</div>
<div class="card" style="margin-bottom:22px;"><div class="chart-wrap"><canvas id="chart"></canvas></div></div>

<!-- ══ CARD PACK PREVIEW ══ -->
<div class="st">🎴 Hero Card Pack Example — complete drop rates (31 items)</div>
<div class="pack-preview">
  <div class="pack-header">
    <div class="pack-icon">🎴</div>
    <div class="pack-info">
      <h3 id="pack-name">Hero Card Pack — 1,500 💎</h3>
      <p><span id="pack-draws">10</span> draws · Duplicates possible · Hero-specific cards only</p>
    </div>
    <div class="pack-total-badge">
      <div class="ptl">DISPLAYED TOTAL</div>
      <div class="ptv" id="pack-sum-val">100.0%</div>
    </div>
  </div>
  <div class="drop-list" id="drop-list"></div>
  <div class="drop-sum-row">
    <span class="ds-label">Sum of all rates:</span>
    <span class="ds-val" id="pack-sum-bot">100.0%</span>
  </div>
</div>

<!-- ══ SCENARIO COMPARISON ══ -->
<div class="st">Reference Scenario Comparison — max median cost (Lv10), 1,500 💎 pack</div>
<div class="sct">
  <p style="color:var(--dim);font-size:12px;margin-bottom:14px;">Constraint: <strong style="color:var(--joker)">Joker rate &lt; Iconic rate</strong> respected in all scenarios. Joker = universal wildcard.</p>
  <table class="sc">
    <thead><tr>
      <th>Scenario</th><th>Pragmatic</th><th>Cool</th><th>Iconic</th><th class="sj">Joker</th>
      <th>Max Pragmatic</th><th>Max Cool</th><th>Max Iconic</th><th class="sj">1 Joker every…</th>
    </tr></thead>
    <tbody>
      <tr>
        <td><strong class="sa">A — Harsh</strong><br><small style="color:var(--dim)">Iconic rare, Cool close</small></td>
        <td>4.6% ×18</td><td>1.5% ×9</td><td>1.0% ×3</td><td class="sj">0.7%</td>
        <td class="sa">€18,668</td><td class="sa">€57,250</td><td class="sa">€85,875</td><td class="sj">~14 packs</td>
      </tr>
      <tr style="background:rgba(255,170,68,.04)">
        <td><strong class="sb">B — Balanced ★</strong><br><small style="color:var(--dim)">Recommended · clear Cool/Iconic ratio</small></td>
        <td>4.0% ×18</td><td>2.5% ×9</td><td>1.5% ×3</td><td class="sj">1.0%</td>
        <td class="sb">€21,469</td><td class="sb">€34,350</td><td class="sb">€57,250</td><td class="sj">~10 packs</td>
      </tr>
      <tr style="background:rgba(68,204,119,.04)">
        <td><strong class="sc2">C — 1500 💎 ★★</strong><br><small style="color:var(--dim)">Boosted rates for perceived value at this price</small></td>
        <td>3.5% ×18</td><td>3.0% ×9</td><td>2.5% ×3</td><td class="sj">1.0%</td>
        <td class="sc2">€24,536</td><td class="sc2">€28,625</td><td class="sc2">€34,350</td><td class="sj">~10 packs</td>
      </tr>
      <tr>
        <td><strong style="color:#aaa">D — Generous</strong><br><small style="color:var(--dim)">Iconic very accessible (saturation risk)</small></td>
        <td>3.0% ×18</td><td>3.2% ×9</td><td>4.0% ×3</td><td class="sj">0.8%</td>
        <td style="color:#aaa">€28,625</td><td style="color:#aaa">€26,836</td><td style="color:#aaa">€21,469</td><td class="sj">~13 packs</td>
      </tr>
    </tbody>
  </table>
  <p style="margin-top:11px;font-size:11px;color:var(--dim)">★★ Scenario C recommended at 1,500 💎: Iconic at 2.5%/card gives a first upgrade (Lv2, 10 copies) at ~€750, Lv5 (88 copies) at ~€6,600, max (458 copies) at ~€34,350. Cool/Iconic difference: 1.2× ratio. Joker 1 every 10 packs = €188/joker.</p>
</div>

<!-- ══ NOTES ══ -->
<div class="st">Design Notes</div>
<div class="insight joker">
  <strong>🃏 Joker = wildcard, not a card to "max out"</strong><br>
  As a consumable, each Joker is used immediately. The acquisition rate (1 every X packs) is the key KPI, not packs-to-max.
  At 1,500 💎/pack: a Joker at 1.0% costs ~€188 median (~10 packs). That's the "premium" players pay for the flexibility to target any card.
</div>
<div class="insight price">
  <strong>💎 At 1,500 diamonds (€18.75): increase Iconic rates</strong><br>
  At this price, keeping rates too low (e.g. Iconic at 1%) makes the first upgrade of an Iconic card (~€1,875) hard to justify.
  Scenario C (Iconic at 2.5%) offers a first visible upgrade at ~€750 and Lv5 at ~€6,600 — gradual long-term progression.
</div>
<div class="insight ok">
  <strong>✓ Everyone starts with all cards</strong><br>
  The gacha only involves duplicates for upgrades. Early levels (Lv2–Lv4, 10–38 copies) must feel reachable quickly.
  Target: first Iconic Lv2 upgrade (10 copies) in 30–60 packs at the target price.
</div>
<div class="insight warn">
  <strong>⚠ Without pity, high variance on rare items</strong><br>
  10% of players will spend ~12% more than the median. For Joker at very low rates (&lt;0.5%), subjective variance is high.
  Displaying average frequency in the UI ("1 Joker every ~13 packs") helps manage expectations.
</div>

</div><!-- /container -->
<footer>Cup Heroes — Gacha Simulator · 80 💎 = €1 · Joker rate &lt; Iconic rate</footer>
"""

_CSS = """\
:host {
  --bg:#0f0f14; --surface:#1a1a24; --surface2:#22222f; --border:#2e2e40;
  --text:#e8e8f0; --dim:#8888aa;
  --iconic:#ffc940; --cool:#4da6ff; --pragmatic:#aaaacc; --joker:#c97fff;
  --red:#ff5555; --orange:#ffaa44; --green:#44cc77;
  display:block; background:var(--bg); color:var(--text);
  font-family:'Segoe UI',system-ui,sans-serif; font-size:14px;
}
*{box-sizing:border-box;margin:0;padding:0;}

/* Header */
header{background:linear-gradient(135deg,#1a1030,#0f1a30);padding:24px 40px;border-bottom:1px solid var(--border);}
header h1{font-size:21px;font-weight:700;}
header p{color:var(--dim);margin-top:5px;font-size:13px;}
.joker-note{margin-top:10px;background:rgba(201,127,255,.1);border:1px solid rgba(201,127,255,.3);border-radius:8px;padding:10px 14px;font-size:13px;color:var(--joker);}

.container{max-width:1380px;margin:0 auto;padding:28px 22px;}

/* Controls */
.controls{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:22px;margin-bottom:18px;}
.ctrl-label{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:var(--dim);margin-bottom:14px;}
.control-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:22px;}
.cg label{display:block;font-size:12px;color:var(--dim);margin-bottom:7px;font-weight:500;}
.cg input[type=range]{width:100%;cursor:pointer;}
.cg input.prag{accent-color:var(--pragmatic);}
.cg input.cool{accent-color:var(--cool);}
.cg input.icon{accent-color:var(--iconic);}
.cg input.jok {accent-color:var(--joker);}
.cg input.dpp {accent-color:var(--orange);}
.cg .val{font-size:16px;font-weight:700;margin-top:5px;}
.badge{display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600;margin-left:5px;}
.bi{background:rgba(255,201,64,.15);color:var(--iconic);}
.bc{background:rgba(77,166,255,.15);color:var(--cool);}
.bp{background:rgba(170,170,204,.15);color:var(--pragmatic);}
.bj{background:rgba(201,127,255,.15);color:var(--joker);}

/* Totals bar */
.totals-bar{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px;padding-top:18px;border-top:1px solid var(--border);}
.tc{background:var(--surface2);border-radius:8px;padding:9px 14px;flex:1;min-width:120px;text-align:center;}
.tc .tl{font-size:11px;color:var(--dim);margin-bottom:3px;}
.tc .tv{font-size:15px;font-weight:700;}
.sum-ok{color:var(--green)!important;}
.sum-warn{color:var(--red)!important;}

/* Price + Presets */
.price-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;align-items:center;}
.price-btn{background:var(--surface2);border:1px solid var(--border);color:var(--dim);padding:7px 15px;border-radius:7px;cursor:pointer;font-size:13px;font-weight:600;transition:all .15s;}
.price-btn.active,.price-btn:hover{background:var(--iconic);color:#111;border-color:var(--iconic);}
.price-btn.hot{border-color:var(--orange);color:var(--orange);}
.price-btn.hot.active,.price-btn.hot:hover{background:var(--orange);color:#111;}
.sep{width:1px;background:var(--border);height:32px;align-self:center;}
.preset-btn{background:rgba(201,127,255,.1);border:1px solid rgba(201,127,255,.4);color:var(--joker);padding:7px 15px;border-radius:7px;cursor:pointer;font-size:12px;font-weight:600;transition:all .15s;}
.preset-btn:hover{background:rgba(201,127,255,.25);}

/* Joker warning */
.jw{background:rgba(255,85,85,.1);border:1px solid rgba(255,85,85,.4);border-radius:8px;padding:10px 14px;font-size:13px;color:var(--red);margin-bottom:12px;display:none;}
.jw.on{display:block;}

/* Insight boxes */
.insight{background:var(--surface2);border-left:3px solid var(--iconic);border-radius:0 8px 8px 0;padding:13px 17px;margin-bottom:11px;font-size:13px;line-height:1.7;}
.insight strong{color:var(--iconic);}
.insight.warn{border-left-color:var(--red);}
.insight.warn strong{color:var(--red);}
.insight.ok{border-left-color:var(--green);}
.insight.ok strong{color:var(--green);}
.insight.joker{border-left-color:var(--joker);}
.insight.joker strong{color:var(--joker);}
.insight.price{border-left-color:var(--orange);}
.insight.price strong{color:var(--orange);}

/* Section title */
.st{font-size:16px;font-weight:700;margin:26px 0 13px;display:flex;align-items:center;gap:10px;}
.st::after{content:'';flex:1;height:1px;background:var(--border);}

/* Cards grid */
.rg{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:22px;}
@media(max-width:960px){.rg{grid-template-columns:1fr;}}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px;}
.ct{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;margin-bottom:3px;display:flex;align-items:center;gap:7px;}
.cs{font-size:12px;color:var(--dim);margin-bottom:13px;}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex-shrink:0;}

/* Milestone table */
table.mt{width:100%;border-collapse:collapse;}
table.mt th{font-size:11px;color:var(--dim);text-align:right;padding:5px 7px;font-weight:500;}
table.mt th:first-child{text-align:left;}
table.mt td{padding:7px 7px;border-top:1px solid var(--border);font-size:13px;text-align:right;}
table.mt td:first-child{text-align:left;color:var(--dim);font-size:12px;}
table.mt .pk{font-weight:600;}
table.mt .eu{color:var(--dim);font-size:12px;}
table.mt .euh{color:var(--iconic);font-weight:700;}
table.mt tr:hover td{background:var(--surface2);}
table.mt tr.hl td{background:rgba(255,201,64,.05);}

/* Joker table */
table.jt{width:100%;border-collapse:collapse;}
table.jt th{font-size:11px;color:var(--joker);text-align:right;padding:5px 7px;font-weight:500;border-bottom:1px solid rgba(201,127,255,.2);}
table.jt th:first-child{text-align:left;}
table.jt td{padding:8px 7px;border-top:1px solid var(--border);font-size:13px;text-align:right;}
table.jt td:first-child{text-align:left;color:var(--dim);font-size:12px;}
table.jt tr:hover td{background:var(--surface2);}
.pct-note{font-size:11px;color:var(--dim);margin-top:9px;}

/* Chart */
.chart-wrap{position:relative;height:290px;}

/* Scenario table */
.sct{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px;margin-bottom:22px;overflow-x:auto;}
table.sc{width:100%;border-collapse:collapse;min-width:820px;}
table.sc th{font-size:11px;color:var(--dim);padding:7px 11px;text-align:right;font-weight:500;border-bottom:1px solid var(--border);white-space:nowrap;}
table.sc th:first-child{text-align:left;}
table.sc td{padding:9px 11px;border-top:1px solid var(--border);text-align:right;font-size:13px;white-space:nowrap;}
table.sc td:first-child{text-align:left;}
table.sc tr:hover td{background:var(--surface2);}
.sa{color:var(--red);} .sb{color:var(--orange);} .sc2{color:var(--green);} .sj{color:var(--joker);}

/* Card Pack Preview */
.pack-preview{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:22px;}
.pack-header{display:flex;align-items:center;gap:14px;margin-bottom:18px;padding-bottom:16px;border-bottom:1px solid var(--border);}
.pack-icon{width:54px;height:54px;border-radius:10px;background:linear-gradient(135deg,#2a1060,#0a2050);border:2px solid rgba(255,201,64,.4);display:flex;align-items:center;justify-content:center;font-size:24px;flex-shrink:0;}
.pack-info h3{font-size:15px;font-weight:700;}
.pack-info p{font-size:12px;color:var(--dim);margin-top:3px;}
.pack-total-badge{margin-left:auto;background:var(--surface2);border-radius:8px;padding:8px 14px;text-align:center;flex-shrink:0;}
.pack-total-badge .ptl{font-size:11px;color:var(--dim);}
.pack-total-badge .ptv{font-size:18px;font-weight:700;}
.drop-list{display:flex;flex-direction:column;gap:4px;}
.drop-section-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;padding:10px 0 5px;color:var(--dim);display:flex;align-items:center;gap:8px;}
.drop-section-title::after{content:'';flex:1;height:1px;background:var(--border);}
.drop-row{display:flex;align-items:center;gap:10px;padding:6px 10px;border-radius:7px;transition:background .1s;}
.drop-row:hover{background:var(--surface2);}
.drop-row .dr-badge{width:72px;font-size:11px;font-weight:700;padding:3px 7px;border-radius:4px;text-align:center;flex-shrink:0;}
.drop-row .dr-name{flex:1;font-size:13px;}
.drop-row .dr-bar-wrap{width:160px;height:8px;background:var(--surface2);border-radius:4px;overflow:hidden;flex-shrink:0;}
.drop-row .dr-bar{height:100%;border-radius:4px;transition:width .3s;}
.drop-row .dr-pct{width:52px;text-align:right;font-size:13px;font-weight:700;flex-shrink:0;}
.iconic-row .dr-badge{background:rgba(255,201,64,.15);color:var(--iconic);}
.iconic-row .dr-bar{background:var(--iconic);}
.iconic-row .dr-pct{color:var(--iconic);}
.cool-row .dr-badge{background:rgba(77,166,255,.15);color:var(--cool);}
.cool-row .dr-bar{background:var(--cool);}
.cool-row .dr-pct{color:var(--cool);}
.pragmatic-row .dr-badge{background:rgba(170,170,204,.15);color:var(--pragmatic);}
.pragmatic-row .dr-bar{background:var(--pragmatic);}
.pragmatic-row .dr-pct{color:var(--pragmatic);}
.joker-row .dr-badge{background:rgba(201,127,255,.15);color:var(--joker);}
.joker-row .dr-bar{background:var(--joker);}
.joker-row .dr-pct{color:var(--joker);}
.drop-sum-row{display:flex;justify-content:flex-end;align-items:center;gap:10px;margin-top:12px;padding-top:12px;border-top:1px solid var(--border);}
.drop-sum-row .ds-label{font-size:12px;color:var(--dim);}
.drop-sum-row .ds-val{font-size:16px;font-weight:700;}

footer{text-align:center;padding:28px;color:var(--dim);font-size:12px;border-top:1px solid var(--border);margin-top:16px;}
"""

_JS = """\
export default function(component) {
  const { parentElement } = component;
  if (parentElement._gachaInit) return;
  parentElement._gachaInit = true;

  const $ = (sel) => parentElement.querySelector(sel);
  const $$ = (sel) => parentElement.querySelectorAll(sel);

  // Load Chart.js dynamically
  function loadChartJS() {
    return new Promise((resolve) => {
      if (window.Chart) { resolve(window.Chart); return; }
      const s = document.createElement('script');
      s.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js';
      s.onload = () => resolve(window.Chart);
      document.head.appendChild(s);
    });
  }

  loadChartJS().then((ChartJS) => { init(ChartJS); });

  function init(ChartJS) {
    // Constants
    const CUM = [10,22,38,58,88,138,208,308,458];
    const LEVELS = ['Lv 2','Lv 3','Lv 4','Lv 5','Lv 6','Lv 7','Lv 8','Lv 9','Lv 10'];
    const JOK_TARGETS = [1,3,5,10,20,50];
    let DPP = 10;
    const DPE = 80;
    let packPrice = 1500;

    const ICONIC_NAMES = ['Iconic #1','Iconic #2','Iconic #3'];
    const COOL_NAMES = ['Cool #1','Cool #2','Cool #3','Cool #4','Cool #5','Cool #6','Cool #7','Cool #8','Cool #9'];
    const PRAG_NAMES = ['Pragmatic #1','Pragmatic #2','Pragmatic #3','Pragmatic #4','Pragmatic #5',
                        'Pragmatic #6','Pragmatic #7','Pragmatic #8','Pragmatic #9','Pragmatic #10',
                        'Pragmatic #11','Pragmatic #12','Pragmatic #13','Pragmatic #14','Pragmatic #15',
                        'Pragmatic #16','Pragmatic #17','Pragmatic #18'];

    // Math helpers
    const ePacks = (r,n) => { const p=DPP*(r/100); return p>0?n/p:Infinity; };
    const p90 = (r,n) => ePacks(r,n)*1.12;
    const fEur = (p) => isFinite(p)?'\\u20ac'+Math.round(p*packPrice/DPE).toLocaleString('en-US'):'\\u2014';
    const fPk = (p) => isFinite(p)?Math.round(p).toLocaleString('en-US'):'\\u2014';

    function buildUpgrade(id, rate) {
      const tb = $('#'+id);
      tb.innerHTML = '';
      CUM.forEach((n,i) => {
        const med=ePacks(rate,n), p9=p90(rate,n), isMax=(i===CUM.length-1);
        const tr=document.createElement('tr');
        if(isMax) tr.classList.add('hl');
        tr.innerHTML='<td>'+LEVELS[i]+(isMax?' \\ud83c\\udfc6':'')+'</td><td>'+n+'</td><td class="pk">'+fPk(med)+'</td>'+
          '<td class="'+(isMax?'euh':'eu')+'">'+fEur(med)+'</td><td class="eu">'+fEur(p9)+'</td>';
        tb.appendChild(tr);
      });
    }

    function buildJoker(rate) {
      const tb=$('#tb-joker');
      tb.innerHTML='';
      JOK_TARGETS.forEach(n => {
        const med=ePacks(rate,n), p9=p90(rate,n);
        const tr=document.createElement('tr');
        tr.innerHTML='<td>'+n+' Joker'+(n>1?'s':'')+'</td>'+
          '<td class="pk" style="color:var(--joker)">'+fPk(med)+'</td>'+
          '<td style="color:var(--joker);font-weight:700">'+fEur(med)+'</td>'+
          '<td style="color:var(--dim);font-size:12px">'+fEur(p9)+'</td>';
        tb.appendChild(tr);
      });
    }

    function buildPackPreview(rPrag, rCool, rIcon, rJok) {
      const sum = 18*rPrag + 9*rCool + 3*rIcon + rJok;
      const maxRate = Math.max(rPrag, rCool, rIcon, rJok);

      $('#pack-name').textContent = 'Hero Card Pack \\u2014 '+packPrice.toLocaleString('en-US')+' \\ud83d\\udc8e';

      const sumStr = sum.toFixed(2)+'%';
      const ok = Math.abs(sum-100)<0.5;
      $('#pack-sum-val').textContent = sumStr;
      $('#pack-sum-val').style.color = ok?'var(--green)':'var(--red)';
      $('#pack-sum-bot').textContent = sumStr;
      $('#pack-sum-bot').style.color = ok?'var(--green)':'var(--red)';

      const list = $('#drop-list');
      list.innerHTML = '';

      const section = (title) => {
        const d=document.createElement('div');
        d.className='drop-section-title';
        d.textContent=title;
        list.appendChild(d);
      };

      const row = (name, rate, cssClass, badgeText) => {
        const barW = Math.min(100, (rate/maxRate)*100);
        const d=document.createElement('div');
        d.className='drop-row '+cssClass;
        d.innerHTML=
          '<div class="dr-badge">'+badgeText+'</div>'+
          '<div class="dr-name">'+name+'</div>'+
          '<div class="dr-bar-wrap"><div class="dr-bar" style="width:'+barW+'%"></div></div>'+
          '<div class="dr-pct">'+rate.toFixed(2)+'%</div>';
        list.appendChild(d);
      };

      section('\\ud83c\\udccf Joker Hero \\u2014 Universal Consumable');
      row('Joker Hero', rJok, 'joker-row', '\\ud83c\\udccf Joker');

      section('\\u2b50 Iconic \\u2014 Premium Tier');
      ICONIC_NAMES.forEach(n => row(n, rIcon, 'iconic-row', '\\u2b50 Iconic'));

      section('\\ud83d\\udc99 Cool \\u2014 Mid Tier');
      COOL_NAMES.forEach(n => row(n, rCool, 'cool-row', '\\ud83d\\udc99 Cool'));

      section('\\u2b1c Pragmatic \\u2014 Base Tier');
      PRAG_NAMES.forEach(n => row(n, rPrag, 'pragmatic-row', '\\u2b1c Pragma'));
    }

    let chart;
    function buildChart(rPrag, rCool, rIcon) {
      const toEur=(r,n)=>{const p=ePacks(r,n);return isFinite(p)?Math.round(p*packPrice/DPE):null;};
      const ds=[
        {label:'Iconic',   color:'#ffc940', rate:rIcon},
        {label:'Cool',     color:'#4da6ff', rate:rCool},
        {label:'Pragmatic',color:'#aaaacc', rate:rPrag},
      ].map(d=>({label:d.label,data:CUM.map(n=>toEur(d.rate,n)),
        borderColor:d.color,backgroundColor:d.color+'18',fill:false,tension:.3,pointRadius:4,pointHoverRadius:6}));
      if(chart) chart.destroy();
      const canvas = $('#chart');
      chart = new ChartJS(canvas.getContext('2d'),{
        type:'line',data:{labels:LEVELS,datasets:ds},
        options:{responsive:true,maintainAspectRatio:false,
          plugins:{legend:{labels:{color:'#e8e8f0',font:{size:12}}},
            tooltip:{callbacks:{label:c=>c.dataset.label+' : '+(c.parsed.y!=null?'\\u20ac'+c.parsed.y.toLocaleString('en-US'):'\\u2014')}}},
          scales:{
            x:{ticks:{color:'#8888aa'},grid:{color:'#2e2e40'}},
            y:{ticks:{color:'#8888aa',callback:v=>'\\u20ac'+v.toLocaleString('en-US')},grid:{color:'#2e2e40'},
               title:{display:true,text:'Median Cumulative Cost (\\u20ac)',color:'#8888aa'}}}}});
    }

    function buildInsights(rPrag, rCool, rIcon, rJok) {
      const lv2i=ePacks(rIcon,10), lv5i=ePacks(rIcon,88), lv10i=ePacks(rIcon,458);
      const lv10c=ePacks(rCool,458);
      const ratio=isFinite(lv10i)&&lv10c>0?(lv10i/lv10c).toFixed(1):'\\u2014';
      const jokP1=Math.round(ePacks(rJok,1));

      const price1500note = packPrice===1500
        ? '<br>\\u26a0 At 1,500 \\ud83d\\udc8e (\\u20ac18.75/pack), aim for first Iconic upgrade (Lv2, 10 copies) under ~\\u20ac1,000.'
        : '';

      $('#insights').innerHTML=
        '<div class="insight" style="margin-bottom:14px;">'+
        '<strong>\\ud83d\\udcca Current Config \\u2014 Pack at '+packPrice.toLocaleString('en-US')+' \\ud83d\\udc8e (\\u20ac'+(packPrice/DPE).toFixed(2)+')</strong><br>'+
        '1st Iconic upgrade Lv2 (10 copies) \\u2192 median <strong>'+fEur(lv2i)+'</strong><br>'+
        'Iconic Lv5 (88 copies) \\u2192 median <strong>'+fEur(lv5i)+'</strong><br>'+
        'Max Iconic Lv10 (458 copies) \\u2192 median <strong>'+fEur(lv10i)+'</strong> &nbsp;|&nbsp; Max Cool Lv10 \\u2192 <strong>'+fEur(lv10c)+'</strong><br>'+
        'Iconic/Cool effort ratio: <strong>'+ratio+'\\u00d7</strong> '+(parseFloat(ratio)>=1.5?'\\u2705 clear differentiation':'\\u26a0 too close')+'<br>'+
        '\\ud83c\\udccf Joker: 1 every ~<strong>'+jokP1+' packs</strong> (median) = <strong>'+fEur(ePacks(rJok,1))+'/joker</strong>'+price1500note+
        '</div>';
    }

    function jwUpdate(rIcon, rJok) {
      const el=$('#jw');
      $('#warn-jok').textContent=rJok.toFixed(2);
      $('#warn-icon').textContent=rIcon.toFixed(2);
      el.classList.toggle('on', rJok>=rIcon);
    }

    function update() {
      DPP = +$('#r-dpp').value;
      $('#v-dpp').textContent = DPP;
      const pricePerDraw = (packPrice / DPP / DPE).toFixed(2);
      $('#dpp-cost-note').textContent = '\\u20ac'+(packPrice/DPE).toFixed(2)+'/pack \\u00b7 \\u20ac'+pricePerDraw+'/draw';
      $('#header-dpp').textContent = DPP;
      $('#pack-draws').textContent = DPP;

      const rPrag=+$('#r-prag').value;
      const rCool=+$('#r-cool').value;
      const rIcon=+$('#r-icon').value;
      const rJok =+$('#r-jok').value;
      const sum=18*rPrag+9*rCool+3*rIcon+rJok;

      $('#v-prag').textContent=rPrag.toFixed(1);
      $('#t-prag').textContent=(18*rPrag).toFixed(1);
      $('#v-cool').textContent=rCool.toFixed(1);
      $('#t-cool').textContent=(9*rCool).toFixed(1);
      $('#v-icon').textContent=rIcon.toFixed(1);
      $('#t-icon').textContent=(3*rIcon).toFixed(1);
      $('#v-jok').textContent =rJok.toFixed(2);

      const sumEl=$('#sum-total');
      const ok=Math.abs(sum-100)<0.5;
      sumEl.textContent=sum.toFixed(1)+'%';
      sumEl.className='tv '+(ok?'sum-ok':'sum-warn');

      $('#tier-prag').textContent=(18*rPrag).toFixed(1)+'%';
      $('#tier-cool').textContent=(9*rCool).toFixed(1)+'%';
      $('#tier-icon').textContent=(3*rIcon).toFixed(1)+'%';
      $('#tier-joker').textContent=rJok.toFixed(2)+'%';

      $$('.lbl-icon').forEach(e=>{ e.textContent=rIcon.toFixed(1); });
      $$('.lbl-cool').forEach(e=>{ e.textContent=rCool.toFixed(1); });
      $$('.lbl-prag').forEach(e=>{ e.textContent=rPrag.toFixed(1); });
      $$('.lbl-jok').forEach(e=>{ e.textContent=rJok.toFixed(2); });

      buildUpgrade('tb-iconic', rIcon);
      buildUpgrade('tb-cool',   rCool);
      buildUpgrade('tb-prag',   rPrag);
      buildJoker(rJok);
      buildChart(rPrag, rCool, rIcon);
      buildInsights(rPrag, rCool, rIcon, rJok);
      buildPackPreview(rPrag, rCool, rIcon, rJok);
      jwUpdate(rIcon, rJok);
    }

    // Events
    ['r-prag','r-cool','r-icon','r-jok','r-dpp'].forEach(id =>
      $('#'+id).addEventListener('input', update));

    $('#price-row').addEventListener('click', e => {
      const btn=e.target.closest('.price-btn');
      if(btn) {
        $$('.price-btn').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        packPrice=parseInt(btn.dataset.price);
        update();
      }
      const pre=e.target.closest('.preset-btn');
      if(pre) {
        if(pre.id==='preset-b') {
          setSliders(4.0, 2.5, 1.5, 1.0);
        } else if(pre.id==='preset-1500') {
          setSliders(3.5, 3.0, 2.5, 1.0);
          $$('.price-btn').forEach(b=>b.classList.remove('active'));
          parentElement.querySelector('[data-price="1500"]').classList.add('active');
          packPrice=1500;
        }
        update();
      }
    });

    function setSliders(p,c,i,j) {
      $('#r-prag').value=p;
      $('#r-cool').value=c;
      $('#r-icon').value=i;
      $('#r-jok').value=j;
    }

    // Init with preset 1500
    setSliders(3.5, 3.0, 2.5, 1.0);
    update();
  }
}
"""

_GACHA_COMPONENT = st.components.v2.component(
    "gacha_drop_rate_simulator",
    html=_HTML,
    css=_CSS,
    js=_JS,
)


def render_gacha_simulator() -> None:
    """Render the gacha drop rate simulator page."""
    st.title("🎴 Gacha Drop Rate Simulator")
    st.caption(
        "Cup Heroes — Interactive card pack economics and drop rate analysis tool. "
        "Adjust sliders to explore how drop rates affect progression costs."
    )
    _GACHA_COMPONENT(height=5200)
