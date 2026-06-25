/* Admin panel client: persisted leads, inbox, KB, CRM integrations and audit. */
(function () {
  "use strict";

  var state = {
    leads: [],
    tickets: [],
    metrics: null,
    company: null,
    kbFiles: [],
    currentKbPath: "",
    crm: null,
    dispatches: [],
    ticketNotes: {},
    audit: []
  };

  var els = {
    brand: document.getElementById("brand-name"),
    refresh: document.getElementById("admin-refresh"),
    conversations: document.getElementById("admin-conversations"),
    leads: document.getElementById("admin-leads"),
    tickets: document.getElementById("admin-tickets"),
    resolved: document.getElementById("admin-resolved"),
    leadFilter: document.getElementById("lead-filter"),
    leadsBody: document.getElementById("leads-body"),
    ticketsList: document.getElementById("tickets-list"),
    companyForm: document.getElementById("company-form"),
    companySave: document.getElementById("company-save"),
    companyStatus: document.getElementById("company-save-status"),
    kbList: document.getElementById("kb-file-list"),
    kbForm: document.getElementById("kb-form"),
    kbName: document.getElementById("kb-file-name"),
    kbContent: document.getElementById("kb-content"),
    kbStatus: document.getElementById("kb-status"),
    kbNew: document.getElementById("kb-new"),
    kbDelete: document.getElementById("kb-delete"),
    kbReindex: document.getElementById("kb-reindex"),
    crmForm: document.getElementById("crm-form"),
    crmSave: document.getElementById("crm-save"),
    crmStatus: document.getElementById("crm-save-status"),
    dispatchList: document.getElementById("dispatch-list"),
    auditList: document.getElementById("audit-list")
  };

  function requestJSON(url, options) {
    return fetch(url, options || {}).then(function (r) {
      if (r.status === 204) { return null; }
      if (!r.ok) { return Promise.reject(new Error("request failed")); }
      return r.json();
    });
  }

  function getJSON(url) {
    return requestJSON(url).catch(function () { return null; });
  }

  function sendJSON(method, url, payload) {
    return requestJSON(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {})
    });
  }

  function pct(x) {
    return Math.round((Number(x) || 0) * 100) + "%";
  }

  function fmtDate(value) {
    if (!value) { return "-"; }
    var d = new Date(value);
    if (Number.isNaN(d.getTime())) { return "-"; }
    return d.toLocaleDateString([], { month: "short", day: "numeric" }) + " " +
      d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
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

  function setPill(el, text, mode) {
    if (!el) { return; }
    el.textContent = text;
    el.classList.toggle("ok", mode === "ok");
    el.classList.toggle("error", mode === "error");
  }

  function renderMetrics() {
    var m = state.metrics || {};
    els.conversations.textContent = m.conversations ?? "0";
    els.leads.textContent = m.leads ?? state.leads.length;
    els.tickets.textContent = m.tickets ?? state.tickets.length;
    els.resolved.textContent = pct(m.resolved_by_ai_rate || 0);
  }

  function matchesLead(lead, query) {
    if (!query) { return true; }
    var haystack = [
      lead.name, lead.company, lead.contact,
      lead.service_interest, lead.budget_range, lead.status
    ].join(" ").toLowerCase();
    return haystack.indexOf(query.toLowerCase()) !== -1;
  }

  function renderLeads() {
    var query = els.leadFilter.value.trim();
    var leads = state.leads.filter(function (lead) { return matchesLead(lead, query); });
    els.leadsBody.innerHTML = "";
    if (!leads.length) {
      els.leadsBody.innerHTML = '<tr><td colspan="6" class="admin-empty">No leads yet.</td></tr>';
      return;
    }
    leads.forEach(function (lead) {
      var tr = document.createElement("tr");
      tr.innerHTML = [
        '<td><b>' + esc(lead.name || "Unknown") + '</b><span>' + esc(lead.contact || "-") + '</span></td>',
        '<td>' + esc(lead.company || "-") + '</td>',
        '<td>' + esc(lead.service_interest || "-") + '</td>',
        '<td>' + esc(lead.budget_range || "-") + '</td>',
        '<td><span class="status-pill">' + esc(lead.status || "new") + '</span></td>',
        '<td>' + esc(fmtDate(lead.created_at)) + '</td>'
      ].join("");
      els.leadsBody.appendChild(tr);
    });
  }

  function renderCompany() {
    if (!state.company || !els.companyForm) { return; }
    [
      "company_name", "company_domain", "company_description",
      "company_contact_email", "assistant_name", "escalation_target",
      "business_industry"
    ].forEach(function (key) {
      var field = els.companyForm.elements[key];
      if (field) { field.value = state.company[key] || ""; }
    });
    if (state.company.brand_label && els.brand) {
      els.brand.textContent = state.company.brand_label;
    }
    setPill(els.companyStatus, "Loaded", "");
  }

  function companyPayload() {
    var data = {};
    [
      "company_name", "company_domain", "company_description",
      "company_contact_email", "assistant_name", "escalation_target",
      "business_industry"
    ].forEach(function (key) {
      data[key] = (els.companyForm.elements[key]?.value || "").trim();
    });
    return data;
  }

  function saveCompany(event) {
    event.preventDefault();
    els.companySave.disabled = true;
    setPill(els.companyStatus, "Saving...", "");
    sendJSON("PUT", "/config/profile", companyPayload())
      .then(function (profile) {
        state.company = profile;
        renderCompany();
        setPill(els.companyStatus, "Saved", "ok");
        loadAudit();
      })
      .catch(function () { setPill(els.companyStatus, "Could not save", "error"); })
      .finally(function () { els.companySave.disabled = false; });
  }

  function renderKnowledgeFiles() {
    if (!els.kbList) { return; }
    els.kbList.innerHTML = "";
    if (!state.kbFiles.length) {
      els.kbList.innerHTML = '<div class="admin-empty">No markdown files yet.</div>';
      return;
    }
    state.kbFiles.forEach(function (file) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "kb-file" + (file.path === state.currentKbPath ? " active" : "");
      button.dataset.path = file.path;
      button.innerHTML = '<b>' + esc(file.path) + '</b><span>' +
        esc(file.preview || "Empty file") + '</span>';
      els.kbList.appendChild(button);
    });
  }

  function loadKnowledgeFiles() {
    return getJSON("/knowledge/files").then(function (files) {
      state.kbFiles = Array.isArray(files) ? files : [];
      renderKnowledgeFiles();
    });
  }

  function loadKnowledgeFile(path) {
    state.currentKbPath = path;
    setPill(els.kbStatus, "Loading...", "");
    return getJSON("/knowledge/files/" + encodeURIComponent(path)).then(function (file) {
      if (!file) { throw new Error("missing file"); }
      els.kbName.value = file.path;
      els.kbContent.value = file.content || "";
      state.currentKbPath = file.path;
      renderKnowledgeFiles();
      setPill(els.kbStatus, "Loaded", "");
    }).catch(function () {
      setPill(els.kbStatus, "Could not load", "error");
    });
  }

  function newKnowledgeFile() {
    state.currentKbPath = "";
    els.kbName.value = "new-document.md";
    els.kbContent.value = "# New document\n\nWrite company knowledge here.";
    renderKnowledgeFiles();
    setPill(els.kbStatus, "Draft", "");
  }

  function saveKnowledgeFile(event) {
    event.preventDefault();
    var path = (els.kbName.value || "").trim();
    if (!path) { setPill(els.kbStatus, "Filename required", "error"); return; }
    if (!path.endsWith(".md")) { path += ".md"; }
    setPill(els.kbStatus, "Saving...", "");
    sendJSON("PUT", "/knowledge/files/" + encodeURIComponent(path), {
      content: els.kbContent.value || ""
    }).then(function (file) {
      state.currentKbPath = file.path;
      els.kbName.value = file.path;
      setPill(els.kbStatus, "Saved", "ok");
      return loadKnowledgeFiles();
    }).then(loadAudit).catch(function () {
      setPill(els.kbStatus, "Could not save", "error");
    });
  }

  function deleteKnowledgeFile() {
    var path = (els.kbName.value || state.currentKbPath || "").trim();
    if (!path) { return; }
    setPill(els.kbStatus, "Deleting...", "");
    fetch("/knowledge/files/" + encodeURIComponent(path), { method: "DELETE" })
      .then(function (r) {
        if (!r.ok && r.status !== 204) { throw new Error("delete failed"); }
        state.currentKbPath = "";
        els.kbName.value = "";
        els.kbContent.value = "";
        setPill(els.kbStatus, "Deleted", "ok");
        return loadKnowledgeFiles();
      }).then(loadAudit).catch(function () {
        setPill(els.kbStatus, "Could not delete", "error");
      });
  }

  function reindexKnowledge() {
    els.kbReindex.disabled = true;
    setPill(els.kbStatus, "Indexing...", "");
    sendJSON("POST", "/knowledge/ingest", {})
      .then(function (result) {
        setPill(els.kbStatus, result.documents + " docs / " + result.chunks + " chunks", "ok");
        loadAudit();
      })
      .catch(function () { setPill(els.kbStatus, "Index failed", "error"); })
      .finally(function () { els.kbReindex.disabled = false; });
  }

  function renderCrm() {
    if (!state.crm || !els.crmForm) { return; }
    els.crmForm.elements.provider.value = state.crm.provider || "local";
    els.crmForm.elements.enabled.checked = !!state.crm.enabled;
    els.crmForm.elements.webhook_url.value = state.crm.webhook_url || "";
    els.crmForm.elements.api_key_env.value = state.crm.api_key_env || "";
    els.crmForm.elements.pipeline_name.value = state.crm.pipeline_name || "";
    setPill(els.crmStatus, "Loaded", "");
  }

  function renderDispatches() {
    if (!els.dispatchList) { return; }
    if (!state.dispatches.length) {
      els.dispatchList.innerHTML = '<div class="admin-empty">No sync attempts yet.</div>';
      return;
    }
    els.dispatchList.innerHTML = state.dispatches.slice(0, 8).map(function (d) {
      return '<article class="dispatch-item"><b>' + esc(d.provider) + ' / ' + esc(d.status) +
        '</b><span>Lead #' + esc(d.lead_id || "-") + ' · ' + esc(fmtDate(d.created_at)) +
        '</span><p>' + esc(d.response_summary || "") + '</p></article>';
    }).join("");
  }

  function crmPayload() {
    return {
      provider: els.crmForm.elements.provider.value,
      enabled: els.crmForm.elements.enabled.checked,
      webhook_url: (els.crmForm.elements.webhook_url.value || "").trim() || null,
      api_key_env: (els.crmForm.elements.api_key_env.value || "").trim() || null,
      pipeline_name: (els.crmForm.elements.pipeline_name.value || "").trim() || null
    };
  }

  function saveCrm(event) {
    event.preventDefault();
    els.crmSave.disabled = true;
    setPill(els.crmStatus, "Saving...", "");
    sendJSON("PUT", "/crm/integration", crmPayload())
      .then(function (integration) {
        state.crm = integration;
        renderCrm();
        setPill(els.crmStatus, "Saved", "ok");
        loadAudit();
      })
      .catch(function () { setPill(els.crmStatus, "Could not save", "error"); })
      .finally(function () { els.crmSave.disabled = false; });
  }

  function renderTickets() {
    els.ticketsList.innerHTML = "";
    if (!state.tickets.length) {
      els.ticketsList.innerHTML = '<div class="admin-empty">No tickets yet.</div>';
      return;
    }
    state.tickets.slice(0, 12).forEach(function (ticket) {
      var item = document.createElement("article");
      item.className = "ticket-item";
      item.dataset.ticketId = ticket.id;
      var notes = state.ticketNotes[ticket.id] || [];
      var notesHtml = notes.length ? notes.slice(0, 3).map(function (note) {
        return '<div class="ticket-note-row"><b>' + esc(note.author || "operator") +
          '</b><span>' + esc(fmtDate(note.created_at)) + '</span><p>' +
          esc(note.body || "") + '</p></div>';
      }).join("") : '<div class="ticket-note-empty">No internal notes.</div>';
      item.innerHTML = [
        '<div class="ticket-row"><b>TCK-' + esc(ticket.id) + '</b><span>' +
          esc(ticket.status || "open") + '</span></div>',
        '<p>' + esc(ticket.summary || "No summary") + '</p>',
        '<div class="ticket-meta">' + esc((ticket.reason || "request").replace(/_/g, " ")) +
          ' · ' + esc(ticket.priority || "normal") + ' · ' + esc(fmtDate(ticket.created_at)) + '</div>',
        '<div class="ticket-controls">',
          '<select class="ticket-status"><option value="open">open</option><option value="in_progress">in progress</option><option value="resolved">resolved</option></select>',
          '<select class="ticket-priority"><option value="normal">normal</option><option value="high">high</option><option value="urgent">urgent</option></select>',
          '<input class="ticket-assignee" type="text" placeholder="Assignee" value="' + esc(ticket.assignee || "") + '">',
          '<button class="btn btn-sm ticket-save" type="button">Save</button>',
        '</div>',
        '<div class="ticket-notes">' + notesHtml + '</div>',
        '<textarea class="ticket-note" rows="2" placeholder="Internal note"></textarea>',
        '<button class="btn btn-sm ticket-note-save" type="button">Add note</button>'
      ].join("");
      item.querySelector(".ticket-status").value = ticket.status || "open";
      item.querySelector(".ticket-priority").value = ticket.priority || "normal";
      els.ticketsList.appendChild(item);
    });
  }

  function saveTicket(item) {
    var id = item.dataset.ticketId;
    return sendJSON("PATCH", "/tickets/" + id, {
      status: item.querySelector(".ticket-status").value,
      priority: item.querySelector(".ticket-priority").value,
      assignee: item.querySelector(".ticket-assignee").value.trim()
    }).then(loadTickets).then(loadAudit);
  }

  function addTicketNote(item) {
    var id = item.dataset.ticketId;
    var textarea = item.querySelector(".ticket-note");
    var body = textarea.value.trim();
    if (!body) { return Promise.resolve(); }
    return sendJSON("POST", "/tickets/" + id + "/notes", {
      author: "operator",
      body: body
    }).then(function () {
      textarea.value = "";
      return Promise.all([loadTickets(), loadAudit()]);
    });
  }

  function renderAudit() {
    if (!els.auditList) { return; }
    if (!state.audit.length) {
      els.auditList.innerHTML = '<div class="admin-empty">No audit events yet.</div>';
      return;
    }
    els.auditList.innerHTML = state.audit.slice(0, 20).map(function (event) {
      return '<article class="audit-item"><b>' + esc(event.action) +
        '</b><span>' + esc(event.actor) + ' · ' + esc(event.entity_type) +
        (event.entity_id ? ' #' + esc(event.entity_id) : '') + ' · ' +
        esc(fmtDate(event.created_at)) + '</span><p>' + esc(event.summary) +
        '</p></article>';
    }).join("");
  }

  function loadTickets() {
    return getJSON("/tickets").then(function (tickets) {
      state.tickets = Array.isArray(tickets) ? tickets : [];
      state.ticketNotes = {};
      var visible = state.tickets.slice(0, 12);
      return Promise.all(visible.map(function (ticket) {
        return getJSON("/tickets/" + ticket.id + "/notes").then(function (notes) {
          state.ticketNotes[ticket.id] = Array.isArray(notes) ? notes : [];
        });
      }));
    }).then(function () {
      renderTickets();
    });
  }

  function loadAudit() {
    return getJSON("/audit/events").then(function (events) {
      state.audit = Array.isArray(events) ? events : [];
      renderAudit();
    });
  }

  function renderAll() {
    renderMetrics();
    renderLeads();
    renderTickets();
    renderCompany();
    renderKnowledgeFiles();
    renderCrm();
    renderDispatches();
    renderAudit();
  }

  function load() {
    if (els.refresh) { els.refresh.disabled = true; }
    Promise.all([
      getJSON("/metrics/demo"),
      getJSON("/crm/leads"),
      getJSON("/tickets"),
      getJSON("/config/profile"),
      getJSON("/knowledge/files"),
      getJSON("/crm/integration"),
      getJSON("/crm/dispatches"),
      getJSON("/audit/events")
    ]).then(function (items) {
      state.metrics = items[0] || {};
      state.leads = Array.isArray(items[1]) ? items[1] : [];
      state.tickets = Array.isArray(items[2]) ? items[2] : [];
      state.company = items[3] || null;
      state.kbFiles = Array.isArray(items[4]) ? items[4] : [];
      state.crm = items[5] || null;
      state.dispatches = Array.isArray(items[6]) ? items[6] : [];
      state.audit = Array.isArray(items[7]) ? items[7] : [];
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
  if (els.companyForm) { els.companyForm.addEventListener("submit", saveCompany); }
  if (els.kbForm) { els.kbForm.addEventListener("submit", saveKnowledgeFile); }
  if (els.kbNew) { els.kbNew.addEventListener("click", newKnowledgeFile); }
  if (els.kbDelete) { els.kbDelete.addEventListener("click", deleteKnowledgeFile); }
  if (els.kbReindex) { els.kbReindex.addEventListener("click", reindexKnowledge); }
  if (els.crmForm) { els.crmForm.addEventListener("submit", saveCrm); }
  if (els.kbList) {
    els.kbList.addEventListener("click", function (event) {
      var button = event.target.closest(".kb-file");
      if (button) { loadKnowledgeFile(button.dataset.path); }
    });
  }
  if (els.ticketsList) {
    els.ticketsList.addEventListener("click", function (event) {
      var item = event.target.closest(".ticket-item");
      if (!item) { return; }
      if (event.target.classList.contains("ticket-save")) { saveTicket(item); }
      if (event.target.classList.contains("ticket-note-save")) { addTicketNote(item); }
    });
  }
  load();
})();
