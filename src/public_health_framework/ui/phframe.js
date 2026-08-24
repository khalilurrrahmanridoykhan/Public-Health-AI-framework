const PHFrame = {
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
  }
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
      this.draw();
      addEventListener("hashchange", () => this.route());
    } catch (error) {
      this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`;
    }
  }
  draw() {
    this.innerHTML = `<a class="ph-skip-link" href="#main">Skip to content</a>
      <div class="ph-shell"><header class="ph-header"><h1 class="ph-brand">PHFrame · ${PHFrame.escape(this.metadata.project)}</h1>
      <nav class="ph-nav" aria-label="Primary"><a href="#/dashboard" data-route="dashboard">Dashboard</a><a href="#/records" data-route="records">Records</a><a href="#/quality" data-route="quality">Data quality</a></nav></header>
      <main class="ph-main" id="main" tabindex="-1"><div id="ph-view"></div></main></div>`;
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
      status.textContent = "Record saved.";
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
      this.innerHTML = `<article class="ph-card"><h3>${PHFrame.escape(this.getAttribute("title") || response.data.label)}</h3><p class="ph-kpi-value">${value == null ? "—" : new Intl.NumberFormat().format(value)}</p><p class="ph-muted">${PHFrame.escape(response.data.operation)}</p></article>`;
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
}

class PHIndicatorChart extends PHElement {
  async render() {
    try {
      const response = await PHFrame.get(`/api/dimensions/${this.getAttribute("dimension")}`);
      const values = response.data.values;
      const maximum = Math.max(1, ...values.map(item => item.count));
      const width = 600, row = 38;
      const bars = values.map((item, index) => `<g transform="translate(0 ${index * row})"><text x="0" y="20">${PHFrame.escape(item.value ?? "Unknown")}</text><rect class="ph-chart-bar" x="150" y="5" width="${Math.round(item.count / maximum * 400)}" height="22"><title>${item.count}</title></rect><text x="560" y="20" text-anchor="end">${item.count}</text></g>`).join("");
      this.innerHTML = `<article class="ph-card ph-widget-wide"><h3>${PHFrame.escape(this.getAttribute("title") || response.data.label)}</h3><svg class="ph-chart" viewBox="0 0 ${width} ${Math.max(row, values.length * row)}" role="img" aria-label="${PHFrame.escape(response.data.label)} bar chart">${bars}</svg>${this.table(values, "Value", "Count")}</article>`;
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
  table(values, first, second) {
    return `<table class="ph-sr-only"><caption>${PHFrame.escape(this.getAttribute("title") || "Chart data")}</caption><thead><tr><th>${first}</th><th>${second}</th></tr></thead><tbody>${values.map(item => `<tr><td>${PHFrame.escape(item.value)}</td><td>${item.count}</td></tr>`).join("")}</tbody></table>`;
  }
}

class PHEpiCurve extends PHElement {
  async render() {
    const query = new URLSearchParams({ date_field: this.getAttribute("date-field") });
    if (this.getAttribute("value-field")) query.set("value_field", this.getAttribute("value-field"));
    try {
      const response = await PHFrame.get(`/api/epi-curve/${this.getAttribute("dataset")}?${query}`);
      const values = response.data;
      const maximum = Math.max(1, ...values.map(item => item.value));
      const points = values.map((item, index) => `${values.length === 1 ? 300 : index / (values.length - 1) * 560 + 20},${200 - item.value / maximum * 170}`).join(" ");
      const circles = points.split(" ").filter(Boolean).map((point, index) => { const [x, y] = point.split(","); return `<circle class="ph-chart-point" cx="${x}" cy="${y}" r="4"><title>${PHFrame.escape(values[index].date)}: ${values[index].value}</title></circle>`; }).join("");
      this.innerHTML = `<article class="ph-card ph-widget-wide"><h3>${PHFrame.escape(this.getAttribute("title") || "Epidemiological curve")}</h3><svg class="ph-chart" viewBox="0 0 600 220" role="img" aria-label="Cases by reporting date"><polyline class="ph-chart-line" points="${points}"></polyline>${circles}</svg><table class="ph-sr-only"><caption>Epidemiological curve data</caption><thead><tr><th>Date</th><th>Value</th></tr></thead><tbody>${values.map(item => `<tr><td>${PHFrame.escape(item.date)}</td><td>${item.value}</td></tr>`).join("")}</tbody></table></article>`;
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
  }
}

class PHDashboard extends PHElement {
  async render() {
    try {
      const response = await PHFrame.get(`/api/dashboards/${this.getAttribute("name")}`);
      const widgets = response.data.widgets.map(widget => {
        if (widget.type === "kpi") return `<ph-kpi title="${PHFrame.escape(widget.title)}" indicator="${widget.indicator}"></ph-kpi>`;
        if (widget.type === "chart") return `<ph-indicator-chart title="${PHFrame.escape(widget.title)}" dimension="${widget.dimension}"></ph-indicator-chart>`;
        return `<ph-epi-curve title="${PHFrame.escape(widget.title)}" dataset="${widget.dataset}" date-field="${widget.date_field}" value-field="${widget.value_field || ""}"></ph-epi-curve>`;
      }).join("");
      this.innerHTML = `<h2>${PHFrame.escape(response.data.label)}</h2><div class="ph-grid">${widgets}</div>`;
    } catch (error) { this.innerHTML = `<p class="ph-error" role="alert">${PHFrame.escape(error.message)}</p>`; }
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
customElements.define("ph-dashboard", PHDashboard);
window.PHFrame = PHFrame;
