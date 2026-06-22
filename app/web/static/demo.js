/* NovaGrowth AI Marketing Agent — web demo client.
   Plain JS, no dependencies. Talks to the FastAPI backend (POST /chat,
   GET /crm/leads, GET /tickets/{id}, GET /metrics/demo). */
(function () {
  "use strict";

  var SESSION_KEY = "novagrowth_demo_session_id";

  /* Scenario messages. Strings run as one turn; arrays run as several turns
     in the same session (used to demonstrate memory). */
  var SCENARIOS = {
    services: "What services does NovaGrowth offer?",
    pricing: "How much does a campaign cost? What pricing packages do you have?",
    lead:
      "Hi, my name is Sam. I work at BrightDesk. We need help launching paid ads " +
      "for our SaaS product. Budget is around $5k/month. Contact me at " +
      "sam@brightdesk.example.",
    human: "I need a human manager for a custom enterprise marketing workflow.",
    memory: [
      "I want to start SEO for my online store, I'm Priya.",
      "My email is priya@studio.example"
    ]
  };

  var chat = document.getElementById("chat");
  var form = document.getElementById("chat-form");
  var input = document.getElementById("message");
  var sendBtn = document.getElementById("send");
  var resetBtn = document.getElementById("reset");
  var shotBtn = document.getElementById("shot-toggle");

  var els = {
    empty: document.getElementById("result-empty"),
    result: document.getElementById("result"),
    cardLead: document.getElementById("card-lead"),
    cardTicket: document.getElementById("card-ticket"),
    cardMetrics: document.getElementById("card-metrics"),
    leadCompany: document.getElementById("lead-company"),
    leadContact: document.getElementById("lead-contact"),
    leadService: document.getElementById("lead-service"),
    leadBudget: document.getElementById("lead-budget"),
    leadStatus: document.getElementById("lead-status"),
    ticketId: document.getElementById("ticket-id"),
    ticketReason: document.getElementById("ticket-reason"),
    ticketPriority: document.getElementById("ticket-priority"),
    ticketStatus: document.getElementById("ticket-status"),
    dIntent: document.getElementById("d-intent"),
    dAction: document.getElementById("d-action"),
    dEscalated: document.getElementById("d-escalated"),
    dSources: document.getElementById("d-sources"),
    mConvos: document.getElementById("m-convos"),
    mLeads: document.getElementById("m-leads"),
    mTickets: document.getElementById("m-tickets"),
    mResolved: document.getElementById("m-resolved")
  };

  var WELCOME = chat.innerHTML;
  var busy = false;

  /* ---------- session ---------- */
  function newSessionId() {
    var rnd = Math.random().toString(36).slice(2, 8);
    return "web-demo-" + Date.now().toString(36) + "-" + rnd;
  }
  function getSessionId() {
    var id = localStorage.getItem(SESSION_KEY);
    if (!id) { id = newSessionId(); localStorage.setItem(SESSION_KEY, id); }
    return id;
  }
  function resetSession() {
    var id = newSessionId();
    localStorage.setItem(SESSION_KEY, id);
    return id;
  }

  /* ---------- chat rendering ---------- */
  function scrollToBottom() { chat.scrollTop = chat.scrollHeight; }

  function addMessage(role, text) {
    var wrap = document.createElement("div");
    wrap.className = "msg " + role;
    if (role === "assistant") {
      var av = document.createElement("span");
      av.className = "avatar"; av.setAttribute("aria-hidden", "true");
      av.textContent = "N";
      wrap.appendChild(av);
    }
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    wrap.appendChild(bubble);
    chat.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  function showTyping() {
    var wrap = document.createElement("div");
    wrap.className = "msg assistant typing";
    wrap.innerHTML = '<span class="avatar" aria-hidden="true">N</span>' +
                     '<div class="bubble">typing…</div>';
    chat.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  /* ---------- result panel ---------- */
  function setBusy(state) {
    busy = state;
    sendBtn.disabled = state;
    input.disabled = state;
  }

  function showResult() {
    els.empty.classList.add("hidden");
    els.result.classList.remove("hidden");
  }

  function updateDetails(data) {
    els.dIntent.textContent = data.intent || "—";
    els.dAction.textContent = data.action_taken || "—";
    els.dEscalated.textContent = data.escalated ? "yes" : "no";
    els.dSources.textContent =
      (data.sources && data.sources.length) ? data.sources.join(", ") : "—";
  }

  function get(url) {
    return fetch(url).then(function (r) { return r.ok ? r.json() : null; })
                     .catch(function () { return null; });
  }

  function fillLead(lead) {
    if (!lead) { return; }
    els.leadCompany.textContent = lead.company || "—";
    els.leadContact.textContent = lead.contact || "—";
    els.leadService.textContent = lead.service_interest || "—";
    els.leadBudget.textContent = lead.budget_range || "—";
    els.leadStatus.textContent = lead.status || "new";
    els.cardLead.classList.remove("hidden");
  }

  function fillTicket(ticket) {
    if (!ticket) { return; }
    els.ticketId.textContent = "TCK-" + ticket.id;
    els.ticketReason.textContent = (ticket.reason || "").replace(/_/g, " ");
    els.ticketPriority.textContent = ticket.priority || "—";
    els.ticketStatus.textContent = ticket.status || "—";
    els.cardTicket.classList.remove("hidden");
  }

  function refreshMetrics() {
    return get("/metrics/demo").then(function (m) {
      if (!m) { return; }
      els.mConvos.textContent = m.conversations;
      els.mLeads.textContent = m.leads;
      els.mTickets.textContent = m.tickets;
      els.mResolved.textContent = Math.round((m.resolved_by_ai_rate || 0) * 100) + "%";
      els.cardMetrics.classList.remove("hidden");
    });
  }

  function updateResult(data) {
    showResult();
    updateDetails(data);
    els.cardLead.classList.add("hidden");
    els.cardTicket.classList.add("hidden");

    var jobs = [];
    if (data.created_lead_id) {
      jobs.push(get("/crm/leads").then(function (leads) {
        if (!leads) { return; }
        for (var i = 0; i < leads.length; i++) {
          if (leads[i].id === data.created_lead_id) { fillLead(leads[i]); break; }
        }
      }));
    }
    if (data.created_ticket_id) {
      jobs.push(get("/tickets/" + data.created_ticket_id).then(fillTicket));
    }
    jobs.push(refreshMetrics());
    return Promise.all(jobs);
  }

  /* ---------- send ---------- */
  function sendMessage(text) {
    if (!text || busy) { return Promise.resolve(); }
    setBusy(true);
    addMessage("user", text);
    var typing = showTyping();

    return fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: getSessionId(), user_message: text })
    })
      .then(function (r) {
        if (!r.ok) { throw new Error("HTTP " + r.status); }
        return r.json();
      })
      .then(function (data) {
        typing.remove();
        addMessage("assistant", data.answer || "…");
        return updateResult(data);
      })
      .catch(function () {
        typing.remove();
        addMessage("assistant",
          "Sorry — I couldn't reach the backend. Make sure the API is running.");
      })
      .finally(function () { setBusy(false); input.focus(); });
  }

  /* ---------- scenarios ---------- */
  function resetConversation() {
    resetSession();
    chat.innerHTML = WELCOME;
    els.result.classList.add("hidden");
    els.empty.classList.remove("hidden");
    refreshMetrics();
  }

  function runScenario(key, btn) {
    if (busy) { return; }
    var steps = SCENARIOS[key];
    if (!steps) { return; }
    if (typeof steps === "string") { steps = [steps]; }

    document.querySelectorAll(".scenario").forEach(function (b) {
      b.classList.remove("active");
    });
    if (btn) { btn.classList.add("active"); }

    // fresh session so each scenario is a clean, repeatable demo
    resetSession();
    chat.innerHTML = WELCOME;

    var chain = Promise.resolve();
    steps.forEach(function (msg) {
      chain = chain.then(function () { return sendMessage(msg); });
    });
    return chain;
  }

  /* ---------- wiring ---------- */
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text) { return; }
    input.value = "";
    sendMessage(text);
  });

  document.querySelectorAll(".scenario").forEach(function (btn) {
    btn.addEventListener("click", function () {
      runScenario(btn.getAttribute("data-scenario"), btn);
    });
  });

  if (resetBtn) {
    resetBtn.addEventListener("click", resetConversation);
  }

  shotBtn.addEventListener("click", function () {
    var on = document.body.classList.toggle("shot");
    shotBtn.setAttribute("aria-pressed", on ? "true" : "false");
  });

  // init
  getSessionId();
  refreshMetrics();
})();
