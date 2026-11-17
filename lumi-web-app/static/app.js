const STORAGE_KEY = window.LUMI_DEMO ? "lumina-bloom-demo-data-v1" : "lumina-bloom-data-v1";
const FEEDBACK_KEY = window.LUMI_DEMO ? "lumina-bloom-demo-feedback-v1" : "lumina-bloom-feedback-v1";
const monthNames = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"];

let currentInput = 0;
const today = new Date();
const currentYear = today.getFullYear();
const currentMonth = today.getMonth();
const currentDate = today.getDate();
let viewingYear = currentYear;
let viewingMonth = currentMonth;

let appState = {
  dataStore: loadDataStore(),
  feedbacks: loadFeedbacks(),
  location: null,
  weather: null,
  places: { candidate_places: [], count: 0 },
  agent: null,
  bloomChatHistory: [],
  bodyState: "",
};

const DEFAULT_LOCATION = {
  lat: Number(window.DEFAULT_LOCATION_LAT ?? 22.3193),
  lon: Number(window.DEFAULT_LOCATION_LON ?? 114.1694),
};

const timeDisplay = document.getElementById("time-display");
const calendarGrid = document.getElementById("calendar-grid");
const monthHeader = document.getElementById("month-header");
const labelTotal = document.getElementById("total-sunlight-label");
const labelCycle = document.getElementById("cycle-label");
const harvestContainer = document.getElementById("harvest-container");
const weatherTemp = document.getElementById("weather-temp");
const weatherUv = document.getElementById("weather-uv");
const placesStatus = document.getElementById("places-status");
const placesList = document.getElementById("places-list");

const dayModal = document.getElementById("day-modal");
const dayDateTxt = document.getElementById("day-modal-date");
const dayMinsTxt = document.getElementById("day-modal-mins");
document.getElementById("close-day-btn").addEventListener("click", () => dayModal.classList.remove("active"));

const viewDefault = document.getElementById("agent-view-default");
const viewReasons = document.getElementById("agent-view-reasons");
const viewResponse = document.getElementById("agent-view-response");
const agentMainText = document.getElementById("agent-main-text");
const responseText = document.getElementById("agent-response-text");
const agentProvider = document.getElementById("agent-provider");
const acceptButton = document.getElementById("btn-accept-nudge");
const stressText = document.getElementById("stress-text");
const stressBar = document.getElementById("stress-bar");
const slackSubtext = document.getElementById("slack-subtext");
const feedbackLog = document.getElementById("feedback-log");
const bloomChatStatus = document.getElementById("bloom-chat-status");
const bloomChatHistoryEl = document.getElementById("bloom-chat-history");
const bloomChatInput = document.getElementById("bloom-chat-input");
const bloomChatSend = document.getElementById("bloom-chat-send");
const bodyStateInput = document.getElementById("body-state-input");

function loadDataStore() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const store = JSON.parse(raw);
      if (store && typeof store === "object" && !Array.isArray(store)) {
        return Object.fromEntries(Object.entries(store).filter(([key, value]) =>
          /^\d{4}-\d{1,2}-\d{1,2}$/.test(key) && Number.isFinite(value) && value >= 0));
      }
    }
  } catch (error) {
    console.warn("Failed to read local storage, using demo seed.", error);
  }
  return window.LUMI_DEMO ? buildDemoSeed() : {};
}

function saveDataStore() {
  persistLocal(STORAGE_KEY, appState.dataStore);
}

function loadFeedbacks() {
  try {
    const raw = localStorage.getItem(FEEDBACK_KEY);
    const feedbacks = raw ? JSON.parse(raw) : [];
    return Array.isArray(feedbacks) ? feedbacks.filter(item => item &&
      ["busy", "lazy", "mood"].includes(item.reason) && typeof item.time === "string").slice(-12) : [];
  } catch (error) {
    console.warn("Failed to read feedbacks.", error);
    return [];
  }
}

function saveFeedbacks() {
  persistLocal(FEEDBACK_KEY, appState.feedbacks.slice(-12));
}

function persistLocal(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.warn("Storage unavailable. Changes last for this visit only.", error);
    agentProvider.textContent = "Storage unavailable: session only";
  }
}

