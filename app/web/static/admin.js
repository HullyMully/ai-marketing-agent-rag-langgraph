/* Admin panel client: renders persisted leads/tickets from the local API. */
(function () {
  "use strict";

  var state = { leads: [], tickets: [], metrics: null };

  var els = {
    brand: document.getElementById("brand-name"),
    refresh: document.getElementById("admin-refresh"),
    conversations: document.getElementById("admin-conversations"),
    leads: document.getElementById("admin-leads"),
    tickets: document.getElementById("admin-tickets"),
    resolved: document.getElementById("admin-resolved"),
    leadFilter: document.getElementById("lead-filter"),
    leadsBody: document.getElementById("leads-body"),
    ticketsList: document.getElementById("tickets-list")
  };

  function getJSON(url) {
    return fetch(url).then(function (r) {
      return r.ok ? r.json() : null;
    }).catch(function () { return null; });
  }

  function pct(x) {
    return Math.round((Number(x) || 0) * 100) + "%";
  }

  function fmtDate(value) {
    if (!value) { return "—"; }
    var d = new Date(value);
    if (Number.isNaN(d.getTime())) { return "—"; }
    return d.toLocaleDateString([], { month: "short", day: "numeric" }) + " " +
      d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function matchesLead(lead, query) {
    if (!query) { return true; }
    var haystack = [
      lead.name, lead.company, lead.contact,
      lead.service_interest, lead.budget_range, lead.status
    ].join(" ").toLowerCase();
    return haystack.indexOf(query.toLowerCase()) !== -1;
  }

  function renderMetrics() {
    var m = state.metrics || {};
    els.conversations.textContent = m.conversations ?? "0";
    els.leads.textContent = m.leads ?? state.leads.length;
    els.tickets.textContent = m.tickets ?? state.tickets.length;
    els.resolved.textContent = pct(m.resolved_by_ai_rate || 0);
  }

  function renderLeads() {
    var query = els.leadFilter.value.trim();
    var leads = state.leads.filter(function (lead) { return matchesLead(lead, query); });
    els.leadsBody.innerHTML = "";

    if (!leads.length) {
      var empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="6" class="admin-empty">No leads yet.</td>';
      els.leadsBody.appendChild(empty);
      return;
    }

    leads.forEach(function (lead) {
      var tr = document.createElement("tr");
      tr.innerHTML = [
        '<td><b>' + esc(lead.name || "Unknown") + '</b><span>' + esc(lead.contact || "—") + '</span></td>',
        '<td>' + esc(lead.company || "—") + '</td>',
        '<td>' + esc(lead.service_interest || "—") + '</td>',
        '<td>' + esc(lead.budget_range || "—") + '</td>',
        '<td><span class="status-pill">' + esc(lead.status || "new") + '</span></td>',
        '<td>' + esc(fmtDate(lead.created_at)) + '</td>'
      ].join("");
      els.leadsBody.appendChild(tr);
    });
  }

  function renderTickets() {
    els.ticketsList.innerHTML = "";
    if (!state.tickets.length) {
      els.ticketsList.innerHTML = '<div class="admin-empty">No tickets yet.</div>';
      return;
    }
    state.tickets.slice(0, 8).forEach(function (ticket) {
      var item = document.createElement("article");
      item.className = "ticket-item";
      item.innerHTML = [
        '<div class="ticket-row"><b>TCK-' + esc(ticket.id) + '</b><span>' + esc(ticket.status || "open") + '</span></div>',
        '<p>' + esc(ticket.summary || "No summary") + '</p>',
        '<div class="ticket-meta">' + esc((ticket.reason || "request").replace(/_/g, " ")) +
          ' · ' + esc(ticket.priority || "normal") + ' · ' + esc(fmtDate(ticket.created_at)) + '</div>'
      ].join("");
      els.ticketsList.appendChild(item);
    });
  }

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, function (ch) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
      }[ch];
    });
  }

  function renderAll() {
    renderMetrics();
    renderLeads();
    renderTickets();
  }

  function load() {
    if (els.refresh) { els.refresh.disabled = true; }
    Promise.all([
      getJSON("/metrics/demo"),
      getJSON("/crm/leads"),
      getJSON("/tickets")
    ]).then(function (items) {
      state.metrics = items[0] || {};
      state.leads = Array.isArray(items[1]) ? items[1] : [];
      state.tickets = Array.isArray(items[2]) ? items[2] : [];
      renderAll();
    }).finally(function () {
      if (els.refresh) { els.refresh.disabled = false; }
    });
  }

  getJSON("/config").then(function (c) {
    if (c && c.brand_label && els.brand) { els.brand.textContent = c.brand_label; }
  });

  if (els.refresh) { els.refresh.addEventListener("click", load); }
  if (els.leadFilter) { els.leadFilter.addEventListener("input", renderLeads); }
  load();
})();
