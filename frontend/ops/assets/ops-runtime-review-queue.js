const els = {
      apiKey: document.getElementById("api-key"),
      status: document.getElementById("status-filter"),
      ownerTeam: document.getElementById("owner-team-filter"),
      assignmentState: document.getElementById("assignment-state-filter"),
      autoRefreshSeconds: document.getElementById("auto-refresh-seconds"),
      notice: document.getElementById("notice"),
      liveDot: document.getElementById("live-dot"),
      liveStatus: document.getElementById("live-status"),
      lastRefresh: document.getElementById("last-refresh"),
      ownerRollupsBody: document.getElementById("owner-rollups-body"),
      reviewsBody: document.getElementById("reviews-body"),
      queueMeta: document.getElementById("queue-meta"),
      total: document.getElementById("stat-total"),
      assigned: document.getElementById("stat-assigned"),
      unassigned: document.getElementById("stat-unassigned"),
      stale: document.getElementById("stat-stale"),
      staleUnassigned: document.getElementById("stat-stale-unassigned"),
      bulkAssignTo: document.getElementById("bulk-assign-to"),
      bulkAssignTeam: document.getElementById("bulk-assign-team"),
      bulkAssignBy: document.getElementById("bulk-assign-by"),
      bulkAssignNote: document.getElementById("bulk-assign-note"),
      bulkResolveBy: document.getElementById("bulk-resolve-by"),
      bulkResolveReason: document.getElementById("bulk-resolve-reason"),
      bulkResolveNote: document.getElementById("bulk-resolve-note"),
      refreshBtn: document.getElementById("refresh-btn"),
      pauseBtn: document.getElementById("pause-btn"),
      downloadCsvBtn: document.getElementById("download-csv-btn"),
      topOwnerBtn: document.getElementById("use-first-owner-btn"),
      bulkAssignBtn: document.getElementById("bulk-assign-btn"),
      bulkResolveBtn: document.getElementById("bulk-resolve-btn"),
    };

let latestQueue = null;
const statState = { total: 0, assigned: 0, unassigned: 0, stale: 0, staleUnassigned: 0 };
const keyStore = "lsa-ops-api-key";
const autoRefreshStore = "lsa-runtime-review-queue-auto-refresh-seconds";
const autoRefreshPausedStore = "lsa-runtime-review-queue-auto-refresh-paused";
const core = window.LSAOps;
core.restoreApiKey(els.apiKey, keyStore);
els.autoRefreshSeconds.value = localStorage.getItem(autoRefreshStore) || "30";
let autoRefreshTimer = null;
let autoRefreshPaused = localStorage.getItem(autoRefreshPausedStore) === "1";
let loadInFlight = false;

function setNotice(text, tone = "muted") {
  core.setNotice(els.notice, text, tone);
}

    function currentParams() {
      const params = new URLSearchParams();
      if (els.status.value) params.set("status", els.status.value);
      if (els.ownerTeam.value.trim()) params.set("owner_team", els.ownerTeam.value.trim());
      if (els.assignmentState.value) params.set("assignment_state", els.assignmentState.value);
      return params;
    }

async function fetchJson(url, options = {}) {
  return core.fetchJson(url, els.apiKey, keyStore, options);
}

async function fetchBlob(url) {
  return core.fetchBlob(url, els.apiKey, keyStore);
}

    function badge(status) {
      return `<span class="badge ${status}">${status.replaceAll("_", " ")}</span>`;
    }

function animateNumber(el, key, next) {
  core.animateNumber(el, statState, key, next);
}

function animateRows(selector) {
  core.animateRows(selector);
}

function pulsePanels() {
  core.pulse(".stat,.panel,.toolbar,.nav", 8, 40, 520);
}

function pulseLiveDot() {
  core.pulseLiveDot(els.liveDot);
}

function stopLiveDot() {
  core.stopLiveDot(els.liveDot);
}

    function updateAutoRefreshUi() {
      const seconds = Number(els.autoRefreshSeconds.value || 0);
      els.liveDot.classList.toggle("live", !autoRefreshPaused && seconds > 0);
      els.liveDot.classList.toggle("paused", autoRefreshPaused || seconds === 0);
      els.pauseBtn.textContent = autoRefreshPaused ? "Resume Auto Refresh" : "Pause Auto Refresh";
      els.liveStatus.textContent = seconds === 0 ? "Auto refresh off." : autoRefreshPaused ? `Auto refresh paused (${seconds}s).` : `Auto refresh every ${seconds}s.`;
      if (!autoRefreshPaused && seconds > 0) pulseLiveDot(); else stopLiveDot();
    }

