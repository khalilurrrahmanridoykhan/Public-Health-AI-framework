const PHFrame = {
  async get(path) {
    const response = await fetch(path, { headers: { accept: "application/json" } });
    if (!response.ok) throw new Error((await response.json()).error?.message || `Request failed (${response.status})`);
    return response.json();
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
    view.innerHTML = `<h2>${PHFrame.escape(route[0].toUpperCase() + route.slice(1))}</h2><p class="ph-muted">This view is ready for PHFrame components.</p>`;
    this.dispatchEvent(new CustomEvent("ph-route", { detail: { route, view, metadata: this.metadata } }));
  }
}

customElements.define("ph-app-shell", PHAppShell);
window.PHFrame = PHFrame;