function buildDemoSeed() {
  const store = {};
  let targetMins = 320;
  const tempDate = new Date(currentYear, currentMonth, currentDate - 1);
  while (targetMins > 0) {
    const y = tempDate.getFullYear();
    const m = tempDate.getMonth();
    const d = tempDate.getDate();
    const add = Math.min(targetMins, 40);
    store[`${y}-${m}-${d}`] = add;
    targetMins -= add;
    tempDate.setDate(tempDate.getDate() - 1);
  }
  return store;
}

function totalMinutes() {
  return Object.values(appState.dataStore).reduce((a, b) => a + b, 0);
}

function getTodayMinutes() {
  return appState.dataStore[`${currentYear}-${currentMonth}-${currentDate}`] || 0;
}

function last7DayAverage() {
  let total = 0;
  for (let i = 0; i < 7; i += 1) {
    const d = new Date(currentYear, currentMonth, currentDate - i);
    total += appState.dataStore[`${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`] || 0;
  }
  return Math.round(total / 7);
}

function getBloomStageLabel() {
  const totalHours = (totalMinutes() / 60) % 30;
  if (totalHours < 1) return "seed";
  if (totalHours < 5) return "sprout";
  if (totalHours < 15) return "young";
  if (totalHours < 25) return "budding";
  return "blooming";
}

function updateFeedbackLog() {
  if (!appState.feedbacks.length) {
    feedbackLog.textContent = "No feedback yet. Reject a nudge to teach Lumi your routine.";
    return;
  }
  const text = appState.feedbacks.slice(-5).map((item) => `> ${item.time}: ${item.reason}`).join("\n");
  feedbackLog.textContent = text;
}

function openDayModal(year, month, day, mins) {
  dayDateTxt.textContent = `${monthNames[month].substring(0, 3)} ${day}, ${year}`;
  dayMinsTxt.textContent = `${mins} MINS`;
  dayModal.classList.add("active");
}

function renderCalendar() {
  monthHeader.textContent = `${monthNames[viewingMonth]} ${viewingYear}`;
  calendarGrid.innerHTML = "";
  const firstDayOfWeek = new Date(viewingYear, viewingMonth, 1).getDay();
  const daysInMonth = new Date(viewingYear, viewingMonth + 1, 0).getDate();

  for (let i = 0; i < firstDayOfWeek; i += 1) {
    const emptyCell = document.createElement("div");
    emptyCell.classList.add("day-cell", "empty-cell");
    calendarGrid.appendChild(emptyCell);
  }

  for (let i = 1; i <= daysInMonth; i += 1) {
    const cell = document.createElement("div");
    cell.classList.add("day-cell");
    cell.textContent = i;
    if (viewingYear === currentYear && viewingMonth === currentMonth && i === currentDate) {
      cell.classList.add("today-cell");
      const indicator = document.createElement("div");
      indicator.classList.add("today-indicator");
      indicator.textContent = "TODAY";
      cell.appendChild(indicator);
    }

    const key = `${viewingYear}-${viewingMonth}-${i}`;
    const mins = appState.dataStore[key] || 0;
    if (mins >= 120) cell.classList.add("heat-3");
    else if (mins >= 60) cell.classList.add("heat-2");
    else if (mins >= 30) cell.classList.add("heat-1");

    cell.addEventListener("click", () => openDayModal(viewingYear, viewingMonth, i, mins));
    calendarGrid.appendChild(cell);
  }
}

function renderBloom() {
  const totalHours = totalMinutes() / 60;
  const cycleLength = 30;
  const currentCycleHours = totalHours % cycleLength;
  const harvestedTomatoes = Math.floor(totalHours / cycleLength);

  labelTotal.textContent = `Total Sunlight: ${totalHours.toFixed(2)} Hours`;
  labelCycle.textContent = `Cycle Progress: ${currentCycleHours.toFixed(1)} / 30h`;

  const plant = document.getElementById("pixel-plant");
  plant.className = "pixel-plant";
  if (currentCycleHours >= 25) plant.classList.add("stage-5");
  else if (currentCycleHours >= 15) plant.classList.add("stage-4");
  else if (currentCycleHours >= 5) plant.classList.add("stage-3");
  else if (currentCycleHours >= 1) plant.classList.add("stage-2");
  else plant.classList.add("stage-1");

  harvestContainer.innerHTML = "";
  if (harvestedTomatoes === 0) {
    harvestContainer.innerHTML = '<span class="subdued">No harvests yet</span>';
  } else {
    for (let i = 0; i < harvestedTomatoes; i += 1) {
      const icon = document.createElement("div");
      icon.innerHTML = `<svg viewBox="0 0 10 10" width="20" height="20" style="shape-rendering: crispEdges;"><rect x="1" y="3" width="8" height="6" fill="#D32F2F"/><rect x="2" y="2" width="6" height="8" fill="#D32F2F"/><rect x="3" y="4" width="2" height="2" fill="#FF8888"/><rect x="4" y="1" width="2" height="2" fill="#214D23"/><rect x="3" y="2" width="4" height="1" fill="#214D23"/></svg>`;
      harvestContainer.appendChild(icon);
    }
  }
}

