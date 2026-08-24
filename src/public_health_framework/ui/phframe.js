const PHFrame = {
  messages: {
    en: { dashboard: "Dashboard", records: "Records", quality: "Data quality", theme: "Theme", saved: "Record saved." },
    bn: { dashboard: "ড্যাশবোর্ড", records: "রেকর্ড", quality: "ডেটার গুণমান", theme: "থিম", saved: "রেকর্ড সংরক্ষিত হয়েছে।" }
  },
  async get(path) {
    const response = await fetch(path, { headers: { accept: "application/json" } });
    if (!response.ok) throw new Error((await response.json()).error?.message || `Request failed (${response.status})`);
    return response.json();
  },
  async send(path, method, body) {
    const response = await fetch(path, {
      method, headers: { accept: "application/json", "content-type": "application/json" },
      body: JSON.stringify(body)
    });
    if (!response.ok) throw new Error((await response.json()).error?.message || `Request failed (${response.status})`);
    return response.status === 204 ? null : response.json();
  },
  escape(value) {
    const span = document.createElement("span");
    span.textContent = value == null ? "" : String(value);
    return span.innerHTML;
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
  notify(message) { dispatchEvent(new CustomEvent("ph-notify", { detail: { message } })); }
};

class PHElement extends HTMLElement {
  connectedCallback() { this.render(); }
  render() {}
}

class PHAppShell extends PHElement {
  async render() {
    this.innerHTML = `<p class="ph-muted" role="status">Loading PHFrame…</p>`;
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
      this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`;
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
      <div class="ph-header-tools"><label>${PHFrame.t("theme")} <select class="ph-theme" aria-label="${PHFrame.t("theme")}"><option value="light">Light</option><option value="dark">Dark</option><option value="high-contrast">High contrast</option></select></label>${PHFrame.siteSettings.access_mode === "private" ? `<button class="ph-logout" type="button">Sign out</button>` : ""}</div></header>
      <main class="ph-main" id="main" tabindex="-1"><div id="ph-view"></div></main>${PHFrame.siteSettings.show_footer ? `<footer class="ph-footer">${PHFrame.siteSettings.footer_html}</footer>` : ""}<ph-notification-center></ph-notification-center></div>`;
    const theme = this.querySelector(".ph-theme");
    theme.value = document.documentElement.dataset.theme;
    theme.addEventListener("change", () => { document.documentElement.dataset.theme = theme.value; localStorage.setItem("ph-theme", theme.value); PHFrame.applyColor(PHFrame.siteSettings.primary_color); });
    this.querySelector(".ph-logout")?.addEventListener("click", async () => { await PHFrame.send("/api/auth/logout", "POST", {}); location.href = "/login"; });
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
      view.innerHTML = `<h2>Records</h2><ph-filter-bar></ph-filter-bar><div class="ph-grid"><ph-data-form dataset="${PHFrame.escape(first)}"></ph-data-form><ph-case-table dataset="${PHFrame.escape(first)}"></ph-case-table></div>`;
      view.querySelector("ph-data-form").metadata = this.metadata.datasets[first];
      view.querySelector("ph-case-table").metadata = this.metadata.datasets[first];
      view.querySelector("ph-filter-bar").metadata = this.metadata;
      view.addEventListener("ph-filter", event => {
        const query = event.detail.filter ? `?filter=${encodeURIComponent(event.detail.filter)}` : "";
        view.querySelector("ph-case-table").load(query);
      });
    } else if (route === "builder") {
      view.innerHTML = `<h2>Data builder</h2><ph-data-builder></ph-data-builder>`;
      view.querySelector("ph-data-builder").metadata = this.metadata;
    } else if (route === "import") {
      view.innerHTML = `<h2>Import data</h2><ph-import-wizard></ph-import-wizard>`;
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
      const dashboard = Object.keys(this.metadata.dashboards || {})[0];
      view.innerHTML = dashboard ? `<ph-dashboard name="${PHFrame.escape(dashboard)}"></ph-dashboard>` : `<h2>Dashboard</h2><p class="ph-muted">No dashboard configured.</p>`;
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
    this.innerHTML = `<section class="ph-card"><h3>${PHFrame.escape(this._metadata.label)}</h3><p role="status">Loading records…</p></section>`;
    try {
      const response = await PHFrame.get(`/api/${this.dataset}${query}`);
      const columns = Object.keys(this._metadata.fields).filter(name => !this._metadata.fields[name].protected);
      const head = columns.map(name => `<th scope="col">${PHFrame.escape(this._metadata.fields[name].label || name)}</th>`).join("");
      const rows = response.data.map(record => `<tr>${columns.map(name => `<td>${PHFrame.escape(record[name] ?? "—")}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${columns.length}">No records found.</td></tr>`;
      this.innerHTML = `<section class="ph-card"><h3>${PHFrame.escape(this._metadata.label)}</h3><div class="ph-table-wrap"><table class="ph-table"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div><p class="ph-muted">Showing ${response.count} records</p></section>`;
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
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
    try {
      const response = await PHFrame.get(`/api/dimensions/${this.getAttribute("dimension")}`);
      const values = response.data.values;
      const visualization = this.getAttribute("visualization") || "tiles";
      if (visualization === "bar" || visualization === "donut" || visualization === "table") {
        this.innerHTML = `<ph-indicator-chart dimension="${PHFrame.escape(this.getAttribute("dimension"))}" title="${PHFrame.escape(this.getAttribute("title"))}" visualization="${visualization}"></ph-indicator-chart>`;
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
}

class PHDashboard extends PHElement {
  async render() {
    try {
      const [response, metadata] = await Promise.all([PHFrame.get(`/api/dashboards/${this.getAttribute("name")}`), PHFrame.get("/api")]);
      this.dashboard = response.data;
      this.metadata = metadata;
      this.storageKey = `ph-dashboard-layout:${this.getAttribute("name")}`;
      this.settings = this.loadSettings();
      this.draw();
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
  widgetId(widget, index) { return widget._id || `${widget.type}-${widget.indicator || widget.dimension || widget.dataset || index}-${index}`; }
  defaults(widget) {
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
    const title = PHFrame.siteSettings?.dashboard_title || this.dashboard.label;
    this.innerHTML = `<section class="ph-dashboard-heading"><div><p class="ph-eyebrow">Data overview</p><h2>${PHFrame.escape(title)}</h2><p class="ph-muted">Live metrics and trends from your configured datasets</p></div><div class="ph-dashboard-actions"><button class="ph-button" type="button" data-add-widget>+ Add visualization</button><button class="ph-button ph-button-secondary" type="button" data-reset>Reset layout</button><span class="ph-save-state" role="status">Changes save automatically</span></div></section><div class="ph-dashboard-grid" aria-label="Customizable dashboard">${cards}</div>${this.widgetDialog()}`;
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
    return `<dialog class="ph-dialog ph-widget-dialog"><form method="dialog" class="ph-stack" data-widget-form><div class="ph-widget-header"><div><p class="ph-eyebrow">Dashboard builder</p><h2>Add visualization</h2></div><button value="cancel" class="ph-dialog-close" aria-label="Close">×</button></div><div class="ph-field"><label for="ph-widget-title">Title</label><input id="ph-widget-title" name="title" required placeholder="My visualization"></div><div class="ph-field"><label for="ph-widget-source">Data source</label><select id="ph-widget-source" name="source" required>${indicators}${numericFields}${dimensions}${fields}${trends}</select></div><div class="ph-actions"><button class="ph-button" value="default" data-create-widget>Add to dashboard</button><button value="cancel">Cancel</button></div></form></dialog>`;
  }
  card(widget, index, id) {
    const defaults = this.defaults(widget), saved = this.settings[id] || {};
    const visualization = saved.visualization || defaults.visualization, size = saved.size || defaults.size;
    const options = defaults.choices.map(([value, label]) => `<option value="${value}" ${value === visualization ? "selected" : ""}>${label}</option>`).join("");
    const sizeOptions = [["compact", "Small"], ["medium", "Medium"], ["wide", "Wide"]].map(([value, label]) => `<option value="${value}" ${value === size ? "selected" : ""}>${label}</option>`).join("");
    let component;
    if (widget.type === "kpi") component = `<ph-kpi indicator="${widget.indicator}" visualization="${visualization}"></ph-kpi>`;
    else if (widget.type === "field_kpi") component = `<ph-kpi dataset="${widget.dataset}" field="${widget.field}" operation="${widget.operation || "sum"}" visualization="${visualization}"></ph-kpi>`;
    else if (widget.type === "chart") component = `<ph-indicator-chart dimension="${widget.dimension}" visualization="${visualization}"></ph-indicator-chart>`;
    else if (widget.type === "field_chart") component = `<ph-indicator-chart dataset="${widget.dataset}" field="${widget.field}" visualization="${visualization}"></ph-indicator-chart>`;
    else if (widget.type === "map") component = `<ph-map dimension="${widget.dimension}" visualization="${visualization}"></ph-map>`;
    else component = `<ph-epi-curve dataset="${widget.dataset}" date-field="${widget.date_field}" value-field="${widget.value_field || ""}" visualization="${visualization}"></ph-epi-curve>`;
    const span = saved.span || { compact: 3, medium: 6, wide: 12 }[size], height = saved.height || 285;
    const handles = ["n", "e", "s", "w", "ne", "se", "sw", "nw"].map(direction => `<button class="ph-resize-handle ph-resize-${direction}" data-resize="${direction}" type="button" aria-label="Resize ${PHFrame.escape(widget.title)} ${direction}" title="Drag to resize"></button>`).join("");
    return `<article class="ph-card ph-dashboard-card ph-size-${size}" style="--ph-widget-span:${span};--ph-widget-height:${height}px" data-widget-id="${id}" draggable="true"><header class="ph-widget-header"><div><p class="ph-widget-kind">${PHFrame.escape(widget.type === "epi_curve" ? "Trend" : widget.type)}</p><h3>${PHFrame.escape(widget.title)}</h3></div><div class="ph-card-actions"><button class="ph-drag-handle" type="button" aria-label="Drag ${PHFrame.escape(widget.title)}" title="Drag to reorder">⠿</button><button class="ph-remove-widget" type="button" aria-label="Remove ${PHFrame.escape(widget.title)}" title="Remove visualization">×</button></div></header><div class="ph-widget-controls"><label>View<select data-visualization>${options}</select></label><label>Size<select data-size>${sizeOptions}</select></label><button type="button" data-move="up" aria-label="Move ${PHFrame.escape(widget.title)} earlier">←</button><button type="button" data-move="down" aria-label="Move ${PHFrame.escape(widget.title)} later">→</button></div><div class="ph-widget-content">${component}</div>${handles}</article>`;
  }
  bind() {
    this.querySelector("[data-reset]").addEventListener("click", () => { localStorage.removeItem(this.storageKey); this.settings = {}; this.draw(); PHFrame.notify("Dashboard layout reset."); });
    const dialog = this.querySelector(".ph-widget-dialog");
    this.querySelector("[data-add-widget]").addEventListener("click", () => dialog.showModal());
    this.querySelector("[data-widget-form]").addEventListener("submit", event => { if (event.submitter?.value === "cancel") return; event.preventDefault(); this.addWidget(event.currentTarget); dialog.close(); });
    this.querySelectorAll(".ph-dashboard-card").forEach(card => {
      card.querySelector("[data-visualization]").addEventListener("change", event => this.updateCard(card, "visualization", event.target.value));
      card.querySelector("[data-size]").addEventListener("change", event => this.updateCard(card, "size", event.target.value));
      card.querySelectorAll("[data-move]").forEach(button => button.addEventListener("click", () => this.move(card, button.dataset.move)));
      card.querySelector(".ph-remove-widget").addEventListener("click", () => this.removeWidget(card.dataset.widgetId));
      card.querySelectorAll("[data-resize]").forEach(handle => handle.addEventListener("pointerdown", event => this.startResize(event, card, handle.dataset.resize)));
      card.addEventListener("dragstart", event => { card.classList.add("ph-dragging"); event.dataTransfer.effectAllowed = "move"; event.dataTransfer.setData("text/plain", card.dataset.widgetId); });
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
    else { const visualization = card.querySelector("[data-visualization]").value; const component = card.querySelector("ph-kpi, ph-indicator-chart, ph-map, ph-epi-curve"); component.setAttribute("visualization", visualization); component.render(); }
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
    else { widget.dataset = parts[1]; widget.date_field = parts[2]; widget.value_field = parts[3]; }
    this.settings.customWidgets = [...(this.settings.customWidgets || []), widget];
    localStorage.setItem(this.storageKey, JSON.stringify(this.settings)); this.draw(); PHFrame.notify("Visualization added.");
  }
  removeWidget(id) {
    this.settings.hidden = [...new Set([...(this.settings.hidden || []), id])];
    this.saveSettings(); this.draw(); PHFrame.notify("Visualization removed. Reset layout to restore it.");
  }
  startResize(event, card, direction) {
    event.preventDefault(); event.stopPropagation(); card.setAttribute("draggable", "false");
    const startX = event.clientX, startY = event.clientY, startSpan = Number(getComputedStyle(card).getPropertyValue("--ph-widget-span")) || 6, startHeight = card.offsetHeight;
    const gridWidth = this.querySelector(".ph-dashboard-grid").clientWidth, columnWidth = gridWidth / 12;
    const move = pointer => { const horizontal = direction.includes("e") ? pointer.clientX - startX : (direction.includes("w") ? startX - pointer.clientX : 0); const vertical = direction.includes("s") ? pointer.clientY - startY : (direction.includes("n") ? startY - pointer.clientY : 0); const span = Math.min(12, Math.max(2, Math.round(startSpan + horizontal / columnWidth))); const height = Math.min(720, Math.max(210, startHeight + vertical)); card.style.setProperty("--ph-widget-span", span); card.style.setProperty("--ph-widget-height", `${height}px`); card.dataset.resizeSpan = span; card.dataset.resizeHeight = Math.round(height); };
    const end = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", end); card.setAttribute("draggable", "true"); const id = card.dataset.widgetId; this.settings[id] = { ...(this.settings[id] || {}), span: Number(card.dataset.resizeSpan || startSpan), height: Number(card.dataset.resizeHeight || startHeight) }; this.saveSettings(); PHFrame.notify("Widget size saved."); };
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
    this.innerHTML = `<section class="ph-card ph-stack"><div class="ph-import-guide"><div><p class="ph-eyebrow">Supported formats</p><h3>Bring your data in safely</h3><p class="ph-muted">Upload CSV, Excel, JSON, or XML. Preview and map every column before anything is saved.</p></div><div class="ph-example-links"><span>Download an example:</span><a data-example="csv">CSV</a><a data-example="json">JSON</a><a data-example="xml">XML</a></div></div><div class="ph-format-cards"><div><b>CSV / Excel</b><small>One record per row with headers</small></div><div><b>JSON</b><small>Array of objects or a records/data array</small></div><div><b>XML</b><small>&lt;records&gt; containing &lt;record&gt; elements</small></div></div><div class="ph-import-step"><h3>1. Choose a file</h3><div class="ph-actions"><div class="ph-field"><label for="ph-import-dataset">Dataset</label><select id="ph-import-dataset">${datasets}</select></div><div class="ph-field"><label for="ph-import-template">Saved mapping</label><select id="ph-import-template"><option value="">Automatic mapping</option>${templateOptions}</select></div><div class="ph-field ph-file-field"><label for="ph-import-file">Data file</label><input id="ph-import-file" type="file" accept=".csv,.xlsx,.xlsm,.json,.xml"></div><button class="ph-button" type="button" data-preview>Preview</button></div></div><div data-workspace></div><p role="status" class="ph-status"></p></section>`;
    this.querySelector("[data-preview]").addEventListener("click", () => this.preview());
    this.querySelectorAll("[data-example]").forEach(link => { link.href = `/api/import-example/${this.querySelector("#ph-import-dataset").value}?format=${link.dataset.example}`; link.setAttribute("download", ""); });
    this.querySelector("#ph-import-dataset").addEventListener("change", event => this.querySelectorAll("[data-example]").forEach(link => { link.href = `/api/import-example/${event.target.value}?format=${link.dataset.example}`; }));
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
    this.innerHTML = `<div class="ph-builder-layout"><section class="ph-card"><p class="ph-eyebrow">Schema</p><h3>Custom columns</h3><p class="ph-muted">Add typed fields for any country, programme, or workflow. PHFrame uses the type for validation, forms, storage, imports, and visualization choices.</p><div class="ph-field"><label for="ph-builder-dataset">Dataset</label><select id="ph-builder-dataset">${datasets}</select></div><div data-fields></div></section><section class="ph-card"><p class="ph-eyebrow">Add column</p><h3>Define a field</h3><form class="ph-stack"><div class="ph-field"><label for="ph-field-name">Column name</label><input id="ph-field-name" name="name" required pattern="[a-z][a-z0-9_]*" placeholder="country_code"><small>Lowercase letters, numbers, and underscores</small></div><div class="ph-field"><label for="ph-field-label">Display label</label><input id="ph-field-label" name="label" placeholder="Country code"></div><div class="ph-field"><label for="ph-field-type">Data type</label><select id="ph-field-type" name="type">${types}</select></div><button class="ph-button" type="submit">Add column</button><p role="status" class="ph-status"></p></form></section></div>`;
    this.querySelector("#ph-builder-dataset").addEventListener("change", () => this.drawFields());
    this.querySelector("form").addEventListener("submit", event => this.addField(event));
    this.drawFields();
  }
  drawFields() {
    const dataset = this.querySelector("#ph-builder-dataset").value;
    const fields = this._metadata.datasets[dataset].fields;
    this.querySelector("[data-fields]").innerHTML = `<div class="ph-field-list">${Object.entries(fields).map(([name, schema]) => `<div><span class="ph-type-badge">${PHFrame.escape(schema.type)}</span><b>${PHFrame.escape(schema.label || name.replaceAll("_", " "))}</b><code>${PHFrame.escape(name)}</code></div>`).join("")}</div>`;
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
    this.innerHTML = `<div class="ph-editor-toolbar" aria-label="Text formatting"><button type="button" data-command="bold"><b>B</b></button><button type="button" data-command="italic"><i>I</i></button><button type="button" data-command="underline"><u>U</u></button><button type="button" data-command="insertUnorderedList">• List</button><button type="button" data-link>Link</button></div><div class="ph-rich-editor" contenteditable="true" role="textbox" aria-multiline="true">${this._value || ""}</div>`;
    this.querySelectorAll("[data-command]").forEach(button => button.addEventListener("click", () => { document.execCommand(button.dataset.command); this.querySelector("[contenteditable]").focus(); }));
    this.querySelector("[data-link]").addEventListener("click", () => { const url = prompt("Enter an https:// link"); if (url && /^https?:\/\//i.test(url)) document.execCommand("createLink", false, url); });
  }
}

class PHSettingsPanel extends PHElement {
  set settings(value) { this._settings = value; if (this.isConnected) this.render(); }
  render() {
    if (!this._settings) return;
    const navigation = Object.entries(this._settings.navigation).map(([route, item]) => `<div class="ph-nav-setting"><label><input type="checkbox" name="nav_visible_${route}" ${item.visible ? "checked" : ""}> Show</label><div class="ph-field"><label for="ph-nav-${route}">${PHFrame.escape(route)}</label><input id="ph-nav-${route}" name="nav_label_${route}" value="${PHFrame.escape(item.label)}"></div></div>`).join("");
    this.innerHTML = `<form class="ph-settings-grid"><section class="ph-card ph-stack"><div><p class="ph-eyebrow">Identity</p><h3>Brand and header</h3></div><div class="ph-field"><label>Brand name</label><input name="brand_name" value="${PHFrame.escape(this._settings.brand_name)}"></div><div class="ph-field"><label>Header title</label><input name="header_title" value="${PHFrame.escape(this._settings.header_title)}"></div><div class="ph-field"><label>Dashboard title</label><input name="dashboard_title" value="${PHFrame.escape(this._settings.dashboard_title)}" placeholder="Use configured dashboard title"></div><div class="ph-form-grid"><div class="ph-field"><label>Logo</label><input type="file" name="logo" accept=".png,.jpg,.jpeg,.webp"></div><div class="ph-field"><label>Favicon</label><input type="file" name="favicon" accept=".png,.jpg,.jpeg,.webp,.ico"></div></div></section><section class="ph-card ph-stack"><div><p class="ph-eyebrow">Appearance</p><h3>Colors and theme</h3></div><div class="ph-color-setting"><input name="primary_color_picker" type="color" value="${PHFrame.escape(this._settings.primary_color)}" aria-label="Primary color picker"><div class="ph-field"><label>Primary color code</label><input name="primary_color" value="${PHFrame.escape(this._settings.primary_color)}" pattern="#[0-9a-fA-F]{6}"></div></div><div class="ph-field"><label>Default theme</label><select name="default_theme"><option value="light">Light</option><option value="dark">Dark</option><option value="high-contrast">High contrast</option></select></div><label><input type="checkbox" name="show_footer" ${this._settings.show_footer ? "checked" : ""}> Show footer</label><div class="ph-field"><label>Footer content</label><ph-rich-editor data-footer-editor></ph-rich-editor></div></section><section class="ph-card ph-stack"><div><p class="ph-eyebrow">Navigation</p><h3>Menu labels and visibility</h3></div><div class="ph-nav-settings">${navigation}</div></section><section class="ph-card ph-stack"><div><p class="ph-eyebrow">Access</p><h3>Public or private mode</h3></div><div class="ph-field"><label>Access mode</label><select name="access_mode"><option value="public">Public — no login required</option><option value="private">Private — login required</option></select></div><p class="ph-muted">Create or update a login when enabling private mode. Passwords are securely hashed and never returned by the API.</p><div class="ph-form-grid"><div class="ph-field"><label>Username</label><input name="username" autocomplete="username" placeholder="admin"></div><div class="ph-field"><label>New password</label><input name="password" type="password" minlength="10" autocomplete="new-password" placeholder="At least 10 characters"></div></div></section><section class="ph-card ph-stack"><div><p class="ph-eyebrow">Responsible AI</p><h3>Provider and privacy boundary</h3></div><p class="ph-provider-guide"><b>Local is the safe default.</b><span>Only configured aggregates are used. Protected fields and row-level records are never included in summary requests.</span></p><div class="ph-field"><label>AI provider</label><select name="ai_provider"><option value="local">Local evidence synthesis</option><option value="openai_compatible">External OpenAI-compatible API</option></select></div><div class="ph-field"><label>Model</label><input name="ai_model" value="${PHFrame.escape(this._settings.ai_model)}"></div><div class="ph-field"><label>HTTPS chat-completions endpoint</label><input name="ai_endpoint" type="url" value="${PHFrame.escape(this._settings.ai_endpoint)}" placeholder="https://provider.example/v1/chat/completions"></div><div class="ph-field"><label>API key environment-variable name</label><input name="ai_api_key_env" value="${PHFrame.escape(this._settings.ai_api_key_env)}" placeholder="PHFRAME_AI_API_KEY"></div><label><input type="checkbox" name="allow_external_ai" ${this._settings.allow_external_ai ? "checked" : ""}> I explicitly allow aggregate evidence to leave this server</label></section><div class="ph-settings-save"><button class="ph-button" type="submit">Save system settings</button><p role="status" class="ph-status"></p></div></form>`;
    this.querySelector('[name="default_theme"]').value = this._settings.default_theme;
    this.querySelector('[name="access_mode"]').value = this._settings.access_mode;
    this.querySelector('[name="ai_provider"]').value = this._settings.ai_provider;
    this.querySelector("[data-footer-editor]").value = this._settings.footer_html;
    const picker = this.querySelector('[name="primary_color_picker"]'), code = this.querySelector('[name="primary_color"]');
    picker.addEventListener("input", () => code.value = picker.value); code.addEventListener("input", () => { if (/^#[0-9a-f]{6}$/i.test(code.value)) picker.value = code.value; });
    this.querySelector("form").addEventListener("submit", event => this.save(event));
  }
  async upload(kind, file) {
    if (!file?.size) return;
    const response = await fetch(`/api/settings/assets/${kind}?filename=${encodeURIComponent(file.name)}`, { method: "POST", headers: { "content-type": "application/octet-stream", accept: "application/json" }, body: file });
    if (!response.ok) throw new Error((await response.json()).error?.message || `${kind} upload failed.`);
  }
  async save(event) {
    event.preventDefault(); const form = event.currentTarget, status = form.querySelector("[role=status]"), data = new FormData(form);
    try {
      await this.upload("logo", data.get("logo")); await this.upload("favicon", data.get("favicon"));
      const navigation = Object.fromEntries(Object.keys(this._settings.navigation).map(route => [route, { label: String(data.get(`nav_label_${route}`) || route), visible: data.has(`nav_visible_${route}`) }]));
      const payload = { brand_name: data.get("brand_name"), header_title: data.get("header_title"), dashboard_title: data.get("dashboard_title"), primary_color: data.get("primary_color"), default_theme: data.get("default_theme"), footer_html: this.querySelector("[data-footer-editor]").value, show_footer: data.has("show_footer"), access_mode: data.get("access_mode"), navigation, username: data.get("username"), password: data.get("password"), ai_provider: data.get("ai_provider"), ai_model: data.get("ai_model"), ai_endpoint: data.get("ai_endpoint"), ai_api_key_env: data.get("ai_api_key_env"), allow_external_ai: data.has("allow_external_ai") };
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
    const pages = (this._settings.pages || []).map(page => `<article class="ph-card"><div class="ph-widget-header"><div><p class="ph-eyebrow">${page.type}</p><h3>${PHFrame.escape(page.title)}</h3><p class="ph-muted">${page.type === "external" ? PHFrame.escape(page.url) : `${page.blocks.length} blocks`}</p></div><button class="ph-icon-danger" data-delete-page="${PHFrame.escape(page.slug)}">×</button></div>${page.type === "internal" ? `<button class="ph-button ph-button-secondary" data-edit-page="${PHFrame.escape(page.slug)}">Design page</button>` : `<a class="ph-button" href="${PHFrame.escape(page.url)}" target="_blank" rel="noopener noreferrer">Open link</a>`}</article>`).join("") || `<div class="ph-empty-state"><span>＋</span><p>No custom pages yet.</p></div>`;
    this.innerHTML = `<div class="ph-builder-layout"><section><div class="ph-grid">${pages}</div></section><section class="ph-card"><p class="ph-eyebrow">Navigation page</p><h3>Create a page or link</h3><form class="ph-stack" data-page-form><div class="ph-field"><label>Page title</label><input name="title" required placeholder="Programme overview"></div><div class="ph-field"><label>Navigation label</label><input name="nav_label" required placeholder="Overview"></div><div class="ph-field"><label>Slug</label><input name="slug" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" placeholder="programme-overview"></div><div class="ph-field"><label>Page type</label><select name="type"><option value="internal">Drag-and-drop page</option><option value="external">External URL redirect</option></select></div><div class="ph-field" data-page-url hidden><label>External URL</label><input name="url" type="url" placeholder="https://example.org"></div><button class="ph-button">Create page</button><p role="status" class="ph-status"></p></form></section></div><div data-page-designer></div>`;
    const form = this.querySelector("[data-page-form]"), type = form.querySelector('[name="type"]'); type.addEventListener("change", () => this.querySelector("[data-page-url]").hidden = type.value !== "external"); form.addEventListener("submit", event => this.create(event));
    this.querySelectorAll("[data-edit-page]").forEach(button => button.addEventListener("click", () => this.design(button.dataset.editPage)));
    this.querySelectorAll("[data-delete-page]").forEach(button => button.addEventListener("click", () => this.remove(button.dataset.deletePage)));
  }
  async persist(pages) {
    const response = await PHFrame.send("/api/settings", "PUT", { pages }); this._settings.pages = response.data.pages; PHFrame.siteSettings.pages = response.data.pages;
  }
  async create(event) {
    event.preventDefault(); const form = event.currentTarget, data = new FormData(form), status = form.querySelector("[role=status]");
    try { const page = { title: data.get("title"), nav_label: data.get("nav_label"), slug: data.get("slug"), type: data.get("type"), url: data.get("url") || "", blocks: [] }; await this.persist([...(this._settings.pages || []), page]); this.render(); PHFrame.notify("Page created."); } catch (error) { status.textContent = error.message; }
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
    const blocks = page.blocks.map(block => this.editorBlock(block, datasets)).join("");
    const designer = this.querySelector("[data-page-designer]"); designer.innerHTML = `<section class="ph-card ph-page-designer"><div class="ph-widget-header"><div><p class="ph-eyebrow">Page designer</p><h3>${PHFrame.escape(page.title)}</h3></div><button class="ph-button" data-save-page>Save page</button></div><div class="ph-actions ph-block-tools"><button type="button" data-add-block="text">+ Text</button><button type="button" data-add-block="table">+ Table</button><button type="button" data-add-block="visualization">+ Visualization</button></div><div class="ph-page-canvas" data-page-canvas>${blocks}</div></section>`;
    page.blocks.forEach(block => { const element = designer.querySelector(`[data-block-id="${CSS.escape(block.id)}"]`); if (block.type === "text") element.querySelector("ph-rich-editor").value = block.html; if (block.type === "table") element.querySelector("[data-block-dataset]").value = block.dataset; if (block.type === "visualization") element.querySelector("[data-block-source]").value = block.source; });
    designer.querySelector("[data-save-page]").addEventListener("click", () => this.saveDesign(page)); designer.querySelectorAll("[data-add-block]").forEach(button => button.addEventListener("click", () => this.addBlock(button.dataset.addBlock, datasets))); this.bindBlocks(); designer.scrollIntoView({ behavior: "smooth" });
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
    await this.persist(this._settings.pages.map(item => item.slug === page.slug ? { ...item, blocks } : item)); this.render(); PHFrame.notify("Page saved.");
  }
}

class PHConnectorConsole extends PHElement {
  async render() {
    try {
      const [connectors, history] = await Promise.all([PHFrame.get("/api/connectors"), PHFrame.get("/api/syncs")]);
      const metadata = await PHFrame.get("/api");
      const cards = connectors.data.map(item => `<article class="ph-card"><div class="ph-widget-header"><div><p class="ph-eyebrow">${item.type.toUpperCase()}</p><h3>${PHFrame.escape(item.name)}</h3></div><button class="ph-icon-danger" data-delete="${item.name}" aria-label="Remove ${PHFrame.escape(item.name)}">×</button></div><p>Feeds <b>${PHFrame.escape(item.dataset)}</b></p><p class="ph-muted">${item.schedule_minutes ? `Every ${item.schedule_minutes} minutes · ${item.due ? "Due" : "Not due"}` : "Manual schedule"}</p><div class="ph-actions"><button class="ph-button ph-button-secondary" data-sync="${item.name}" data-dry="true">Test connection</button><ph-confirm label="Sync now" message="Pull and atomically import records from ${PHFrame.escape(item.name)}?" data-connector="${item.name}"></ph-confirm></div></article>`).join("") || `<div class="ph-empty-state"><span>⌁</span><p>No connectors yet. Create one below.</p></div>`;
      const rows = history.data.map(item => `<tr><td>${PHFrame.escape(item.created_at)}</td><td>${PHFrame.escape(item.connector)}</td><td>${item.status}</td><td>${item.imported_rows}/${item.fetched_rows}</td><td>${item.errors.map(error => PHFrame.escape(error.message)).join("; ")}</td></tr>`).join("") || `<tr><td colspan="5">No synchronization runs.</td></tr>`;
      const datasets = Object.entries(metadata.datasets).map(([name, item]) => `<option value="${name}">${PHFrame.escape(item.label)}</option>`).join("");
      this.innerHTML = `<section class="ph-card ph-stack"><div><p class="ph-eyebrow">New data source</p><h3>Add a connector</h3><p class="ph-muted">Choose a provider for guided setup. Every connector maps remote fields into a typed PHFrame dataset.</p></div><form class="ph-stack" data-connector-form><div class="ph-provider-grid"><label><input type="radio" name="type" value="api" checked><b>REST API</b><small>Any JSON endpoint</small></label><label><input type="radio" name="type" value="dhis2"><b>DHIS2</b><small>Data value sets</small></label><label><input type="radio" name="type" value="kobo"><b>KoboToolbox</b><small>Form submissions</small></label><label><input type="radio" name="type" value="odk"><b>ODK Central</b><small>OData submissions</small></label></div><div class="ph-provider-guide" data-provider-guide></div><div class="ph-form-grid"><div class="ph-field"><label>Name</label><input name="name" required pattern="[a-z][a-z0-9_]*" placeholder="global_cases_api"></div><div class="ph-field"><label>Destination dataset</label><select name="dataset">${datasets}</select></div><div class="ph-field"><label>Server base URL</label><input name="base_url" type="url" required placeholder="https://api.example.org"></div><div class="ph-field"><label data-resource-label>Resource path</label><input name="resource" required placeholder="v1/events"></div><div class="ph-field" data-records-path><label>Records path</label><input name="records_path" placeholder="data.records"></div><div class="ph-field"><label>Schedule (minutes)</label><input name="schedule_minutes" type="number" min="1" placeholder="60"></div><div class="ph-field"><label>Token environment variable</label><input name="token_env" placeholder="HEALTH_API_TOKEN"></div><div class="ph-field"><label>Username environment variable</label><input name="username_env" placeholder="ODK_USERNAME"></div><div class="ph-field"><label>Password environment variable</label><input name="password_env" placeholder="ODK_PASSWORD"></div></div><div class="ph-field"><label>Field mapping (JSON)</label><textarea name="mapping" rows="5" required placeholder='{"source.id":"record_id","source.country":"country"}'></textarea><small>Left: provider source path. Right: destination dataset column.</small></div><button class="ph-button" type="submit">Create connector</button><p class="ph-status" role="status"></p></form></section><section><h3>Configured connectors</h3><div class="ph-grid">${cards}</div></section><section class="ph-card"><h3>Synchronization history</h3><div class="ph-table-wrap"><table class="ph-table"><thead><tr><th>Time</th><th>Connector</th><th>Status</th><th>Rows</th><th>Errors</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
      this.querySelectorAll("[data-sync]").forEach(button => button.addEventListener("click", () => this.sync(button.dataset.sync, true)));
      this.querySelectorAll("ph-confirm[data-connector]").forEach(confirm => confirm.addEventListener("ph-confirmed", () => this.sync(confirm.dataset.connector, false)));
      this.querySelectorAll("[data-delete]").forEach(button => button.addEventListener("click", () => this.remove(button.dataset.delete)));
      this.querySelector("[data-connector-form]").addEventListener("submit", event => this.create(event));
      this.querySelectorAll('[name="type"]').forEach(input => input.addEventListener("change", () => this.providerChanged()));
      this.providerChanged();
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
  async create(event) {
    event.preventDefault(); const form = event.currentTarget, status = form.querySelector("[role=status]");
    try {
      const raw = Object.fromEntries(new FormData(form));
      const auth = {}; if (raw.token_env) auth.token_env = raw.token_env; if (raw.username_env) auth.username_env = raw.username_env; if (raw.password_env) auth.password_env = raw.password_env;
      const payload = { ...raw, mapping: JSON.parse(raw.mapping), auth };
      delete payload.token_env; delete payload.username_env; delete payload.password_env; if (!payload.records_path) delete payload.records_path; if (!payload.schedule_minutes) delete payload.schedule_minutes;
      await PHFrame.send("/api/connectors", "POST", payload); PHFrame.notify("Connector created."); this.render();
    } catch (error) { status.textContent = error.message; status.className = "ph-status ph-error"; }
  }
  providerChanged() {
    const type = this.querySelector('[name="type"]:checked').value;
    const presets = {
      api: ["Generic REST API", "Enter the endpoint path and optional nested records path. Bearer token and basic authentication are supported through environment variables.", "v1/events", "Resource path", true],
      dhis2: ["DHIS2 data value set", "Enter the DHIS2 server URL and Data Set UID. Use a token environment variable for an ApiToken or username/password environment variables for Basic authentication.", "BfMAe6Itzgt", "Data Set UID", false],
      kobo: ["KoboToolbox submissions", "Enter the Kobo server URL and Asset UID. The token environment variable is sent using Kobo's Token authentication scheme.", "aR9xExampleAsset", "Asset UID", false],
      odk: ["ODK Central submissions", "Enter the Central URL and PROJECT_ID/FORM_ID. Configure token or Basic authentication with environment-variable names.", "12/household_survey", "Project ID / Form ID", false]
    }[type];
    this.querySelector("[data-provider-guide]").innerHTML = `<b>${presets[0]}</b><span>${presets[1]}</span>`;
    this.querySelector("[name=resource]").placeholder = presets[2]; this.querySelector("[data-resource-label]").textContent = presets[3]; this.querySelector("[data-records-path]").hidden = !presets[4];
  }
  async remove(name) {
    if (!confirm(`Remove connector ${name}? Imported records will remain.`)) return;
    try { await PHFrame.send(`/api/connectors/${name}`, "DELETE"); PHFrame.notify("Connector removed."); this.render(); } catch (error) { PHFrame.notify(error.message); }
  }
  async sync(name, dryRun) {
    try {
      const response = await PHFrame.send(`/api/connectors/${name}/sync?dry_run=${dryRun}`, "POST", {});
      PHFrame.notify(`${name}: ${response.data.status}`);
      this.render();
    } catch (error) { PHFrame.notify(`${name}: ${error.message}`); }
  }
}

class PHAIWorkspace extends PHElement {
  set metadata(value) { this._metadata = value; if (this.isConnected) this.render(); }
  async render() {
    if (!this._metadata) return;
    this.innerHTML = `<p class="ph-muted" role="status">Loading responsible AI workspace…</p>`;
    try {
      const [summaries, audit] = await Promise.all([PHFrame.get("/api/ai/summaries"), PHFrame.get("/api/ai/audit")]);
      const datasets = Object.entries(this._metadata.datasets).map(([name, item]) => `<option value="${name}">${PHFrame.escape(item.label)}</option>`).join("");
      const cards = summaries.data.map(item => this.summaryCard(item)).join("") || `<div class="ph-empty-state"><span>AI</span><p>No AI-assisted drafts yet.</p></div>`;
      const events = audit.data.map(item => `<tr><td>${PHFrame.escape(item.created_at)}</td><td>${PHFrame.escape(item.event)}</td><td>${PHFrame.escape(item.actor)}</td><td>${item.summary_id ?? "—"}</td></tr>`).join("") || `<tr><td colspan="4">No AI activity yet.</td></tr>`;
      this.innerHTML = `<div class="ph-ai-notice"><b>Human-controlled assistance</b><span>PHFrame uses aggregate evidence only. Output is a draft until a person approves it; do not use it as diagnosis or clinical advice.</span></div><div class="ph-ai-layout"><section class="ph-card ph-stack"><div><p class="ph-eyebrow">Evidence summary</p><h3>Create an AI-assisted draft</h3></div><form class="ph-stack" data-ai-form><div class="ph-field"><label>Your name (public mode audit)</label><input name="author" required placeholder="Amina Rahman"></div><div class="ph-field"><label>Briefing title</label><input name="title" required value="Public health situation summary"></div><div class="ph-field"><label>Purpose and audience</label><textarea name="purpose" rows="4" placeholder="Weekly surveillance meeting for programme managers"></textarea></div><button class="ph-button">Generate evidence-backed draft</button><p class="ph-muted">The request contains indicators, grouped counts, alert states, and quality scores — never protected or row-level data.</p><p role="status" class="ph-status"></p></form></section><section class="ph-card ph-stack"><div><p class="ph-eyebrow">De-identification</p><h3>Preview a safer dataset view</h3></div><form class="ph-actions" data-deid-form><div class="ph-field"><label>Dataset</label><select name="dataset">${datasets}</select></div><div class="ph-field"><label>Rows</label><input name="limit" type="number" min="1" max="100" value="10"></div><button class="ph-button ph-button-secondary">Preview</button></form><p class="ph-muted">Protected identifiers are removed; dates become years and ages become bands. This reduces exposure but is not a legal certification.</p><div data-deid-result></div></section></div><section><div class="ph-widget-header"><div><p class="ph-eyebrow">Human approval queue</p><h3>Drafts and decisions</h3></div></div><div class="ph-ai-summaries">${cards}</div></section><section class="ph-card"><p class="ph-eyebrow">Audit history</p><h3>Immutable AI events</h3><div class="ph-table-wrap"><table class="ph-table"><thead><tr><th>Time</th><th>Event</th><th>Actor</th><th>Summary</th></tr></thead><tbody>${events}</tbody></table></div></section>`;
      this.querySelector("[data-ai-form]").addEventListener("submit", event => this.generate(event));
      this.querySelector("[data-deid-form]").addEventListener("submit", event => this.preview(event));
      this.querySelectorAll("[data-review]").forEach(button => button.addEventListener("click", () => this.review(button.dataset.id, button.dataset.review)));
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
  summaryCard(item) {
    const review = item.status === "draft" ? `<div class="ph-actions"><button class="ph-button" data-review="approved" data-id="${item.id}">Approve</button><button class="ph-button ph-button-secondary" data-review="rejected" data-id="${item.id}">Reject</button></div>` : `<p class="ph-review-note"><b>Reviewed by ${PHFrame.escape(item.reviewed_by)}</b><br>${PHFrame.escape(item.review_note)}</p>`;
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
    const reviewer = prompt("Your name for the audit history (public mode)");
    if (!reviewer?.trim()) return;
    try { await PHFrame.send(`/api/ai/summaries/${id}/review`, "POST", { decision, note, reviewer }); PHFrame.notify(`Draft ${decision}.`); this.render(); } catch (error) { PHFrame.notify(error.message); }
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
customElements.define("ph-ai-workspace", PHAIWorkspace);
customElements.define("ph-connector-console", PHConnectorConsole);
window.PHFrame = PHFrame;
