/* AI Marketing Agent — web demo client.
   Plain JS, no dependencies. Talks to the existing POST /chat endpoint. */
(function () {
  "use strict";

  var SESSION_KEY = "novagrowth_demo_session_id";

  var SCENARIOS = {
    services: "What services does NovaGrowth Agency provide?",
    pricing: "What pricing packages are available?",
    lead: "Hi, my name is Sam. I work at BrightDesk. We need help with paid ads " +
          "and have a budget around $5k/month. Contact me at sam@brightdesk.example.",
    human: "I need a human manager for a custom enterprise workflow.",
    memory: "Can you remember my company and suggest the next step?"
  };

  var chat = document.getElementById("chat");
  var form = document.getElementById("chat-form");
  var input = document.getElementById("message");
  var sendBtn = document.getElementById("send");
  var clearBtn = document.getElementById("clear");
  var sessionEl = document.getElementById("session");

  var panel = {
    intent: document.getElementById("intent"),
    action: document.getElementById("action"),
    escalated: document.getElementById("escalated"),
    lead: document.getElementById("lead"),
    ticket: document.getElementById("ticket"),
    sources: document.getElementById("sources")
  };

  var busy = false;

  function newSessionId() {
    var rnd = Math.random().toString(36).slice(2, 10);
    return "web-demo-" + Date.now().toString(36) + "-" + rnd;
  }

  function getSessionId() {
    var id = localStorage.getItem(SESSION_KEY);
    if (!id) {
      id = newSessionId();
      localStorage.setItem(SESSION_KEY, id);
    }
    return id;
  }

  function setText(el, value, cls) {
    el.textContent = (value === null || value === undefined || value === "") ? "—" : value;
    el.className = "kv-val" + (cls ? " " + cls : "");
  }

  function scrollToBottom() {
    chat.scrollTop = chat.scrollHeight;
  }

  function addMessage(role, text) {
    var wrap = document.createElement("div");
    wrap.className = "msg " + role;
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    wrap.appendChild(bubble);
    chat.appendChild(wrap);
    scrollToBottom();
    return bubble;
  }

  function addLoading() {
    var wrap = document.createElement("div");
    wrap.className = "msg assistant";
    var bubble = document.createElement("div");
    bubble.className = "bubble loading";
    bubble.textContent = "Thinking…";
    wrap.appendChild(bubble);
    chat.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  function updatePanel(data) {
    // The /chat response includes rich metadata; fall back gracefully if not.
    if (!data || typeof data !== "object") {
      setText(panel.intent, "demo response");
      setText(panel.action, "see backend logs / API docs");
      return;
    }
    setText(panel.intent, data.intent || "demo response", data.intent ? "active" : null);
    setText(panel.action, data.action_taken || "see backend logs / API docs");
    setText(panel.escalated, data.escalated ? "yes" : "no", data.escalated ? "alert" : null);
    setText(panel.lead, data.created_lead_id);
    setText(panel.ticket, data.created_ticket_id);
    if (data.sources && data.sources.length) {
      setText(panel.sources, data.sources.join(", "));
    } else {
      setText(panel.sources, "—");
    }
  }

  function setBusy(state) {
    busy = state;
    sendBtn.disabled = state;
    input.disabled = state;
  }

  async function sendMessage(text) {
    if (busy || !text.trim()) return;
    addMessage("user", text);
    input.value = "";
    setBusy(true);
    var loading = addLoading();

    try {
      var resp = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: getSessionId(),
          user_message: text,
          user_id: "web-demo-user"
        })
      });

      chat.removeChild(loading);

      if (!resp.ok) {
        addMessage("error", "Request failed (" + resp.status + "). Check /health and /docs.");
        return;
      }

      var data = await resp.json();
      addMessage("assistant", data.answer || "(no answer returned)");
      updatePanel(data);
    } catch (err) {
      if (loading.parentNode) chat.removeChild(loading);
      addMessage("error", "Could not reach the server. Is the API running?");
    } finally {
      setBusy(false);
      input.focus();
    }
  }

  function clearSession() {
    var id = newSessionId();
    localStorage.setItem(SESSION_KEY, id);
    sessionEl.textContent = id;
    chat.innerHTML = "";
    addMessage("assistant",
      "New session started. Ask a question or pick a scenario on the left.");
    updatePanel(null);
    setText(panel.escalated, "—");
    setText(panel.lead, "—");
    setText(panel.ticket, "—");
    setText(panel.sources, "—");
  }

  // --- wire up events ---
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    sendMessage(input.value);
  });

  clearBtn.addEventListener("click", clearSession);

  document.querySelectorAll(".scenario").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var msg = SCENARIOS[btn.getAttribute("data-scenario")];
      if (msg) sendMessage(msg);
    });
  });

  // --- init ---
  sessionEl.textContent = getSessionId();
  input.focus();
})();
