/* AI Customer Assistant — web chat client.
   Plain JS, no dependencies. Every reply comes from the real agent via
   POST /chat. Suggested prompts only send a normal user message; the right
   panel renders the actual conversation state returned by the backend. */
(function () {
  "use strict";

  var SESSION_KEY = "assistant_demo_session_id";

  var INTENT_LABEL = {
    // planner user_intent vocabulary
    greeting: "Greeting",
    casual_chat: "Casual chat",
    ask_services: "Service question",
    ask_pricing: "Pricing question",
    ask_process: "Process question",
    start_project: "Start a project",
    provide_lead_info: "Lead details",
    ask_human: "Wants a human",
    complaint: "Complaint",
    meta_question: "Meta question",
    unclear: "Unclear",
    // legacy intents (still emitted for metrics)
    service_question: "Service question",
    pricing_question: "Pricing question",
    support_request: "Support request",
    human_escalation: "Human escalation",
    memory_question: "Memory question",
    unknown: "Unclear"
  };

  var FIELD_LABELS = {
    name: "Name",
    company: "Company",
    contact_email: "Contact email",
    service_interest: "Service",
    budget_range: "Budget",
    product_type: "Product"
  };

  var ACTION_LABEL = {
    collecting_info: "Qualifying lead",
    created_lead: "Lead created",
    lead_already_exists: "Lead already created",
    answered_from_kb: "Answered from knowledge base",
    escalated_to_human: "Escalated to a human",
    answered_with_memory: "Used session memory",
    asked_clarification: "Asked for clarification",
    greeted: "Greeted the user",
    exploring: "Exploring options",
    clarifying_direction: "Confirming direction",
    qualification_paused: "Qualification paused"
  };

  // Planner's recommended action (what it asked the backend to consider).
  var REC_ACTION_LABEL = {
    answer_only: "Answer only",
    update_lead_draft: "Update lead draft",
    create_lead: "Create lead",
    create_ticket: "Create ticket",
    ask_clarifying_question: "Ask a question",
    pause_qualification: "Pause qualification",
    retrieve_knowledge: "Retrieve knowledge"
  };

  // Backend validation reason codes -> human text.
  var VALIDATION_LABEL = {
    ok: "Approved",
    not_applicable: "No action needed",
    action_not_recommended: "No action recommended",
    missing_required_fields: "Blocked — missing details",
    user_has_not_agreed: "Blocked — not confirmed yet",
    lead_already_exists: "Blocked — lead already exists",
    not_an_escalation: "Blocked — not an escalation",
    ticket_already_exists: "Blocked — ticket already exists",
    planner_error: "Reasoning unavailable"
  };

  var chat = document.getElementById("chat");
  var form = document.getElementById("chat-form");
  var input = document.getElementById("message");
  var sendBtn = document.getElementById("send");
  var newChatBtn = document.getElementById("new-chat");
  var emptyChat = document.getElementById("empty-chat");

  var els = {
    empty: document.getElementById("result-empty"),
    result: document.getElementById("result"),
    rcLead: document.getElementById("rc-lead"),
    rcDraft: document.getElementById("rc-draft"),
    rcTicket: document.getElementById("rc-ticket"),
    rcSources: document.getElementById("rc-sources"),
    rcMemory: document.getElementById("rc-memory"),
    lCompany: document.getElementById("l-company"),
    lContact: document.getElementById("l-contact"),
    lService: document.getElementById("l-service"),
    lBudget: document.getElementById("l-budget"),
    draftKnown: document.getElementById("draft-known"),
    draftMissing: document.getElementById("draft-missing"),
    tId: document.getElementById("t-id"),
    tReason: document.getElementById("t-reason"),
    tPriority: document.getElementById("t-priority"),
    tStatus: document.getElementById("t-status"),
    sources: document.getElementById("r-sources"),
    workflow: document.getElementById("r-workflow"),
    intent: document.getElementById("r-intent"),
    mode: document.getElementById("r-mode"),
    paused: document.getElementById("r-paused"),
    interests: document.getElementById("r-interests"),
    next: document.getElementById("r-next"),
    action: document.getElementById("r-action"),
    validation: document.getElementById("r-validation"),
    executed: document.getElementById("r-executed")
  };

  var MODE_LABEL = {
    answering: "Answering",
    exploring: "Exploring options",
    qualifying: "Qualifying lead",
    paused: "Paused"
  };

  var lastRole = null;
  var busy = false;
  var assistantName = "AI Assistant";

  /* ---------- config ---------- */
  function loadConfig() {
    fetch("/config").then(function (r) { return r.ok ? r.json() : null; })
      .then(function (c) {
        if (!c) { return; }
        assistantName = c.assistant_name || assistantName;
        var brand = document.getElementById("brand-name");
        if (brand && c.brand_label) { brand.textContent = c.brand_label; }
        var an = document.getElementById("assistant-name");
        if (an) { an.textContent = assistantName; }
        var ava = document.getElementById("ava-initial");
        if (ava) { ava.textContent = (assistantName.charAt(0) || "A").toUpperCase(); }
      }).catch(function () {});
  }

  /* ---------- session ---------- */
  function newSessionId() {
    return "web-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
  }
  function getSessionId() {
    var id = localStorage.getItem(SESSION_KEY);
    if (!id) { id = newSessionId(); localStorage.setItem(SESSION_KEY, id); }
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
      lbl.textContent = assistantName;
      wrap.appendChild(lbl);
    }
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    var textNode = document.createElement("span");
    textNode.className = "bubble-text";
    textNode.textContent = text;
    bubble.appendChild(textNode);
    var time = document.createElement("span");
    time.className = "msg-time";
    time.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    bubble.appendChild(time);
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
    var lbl = document.createElement("div");
    lbl.className = "msg-label"; lbl.textContent = assistantName;
    var bubble = document.createElement("div");
    bubble.className = "bubble typing-bubble";
    var dots = document.createElement("span");
    dots.className = "typing-dots";
    for (var i = 0; i < 3; i += 1) {
      var dot = document.createElement("i");
      dots.appendChild(dot);
    }
    var label = document.createElement("span");
    label.className = "typing-label";
    label.textContent = "typing";
    bubble.appendChild(dots);
    bubble.appendChild(label);
    wrap.appendChild(lbl); wrap.appendChild(bubble);
    chat.appendChild(wrap);
    lastRole = "assistant";
    scrollToBottom();
    return wrap;
  }

  /* ---------- result panel ---------- */
  function setText(el, v) { el.textContent = (v === undefined || v === null || v === "") ? "—" : v; }

  function renderDraft(draft, missing) {
    els.draftKnown.innerHTML = "";
    Object.keys(FIELD_LABELS).forEach(function (key) {
      if (draft[key]) {
        var row = document.createElement("div");
        var dt = document.createElement("dt"); dt.textContent = FIELD_LABELS[key];
        var dd = document.createElement("dd"); dd.textContent = draft[key];
        row.appendChild(dt); row.appendChild(dd);
        els.draftKnown.appendChild(row);
      }
    });
    els.draftMissing.innerHTML = "";
    (missing || []).forEach(function (key) {
      var li = document.createElement("li");
      li.textContent = FIELD_LABELS[key] || key;
      els.draftMissing.appendChild(li);
    });
    els.rcDraft.classList.remove("hidden");
  }

  function getJSON(url) {
    return fetch(url).then(function (r) { return r.ok ? r.json() : null; })
                     .catch(function () { return null; });
  }

  function renderPanel(data) {
    els.empty.classList.add("hidden");
    els.result.classList.remove("hidden");

    var draft = data.lead_draft || {};
    var hasDraft = Object.keys(draft).length > 0;
    var mode = data.mode || "answering";

    // Dialogue mode summary.
    setText(els.mode, MODE_LABEL[mode] || mode);
    els.paused.classList.toggle("hidden", !data.qualification_paused);
    var interests = (data.known_interests || []).join(", ");
    setText(els.interests, interests);
    setText(els.next, data.next_step);

    if (data.lead_created) {
      setText(els.lCompany, draft.company);
      setText(els.lContact, draft.contact_email);
      setText(els.lService, draft.service_interest);
      setText(els.lBudget, draft.budget_range);
      els.rcLead.classList.remove("hidden");
      els.rcDraft.classList.add("hidden");
    } else if (hasDraft && mode === "qualifying") {
      // Only show a "lead draft" while we're actually qualifying — never imply
      // the user is a lead during an exploratory chat.
      els.rcLead.classList.add("hidden");
      renderDraft(draft, data.missing_fields);
    } else {
      els.rcLead.classList.add("hidden");
      els.rcDraft.classList.add("hidden");
    }

    if (data.ticket_created && data.ticket_id) {
      getJSON("/tickets/" + data.ticket_id).then(function (t) {
        if (!t) { return; }
        setText(els.tId, "TCK-" + t.id);
        setText(els.tReason, (t.reason || "").replace(/_/g, " "));
        setText(els.tPriority, t.priority);
        setText(els.tStatus, t.status);
        els.rcTicket.classList.remove("hidden");
      });
    } else {
      els.rcTicket.classList.add("hidden");
    }

    if (data.sources && data.sources.length) {
      setText(els.sources, data.sources.join(", "));
      els.rcSources.classList.remove("hidden");
    } else {
      els.rcSources.classList.add("hidden");
    }

    els.rcMemory.classList.toggle("hidden", !data.memory_used);

    // Backend decision: planner recommendation + validation outcome (honest).
    var rec = data.recommended_action || "answer_only";
    setText(els.action, REC_ACTION_LABEL[rec] || rec);
    var v = data.validation || {};
    var vText = VALIDATION_LABEL[v.reason] || v.reason || "—";
    setText(els.validation, vText);
    els.validation.classList.toggle("green", v.allowed === true);
    els.validation.classList.toggle("amber", v.allowed === false);
    setText(els.executed, data.action_executed ? "Yes" : "No");

    setText(els.workflow, ACTION_LABEL[data.action] || "Replied");
    var shownIntent = data.user_intent || data.intent;
    setText(els.intent, INTENT_LABEL[shownIntent] || shownIntent);
  }

  /* ---------- send ---------- */
  function postChat(text) {
    return fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: getSessionId(), user_message: text })
    }).then(function (r) { return r.ok ? r.json() : null; });
  }

  function send(text) {
    if (!text || busy) { return; }
    busy = true; sendBtn.disabled = true; input.disabled = true;
    addMessage("user", text);
    var typing = showTyping();
    postChat(text)
      .then(function (data) {
        typing.remove(); lastRole = null;
        if (!data) { throw new Error("no response"); }
        addMessage("assistant", data.answer || "…");
        renderPanel(data);
      })
      .catch(function () {
        typing.remove(); lastRole = null;
        addMessage("assistant", "Sorry — I couldn't reach the backend. Make sure the API is running.");
      })
      .finally(function () { busy = false; sendBtn.disabled = false; input.disabled = false; input.focus(); });
  }

  function newConversation() {
    localStorage.setItem(SESSION_KEY, newSessionId());
    chat.innerHTML = "";
    if (emptyChat) { chat.appendChild(emptyChat); emptyChat.style.display = ""; }
    lastRole = null;
    els.result.classList.add("hidden");
    els.empty.classList.remove("hidden");
    document.querySelectorAll(".qa").forEach(function (b) { b.classList.remove("active"); });
  }

  /* ---------- wiring ---------- */
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text) { return; }
    input.value = "";
    document.querySelectorAll(".qa").forEach(function (b) { b.classList.remove("active"); });
    send(text);
  });

  document.querySelectorAll(".qa").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var msg = btn.getAttribute("data-prompt");
      if (!msg) { return; }
      send(msg);
    });
  });

  if (newChatBtn) { newChatBtn.addEventListener("click", newConversation); }

  loadConfig();
  getSessionId();
})();
