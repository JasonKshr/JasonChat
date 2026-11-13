(() => {
  const $ = (selector) => document.querySelector(selector);
  const authScreen = $("#auth-screen");
  const chatScreen = $("#chat-screen");
  const authForm = $("#auth-form");
  const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;
  const conversations = new Map();
  let profile = null;
  let activeConversationId = null;
  let authMode = "login";
  let searchTimer = null;
  let pollTimer = null;

  function getCookie(name) {
    const cookie = document.cookie.split("; ").find((item) => item.startsWith(`${name}=`));
    return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : "";
  }

  async function api(path, options = {}) {
    const headers = { Accept: "application/json", ...options.headers };
    if (options.body && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }
    const token = getCookie("csrftoken") || csrfToken;
    if (token && options.method && options.method !== "GET") headers["X-CSRFToken"] = token;
    const response = await fetch(path, { credentials: "same-origin", ...options, headers });
    if (response.status === 204) return null;
    const contentType = response.headers.get("content-type") || "";
    const result = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok) {
      const detail = result?.error || result?.detail || Object.values(result || {}).flat().join(" ");
      throw new Error(detail || `Request failed (${response.status})`);
    }
    return result;
  }

  function showError(element, message) {
    element.textContent = message || "";
  }

  function initials(name) {
    return (name || "?").trim().charAt(0).toUpperCase();
  }

  function avatar(element, name, colorSeed = name) {
    element.textContent = initials(name);
    const colors = ["#d9e8dd", "#f0dfc8", "#e7ddef", "#dce7f1", "#f2d9d4"];
    let hash = 0;
    for (const char of colorSeed || "") hash = (hash * 31 + char.charCodeAt(0)) | 0;
    element.style.setProperty("--avatar-color", colors[Math.abs(hash) % colors.length]);
  }

  function dateLabel(dateString) {
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return "";
    const today = new Date();
    if (date.toDateString() === today.toDateString()) {
      return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    }
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  }

  function friendlyTime(dateString) {
    const date = new Date(dateString);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }

  function conversationName(conversation) {
    if (conversation.name) return conversation.name;
    const other = conversation.members?.find((member) => member.username !== profile.username);
    return other?.username || "Conversation";
  }

  function renderConversationList() {
    const list = $("#conversation-list");
    const filter = $("#chat-filter").value.trim().toLowerCase();
    list.replaceChildren();
    const items = [...conversations.values()]
      .filter((conversation) => conversationName(conversation).toLowerCase().includes(filter))
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    $("#conversation-count").textContent = items.length ? String(items.length).padStart(2, "0") : "";
    for (const conversation of items) {
      const name = conversationName(conversation);
      const button = document.createElement("button");
      button.type = "button";
      button.className = `conversation-item${conversation.id === activeConversationId ? " selected" : ""}`;
      button.dataset.id = conversation.id;
      const image = document.createElement("span");
      image.className = "avatar";
      avatar(image, name, String(conversation.id));
      const copy = document.createElement("span");
      copy.className = "conversation-copy";
      const title = document.createElement("strong");
      title.textContent = name;
      const preview = document.createElement("span");
      const latest = conversation.messages?.at(-1);
      preview.textContent = latest?.content || (conversation.is_group ? "Group conversation" : "Say hello");
      const time = document.createElement("span");
      time.className = "conversation-time";
      time.textContent = latest ? dateLabel(latest.sent_at) : "";
      copy.append(title, preview);
      button.append(image, copy, time);
      button.addEventListener("click", () => openConversation(conversation.id));
      list.append(button);
    }
    if (!items.length && filter) {
      const empty = document.createElement("p");
      empty.className = "list-empty";
      empty.textContent = "No conversations found.";
      list.append(empty);
    }
  }

  function renderMessages(items) {
    const container = $("#messages");
    const wasNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
    container.replaceChildren();
    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "messages-empty";
      const mark = document.createElement("span");
      mark.className = "messages-empty-mark";
      mark.setAttribute("aria-hidden", "true");
      mark.textContent = "✳";
      const title = document.createElement("strong");
      title.textContent = "A fresh conversation";
      const hint = document.createElement("span");
      hint.textContent = "Send a hello to get things started.";
      empty.append(mark, title, hint);
      container.append(empty);
      return;
    }
    let previousDay = "";
    for (const message of items) {
      const date = new Date(message.sent_at);
      const day = Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
      if (day && day !== previousDay) {
        const divider = document.createElement("div");
        divider.className = "date-divider";
        const label = document.createElement("span");
        label.textContent = day;
        divider.append(label);
        container.append(divider);
        previousDay = day;
      }
      const mine = conversationMemberId(activeConversationId, profile.username) === message.sender;
      const row = document.createElement("article");
      row.className = `message-row${mine ? " mine" : ""}`;
      const bubble = document.createElement("div");
      bubble.className = "message-bubble";
      const content = document.createElement("p");
      content.textContent = message.content;
      const time = document.createElement("time");
      time.textContent = friendlyTime(message.sent_at);
      bubble.append(content, time);
      row.append(bubble);
      container.append(row);
    }
    if (wasNearBottom) container.scrollTop = container.scrollHeight;
  }

  function conversationMemberId(id, username) {
    return conversations.get(id)?.members?.find((member) => member.username === username)?.id;
  }

  async function loadConversations() {
    showError($("#sidebar-error"), "");
    const results = await api("/chat/");
    const hydrated = await Promise.all(results.map(async (conversation) => {
      const members = await api(`/chat/${conversation.id}/participants/`);
      return { ...conversation, members };
    }));
    conversations.clear();
    for (const conversation of hydrated) conversations.set(conversation.id, conversation);
    renderConversationList();
    if (!activeConversationId && hydrated.length === 0) showEmptyState();
    else if (activeConversationId && !conversations.has(activeConversationId)) showEmptyState();
  }

  function showEmptyState() {
    activeConversationId = null;
    $("#active-chat").classList.add("hidden");
    $("#empty-state").classList.remove("hidden");
    $("#sidebar").classList.remove("mobile-hidden");
    renderConversationList();
  }

  async function openConversation(id) {
    activeConversationId = id;
    renderConversationList();
    $("#empty-state").classList.add("hidden");
    $("#active-chat").classList.remove("hidden");
    $("#sidebar").classList.add("mobile-hidden");
    const conversation = conversations.get(id);
    const name = conversationName(conversation);
    $("#chat-title").textContent = name;
    $("#chat-subtitle").textContent = conversation.is_group
      ? `${conversation.members.length} people in this conversation`
      : "Here for a good chat";
    avatar($("#chat-avatar"), name, String(id));
    $("#messages").replaceChildren();
    try {
      const messages = await api(`/chat/${id}/messages/`);
      if (activeConversationId !== id) return;
      conversation.messages = messages;
      renderMessages(messages);
      renderConversationList();
      $("#message-input").focus();
    } catch (error) {
      showError($("#sidebar-error"), error.message);
    }
  }

  async function refreshActiveMessages() {
    const id = activeConversationId;
    if (!id || document.hidden) return;
    try {
      const messages = await api(`/chat/${id}/messages/`);
      if (activeConversationId !== id) return;
      const existing = conversations.get(id).messages || [];
      if (messages.length !== existing.length || messages.at(-1)?.id !== existing.at(-1)?.id) {
        conversations.get(id).messages = messages;
        renderMessages(messages);
        renderConversationList();
      }
    } catch (error) {
      showError($("#sidebar-error"), error.message);
    }
  }

  function showChat(profileData) {
    profile = profileData;
    authScreen.classList.add("hidden");
    chatScreen.classList.remove("hidden");
    $("#account-name").textContent = profile.username;
    avatar($("#account-avatar"), profile.username);
    activeConversationId = null;
    loadConversations().catch((error) => showError($("#sidebar-error"), error.message));
    clearInterval(pollTimer);
    pollTimer = setInterval(refreshActiveMessages, 5000);
  }

  async function startApp() {
    try {
      showChat(await api("/users/me/"));
    } catch {
      chatScreen.classList.add("hidden");
      authScreen.classList.remove("hidden");
    }
  }

  function setAuthMode(mode) {
    authMode = mode;
    const registering = mode === "register";
    $("#auth-title").textContent = registering ? "Your people are waiting." : "Good conversations start here.";
    $("#email-field").classList.toggle("hidden", !registering);
    $("#email").required = registering;
    $("#password").autocomplete = registering ? "new-password" : "current-password";
    $("#auth-submit").textContent = registering ? "Create account" : "Sign in";
    $(".auth-footnote").textContent = registering ? "A good conversation is just a hello away." : "Your conversations, all in one place.";
    document.querySelectorAll(".auth-tab").forEach((tab) => {
      const active = tab.dataset.mode === mode;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-selected", String(active));
    });
    showError($("#auth-error"), "");
  }

  authForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = $("#auth-submit");
    submit.disabled = true;
    showError($("#auth-error"), "");
    const form = new FormData(authForm);
    const payload = {
      username: form.get("username"),
      password: form.get("password"),
    };
    if (authMode === "register") payload.email = form.get("email");
    try {
      if (authMode === "register") {
        await api("/users/register/", { method: "POST", body: JSON.stringify(payload) });
      }
      await api("/users/login/", { method: "POST", body: JSON.stringify({ username: payload.username, password: payload.password }) });
      showChat(await api("/users/me/"));
    } catch (error) {
      showError($("#auth-error"), error.message);
    } finally {
      submit.disabled = false;
    }
  });

  document.querySelectorAll(".auth-tab").forEach((tab) => {
    tab.addEventListener("click", () => setAuthMode(tab.dataset.mode));
  });

  async function searchUsers(query) {
    const results = $("#user-search-results");
    results.replaceChildren();
    if (!query.trim()) {
      const hint = document.createElement("p");
      hint.className = "search-hint";
      hint.textContent = "Search for someone to start a conversation.";
      results.append(hint);
      return;
    }
    try {
      const users = await api(`/users/search/?q=${encodeURIComponent(query.trim())}`);
      if (!users.length) {
        const empty = document.createElement("p");
        empty.className = "search-hint";
        empty.textContent = "No one found. Try another username.";
        results.append(empty);
        return;
      }
      for (const user of users) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "user-result";
        const image = document.createElement("span");
        image.className = "avatar";
        avatar(image, user.username, String(user.id));
        const copy = document.createElement("span");
        copy.className = "user-result-copy";
        const name = document.createElement("strong");
        name.textContent = user.username;
        const hint = document.createElement("span");
        hint.textContent = "Start a conversation";
        copy.append(name, hint);
        const arrow = document.createElement("span");
        arrow.className = "user-result-arrow";
        arrow.textContent = "↗";
        button.append(image, copy, arrow);
        button.addEventListener("click", () => beginConversation(user));
        results.append(button);
      }
    } catch (error) {
      const message = document.createElement("p");
      message.className = "search-hint form-error";
      message.textContent = error.message;
      results.append(message);
    }
  }

  async function beginConversation(user) {
    const dialog = $("#new-chat-dialog");
    try {
      const existing = [...conversations.values()].find((conversation) =>
        !conversation.is_group && conversation.members?.some((member) => member.id === user.id)
      );
      if (existing) {
        dialog.close();
        await openConversation(existing.id);
        return;
      }
      const created = await api("/chat/create/", {
        method: "POST",
        body: JSON.stringify({ is_group: false, participants: [user.id] }),
      });
      const members = await api(`/chat/${created.id}/participants/`);
      conversations.set(created.id, { ...created, members, messages: [] });
      dialog.close();
      $("#user-search").value = "";
      $("#chat-filter").value = "";
      await openConversation(created.id);
    } catch (error) {
      const results = $("#user-search-results");
      const message = document.createElement("p");
      message.className = "search-hint form-error";
      message.textContent = error.message;
      results.prepend(message);
    }
  }

  function openNewChat() {
    $("#new-chat-dialog").showModal();
    $("#user-search").focus();
  }

  $("#new-chat-button").addEventListener("click", openNewChat);
  $("#empty-new-chat").addEventListener("click", openNewChat);
  $("#close-dialog").addEventListener("click", () => $("#new-chat-dialog").close());
  $("#new-chat-dialog").addEventListener("click", (event) => {
    if (event.target === $("#new-chat-dialog")) $("#new-chat-dialog").close();
  });
  $("#user-search").addEventListener("input", (event) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => searchUsers(event.target.value), 250);
  });
  $("#chat-filter").addEventListener("input", renderConversationList);

  $("#message-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = $("#message-input");
    const content = input.value.trim();
    const id = activeConversationId;
    if (!content || !id) return;
    const button = $("#message-form button[type='submit']");
    button.disabled = true;
    try {
      const message = await api("/chat/send/", {
        method: "POST",
        body: JSON.stringify({ conversation: id, content }),
      });
      if (activeConversationId !== id) return;
      input.value = "";
      conversations.get(id).messages = [...(conversations.get(id).messages || []), message];
      renderMessages(conversations.get(id).messages);
      renderConversationList();
    } catch (error) {
      showError($("#sidebar-error"), error.message);
    } finally {
      button.disabled = !input.value.trim();
    }
  });

  $("#message-input").addEventListener("input", (event) => {
    event.target.style.height = "auto";
    event.target.style.height = `${Math.min(event.target.scrollHeight, 120)}px`;
    $("#message-form button[type='submit']").disabled = !event.target.value.trim();
  });
  $("#message-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      $("#message-form").requestSubmit();
    }
  });
  $("#mobile-back").addEventListener("click", showEmptyState);
  $("#logout-button").addEventListener("click", async () => {
    try {
      await api("/users/logout/", { method: "POST" });
      clearInterval(pollTimer);
      conversations.clear();
      profile = null;
      chatScreen.classList.add("hidden");
      authScreen.classList.remove("hidden");
      authForm.reset();
    } catch (error) {
      showError($("#sidebar-error"), error.message);
    }
  });

  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      $("#chat-filter").focus();
    }
    if (event.key === "Escape" && $("#new-chat-dialog").open) $("#new-chat-dialog").close();
  });

  startApp();
})();