function updateLastRefresh() {
  core.stampLastRefresh(els.lastRefresh);
}

    function syncAutoRefresh() {
      localStorage.setItem(autoRefreshStore, els.autoRefreshSeconds.value);
      localStorage.setItem(autoRefreshPausedStore, autoRefreshPaused ? "1" : "0");
      if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
      }
      const seconds = Number(els.autoRefreshSeconds.value || 0);
      updateAutoRefreshUi();
      if (autoRefreshPaused || seconds === 0) return;
      autoRefreshTimer = setInterval(() => {
        if (!loadInFlight) loadQueue({ silent: true });
      }, seconds * 1000);
    }

    function renderQueue(queue) {
      latestQueue = queue;
      animateNumber(els.total, "total", queue.total_reviews);
      animateNumber(els.assigned, "assigned", queue.assigned_reviews);
      animateNumber(els.unassigned, "unassigned", queue.unassigned_reviews);
      animateNumber(els.stale, "stale", queue.stale_reviews);
      animateNumber(els.staleUnassigned, "staleUnassigned", queue.stale_unassigned_reviews);
      els.queueMeta.textContent =
        `Environment ${queue.environment_name}. Oldest review age: ${queue.oldest_review_age_hours ?? "n/a"} hours.`;

      els.ownerRollupsBody.innerHTML = queue.owner_team_rollups.length
        ? queue.owner_team_rollups.map((row) => `
            <tr>
              <td><button class="ghost owner-filter" data-owner="${row.owner_team}">${row.owner_team}</button></td>
              <td>${row.total_reviews}</td>
              <td>${row.assigned_reviews}</td>
              <td>${row.unassigned_reviews}</td>
              <td class="${row.stale_reviews ? "tone-bad" : ""}">${row.stale_reviews}</td>
            </tr>
          `).join("")
        : `<tr><td colspan="5" class="muted">No owner-team data.</td></tr>`;

      els.reviewsBody.innerHTML = queue.reviews.length
        ? queue.reviews.map((row) => `
            <tr>
              <td class="mono">${row.review_id}</td>
              <td>${badge(row.status)}</td>
              <td>${row.owner_team || "<span class='muted'>unowned</span>"}</td>
              <td>${row.assigned_to || "<span class='muted'>unassigned</span>"}</td>
              <td>${row.next_due_at ? `${row.due_in_hours ?? "?"}h left` : "<span class='muted'>n/a</span>"}</td>
              <td>${row.summary}</td>
            </tr>
          `).join("")
        : `<tr><td colspan="6" class="muted">No reviews matched.</td></tr>`;

      document.querySelectorAll(".owner-filter").forEach((button) => {
        button.addEventListener("click", () => {
          els.ownerTeam.value = button.dataset.owner === "unowned" ? "" : button.dataset.owner;
          loadQueue();
        });
      });
      animateRows("#owner-rollups-body tr");
      animateRows("#reviews-body tr");
    }

    async function loadQueue(options = {}) {
      const silent = Boolean(options.silent);
      if (loadInFlight) return;
      loadInFlight = true;
      if (!silent) setNotice("Loading queue...");
      try {
        const queue = await fetchJson(`/maintenance/control-plane-runtime-validation-review-queue?${currentParams().toString()}`);
        renderQueue(queue);
        pulsePanels();
        updateLastRefresh();
        if (!silent) setNotice("Queue loaded.", "tone-good");
      } catch (error) {
        setNotice(String(error.message || error), "tone-bad");
      } finally {
        loadInFlight = false;
      }
    }

    async function bulkAssign() {
      try {
        const payload = {
          assigned_to: els.bulkAssignTo.value.trim(),
          assigned_to_team: els.bulkAssignTeam.value.trim() || null,
          assigned_by: els.bulkAssignBy.value.trim(),
          assignment_note: els.bulkAssignNote.value.trim() || null,
          status: els.status.value || null,
          owner_team: els.ownerTeam.value.trim() || null,
          assignment_state: els.assignmentState.value || null,
        };
        const result = await fetchJson("/maintenance/control-plane-runtime-validation-reviews/bulk-assign", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setNotice(`Bulk assign changed ${result.changed_count} review(s).`, "tone-good");
        await loadQueue();
      } catch (error) {
        setNotice(String(error.message || error), "tone-bad");
      }
    }

    async function bulkResolve() {
      try {
        const payload = {
          resolved_by: els.bulkResolveBy.value.trim(),
          resolution_reason: els.bulkResolveReason.value.trim() || "manual_resolution",
          resolution_note: els.bulkResolveNote.value.trim() || null,
          status: els.status.value || null,
          owner_team: els.ownerTeam.value.trim() || null,
          assignment_state: els.assignmentState.value || null,
        };
        const result = await fetchJson("/maintenance/control-plane-runtime-validation-reviews/bulk-resolve", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setNotice(`Bulk resolve changed ${result.changed_count} review(s).`, "tone-good");
        await loadQueue();
      } catch (error) {
        setNotice(String(error.message || error), "tone-bad");
      }
    }

    async function downloadCsv() {
      try {
        setNotice("Building CSV export...");
        const blob = await fetchBlob(`/maintenance/control-plane-runtime-validation-review-queue.csv?${currentParams().toString()}`);
        const link = document.createElement("a");
        const owner = els.ownerTeam.value.trim() || "all";
        link.href = URL.createObjectURL(blob);
        link.download = `runtime-validation-review-queue-${owner}.csv`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(link.href);
        setNotice("CSV ready.", "tone-good");
      } catch (error) {
        setNotice(String(error.message || error), "tone-bad");
      }
    }

    els.refreshBtn.addEventListener("click", loadQueue);
    els.pauseBtn.addEventListener("click", () => {
      autoRefreshPaused = !autoRefreshPaused;
      syncAutoRefresh();
    });
    els.autoRefreshSeconds.addEventListener("change", () => {
      autoRefreshPaused = false;
      syncAutoRefresh();
    });
    els.downloadCsvBtn.addEventListener("click", downloadCsv);
    els.bulkAssignBtn.addEventListener("click", bulkAssign);
    els.bulkResolveBtn.addEventListener("click", bulkResolve);
    els.topOwnerBtn.addEventListener("click", () => {
      if (!latestQueue || !latestQueue.owner_team_rollups.length) return;
      const top = latestQueue.owner_team_rollups[0].owner_team;
      els.ownerTeam.value = top === "unowned" ? "" : top;
      loadQueue();
    });

    syncAutoRefresh();
    loadQueue();
