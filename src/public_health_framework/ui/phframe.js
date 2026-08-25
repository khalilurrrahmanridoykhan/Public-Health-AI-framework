const PHFrame = {
  pendingGets: new Map(),
  messages: {
    en: { dashboard: "Dashboard", records: "Records", quality: "Data quality", theme: "Theme", saved: "Record saved." },
    bn: { dashboard: "ড্যাশবোর্ড", records: "রেকর্ড", quality: "ডেটার গুণমান", theme: "থিম", saved: "রেকর্ড সংরক্ষিত হয়েছে।" }
  },
  async get(path) {
    if (this.pendingGets.has(path)) return this.pendingGets.get(path);
    const request = fetch(path, { headers: { accept: "application/json" } }).then(async response => {
      if (!response.ok) throw new Error((await response.json()).error?.message || `Request failed (${response.status})`);
      return response.json();
    }).finally(() => this.pendingGets.delete(path));
    this.pendingGets.set(path, request);
    return request;
  },
  async send(path, method, body) {
    const response = await fetch(path, {
      method, headers: { accept: "application/json", "content-type": "application/json" },
      body: JSON.stringify(body)
    });
    if (!response.ok) { const payload = await response.json(); throw new Error(payload.error?.message || payload.data?.errors?.[0]?.message || `Request failed (${response.status})`); }
    return response.status === 204 ? null : response.json();
  },
  escape(value) {
    const span = document.createElement("span");
    span.textContent = value == null ? "" : String(value);
    return span.innerHTML;
  },
  loading(message = "Loading…", compact = false) {
    return `<div class="ph-loader ${compact ? "ph-loader-compact" : ""}" role="status" aria-live="polite"><span class="ph-spinner" aria-hidden="true"></span><span>${this.escape(message)}</span></div>`;
  },
  markdown(value) {
    return this.escape(value).replace(/^### (.+)$/gm, "<h4>$1</h4>").replace(/^## (.+)$/gm, "<h3>$1</h3>").replace(/^# (.+)$/gm, "<h2>$1</h2>").replace(/^[-] (.+)$/gm, "<li>$1</li>").replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\n\n/g, "</p><p>").replace(/\n/g, "<br>");
  },
  applyColor(value) {
    const hex = /^#[0-9a-f]{6}$/i.test(value || "") ? value : "#087e8b";
    const channels = [1, 3, 5].map(index => parseInt(hex.slice(index, index + 2), 16));
    const mix = (target, amount) => `#${channels.map(channel => Math.round(channel + (target - channel) * amount).toString(16).padStart(2, "0")).join("")}`;
    const dark = document.documentElement.dataset.theme === "dark";
    document.documentElement.style.setProperty("--ph-color-primary", dark ? mix(255, .38) : hex);
    document.documentElement.style.setProperty("--ph-color-primary-strong", dark ? hex : mix(0, .25));
    document.documentElement.style.setProperty("--ph-color-accent", dark ? mix(255, .38) : hex);
    document.documentElement.style.setProperty("--ph-color-accent-soft", `color-mix(in srgb, ${hex} 18%, transparent)`);
  },
  t(key) { return this.customMessages?.[key] || this.messages[this.locale]?.[key] || this.messages.en[key] || key; },
  basemaps: {
    "openstreetmap": { label: "OpenStreetMap", url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", attribution: "© OpenStreetMap contributors" },
    "carto-light": { label: "CARTO Light", url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", attribution: "© OpenStreetMap contributors © CARTO" },
    "carto-dark": { label: "CARTO Dark", url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", attribution: "© OpenStreetMap contributors © CARTO" },
    "esri-imagery": { label: "Esri World Imagery", url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attribution: "Tiles © Esri" }
  },
  async leaflet() {
    if (window.L) return window.L;
    if (!this._leafletPromise) this._leafletPromise = new Promise((resolve, reject) => {
      const style = document.createElement("link"); style.rel = "stylesheet"; style.href = "/assets/leaflet.css"; document.head.append(style);
      const script = document.createElement("script"); script.src = "/assets/leaflet.js"; script.onload = () => resolve(window.L); script.onerror = () => reject(new Error("Interactive map library could not load.")); document.head.append(script);
    });
    return this._leafletPromise;
  },
  notify(message) { dispatchEvent(new CustomEvent("ph-notify", { detail: { message } })); }
};

class PHElement extends HTMLElement {
  connectedCallback() { this.render(); }
  render() {}
}

class PHAppShell extends PHElement {
  async render() {
    this.innerHTML = `<main class="ph-boot-screen">${PHFrame.loading("Preparing your PHFrame workspace")}</main>`;
    try {
      const [metadata, settings] = await Promise.all([PHFrame.get("/api"), PHFrame.get("/api/settings")]);
      this.metadata = metadata;
      PHFrame.appMetadata = metadata;
      PHFrame.siteSettings = settings.data;
      PHFrame.locale = this.metadata.ui?.locale || "en";
      PHFrame.customMessages = this.metadata.ui?.translations || {};
      document.documentElement.lang = PHFrame.locale;
      document.documentElement.dataset.theme = localStorage.getItem("ph-theme") || PHFrame.siteSettings.default_theme || this.metadata.ui?.theme || "light";
      PHFrame.applyColor(PHFrame.siteSettings.primary_color);
      const favicon = document.querySelector("[data-ph-favicon]"); if (favicon) favicon.href = PHFrame.siteSettings.favicon_url;
      this.draw();
      addEventListener("hashchange", () => this.route());
    } catch (error) {
      this.innerHTML = `<main class="ph-boot-screen"><div class="ph-load-error" role="alert"><h2>PHFrame could not load</h2><p>${PHFrame.escape(error.message)}</p><button class="ph-button" type="button">Try again</button></div></main>`;
      this.querySelector("button").addEventListener("click", () => this.render());
    }
  }
  draw() {
    const navigation = PHFrame.siteSettings.navigation;
    const builtInLinks = Object.entries(navigation).filter(([, item]) => item.visible).map(([route, item]) => `<a href="#/${route}" data-route="${route}">${PHFrame.escape(item.label)}</a>`).join("");
    const customLinks = (PHFrame.siteSettings.pages || []).map(page => page.type === "external" ? `<a href="${PHFrame.escape(page.url)}">${PHFrame.escape(page.nav_label)}</a>` : `<a href="#/page/${PHFrame.escape(page.slug)}" data-page="${PHFrame.escape(page.slug)}">${PHFrame.escape(page.nav_label)}</a>`).join("");
    const links = builtInLinks + customLinks;
    this.innerHTML = `<a class="ph-skip-link" href="#main">Skip to content</a>
      <div class="ph-shell"><header class="ph-header"><a class="ph-brand" href="#/dashboard"><img src="${PHFrame.escape(PHFrame.siteSettings.logo_url)}" alt=""><span><b>${PHFrame.escape(PHFrame.siteSettings.brand_name)}</b><small>${PHFrame.escape(PHFrame.siteSettings.header_title)}</small></span></a>
      <nav class="ph-nav" aria-label="Primary">${links}</nav>
      <div class="ph-header-tools"><div class="ph-theme-switcher" role="group" aria-label="Color theme"><button type="button" data-theme-choice="light" aria-label="Use light theme">☀</button><button type="button" data-theme-choice="dark" aria-label="Use dark theme">☾</button><button type="button" data-theme-choice="high-contrast" aria-label="Use high contrast theme">◐</button></div>${PHFrame.siteSettings.access_mode === "private" ? `<button class="ph-logout" type="button">Sign out</button>` : ""}</div></header>
      <main class="ph-main" id="main" tabindex="-1"><div id="ph-view"></div></main>${PHFrame.siteSettings.show_footer ? `<footer class="ph-footer">${PHFrame.siteSettings.footer_html}</footer>` : ""}<ph-ai-assistant></ph-ai-assistant><ph-notification-center></ph-notification-center></div>`;
    const applyTheme = value => { document.documentElement.classList.add("ph-theme-changing"); document.documentElement.dataset.theme = value; localStorage.setItem("ph-theme", value); PHFrame.applyColor(PHFrame.siteSettings.primary_color); this.querySelectorAll("[data-theme-choice]").forEach(button => { const active = button.dataset.themeChoice === value; button.classList.toggle("ph-theme-choice-active", active); button.setAttribute("aria-pressed", String(active)); }); clearTimeout(this._themeTimer); this._themeTimer = setTimeout(() => document.documentElement.classList.remove("ph-theme-changing"), 280); };
    this.querySelectorAll("[data-theme-choice]").forEach(button => button.addEventListener("click", event => {
      applyTheme(button.dataset.themeChoice);
      if (event.detail > 0) button.blur();
    }));
    applyTheme(document.documentElement.dataset.theme);
    this.querySelector(".ph-logout")?.addEventListener("click", async () => { await PHFrame.send("/api/auth/logout", "POST", {}); location.href = "/login"; });
    this.querySelector("ph-ai-assistant").metadata = this.metadata;
    this.route();
  }
  route() {
    const route = (location.hash.match(/^#\/([^/?]+)/) || [])[1] || "dashboard";
    this.querySelectorAll("[data-route]").forEach(link => link.toggleAttribute("aria-current", link.dataset.route === route));
    const activeSlug = route === "page" ? decodeURIComponent(location.hash.split("/")[2] || "") : "";
    this.querySelectorAll("[data-page]").forEach(link => link.toggleAttribute("aria-current", link.dataset.page === activeSlug));
    const view = this.querySelector("#ph-view");
    if (route === "records") {
      const first = Object.keys(this.metadata.datasets)[0];
      const datasetOptions = Object.entries(this.metadata.datasets).map(([name, item]) => `<option value="${PHFrame.escape(name)}">${PHFrame.escape(item.label)}</option>`).join("");
      view.innerHTML = `<div class="ph-page-heading"><div><p class="ph-eyebrow">Data workspace</p><h2>Records</h2><p>Browse, search, and add records without losing your place.</p></div><div class="ph-field ph-page-dataset"><label for="ph-records-dataset">Dataset</label><select id="ph-records-dataset">${datasetOptions}</select></div></div><ph-filter-bar></ph-filter-bar><div class="ph-records-workspace"><aside class="ph-workspace-sidebar"><div><p class="ph-eyebrow">Workspace</p><h3>Manage data</h3></div><nav aria-label="Record actions"><button type="button" class="ph-workspace-tab-active" data-records-tab="browse"><span>▦</span><b>Browse records</b><small>Search and review data</small></button><button type="button" data-records-tab="add"><span>＋</span><b>Add record</b><small>Enter a new row</small></button></nav></aside><div class="ph-records-content"><div data-records-panel="browse"><ph-case-table dataset="${PHFrame.escape(first)}"></ph-case-table></div><div data-records-panel="add" hidden><ph-data-form dataset="${PHFrame.escape(first)}"></ph-data-form></div></div></div>`;
      const setDataset = name => { const form = view.querySelector("ph-data-form"), table = view.querySelector("ph-case-table"); form.setAttribute("dataset", name); table.setAttribute("dataset", name); form.metadata = this.metadata.datasets[name]; table.metadata = this.metadata.datasets[name]; };
      setDataset(first);
      view.querySelector("ph-filter-bar").metadata = this.metadata;
      view.querySelector("#ph-records-dataset").addEventListener("change", event => setDataset(event.target.value));
      view.querySelectorAll("[data-records-tab]").forEach(button => button.addEventListener("click", () => { view.querySelectorAll("[data-records-tab]").forEach(item => item.classList.toggle("ph-workspace-tab-active", item === button)); view.querySelectorAll("[data-records-panel]").forEach(panel => panel.hidden = panel.dataset.recordsPanel !== button.dataset.recordsTab); }));
      view.addEventListener("ph-filter", event => {
        const query = event.detail.filter ? `?filter=${encodeURIComponent(event.detail.filter)}` : "";
        view.querySelector("ph-case-table").load(query);
      });
    } else if (route === "builder") {
      view.innerHTML = `<div class="ph-page-heading"><div><p class="ph-eyebrow">Structure your data</p><h2>Data builder</h2><p>Create reliable schemas that work across countries, programmes, and use cases.</p></div></div><ph-data-builder></ph-data-builder>`;
      view.querySelector("ph-data-builder").metadata = this.metadata;
    } else if (route === "import") {
      view.innerHTML = `<div class="ph-page-heading"><div><p class="ph-eyebrow">Bring data into PHFrame</p><h2>Import data</h2><p>Preview, map, and validate every record before it reaches your dataset.</p></div></div><ph-import-wizard></ph-import-wizard>`;
      view.querySelector("ph-import-wizard").metadata = this.metadata;
    } else if (route === "connectors") {
      view.innerHTML = `<h2>Connectors</h2><ph-connector-console></ph-connector-console>`;
    } else if (route === "quality") {
      view.innerHTML = `<h2>Data quality</h2><ph-quality-panel></ph-quality-panel>`;
    } else if (route === "settings") {
      view.innerHTML = `<h2>Settings</h2><ph-settings-panel></ph-settings-panel>`;
      view.querySelector("ph-settings-panel").settings = PHFrame.siteSettings;
    } else if (route === "pages") {
      view.innerHTML = `<h2>Pages</h2><ph-page-builder></ph-page-builder>`;
      view.querySelector("ph-page-builder").settings = PHFrame.siteSettings;
      view.querySelector("ph-page-builder").metadata = this.metadata;
    } else if (route === "ai") {
      view.innerHTML = `<h2>AI assistance</h2><ph-ai-workspace></ph-ai-workspace>`;
      view.querySelector("ph-ai-workspace").metadata = this.metadata;
    } else if (route === "page") {
      const slug = decodeURIComponent(location.hash.split("/")[2] || "");
      view.innerHTML = `<ph-custom-page slug="${PHFrame.escape(slug)}"></ph-custom-page>`;
      view.querySelector("ph-custom-page").settings = PHFrame.siteSettings;
    } else {
      view.innerHTML = `<ph-dashboard-manager></ph-dashboard-manager>`;
      view.querySelector("ph-dashboard-manager").metadata = this.metadata;
    }
    this.dispatchEvent(new CustomEvent("ph-route", { detail: { route, view, metadata: this.metadata } }));
  }
}

class PHDataForm extends PHElement {
  set metadata(value) { this._metadata = value; if (this.isConnected) this.render(); }
  render() {
    if (!this._metadata) return;
    const organisationField = Object.entries(this._metadata.fields).find(([, schema]) => schema.type === "organisation_unit");
    const fields = Object.entries(this._metadata.fields).filter(([, schema]) => schema.type !== "organisation_unit").map(([name, schema]) => {
      const type = ["integer", "number", "age"].includes(schema.type) ? "number" : (["date", "datetime"].includes(schema.type) ? schema.type.replace("time", "time-local") : "text");
      return `<div class="ph-field"><label for="ph-${name}">${PHFrame.escape(schema.label || name.replaceAll("_", " "))}${schema.required ? " *" : ""}</label><input id="ph-${name}" name="${name}" type="${type}" ${schema.required ? "required" : ""}></div>`;
    }).join("");
    const organisationSelect = organisationField ? `<ph-org-unit-select field="${organisationField[0]}"></ph-org-unit-select>` : "";
    this.innerHTML = `<section class="ph-card" aria-labelledby="ph-form-title"><h3 id="ph-form-title">Add ${PHFrame.escape(this._metadata.label)}</h3><form class="ph-stack">${fields}${organisationSelect}<button class="ph-button" type="submit">Save record</button><p class="ph-status" role="status"></p></form></section>`;
    this.querySelector("form").addEventListener("submit", event => this.submit(event));
  }
  async submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const status = form.querySelector("[role=status]");
    const payload = Object.fromEntries([...new FormData(form)].filter(([, value]) => value !== ""));
    try {
      await PHFrame.send(`/api/${this.dataset}`, "POST", payload);
      status.textContent = PHFrame.t("saved");
      PHFrame.notify(PHFrame.t("saved"));
      form.reset();
      dispatchEvent(new CustomEvent("ph-record-saved", { detail: { dataset: this.dataset } }));
    } catch (error) { status.textContent = error.message; status.className = "ph-status ph-error"; }
  }
  get dataset() { return this.getAttribute("dataset"); }
}

class PHCaseTable extends PHElement {
  set metadata(value) { this._metadata = value; if (this.isConnected) this.render(); }
  connectedCallback() { addEventListener("ph-record-saved", event => { if (event.detail.dataset === this.dataset) this.load(); }); this.render(); }
  render() { if (this._metadata) this.load(); }
  async load(query = "") {
    this.innerHTML = `<section class="ph-card ph-records-table-card"><div class="ph-loader ph-loader-compact"><div class="ph-spinner"></div><span>Loading records…</span></div></section>`;
    try {
      const response = await PHFrame.get(`/api/${this.dataset}${query}`);
      this.records = response.data; this.columns = Object.keys(this._metadata.fields).filter(name => !this._metadata.fields[name].protected); this.page = 1; this.pageSize = 25; this.drawTable();
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
  drawTable() {
    const search = (this.search || "").toLowerCase(), filtered = this.records.filter(record => !search || this.columns.some(name => String(record[name] ?? "").toLowerCase().includes(search)));
    const pages = Math.max(1, Math.ceil(filtered.length / this.pageSize)); this.page = Math.min(this.page, pages);
    const start = (this.page - 1) * this.pageSize, visible = filtered.slice(start, start + this.pageSize);
    const head = this.columns.map(name => `<th scope="col">${PHFrame.escape(this._metadata.fields[name].label || name)}</th>`).join("");
    const rows = visible.map(record => `<tr>${this.columns.map(name => `<td title="${PHFrame.escape(record[name] ?? "")}">${PHFrame.escape(record[name] ?? "—")}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${this.columns.length}"><div class="ph-table-empty">No matching records found.</div></td></tr>`;
    this.innerHTML = `<section class="ph-card ph-records-table-card"><header class="ph-records-table-header"><div><p class="ph-eyebrow">Dataset records</p><h3>${PHFrame.escape(this._metadata.label)}</h3><p>${filtered.length} ${filtered.length === 1 ? "record" : "records"}</p></div><label class="ph-table-search"><span class="ph-sr-only">Search records</span><input type="search" value="${PHFrame.escape(this.search || "")}" placeholder="Search all columns…"></label></header><div class="ph-table-wrap ph-records-scroll"><table class="ph-table ph-records-table"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div><footer class="ph-table-pagination"><p>Showing ${filtered.length ? start + 1 : 0}–${Math.min(start + this.pageSize, filtered.length)} of ${filtered.length}</p><div><button type="button" data-page="prev" ${this.page === 1 ? "disabled" : ""}>← Previous</button><span>Page ${this.page} of ${pages}</span><button type="button" data-page="next" ${this.page === pages ? "disabled" : ""}>Next →</button></div></footer></section>`;
    this.querySelector("input[type=search]").addEventListener("input", event => { this.search = event.target.value; this.page = 1; this.drawTable(); this.querySelector("input[type=search]").focus(); });
    this.querySelectorAll("[data-page]").forEach(button => button.addEventListener("click", () => { this.page += button.dataset.page === "next" ? 1 : -1; this.drawTable(); }));
  }
  get dataset() { return this.getAttribute("dataset"); }
}

class PHFilterBar extends PHElement {
  set metadata(value) { this._metadata = value; if (this.isConnected) this.render(); }
  render() {
    if (!this._metadata) return;
    const options = Object.entries(this._metadata.filters || {}).map(([name, item]) => `<option value="${name}">${PHFrame.escape(item.label)}</option>`).join("");
    this.innerHTML = `<section class="ph-card ph-actions" aria-label="Record filters"><div class="ph-field"><label for="ph-saved-filter">Saved filter</label><select id="ph-saved-filter"><option value="">All records</option>${options}</select></div><button class="ph-button" type="button">Apply</button></section>`;
    this.querySelector("button").addEventListener("click", () => this.dispatchEvent(new CustomEvent("ph-filter", { bubbles: true, detail: { filter: this.querySelector("select").value } })));
  }
}

class PHOrgUnitSelect extends PHElement {
  async render() {
    try {
      const response = await PHFrame.get("/api/organisation-units");
      const options = response.data.map(unit => `<option value="${unit.code}">${PHFrame.escape(unit.name)} (${PHFrame.escape(unit.level)})</option>`).join("");
      const field = this.getAttribute("field") || "reporting_unit";
      this.innerHTML = `<div class="ph-field"><label for="ph-${field}">Reporting unit</label><select id="ph-${field}" name="${field}"><option value="">Select a unit</option>${options}</select></div>`;
    } catch (_) { this.innerHTML = ""; }
  }
}

class PHQualityPanel extends PHElement {
  async render() {
    try {
      const response = await PHFrame.get("/api/data-quality");
      this.innerHTML = `<div class="ph-grid">${response.data.map(rule => `<article class="ph-card"><h3>${PHFrame.escape(rule.label)}</h3><p><strong>${rule.score == null ? "—" : rule.score.toFixed(1) + "%"}</strong> valid</p><p class="ph-muted">${rule.violations} violations across ${rule.total} records</p></article>`).join("")}</div>`;
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
}

class PHKPI extends PHElement {
  async render() {
    this.innerHTML = PHFrame.loading("Loading metric", true);
    try {
      const endpoint = this.getAttribute("field") ? `/api/visualize/${this.getAttribute("dataset")}?field=${encodeURIComponent(this.getAttribute("field"))}&operation=${this.getAttribute("operation") || "sum"}` : `/api/indicators/${this.getAttribute("indicator")}`;
      const response = await PHFrame.get(endpoint);
      const value = response.data.value;
      const formatted = value == null ? "—" : new Intl.NumberFormat().format(value);
      const visualization = this.getAttribute("visualization") || "number";
      if (visualization === "gauge") {
        const percentage = value == null ? 0 : Math.min(100, Math.max(0, Number(value)));
        this.innerHTML = `<div class="ph-widget-body ph-kpi-gauge"><div class="ph-gauge" style="--ph-gauge-value:${percentage}" role="img" aria-label="${PHFrame.escape(formatted)}"><span>${formatted}</span></div><p class="ph-widget-meta">${PHFrame.escape(response.data.operation)}</p></div>`;
      } else {
        this.innerHTML = `<div class="ph-widget-body ph-kpi"><p class="ph-kpi-value">${formatted}</p><p class="ph-widget-meta"><span class="ph-status-dot"></span>${PHFrame.escape(response.data.operation)}</p></div>`;
      }
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
}

class PHIndicatorChart extends PHElement {
  async render() {
    this.innerHTML = PHFrame.loading("Loading chart", true);
    try {
      const endpoint = this.getAttribute("field") ? `/api/visualize/${this.getAttribute("dataset")}?field=${encodeURIComponent(this.getAttribute("field"))}` : `/api/dimensions/${this.getAttribute("dimension")}`;
      const response = await PHFrame.get(endpoint);
      const values = response.data.values;
      const visualization = this.getAttribute("visualization") || "bar";
      if (!values.length) { this.innerHTML = this.empty("No dimension data yet"); return; }
      const maximum = Math.max(1, ...values.map(item => item.count));
      if (visualization === "donut") {
        const total = values.reduce((sum, item) => sum + item.count, 0);
        let offset = 0;
        const colors = ["#13b8a6", "#5b8def", "#f59e0b", "#e76f92", "#8b7cf6", "#4fb477"];
        const segments = values.map((item, index) => { const length = total ? item.count / total * 100 : 0; const segment = `<circle cx="60" cy="60" r="45" pathLength="100" fill="none" stroke="${colors[index % colors.length]}" stroke-width="18" stroke-dasharray="${length} ${100 - length}" stroke-dashoffset="${-offset}"><title>${PHFrame.escape(item.value)}: ${item.count}</title></circle>`; offset += length; return segment; }).join("");
        const legend = values.map((item, index) => `<li><span style="--ph-legend-color:${colors[index % colors.length]}"></span><b>${PHFrame.escape(item.value ?? "Unknown")}</b><small>${item.count}</small></li>`).join("");
        this.innerHTML = `<div class="ph-widget-body ph-donut-layout"><svg class="ph-donut" viewBox="0 0 120 120" role="img" aria-label="${PHFrame.escape(response.data.label)} donut chart">${segments}<text x="60" y="57" text-anchor="middle" class="ph-donut-total">${total}</text><text x="60" y="72" text-anchor="middle" class="ph-donut-caption">total</text></svg><ul class="ph-chart-legend">${legend}</ul></div>${this.table(values, "Value", "Count", visualization === "table")}`;
      } else if (visualization === "table") {
        this.innerHTML = this.table(values, "Value", "Count", true);
      } else {
        const width = 600, row = 44;
        const bars = values.map((item, index) => `<g transform="translate(0 ${index * row})"><text class="ph-axis-label" x="0" y="25">${PHFrame.escape(item.value ?? "Unknown")}</text><rect class="ph-chart-track" x="155" y="7" width="390" height="25" rx="7"></rect><rect class="ph-chart-bar" x="155" y="7" width="${Math.round(item.count / maximum * 390)}" height="25" rx="7"><title>${item.count}</title></rect><text class="ph-axis-value" x="580" y="25" text-anchor="end">${item.count}</text></g>`).join("");
        this.innerHTML = `<div class="ph-widget-body"><svg class="ph-chart" viewBox="0 0 ${width} ${Math.max(row, values.length * row)}" role="img" aria-label="${PHFrame.escape(response.data.label)} bar chart">${bars}</svg></div>${this.table(values, "Value", "Count")}`;
      }
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
  empty(message) { return `<div class="ph-empty-state"><span>↗</span><p>${message}</p></div>`; }
  table(values, first, second, visible = false) {
    return `<div class="${visible ? "ph-table-wrap ph-chart-table" : "ph-sr-only"}"><table class="ph-table"><caption>${PHFrame.escape(this.getAttribute("title") || "Chart data")}</caption><thead><tr><th>${first}</th><th>${second}</th></tr></thead><tbody>${values.map(item => `<tr><td>${PHFrame.escape(item.value)}</td><td>${item.count}</td></tr>`).join("")}</tbody></table></div>`;
  }
}

class PHEpiCurve extends PHElement {
  async render() {
    this.innerHTML = PHFrame.loading("Loading trend", true);
    const query = new URLSearchParams({ date_field: this.getAttribute("date-field") });
    if (this.getAttribute("value-field")) query.set("value_field", this.getAttribute("value-field"));
    try {
      const response = await PHFrame.get(`/api/epi-curve/${this.getAttribute("dataset")}?${query}`);
      const values = response.data;
      const visualization = this.getAttribute("visualization") || "line";
      if (!values.length) { this.innerHTML = `<div class="ph-empty-state"><span>⌁</span><p>No time-series data yet</p></div>`; return; }
      const maximum = Math.max(1, ...values.map(item => item.value));
      const table = `<div class="${visualization === "table" ? "ph-table-wrap ph-chart-table" : "ph-sr-only"}"><table class="ph-table"><caption>Epidemiological curve data</caption><thead><tr><th>Date</th><th>Value</th></tr></thead><tbody>${values.map(item => `<tr><td>${PHFrame.escape(item.date)}</td><td>${item.value}</td></tr>`).join("")}</tbody></table></div>`;
      if (visualization === "table") { this.innerHTML = table; return; }
      const positions = values.map((item, index) => ({ x: values.length === 1 ? 300 : index / (values.length - 1) * 530 + 45, y: 190 - item.value / maximum * 145 }));
      const grid = [45, 93, 142, 190].map(y => `<line class="ph-chart-grid" x1="45" y1="${y}" x2="575" y2="${y}"></line>`).join("");
      const marks = visualization === "column" ? positions.map((point, index) => `<rect class="ph-chart-bar" x="${point.x - 13}" y="${point.y}" width="26" height="${190 - point.y}" rx="5"><title>${PHFrame.escape(values[index].date)}: ${values[index].value}</title></rect>`).join("") : `<polyline class="ph-chart-line" points="${positions.map(point => `${point.x},${point.y}`).join(" ")}"></polyline>${positions.map((point, index) => `<circle class="ph-chart-point" cx="${point.x}" cy="${point.y}" r="5"><title>${PHFrame.escape(values[index].date)}: ${values[index].value}</title></circle>`).join("")}`;
      const labels = positions.filter((_, index) => index === 0 || index === positions.length - 1).map((point, index) => `<text class="ph-axis-label" x="${point.x}" y="214" text-anchor="${index ? "end" : "start"}">${PHFrame.escape(values[index ? values.length - 1 : 0].date)}</text>`).join("");
      this.innerHTML = `<div class="ph-widget-body"><svg class="ph-chart" viewBox="0 0 600 225" role="img" aria-label="Cases by reporting date">${grid}${marks}${labels}</svg></div>${table}`;
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
}

class PHMap extends PHElement {
  async render() {
    this.innerHTML = PHFrame.loading("Loading map", true);
    try {
      const response = await PHFrame.get(`/api/dimensions/${this.getAttribute("dimension")}`);
      const values = response.data.values;
      const visualization = this.getAttribute("visualization") || "tiles";
      if (visualization === "bar" || visualization === "donut" || visualization === "table") {
        this.innerHTML = `<ph-indicator-chart dimension="${PHFrame.escape(this.getAttribute("dimension"))}" title="${PHFrame.escape(this.getAttribute("title"))}" visualization="${visualization}"></ph-indicator-chart>`;
        return;
      }
      const layers = await PHFrame.get("/api/boundaries");
      if (layers.data.length) {
        const boundary = await PHFrame.get(`/api/boundaries/${encodeURIComponent(layers.data.at(-1).id)}`);
        await this.renderBoundary(boundary.data, values);
        return;
      }
      if (!values.length) { this.innerHTML = `<div class="ph-empty-state"><span>⌖</span><p>No geographic data yet</p></div>`; return; }
      const maximum = Math.max(1, ...values.map(item => item.count));
      const columns = Math.max(1, Math.ceil(Math.sqrt(values.length)));
      const tiles = values.map((item, index) => {
        const x = (index % columns) * 150, y = Math.floor(index / columns) * 105;
        const opacity = .2 + item.count / maximum * .8;
        return `<g transform="translate(${x} ${y})"><rect class="ph-map-tile" width="140" height="95" rx="8" fill="var(--ph-color-primary)" fill-opacity="${opacity}"><title>${PHFrame.escape(item.value)}: ${item.count}</title></rect><text class="ph-map-label" x="70" y="44" text-anchor="middle">${PHFrame.escape(item.value)}</text><text class="ph-map-label" x="70" y="65" text-anchor="middle">${item.count}</text></g>`;
      }).join("");
      const rows = Math.max(1, Math.ceil(values.length / columns));
      this.innerHTML = `<div class="ph-widget-body"><svg class="ph-chart" viewBox="0 0 ${columns * 150} ${rows * 105}" role="img" aria-label="Geographic tile map">${tiles}</svg></div><table class="ph-sr-only"><caption>Geographic distribution data</caption><thead><tr><th>Location</th><th>Count</th></tr></thead><tbody>${values.map(item => `<tr><td>${PHFrame.escape(item.value)}</td><td>${item.count}</td></tr>`).join("")}</tbody></table>`;
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
  async renderBoundary(boundary, values) {
    const L = await PHFrame.leaflet(), basemap = PHFrame.basemaps[PHFrame.siteSettings.basemap] || PHFrame.basemaps["carto-light"];
    this.innerHTML = `<div class="ph-boundary-map"><div class="ph-leaflet-map" role="application" aria-label="${PHFrame.escape(boundary.country)} administrative boundary choropleth"></div></div>`;
    const counts = new Map(values.map(item => [this.normalizePlace(item.value), Number(item.count || 0)]));
    const distinct = [...new Set([0, ...counts.values()].filter(Number.isFinite))].sort((a, b) => a - b);
    const palette = ["#e7ecef", "#fff59d", "#ff8a3d", "#ef5350", "#c62828", "#7f0000"];
    const exactClasses = distinct.length <= palette.length;
    const maximum = Math.max(1, ...distinct), stops = exactClasses ? distinct : [0, .2, .4, .6, .8, 1].map(part => Math.round(maximum * part)).filter((value, index, items) => index === 0 || value !== items[index - 1]);
    const color = value => { if (!value) return palette[0]; const index = exactClasses ? distinct.indexOf(value) : Math.max(1, stops.findIndex(stop => value <= stop)); return palette[Math.min(palette.length - 1, Math.max(1, index))]; };
    const nameOf = feature => { const p = feature.properties || {}; return p.shapeName || p.name || p.NAME_1 || p.NAME_2 || p.NAME || "Area"; };
    const map = L.map(this.querySelector(".ph-leaflet-map"), { zoomControl: true, scrollWheelZoom: false });
    L.tileLayer(basemap.url, { attribution: basemap.attribution, maxZoom: 19 }).addTo(map);
    const layer = L.geoJSON(boundary.geojson, { style: feature => { const count = counts.get(this.normalizePlace(nameOf(feature))) || 0; return { color: "#34444c", weight: 1, fillColor: color(count), fillOpacity: .82 }; }, onEachFeature: (feature, item) => { const name = nameOf(feature), count = counts.get(this.normalizePlace(name)) || 0; item.bindTooltip(`${PHFrame.escape(name)}: ${count}`, { sticky: true }); item.bindPopup(`<div class="ph-map-popup"><b>${PHFrame.escape(name)}</b><span>Value: ${count.toLocaleString()}</span><small>${PHFrame.escape(boundary.country)} ${PHFrame.escape(boundary.level)}</small></div>`); item.on({ mouseover: event => event.target.setStyle({ weight: 3, fillOpacity: 1 }), mouseout: event => layer.resetStyle(event.target) }); } }).addTo(map);
    map.fitBounds(layer.getBounds(), { padding: [16, 16] });
    const legend = L.control({ position: "topright" }); legend.onAdd = () => { const node = L.DomUtil.create("div", "ph-map-legend"); node.innerHTML = `<b>Value</b>${stops.map((stop, index) => `<span><i style="background:${color(stop)}"></i>${exactClasses || index === 0 ? stop.toLocaleString() : `${stops[index - 1].toLocaleString()}–${stop.toLocaleString()}`}</span>`).join("")}<small>${PHFrame.escape(boundary.country)} · ${PHFrame.escape(boundary.level)}</small>`; return node; }; legend.addTo(map);
    setTimeout(() => map.invalidateSize(), 80);
  }
  normalizePlace(value) { return String(value || "").toLowerCase().normalize("NFKD").replace(/[^a-z0-9]/g, ""); }
  geometryPoints(geometry) { if (!geometry) return []; const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : (geometry.type === "MultiPolygon" ? geometry.coordinates : []); return polygons.flatMap(polygon => polygon.flatMap(ring => ring)); }
  geometryPath(geometry, bounds) { const [minX, minY, maxX, maxY] = bounds, width = Math.max(.0001, maxX - minX), height = Math.max(.0001, maxY - minY), scale = Math.min(680 / width, 380 / height), offsetX = (720 - width * scale) / 2, offsetY = (420 - height * scale) / 2; const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : (geometry.type === "MultiPolygon" ? geometry.coordinates : []); return polygons.map(polygon => polygon.map(ring => ring.map((point, index) => `${index ? "L" : "M"}${(offsetX + (point[0] - minX) * scale).toFixed(1)},${(offsetY + (maxY - point[1]) * scale).toFixed(1)}`).join(" ") + " Z").join(" ")).join(" "); }
}

class PHGeoMap extends PHElement {
  async render() {
    this.innerHTML = PHFrame.loading("Loading map", true);
    try {
      const dataset = this.getAttribute("dataset"), latitude = this.getAttribute("latitude-field"), longitude = this.getAttribute("longitude-field");
      const response = await PHFrame.get(`/api/geospatial/${dataset}?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`), points = response.data.points;
      if (!points.length) { this.innerHTML = `<div class="ph-empty-state"><span>◎</span><p>No valid coordinates yet. Add numeric latitude and longitude columns, then import coordinate data.</p></div>`; return; }
      const maximum = Math.max(...points.map(point => point.count));
      const grid = [-120, -60, 0, 60, 120].map(lon => `<line x1="${lon + 180}" y1="0" x2="${lon + 180}" y2="180"></line>`).join("") + [-60, -30, 0, 30, 60].map(lat => `<line x1="0" y1="${90 - lat}" x2="360" y2="${90 - lat}"></line>`).join("");
      const marks = points.map(point => { const x = point.longitude + 180, y = 90 - point.latitude, radius = 3 + Math.sqrt(point.count / maximum) * 10; return `<circle cx="${x}" cy="${y}" r="${radius}"><title>${point.latitude}, ${point.longitude}: ${point.count}</title></circle>`; }).join("");
      this.innerHTML = `<div class="ph-widget-body ph-world-map"><svg class="ph-chart" viewBox="0 0 360 180" role="img" aria-label="Worldwide coordinate distribution"><rect width="360" height="180" rx="8"></rect><g class="ph-map-grid">${grid}</g><g class="ph-map-points">${marks}</g></svg><p class="ph-muted">${points.length} coordinate area(s) · coordinates privacy-rounded to 0.01°</p></div>`;
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
}

class PHDashboardManager extends PHElement {
  set metadata(value) { this._metadata = value; if (this.isConnected) this.render(); }
  async render() {
    if (!this._metadata) return;
    const renderId = (this._renderId || 0) + 1;
    this._renderId = renderId;
    this.innerHTML = `<section class="ph-dashboard-loading">${PHFrame.loading("Loading dashboard and visualizations")}</section>`;
    let configured;
    try {
      configured = await Promise.all(Object.entries(this._metadata.dashboards || {}).map(async ([id, item]) => ({ id: `configured-${id}`, configured: true, ...(await PHFrame.get(item.endpoint)).data })));
    } catch (error) {
      this.innerHTML = `<div class="ph-load-error" role="alert"><h2>Dashboard could not load</h2><p>${PHFrame.escape(error.message)}</p><button class="ph-button" type="button">Try again</button></div>`;
      this.querySelector("button").addEventListener("click", () => this.render());
      return;
    }
    if (renderId !== this._renderId) return;
    this.dashboards = [...configured.map(item => ({ ...item, title: item.label, description: "Configured project dashboard" })), ...(PHFrame.siteSettings.dashboards || [])];
    const selected = localStorage.getItem("ph-active-dashboard"), active = this.dashboards.find(item => item.id === selected) || this.dashboards[0];
    const options = this.dashboards.map(item => `<option value="${PHFrame.escape(item.id)}" ${item === active ? "selected" : ""}>${PHFrame.escape(item.title)}</option>`).join("");
    this.innerHTML = `<section class="ph-dashboard-manager"><div class="ph-dashboard-switcher"><div class="ph-field"><label>Dashboard</label><select data-dashboard-select>${options}</select></div><button class="ph-button" data-new-dashboard>+ Create new</button>${active?.configured ? `<button class="ph-button ph-button-secondary" data-customize-dashboard>Customize this dashboard</button>` : (active ? `<button class="ph-button ph-button-secondary" data-edit-dashboard>Edit name</button><button class="ph-icon-danger" data-delete-dashboard title="Delete dashboard">×</button>` : "")}${active ? `<button class="ph-button ph-button-secondary" data-publish-dashboard>Publish dashboard</button>` : ""}</div><div data-dashboard-host></div>${this.createDialog()}${this.customizeDialog()}${this.publishDialog(active)}</section>`;
    if (active) this.show(active); else this.querySelector("[data-dashboard-host]").innerHTML = `<div class="ph-empty-state"><span>▦</span><p>Create your first dashboard from a professional template.</p></div>`;
    this.querySelector("[data-dashboard-select]").addEventListener("change", event => { localStorage.setItem("ph-active-dashboard", event.target.value); this.render(); });
    const dialog = this.querySelector(":scope > .ph-dashboard-manager > .ph-template-dialog");
    this.querySelector("[data-new-dashboard]").addEventListener("click", () => { dialog.showModal(); this.updateTemplateRecommendations(); });
    dialog.querySelector('[name="dataset"]').addEventListener("change", () => this.updateTemplateRecommendations());
    dialog.querySelectorAll("[data-template]").forEach(button => button.addEventListener("click", () => this.createDashboard(button.dataset.template)));
    this.querySelector("[data-edit-dashboard]")?.addEventListener("click", () => this.editDashboard(active));
    this.querySelector("[data-customize-dashboard]")?.addEventListener("click", () => this.openCustomizeDialog(active));
    this.querySelector("[data-customize-form]")?.addEventListener("submit", event => this.customizeDashboard(event, active));
    this.querySelector("[data-delete-dashboard]")?.addEventListener("click", () => this.deleteDashboard(active));
    this.querySelector("[data-publish-dashboard]")?.addEventListener("click", () => this.querySelector(".ph-publish-dialog").showModal());
    this.querySelector("[data-publish-form]")?.addEventListener("submit", event => this.publishDashboard(event, active));
    this.querySelector("[data-download-bundle]")?.addEventListener("click", () => this.downloadBundle(active));
    this.querySelector('[name="mode"]')?.addEventListener("change", event => this.toggleLiveFields(event.target.value));
  }
  show(dashboard) { const component = document.createElement("ph-dashboard"); component.definition = dashboard; component.metadata = this._metadata; component.addEventListener("ph-dashboard-definition", event => this.updateDefinition(event.detail)); this.querySelector("[data-dashboard-host]").replaceChildren(component); }
  createDialog() {
    const datasets = Object.entries(this._metadata.datasets).map(([name, item]) => `<option value="${name}">${PHFrame.escape(item.label)}</option>`).join("");
    return `<dialog class="ph-dialog ph-template-dialog"><form method="dialog" class="ph-stack"><div class="ph-widget-header"><div><p class="ph-eyebrow">Dashboard templates</p><h2>Create a professional dashboard</h2></div><button value="cancel" class="ph-dialog-close">×</button></div><div class="ph-form-grid"><div class="ph-field"><label>Dashboard name</label><input name="title" required placeholder="National programme overview"></div><div class="ph-field"><label>Primary dataset</label><select name="dataset">${datasets}</select></div></div><div class="ph-template-grid"><button type="button" data-template="overview"><b>Executive overview</b><span>Headline metric, categories, and trend</span></button><button type="button" data-template="surveillance"><b>Surveillance operations</b><span>Indicators, alerts, locations, and time</span></button><button type="button" data-template="programme"><b>Programme monitoring</b><span>Coverage-style metrics and disaggregation</span></button><button type="button" data-template="dhis2"><b>DHIS2 aggregate</b><span>Data values, elements, and category combinations</span></button><button type="button" data-template="geospatial"><b>Worldwide geospatial</b><span>Coordinate map and geographic breakdown</span></button><button type="button" data-template="blank"><b>Blank canvas</b><span>Add text, links, tables, maps, and charts yourself</span></button></div><p class="ph-muted" data-template-advice></p></form></dialog>`;
  }
  customizeDialog() {
    return `<dialog class="ph-dialog ph-customize-dialog"><form method="dialog" class="ph-stack" data-customize-form><div class="ph-widget-header"><div><p class="ph-eyebrow">Editable dashboard</p><h2>Customize this dashboard</h2></div><button value="cancel" class="ph-dialog-close" aria-label="Close">×</button></div><p class="ph-muted">PHFrame will create an editable copy. Your original configured dashboard remains unchanged.</p><div class="ph-field"><label for="ph-custom-dashboard-name">Dashboard name</label><input id="ph-custom-dashboard-name" name="title" required></div><div class="ph-actions"><button class="ph-button" value="default">Create editable copy</button><button value="cancel">Cancel</button></div></form></dialog>`;
  }
  publishDialog(active) {
    if (!active) return "";
    const previous = (PHFrame.siteSettings.publications || []).find(item => item.dashboard_id === active.id);
    const project = String(previous?.project_name || PHFrame.siteSettings.cloudflare_project_name || active.title || "dashboard").toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-|-$/g, "").slice(0, 58);
    const mode = previous?.mode || "snapshot", refresh = Number(previous?.refresh_minutes || 15), action = previous ? "Update published dashboard" : "Publish to Cloudflare";
    return `<dialog class="ph-dialog ph-publish-dialog"><form method="dialog" class="ph-stack" data-publish-form><div class="ph-widget-header"><div><p class="ph-eyebrow">Privacy-aware publication</p><h2>${previous ? "Update published dashboard" : "Publish this dashboard"}</h2></div><button value="cancel" class="ph-dialog-close" aria-label="Close">×</button></div><p class="ph-muted">${previous ? `Your changes will replace the current dashboard at <a href="${PHFrame.escape(previous.url)}" target="_blank" rel="noopener">the same public URL</a>.` : "Only aggregate visualization output is exported. PHFrame blocks protected fields before creating a bundle or deployment."}</p><div class="ph-form-grid"><div class="ph-field"><label>Publication mode</label><select name="mode"><option value="snapshot" ${mode === "snapshot" ? "selected" : ""}>Snapshot — fixed data</option><option value="live" ${mode === "live" ? "selected" : ""}>Live — refresh from aggregate API</option></select></div><div class="ph-field"><label>Cloudflare project name</label><input name="project_name" value="${PHFrame.escape(project)}" pattern="[a-z0-9][a-z0-9-]*[a-z0-9]|[a-z0-9]" required ${previous ? "readonly" : ""}></div></div><div class="ph-stack" data-live-fields ${mode === "live" ? "" : "hidden"}><div class="ph-field"><label>HTTPS aggregate API URL</label><input name="upstream_url" type="url" placeholder="https://api.example.org/dashboard-feed"></div><div class="ph-field"><label>Refresh/cache interval (minutes)</label><input name="refresh_minutes" type="number" min="1" max="1440" value="${refresh}"></div><p class="ph-muted">If the API needs a bearer token, add the <code>UPSTREAM_API_TOKEN</code> secret to the deployed Cloudflare Pages project.</p></div><div class="ph-card ph-publication-review" data-publication-review><b>Privacy review required</b><span>Publish or download to run the aggregate-only review.</span></div><div class="ph-actions"><button class="ph-button" value="publish">${action}</button><button class="ph-button ph-button-secondary" type="button" data-download-bundle>Download bundle</button><button value="cancel">Cancel</button></div><p class="ph-status" role="status" data-publication-status>${previous ? `Currently published: <a href="${PHFrame.escape(previous.url)}" target="_blank" rel="noopener">${PHFrame.escape(previous.url)}</a>` : ""}</p></form></dialog>`;
  }
  toggleLiveFields(mode) { const host = this.querySelector("[data-live-fields]"); if (host) { host.hidden = mode !== "live"; host.querySelector('[name="upstream_url"]').required = mode === "live"; } }
  publicationPayload(active) { const form = this.querySelector("[data-publish-form]"), data = new FormData(form); return { dashboard_id: active.id, mode: data.get("mode"), project_name: data.get("project_name"), upstream_url: data.get("upstream_url") || "", refresh_minutes: Number(data.get("refresh_minutes") || 15) }; }
  async reviewPublication(active) { const review = this.querySelector("[data-publication-review]"), response = await PHFrame.send("/api/publications/preview", "POST", this.publicationPayload(active)); review.innerHTML = `<b>✓ Privacy review passed</b><span>${response.data.sources.length} aggregate source(s), ${response.data.row_level_records} row-level records, ${response.data.protected_fields} protected fields.</span>`; review.classList.add("ph-publication-approved"); return response.data; }
  async publishDashboard(event, active) { if (event.submitter?.value !== "publish") return; event.preventDefault(); const status = this.querySelector("[data-publication-status]"), button = event.submitter, updating = (PHFrame.siteSettings.publications || []).some(item => item.dashboard_id === active.id); button.disabled = true; status.textContent = updating ? "Reviewing privacy and updating the public dashboard…" : "Reviewing privacy and deploying…"; try { await this.reviewPublication(active); const response = await PHFrame.send("/api/publications/deploy", "POST", this.publicationPayload(active)); PHFrame.siteSettings.publications = [response.data, ...(PHFrame.siteSettings.publications || [])]; status.innerHTML = `Published: <a href="${PHFrame.escape(response.data.url)}" target="_blank" rel="noopener">${PHFrame.escape(response.data.url)}</a>`; button.textContent = "Update published dashboard"; PHFrame.notify(updating ? "Public dashboard updated at the same URL." : "Dashboard published to Cloudflare."); } catch (error) { status.textContent = error.message; status.className = "ph-status ph-error"; } finally { button.disabled = false; } }
  async downloadBundle(active) { const status = this.querySelector("[data-publication-status]"); status.textContent = "Reviewing privacy and building bundle…"; try { await this.reviewPublication(active); const response = await fetch("/api/publications/bundle", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(this.publicationPayload(active)) }); if (!response.ok) throw new Error((await response.json()).error?.message || "Bundle creation failed."); const blob = await response.blob(), link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `${this.publicationPayload(active).project_name}-cloudflare.zip`; link.click(); URL.revokeObjectURL(link.href); status.textContent = "Deployment bundle downloaded."; } catch (error) { status.textContent = error.message; status.className = "ph-status ph-error"; } }
  capabilities(dataset) {
    const fields = this._metadata.datasets[dataset].fields, entries = Object.entries(fields);
    const numeric = entries.filter(([, field]) => ["integer", "number", "age"].includes(field.type)).map(([name]) => name), dates = entries.filter(([, field]) => ["date", "datetime"].includes(field.type)).map(([name]) => name), categories = entries.filter(([, field]) => !["integer", "number", "age", "date", "datetime"].includes(field.type) && !field.protected).map(([name]) => name);
    const latitude = numeric.find(name => /^(lat|latitude|y_coordinate)$/i.test(name)), longitude = numeric.find(name => /^(lon|lng|longitude|x_coordinate)$/i.test(name));
    return { numeric, dates, categories, latitude, longitude, dhis2: "data_element" in fields || dataset.toLowerCase().includes("dhis2") };
  }
  updateTemplateRecommendations() {
    const dataset = this.querySelector('.ph-template-dialog [name="dataset"]').value, caps = this.capabilities(dataset);
    this.querySelectorAll("[data-template]").forEach(button => button.classList.remove("ph-template-recommended"));
    const recommended = caps.dhis2 ? "dhis2" : (caps.latitude && caps.longitude ? "geospatial" : (caps.dates.length ? "surveillance" : "overview"));
    this.querySelector(`[data-template="${recommended}"]`).classList.add("ph-template-recommended");
    this.querySelector("[data-template-advice]").textContent = `Recommended: ${this.querySelector(`[data-template="${recommended}"] b`).textContent}. Based on ${caps.numeric.length} numeric, ${caps.categories.length} categorical, and ${caps.dates.length} date columns${caps.dhis2 ? ", including DHIS2 aggregate fields" : ""}.`;
  }
  templateWidgets(template, dataset) {
    const caps = this.capabilities(dataset), label = this._metadata.datasets[dataset].label, widgets = [{ _id: `content-${Date.now()}`, type: "content", title: "About this dashboard", html: `<p><strong>${PHFrame.escape(label)}</strong></p><p>Edit this text to explain the programme, reporting period, and audience. Add <a href="https://www.who.int">supporting links</a> as needed.</p>` }];
    if (caps.numeric[0]) widgets.push({ _id: `metric-${Date.now()}`, type: "field_kpi", title: `Total ${caps.numeric[0].replaceAll("_", " ")}`, dataset, field: caps.numeric[0], operation: "sum" });
    if (caps.categories[0]) widgets.push({ _id: `groups-${Date.now()}`, type: "field_chart", title: `${caps.categories[0].replaceAll("_", " ")} distribution`, dataset, field: caps.categories[0] });
    if (caps.dates[0] && caps.numeric[0]) widgets.push({ _id: `trend-${Date.now()}`, type: "epi_curve", title: `${caps.numeric[0].replaceAll("_", " ")} over time`, dataset, date_field: caps.dates[0], value_field: caps.numeric[0] });
    if (template === "dhis2") caps.categories.slice(0, 2).forEach((field, index) => widgets.push({ _id: `dhis2-${index}-${Date.now()}`, type: "field_chart", title: `${field.replaceAll("_", " ")} breakdown`, dataset, field }));
    if (template === "surveillance") Object.entries(this._metadata.indicators || {}).filter(([, item]) => item.dataset === dataset).slice(0, 3).forEach(([indicator, item]) => widgets.push({ _id: `indicator-${indicator}-${Date.now()}`, type: "kpi", title: item.label, indicator }));
    if (template === "geospatial" && caps.latitude && caps.longitude) widgets.push({ _id: `map-${Date.now()}`, type: "geo_map", title: "Geographic distribution", dataset, latitude_field: caps.latitude, longitude_field: caps.longitude });
    return template === "blank" ? [] : widgets;
  }
  async createDashboard(template) {
    const form = this.querySelector(".ph-template-dialog form"), title = form.elements.title.value.trim(), dataset = form.elements.dataset.value;
    if (!title) { form.elements.title.reportValidity(); return; }
    const dashboard = { id: `dashboard-${Date.now()}`, title, description: `${this._metadata.datasets[dataset].label} · ${template.replaceAll("_", " ")} template`, dataset, template, widgets: this.templateWidgets(template, dataset) };
    await this.persist([...(PHFrame.siteSettings.dashboards || []), dashboard]); localStorage.setItem("ph-active-dashboard", dashboard.id); this.querySelector(".ph-template-dialog").close(); this.render();
  }
  async persist(dashboards) { const response = await PHFrame.send("/api/settings", "PUT", { dashboards }); PHFrame.siteSettings.dashboards = response.data.dashboards; }
  async updateDefinition(dashboard) { if (dashboard.configured) return; await this.persist(PHFrame.siteSettings.dashboards.map(item => item.id === dashboard.id ? dashboard : item)); }
  openCustomizeDialog(dashboard) { const dialog = this.querySelector(".ph-customize-dialog"); dialog.querySelector('[name="title"]').value = `${dashboard.title} — Custom`; dialog.showModal(); dialog.querySelector('[name="title"]').select(); }
  async customizeDashboard(event, dashboard) { if (event.submitter?.value === "cancel") return; event.preventDefault(); const title = new FormData(event.currentTarget).get("title").trim(); if (!title) return; const copy = { id: `dashboard-${Date.now()}`, title, description: dashboard.description || "Customized project dashboard", dataset: "", template: "custom", widgets: dashboard.widgets.map((widget, index) => ({ ...widget, _id: widget._id || `widget-${index}-${Date.now()}` })) }; await this.persist([...(PHFrame.siteSettings.dashboards || []), copy]); localStorage.setItem("ph-active-dashboard", copy.id); this.querySelector(".ph-customize-dialog").close(); this.render(); }
  async editDashboard(dashboard) { const title = prompt("Dashboard name", dashboard.title); if (!title?.trim()) return; const description = prompt("Dashboard description", dashboard.description || "") ?? dashboard.description; await this.updateDefinition({ ...dashboard, title: title.trim(), description }); this.render(); }
  async deleteDashboard(dashboard) { if (!confirm(`Delete ${dashboard.title}?`)) return; await this.persist(PHFrame.siteSettings.dashboards.filter(item => item.id !== dashboard.id)); localStorage.removeItem("ph-active-dashboard"); this.render(); }
}

class PHDashboard extends PHElement {
  set definition(value) { this._definition = value; if (this.isConnected && this._metadata) this.render(); }
  get metadata() { return this._metadata; }
  set metadata(value) { this._metadata = value; if (this.isConnected && this._definition) this.render(); }
  async render() {
    try {
      if (this._definition) { this.dashboard = this._definition; }
      else { const [response, metadata] = await Promise.all([PHFrame.get(`/api/dashboards/${this.getAttribute("name")}`), PHFrame.get("/api")]); this.dashboard = response.data; this.metadata = metadata; }
      this.storageKey = `ph-dashboard-layout:${this.dashboard.id || this.getAttribute("name") || this.dashboard.name}`;
      this.settings = this.loadSettings();
      this.draw();
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
  widgetId(widget, index) { return widget._id || `${widget.type}-${widget.indicator || widget.dimension || widget.dataset || index}-${index}`; }
  defaults(widget) {
    if (widget.type === "content") return { visualization: "text", size: "wide", choices: [["text", "Rich text"]] };
    if (widget.type === "geo_map") return { visualization: "coordinates", size: "wide", choices: [["coordinates", "Coordinate map"]] };
    if (widget.type === "kpi" || widget.type === "field_kpi") return { visualization: "number", size: "compact", choices: [["number", "Number"], ["gauge", "Gauge"]] };
    if (widget.type === "chart" || widget.type === "field_chart") return { visualization: "bar", size: "medium", choices: [["bar", "Bar chart"], ["donut", "Donut chart"], ["table", "Data table"]] };
    if (widget.type === "map") return { visualization: "tiles", size: "medium", choices: [["tiles", "Tile map"], ["bar", "Bar chart"], ["donut", "Donut chart"], ["table", "Data table"]] };
    return { visualization: "line", size: "wide", choices: [["line", "Line chart"], ["column", "Column chart"], ["table", "Data table"]] };
  }
  loadSettings() {
    try { return JSON.parse(localStorage.getItem(this.storageKey)) || {}; } catch (_) { return {}; }
  }
  saveSettings() {
    const cards = [...this.querySelectorAll(".ph-dashboard-card")];
    this.settings.order = cards.map(card => card.dataset.widgetId);
    localStorage.setItem(this.storageKey, JSON.stringify(this.settings));
  }
  draw() {
    const allWidgets = [...this.dashboard.widgets, ...(this.settings.customWidgets || [])];
    const hidden = new Set(this.settings.hidden || []);
    const indexed = allWidgets.map((widget, index) => ({ widget, index, id: this.widgetId(widget, index) })).filter(item => !hidden.has(item.id));
    const order = this.settings.order || [];
    indexed.sort((a, b) => { const ai = order.indexOf(a.id), bi = order.indexOf(b.id); return (ai < 0 ? 999 + a.index : ai) - (bi < 0 ? 999 + b.index : bi); });
    const cards = indexed.map(item => this.card(item.widget, item.index, item.id)).join("");
    const title = this.dashboard.title || this.dashboard.label, description = this.dashboard.description || "Live metrics, content, maps, and trends from your selected data";
    this.innerHTML = `<section class="ph-dashboard-heading"><div><p class="ph-eyebrow">${PHFrame.escape(this.dashboard.template || "Data overview")}</p><h2>${PHFrame.escape(title)}</h2><p class="ph-muted">${PHFrame.escape(description)}</p></div><div class="ph-dashboard-actions"><button class="ph-button" type="button" data-add-widget>+ Add visualization</button><button class="ph-button ph-button-secondary" type="button" data-add-content>+ Add text</button><button class="ph-button ph-button-secondary" type="button" data-reset>Reset layout</button><span class="ph-save-state" role="status">Changes save automatically</span></div></section><div class="ph-dashboard-grid" aria-label="Customizable dashboard">${cards || `<div class="ph-empty-state"><span>＋</span><p>Blank dashboard. Add text, a table, chart, metric, trend, or map.</p></div>`}</div>${this.widgetDialog()}${this.contentDialog()}`;
    this.bind();
  }
  widgetDialog() {
    const indicators = Object.entries(this.metadata.indicators || {}).map(([name, item]) => `<option value="kpi|${name}">Metric · ${PHFrame.escape(item.label)}</option>`).join("");
    const dimensions = Object.entries(this.metadata.dimensions || {}).map(([name, item]) => `<option value="chart|${name}">Category · ${PHFrame.escape(item.label)}</option>`).join("");
    const fields = Object.entries(this.metadata.datasets || {}).flatMap(([dataset, item]) => Object.entries(item.fields).filter(([, field]) => !["integer", "number", "date", "datetime"].includes(field.type)).map(([name, field]) => `<option value="field_chart|${dataset}|${name}">Column · ${PHFrame.escape(item.label)} · ${PHFrame.escape(field.label || name)}</option>`)).join("");
    const numericFields = Object.entries(this.metadata.datasets || {}).flatMap(([dataset, item]) => Object.entries(item.fields).filter(([, field]) => ["integer", "number", "age"].includes(field.type)).map(([name, field]) => `<option value="field_kpi|${dataset}|${name}">Metric · Sum of ${PHFrame.escape(field.label || name)}</option>`)).join("");
    const trends = Object.entries(this.metadata.datasets || {}).flatMap(([dataset, item]) => {
      const dates = Object.entries(item.fields).filter(([, field]) => ["date", "datetime"].includes(field.type));
      const numbers = Object.entries(item.fields).filter(([, field]) => ["integer", "number", "age"].includes(field.type));
      return dates.flatMap(([date]) => numbers.map(([value]) => `<option value="epi_curve|${dataset}|${date}|${value}">Trend · ${PHFrame.escape(item.label)} · ${PHFrame.escape(value)}</option>`));
    }).join("");
    const maps = Object.entries(this.metadata.datasets || {}).flatMap(([dataset, item]) => { const numeric = Object.entries(item.fields).filter(([, field]) => ["integer", "number"].includes(field.type)).map(([name]) => name), lat = numeric.find(name => /^(lat|latitude|y_coordinate)$/i.test(name)), lon = numeric.find(name => /^(lon|lng|longitude|x_coordinate)$/i.test(name)); return lat && lon ? [`<option value="geo_map|${dataset}|${lat}|${lon}">Map · ${PHFrame.escape(item.label)} · coordinates</option>`] : []; }).join("");
    return `<dialog class="ph-dialog ph-widget-dialog"><form method="dialog" class="ph-stack" data-widget-form><div class="ph-widget-header"><div><p class="ph-eyebrow">Dashboard builder</p><h2>Add visualization</h2></div><button value="cancel" class="ph-dialog-close" aria-label="Close">×</button></div><div class="ph-field"><label for="ph-widget-title">Title</label><input id="ph-widget-title" name="title" required placeholder="My visualization"></div><div class="ph-field"><label for="ph-widget-source">Data source</label><select id="ph-widget-source" name="source" required>${indicators}${numericFields}${dimensions}${fields}${trends}${maps}</select></div><div class="ph-actions"><button class="ph-button" value="default" data-create-widget>Add to dashboard</button><button value="cancel">Cancel</button></div></form></dialog>`;
  }
  contentDialog() { return `<dialog class="ph-dialog ph-content-dialog"><form method="dialog" class="ph-stack" data-content-form><div class="ph-widget-header"><div><p class="ph-eyebrow">Dashboard content</p><h2>Add text, heading, paragraph, or link</h2></div><button value="cancel" class="ph-dialog-close">×</button></div><div class="ph-field"><label>Block title</label><input name="title" required placeholder="About this dashboard"></div><ph-rich-editor data-dashboard-editor></ph-rich-editor><div class="ph-actions"><button class="ph-button" value="default">Add content</button><button value="cancel">Cancel</button></div></form></dialog>`; }
  card(widget, index, id) {
    const defaults = this.defaults(widget), saved = this.settings[id] || {};
    const visualization = saved.visualization || defaults.visualization, size = saved.size || defaults.size;
    const options = defaults.choices.map(([value, label]) => `<option value="${value}" ${value === visualization ? "selected" : ""}>${label}</option>`).join("");
    const sizeOptions = [["compact", "Small"], ["medium", "Medium"], ["wide", "Wide"]].map(([value, label]) => `<option value="${value}" ${value === size ? "selected" : ""}>${label}</option>`).join("");
    let component;
    if (widget.type === "content") component = `<div class="ph-dashboard-content ph-prose">${widget.html || ""}</div>`;
    else if (widget.type === "geo_map") component = `<ph-geo-map dataset="${widget.dataset}" latitude-field="${widget.latitude_field}" longitude-field="${widget.longitude_field}"></ph-geo-map>`;
    else if (widget.type === "kpi") component = `<ph-kpi indicator="${widget.indicator}" visualization="${visualization}"></ph-kpi>`;
    else if (widget.type === "field_kpi") component = `<ph-kpi dataset="${widget.dataset}" field="${widget.field}" operation="${widget.operation || "sum"}" visualization="${visualization}"></ph-kpi>`;
    else if (widget.type === "chart") component = `<ph-indicator-chart dimension="${widget.dimension}" visualization="${visualization}"></ph-indicator-chart>`;
    else if (widget.type === "field_chart") component = `<ph-indicator-chart dataset="${widget.dataset}" field="${widget.field}" visualization="${visualization}"></ph-indicator-chart>`;
    else if (widget.type === "map") component = `<ph-map dimension="${widget.dimension}" visualization="${visualization}"></ph-map>`;
    else component = `<ph-epi-curve dataset="${widget.dataset}" date-field="${widget.date_field}" value-field="${widget.value_field || ""}" visualization="${visualization}"></ph-epi-curve>`;
    const span = saved.span || { compact: 3, medium: 6, wide: 12 }[size], height = saved.height || 285;
    const handles = ["n", "e", "s", "w", "ne", "se", "sw", "nw"].map(direction => `<button class="ph-resize-handle ph-resize-${direction}" data-resize="${direction}" type="button" aria-label="Resize ${PHFrame.escape(widget.title)} ${direction}" title="Drag to resize"></button>`).join("");
    const edit = widget.type === "content" ? `<button class="ph-edit-content" type="button" aria-label="Edit ${PHFrame.escape(widget.title)}" title="Edit content">✎</button>` : "";
    return `<article class="ph-card ph-dashboard-card ph-size-${size}" style="--ph-widget-span:${span};--ph-widget-height:${height}px" data-widget-id="${id}"><header class="ph-widget-header"><div><p class="ph-widget-kind">${PHFrame.escape(widget.type === "epi_curve" ? "Trend" : widget.type)}</p><h3>${PHFrame.escape(widget.title)}</h3></div><div class="ph-card-actions"><button class="ph-drag-handle" type="button" draggable="true" aria-label="Drag ${PHFrame.escape(widget.title)}" title="Drag to reorder">⠿</button>${edit}<button class="ph-remove-widget" type="button" aria-label="Remove ${PHFrame.escape(widget.title)}" title="Remove visualization">×</button></div></header><div class="ph-widget-controls"><label>View<select data-visualization>${options}</select></label><label>Size<select data-size>${sizeOptions}</select></label><button type="button" data-move="up" aria-label="Move ${PHFrame.escape(widget.title)} earlier">←</button><button type="button" data-move="down" aria-label="Move ${PHFrame.escape(widget.title)} later">→</button></div><div class="ph-widget-content">${component}</div>${handles}</article>`;
  }
  bind() {
    this.querySelector("[data-reset]").addEventListener("click", () => { localStorage.removeItem(this.storageKey); this.settings = {}; this.draw(); PHFrame.notify("Dashboard layout reset."); });
    const dialog = this.querySelector(".ph-widget-dialog");
    const contentDialog = this.querySelector(".ph-content-dialog"); contentDialog.querySelector("ph-rich-editor").value = "<h3>Heading</h3><p>Write your dashboard explanation here. Select text and use the toolbar to add formatting or a hyperlink.</p>";
    this.querySelector("[data-add-widget]").addEventListener("click", () => dialog.showModal());
    this.querySelector("[data-add-content]").addEventListener("click", () => contentDialog.showModal());
    this.querySelector("[data-widget-form]").addEventListener("submit", event => { if (event.submitter?.value === "cancel") return; event.preventDefault(); this.addWidget(event.currentTarget); dialog.close(); });
    this.querySelector("[data-content-form]").addEventListener("submit", event => { if (event.submitter?.value === "cancel") return; event.preventDefault(); const form = event.currentTarget, editing = form.dataset.editing, widget = { _id: editing || `content-${Date.now()}`, type: "content", title: form.elements.title.value, html: form.querySelector("ph-rich-editor").value }; editing ? this.updateContent(widget) : this.addManagedWidget(widget); delete form.dataset.editing; contentDialog.close(); });
    this.querySelectorAll(".ph-dashboard-card").forEach(card => {
      card.querySelector("[data-visualization]").addEventListener("change", event => this.updateCard(card, "visualization", event.target.value));
      card.querySelector("[data-size]").addEventListener("change", event => this.updateCard(card, "size", event.target.value));
      card.querySelectorAll("[data-move]").forEach(button => button.addEventListener("click", () => this.move(card, button.dataset.move)));
      card.querySelector(".ph-remove-widget").addEventListener("click", () => this.removeWidget(card.dataset.widgetId));
      card.querySelector(".ph-edit-content")?.addEventListener("click", () => this.editContent(card.dataset.widgetId, contentDialog));
      card.querySelectorAll("[data-resize]").forEach(handle => handle.addEventListener("pointerdown", event => this.startResize(event, card, handle.dataset.resize)));
      card.addEventListener("dragstart", event => { if (!event.target.closest(".ph-drag-handle")) { event.preventDefault(); return; } card.classList.add("ph-dragging"); event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", card.dataset.widgetId); });
      card.addEventListener("dragend", () => { card.classList.remove("ph-dragging"); this.querySelectorAll(".ph-drag-over").forEach(item => item.classList.remove("ph-drag-over")); });
      card.addEventListener("dragover", event => { event.preventDefault(); card.classList.add("ph-drag-over"); });
      card.addEventListener("dragleave", () => card.classList.remove("ph-drag-over"));
      card.addEventListener("drop", event => { event.preventDefault(); const source = this.querySelector(`[data-widget-id="${CSS.escape(event.dataTransfer.getData("text/plain"))}"]`); if (source && source !== card) card.before(source); card.classList.remove("ph-drag-over"); this.saveSettings(); PHFrame.notify("Dashboard layout saved."); });
    });
  }
  updateCard(card, property, value) {
    const id = card.dataset.widgetId;
    this.settings[id] = { ...(this.settings[id] || {}), [property]: value };
    if (property === "size") { const span = { compact: 3, medium: 6, wide: 12 }[value]; this.settings[id].span = span; card.className = `ph-card ph-dashboard-card ph-size-${value}`; card.style.setProperty("--ph-widget-span", span); }
    else { const visualization = card.querySelector("[data-visualization]").value; const component = card.querySelector("ph-kpi, ph-indicator-chart, ph-map, ph-epi-curve"); if (component) { component.setAttribute("visualization", visualization); component.render(); } }
    this.saveSettings();
  }
  move(card, direction) {
    const sibling = direction === "up" ? card.previousElementSibling : card.nextElementSibling;
    if (!sibling) return;
    if (direction === "up") sibling.before(card); else sibling.after(card);
    this.saveSettings(); card.querySelector(".ph-drag-handle").focus(); PHFrame.notify("Dashboard layout saved.");
  }
  addWidget(form) {
    const data = new FormData(form), parts = String(data.get("source")).split("|");
    const widget = { _id: `custom-${Date.now()}`, type: parts[0], title: String(data.get("title")) };
    if (widget.type === "kpi") widget.indicator = parts[1];
    else if (widget.type === "field_kpi") { widget.dataset = parts[1]; widget.field = parts[2]; widget.operation = "sum"; }
    else if (widget.type === "chart") widget.dimension = parts[1];
    else if (widget.type === "field_chart") { widget.dataset = parts[1]; widget.field = parts[2]; }
    else if (widget.type === "geo_map") { widget.dataset = parts[1]; widget.latitude_field = parts[2]; widget.longitude_field = parts[3]; }
    else { widget.dataset = parts[1]; widget.date_field = parts[2]; widget.value_field = parts[3]; }
    this.addManagedWidget(widget);
  }
  addManagedWidget(widget) { if (this.dashboard.configured) { this.settings.customWidgets = [...(this.settings.customWidgets || []), widget]; localStorage.setItem(this.storageKey, JSON.stringify(this.settings)); } else { this.dashboard = { ...this.dashboard, widgets: [...this.dashboard.widgets, widget] }; this.dispatchEvent(new CustomEvent("ph-dashboard-definition", { bubbles: true, detail: this.dashboard })); } this.draw(); PHFrame.notify(`${widget.type === "content" ? "Content" : "Visualization"} added.`); }
  editContent(id, dialog) { const widgets = [...this.dashboard.widgets, ...(this.settings.customWidgets || [])], widget = widgets.find((item, index) => this.widgetId(item, index) === id || item._id === id); if (!widget) return; const form = dialog.querySelector("form"); form.dataset.editing = widget._id; form.elements.title.value = widget.title; form.querySelector("ph-rich-editor").value = widget.html; dialog.showModal(); }
  updateContent(widget) { if (this.dashboard.configured) { this.settings.customWidgets = (this.settings.customWidgets || []).map(item => item._id === widget._id ? widget : item); localStorage.setItem(this.storageKey, JSON.stringify(this.settings)); } else { this.dashboard = { ...this.dashboard, widgets: this.dashboard.widgets.map(item => item._id === widget._id ? widget : item) }; this.dispatchEvent(new CustomEvent("ph-dashboard-definition", { bubbles: true, detail: this.dashboard })); } this.draw(); PHFrame.notify("Dashboard content updated."); }
  removeWidget(id) {
    if (!this.dashboard.configured) { this.dashboard = { ...this.dashboard, widgets: this.dashboard.widgets.filter((widget, index) => this.widgetId(widget, index) !== id) }; this.dispatchEvent(new CustomEvent("ph-dashboard-definition", { bubbles: true, detail: this.dashboard })); }
    else { this.settings.hidden = [...new Set([...(this.settings.hidden || []), id])]; this.saveSettings(); }
    this.draw(); PHFrame.notify("Dashboard item removed.");
  }
  startResize(event, card, direction) {
    event.preventDefault(); event.stopPropagation();
    const startX = event.clientX, startY = event.clientY, startSpan = Number(getComputedStyle(card).getPropertyValue("--ph-widget-span")) || 6, startHeight = card.offsetHeight;
    const gridWidth = this.querySelector(".ph-dashboard-grid").clientWidth, columnWidth = gridWidth / 12;
    const move = pointer => { const horizontal = direction.includes("e") ? pointer.clientX - startX : (direction.includes("w") ? startX - pointer.clientX : 0); const vertical = direction.includes("s") ? pointer.clientY - startY : (direction.includes("n") ? startY - pointer.clientY : 0); const span = Math.min(12, Math.max(2, Math.round(startSpan + horizontal / columnWidth))); const height = Math.min(720, Math.max(210, startHeight + vertical)); card.style.setProperty("--ph-widget-span", span); card.style.setProperty("--ph-widget-height", `${height}px`); card.dataset.resizeSpan = span; card.dataset.resizeHeight = Math.round(height); };
    const end = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", end); const id = card.dataset.widgetId; this.settings[id] = { ...(this.settings[id] || {}), span: Number(card.dataset.resizeSpan || startSpan), height: Number(card.dataset.resizeHeight || startHeight) }; this.saveSettings(); PHFrame.notify("Widget size saved."); };
    addEventListener("pointermove", move); addEventListener("pointerup", end, { once: true });
  }
}

class PHNotificationCenter extends PHElement {
  connectedCallback() {
    this.innerHTML = `<div class="ph-toast-region" role="status" aria-live="polite" aria-atomic="true"></div>`;
    addEventListener("ph-notify", event => this.show(event.detail.message));
  }
  show(message) {
    const toast = document.createElement("div");
    toast.className = "ph-toast";
    toast.textContent = message;
    this.firstElementChild.append(toast);
    setTimeout(() => toast.remove(), 5000);
  }
}

class PHModal extends PHElement {
  connectedCallback() {
    const title = this.getAttribute("title") || "Dialog";
    const content = this.innerHTML;
    this.innerHTML = `<dialog class="ph-dialog" aria-labelledby="ph-modal-title"><h2 id="ph-modal-title">${PHFrame.escape(title)}</h2><div>${content}</div><form method="dialog"><button class="ph-button">Close</button></form></dialog>`;
  }
  open() { this.querySelector("dialog").showModal(); }
  close() { this.querySelector("dialog").close(); }
}

class PHConfirm extends PHElement {
  connectedCallback() {
    const label = this.getAttribute("label") || "Confirm";
    this.innerHTML = `<button class="ph-button" type="button">${PHFrame.escape(label)}</button><dialog class="ph-dialog" aria-labelledby="ph-confirm-title"><h2 id="ph-confirm-title">Confirm action</h2><p>${PHFrame.escape(this.getAttribute("message") || "Are you sure?")}</p><div class="ph-actions"><button type="button" data-confirm class="ph-button">Confirm</button><button type="button" data-cancel>Cancel</button></div></dialog>`;
    const dialog = this.querySelector("dialog");
    this.querySelector(":scope > button").addEventListener("click", () => dialog.showModal());
    this.querySelector("[data-cancel]").addEventListener("click", () => dialog.close());
    this.querySelector("[data-confirm]").addEventListener("click", () => { dialog.close(); this.dispatchEvent(new CustomEvent("ph-confirmed", { bubbles: true })); });
  }
}

class PHImportWizard extends PHElement {
  set metadata(value) { this._metadata = value; if (this.isConnected) this.render(); }
  async render() {
    if (!this._metadata) return;
    const datasets = Object.entries(this._metadata.datasets).map(([name, item]) => `<option value="${name}">${PHFrame.escape(item.label)}</option>`).join("");
    const templates = await PHFrame.get("/api/import-mappings");
    this.templates = Object.fromEntries(templates.data.map(item => [item.name, item]));
    const templateOptions = templates.data.map(item => `<option value="${item.name}">${PHFrame.escape(item.name)}</option>`).join("");
    this.innerHTML = `<div class="ph-import-shell"><aside class="ph-import-sidebar"><p class="ph-eyebrow">Import workflow</p><h3>Three safe steps</h3><ol><li class="ph-step-active"><span>1</span><div><b>Upload</b><small>Choose source data</small></div></li><li><span>2</span><div><b>Map fields</b><small>Match your schema</small></div></li><li><span>3</span><div><b>Validate & import</b><small>Review before saving</small></div></li></ol><div class="ph-import-safety"><b>Nothing is saved yet</b><small>PHFrame validates structure and types before importing.</small></div></aside><section class="ph-card ph-stack ph-import-workspace"><div class="ph-import-guide"><div><p class="ph-eyebrow">New import</p><h3>Bring your data in safely</h3><p class="ph-muted">Upload CSV, Excel, JSON, or XML. Preview and map every column before anything is saved.</p></div><div class="ph-example-links"><span>Example files</span><a data-example="csv">CSV</a><a data-example="json">JSON</a><a data-example="xml">XML</a></div></div><div class="ph-format-cards"><div><span>▦</span><b>CSV / Excel</b><small>Tabular rows with headers</small></div><div><span>{ }</span><b>JSON</b><small>Objects or records/data arrays</small></div><div><span>&lt;/&gt;</span><b>XML</b><small>Records containing record elements</small></div></div><div class="ph-import-step"><div class="ph-step-heading"><span>01</span><div><h3>Choose destination and file</h3><p>Select where the records belong, then upload your source.</p></div></div><div class="ph-form-grid"><div class="ph-field"><label for="ph-import-dataset">Destination dataset</label><select id="ph-import-dataset">${datasets}</select></div><div class="ph-field"><label for="ph-import-template">Field mapping</label><select id="ph-import-template"><option value="">Automatic mapping</option>${templateOptions}</select></div></div><label class="ph-file-drop" for="ph-import-file"><span>⇧</span><b>Drop a data file here or browse</b><small>CSV, XLSX, JSON, or XML</small><input id="ph-import-file" type="file" accept=".csv,.xlsx,.xlsm,.json,.xml"></label><div class="ph-import-actions"><p role="status" class="ph-status">Ready for a file.</p><button class="ph-button" type="button" data-preview>Preview and continue →</button></div></div><div data-workspace></div></section></div>`;
    this.querySelector("[data-preview]").addEventListener("click", () => this.preview());
    this.querySelectorAll("[data-example]").forEach(link => { link.href = `/api/import-example/${this.querySelector("#ph-import-dataset").value}?format=${link.dataset.example}`; link.setAttribute("download", ""); });
    this.querySelector("#ph-import-dataset").addEventListener("change", event => this.querySelectorAll("[data-example]").forEach(link => { link.href = `/api/import-example/${event.target.value}?format=${link.dataset.example}`; }));
    this.querySelector("#ph-import-file").addEventListener("change", event => { const file = event.target.files[0]; if (file) { this.querySelector(".ph-file-drop b").textContent = file.name; this.querySelector(".ph-file-drop small").textContent = `${Math.max(1, Math.round(file.size / 1024))} KB · ready to preview`; this.querySelector(".ph-file-drop").classList.add("ph-file-selected"); } });
  }
  async upload(path) {
    const file = this.querySelector("input[type=file]").files[0];
    if (!file) throw new Error("Choose a CSV, Excel, JSON, or XML file.");
    const separator = path.includes("?") ? "&" : "?";
    const response = await fetch(`${path}${separator}filename=${encodeURIComponent(file.name)}`, {
      method: "POST", headers: { "content-type": "application/octet-stream", accept: "application/json" }, body: file
    });
    const payload = await response.json();
    if (!response.ok) throw Object.assign(new Error(payload.error?.message || "Import failed."), { payload });
    return payload;
  }
  async preview() {
    const status = this.querySelector("[role=status]");
    status.textContent = "Reading and validating file structure…";
    try {
      const dataset = this.querySelector("#ph-import-dataset").value;
      const response = await this.upload(`/api/browser-import/${dataset}/preview`);
      this.previewData = response.data;
      const template = this.templates[this.querySelector("#ph-import-template").value];
      const initialMapping = template?.dataset === dataset ? template.mapping : response.data.suggested_mapping;
      const fields = response.data.fields;
      const mappings = response.data.columns.map(column => `<div class="ph-field"><label>${PHFrame.escape(column)}</label><select data-source="${PHFrame.escape(column)}"><option value="">Skip column</option>${fields.map(field => `<option value="${field.name}" ${initialMapping[column] === field.name ? "selected" : ""}>${PHFrame.escape(field.label)} (${field.type})${field.required ? " *" : ""}</option>`).join("")}</select></div>`).join("");
      const headers = response.data.columns.map(column => `<th>${PHFrame.escape(column)}</th>`).join("");
      const rows = response.data.sample.map(row => `<tr>${response.data.columns.map(column => `<td>${PHFrame.escape(row[column] ?? "")}</td>`).join("")}</tr>`).join("");
      this.querySelector("[data-workspace]").innerHTML = `<div class="ph-import-step"><h3>2. Map columns</h3><div class="ph-grid">${mappings}</div><div class="ph-actions"><div class="ph-field"><label for="ph-mapping-name">Save mapping as</label><input id="ph-mapping-name" pattern="[a-z][a-z0-9_]*" placeholder="monthly_cases"></div><button type="button" data-save-mapping>Save mapping</button></div></div><div class="ph-import-step"><h3>3. Review ${response.data.total_rows} rows</h3><div class="ph-table-wrap"><table class="ph-table"><thead><tr>${headers}</tr></thead><tbody>${rows}</tbody></table></div><div class="ph-actions"><button class="ph-button" type="button" data-validate>Validate</button><button class="ph-button" type="button" data-import>Import atomically</button></div></div><div data-results></div>`;
      this.querySelector("[data-save-mapping]").addEventListener("click", () => this.saveMapping());
      this.querySelector("[data-validate]").addEventListener("click", () => this.execute(true));
      this.querySelector("[data-import]").addEventListener("click", () => this.execute(false));
      status.textContent = "Preview ready. Confirm the column mapping.";
    } catch (error) { status.textContent = error.message; status.className = "ph-status ph-error"; }
  }
  async execute(dryRun) {
    const dataset = this.querySelector("#ph-import-dataset").value;
    const mapping = this.currentMapping();
    const query = new URLSearchParams({ mapping: JSON.stringify(mapping), dry_run: String(dryRun) });
    const results = this.querySelector("[data-results]");
    try {
      const response = await this.upload(`/api/browser-import/${dataset}?${query}`);
      const item = response.data;
      results.innerHTML = `<div class="ph-card" role="status"><h3>${dryRun ? "Validation passed" : "Import completed"}</h3><p>${item.imported_rows} imported / ${item.total_rows} total rows. Run ${item.run_id}.</p></div>`;
      if (!dryRun) PHFrame.notify("Import completed.");
    } catch (error) {
      const errors = error.payload?.data?.errors || [];
      results.innerHTML = `<div class="ph-error" role="alert"><h3>Import validation failed</h3><ul class="ph-error-list">${errors.map(item => `<li>Row ${item.row}: ${PHFrame.escape(item.message)}</li>`).join("") || `<li>${PHFrame.escape(error.message)}</li>`}</ul></div>`;
    }
  }
  currentMapping() {
    return Object.fromEntries([...this.querySelectorAll("[data-source]")].map(select => [select.dataset.source, select.value]).filter(([, target]) => target));
  }
  async saveMapping() {
    const name = this.querySelector("#ph-mapping-name").value;
    if (!name) return PHFrame.notify("Enter a mapping name.");
    try {
      await PHFrame.send(`/api/import-mappings/${name}`, "PUT", {
        dataset: this.querySelector("#ph-import-dataset").value, mapping: this.currentMapping()
      });
      PHFrame.notify(`Mapping ${name} saved.`);
    } catch (error) { PHFrame.notify(error.message); }
  }
}

class PHDataBuilder extends PHElement {
  set metadata(value) { this._metadata = value; if (this.isConnected) this.render(); }
  render() {
    if (!this._metadata) return;
    const datasets = Object.entries(this._metadata.datasets).map(([name, item]) => `<option value="${name}">${PHFrame.escape(item.label)}</option>`).join("");
    const types = (this._metadata.field_types || ["string", "integer", "number", "boolean", "date", "datetime", "location"]).map(type => `<option value="${type}">${PHFrame.escape(type.replaceAll("_", " "))}</option>`).join("");
    this.innerHTML = `<div class="ph-builder-workspace"><aside class="ph-workspace-sidebar"><div><p class="ph-eyebrow">Data model</p><h3>Schema builder</h3><p>Manage typed columns used across forms, imports, APIs, and charts.</p></div><nav aria-label="Schema actions"><button type="button" class="ph-workspace-tab-active" data-builder-tab="schema"><span>▤</span><b>Dataset schema</b><small>Review fields and types</small></button><button type="button" data-builder-tab="add"><span>＋</span><b>Add a field</b><small>Extend this dataset</small></button></nav><div class="ph-builder-tip"><b>Why types matter</b><small>Field types control validation and recommend compatible visualizations.</small></div></aside><div class="ph-builder-content"><section class="ph-card" data-builder-panel="schema"><header class="ph-schema-header"><div><p class="ph-eyebrow">Schema</p><h3>Dataset fields</h3><p class="ph-muted">Review the structure currently available to PHFrame.</p></div><div class="ph-field"><label for="ph-builder-dataset">Dataset</label><select id="ph-builder-dataset">${datasets}</select></div></header><label class="ph-schema-search"><span class="ph-sr-only">Search fields</span><input type="search" data-field-search placeholder="Search field name, label, or type…"></label><div data-fields></div></section><section class="ph-card ph-add-field-panel" data-builder-panel="add" hidden><div><p class="ph-eyebrow">Add field</p><h3>Define a new column</h3><p class="ph-muted">Choose a stable machine name, a readable label, and the type that best represents the data.</p></div><form class="ph-stack"><div class="ph-form-grid"><div class="ph-field"><label for="ph-field-name">Column name</label><input id="ph-field-name" name="name" required pattern="[a-z][a-z0-9_]*" placeholder="country_code"><small>Lowercase letters, numbers, and underscores</small></div><div class="ph-field"><label for="ph-field-label">Display label</label><input id="ph-field-label" name="label" placeholder="Country code"><small>Shown to people in forms and tables</small></div></div><div class="ph-field"><label for="ph-field-type">Data type</label><select id="ph-field-type" name="type">${types}</select><small>Select the semantic type used for validation and visualization suggestions.</small></div><div class="ph-form-footer"><p role="status" class="ph-status"></p><button class="ph-button" type="submit">Add field to dataset</button></div></form></section></div></div>`;
    this.querySelector("#ph-builder-dataset").addEventListener("change", () => this.drawFields());
    this.querySelector("[data-field-search]").addEventListener("input", event => { this.fieldSearch = event.target.value; this.drawFields(); });
    this.querySelectorAll("[data-builder-tab]").forEach(button => button.addEventListener("click", () => { this.querySelectorAll("[data-builder-tab]").forEach(item => item.classList.toggle("ph-workspace-tab-active", item === button)); this.querySelectorAll("[data-builder-panel]").forEach(panel => panel.hidden = panel.dataset.builderPanel !== button.dataset.builderTab); }));
    this.querySelector("form").addEventListener("submit", event => this.addField(event));
    this.drawFields();
  }
  drawFields() {
    const dataset = this.querySelector("#ph-builder-dataset").value;
    const fields = this._metadata.datasets[dataset].fields;
    const search = (this.fieldSearch || "").toLowerCase(), entries = Object.entries(fields).filter(([name, schema]) => !search || `${name} ${schema.label || ""} ${schema.type}`.toLowerCase().includes(search));
    const required = entries.filter(([, schema]) => schema.required).length;
    this.querySelector("[data-fields]").innerHTML = `<div class="ph-schema-summary"><div><b>${Object.keys(fields).length}</b><span>Total fields</span></div><div><b>${required}</b><span>Required</span></div><div><b>${new Set(Object.values(fields).map(item => item.type)).size}</b><span>Data types</span></div></div><div class="ph-field-list ph-schema-fields">${entries.map(([name, schema]) => `<div><span class="ph-type-badge">${PHFrame.escape(schema.type)}</span><span><b>${PHFrame.escape(schema.label || name.replaceAll("_", " "))}</b><small>${schema.required ? "Required field" : "Optional field"}</small></span><code>${PHFrame.escape(name)}</code></div>`).join("") || `<div class="ph-table-empty">No fields match your search.</div>`}</div>`;
  }
  async addField(event) {
    event.preventDefault();
    const form = event.currentTarget, status = form.querySelector("[role=status]");
    const dataset = this.querySelector("#ph-builder-dataset").value;
    try {
      const payload = Object.fromEntries(new FormData(form));
      const response = await PHFrame.send(`/api/project/datasets/${dataset}/fields`, "POST", payload);
      this._metadata.datasets[dataset].fields[response.data.name] = response.data;
      status.textContent = `Column ${response.data.name} added and database updated.`;
      form.reset(); this.drawFields(); PHFrame.notify("Custom column added.");
    } catch (error) { status.textContent = error.message; status.className = "ph-status ph-error"; }
  }
}

class PHRichEditor extends PHElement {
  set value(value) { this._value = value || ""; if (this.isConnected) this.render(); }
  get value() { return this.querySelector("[contenteditable]")?.innerHTML || ""; }
  render() {
    this.innerHTML = `<div class="ph-editor-toolbar" aria-label="Text formatting"><button type="button" data-block="h2">Heading</button><button type="button" data-block="p">Paragraph</button><button type="button" data-command="bold"><b>B</b></button><button type="button" data-command="italic"><i>I</i></button><button type="button" data-command="underline"><u>U</u></button><button type="button" data-command="insertUnorderedList">• List</button><button type="button" data-link>Link</button></div><div class="ph-rich-editor" contenteditable="true" role="textbox" aria-multiline="true">${this._value || ""}</div>`;
    this.querySelectorAll("[data-command]").forEach(button => button.addEventListener("click", () => { document.execCommand(button.dataset.command); this.querySelector("[contenteditable]").focus(); }));
    this.querySelectorAll("[data-block]").forEach(button => button.addEventListener("click", () => { document.execCommand("formatBlock", false, button.dataset.block); this.querySelector("[contenteditable]").focus(); }));
    this.querySelector("[data-link]").addEventListener("click", () => { const url = prompt("Enter an https:// link"); if (url && /^https?:\/\//i.test(url)) document.execCommand("createLink", false, url); });
  }
}

class PHSettingsPanel extends PHElement {
  set settings(value) { this._settings = value; if (this.isConnected) this.render(); }
  render() {
    if (!this._settings) return;
    const navigation = Object.entries(this._settings.navigation).map(([route, item]) => `<div class="ph-nav-setting"><label><input type="checkbox" name="nav_visible_${route}" ${item.visible ? "checked" : ""}> Show</label><div class="ph-field"><label for="ph-nav-${route}">${PHFrame.escape(route)}</label><input id="ph-nav-${route}" name="nav_label_${route}" value="${PHFrame.escape(item.label)}"></div></div>`).join("");
    this.innerHTML = `<form class="ph-settings-grid"><section class="ph-card ph-stack"><div><p class="ph-eyebrow">Identity</p><h3>Brand and header</h3></div><div class="ph-field"><label>Brand name</label><input name="brand_name" value="${PHFrame.escape(this._settings.brand_name)}"></div><div class="ph-field"><label>Header title</label><input name="header_title" value="${PHFrame.escape(this._settings.header_title)}"></div><div class="ph-field"><label>Dashboard title</label><input name="dashboard_title" value="${PHFrame.escape(this._settings.dashboard_title)}" placeholder="Use configured dashboard title"></div><div class="ph-form-grid"><div class="ph-field"><label>Logo</label><input type="file" name="logo" accept=".png,.jpg,.jpeg,.webp"></div><div class="ph-field"><label>Favicon</label><input type="file" name="favicon" accept=".png,.jpg,.jpeg,.webp,.ico"></div></div></section><section class="ph-card ph-stack"><div><p class="ph-eyebrow">Appearance</p><h3>Colors and theme</h3></div><div class="ph-color-setting"><input name="primary_color_picker" type="color" value="${PHFrame.escape(this._settings.primary_color)}" aria-label="Primary color picker"><div class="ph-field"><label>Primary color code</label><input name="primary_color" value="${PHFrame.escape(this._settings.primary_color)}" pattern="#[0-9a-fA-F]{6}"></div></div><div class="ph-field"><label>Default theme</label><select name="default_theme"><option value="light">Light</option><option value="dark">Dark</option><option value="high-contrast">High contrast</option></select></div><label><input type="checkbox" name="show_footer" ${this._settings.show_footer ? "checked" : ""}> Show footer</label><div class="ph-field"><label>Footer content</label><ph-rich-editor data-footer-editor></ph-rich-editor></div></section><section class="ph-card ph-stack"><div><p class="ph-eyebrow">Navigation</p><h3>Menu labels and visibility</h3></div><div class="ph-nav-settings">${navigation}</div></section><section class="ph-card ph-stack"><div><p class="ph-eyebrow">Access</p><h3>Public or private mode</h3></div><div class="ph-field"><label>Access mode</label><select name="access_mode"><option value="public">Public — no login required</option><option value="private">Private — login required</option></select></div><p class="ph-muted">Create or update a login when enabling private mode. Passwords are securely hashed and never returned by the API.</p><div class="ph-form-grid"><div class="ph-field"><label>Username</label><input name="username" autocomplete="username" placeholder="admin"></div><div class="ph-field"><label>New password</label><input name="password" type="password" minlength="10" autocomplete="new-password" placeholder="At least 10 characters"></div></div></section><section class="ph-card ph-stack"><div><p class="ph-eyebrow">Responsible AI</p><h3>Provider and privacy boundary</h3></div><p class="ph-provider-guide"><b>Local is the safe default.</b><span>Only configured aggregates are used. Protected fields and row-level records are never included in summary requests.</span></p><div class="ph-field"><label>AI provider</label><select name="ai_provider"><option value="local">Local evidence synthesis</option><option value="openai_compatible">External OpenAI-compatible API</option></select></div><div class="ph-field"><label>Model</label><input name="ai_model" value="${PHFrame.escape(this._settings.ai_model)}"></div><div class="ph-field"><label>HTTPS chat-completions endpoint</label><input name="ai_endpoint" type="url" value="${PHFrame.escape(this._settings.ai_endpoint)}" placeholder="https://provider.example/v1/chat/completions"></div><div class="ph-field"><label>API key environment-variable name</label><input name="ai_api_key_env" value="${PHFrame.escape(this._settings.ai_api_key_env)}" placeholder="PHFRAME_AI_API_KEY"></div><label><input type="checkbox" name="allow_external_ai" ${this._settings.allow_external_ai ? "checked" : ""}> I explicitly allow aggregate evidence to leave this server</label></section><div class="ph-settings-save"><button class="ph-button" type="submit">Save system settings</button><p role="status" class="ph-status"></p></div></form>`;
    this.querySelector(".ph-settings-save").insertAdjacentHTML("beforebegin", `<section class="ph-card ph-stack ph-boundary-settings"><div><p class="ph-eyebrow">Geographic maps</p><h3>Basemap and country boundaries</h3></div><div class="ph-field"><label>Default basemap</label><select name="basemap"><option value="carto-light">CARTO Light</option><option value="openstreetmap">OpenStreetMap</option><option value="carto-dark">CARTO Dark</option><option value="esri-imagery">Esri World Imagery</option></select><small>Used behind choropleth and geographic layers.</small></div><hr><p class="ph-muted">Download open administrative boundaries for real choropleth maps. Use ISO3 codes such as BGD, USA, GBR, or KEN.</p><div class="ph-form-grid"><div class="ph-field"><label>Country ISO3</label><input data-boundary-country maxlength="3" pattern="[A-Za-z]{3}" placeholder="BGD"></div><div class="ph-field"><label>Administrative level</label><select data-boundary-level><option>ADM0</option><option>ADM1</option><option selected>ADM2</option><option>ADM3</option><option>ADM4</option><option>ADM5</option></select></div></div><button class="ph-button" type="button" data-boundary-download>Download boundary layer</button><p class="ph-status" role="status" data-boundary-status></p><div data-boundary-list></div><small class="ph-muted">Boundary data: geoBoundaries gbOpen, CC BY 4.0. Attribution is required.</small></section>`);
    this.querySelector(".ph-settings-save").insertAdjacentHTML("beforebegin", `<section class="ph-card ph-stack ph-cloudflare-settings"><div><p class="ph-eyebrow">Public dashboard hosting</p><h3>Cloudflare Pages</h3></div><p class="ph-muted">Connect once, approve access on Cloudflare, and return here automatically. OAuth credentials are encrypted and never shown in PHFrame.</p><div class="ph-cloudflare-connection" data-cloudflare-connection><p class="ph-muted">Checking Cloudflare connection…</p></div><div class="ph-field"><label>Default Pages project name</label><input name="cloudflare_project_name" value="${PHFrame.escape(this._settings.cloudflare_project_name || "")}" pattern="[a-z0-9][a-z0-9-]*[a-z0-9]|[a-z0-9]" placeholder="my-public-health-dashboard"></div><details><summary>Advanced API-token fallback</summary><div class="ph-stack ph-settings-advanced"><div class="ph-field"><label>Cloudflare account ID</label><input name="cloudflare_account_id" value="${PHFrame.escape(this._settings.cloudflare_account_id || "")}" autocomplete="off"></div><div class="ph-field"><label>API token environment variable</label><input name="cloudflare_token_env" value="${PHFrame.escape(this._settings.cloudflare_token_env || "CLOUDFLARE_API_TOKEN")}" pattern="[A-Z_][A-Z0-9_]*"></div><p class="ph-muted">Only use this fallback when this server has no OAuth client configured.</p></div></details><div data-publication-history><p class="ph-muted">Loading publication history…</p></div></section>`);
    this.setupSettingsNavigation();
    const countryInput = this.querySelector("[data-boundary-country]"); countryInput.setAttribute("list", "ph-boundary-countries"); countryInput.removeAttribute("maxlength"); countryInput.removeAttribute("pattern"); countryInput.placeholder = "Search country name or ISO3"; countryInput.insertAdjacentHTML("afterend", `<datalist id="ph-boundary-countries"></datalist><small data-country-help>Start typing a country name or three-letter code.</small>`);
    this.querySelector('[name="default_theme"]').value = this._settings.default_theme;
    this.querySelector('[name="basemap"]').value = this._settings.basemap || "carto-light";
    this.querySelector('[name="access_mode"]').value = this._settings.access_mode;
    this.querySelector('[name="ai_provider"]').value = this._settings.ai_provider;
    this.querySelector("[data-footer-editor]").value = this._settings.footer_html;
    const picker = this.querySelector('[name="primary_color_picker"]'), code = this.querySelector('[name="primary_color"]');
    picker.addEventListener("input", () => code.value = picker.value); code.addEventListener("input", () => { if (/^#[0-9a-f]{6}$/i.test(code.value)) picker.value = code.value; });
    this.querySelector("form").addEventListener("submit", event => this.save(event));
    this.querySelector("[data-boundary-download]").addEventListener("click", () => this.downloadBoundary());
    this.loadBoundaries(); this.loadBoundaryCountries(); this.loadCloudflare(); this.loadPublications();
  }
  setupSettingsNavigation() {
    const form = this.querySelector("form"), panels = [...form.querySelectorAll(":scope > section")];
    const icons = ["◈", "◐", "☰", "◉", "✦", "◎", "☁"];
    panels.forEach((panel, index) => { panel.id = `ph-settings-panel-${index}`; panel.dataset.settingsPanel = String(index); panel.setAttribute("role", "tabpanel"); panel.setAttribute("aria-labelledby", `ph-settings-tab-${index}`); });
    const tabs = panels.map((panel, index) => { const title = panel.querySelector("h3")?.textContent || `Settings ${index + 1}`, group = panel.querySelector(".ph-eyebrow")?.textContent || "Settings"; return `<button type="button" id="ph-settings-tab-${index}" role="tab" aria-controls="${panel.id}" data-settings-tab="${index}"><span class="ph-settings-tab-icon">${icons[index] || "•"}</span><span><small>${PHFrame.escape(group)}</small><b>${PHFrame.escape(title)}</b></span><span class="ph-settings-tab-arrow">›</span></button>`; }).join("");
    form.insertAdjacentHTML("afterbegin", `<aside class="ph-settings-sidebar"><div class="ph-settings-sidebar-heading"><p class="ph-eyebrow">System configuration</p><h3>Settings</h3><p>Choose an area to customize.</p></div><nav role="tablist" aria-label="Settings sections">${tabs}</nav></aside>`);
    const saved = Number(sessionStorage.getItem("ph-settings-tab") || 0), initial = saved >= 0 && saved < panels.length ? saved : 0;
    const activate = index => { panels.forEach((panel, panelIndex) => { const selected = panelIndex === index; panel.hidden = !selected; }); form.querySelectorAll("[data-settings-tab]").forEach((tab, tabIndex) => { const selected = tabIndex === index; tab.classList.toggle("ph-settings-tab-active", selected); tab.setAttribute("aria-selected", String(selected)); tab.tabIndex = selected ? 0 : -1; }); sessionStorage.setItem("ph-settings-tab", String(index)); };
    form.querySelectorAll("[data-settings-tab]").forEach((tab, index) => { tab.addEventListener("click", () => activate(index)); tab.addEventListener("keydown", event => { if (!["ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return; event.preventDefault(); const forward = ["ArrowDown", "ArrowRight"].includes(event.key), next = event.key === "Home" ? 0 : (event.key === "End" ? panels.length - 1 : (index + (forward ? 1 : -1) + panels.length) % panels.length); activate(next); form.querySelector(`[data-settings-tab="${next}"]`).focus(); }); });
    activate(initial);
  }
  async loadBoundaryCountries() { const list = this.querySelector("#ph-boundary-countries"), help = this.querySelector("[data-country-help]"); try { const response = await PHFrame.get("/api/boundaries/countries"); this.boundaryCountries = response.data; list.innerHTML = response.data.map(country => `<option value="${PHFrame.escape(country.iso3)}">${PHFrame.escape(country.name)}</option>`).join(""); help.textContent = `${response.data.length} countries available. Search by name or ISO3 code.`; } catch (error) { help.textContent = `Country list unavailable: ${error.message}. You can still enter an ISO3 code.`; } }
  async loadBoundaries() { const host = this.querySelector("[data-boundary-list]"); try { const response = await PHFrame.get("/api/boundaries"); host.innerHTML = response.data.length ? `<div class="ph-field-list">${response.data.map(item => `<div><span class="ph-type-badge">${PHFrame.escape(item.level)}</span><b>${PHFrame.escape(item.country)}</b><code>${PHFrame.escape(item.id)} · ${item.feature_count} areas</code></div>`).join("")}</div>` : `<p class="ph-muted">No boundary layers installed yet.</p>`; } catch (error) { host.innerHTML = `<p class="ph-error">${PHFrame.escape(error.message)}</p>`; } }
  async loadPublications() { const host = this.querySelector("[data-publication-history]"); try { const response = await PHFrame.get("/api/publications"); host.innerHTML = response.data.length ? `<h4>Recent publications</h4><div class="ph-field-list">${response.data.slice(0, 5).map(item => `<div><span class="ph-type-badge">${PHFrame.escape(item.mode)}</span><a href="${PHFrame.escape(item.url)}" target="_blank" rel="noopener"><b>${PHFrame.escape(item.project_name)}</b></a><code>${PHFrame.escape(new Date(item.published_at).toLocaleString())}</code></div>`).join("")}</div>` : `<p class="ph-muted">No dashboards published yet. Use <b>Publish dashboard</b> on the Dashboard screen.</p>`; } catch (error) { host.innerHTML = `<p class="ph-error">${PHFrame.escape(error.message)}</p>`; } }
  async loadCloudflare() { const host = this.querySelector("[data-cloudflare-connection]"); try { const { data } = await PHFrame.get("/api/integrations/cloudflare/status"); if (!data.available && !data.connected) { host.innerHTML = `<div class="ph-provider-guide"><b>OAuth setup required on this server</b><span>Set <code>PHFRAME_CLOUDFLARE_CLIENT_ID</code>, <code>PHFRAME_CLOUDFLARE_CLIENT_SECRET</code>, and the registered redirect URI, then restart PHFrame.</span></div>`; return; } if (!data.connected) { host.innerHTML = `<button type="button" class="ph-button" data-cloudflare-connect>☁ Connect with Cloudflare</button><small class="ph-muted">You will be redirected to Cloudflare to approve Pages access.</small>`; host.querySelector("[data-cloudflare-connect]").addEventListener("click", () => location.href = "/api/integrations/cloudflare/connect"); return; } const options = data.accounts.map(account => `<option value="${PHFrame.escape(account.id)}" ${account.id === data.account.id ? "selected" : ""}>${PHFrame.escape(account.name)} · ${PHFrame.escape(account.id)}</option>`).join(""); host.innerHTML = `<div class="ph-cloudflare-connected"><span class="ph-status-dot"></span><div><b>Cloudflare connected</b><small>Authorized securely with OAuth</small></div></div><div class="ph-field"><label>Publishing account</label><select data-cloudflare-account>${options}</select></div><button type="button" class="ph-button ph-button-secondary" data-cloudflare-disconnect>Disconnect Cloudflare</button>`; host.querySelector("[data-cloudflare-account]").addEventListener("change", async event => { await PHFrame.send("/api/integrations/cloudflare/account", "PUT", { account_id: event.target.value }); PHFrame.notify("Cloudflare account updated."); }); host.querySelector("[data-cloudflare-disconnect]").addEventListener("click", async () => { if (!confirm("Disconnect Cloudflare from PHFrame?")) return; await PHFrame.send("/api/integrations/cloudflare/disconnect", "POST", {}); await this.loadCloudflare(); }); } catch (error) { host.innerHTML = `<p class="ph-error">${PHFrame.escape(error.message)}</p>`; } }
  async downloadBoundary() { const status = this.querySelector("[data-boundary-status]"), button = this.querySelector("[data-boundary-download]"), entered = this.querySelector("[data-boundary-country]").value.trim(), match = (this.boundaryCountries || []).find(country => country.iso3 === entered.toUpperCase() || country.name.toLowerCase() === entered.toLowerCase()), iso3 = (match?.iso3 || entered).toUpperCase(), level = this.querySelector("[data-boundary-level]").value; if (!/^[A-Z]{3}$/.test(iso3)) { status.textContent = "Select a country from the searchable list."; return; } button.disabled = true; status.textContent = `Downloading ${iso3} ${level}…`; try { const response = await PHFrame.send("/api/boundaries", "POST", { iso3, level }); status.textContent = `${response.data.country} ${level} installed with ${response.data.feature_count} areas.`; await this.loadBoundaries(); PHFrame.notify("Boundary layer installed."); } catch (error) { status.textContent = error.message; status.className = "ph-status ph-error"; } finally { button.disabled = false; } }
  async upload(kind, file) {
    if (!file?.size) return;
    const response = await fetch(`/api/settings/assets/${kind}?filename=${encodeURIComponent(file.name)}`, { method: "POST", headers: { "content-type": "application/octet-stream", accept: "application/json" }, body: file });
    if (!response.ok) throw new Error((await response.json()).error?.message || `${kind} upload failed.`);
  }
  async save(event) {
    event.preventDefault(); const form = event.currentTarget, status = form.querySelector(".ph-settings-save [role=status]"), data = new FormData(form);
    try {
      await this.upload("logo", data.get("logo")); await this.upload("favicon", data.get("favicon"));
      const navigation = Object.fromEntries(Object.keys(this._settings.navigation).map(route => [route, { label: String(data.get(`nav_label_${route}`) || route), visible: data.has(`nav_visible_${route}`) }]));
      const payload = { brand_name: data.get("brand_name"), header_title: data.get("header_title"), dashboard_title: data.get("dashboard_title"), primary_color: data.get("primary_color"), default_theme: data.get("default_theme"), basemap: data.get("basemap"), footer_html: this.querySelector("[data-footer-editor]").value, show_footer: data.has("show_footer"), access_mode: data.get("access_mode"), navigation, username: data.get("username"), password: data.get("password"), ai_provider: data.get("ai_provider"), ai_model: data.get("ai_model"), ai_endpoint: data.get("ai_endpoint"), ai_api_key_env: data.get("ai_api_key_env"), allow_external_ai: data.has("allow_external_ai"), cloudflare_account_id: data.get("cloudflare_account_id"), cloudflare_project_name: data.get("cloudflare_project_name"), cloudflare_token_env: data.get("cloudflare_token_env") };
      await PHFrame.send("/api/settings", "PUT", payload); status.textContent = "Settings saved. Reloading…"; localStorage.removeItem("ph-theme"); setTimeout(() => location.reload(), 500);
    } catch (error) { status.textContent = error.message; status.className = "ph-status ph-error"; }
  }
}

class PHPageTable extends PHElement {
  async render() {
    try {
      const dataset = this.getAttribute("dataset"), response = await PHFrame.get(`/api/${dataset}?limit=20`), schema = PHFrame.appMetadata.datasets[dataset];
      const columns = Object.keys(schema.fields).filter(name => !schema.fields[name].protected);
      this.innerHTML = `<div class="ph-table-wrap"><table class="ph-table"><thead><tr>${columns.map(name => `<th>${PHFrame.escape(schema.fields[name].label || name)}</th>`).join("")}</tr></thead><tbody>${response.data.map(row => `<tr>${columns.map(name => `<td>${PHFrame.escape(row[name] ?? "—")}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${columns.length}">No records yet.</td></tr>`}</tbody></table></div>`;
    } catch (error) { this.innerHTML = `<p class="ph-error">${PHFrame.escape(error.message)}</p>`; }
  }
}

class PHCustomPage extends PHElement {
  set settings(value) { this._settings = value; if (this.isConnected) this.render(); }
  render() {
    if (!this._settings) return;
    const page = (this._settings.pages || []).find(item => item.slug === this.getAttribute("slug"));
    if (!page) { this.innerHTML = `<h2>Page not found</h2>`; return; }
    const blocks = page.blocks.map(block => `<article class="ph-card ph-page-block">${block.title ? `<h3>${PHFrame.escape(block.title)}</h3>` : ""}${this.block(block)}</article>`).join("");
    this.innerHTML = `<header class="ph-page-heading"><p class="ph-eyebrow">Custom page</p><h2>${PHFrame.escape(page.title)}</h2></header><div class="ph-page-grid">${blocks}</div>`;
  }
  block(block) {
    if (block.type === "text") return `<div class="ph-prose">${block.html}</div>`;
    if (block.type === "table") return `<ph-page-table dataset="${PHFrame.escape(block.dataset)}"></ph-page-table>`;
    const [type, ...parts] = block.source.split("|");
    if (type === "kpi") return `<ph-kpi indicator="${parts[0]}"></ph-kpi>`;
    if (type === "field_kpi") return `<ph-kpi dataset="${parts[0]}" field="${parts[1]}" operation="sum"></ph-kpi>`;
    if (type === "chart") return `<ph-indicator-chart dimension="${parts[0]}"></ph-indicator-chart>`;
    if (type === "field_chart") return `<ph-indicator-chart dataset="${parts[0]}" field="${parts[1]}"></ph-indicator-chart>`;
    return `<ph-epi-curve dataset="${parts[0]}" date-field="${parts[1]}" value-field="${parts[2] || ""}"></ph-epi-curve>`;
  }
}

class PHPageBuilder extends PHElement {
  set settings(value) { this._settings = value; if (this.isConnected) this.render(); }
  set metadata(value) { this._metadata = value; PHFrame.appMetadata = value; if (this.isConnected) this.render(); }
  render() {
    if (!this._settings || !this._metadata) return;
    const pages = (this._settings.pages || []).map(page => `<article class="ph-card ph-page-list-card"><div class="ph-widget-header"><div><p class="ph-eyebrow">${page.type === "internal" ? "Custom page" : "External link"}</p><h3>${PHFrame.escape(page.title)}</h3><p class="ph-muted">${page.type === "external" ? PHFrame.escape(page.url) : `${page.blocks.length} content block${page.blocks.length === 1 ? "" : "s"} · /${PHFrame.escape(page.slug)}`}</p></div><button class="ph-icon-danger" data-delete-page="${PHFrame.escape(page.slug)}" aria-label="Delete ${PHFrame.escape(page.title)}">×</button></div><div class="ph-actions">${page.type === "internal" ? `<button class="ph-button ph-button-secondary" data-edit-page="${PHFrame.escape(page.slug)}">Customize page</button><a class="ph-button ph-button-secondary" href="#/page/${PHFrame.escape(page.slug)}">View page</a>` : `<a class="ph-button ph-button-secondary" href="${PHFrame.escape(page.url)}" target="_blank" rel="noopener noreferrer">Open link ↗</a>`}</div></article>`).join("") || `<div class="ph-empty-state"><span>＋</span><h3>No pages yet</h3><p>Create a drag-and-drop page or add an external navigation link.</p><button class="ph-button" type="button" data-empty-create>Create first page</button></div>`;
    this.innerHTML = `<div class="ph-pages-workspace"><aside class="ph-pages-sidebar"><div class="ph-pages-sidebar-heading"><p class="ph-eyebrow">Page workspace</p><h3>Pages</h3><p>Create and manage navigation content.</p></div><nav role="tablist" aria-label="Page builder sections"><button type="button" role="tab" data-page-tab="create"><span>＋</span><span><small>Build</small><b>Create page</b></span><i>›</i></button><button type="button" role="tab" data-page-tab="all"><span>▦</span><span><small>Manage</small><b>All pages</b></span><i>›</i></button><button type="button" role="tab" data-page-tab="customize"><span>✦</span><span><small>Design</small><b>Customize page</b></span><i>›</i></button></nav></aside><section class="ph-card ph-stack ph-page-workspace-panel" data-page-panel="create"><div class="ph-page-panel-heading"><p class="ph-eyebrow">Navigation page</p><h3>Create a page or link</h3><p class="ph-muted">Build a flexible content page or send visitors to a trusted external website.</p></div><form class="ph-stack" data-page-form><div class="ph-form-grid"><div class="ph-field"><label>Page title</label><input name="title" required placeholder="Programme overview"></div><div class="ph-field"><label>Navigation label</label><input name="nav_label" required placeholder="Overview"></div></div><div class="ph-form-grid"><div class="ph-field"><label>Slug</label><input name="slug" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" placeholder="programme-overview"><small>Used in the page URL.</small></div><div class="ph-field"><label>Page type</label><select name="type"><option value="internal">Drag-and-drop page</option><option value="external">External URL redirect</option></select></div></div><div class="ph-field" data-page-url hidden><label>External URL</label><input name="url" type="url" placeholder="https://example.org"><small>Only required for an external redirect.</small></div><div class="ph-actions"><button class="ph-button">Create page</button><button class="ph-button ph-button-secondary" type="reset">Clear</button></div><p role="status" class="ph-status"></p></form></section><section class="ph-page-workspace-panel" data-page-panel="all"><div class="ph-page-panel-heading"><p class="ph-eyebrow">Page library</p><h3>All pages</h3><p class="ph-muted">${(this._settings.pages || []).length} page${(this._settings.pages || []).length === 1 ? "" : "s"} connected to navigation.</p></div><div class="ph-page-list">${pages}</div></section><section class="ph-page-workspace-panel" data-page-panel="customize"><div data-page-designer><div class="ph-empty-state"><span>✦</span><h3>Select a page to customize</h3><p>Open All pages and choose Customize page to edit text, tables, and visualizations.</p><button class="ph-button ph-button-secondary" type="button" data-open-pages>Browse pages</button></div></div></section></div>`;
    const form = this.querySelector("[data-page-form]"), type = form.querySelector('[name="type"]'), url = form.querySelector('[name="url"]');
    const toggleUrl = () => { const external = type.value === "external"; this.querySelector("[data-page-url]").hidden = !external; url.required = external; if (!external) url.value = ""; };
    type.addEventListener("change", toggleUrl); form.addEventListener("reset", () => setTimeout(toggleUrl)); toggleUrl(); form.addEventListener("submit", event => this.create(event));
    const title = form.querySelector('[name="title"]'), navLabel = form.querySelector('[name="nav_label"]'), slug = form.querySelector('[name="slug"]'); let slugEdited = false;
    slug.addEventListener("input", () => slugEdited = Boolean(slug.value)); title.addEventListener("input", () => { if (!navLabel.value) navLabel.value = title.value; if (!slugEdited) slug.value = title.value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); });
    this.setupPageNavigation();
    this.querySelectorAll("[data-edit-page]").forEach(button => button.addEventListener("click", () => this.design(button.dataset.editPage)));
    this.querySelectorAll("[data-delete-page]").forEach(button => button.addEventListener("click", () => this.remove(button.dataset.deletePage)));
    this.querySelector("[data-empty-create]")?.addEventListener("click", () => this.activatePagePanel("create"));
    this.querySelector("[data-open-pages]")?.addEventListener("click", () => this.activatePagePanel("all"));
  }
  setupPageNavigation() { this.querySelectorAll("[data-page-tab]").forEach(tab => tab.addEventListener("click", () => this.activatePagePanel(tab.dataset.pageTab))); this.activatePagePanel(sessionStorage.getItem("ph-pages-tab") || "all"); }
  activatePagePanel(name) { if (!this.querySelector(`[data-page-panel="${name}"]`)) name = "all"; this.querySelectorAll("[data-page-panel]").forEach(panel => panel.hidden = panel.dataset.pagePanel !== name); this.querySelectorAll("[data-page-tab]").forEach(tab => { const active = tab.dataset.pageTab === name; tab.classList.toggle("ph-page-tab-active", active); tab.setAttribute("aria-selected", String(active)); tab.tabIndex = active ? 0 : -1; }); sessionStorage.setItem("ph-pages-tab", name); }
  async persist(pages) {
    const response = await PHFrame.send("/api/settings", "PUT", { pages }); this._settings.pages = response.data.pages; PHFrame.siteSettings.pages = response.data.pages;
  }
  async create(event) {
    event.preventDefault(); const form = event.currentTarget, data = new FormData(form), status = form.querySelector("[role=status]");
    try { const page = { title: data.get("title"), nav_label: data.get("nav_label"), slug: data.get("slug"), type: data.get("type"), url: data.get("url") || "", blocks: [] }; await this.persist([...(this._settings.pages || []), page]); sessionStorage.setItem("ph-pages-tab", page.type === "internal" ? "customize" : "all"); this.render(); if (page.type === "internal") this.design(page.slug); PHFrame.notify("Page created."); } catch (error) { status.textContent = error.message; }
  }
  async remove(slug) { if (!confirm("Remove this page and its navigation item?")) return; await this.persist(this._settings.pages.filter(page => page.slug !== slug)); this.render(); }
  sourceOptions() {
    const metrics = Object.entries(this._metadata.indicators || {}).map(([name, item]) => `<option value="kpi|${name}">Metric · ${PHFrame.escape(item.label)}</option>`).join("");
    const dimensions = Object.entries(this._metadata.dimensions || {}).map(([name, item]) => `<option value="chart|${name}">Chart · ${PHFrame.escape(item.label)}</option>`).join("");
    const fields = Object.entries(this._metadata.datasets).flatMap(([dataset, item]) => Object.entries(item.fields).filter(([, field]) => !["date", "datetime"].includes(field.type)).map(([name, field]) => ["integer", "number", "age"].includes(field.type) ? `<option value="field_kpi|${dataset}|${name}">Sum · ${PHFrame.escape(field.label || name)}</option>` : `<option value="field_chart|${dataset}|${name}">Groups · ${PHFrame.escape(field.label || name)}</option>`)).join("");
    return metrics + dimensions + fields;
  }
  design(slug) {
    const page = this._settings.pages.find(item => item.slug === slug), datasets = Object.entries(this._metadata.datasets).map(([name, item]) => `<option value="${name}">${PHFrame.escape(item.label)}</option>`).join("");
    if (!page || page.type !== "internal") return;
    this.activatePagePanel("customize");
    const blocks = page.blocks.map(block => this.editorBlock(block, datasets)).join("");
    const designer = this.querySelector("[data-page-designer]"); designer.innerHTML = `<section class="ph-card ph-page-designer"><div class="ph-widget-header"><div><p class="ph-eyebrow">Page designer</p><h3>${PHFrame.escape(page.title)}</h3><p class="ph-muted">Drag blocks to reorder them, then save your changes.</p></div><button class="ph-button" data-save-page>Save page</button></div><div class="ph-form-grid ph-page-details"><div class="ph-field"><label>Page title</label><input data-page-title value="${PHFrame.escape(page.title)}" required></div><div class="ph-field"><label>Navigation label</label><input data-page-nav-label value="${PHFrame.escape(page.nav_label)}" required></div></div><div class="ph-actions ph-block-tools"><button type="button" data-add-block="text">+ Text</button><button type="button" data-add-block="table">+ Table</button><button type="button" data-add-block="visualization">+ Visualization</button></div><div class="ph-page-canvas" data-page-canvas>${blocks}</div></section>`;
    page.blocks.forEach(block => { const element = designer.querySelector(`[data-block-id="${CSS.escape(block.id)}"]`); if (block.type === "text") element.querySelector("ph-rich-editor").value = block.html; if (block.type === "table") element.querySelector("[data-block-dataset]").value = block.dataset; if (block.type === "visualization") element.querySelector("[data-block-source]").value = block.source; });
    designer.querySelector("[data-save-page]").addEventListener("click", () => this.saveDesign(page)); designer.querySelectorAll("[data-add-block]").forEach(button => button.addEventListener("click", () => this.addBlock(button.dataset.addBlock, datasets))); this.bindBlocks(); designer.querySelector("h3")?.focus();
  }
  editorBlock(block, datasets) {
    let editor = block.type === "text" ? `<ph-rich-editor data-block-html></ph-rich-editor>` : (block.type === "table" ? `<div class="ph-field"><label>Dataset</label><select data-block-dataset>${datasets}</select></div>` : `<div class="ph-field"><label>Visualization source</label><select data-block-source>${this.sourceOptions()}</select></div>`);
    return `<article class="ph-card ph-page-editor-block" draggable="true" data-block-id="${block.id}" data-block-type="${block.type}"><div class="ph-widget-header"><b>${block.type}</b><div><button type="button" data-block-move="up">↑</button><button type="button" data-block-move="down">↓</button><button type="button" data-remove-block>×</button></div></div><div class="ph-field"><label>Block title</label><input data-block-title value="${PHFrame.escape(block.title || "")}"></div>${editor}</article>`;
  }
  addBlock(type, datasets) { const block = { id: `block-${Date.now()}`, type, title: "", html: "<p>Write your content here…</p>", dataset: Object.keys(this._metadata.datasets)[0], source: `kpi|${Object.keys(this._metadata.indicators)[0] || ""}` }; this.querySelector("[data-page-canvas]").insertAdjacentHTML("beforeend", this.editorBlock(block, datasets)); const element = this.querySelector(`[data-block-id="${block.id}"]`); if (type === "text") element.querySelector("ph-rich-editor").value = block.html; this.bindBlocks(); }
  bindBlocks() {
    this.querySelectorAll(".ph-page-editor-block").forEach(block => {
      if (block.dataset.bound) return; block.dataset.bound = "true";
      block.querySelector("[data-remove-block]").addEventListener("click", () => block.remove());
      block.querySelectorAll("[data-block-move]").forEach(button => button.addEventListener("click", () => { const sibling = button.dataset.blockMove === "up" ? block.previousElementSibling : block.nextElementSibling; if (sibling) button.dataset.blockMove === "up" ? sibling.before(block) : sibling.after(block); }));
      block.addEventListener("dragstart", event => event.dataTransfer.setData("text/plain", block.dataset.blockId)); block.addEventListener("dragover", event => event.preventDefault()); block.addEventListener("drop", event => { event.preventDefault(); const source = this.querySelector(`[data-block-id="${CSS.escape(event.dataTransfer.getData("text/plain"))}"]`); if (source && source !== block) block.before(source); });
    });
  }
  async saveDesign(page) {
    const blocks = [...this.querySelectorAll(".ph-page-editor-block")].map(block => ({ id: block.dataset.blockId, type: block.dataset.blockType, title: block.querySelector("[data-block-title]").value, html: block.querySelector("[data-block-html]")?.value || "", dataset: block.querySelector("[data-block-dataset]")?.value || "", source: block.querySelector("[data-block-source]")?.value || "" }));
    const title = this.querySelector("[data-page-title]").value.trim(), navLabel = this.querySelector("[data-page-nav-label]").value.trim(); if (!title || !navLabel) { PHFrame.notify("Page title and navigation label are required."); return; }
    await this.persist(this._settings.pages.map(item => item.slug === page.slug ? { ...item, title, nav_label: navLabel, blocks } : item)); sessionStorage.setItem("ph-pages-tab", "customize"); this.render(); this.design(page.slug); PHFrame.notify("Page saved.");
  }
}

class PHConnectorConsole extends PHElement {
  async render() {
    this.innerHTML = `<section class="ph-dashboard-loading">${PHFrame.loading("Loading connector workspace")}</section>`;
    try {
      const [connectors, history, dhis2] = await Promise.all([PHFrame.get("/api/connectors"), PHFrame.get("/api/syncs"), PHFrame.get("/api/integrations/dhis2/status")]);
      this.dhis2Status = dhis2.data;
      const metadata = await PHFrame.get("/api");
      const cards = connectors.data.map(item => `<article class="ph-card"><div class="ph-widget-header"><div><p class="ph-eyebrow">${item.type.toUpperCase()}</p><h3>${PHFrame.escape(item.name)}</h3></div><button class="ph-icon-danger" data-delete="${item.name}" aria-label="Remove ${PHFrame.escape(item.name)}">×</button></div><p>Feeds <b>${PHFrame.escape(item.dataset)}</b></p><p class="ph-muted">${item.schedule_minutes ? `Every ${item.schedule_minutes} minutes · ${item.due ? "Due" : "Not due"}` : "Manual schedule"}</p><div class="ph-actions"><button class="ph-button ph-button-secondary" data-sync="${item.name}" data-dry="true">Test connection</button><ph-confirm label="Sync now" message="Pull and atomically import records from ${PHFrame.escape(item.name)}?" data-connector="${item.name}"></ph-confirm></div></article>`).join("") || `<div class="ph-empty-state"><span>⌁</span><p>No connectors yet. Create one below.</p></div>`;
      const rows = history.data.map(item => `<tr><td>${PHFrame.escape(item.created_at)}</td><td>${PHFrame.escape(item.connector)}</td><td>${item.status}</td><td>${item.imported_rows}/${item.fetched_rows}</td><td>${item.errors.map(error => PHFrame.escape(error.message)).join("; ")}</td></tr>`).join("") || `<tr><td colspan="5">No synchronization runs.</td></tr>`;
      const datasets = Object.entries(metadata.datasets).map(([name, item]) => `<option value="${name}">${PHFrame.escape(item.label)}</option>`).join("");
      this.innerHTML = `<section class="ph-card ph-stack"><div><p class="ph-eyebrow">New data source</p><h3>Add a connector</h3><p class="ph-muted">Choose a provider for guided setup. Every connector maps remote fields into a typed PHFrame dataset.</p></div><form class="ph-stack" data-connector-form><div class="ph-provider-grid"><label><input type="radio" name="type" value="api" checked><b>REST API</b><small>Any JSON endpoint</small></label><label><input type="radio" name="type" value="dhis2"><b>DHIS2</b><small>One-click OAuth</small></label><label><input type="radio" name="type" value="kobo"><b>KoboToolbox</b><small>Form submissions</small></label><label><input type="radio" name="type" value="odk"><b>ODK Central</b><small>OData submissions</small></label></div><div class="ph-provider-guide" data-provider-guide></div><div class="ph-form-grid"><div class="ph-field"><label>Name</label><input name="name" required pattern="[a-z][a-z0-9_]*" placeholder="global_cases_api"></div><div class="ph-field"><label>Destination dataset</label><select name="dataset">${datasets}</select></div><div class="ph-field"><label>Server base URL</label><input name="base_url" type="url" required placeholder="https://api.example.org"></div><div class="ph-field"><label data-resource-label>Resource path</label><input name="resource" required list="ph-dhis2-data-sets" placeholder="v1/events"><datalist id="ph-dhis2-data-sets"></datalist></div><div class="ph-field" data-records-path><label>Records path</label><input name="records_path" placeholder="data.records"></div><div class="ph-field"><label>Schedule (minutes)</label><input name="schedule_minutes" type="number" min="1" placeholder="60"></div><div class="ph-field" data-auth-field><label>Token environment variable</label><input name="token_env" placeholder="HEALTH_API_TOKEN"></div><div class="ph-field" data-auth-field><label>Username environment variable</label><input name="username_env" placeholder="ODK_USERNAME"></div><div class="ph-field" data-auth-field><label>Password environment variable</label><input name="password_env" placeholder="ODK_PASSWORD"></div></div><div class="ph-field"><label>Field mapping (JSON)</label><textarea name="mapping" rows="5" required placeholder='{"source.id":"record_id","source.country":"country"}'></textarea><small>Left: provider source path. Right: destination dataset column.</small></div><button class="ph-button" type="submit">Create connector</button><p class="ph-status" role="status"></p></form></section><section><h3>Configured connectors</h3><div class="ph-grid">${cards}</div></section><section class="ph-card"><h3>Synchronization history</h3><div class="ph-table-wrap"><table class="ph-table"><thead><tr><th>Time</th><th>Connector</th><th>Status</th><th>Rows</th><th>Errors</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
      this.setupConnectorNavigation(connectors.data.length, history.data.length);
      this.querySelectorAll("[data-sync]").forEach(button => button.addEventListener("click", () => this.sync(button.dataset.sync, true)));
      this.querySelectorAll("ph-confirm[data-connector]").forEach(confirm => confirm.addEventListener("ph-confirmed", () => this.sync(confirm.dataset.connector, false)));
      this.querySelectorAll("[data-delete]").forEach(button => button.addEventListener("click", () => this.remove(button.dataset.delete)));
      this.querySelector("[data-connector-form]").addEventListener("submit", event => this.create(event));
      this.querySelectorAll('[name="type"]').forEach(input => input.addEventListener("change", () => this.providerChanged()));
      this.providerChanged();
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
  setupConnectorNavigation(connectorCount, syncCount) {
    const sections = [...this.querySelectorAll(":scope > section")], names = ["add", "configured", "history"];
    const workspace = document.createElement("div"); workspace.className = "ph-connectors-workspace";
    workspace.innerHTML = `<aside class="ph-connectors-sidebar"><div class="ph-connectors-sidebar-heading"><p class="ph-eyebrow">Data integrations</p><h3>Connectors</h3><p>Configure, test, and monitor external data sources.</p></div><nav role="tablist" aria-label="Connector sections"><button type="button" role="tab" data-connector-tab="add"><span>+</span><span><small>Setup</small><b>Add connector</b></span><i>›</i></button><button type="button" role="tab" data-connector-tab="configured"><span>⌁</span><span><small>${connectorCount} active</small><b>Configured</b></span><i>›</i></button><button type="button" role="tab" data-connector-tab="history"><span>↻</span><span><small>${syncCount} runs</small><b>Sync history</b></span><i>›</i></button></nav></aside>`;
    this.prepend(workspace); sections.forEach((section, index) => { section.classList.add("ph-connector-panel"); section.dataset.connectorPanel = names[index]; workspace.append(section); });
    this.querySelectorAll("[data-connector-tab]").forEach(tab => tab.addEventListener("click", () => this.activateConnectorPanel(tab.dataset.connectorTab)));
    this.activateConnectorPanel(sessionStorage.getItem("ph-connectors-tab") || (connectorCount ? "configured" : "add"));
  }
  activateConnectorPanel(name) { if (!this.querySelector(`[data-connector-panel="${name}"]`)) name = "add"; this.querySelectorAll("[data-connector-panel]").forEach(panel => panel.hidden = panel.dataset.connectorPanel !== name); this.querySelectorAll("[data-connector-tab]").forEach(tab => { const active = tab.dataset.connectorTab === name; tab.classList.toggle("ph-connector-tab-active", active); tab.setAttribute("aria-selected", String(active)); tab.tabIndex = active ? 0 : -1; }); sessionStorage.setItem("ph-connectors-tab", name); }
  async create(event) {
    event.preventDefault(); const form = event.currentTarget, status = form.querySelector("[role=status]");
    try {
      const raw = Object.fromEntries(new FormData(form));
      const auth = {}; if (raw.type === "dhis2" && this.dhis2Status?.connected) auth.token_env = "PHFRAME_DHIS2_OAUTH_TOKEN"; else { if (raw.token_env) auth.token_env = raw.token_env; if (raw.username_env) auth.username_env = raw.username_env; if (raw.password_env) auth.password_env = raw.password_env; }
      const payload = { ...raw, mapping: JSON.parse(raw.mapping), auth };
      delete payload.token_env; delete payload.username_env; delete payload.password_env; if (!payload.records_path) delete payload.records_path; if (!payload.schedule_minutes) delete payload.schedule_minutes;
      await PHFrame.send("/api/connectors", "POST", payload); sessionStorage.setItem("ph-connectors-tab", "configured"); PHFrame.notify("Connector created."); this.render();
    } catch (error) { status.textContent = error.message; status.className = "ph-status ph-error"; }
  }
  async providerChanged() {
    const type = this.querySelector('[name="type"]:checked').value;
    const form = this.querySelector("[data-connector-form]"), connectorFields = form.querySelector('[name="name"]').closest(".ph-form-grid"), serverField = form.querySelector('[name="base_url"]').closest(".ph-field");
    if (serverField.parentElement !== connectorFields) connectorFields.appendChild(serverField);
    const presets = {
      api: ["Generic REST API", "Enter the endpoint path and optional nested records path. Bearer token and basic authentication are supported through environment variables.", "v1/events", "Resource path", true],
      dhis2: ["Connect to DHIS2", "Enter your DHIS2 server and login here. PHFrame validates the connection, encrypts the credential, and discovers available data sets without leaving this page.", "BfMAe6Itzgt", "Data Set UID", false],
      kobo: ["KoboToolbox submissions", "Enter the Kobo server URL and Asset UID. The token environment variable is sent using Kobo's Token authentication scheme.", "aR9xExampleAsset", "Asset UID", false],
      odk: ["ODK Central submissions", "Enter the Central URL and PROJECT_ID/FORM_ID. Configure token or Basic authentication with environment-variable names.", "12/household_survey", "Project ID / Form ID", false]
    }[type];
    const guide = this.querySelector("[data-provider-guide]"), connected = type === "dhis2" && this.dhis2Status?.connected;
    guide.innerHTML = `<b>${presets[0]}</b><span>${presets[1]}</span>${type === "dhis2" ? (connected ? `<span class="ph-oauth-connected"><i></i> Connected as ${PHFrame.escape(this.dhis2Status.user?.displayName || this.dhis2Status.user?.username || "DHIS2 user")}</span><div class="ph-dhis2-import"><div class="ph-field"><label>DHIS2 data set</label><select data-dhis2-data-set><option value="">Loading available data sets…</option></select></div><div class="ph-field"><label>New PHFrame dataset name</label><input data-dhis2-local-name pattern="[a-z][a-z0-9_]*" placeholder="malaria_monthly_data"></div><div class="ph-field"><label>Automatic sync (minutes)</label><input data-dhis2-schedule type="number" min="1" value="60"></div><button type="button" class="ph-button" data-dhis2-import>Create dataset and connector</button></div><button type="button" class="ph-button ph-button-secondary" data-dhis2-disconnect>Disconnect</button>` : `<div class="ph-form-grid ph-dhis2-login"><div class="ph-field"><label>DHIS2 username</label><input data-dhis2-username autocomplete="username" required placeholder="admin"></div><div class="ph-field"><label>DHIS2 password</label><input data-dhis2-password type="password" autocomplete="current-password" required placeholder="Password"></div></div><button type="button" class="ph-button" data-dhis2-connect>Connect and load datasets</button>`) : ""}`;
    this.querySelector("[name=resource]").placeholder = presets[2]; this.querySelector("[data-resource-label]").textContent = presets[3]; this.querySelector("[data-records-path]").hidden = !presets[4];
    this.querySelectorAll("[data-auth-field]").forEach(field => field.hidden = type === "dhis2");
    const server = this.querySelector("[name=base_url]"); if (connected) { server.value = this.dhis2Status.server_url; server.readOnly = true; } else server.readOnly = false;
    const regularFields = [...connectorFields.children].filter(field => field.classList.contains("ph-field")), mappingField = form.querySelector("textarea[name=mapping]").closest(".ph-field"), createButton = form.querySelector(':scope > button[type="submit"]');
    if (type === "dhis2") { regularFields.forEach(field => field.hidden = field.querySelector('[name="base_url"]') ? connected : true); mappingField.hidden = true; createButton.hidden = true; } else { regularFields.forEach(field => field.hidden = field.hasAttribute("data-records-path") ? !presets[4] : false); mappingField.hidden = false; createButton.hidden = false; }
    if (type === "dhis2" && !connected) { serverField.hidden = false; guide.insertBefore(serverField, guide.querySelector(".ph-dhis2-login")); }
    guide.querySelector("[data-dhis2-connect]")?.addEventListener("click", async event => { const username = guide.querySelector("[data-dhis2-username]"), password = guide.querySelector("[data-dhis2-password]"); if (!server || !username || !password) { PHFrame.notify("DHIS2 connection fields could not load. Refresh the page and try again."); return; } if (!server.reportValidity() || !username.reportValidity() || !password.reportValidity()) return; event.currentTarget.disabled = true; try { const response = await PHFrame.send("/api/integrations/dhis2/password-connect", "POST", { server_url: server.value, username: username.value, password: password.value }); password.value = ""; this.dhis2Status = response.data; PHFrame.notify("DHIS2 connected. Loading datasets…"); await this.providerChanged(); } catch (error) { PHFrame.notify(error.message); event.currentTarget.disabled = false; } });
    guide.querySelector("[data-dhis2-disconnect]")?.addEventListener("click", async () => { await PHFrame.send("/api/integrations/dhis2/disconnect", "POST", {}); this.dhis2Status = { connected: false }; this.providerChanged(); PHFrame.notify("DHIS2 disconnected."); });
    if (connected) { try { const response = await PHFrame.get("/api/integrations/dhis2/data-sets"), select = guide.querySelector("[data-dhis2-data-set]"); select.innerHTML = `<option value="">Select a DHIS2 data set</option>` + response.data.map(item => `<option value="${PHFrame.escape(item.id)}" data-name="${PHFrame.escape(item.name)}">${PHFrame.escape(item.name)}</option>`).join(""); select.addEventListener("change", () => { const option = select.selectedOptions[0], slug = String(option?.dataset.name || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, ""); guide.querySelector("[data-dhis2-local-name]").value = slug; }); guide.querySelector("[data-dhis2-import]").addEventListener("click", () => this.importDhis2DataSet(guide)); } catch (error) { guide.insertAdjacentHTML("beforeend", `<span class="ph-error">${PHFrame.escape(error.message)}</span>`); } }
  }
  async importDhis2DataSet(guide) { const select = guide.querySelector("[data-dhis2-data-set]"), local = guide.querySelector("[data-dhis2-local-name]"), button = guide.querySelector("[data-dhis2-import]"); if (!select.value) { select.reportValidity(); PHFrame.notify("Select a DHIS2 data set."); return; } if (!local.reportValidity() || !local.value) return; button.disabled = true; try { const response = await PHFrame.send("/api/integrations/dhis2/import-data-set", "POST", { data_set_id: select.value, data_set_name: select.selectedOptions[0].dataset.name, local_name: local.value, schedule_minutes: Number(guide.querySelector("[data-dhis2-schedule]").value || 60) }); sessionStorage.setItem("ph-connectors-tab", "configured"); PHFrame.notify(`${response.data.label} is ready to sync.`); this.render(); } catch (error) { PHFrame.notify(error.message); button.disabled = false; } }
  async remove(name) {
    if (!confirm(`Remove connector ${name}? Imported records will remain.`)) return;
    try { await PHFrame.send(`/api/connectors/${name}`, "DELETE"); sessionStorage.setItem("ph-connectors-tab", "configured"); PHFrame.notify("Connector removed."); this.render(); } catch (error) { PHFrame.notify(error.message); }
  }
  async sync(name, dryRun) {
    try {
      const response = await PHFrame.send(`/api/connectors/${name}/sync?dry_run=${dryRun}`, "POST", {});
      sessionStorage.setItem("ph-connectors-tab", "history"); PHFrame.notify(`${name}: ${response.data.status}`);
      this.render();
    } catch (error) { PHFrame.notify(`${name}: ${error.message}`); }
  }
}

class PHAIAssistant extends PHElement {
  set metadata(value) { this._metadata = value; if (this.isConnected) this.render(); }
  render() {
    if (!this._metadata) return;
    this.innerHTML = `<button class="ph-ai-launcher" type="button" aria-label="Open AI assistance" aria-expanded="false"><span class="ph-ai-launcher-spark">✦</span><span class="ph-ai-launcher-label"><b>Ask PHFrame</b><small>AI data assistant</small></span></button><div class="ph-ai-backdrop" hidden></div><aside class="ph-ai-popup" role="dialog" aria-modal="false" aria-labelledby="ph-ai-popup-title" hidden><header><div class="ph-ai-popup-brand"><span>✦</span><div><h2 id="ph-ai-popup-title">AI assistance</h2><p><i></i> Ready · aggregate evidence only</p></div></div><button class="ph-ai-popup-close" type="button" aria-label="Close AI assistance">×</button></header><ph-ai-workspace compact></ph-ai-workspace><footer><span>◈ Privacy protected</span><span>Answers include evidence</span></footer></aside>`;
    this.querySelector("ph-ai-workspace").metadata = this._metadata;
    this.querySelector(".ph-ai-launcher").addEventListener("click", () => this.open());
    this.querySelector(".ph-ai-popup-close").addEventListener("click", () => this.close());
    this.querySelector(".ph-ai-backdrop").addEventListener("click", () => this.close());
    this.addEventListener("keydown", event => { if (event.key === "Escape") this.close(); });
  }
  open() { clearTimeout(this._closeTimer); const popup = this.querySelector(".ph-ai-popup"), backdrop = this.querySelector(".ph-ai-backdrop"), launcher = this.querySelector(".ph-ai-launcher"); popup.hidden = false; backdrop.hidden = false; launcher.setAttribute("aria-expanded", "true"); document.body.classList.add("ph-ai-popup-open"); requestAnimationFrame(() => { popup.classList.add("ph-ai-popup-visible"); this.querySelector('textarea[name="question"]')?.focus(); }); }
  close() { const popup = this.querySelector(".ph-ai-popup"), backdrop = this.querySelector(".ph-ai-backdrop"), launcher = this.querySelector(".ph-ai-launcher"); if (!popup || popup.hidden) return; popup.classList.remove("ph-ai-popup-visible"); launcher.setAttribute("aria-expanded", "false"); document.body.classList.remove("ph-ai-popup-open"); this._closeTimer = setTimeout(() => { popup.hidden = true; backdrop.hidden = true; launcher.focus(); }, 180); }
}

class PHAIWorkspace extends PHElement {
  set metadata(value) { this._metadata = value; if (this.isConnected) this.render(); }
  sessionId() {
    let value = localStorage.getItem("ph-ai-session");
    if (!value) { value = `analyst-${crypto.randomUUID()}`; localStorage.setItem("ph-ai-session", value); }
    return value;
  }
  async render() {
    if (!this._metadata) return;
    const compact = this.hasAttribute("compact");
    this.innerHTML = `<p class="ph-muted" role="status">Loading responsible AI workspace…</p>`;
    try {
      const session = this.sessionId();
      const [summaries, audit, chats] = compact ? [{ data: [] }, { data: [] }, await PHFrame.get(`/api/ai/chat?session_id=${encodeURIComponent(session)}`)] : await Promise.all([PHFrame.get("/api/ai/summaries"), PHFrame.get("/api/ai/audit"), PHFrame.get(`/api/ai/chat?session_id=${encodeURIComponent(session)}`)]);
      const datasets = Object.entries(this._metadata.datasets).map(([name, item]) => `<option value="${name}">${PHFrame.escape(item.label)}</option>`).join("");
      const cards = summaries.data.map(item => this.summaryCard(item)).join("") || `<div class="ph-empty-state"><span>AI</span><p>No AI-assisted drafts yet.</p></div>`;
      const events = audit.data.map(item => `<tr><td>${PHFrame.escape(item.created_at)}</td><td>${PHFrame.escape(item.event)}</td><td>${PHFrame.escape(item.actor)}</td><td>${item.summary_id ?? "—"}</td></tr>`).join("") || `<tr><td colspan="4">No AI activity yet.</td></tr>`;
      const transcript = chats.data.map(item => this.chatTurn(item)).join("") || `<div class="ph-ai-welcome"><span>✦</span><h3>Ask your public-health data</h3><p>I can compare locations, analyze trends, flag unusual changes, explain alerts, inspect data quality, and draft a cited situation report.</p></div>`;
      const notice = compact ? "" : `<div class="ph-ai-notice"><b>Human-controlled assistance</b><span>PHFrame uses aggregate evidence only. Output is a draft until a person approves it; do not use it as diagnosis or clinical advice.</span></div>`;
      const tools = compact ? "" : `<details class="ph-ai-tools"><summary>Reports, de-identification, approvals, and audit</summary><div class="ph-ai-layout"><section class="ph-card ph-stack"><div><p class="ph-eyebrow">Evidence summary</p><h3>Create a full briefing draft</h3></div><form class="ph-stack" data-ai-form><input type="hidden" name="author" value="Me"><div class="ph-field"><label>Briefing title</label><input name="title" required value="Public health situation summary"></div><div class="ph-field"><label>Purpose and audience</label><textarea name="purpose" rows="4" placeholder="Weekly surveillance meeting for programme managers"></textarea></div><button class="ph-button">Generate evidence-backed draft</button><p role="status" class="ph-status"></p></form></section><section class="ph-card ph-stack"><div><p class="ph-eyebrow">De-identification</p><h3>Preview a safer dataset view</h3></div><form class="ph-actions" data-deid-form><div class="ph-field"><label>Dataset</label><select name="dataset">${datasets}</select></div><div class="ph-field"><label>Rows</label><input name="limit" type="number" min="1" max="100" value="10"></div><button class="ph-button ph-button-secondary">Preview</button></form><p class="ph-muted">Protected identifiers are removed; dates become years and ages become bands. This reduces exposure but is not a legal certification.</p><div data-deid-result></div></section></div><section><div class="ph-widget-header"><div><p class="ph-eyebrow">Human approval queue</p><h3>Drafts and decisions</h3></div></div><div class="ph-ai-summaries">${cards}</div></section><section class="ph-card"><p class="ph-eyebrow">Audit history</p><h3>Immutable AI events</h3><div class="ph-table-wrap"><table class="ph-table"><thead><tr><th>Time</th><th>Event</th><th>Actor</th><th>Summary</th></tr></thead><tbody>${events}</tbody></table></div></section></details>`;
      this.innerHTML = `${notice}<section class="ph-ai-chat"><header><div><p class="ph-eyebrow">Evidence-aware assistant</p><h3>Ask your public-health data</h3></div><button class="ph-button ph-button-secondary" type="button" data-new-chat>New conversation</button></header><div class="ph-ai-prompts"><button>Summarize the latest situation</button><button>Are cases increasing over time?</button><button>Is there an unusual spike?</button><button>Compare reporting locations</button><button>Check data quality</button><button>Explain current alerts</button></div><div class="ph-ai-transcript" data-chat-transcript>${transcript}</div><form class="ph-ai-composer" data-chat-form><textarea name="question" required rows="2" placeholder="Ask a question about trends, locations, alerts, or data quality…"></textarea><button class="ph-button" aria-label="Send question">Send <span>↑</span></button><p role="status" class="ph-status"></p></form></section>${tools}`;
      this.querySelector("[data-chat-form]").addEventListener("submit", event => this.ask(event));
      this.querySelectorAll(".ph-ai-prompts button").forEach(button => button.addEventListener("click", () => { this.querySelector('[name="question"]').value = button.textContent; this.querySelector('[name="question"]').focus(); }));
      this.querySelectorAll("[data-chat-report]").forEach(button => button.addEventListener("click", () => this.makeReport(button.dataset.chatReport)));
      this.querySelector("[data-new-chat]").addEventListener("click", () => { localStorage.removeItem("ph-ai-session"); this.render(); });
      this.querySelector("[data-ai-form]")?.addEventListener("submit", event => this.generate(event));
      this.querySelector("[data-deid-form]")?.addEventListener("submit", event => this.preview(event));
      this.querySelectorAll("[data-review]").forEach(button => button.addEventListener("click", () => this.review(button.dataset.id, button.dataset.review)));
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
  chatTurn(item) {
    return `<article class="ph-chat-turn"><div class="ph-chat-question"><b>Me</b><p>${PHFrame.escape(item.question)}</p></div><div class="ph-chat-answer"><div class="ph-chat-avatar">✦</div><div><div class="ph-chat-meta"><b>AI assistance · ${PHFrame.escape(item.intent)}</b><time>${PHFrame.escape(new Date(item.created_at).toLocaleString())}</time></div><div class="ph-ai-copy"><p>${PHFrame.markdown(item.answer)}</p></div><div class="ph-ai-privacy"><span>Aggregate evidence only</span><span>${item.evidence.length} sources</span><span>Trace ${PHFrame.escape(item.evidence_digest.slice(0, 8))}</span></div><div class="ph-actions"><button class="ph-button ph-button-secondary" data-chat-report="${item.id}">Create report draft</button><details><summary>View evidence</summary><ol>${item.evidence.map(source => `<li><a href="${PHFrame.escape(source.endpoint)}" target="_blank">${PHFrame.escape(source.label || source.name)}</a></li>`).join("")}</ol></details></div></div></div></article>`;
  }
  async ask(event) {
    event.preventDefault(); const form = event.currentTarget, data = Object.fromEntries(new FormData(form)), status = form.querySelector("[role=status]"), button = form.querySelector("button"); status.textContent = "Analyzing relevant aggregate evidence…"; button.disabled = true;
    try { await PHFrame.send("/api/ai/chat", "POST", { ...data, author: "Me", session_id: this.sessionId() }); await this.render(); this.querySelector("[data-chat-transcript]")?.scrollTo({ top: 999999, behavior: "smooth" }); } catch (error) { status.textContent = error.message; status.className = "ph-status ph-error"; button.disabled = false; }
  }
  async makeReport(chatId) {
    const title = prompt("Situation report title", "Public health situation report"); if (!title) return;
    try { await PHFrame.send(`/api/ai/chat/${chatId}/report`, "POST", { title, author: "Me" }); PHFrame.notify("Report draft created. Open Reports and approvals to review it."); this.render(); } catch (error) { PHFrame.notify(error.message); }
  }
  summaryCard(item) {
    const review = item.status === "draft" ? `<div class="ph-actions"><button class="ph-button" data-review="approved" data-id="${item.id}">Approve</button><button class="ph-button ph-button-secondary" data-review="rejected" data-id="${item.id}">Reject</button><a class="ph-button ph-button-secondary" href="/api/ai/summaries/${item.id}/export">Download draft</a></div>` : `<p class="ph-review-note"><b>Reviewed by ${PHFrame.escape(item.reviewed_by)}</b><br>${PHFrame.escape(item.review_note)}</p><a class="ph-button ph-button-secondary" href="/api/ai/summaries/${item.id}/export">Download report</a>`;
    return `<article class="ph-card ph-ai-summary"><div class="ph-widget-header"><div><p class="ph-eyebrow">${PHFrame.escape(item.provider)} · ${PHFrame.escape(item.model)}</p><h3>${PHFrame.escape(item.title)}</h3></div><span class="ph-status-badge ph-status-${item.status}">${PHFrame.escape(item.status)}</span></div><div class="ph-ai-privacy"><span>0 row-level records sent</span><span>0 protected fields sent</span><span>Evidence ${PHFrame.escape(item.evidence_digest.slice(0, 12))}…</span></div><div class="ph-ai-copy"><p>${PHFrame.markdown(item.content)}</p></div><details><summary>Evidence register (${item.evidence.length})</summary><ol>${item.evidence.map(evidence => `<li><a href="${PHFrame.escape(evidence.endpoint)}" target="_blank">${PHFrame.escape(evidence.label || evidence.name)}</a></li>`).join("")}</ol></details>${review}</article>`;
  }
  async generate(event) {
    event.preventDefault(); const form = event.currentTarget, status = form.querySelector("[role=status]"); status.textContent = "Building aggregate evidence and draft…";
    try { await PHFrame.send("/api/ai/summaries", "POST", Object.fromEntries(new FormData(form))); PHFrame.notify("AI draft created for human review."); this.render(); } catch (error) { status.textContent = error.message; status.className = "ph-status ph-error"; }
  }
  async preview(event) {
    event.preventDefault(); const data = Object.fromEntries(new FormData(event.currentTarget)), result = this.querySelector("[data-deid-result]");
    try { const response = await PHFrame.send(`/api/ai/deidentify/${data.dataset}`, "POST", { limit: Number(data.limit) }); const item = response.data; const fields = item.records[0] ? Object.keys(item.records[0]) : []; result.innerHTML = `<div class="ph-ai-privacy"><span>Removed: ${PHFrame.escape(item.removed_fields.join(", ") || "none")}</span><span>Generalized: ${PHFrame.escape(item.transformed_fields.join(", ") || "none")}</span></div><div class="ph-table-wrap"><table class="ph-table"><thead><tr>${fields.map(field => `<th>${PHFrame.escape(field)}</th>`).join("")}</tr></thead><tbody>${item.records.map(row => `<tr>${fields.map(field => `<td>${PHFrame.escape(row[field] ?? "—")}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`; } catch (error) { result.innerHTML = `<p class="ph-error">${PHFrame.escape(error.message)}</p>`; }
  }
  async review(id, decision) {
    const note = prompt(`Explain why this draft is ${decision}. This note becomes part of the audit history.`);
    if (!note?.trim()) return;
    try { await PHFrame.send(`/api/ai/summaries/${id}/review`, "POST", { decision, note, reviewer: "Me" }); PHFrame.notify(`Draft ${decision}.`); this.render(); } catch (error) { PHFrame.notify(error.message); }
  }
}

customElements.define("ph-app-shell", PHAppShell);
customElements.define("ph-data-form", PHDataForm);
customElements.define("ph-case-table", PHCaseTable);
customElements.define("ph-filter-bar", PHFilterBar);
customElements.define("ph-org-unit-select", PHOrgUnitSelect);
customElements.define("ph-quality-panel", PHQualityPanel);
customElements.define("ph-kpi", PHKPI);
customElements.define("ph-indicator-chart", PHIndicatorChart);
customElements.define("ph-epi-curve", PHEpiCurve);
customElements.define("ph-map", PHMap);
customElements.define("ph-geo-map", PHGeoMap);
customElements.define("ph-dashboard-manager", PHDashboardManager);
customElements.define("ph-dashboard", PHDashboard);
customElements.define("ph-notification-center", PHNotificationCenter);
customElements.define("ph-modal", PHModal);
customElements.define("ph-confirm", PHConfirm);
customElements.define("ph-import-wizard", PHImportWizard);
customElements.define("ph-data-builder", PHDataBuilder);
customElements.define("ph-settings-panel", PHSettingsPanel);
customElements.define("ph-rich-editor", PHRichEditor);
customElements.define("ph-page-table", PHPageTable);
customElements.define("ph-custom-page", PHCustomPage);
customElements.define("ph-page-builder", PHPageBuilder);
customElements.define("ph-ai-assistant", PHAIAssistant);
customElements.define("ph-ai-workspace", PHAIWorkspace);
customElements.define("ph-connector-console", PHConnectorConsole);
window.PHFrame = PHFrame;
