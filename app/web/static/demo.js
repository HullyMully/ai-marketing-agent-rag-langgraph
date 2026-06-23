/* NovaGrowth AI Assistant — web demo client.
   Plain JS, no dependencies.

   Two modes:
   - Quick-action scenarios render a clean, deterministic, product-quality flow
     (and quietly call the backend so leads/tickets/metrics stay real).
   - Free-typed messages call POST /chat live and show a humanised result. */
(function () {
  "use strict";

  var SESSION_KEY = "novagrowth_demo_session_id";

  /* ---------- scripted, screenshot-ready scenarios ---------- */
  var SCENARIOS = {
    lead: {
      messages: [
        ["assistant", "Hi, I'm NovaGrowth AI. I can answer questions, qualify leads and create CRM records for the marketing team."],
        ["user", "Hi, we need help launching paid ads for our SaaS product."],
        ["assistant", "Sure. I can help qualify the request. What monthly ad budget are you planning, and who should the team contact?"],
        ["user", "My name is Sam. I work at BrightDesk. Budget is around $5k/month. Contact me at sam@brightdesk.example."],
        ["assistant", "Done. I created a new lead for BrightDesk and routed it to the marketing team. A manager will follow up with Sam at sam@brightdesk.example."]
      ],
      panel: {
        workflow: "Lead created and routed to the marketing team",
        lead: { company: "BrightDesk", contact: "sam@brightdesk.example",
                service: "Paid acquisition", budget: "$5k/month", status: "new" },
        sources: "Not required"
      },
      backend: ["Hi, my name is Sam. I work at BrightDesk. We need help launching paid " +
                "ads for our SaaS product. Budget is around $5k/month. Contact me at " +
                "sam@brightdesk.example."]
    },

    services: {
      messages: [
        ["user", "What services does NovaGrowth provide?"],
        ["assistant", "NovaGrowth supports paid acquisition, landing page audits, analytics setup, campaign optimization and reporting workflows."]
      ],
      panel: {
        workflow: "Answered from knowledge base",
        sources: "services.md"
      },
      backend: ["What services does NovaGrowth provide?"]
    },

    pricing: {
      messages: [
        ["user", "What pricing packages are available?"],
        ["assistant", "We offer three packages: Starter at $1,500/mo for a single channel, " +
                      "Growth at $3,500/mo for multi-channel campaigns, and Scale at $7,000/mo " +
                      "with dedicated strategy and reporting."]
      ],
      panel: {
        workflow: "Answered from knowledge base",
        sources: "pricing.md"
      },
      backend: ["What pricing packages are available?"]
    },

    human: {
      messages: [
        ["user", "I need a human manager for a custom enterprise marketing workflow."],
        ["assistant", "I created an escalation ticket for a human manager. The team will review the request and follow up within one business day."]
      ],
      panel: {
        workflow: "Escalated to a manager",
        ticket: { id: "TCK-1024", reason: "Custom enterprise workflow",
                  priority: "medium", status: "open" },
        sources: "Not required"
      },
      backend: ["I need a human manager for a custom enterprise marketing workflow."]
    },

    memory: {
      messages: [
        ["user", "Hi, we need help launching paid ads. I'm Sam from BrightDesk, budget around $5k/month."],
        ["assistant", "Got it, Sam — noted BrightDesk and a paid acquisition request at around $5k/month."],
        ["user", "Can you remind me what company I mentioned?"],
        ["assistant", "You mentioned BrightDesk. The current request is about paid acquisition with a budget around $5k/month."]
      ],
      panel: {
        workflow: "Session memory used",
        memory: "Remembered BrightDesk · paid acquisition · ~$5k/month",
        sources: "Not required"
      },
      backend: []
    }
  };

  /* ---------- humanise live backend values ---------- */
  var INTENT_LABEL = {
    service_question: "Service question",
    pricing_question: "Pricing question",
    create_lead: "Lead qualification",
    campaign_status_question: "Campaign question",
    support_request: "Support request",
    human_escalation: "Human escalation",
    general_question: "General question",
    unknown: "General question"
  };
  var ACTION_LABEL = {
    answered_from_kb: "Answered from knowledge base",
    created_lead: "Lead created and routed to the marketing team",
    escalated_to_human: "Escalated to a manager",
    collect_missing_info: "Collecting a few details"
  };

  var chat = document.getElementById("chat");
  var form = document.getElementById("chat-form");
  var input = document.getElementById("message");
  var sendBtn = document.getElementById("send");
  var emptyChat = document.getElementById("empty-chat");

  var els = {
    empty: document.getElementById("result-empty"),
    result: document.getElementById("result"),
    rcLead: document.getElementById("rc-lead"),
    rcTicket: document.getElementById("rc-ticket"),
    rcSources: document.getElementById("rc-sources"),
    rcMemory: document.getElementById("rc-memory"),
    lCompany: document.getElementById("l-company"),
    lContact: document.getElementById("l-contact"),
    lService: document.getElementById("l-service"),
    lBudget: document.getElementById("l-budget"),
    lStatus: document.getElementById("l-status"),
    tId: document.getElementById("t-id"),
    tReason: document.getElementById("t-reason"),
    tPriority: document.getElementById("t-priority"),
    tStatus: document.getElementById("t-status"),
    workflow: document.getElementById("r-workflow"),
    sources: document.getElementById("r-sources"),
    memory: document.getElementById("r-memory")
  };

  var lastRole = null;
  var busy = false;

  /* ---------- session ---------- */
  function newSessionId() {
    return "web-demo-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
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

  function hideEmptyChat() { if (emptyChat) { emptyChat.style.display = "none"; } }

  function addMessage(role, text) {
    hideEmptyChat();
    var groupStart = role !== lastRole;
    var wrap = document.createElement("div");
    wrap.className = "msg " + role + (groupStart ? " group-start" : "");
    if (role === "assistant" && groupStart) {
      var lbl = document.createElement("div");
      lbl.className = "msg-label";
      lbl.textContent = "NovaGrowth AI";
      wrap.appendChild(lbl);
    }
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    wrap.appendChild(bubble);
    chat.appendChild(wrap);
    lastRole = role;
    scrollToBottom();
    return wrap;
  }

  function showTyping() {
    hideEmptyChat();
    var wrap = document.createElement("div");
    wrap.className = "msg assistant group-start typing";
    wrap.innerHTML = '<div class="msg-label">NovaGrowth AI</div><div class="bubble">typing…</div>';
    chat.appendChild(wrap);
    lastRole = "assistant";
    scrollToBottom();
    return wrap;
  }

  function clearChat() {
    chat.innerHTML = "";
    if (emptyChat) { chat.appendChild(emptyChat); emptyChat.style.display = ""; }
    lastRole = null;
  }

  /* ---------- result panel ---------- */
  function setText(el, v) { el.textContent = (v === undefined || v === null || v === "") ? "—" : v; }

  function renderPanel(p) {
    els.empty.classList.add("hidden");
    els.result.classList.remove("hidden");

    if (p.lead) {
      setText(els.lCompany, p.lead.company);
      setText(els.lContact, p.lead.contact);
      setText(els.lService, p.lead.service);
      setText(els.lBudget, p.lead.budget);
      setText(els.lStatus, p.lead.status || "new");
      els.rcLead.classList.remove("hidden");
    } else {
      els.rcLead.classList.add("hidden");
    }

    if (p.ticket) {
      setText(els.tId, p.ticket.id);
      setText(els.tReason, p.ticket.reason);
      setText(els.tPriority, p.ticket.priority);
      setText(els.tStatus, p.ticket.status);
      els.rcTicket.classList.remove("hidden");
    } else {
      els.rcTicket.classList.add("hidden");
    }

    setText(els.workflow, p.workflow);
    setText(els.sources, p.sources || "Not required");

    if (p.memory) {
      setText(els.memory, p.memory);
      els.rcMemory.classList.remove("hidden");
    } else {
      els.rcMemory.classList.add("hidden");
    }
  }

  /* ---------- backend helpers ---------- */
  function postChat(text) {
    return fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: getSessionId(), user_message: text })
    }).then(function (r) { return r.ok ? r.json() : null; });
  }
  function getJSON(url) {
    return fetch(url).then(function (r) { return r.ok ? r.json() : null; })
                     .catch(function () { return null; });
  }

  /* fire scenario messages at the backend so records/metrics stay real;
     returns the last response (used to pick up a real ticket id). */
  function syncBackend(messages) {
    var last = Promise.resolve(null);
    messages.forEach(function (m) {
      last = last.then(function () { return postChat(m).catch(function () { return null; }); });
    });
    return last;
  }

  /* ---------- scenarios ---------- */
  function runScenario(key, btn) {
    if (busy) { return; }
    var sc = SCENARIOS[key];
    if (!sc) { return; }

    document.querySelectorAll(".qa").forEach(function (b) { b.classList.remove("active"); });
    if (btn) { btn.classList.add("active"); }

    resetSession();
    clearChat();
    sc.messages.forEach(function (m) { addMessage(m[0], m[1]); });
    renderPanel(sc.panel);

    // Keep backend records real, but never let it change the clean display.
    if (sc.backend && sc.backend.length) {
      syncBackend(sc.backend).then(function (resp) {
        if (key === "human" && resp && resp.created_ticket_id) {
          els.tId.textContent = "TCK-" + resp.created_ticket_id;
        }
      });
    }
  }

  /* ---------- free-typed chat (live) ---------- */
  function livePanel(data) {
    var p = {
      workflow: ACTION_LABEL[data.action_taken] ||
                INTENT_LABEL[data.intent] || "Answered",
      sources: (data.sources && data.sources.length) ? data.sources.join(", ") : "Not required"
    };
    renderPanel(p);

    if (data.created_lead_id) {
      getJSON("/crm/leads").then(function (leads) {
        if (!leads) { return; }
        for (var i = 0; i < leads.length; i++) {
          if (leads[i].id === data.created_lead_id) {
            renderPanel({
              workflow: "Lead created and routed to the marketing team",
              sources: p.sources,
              lead: {
                company: leads[i].company, contact: leads[i].contact,
                service: leads[i].service_interest, budget: leads[i].budget_range,
                status: leads[i].status
              }
            });
            break;
          }
        }
      });
    } else if (data.created_ticket_id) {
      getJSON("/tickets/" + data.created_ticket_id).then(function (t) {
        if (!t) { return; }
        renderPanel({
          workflow: "Escalated to a manager",
          sources: "Not required",
          ticket: { id: "TCK-" + t.id, reason: (t.reason || "").replace(/_/g, " "),
                    priority: t.priority, status: t.status }
        });
      });
    }
  }

  function sendLive(text) {
    if (!text || busy) { return; }
    busy = true; sendBtn.disabled = true; input.disabled = true;
    addMessage("user", text);
    var typing = showTyping();
    postChat(text)
      .then(function (data) {
        typing.remove(); lastRole = null;
        if (!data) { throw new Error("no response"); }
        addMessage("assistant", data.answer || "…");
        livePanel(data);
      })
      .catch(function () {
        typing.remove(); lastRole = null;
        addMessage("assistant", "Sorry — I couldn't reach the backend. Make sure the API is running.");
      })
      .finally(function () { busy = false; sendBtn.disabled = false; input.disabled = false; input.focus(); });
  }

  /* ---------- wiring ---------- */
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text) { return; }
    input.value = "";
    document.querySelectorAll(".qa").forEach(function (b) { b.classList.remove("active"); });
    sendLive(text);
  });

  document.querySelectorAll(".qa").forEach(function (btn) {
    btn.addEventListener("click", function () {
      runScenario(btn.getAttribute("data-scenario"), btn);
    });
  });

  getSessionId();
})();
