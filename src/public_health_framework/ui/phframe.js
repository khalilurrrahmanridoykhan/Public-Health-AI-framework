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
      this.metadata = await PHFrame.get("/api");
      PHFrame.locale = this.metadata.ui?.locale || "en";
      PHFrame.customMessages = this.metadata.ui?.translations || {};
      document.documentElement.lang = PHFrame.locale;
      document.documentElement.dataset.theme = localStorage.getItem("ph-theme") || this.metadata.ui?.theme || "light";
      this.draw();
      addEventListener("hashchange", () => this.route());
    } catch (error) {
      this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`;
    }
  }
  draw() {
    this.innerHTML = `<a class="ph-skip-link" href="#main">Skip to content</a>
      <div class="ph-shell"><header class="ph-header"><h1 class="ph-brand">PHFrame · ${PHFrame.escape(this.metadata.project)}</h1>
      <nav class="ph-nav" aria-label="Primary"><a href="#/dashboard" data-route="dashboard">${PHFrame.t("dashboard")}</a><a href="#/records" data-route="records">${PHFrame.t("records")}</a><a href="#/import" data-route="import">Import</a><a href="#/connectors" data-route="connectors">Connectors</a><a href="#/quality" data-route="quality">${PHFrame.t("quality")}</a></nav>
      <label>${PHFrame.t("theme")} <select class="ph-theme" aria-label="${PHFrame.t("theme")}"><option value="light">Light</option><option value="dark">Dark</option><option value="high-contrast">High contrast</option></select></label></header>
      <main class="ph-main" id="main" tabindex="-1"><div id="ph-view"></div></main><ph-notification-center></ph-notification-center></div>`;
    const theme = this.querySelector(".ph-theme");
    theme.value = document.documentElement.dataset.theme;
    theme.addEventListener("change", () => { document.documentElement.dataset.theme = theme.value; localStorage.setItem("ph-theme", theme.value); });
    this.route();
  }
  route() {
    const route = (location.hash.match(/^#\/([^/?]+)/) || [])[1] || "dashboard";
    this.querySelectorAll("[data-route]").forEach(link => link.toggleAttribute("aria-current", link.dataset.route === route));
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
    } else if (route === "import") {
      view.innerHTML = `<h2>Import data</h2><ph-import-wizard></ph-import-wizard>`;
      view.querySelector("ph-import-wizard").metadata = this.metadata;
    } else if (route === "connectors") {
      view.innerHTML = `<h2>Connectors</h2><ph-connector-console></ph-connector-console>`;
    } else if (route === "quality") {
      view.innerHTML = `<h2>Data quality</h2><ph-quality-panel></ph-quality-panel>`;
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
      const response = await PHFrame.get(`/api/indicators/${this.getAttribute("indicator")}`);
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
      const response = await PHFrame.get(`/api/dimensions/${this.getAttribute("dimension")}`);
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
      const response = await PHFrame.get(`/api/dashboards/${this.getAttribute("name")}`);
      this.dashboard = response.data;
      this.storageKey = `ph-dashboard-layout:${this.getAttribute("name")}`;
      this.settings = this.loadSettings();
      this.draw();
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
  widgetId(widget, index) { return `${widget.type}-${widget.indicator || widget.dimension || widget.dataset || index}-${index}`; }
  defaults(widget) {
    if (widget.type === "kpi") return { visualization: "number", size: "compact", choices: [["number", "Number"], ["gauge", "Gauge"]] };
    if (widget.type === "chart") return { visualization: "bar", size: "medium", choices: [["bar", "Bar chart"], ["donut", "Donut chart"], ["table", "Data table"]] };
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
    const indexed = this.dashboard.widgets.map((widget, index) => ({ widget, index, id: this.widgetId(widget, index) }));
    const order = this.settings.order || [];
    indexed.sort((a, b) => { const ai = order.indexOf(a.id), bi = order.indexOf(b.id); return (ai < 0 ? 999 + a.index : ai) - (bi < 0 ? 999 + b.index : bi); });
    const cards = indexed.map(item => this.card(item.widget, item.index, item.id)).join("");
    this.innerHTML = `<section class="ph-dashboard-heading"><div><p class="ph-eyebrow">Surveillance overview</p><h2>${PHFrame.escape(this.dashboard.label)}</h2><p class="ph-muted">Live operational metrics and trends</p></div><div class="ph-dashboard-actions"><button class="ph-button ph-button-secondary" type="button" data-reset>Reset layout</button><span class="ph-save-state" role="status">Changes save automatically</span></div></section><div class="ph-dashboard-grid" aria-label="Customizable dashboard">${cards}</div>`;
    this.bind();
  }
  card(widget, index, id) {
    const defaults = this.defaults(widget), saved = this.settings[id] || {};
    const visualization = saved.visualization || defaults.visualization, size = saved.size || defaults.size;
    const options = defaults.choices.map(([value, label]) => `<option value="${value}" ${value === visualization ? "selected" : ""}>${label}</option>`).join("");
    const sizeOptions = [["compact", "Small"], ["medium", "Medium"], ["wide", "Wide"]].map(([value, label]) => `<option value="${value}" ${value === size ? "selected" : ""}>${label}</option>`).join("");
    let component;
    if (widget.type === "kpi") component = `<ph-kpi indicator="${widget.indicator}" visualization="${visualization}"></ph-kpi>`;
    else if (widget.type === "chart") component = `<ph-indicator-chart dimension="${widget.dimension}" visualization="${visualization}"></ph-indicator-chart>`;
    else if (widget.type === "map") component = `<ph-map dimension="${widget.dimension}" visualization="${visualization}"></ph-map>`;
    else component = `<ph-epi-curve dataset="${widget.dataset}" date-field="${widget.date_field}" value-field="${widget.value_field || ""}" visualization="${visualization}"></ph-epi-curve>`;
    return `<article class="ph-card ph-dashboard-card ph-size-${size}" data-widget-id="${id}" draggable="true"><header class="ph-widget-header"><div><p class="ph-widget-kind">${PHFrame.escape(widget.type === "epi_curve" ? "Trend" : widget.type)}</p><h3>${PHFrame.escape(widget.title)}</h3></div><button class="ph-drag-handle" type="button" aria-label="Drag ${PHFrame.escape(widget.title)}" title="Drag to reorder">⠿</button></header><div class="ph-widget-controls"><label>View<select data-visualization>${options}</select></label><label>Size<select data-size>${sizeOptions}</select></label><button type="button" data-move="up" aria-label="Move ${PHFrame.escape(widget.title)} earlier">←</button><button type="button" data-move="down" aria-label="Move ${PHFrame.escape(widget.title)} later">→</button></div>${component}</article>`;
  }
  bind() {
    this.querySelector("[data-reset]").addEventListener("click", () => { localStorage.removeItem(this.storageKey); this.settings = {}; this.draw(); PHFrame.notify("Dashboard layout reset."); });
    this.querySelectorAll(".ph-dashboard-card").forEach(card => {
      card.querySelector("[data-visualization]").addEventListener("change", event => this.updateCard(card, "visualization", event.target.value));
      card.querySelector("[data-size]").addEventListener("change", event => this.updateCard(card, "size", event.target.value));
      card.querySelectorAll("[data-move]").forEach(button => button.addEventListener("click", () => this.move(card, button.dataset.move)));
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
    if (property === "size") { card.className = `ph-card ph-dashboard-card ph-size-${value}`; }
    else { const visualization = card.querySelector("[data-visualization]").value; const component = card.querySelector("ph-kpi, ph-indicator-chart, ph-map, ph-epi-curve"); component.setAttribute("visualization", visualization); component.render(); }
    this.saveSettings();
  }
  move(card, direction) {
    const sibling = direction === "up" ? card.previousElementSibling : card.nextElementSibling;
    if (!sibling) return;
    if (direction === "up") sibling.before(card); else sibling.after(card);
    this.saveSettings(); card.querySelector(".ph-drag-handle").focus(); PHFrame.notify("Dashboard layout saved.");
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
    this.innerHTML = `<section class="ph-card ph-stack"><div class="ph-import-step"><h3>1. Choose a file</h3><div class="ph-actions"><div class="ph-field"><label for="ph-import-dataset">Dataset</label><select id="ph-import-dataset">${datasets}</select></div><div class="ph-field"><label for="ph-import-template">Saved mapping</label><select id="ph-import-template"><option value="">Automatic mapping</option>${templateOptions}</select></div><div class="ph-field"><label for="ph-import-file">CSV or Excel file</label><input id="ph-import-file" type="file" accept=".csv,.xlsx,.xlsm"></div><button class="ph-button" type="button" data-preview>Preview</button></div></div><div data-workspace></div><p role="status" class="ph-status"></p></section>`;
    this.querySelector("[data-preview]").addEventListener("click", () => this.preview());
  }
  async upload(path) {
    const file = this.querySelector("input[type=file]").files[0];
    if (!file) throw new Error("Choose a CSV or Excel file.");
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

class PHConnectorConsole extends PHElement {
  async render() {
    try {
      const [connectors, history] = await Promise.all([PHFrame.get("/api/connectors"), PHFrame.get("/api/syncs")]);
      const cards = connectors.data.map(item => `<article class="ph-card"><h3>${PHFrame.escape(item.name)}</h3><p>${item.type.toUpperCase()} → ${PHFrame.escape(item.dataset)}</p><p class="ph-muted">${item.schedule_minutes ? `Every ${item.schedule_minutes} minutes · ${item.due ? "Due" : "Not due"}` : "Manual schedule"}</p><div class="ph-actions"><button class="ph-button" data-sync="${item.name}" data-dry="true">Validate pull</button><ph-confirm label="Synchronize" message="Pull and atomically import records from ${PHFrame.escape(item.name)}?" data-connector="${item.name}"></ph-confirm></div></article>`).join("") || `<p class="ph-muted">No connectors configured.</p>`;
      const rows = history.data.map(item => `<tr><td>${PHFrame.escape(item.created_at)}</td><td>${PHFrame.escape(item.connector)}</td><td>${item.status}</td><td>${item.imported_rows}/${item.fetched_rows}</td><td>${item.errors.map(error => PHFrame.escape(error.message)).join("; ")}</td></tr>`).join("") || `<tr><td colspan="5">No synchronization runs.</td></tr>`;
      this.innerHTML = `<div class="ph-grid">${cards}</div><section class="ph-card"><h3>Synchronization history</h3><div class="ph-table-wrap"><table class="ph-table"><thead><tr><th>Time</th><th>Connector</th><th>Status</th><th>Rows</th><th>Errors</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
      this.querySelectorAll("[data-sync]").forEach(button => button.addEventListener("click", () => this.sync(button.dataset.sync, true)));
      this.querySelectorAll("ph-confirm[data-connector]").forEach(confirm => confirm.addEventListener("ph-confirmed", () => this.sync(confirm.dataset.connector, false)));
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
  async sync(name, dryRun) {
    try {
      const response = await PHFrame.send(`/api/connectors/${name}/sync?dry_run=${dryRun}`, "POST", {});
      PHFrame.notify(`${name}: ${response.data.status}`);
      this.render();
    } catch (error) { PHFrame.notify(`${name}: ${error.message}`); }
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
customElements.define("ph-connector-console", PHConnectorConsole);
window.PHFrame = PHFrame;
