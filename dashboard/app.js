
const $ = (selector) => document.querySelector(selector);

const title = $("#panelTitle");
const description = $("#panelDescription");
const preview = $("#preview");
const loginBtn = $("#loginBtn");
const logoutBtn = $("#logoutBtn");
const userLabel = $("#userLabel");
const guildSelect = $("#guildSelect");
const guildStatus = $("#guildStatus");
const selectedServer = $("#selectedServer");
const notice = $("#notice");
const saveBtn = $("#saveBtn");
const saveStatus = $("#saveStatus");

let currentUser = null;
let currentGuilds = [];

function setNotice(message) {
  notice.textContent = message;
}

function setSettingsEnabled(enabled) {
  title.disabled = !enabled;
  description.disabled = !enabled;
  saveBtn.disabled = !enabled;
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {})
    }
  });

  if (response.status === 401) {
    throw new Error("Please sign in with Discord again.");
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || "Request failed.");
  }

  return data;
}

function showPreview() {
  preview.textContent =
    `${title.value.trim() || "Contact Support"}\n\n` +
    `${description.value.trim() || "Choose the button below to open a support ticket."}\n\n` +
    "[ Open Ticket ]";
}

$("#previewBtn").addEventListener("click", showPreview);

loginBtn.addEventListener("click", () => {
  window.location.href = "/auth/login";
});

logoutBtn.addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
  } finally {
    window.location.reload();
  }
});

async function loadGuildConfig(guildId) {
  setSettingsEnabled(false);
  saveStatus.textContent = "";
  selectedServer.textContent =
    guildSelect.options[guildSelect.selectedIndex]?.text || "None";

  try {
    const config = await api(`/dashboard/guilds/${guildId}/config`);

    title.value = config.panel_title ?? "Contact Support";
    description.value =
      config.panel_description ??
      "Choose the button below to open a support ticket.";

    setSettingsEnabled(true);
    setNotice("Server settings loaded. You can now edit the ticket panel.");
  } catch (error) {
    setNotice(error.message);
    setSettingsEnabled(false);
  }
}

guildSelect.addEventListener("change", async () => {
  const guildId = guildSelect.value;

  if (!guildId) {
    selectedServer.textContent = "None";
    setSettingsEnabled(false);
    return;
  }

  await loadGuildConfig(guildId);
});

saveBtn.addEventListener("click", async () => {
  const guildId = guildSelect.value;
  if (!guildId) return;

  saveBtn.disabled = true;
  saveStatus.textContent = "Saving...";

  try {
    await api(`/dashboard/guilds/${guildId}/config`, {
      method: "PUT",
      body: JSON.stringify({
        panel_title: title.value.trim() || "Contact Support",
        panel_description:
          description.value.trim() ||
          "Choose the button below to open a support ticket."
      })
    });

    saveStatus.textContent = "Settings saved successfully.";
  } catch (error) {
    saveStatus.textContent = error.message;
  } finally {
    saveBtn.disabled = false;
  }
});

async function initDashboard() {
  setSettingsEnabled(false);

  try {
    const data = await api("/auth/me");
    currentUser = data.user;
    currentGuilds = data.guilds || [];

    userLabel.textContent =
      currentUser.global_name || currentUser.username;

    loginBtn.hidden = true;
    logoutBtn.hidden = false;

    guildSelect.innerHTML = "";

    if (currentGuilds.length === 0) {
      guildSelect.add(new Option("No manageable servers found", ""));
      guildSelect.disabled = true;
      guildStatus.textContent =
        "Your Discord account has no servers with Manage Server or Administrator permission.";
      setNotice("No manageable servers were found.");
      return;
    }

    guildSelect.add(new Option("Choose a server...", ""));
    for (const guild of currentGuilds) {
      guildSelect.add(new Option(guild.name, guild.id));
    }

    guildSelect.disabled = false;
    guildStatus.textContent = `${currentGuilds.length} manageable server(s) found.`;
    setNotice("Signed in. Select a server to load its settings.");
  } catch {
    currentUser = null;
    currentGuilds = [];

    userLabel.textContent = "Not signed in";
    loginBtn.hidden = false;
    logoutBtn.hidden = true;
    guildSelect.replaceChildren(new Option("Sign in first", ""));
    guildSelect.disabled = true;
    selectedServer.textContent = "None";
    setSettingsEnabled(false);
    setNotice("Sign in with Discord to manage your servers.");
  }
}

initDashboard();