function renderWeather() {
  if (!appState.weather) return;
  const sample = appState.weather.source === "fallback" || appState.weather.source === "demo-sample";
  weatherTemp.textContent = `${Math.round(appState.weather.temperature_c)}°C${sample ? "*" : ""}`;
  weatherUv.textContent = `UV: ${Number(appState.weather.uv_index || 0).toFixed(1)}${sample ? " (sample)" : ""}`;
}

function renderPlaces() {
  const aiPlaces = appState.agent?.place_recommendations || [];
  const candidateCount = appState.places?.count || appState.places?.candidate_places?.length || 0;
  placesList.innerHTML = "";

  if (!aiPlaces.length) {
    placesStatus.textContent = appState.location
      ? "Nearby places unavailable. You can still log your time."
      : "Allow location to load nearby spots.";
    return;
  }

  placesStatus.textContent = window.LUMI_DEMO
    ? "3 sample spots for this demo; these are not real nearby locations."
    : `${aiPlaces.length} suggestions from ${candidateCount} candidates.${appState.location?.source === "fallback-default" ? " Using default location (not GPS)." : ""}`;
  aiPlaces.slice(0, 3).forEach((place) => {
    const item = document.createElement("div");
    item.className = "place-item";
    const score = place.recommendation_score ?? 0;
    const label = place.recommendation_label || "Recommended";
    item.innerHTML = `
      <div class="place-header">
        <div class="place-name">${escapeHtml(place.name)}</div>
        <div class="place-score">${escapeHtml(label)} · ${escapeHtml(score)}/100</div>
      </div>
      <div class="place-meta">${escapeHtml(place.why)} · ${escapeHtml(place.distance_m)}m</div>
    `;
    try {
      const url = new URL(place.map_url);
      if (url.protocol === "https:" && url.hostname === "www.openstreetmap.org") {
        const link = document.createElement("a");
        link.className = "place-link";
        link.href = url.href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "OPEN MAP";
        item.appendChild(link);
      }
    } catch (_) { /* Sample spots have no map destination. */ }
    placesList.appendChild(item);
  });
}

function renderAgent() {
  const agent = appState.agent;
  if (!agent) return;
  agentMainText.textContent = agent.nudge_text;
  agentProvider.textContent = agent.provider || "local guide";
  acceptButton.textContent = `ACCEPT (${agent.suggested_duration_min}M)`;
  const biometric = agent.biometric_estimate || {
    stress_label: "MODERATE",
    stress_pct: 45,
    slacking_probability_pct: 35,
    slack_subtext: "Fallback mode is active.",
  };
  stressText.textContent = biometric.stress_label;
  stressBar.style.width = `${biometric.stress_pct}%`;
  if (biometric.stress_label === "HIGH") {
    stressText.style.color = "var(--tomato-red)";
    stressBar.style.background = "var(--tomato-red)";
  } else if (biometric.stress_label === "LOW") {
    stressText.style.color = "var(--pixel-green)";
    stressBar.style.background = "var(--pixel-green)";
  } else {
    stressText.style.color = "var(--flower-yellow)";
    stressBar.style.background = "var(--flower-yellow)";
  }
  slackSubtext.textContent = `${biometric.slack_subtext} Skip risk: ${biometric.slacking_probability_pct}%.`;
}

function renderBloomChat() {
  bloomChatHistoryEl.innerHTML = "";
  if (!appState.bloomChatHistory.length) {
    bloomChatHistoryEl.innerHTML = `
      <div class="chat-bubble assistant">
        Hi, I'm Bloom. You can tell me if you're tired, stressed, low-energy, or just want a little company.
      </div>
    `;
    return;
  }

  appState.bloomChatHistory.forEach((msg) => {
    const div = document.createElement("div");
    div.className = `chat-bubble ${msg.role === "user" ? "user" : "assistant"}`;
    div.textContent = msg.content;
    bloomChatHistoryEl.appendChild(div);
  });
  bloomChatHistoryEl.scrollTop = bloomChatHistoryEl.scrollHeight;
}

