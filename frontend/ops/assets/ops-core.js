window.LSAOps = {
  restoreApiKey(input, keyStore) {
    input.value = localStorage.getItem(keyStore) || "";
  },

  authHeaders(input, keyStore, includeJson = true) {
    const key = input.value.trim();
    localStorage.setItem(keyStore, key);
    const headers = key ? { "X-API-Key": key } : {};
    if (includeJson) headers["Content-Type"] = "application/json";
    return headers;
  },

  async fetchJson(url, input, keyStore, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...this.authHeaders(input, keyStore, true),
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const payload = await response.json();
        if (payload.detail) detail = payload.detail;
      } catch {}
      throw new Error(detail);
    }
    return response.json();
  },

  async fetchBlob(url, input, keyStore) {
    const response = await fetch(url, {
      headers: this.authHeaders(input, keyStore, false),
    });
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const payload = await response.json();
        if (payload.detail) detail = payload.detail;
      } catch {}
      throw new Error(detail);
    }
    return response.blob();
  },

  setNotice(el, text, tone = "muted", prefix = "") {
    el.className = prefix ? `${prefix} ${tone}` : tone;
    el.textContent = text;
  },

  animateNumber(el, state, key, next) {
    if (!window.anime) {
      el.textContent = String(next);
      state[key] = next;
      return;
    }
    const current = { value: state[key] || 0 };
    anime({
      targets: current,
      value: Number(next) || 0,
      round: 1,
      easing: "easeOutExpo",
      duration: 900,
      update() {
        el.textContent = String(current.value);
      },
    });
    state[key] = Number(next) || 0;
  },

  animateRows(selector, delay = 28, duration = 500) {
    if (!window.anime) return;
    anime({
      targets: selector,
      translateY: [14, 0],
      opacity: [0, 1],
      delay: anime.stagger(delay),
      duration,
      easing: "easeOutQuad",
    });
  },

  pulse(targets, translateY = 8, delayStart = 40, duration = 520) {
    if (!window.anime) return;
    anime({
      targets,
      opacity: [0, 1],
      translateY: [translateY, 0],
      delay: anime.stagger(35, { start: delayStart }),
      duration,
      easing: "easeOutCubic",
    });
  },

  pulseLiveDot(dotEl) {
    if (!window.anime) return;
    anime.remove(dotEl);
    anime({
      targets: dotEl,
      boxShadow: [
        "0 0 0 0 rgba(13,107,107,.28)",
        "0 0 0 12px rgba(13,107,107,0)",
      ],
      duration: 1200,
      easing: "easeOutCubic",
      loop: true,
    });
  },

  stopLiveDot(dotEl) {
    if (!window.anime) return;
    anime.remove(dotEl);
    dotEl.style.boxShadow = "0 0 0 0 rgba(13,107,107,0)";
  },

  stampLastRefresh(el) {
    el.textContent = `Last refresh: ${new Date().toLocaleTimeString()}`;
  },
};
