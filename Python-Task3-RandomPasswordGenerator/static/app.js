const $ = (id) => document.getElementById(id);

const criteria = { mode: "password", length: 16, words: 4,
    upper: true, lower: true, digits: true, symbols: true,
    exclude_ambiguous: false };

let debounceTimer = null;

async function api(path, payload) {
    const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    return res.json();
}

/* ---------- Generator: instant updates via debounced fetch ---------- */
async function refreshPassword() {
    const data = await api("/api/generate", criteria);
    if (data.error) { $("password-output").value = data.error; return; }
    $("password-output").value = data.password;
    renderStrength(data);
    $("breach-result").classList.add("hidden");
}

function renderStrength(data) {
    const bits = data.entropy_bits;
    $("entropy-bits").textContent = `${bits} bits of entropy`;
    $("crack-online").textContent = `Online (throttled): ${data.crack.online_throttled}`;
    $("crack-offline").textContent = `Offline (GPU leak): ${data.crack.offline_fast_hash}`;
    const pct = Math.min(100, (bits / 128) * 100);
    const fill = $("meter-fill");
    fill.style.width = `${pct}%`;
    fill.style.background =
        bits < 40 ? "var(--bad)" :       // trivially crackable
        bits < 70 ? "var(--warn)" :      // weak
        bits < 100 ? "var(--accent)" :   // strong
                     "var(--good)";      // excellent
}

function scheduleRefresh() {           // 150ms debounce so slider drags don't spam
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(refreshPassword, 150);
}

$("length").addEventListener("input", (e) => {
    criteria.length = +e.target.value;
    $("length-value").textContent = criteria.length;
    scheduleRefresh();
});
$("words").addEventListener("input", (e) => {
    criteria.words = +e.target.value;
    $("words-value").textContent = criteria.words;
    scheduleRefresh();
});
for (const id of ["upper", "lower", "digits", "symbols", "exclude_ambiguous"]) {
    $(id).addEventListener("change", (e) => { criteria[id] = e.target.checked; refreshPassword(); });
}

function setMode(mode) {
    criteria.mode = mode;
    $("mode-password").classList.toggle("active", mode === "password");
    $("mode-passphrase").classList.toggle("active", mode === "passphrase");
    $("criteria-password").classList.toggle("hidden", mode !== "password");
    $("criteria-passphrase").classList.toggle("hidden", mode !== "passphrase");
    refreshPassword();
}
$("mode-password").addEventListener("click", () => setMode("password"));
$("mode-passphrase").addEventListener("click", () => setMode("passphrase"));
$("regen-btn").addEventListener("click", refreshPassword);

/* ---------- One-click copy with legacy fallback ---------- */
$("copy-btn").addEventListener("click", async () => {
    const text = $("password-output").value;
    if (!text) return;
    try {
        await navigator.clipboard.writeText(text);
    } catch {
        const tmp = document.createElement("textarea");
        tmp.value = text; document.body.appendChild(tmp);
        tmp.select(); document.execCommand("copy"); tmp.remove();
    }
    $("copy-btn").textContent = "✓ Copied";
    setTimeout(() => ($("copy-btn").textContent = "⧉ Copy"), 1200);
});

/* ---------- HIBP breach check ---------- */
$("breach-btn").addEventListener("click", async () => {
    const password = $("password-output").value;
    if (!password) return;
    $("breach-btn").textContent = "Checking…";
    const data = await api("/api/breach", { password });
    const el = $("breach-result");
    el.classList.remove("hidden", "pwned", "clean");
    if (data.error) el.textContent = data.error;
    else if (data.pwned) {
        el.textContent = `⚠ FOUND in ${data.count.toLocaleString()} breaches — do not use this password.`;
        el.classList.add("pwned");
    } else {
        el.textContent = "✓ Not found in any known breach (k-anonymity check).";
        el.classList.add("clean");
    }
    $("breach-btn").textContent = "Check breach status (HIBP k-anonymity)";
});

/* ---------- Vault ---------- */
async function refreshVaultStatus() {
    const data = await (await fetch("/api/status")).json();
    const badge = $("vault-state");
    $("setup-btn").classList.toggle("hidden", data.has_master);
    $("unlock-btn").classList.toggle("hidden", !data.has_master);
    badge.textContent = data.unlocked ? "unlocked" : "locked";
    badge.classList.toggle("unlocked", data.unlocked);
    $("vault-panel").classList.toggle("hidden", !data.unlocked);
    if (data.unlocked) renderVaultList();
}

async function doAuth(path) {
    const data = await api(path, { master: $("master").value });
    $("vault-msg").textContent = data.error || "";
    $("master").value = "";
    refreshVaultStatus();
}
$("unlock-btn").addEventListener("click", () => doAuth("/api/unlock"));
$("setup-btn").addEventListener("click", () => doAuth("/api/setup"));
$("lock-btn").addEventListener("click", async () => {
    await fetch("/api/lock", { method: "POST" });
    refreshVaultStatus();
});

$("v-save").addEventListener("click", async () => {
    const data = await api("/api/vault/save", {
        service: $("v-service").value,
        username: $("v-username").value,
        password: $("v-password").value,
    });
    if (data.error) { $("vault-msg").textContent = data.error; return; }
    $("v-service").value = $("v-username").value = $("v-password").value = "";
    renderVaultList();
});

async function renderVaultList() {
    const data = await (await fetch("/api/vault/list")).json();
    const ul = $("vault-list");
    ul.innerHTML = "";
    for (const e of data.entries || []) {
        const li = document.createElement("li");
        const left = document.createElement("div");
        left.innerHTML = `<div class="svc"></div><div class="usr"></div>`;
        left.querySelector(".svc").textContent = e.service;
        left.querySelector(".usr").textContent = e.username;
        const revealBtn = document.createElement("button");
        revealBtn.className = "btn";
        revealBtn.textContent = "Reveal";
        revealBtn.addEventListener("click", async () => {
            const d = await api("/api/vault/reveal", { id: e.id });
            if (d.error) return alert(d.error);
            const span = document.createElement("span");
            span.className = "secret";
            span.textContent = d.password;
            revealBtn.replaceWith(span);
        });
        li.append(left, revealBtn);
        ul.appendChild(li);
    }
}

refreshPassword();
refreshVaultStatus();