function updateApp() {
  renderCalendar();
  renderBloom();
  renderWeather();
  renderPlaces();
  renderAgent();
  renderBloomChat();
  updateFeedbackLog();
}

function switchScreen(targetId) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  document.getElementById(targetId).classList.add("active");
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.target === targetId));
}

function pushFeedback(reason) {
  appState.feedbacks.push({ reason, time: new Date().toLocaleString() });
  appState.feedbacks = appState.feedbacks.slice(-12);
  saveFeedbacks();
}

function recentFeedbackReasons() {
  return appState.feedbacks.slice(-5).map((item) => item.reason);
}

async function apiGet(url) {
  if (window.LUMI_DEMO) return window.lumiDemoRequest(url);
  const response = await fetch(url);
  if (!response.ok) throw new Error(`GET ${url} failed`);
  return response.json();
}

async function apiPost(url, payload) {
  if (window.LUMI_DEMO) return window.lumiDemoRequest(url, payload);
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`POST ${url} failed`);
  return response.json();
}

async function loadLocation() {
  if (window.LUMI_DEMO) return { ...DEFAULT_LOCATION, source: "demo-sample" };
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve({ ...DEFAULT_LOCATION, source: "fallback-default" });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({ lat: position.coords.latitude, lon: position.coords.longitude, source: "browser-geolocation" }),
      () => resolve({ ...DEFAULT_LOCATION, source: "fallback-default" }),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 10 * 60 * 1000 },
    );
  });
}

function buildAgentContext() {
  return {
    user_profile: {
      preferred_duration_min: appState.agent?.suggested_duration_min || 10,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    },
    today_context: {
      local_time: new Date().toISOString(),
      minutes_outdoors_today: getTodayMinutes(),
    },
    weather: appState.weather,
    places: {
      source: appState.places?.source || null,
      count: appState.places?.count || 0,
      candidate_places: appState.places?.candidate_places || [],
    },
    recent_behavior: {
      last_7d_avg_minutes: last7DayAverage(),
      skip_reasons: recentFeedbackReasons(),
    },
    location: appState.location,
  };
}

function buildBloomContext() {
  const weather = appState.weather || {};
  const biometrics = appState.agent?.biometric_estimate || {};
  return {
    sunlight_today_min: getTodayMinutes(),
    sunlight_7d_avg_min: last7DayAverage(),
    stress_label: biometrics.stress_label || "MODERATE",
    stress_pct: biometrics.stress_pct || 45,
    slacking_probability_pct: biometrics.slacking_probability_pct || 35,
    weather_summary: `temp=${weather.temperature_c ?? "?"}C, uv=${weather.uv_index ?? "?"}, cloud=${weather.cloud_cover ?? "?"}%`,
    body_state: appState.bodyState || "",
    recent_skip_reasons: recentFeedbackReasons(),
    bloom_stage: getBloomStageLabel(),
  };
}

async function refreshWeatherAndPlaces() {
  appState.location = await loadLocation();
  const [weatherResult, placesResult] = await Promise.allSettled([
    apiGet(`/api/weather?lat=${appState.location.lat}&lon=${appState.location.lon}`),
    apiGet(`/api/places?lat=${appState.location.lat}&lon=${appState.location.lon}&radius=1500`),
  ]);

  if (weatherResult.status === "fulfilled") {
    appState.weather = weatherResult.value;
  } else {
    console.error(weatherResult.reason);
  }

  if (placesResult.status === "fulfilled") {
    appState.places = placesResult.value;
  } else {
    console.error(placesResult.reason);
    appState.places = { candidate_places: [], count: 0 };
    placesStatus.textContent = "Weather loaded, but nearby place lookup is unavailable right now.";
  }

  updateApp();
}

async function refreshAgent() {
  try {
    const recommendation = await apiPost("/api/agent/recommend", buildAgentContext());
    appState.agent = recommendation;
    updateApp();
  } catch (error) {
    console.error(error);
    appState.agent = {
      provider: "offline-fallback",
      nudge_text: "A short 5-minute outdoor break is enough for now.",
      suggested_duration_min: 5,
      place_recommendations: [],
      biometric_estimate: {
        stress_label: "MODERATE",
        stress_pct: 45,
        slacking_probability_pct: 35,
        slack_subtext: "Fallback mode is active.",
      },
    };
    updateApp();
  }
}

async function sendBloomChat() {
  if (bloomChatSend.disabled) return;
  const text = bloomChatInput.value.trim();
  if (!text) return;
  bloomChatSend.disabled = true;
  appState.bodyState = bodyStateInput.value.trim();
  appState.bloomChatHistory.push({ role: "user", content: text });
  bloomChatInput.value = "";
  bloomChatStatus.textContent = "Bloom is thinking...";
  renderBloomChat();

  try {
    const data = await apiPost("/api/bloom/chat", {
      message: text,
      context: buildBloomContext(),
      history: appState.bloomChatHistory.slice(0, -1),
    });
    const reply = data.reply || "I'm here with you. Let's keep this moment gentle.";
    appState.bloomChatHistory.push({ role: "assistant", content: reply });
    bloomChatStatus.textContent = data.provider ? `Connected to ${data.provider}` : "Bloom is here.";
  } catch (error) {
    console.error(error);
    appState.bloomChatHistory.push({ role: "assistant", content: "I couldn't speak just now, but I'm still here with you. Try again in a moment." });
    bloomChatStatus.textContent = "Local Bloom backend unavailable.";
  }
  bloomChatSend.disabled = false;
  renderBloomChat();
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.getElementById("btn-minus").addEventListener("click", () => {
  if (currentInput > 0) currentInput -= 5;
  timeDisplay.textContent = currentInput;
});

document.getElementById("btn-plus").addEventListener("click", () => {
  currentInput += 5;
  timeDisplay.textContent = currentInput;
});

document.getElementById("btn-accept-nudge").addEventListener("click", () => {
  const minutes = appState.agent?.suggested_duration_min || 10;
  currentInput = minutes;
  timeDisplay.textContent = currentInput;
});

document.getElementById("btn-reject-init").addEventListener("click", () => {
  viewDefault.style.display = "none";
  viewReasons.style.display = "block";
  viewResponse.style.display = "none";
});

document.getElementById("btn-back-to-default").addEventListener("click", () => {
  viewDefault.style.display = "block";
  viewReasons.style.display = "none";
  viewResponse.style.display = "none";
});

document.querySelectorAll(".btn-reason").forEach((btn) => {
  btn.addEventListener("click", async (e) => {
    const reason = e.target.dataset.reason;
    pushFeedback(reason);
    viewReasons.style.display = "none";
    viewResponse.style.display = "block";
    responseText.textContent = `Thanks. I saved “${reason}” as a signal and will adapt future nudges.`;
    updateApp();
    await refreshAgent();
    responseText.textContent = appState.agent?.nudge_text || responseText.textContent;
  });
});

document.getElementById("btn-save").addEventListener("click", async () => {
  if (currentInput <= 0) return;
  const key = `${currentYear}-${currentMonth}-${currentDate}`;
  appState.dataStore[key] = (appState.dataStore[key] || 0) + currentInput;
  saveDataStore();
  currentInput = 0;
  timeDisplay.textContent = currentInput;
  updateApp();
  switchScreen("screen-bloom");
  await refreshAgent();
});

document.getElementById("btn-prev-month").addEventListener("click", () => {
  viewingMonth -= 1;
  if (viewingMonth < 0) {
    viewingMonth = 11;
    viewingYear -= 1;
  }
  renderCalendar();
});

document.getElementById("btn-next-month").addEventListener("click", () => {
  viewingMonth += 1;
  if (viewingMonth > 11) {
    viewingMonth = 0;
    viewingYear += 1;
  }
  renderCalendar();
});

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", (e) => switchScreen(e.currentTarget.dataset.target));
});

bloomChatSend.addEventListener("click", sendBloomChat);
bloomChatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendBloomChat();
});
bodyStateInput.addEventListener("input", (e) => {
  appState.bodyState = e.target.value;
});

document.getElementById("btn-reset-demo")?.addEventListener("click", () => {
  appState.dataStore = buildDemoSeed();
  appState.feedbacks = [];
  appState.bloomChatHistory = [];
  appState.bodyState = "";
  bodyStateInput.value = "";
  currentInput = 0;
  timeDisplay.textContent = "0";
  saveDataStore();
  saveFeedbacks();
  viewDefault.style.display = "block";
  viewReasons.style.display = "none";
  viewResponse.style.display = "none";
  switchScreen("screen-log");
  updateApp();
  refreshAgent();
});

(async function init() {
  updateApp();
  await refreshWeatherAndPlaces();
  await refreshAgent();
})();
