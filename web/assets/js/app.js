(function () {
  "use strict";

  const LOCAL_STORAGE_KEY = "lcn-grille-designer-cache-v3";
  const UI_STORAGE_KEY = "lcn-grille-designer-ui-v2";
  const STEP_MINUTES = 5;
  const STEP_HEIGHT = 8;
  const DAY_STEPS = (24 * 60) / STEP_MINUTES;
  const MIN_CARD_HEIGHT = 18;
  const DEFAULT_COLLAPSED_PANELS = {
    preview: true,
  };
  const DEFAULT_RUNTIME = {
    paths: {
      musicLibraryRoot: "/path/to/music-library",
      radioRoot: "/path/to/radio",
      poolsDir: "/path/to/radio/pools",
      emissionsDir: "/path/to/radio/emissions",
      jinglesDir: "/path/to/radio/jingles",
      reclamesDir: "/path/to/radio/reclames",
      logsDir: "/path/to/radio/logs",
      webRoot: "/path/to/web-root",
      currentShowJson: "/path/to/web-root/current-show.json",
      nowPlayingJson: "/path/to/web-root/nowplaying.json",
      historyDir: "/path/to/web-root/history",
    },
    liveInput: {
      enabled: true,
      harborName: "live",
      port: 8005,
      password: "",
      icy: true,
    },
    outputs: [
      {
        id: "opus",
        enabled: true,
        format: "opus",
        bitrateKbps: 96,
        stereo: true,
        host: "localhost",
        port: 8000,
        password: "",
        mount: "/stream",
        name: "Le Chat Noir",
        description: "Laboratoire radiophonique expérimental",
        genre: "Experimental",
        url: "http://localhost:8000",
      },
      {
        id: "mp3",
        enabled: true,
        format: "mp3",
        bitrateKbps: 192,
        stereo: true,
        host: "localhost",
        port: 8000,
        password: "",
        mount: "/stream.mp3",
        name: "Le Chat Noir (Web)",
        description: "Flux web MP3",
        genre: "Experimental",
        url: "http://localhost:8000",
      },
    ],
  };
  const DEFAULT_ROTATION_POLICY = {
    artistCooldownMinutes: 90,
    albumCooldownMinutes: 180,
    trackCooldownMinutes: 1440,
  };

  const DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
  const DAY_LABELS = {
    mon: "Lundi",
    tue: "Mardi",
    wed: "Mercredi",
    thu: "Jeudi",
    fri: "Vendredi",
    sat: "Samedi",
    sun: "Dimanche",
  };

  const refs = {
    saveFileButton: document.getElementById("saveFileButton"),
    exportJsonButton: document.getElementById("exportJsonButton"),
    exportJsonlButton: document.getElementById("exportJsonlButton"),
    currentGridButton: document.getElementById("currentGridButton"),
    blankGridButton: document.getElementById("blankGridButton"),
    importFileInput: document.getElementById("importFileInput"),
    createBlockModeButton: document.getElementById("createBlockModeButton"),
    createEventModeButton: document.getElementById("createEventModeButton"),
    showFilterSelect: document.getElementById("showFilterSelect"),
    statusBadge: document.getElementById("statusBadge"),
    cacheBadge: document.getElementById("cacheBadge"),
    diskPathLabel: document.getElementById("diskPathLabel"),
    plannerGrid: document.getElementById("plannerGrid"),
    slotEditorPanelBody: document.getElementById("slotEditorPanelBody"),
    profilePanelBody: document.getElementById("profilePanelBody"),
    tagSearchInput: document.getElementById("tagSearchInput"),
    tagRelatedOnlyInput: document.getElementById("tagRelatedOnlyInput"),
    tagLibraryPanelBody: document.getElementById("tagLibraryPanelBody"),
    tagTracksPanelBody: document.getElementById("tagTracksPanelBody"),
    dressingPanelBody: document.getElementById("dressingPanelBody"),
    runtimePanelBody: document.getElementById("runtimePanelBody"),
    previewJsonButton: document.getElementById("previewJsonButton"),
    previewJsonlButton: document.getElementById("previewJsonlButton"),
    exportPreview: document.getElementById("exportPreview"),
  };

  const store = {
    state: null,
    serverSnapshot: null,
    paths: null,
    selected: null,
    dirty: false,
    localSavedAt: "",
    previewFormat: "json",
    filterKey: "",
    creationMode: "block",
    tagSearch: "",
    tagRelatedOnly: false,
    selectedTagKey: "",
    collapsedPanels: {},
    interaction: null,
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function deepClone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function buildHelpBubble(label, text, alignLeft) {
    return (
      '<details class="help-bubble' + (alignLeft ? " align-left" : "") + '">' +
      '<summary aria-label="' + escapeHtml(label) + '">?</summary>' +
      '<div class="help-bubble-panel">' + text + "</div>" +
      "</details>"
    );
  }

  function normalizeTime(value, fallback) {
    const raw = String(value || "").trim();
    if (!/^\d{2}:\d{2}$/.test(raw)) {
      return fallback || "00:00";
    }
    const hours = Number(raw.slice(0, 2));
    const minutes = Number(raw.slice(3));
    if (hours === 24 && minutes === 0) {
      return "24:00";
    }
    if (!Number.isFinite(hours) || !Number.isFinite(minutes)) {
      return fallback || "00:00";
    }
    if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
      return fallback || "00:00";
    }
    return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
  }

  function timeToMinutes(value) {
    const normalized = normalizeTime(value, "00:00");
    const hours = Number(normalized.slice(0, 2));
    const minutes = Number(normalized.slice(3));
    return (hours * 60) + minutes;
  }

  function minutesToTime(totalMinutes) {
    const bounded = clamp(Math.round(totalMinutes), 0, 1440);
    if (bounded === 1440) {
      return "24:00";
    }
    const hours = Math.floor(bounded / 60);
    const minutes = bounded % 60;
    return String(hours).padStart(2, "0") + ":" + String(minutes).padStart(2, "0");
  }

  function timeToStep(value, fallback) {
    return clamp(Math.round(timeToMinutes(normalizeTime(value, fallback || "00:00")) / STEP_MINUTES), 0, DAY_STEPS);
  }

  function stepToTime(step) {
    return minutesToTime(clamp(step, 0, DAY_STEPS) * STEP_MINUTES);
  }

  function formatTimeRange(startStep, endStep) {
    return stepToTime(startStep) + " → " + stepToTime(endStep);
  }

  function generateSlotId(dayKey, mode) {
    return dayKey + "-" + mode + "-" + Date.now() + "-" + Math.floor(Math.random() * 100000);
  }

  function loadUiPrefs() {
    try {
      const parsed = JSON.parse(window.localStorage.getItem(UI_STORAGE_KEY) || "{}");
      const collapsed = parsed && parsed.collapsedPanels && typeof parsed.collapsedPanels === "object"
        ? parsed.collapsedPanels
        : {};
      store.collapsedPanels = Object.assign({}, DEFAULT_COLLAPSED_PANELS, collapsed);
    } catch (_error) {
      store.collapsedPanels = deepClone(DEFAULT_COLLAPSED_PANELS);
    }
  }

  function saveUiPrefs() {
    window.localStorage.setItem(
      UI_STORAGE_KEY,
      JSON.stringify({ collapsedPanels: store.collapsedPanels })
    );
  }

  function isPanelCollapsed(panelId) {
    return Boolean(store.collapsedPanels && store.collapsedPanels[panelId]);
  }

  function togglePanel(panelId) {
    store.collapsedPanels[panelId] = !isPanelCollapsed(panelId);
    saveUiPrefs();
    applyCollapsedPanels();
  }

  function applyCollapsedPanels() {
    document.querySelectorAll("[data-collapsible-panel]").forEach((panel) => {
      const panelId = panel.getAttribute("data-collapsible-panel");
      panel.classList.toggle("is-collapsed", isPanelCollapsed(panelId));
    });

    document.querySelectorAll("[data-collapsible-body]").forEach((body) => {
      const panelId = body.getAttribute("data-collapsible-body");
      body.hidden = isPanelCollapsed(panelId);
    });

    document.querySelectorAll("[data-panel-toggle]").forEach((button) => {
      const panelId = button.getAttribute("data-panel-toggle");
      const collapsed = isPanelCollapsed(panelId);
      const label = collapsed ? "Déplier cet encart" : "Replier cet encart";
      button.textContent = collapsed ? "+" : "-";
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
      button.setAttribute("aria-expanded", collapsed ? "false" : "true");
    });
  }

  function ensureStateShape(state) {
    if (!state || typeof state !== "object") {
      return state;
    }

    if (!state.settings || typeof state.settings !== "object") {
      state.settings = {};
    }
    if (!Array.isArray(state.settings.dressing)) {
      state.settings.dressing = [];
    }
    if (!state.catalog || typeof state.catalog !== "object") {
      state.catalog = {};
    }
    if (!Array.isArray(state.catalog.shows)) {
      state.catalog.shows = [];
    }
    if (!Array.isArray(state.catalog.sourceModes)) {
      state.catalog.sourceModes = [];
    }
    if (!Array.isArray(state.catalog.scheduleModes)) {
      state.catalog.scheduleModes = [];
    }
    if (!Array.isArray(state.catalog.playlists)) {
      state.catalog.playlists = [];
    }
    if (!Array.isArray(state.catalog.randomSources)) {
      state.catalog.randomSources = [];
    }
    if (!state.catalog.tagLibrary || typeof state.catalog.tagLibrary !== "object") {
      state.catalog.tagLibrary = { observedTags: [] };
    }
    if (!Array.isArray(state.catalog.tagLibrary.observedTags)) {
      state.catalog.tagLibrary.observedTags = [];
    }
    if (!Array.isArray(state.catalog.tagLibrary.trackRecords)) {
      state.catalog.tagLibrary.trackRecords = [];
    }
    if (!state.catalog.tagLibrary.tracksByTag || typeof state.catalog.tagLibrary.tracksByTag !== "object") {
      state.catalog.tagLibrary.tracksByTag = {};
    }
    if (!Array.isArray(state.catalog.showProfiles)) {
      state.catalog.showProfiles = [];
    }
    if (!state.week || typeof state.week !== "object") {
      state.week = {};
    }
    if (!state.runtime || typeof state.runtime !== "object") {
      state.runtime = deepClone(DEFAULT_RUNTIME);
    }
    if (!state.runtime.paths || typeof state.runtime.paths !== "object") {
      state.runtime.paths = {};
    }
    Object.keys(DEFAULT_RUNTIME.paths).forEach((key) => {
      state.runtime.paths[key] = String(state.runtime.paths[key] || DEFAULT_RUNTIME.paths[key]);
    });
    if (!state.runtime.liveInput || typeof state.runtime.liveInput !== "object") {
      state.runtime.liveInput = {};
    }
    state.runtime.liveInput.enabled = typeof state.runtime.liveInput.enabled === "boolean"
      ? state.runtime.liveInput.enabled
      : DEFAULT_RUNTIME.liveInput.enabled;
    state.runtime.liveInput.harborName = String(state.runtime.liveInput.harborName || DEFAULT_RUNTIME.liveInput.harborName);
    state.runtime.liveInput.port = Number(state.runtime.liveInput.port || DEFAULT_RUNTIME.liveInput.port);
    state.runtime.liveInput.password = String(state.runtime.liveInput.password || DEFAULT_RUNTIME.liveInput.password);
    state.runtime.liveInput.icy = typeof state.runtime.liveInput.icy === "boolean"
      ? state.runtime.liveInput.icy
      : DEFAULT_RUNTIME.liveInput.icy;

    const outputById = {};
    if (Array.isArray(state.runtime.outputs)) {
      state.runtime.outputs.forEach((item) => {
        if (item && item.id) {
          outputById[item.id] = item;
        }
      });
    }
    state.runtime.outputs = DEFAULT_RUNTIME.outputs.map((template) => {
      const output = Object.assign({}, template, outputById[template.id] || {});
      output.enabled = typeof output.enabled === "boolean" ? output.enabled : template.enabled;
      output.bitrateKbps = Number(output.bitrateKbps || template.bitrateKbps);
      output.port = Number(output.port || template.port);
      output.stereo = typeof output.stereo === "boolean" ? output.stereo : template.stereo;
      return output;
    });

    if (!state.rotationPolicy || typeof state.rotationPolicy !== "object") {
      state.rotationPolicy = deepClone(DEFAULT_ROTATION_POLICY);
    }
    state.rotationPolicy.artistCooldownMinutes = Number(
      state.rotationPolicy.artistCooldownMinutes || DEFAULT_ROTATION_POLICY.artistCooldownMinutes
    );
    state.rotationPolicy.albumCooldownMinutes = Number(
      state.rotationPolicy.albumCooldownMinutes || DEFAULT_ROTATION_POLICY.albumCooldownMinutes
    );
    state.rotationPolicy.trackCooldownMinutes = Number(
      state.rotationPolicy.trackCooldownMinutes || DEFAULT_ROTATION_POLICY.trackCooldownMinutes
    );

    DAY_ORDER.forEach((dayKey, index) => {
      if (!state.week[dayKey] || typeof state.week[dayKey] !== "object") {
        state.week[dayKey] = {
          index: index + 1,
          id: dayKey,
          label: DAY_LABELS[dayKey],
          blocks: [],
          events: [],
        };
      }

      const day = state.week[dayKey];
      day.id = day.id || dayKey;
      day.index = day.index || (index + 1);
      day.label = day.label || DAY_LABELS[dayKey];
      if (!Array.isArray(day.blocks)) {
        day.blocks = [];
      }
      if (!Array.isArray(day.events)) {
        day.events = [];
      }
    });

    state.settings.dressing = state.settings.dressing.map((item) => {
      const template = item && item.id === "reclames"
        ? { catchupMode: "until_next_trigger", priority: 40 }
        : { catchupMode: "until_next_trigger", priority: 30 };
      item.catchupMode = String(item.catchupMode || template.catchupMode);
      item.priority = Number(item.priority || template.priority);
      return item;
    });

    return state;
  }

  function getCatalogShows() {
    return store.state && store.state.catalog && Array.isArray(store.state.catalog.shows)
      ? store.state.catalog.shows.slice()
      : [];
  }

  function getShowById(showId) {
    return getCatalogShows().find((show) => show.id === showId) || null;
  }

  function getShowProfiles() {
    return store.state && store.state.catalog && Array.isArray(store.state.catalog.showProfiles)
      ? store.state.catalog.showProfiles
      : [];
  }

  function getShowProfile(showId) {
    return getShowProfiles().find((profile) => profile.showId === showId) || null;
  }

  function getTagLibrary() {
    return store.state && store.state.catalog && store.state.catalog.tagLibrary
      ? store.state.catalog.tagLibrary
      : { observedTags: [], trackRecords: [], tracksByTag: {}, trackCount: 0, rawTagCount: 0, normalizedTagCount: 0 };
  }

  function getFilteredTagItems() {
    const library = getTagLibrary();
    const search = String(store.tagSearch || "").trim().toLowerCase();
    const found = findSelectedSlotRef();
    const selectedShowId = found && found.slot ? found.slot.showId : "";

    let items = (library.observedTags || []).slice();
    if (search) {
      items = items.filter((item) => {
        const haystack = [
          item.normalizedTag,
          item.rawTag,
          item.primaryShowTitle,
          (item.secondaryShowTitles || []).join(" "),
          item.notes,
        ].join(" ").toLowerCase();
        return haystack.indexOf(search) !== -1;
      });
    }

    if (store.tagRelatedOnly && selectedShowId) {
      items = items.filter((item) => {
        return item.primaryShowId === selectedShowId || (item.secondaryShowIds || []).indexOf(selectedShowId) !== -1;
      });
    }

    return items;
  }

  function getRuntimeConfig() {
    return store.state && store.state.runtime
      ? store.state.runtime
      : deepClone(DEFAULT_RUNTIME);
  }

  function getRotationPolicy() {
    return store.state && store.state.rotationPolicy
      ? store.state.rotationPolicy
      : deepClone(DEFAULT_ROTATION_POLICY);
  }

  function getPlaylistOptions() {
    return store.state && store.state.catalog && Array.isArray(store.state.catalog.playlists)
      ? store.state.catalog.playlists
      : [];
  }

  function getRandomOptions() {
    return store.state && store.state.catalog && Array.isArray(store.state.catalog.randomSources)
      ? store.state.catalog.randomSources
      : [];
  }

  function getSourceModeOptions() {
    return store.state && store.state.catalog && Array.isArray(store.state.catalog.sourceModes)
      ? store.state.catalog.sourceModes
      : [];
  }

  function getScheduleModeOptions() {
    return store.state && store.state.catalog && Array.isArray(store.state.catalog.scheduleModes)
      ? store.state.catalog.scheduleModes
      : [];
  }

  function getStateDay(dayKey) {
    return store.state && store.state.week ? store.state.week[dayKey] : null;
  }

  function compareSlots(left, right) {
    return timeToMinutes(left.startTime || "00:00") - timeToMinutes(right.startTime || "00:00");
  }

  function sortDay(dayKey) {
    const day = getStateDay(dayKey);
    if (!day) return;
    day.blocks.sort(compareSlots);
    day.events.sort(compareSlots);
  }

  function getSlotExtent(slot) {
    const startStep = clamp(timeToStep(slot.startTime || "00:00"), 0, DAY_STEPS - 1);
    const rawEnd = slot.scheduleMode === "event"
      ? (slot.pendingUntil || slot.startTime || stepToTime(startStep + 1))
      : (slot.endTime || slot.startTime || stepToTime(startStep + 1));
    let endStep = clamp(timeToStep(rawEnd, stepToTime(startStep + 1)), 0, DAY_STEPS);
    if (endStep <= startStep) {
      endStep = Math.min(DAY_STEPS, startStep + 1);
    }
    return {
      startStep: startStep,
      endStep: endStep,
      span: Math.max(1, endStep - startStep),
    };
  }

  function getRenderedExtent(dayKey, mode, slot) {
    if (
      store.interaction &&
      store.interaction.slotId === slot.id &&
      store.interaction.dayKey === dayKey &&
      store.interaction.mode === mode &&
      typeof store.interaction.previewStartStep === "number" &&
      typeof store.interaction.previewEndStep === "number"
    ) {
      return {
        startStep: store.interaction.previewStartStep,
        endStep: store.interaction.previewEndStep,
        span: Math.max(1, store.interaction.previewEndStep - store.interaction.previewStartStep),
      };
    }
    return getSlotExtent(slot);
  }

  function applyExtentToSlot(slot, startStep, endStep) {
    const safeStart = clamp(Math.min(startStep, endStep - 1), 0, DAY_STEPS - 1);
    const safeEnd = clamp(Math.max(endStep, safeStart + 1), safeStart + 1, DAY_STEPS);
    slot.startTime = stepToTime(safeStart);
    if (slot.scheduleMode === "event") {
      slot.pendingUntil = stepToTime(safeEnd);
      slot.endTime = "";
    } else {
      slot.endTime = stepToTime(safeEnd);
      slot.pendingUntil = "";
    }
  }

  function buildDefaultSlot(mode, dayKey, startStep, endStep) {
    const start = typeof startStep === "number" ? startStep : 12 * 12;
    const end = typeof endStep === "number" ? endStep : start + 12;
    const playlist = getPlaylistOptions()[0];
    const randomSource = getRandomOptions()[0];

    if (mode === "event") {
      return {
        id: generateSlotId(dayKey, mode),
        showId: "",
        title: "Nouvelle émission",
        description: "",
        scheduleMode: "event",
        category: "editorial_event",
        color: "event",
        startTime: stepToTime(start),
        endTime: "",
        pendingUntil: stepToTime(Math.max(start + 1, end)),
        sourceMode: "random_directory",
        sourcePath: randomSource ? randomSource.path : "",
        notes: "",
      };
    }

    return {
      id: generateSlotId(dayKey, mode),
      showId: "",
      title: "Nouveau bloc",
      description: "",
      scheduleMode: "block",
      category: "music_block",
      color: "warm",
      startTime: stepToTime(start),
      endTime: stepToTime(Math.max(start + 1, end)),
      pendingUntil: "",
      sourceMode: "playlist_m3u",
      sourcePath: playlist ? playlist.path : "",
      notes: "",
    };
  }

  function buildBlankState(baseState) {
    const copy = ensureStateShape(deepClone(baseState));
    copy.savedAt = "";
    DAY_ORDER.forEach((dayKey) => {
      copy.week[dayKey].blocks = [];
      copy.week[dayKey].events = [];
    });
    return copy;
  }

  function findSlotRef(dayKey, mode, slotId) {
    if (!store.state || !store.state.week || !slotId) return null;
    const day = getStateDay(dayKey);
    if (!day) return null;
    const list = mode === "event" ? day.events : day.blocks;
    const index = list.findIndex((slot) => slot.id === slotId);
    if (index === -1) return null;
    return {
      dayKey: dayKey,
      mode: mode,
      index: index,
      list: list,
      slot: list[index],
    };
  }

  function findSelectedSlotRef() {
    if (!store.selected) return null;
    return findSlotRef(store.selected.dayKey, store.selected.mode, store.selected.slotId);
  }

  function selectSlot(dayKey, mode, slotId) {
    store.selected = { dayKey: dayKey, mode: mode, slotId: slotId };
    renderAll();
  }

  function moveSelectedSlot(targetDayKey, targetMode) {
    const found = findSelectedSlotRef();
    if (!found) return null;

    const clone = deepClone(found.slot);
    const extent = getSlotExtent(found.slot);
    found.list.splice(found.index, 1);

    clone.scheduleMode = targetMode;
    clone.startTime = stepToTime(extent.startStep);
    if (targetMode === "event") {
      clone.endTime = "";
      clone.pendingUntil = stepToTime(extent.endStep);
    } else {
      clone.pendingUntil = "";
      clone.endTime = stepToTime(extent.endStep);
    }

    const targetDay = getStateDay(targetDayKey);
    if (!targetDay) return null;
    if (targetMode === "event") {
      targetDay.events.push(clone);
    } else {
      targetDay.blocks.push(clone);
    }

    sortDay(targetDayKey);
    store.selected = { dayKey: targetDayKey, mode: targetMode, slotId: clone.id };
    return findSelectedSlotRef();
  }

  function applyShowPreset(showId) {
    let found = findSelectedSlotRef();
    const show = getShowById(showId);
    if (!found || !show) return;

    if (show.defaultScheduleMode && show.defaultScheduleMode !== found.mode) {
      found = moveSelectedSlot(found.dayKey, show.defaultScheduleMode);
    }
    if (!found) return;

    found.slot.showId = show.id;
    found.slot.title = show.title;
    found.slot.description = show.description || "";
    found.slot.category = show.category || found.slot.category;
    found.slot.color = show.color || found.slot.color;
    found.slot.sourceMode = show.defaultSourceMode || found.slot.sourceMode;
    found.slot.sourcePath = show.defaultSourcePath || found.slot.sourcePath;

    sortDay(found.dayKey);
    markDirty("Émission appliquée.");
  }

  function removeSelectedSlot() {
    const found = findSelectedSlotRef();
    if (!found) return;
    found.list.splice(found.index, 1);
    store.selected = null;
    markDirty("Créneau supprimé.");
  }

  function duplicateSelectedSlot() {
    const found = findSelectedSlotRef();
    if (!found) return;
    const clone = deepClone(found.slot);
    clone.id = generateSlotId(found.dayKey, found.mode);
    if (found.mode === "event") {
      getStateDay(found.dayKey).events.push(clone);
    } else {
      getStateDay(found.dayKey).blocks.push(clone);
    }
    sortDay(found.dayKey);
    store.selected = { dayKey: found.dayKey, mode: found.mode, slotId: clone.id };
    markDirty("Créneau dupliqué.");
  }

  function updateSelectedSlotField(fieldName, value) {
    let found = findSelectedSlotRef();
    if (!found) return;

    if (fieldName === "dayKey") {
      moveSelectedSlot(String(value || "mon"), found.mode);
      markDirty("Jour mis à jour.");
      return;
    }

    if (fieldName === "scheduleMode") {
      moveSelectedSlot(found.dayKey, value === "event" ? "event" : "block");
      markDirty("Type de créneau mis à jour.");
      return;
    }

    if (fieldName === "showId") {
      if (!value) {
        found.slot.showId = "";
        found.slot.title = found.mode === "event" ? "Nouvelle émission" : "Nouveau bloc";
        found.slot.description = "";
        markDirty("Association d’émission retirée.");
        return;
      }
      applyShowPreset(String(value));
      return;
    }

    if (fieldName === "sourceMode") {
      found.slot.sourceMode = value;
      const options = value === "playlist_m3u" ? getPlaylistOptions() : getRandomOptions();
      if (options.length) {
        found.slot.sourcePath = options[0].path;
      }
      markDirty("Mode source mis à jour.");
      return;
    }

    if (fieldName === "startTime" || fieldName === "endTime" || fieldName === "pendingUntil") {
      const currentExtent = getSlotExtent(found.slot);
      let startStep = currentExtent.startStep;
      let endStep = currentExtent.endStep;

      if (fieldName === "startTime") {
        startStep = timeToStep(normalizeTime(value, found.slot.startTime || "00:00"));
      } else {
        endStep = timeToStep(
          normalizeTime(value, found.slot.scheduleMode === "event" ? found.slot.pendingUntil : found.slot.endTime)
        );
      }

      if (endStep <= startStep) {
        endStep = Math.min(DAY_STEPS, startStep + 1);
      }

      applyExtentToSlot(found.slot, startStep, endStep);
      sortDay(found.dayKey);
      markDirty("Horaires mis à jour.");
      return;
    }

    found.slot[fieldName] = value;
    sortDay(found.dayKey);
    markDirty("Créneau modifié.");
  }

  function updateDressingField(dressingId, fieldName, value, isChecked) {
    if (!store.state || !store.state.settings || !Array.isArray(store.state.settings.dressing)) {
      return;
    }
    const item = store.state.settings.dressing.find((entry) => entry.id === dressingId);
    if (!item) return;

    if (fieldName === "enabled") {
      item.enabled = Boolean(isChecked);
    } else if (fieldName === "intervalMinutes" || fieldName === "offsetMinutes") {
      item[fieldName] = String(value == null ? "" : value);
    } else {
      item[fieldName] = value;
    }

    markDirty("Habillage mis à jour.");
  }

  function updateRuntimePath(fieldName, value) {
    const runtime = getRuntimeConfig();
    if (!runtime.paths) {
      runtime.paths = {};
    }
    runtime.paths[fieldName] = String(value == null ? "" : value);
    markDirty("Chemins runtime mis à jour.");
  }

  function updateLiveField(fieldName, value, isChecked) {
    const runtime = getRuntimeConfig();
    if (!runtime.liveInput) {
      runtime.liveInput = deepClone(DEFAULT_RUNTIME.liveInput);
    }
    if (fieldName === "enabled" || fieldName === "icy") {
      runtime.liveInput[fieldName] = Boolean(isChecked);
    } else if (fieldName === "port") {
      runtime.liveInput[fieldName] = Number.parseInt(String(value || "").trim(), 10) || DEFAULT_RUNTIME.liveInput.port;
    } else {
      runtime.liveInput[fieldName] = String(value == null ? "" : value);
    }
    markDirty("Entrée live mise à jour.");
  }

  function updateOutputField(outputId, fieldName, value, isChecked) {
    const runtime = getRuntimeConfig();
    const output = (runtime.outputs || []).find((item) => item.id === outputId);
    if (!output) return;

    if (fieldName === "enabled" || fieldName === "stereo") {
      output[fieldName] = Boolean(isChecked);
    } else if (fieldName === "bitrateKbps" || fieldName === "port") {
      output[fieldName] = Number.parseInt(String(value || "").trim(), 10) || 0;
    } else {
      output[fieldName] = String(value == null ? "" : value);
    }

    markDirty("Sortie Icecast mise à jour.");
  }

  function updateRotationField(fieldName, value) {
    const rotationPolicy = getRotationPolicy();
    const fallback = DEFAULT_ROTATION_POLICY[fieldName] || 0;
    rotationPolicy[fieldName] = Number.parseInt(String(value || "").trim(), 10) || fallback;
    markDirty("Politique de rotation mise à jour.");
  }

  function slotFilterKey(slot) {
    if (slot.showId) {
      return "show:" + slot.showId;
    }
    return "title:" + String(slot.title || "").trim().toLowerCase();
  }

  function slotMatchesFilter(slot) {
    return !store.filterKey || slotFilterKey(slot) === store.filterKey;
  }

  function getAllSlots() {
    if (!store.state || !store.state.week) return [];
    const items = [];
    DAY_ORDER.forEach((dayKey) => {
      const day = getStateDay(dayKey);
      if (!day) return;
      day.blocks.forEach((slot) => items.push({ dayKey: dayKey, mode: "block", slot: slot }));
      day.events.forEach((slot) => items.push({ dayKey: dayKey, mode: "event", slot: slot }));
    });
    return items;
  }

  function getFilterEntries() {
    const counts = {};
    getAllSlots().forEach((entry) => {
      const key = slotFilterKey(entry.slot);
      if (!counts[key]) {
        counts[key] = {
          key: key,
          label: entry.slot.title || "Sans titre",
          count: 0,
        };
      }
      counts[key].count += 1;
    });
    return Object.keys(counts)
      .map((key) => counts[key])
      .sort((left, right) => left.label.localeCompare(right.label, "fr"));
  }

  function updateStatus(text, kind) {
    refs.statusBadge.textContent = text;
    refs.statusBadge.classList.remove("is-warning", "is-success");
    if (kind === "warning") refs.statusBadge.classList.add("is-warning");
    if (kind === "success") refs.statusBadge.classList.add("is-success");
  }

  function updateCacheBadge() {
    if (!store.localSavedAt) {
      refs.cacheBadge.textContent = "Cache navigateur actif";
      return;
    }
    refs.cacheBadge.textContent =
      "Brouillon local " + (store.dirty ? "non sauvegardé" : "aligné") + " · " + store.localSavedAt;
  }

  function writeLocalDraft() {
    if (!store.state) return;
    store.localSavedAt = new Date().toLocaleString("fr-FR");
    window.localStorage.setItem(
      LOCAL_STORAGE_KEY,
      JSON.stringify({
        localSavedAt: store.localSavedAt,
        dirty: store.dirty,
        state: store.state,
      })
    );
  }

  function markDirty(message) {
    store.dirty = true;
    writeLocalDraft();
    updateStatus(message || "Brouillon mis à jour dans le navigateur.", "warning");
    renderAll();
  }

  function buildExportJson() {
    return JSON.stringify(store.state, null, 2);
  }

  function buildExportJsonl() {
    if (!store.state) return "";
    const lines = [];

    (store.state.catalog && store.state.catalog.shows || []).forEach((show) => {
      lines.push(JSON.stringify(Object.assign({ recordType: "show" }, show)));
    });

    (store.state.catalog && store.state.catalog.showProfiles || []).forEach((profile) => {
      lines.push(JSON.stringify(Object.assign({ recordType: "show_profile" }, profile)));
    });

    (store.state.catalog && store.state.catalog.tagLibrary && store.state.catalog.tagLibrary.observedTags || []).forEach((tag) => {
      lines.push(JSON.stringify(Object.assign({ recordType: "tag" }, tag)));
    });

    (store.state.catalog && store.state.catalog.tagLibrary && store.state.catalog.tagLibrary.trackRecords || []).forEach((track) => {
      lines.push(JSON.stringify(Object.assign({ recordType: "track" }, track)));
    });

    (store.state.settings && store.state.settings.dressing || []).forEach((item) => {
      lines.push(JSON.stringify(Object.assign({ recordType: "dressing" }, item)));
    });

    if (store.state.runtime && store.state.runtime.paths) {
      lines.push(JSON.stringify(Object.assign({ recordType: "runtime_paths" }, store.state.runtime.paths)));
    }

    if (store.state.runtime && store.state.runtime.liveInput) {
      lines.push(JSON.stringify(Object.assign({ recordType: "runtime_live_input" }, store.state.runtime.liveInput)));
    }

    (store.state.runtime && store.state.runtime.outputs || []).forEach((output) => {
      lines.push(JSON.stringify(Object.assign({ recordType: "runtime_output" }, output)));
    });

    if (store.state.rotationPolicy) {
      lines.push(JSON.stringify(Object.assign({ recordType: "rotation_policy" }, store.state.rotationPolicy)));
    }

    DAY_ORDER.forEach((dayKey) => {
      const day = getStateDay(dayKey);
      ["blocks", "events"].forEach((bucketName) => {
        (day && day[bucketName] || []).forEach((slot) => {
          lines.push(JSON.stringify(Object.assign(
            { recordType: "slot", day: dayKey, dayLabel: day.label || DAY_LABELS[dayKey] },
            slot
          )));
        });
      });
    });

    return lines.join("\n") + "\n";
  }

  function downloadText(filename, mimeType, content) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function saveToServer() {
    if (!store.state) return;
    updateStatus("Sauvegarde sur disque en cours…");
    const response = await fetch("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: store.state }),
    });
    const payload = await response.json();
    if (!payload.ok) {
      throw new Error(payload.message || "Sauvegarde impossible.");
    }

    store.state = ensureStateShape(payload.state);
    store.serverSnapshot = deepClone(store.state);
    store.paths = payload.paths || null;
    store.dirty = false;
    writeLocalDraft();
    updateStatus(payload.message || "Sauvegarde terminée.", "success");
    renderAll();
  }

  function loadCurrentGridPreset() {
    if (!store.serverSnapshot) return;
    if (store.dirty && !window.confirm("Recharger la grille actuelle et abandonner les modifications locales non sauvegardées ?")) {
      return;
    }
    store.state = ensureStateShape(deepClone(store.serverSnapshot));
    store.selected = null;
    store.selectedTagKey = "";
    store.dirty = false;
    writeLocalDraft();
    updateStatus("Grille actuelle rechargée.", "success");
    renderAll();
  }

  function loadBlankGridPreset() {
    if (!store.serverSnapshot) return;
    if (store.dirty && !window.confirm("Créer une grille vierge et abandonner les modifications locales non sauvegardées ?")) {
      return;
    }
    store.state = buildBlankState(store.serverSnapshot);
    store.selected = null;
    store.selectedTagKey = "";
    markDirty("Grille vierge chargée dans le navigateur.");
  }

  function setStateFromPayload(payload) {
    store.state = ensureStateShape(payload.state);
    store.serverSnapshot = deepClone(store.state);
    store.paths = payload.paths || null;
    store.selected = null;
    store.tagSearch = "";
    store.tagRelatedOnly = false;
    store.selectedTagKey = "";
    refs.tagSearchInput.value = "";
    refs.tagRelatedOnlyInput.checked = false;

    try {
      const cached = JSON.parse(window.localStorage.getItem(LOCAL_STORAGE_KEY) || "null");
      const sameDocumentation =
        cached &&
        cached.state &&
        cached.state.documentationFingerprint &&
        store.state.documentationFingerprint &&
        cached.state.documentationFingerprint === store.state.documentationFingerprint;
      if (cached && cached.state && cached.state.version === store.state.version && sameDocumentation) {
        store.state = ensureStateShape(cached.state);
        store.dirty = Boolean(cached.dirty);
        store.localSavedAt = String(cached.localSavedAt || "");
        updateStatus(
          "Brouillon local restauré depuis le navigateur.",
          store.dirty ? "warning" : "success"
        );
      } else {
        store.dirty = false;
        store.localSavedAt = "";
      }
    } catch (_error) {
      store.dirty = false;
      store.localSavedAt = "";
    }

    renderAll();
  }

  function renderToolbar() {
    refs.createBlockModeButton.classList.toggle("is-active", store.creationMode === "block");
    refs.createEventModeButton.classList.toggle("is-active", store.creationMode === "event");

    const entries = getFilterEntries();
    if (store.filterKey && !entries.some((entry) => entry.key === store.filterKey)) {
      store.filterKey = "";
    }
    refs.showFilterSelect.innerHTML = [
      '<option value="">Toutes les émissions</option>',
      ...entries.map((entry) => (
        '<option value="' + escapeHtml(entry.key) + '">' +
          escapeHtml(entry.label) +
          " · " +
          escapeHtml(String(entry.count)) +
        "</option>"
      )),
    ].join("");
    refs.showFilterSelect.value = store.filterKey;

    refs.diskPathLabel.textContent = store.paths && store.paths.json
      ? store.paths.json
      : "Chemin de sauvegarde en attente…";

    updateCacheBadge();
  }

  function buildSelectionPreview(dayKey) {
    if (!store.interaction || store.interaction.type !== "create" || store.interaction.dayKey !== dayKey) {
      return "";
    }
    const startStep = Math.min(store.interaction.anchorStep, store.interaction.currentStep);
    const endStep = Math.max(store.interaction.anchorStep, store.interaction.currentStep) + 1;
    const top = startStep * STEP_HEIGHT;
    const height = Math.max((endStep - startStep) * STEP_HEIGHT, MIN_CARD_HEIGHT);
    return '<div class="selection-preview" style="top:' + top + "px;height:" + height + 'px"></div>';
  }

  function renderSlotCard(dayKey, mode, slot) {
    const extent = getRenderedExtent(dayKey, mode, slot);
    const top = extent.startStep * STEP_HEIGHT;
    const actualHeight = extent.span * STEP_HEIGHT;
    const height = Math.min(Math.max(actualHeight, MIN_CARD_HEIGHT), (DAY_STEPS * STEP_HEIGHT) - top);
    const selected = store.selected &&
      store.selected.dayKey === dayKey &&
      store.selected.mode === mode &&
      store.selected.slotId === slot.id;
    const muted = !slotMatchesFilter(slot);

    const classes = [
      "slot-card",
      "slot--" + escapeHtml(slot.color || "warm"),
      selected ? "is-selected" : "",
      muted ? "is-muted" : "",
      height <= 22 ? "is-mini" : "",
      height <= 36 ? "is-compact" : "",
      height <= 52 ? "is-tight" : "",
    ].filter(Boolean).join(" ");

    const modeLabel = mode === "event" ? "Émission" : "Bloc";
    const sourceLabel = slot.sourceMode === "random_directory" ? "Mode random" : "Playlist .m3u";
    const zIndex = selected ? 50 : (mode === "event" ? 30 : 20);

    return (
      '<button class="' + classes + '"' +
        ' type="button"' +
        ' data-slot-id="' + escapeHtml(slot.id) + '"' +
        ' data-day-key="' + escapeHtml(dayKey) + '"' +
        ' data-mode="' + escapeHtml(mode) + '"' +
        ' style="top:' + top + "px;height:" + height + "px;z-index:" + zIndex + ';">' +
        '<span class="slot-handle" data-edge="start"></span>' +
        '<div class="slot-content">' +
          '<div class="slot-meta">' + escapeHtml(formatTimeRange(extent.startStep, extent.endStep)) + " · " + escapeHtml(modeLabel) + "</div>" +
          '<h3 class="slot-title">' + escapeHtml(slot.title || "Sans titre") + "</h3>" +
          '<div class="slot-body">' + escapeHtml(slot.description || "Aucune description") + "</div>" +
          '<div class="slot-source">' + escapeHtml(sourceLabel) + "</div>" +
        "</div>" +
        '<span class="slot-handle" data-edge="end"></span>' +
      "</button>"
    );
  }

  function renderPlanner() {
    if (!store.state) {
      refs.plannerGrid.innerHTML = '<div class="empty-state"><h3>Chargement…</h3><p>La grille arrive.</p></div>';
      return;
    }

    const previousScroller = refs.plannerGrid.querySelector(".planner-scroller");
    const previousTop = previousScroller ? previousScroller.scrollTop : 0;
    const previousLeft = previousScroller ? previousScroller.scrollLeft : 0;
    const trackHeight = DAY_STEPS * STEP_HEIGHT;
    const timeLabels = [];

    for (let hour = 0; hour <= 24; hour += 1) {
      const position = hour * 12 * STEP_HEIGHT;
      timeLabels.push(
        '<div class="time-label' + (hour === 24 ? " is-end" : "") + '" style="top:' + position + 'px">' +
        escapeHtml(String(hour).padStart(2, "0") + ":00") +
        "</div>"
      );
    }

    const dayHeaders = DAY_ORDER.map((dayKey) => {
      const day = getStateDay(dayKey);
      const slotCount = (day.blocks || []).length + (day.events || []).length;
      return (
        '<div class="planner-day-head">' +
          '<p class="day-title">' + escapeHtml(day.label || DAY_LABELS[dayKey]) + "</p>" +
          '<p class="day-subtitle">' + escapeHtml(String(slotCount)) + " créneau" + (slotCount > 1 ? "x" : "") + "</p>" +
        "</div>"
      );
    }).join("");

    const dayColumns = DAY_ORDER.map((dayKey) => {
      const day = getStateDay(dayKey);
      const slots = []
        .concat((day.blocks || []).map((slot) => ({ mode: "block", slot: slot })))
        .concat((day.events || []).map((slot) => ({ mode: "event", slot: slot })))
        .sort((left, right) => compareSlots(left.slot, right.slot));

      return (
        '<div class="planner-day-body">' +
          '<div class="day-track" data-day-track="' + escapeHtml(dayKey) + '">' +
            buildSelectionPreview(dayKey) +
            slots.map((entry) => renderSlotCard(dayKey, entry.mode, entry.slot)).join("") +
          "</div>" +
        "</div>"
      );
    }).join("");

    refs.plannerGrid.innerHTML =
      '<div class="planner-scroller">' +
        '<div class="planner-canvas" style="--step-height:' + STEP_HEIGHT + "px;--track-height:" + trackHeight + 'px">' +
          '<div class="planner-corner"><p class="day-title">Heure</p><p class="axis-caption">24 h visibles</p></div>' +
          dayHeaders +
          '<div class="planner-time-column"><div class="time-track">' + timeLabels.join("") + "</div></div>" +
          dayColumns +
        "</div>" +
      "</div>";

    const scroller = refs.plannerGrid.querySelector(".planner-scroller");
    if (scroller) {
      scroller.scrollTop = previousTop;
      const maxScrollLeft = Math.max(scroller.scrollWidth - scroller.clientWidth, 0);
      scroller.scrollLeft = previousLeft > maxScrollLeft ? 0 : previousLeft;
    }
  }

  function buildShowOptions(selectedShowId) {
    const groups = [];
    const groupsByLabel = {};

    getCatalogShows().forEach((show) => {
      const label = show.groupLabel || "Bibliothèque";
      if (!groupsByLabel[label]) {
        groupsByLabel[label] = [];
        groups.push(label);
      }
      groupsByLabel[label].push(show);
    });

    return [
      '<option value="">Aucune émission prédéfinie</option>',
      ...groups.map((label) => (
        '<optgroup label="' + escapeHtml(label) + '">' +
          groupsByLabel[label]
            .sort((left, right) => String(left.title || "").localeCompare(String(right.title || ""), "fr"))
            .map((show) => (
              '<option value="' + escapeHtml(show.id) + '"' +
                (selectedShowId === show.id ? " selected" : "") +
              ">" + escapeHtml(show.title) + "</option>"
            ))
            .join("") +
        "</optgroup>"
      )),
    ].join("");
  }

  function buildSourcePresetOptions(slot) {
    const options = slot.sourceMode === "playlist_m3u" ? getPlaylistOptions() : getRandomOptions();
    const hasCurrent = options.some((item) => item.path === slot.sourcePath);
    const extraOption = slot.sourcePath && !hasCurrent
      ? '<option value="' + escapeHtml(slot.sourcePath) + '" selected>Chemin personnalisé</option>'
      : "";

    return [
      extraOption,
      ...options.map((item) => (
        '<option value="' + escapeHtml(item.path) + '"' +
          (slot.sourcePath === item.path ? " selected" : "") +
        ">" + escapeHtml(item.label || item.filename || item.path) + "</option>"
      )),
    ].join("");
  }

  function renderSlotEditor() {
    const found = findSelectedSlotRef();
    if (!found) {
      refs.slotEditorPanelBody.innerHTML =
        '<div class="empty-state">' +
          "<h3>Aucun créneau sélectionné</h3>" +
          "<p>Clique sur un créneau existant ou crée-en un dans la grille pour commencer son édition.</p>" +
        "</div>";
      return;
    }

    const slot = found.slot;
    const sourceModes = getSourceModeOptions();
    const scheduleModes = getScheduleModeOptions();
    const extent = getRenderedExtent(found.dayKey, found.mode, slot);
    const scheduleOptionsHtml = scheduleModes.map((item) => (
      `<option value="${escapeHtml(item.id)}"${slot.scheduleMode === item.id ? " selected" : ""}>${escapeHtml(item.label)}</option>`
    )).join("");
    const dayOptionsHtml = DAY_ORDER.map((dayKey) => (
      `<option value="${escapeHtml(dayKey)}"${found.dayKey === dayKey ? " selected" : ""}>${escapeHtml(DAY_LABELS[dayKey])}</option>`
    )).join("");
    const sourceModeOptionsHtml = sourceModes.map((item) => (
      `<option value="${escapeHtml(item.id)}"${slot.sourceMode === item.id ? " selected" : ""}>${escapeHtml(item.label)}</option>`
    )).join("");

    refs.slotEditorPanelBody.innerHTML = `
      <div class="stack-gap">
        <div class="info-card">
          <strong>Créneau actif</strong>
          <span>${escapeHtml((getStateDay(found.dayKey).label || DAY_LABELS[found.dayKey]) + " · " + formatTimeRange(extent.startStep, extent.endStep))}</span>
          <p>${escapeHtml(slot.scheduleMode === "event" ? "Émission ponctuelle superposable." : "Bloc continu éditable à la souris.")}</p>
        </div>

        <label class="field">
          <span class="field-label-row">
            <span>Émission</span>
            ${buildHelpBubble("Aide sur l’émission", "Choisis une émission de la bibliothèque pour récupérer son titre, sa description, son mode source et son rattachement documentaire.", false)}
          </span>
          <select class="select-input" data-slot-field="showId">
            ${buildShowOptions(slot.showId || "")}
          </select>
        </label>

        <div class="split-fields">
          <label class="field">
            <span class="field-label-row">
              <span>Nature</span>
              ${buildHelpBubble("Aide sur la nature du créneau", "Un bloc continu occupe une plage fixe. Une émission ponctuelle peut venir se superposer à un bloc musical.", false)}
            </span>
            <select class="select-input" data-slot-field="scheduleMode">
              ${scheduleOptionsHtml}
            </select>
          </label>
          <label class="field">
            <span class="field-label-row"><span>Jour</span></span>
            <select class="select-input" data-slot-field="dayKey">
              ${dayOptionsHtml}
            </select>
          </label>
        </div>

        <div class="split-fields">
          <label class="field">
            <span class="field-label-row">
              <span>Début</span>
              ${buildHelpBubble("Aide sur l’horaire de début", "Utilise le format HH:MM. Le concepteur travaille par pas de 5 minutes pour rester fidèle aux créneaux courts.", false)}
            </span>
            <input class="text-input" data-slot-field="startTime" type="text" value="${escapeHtml(slot.startTime || "")}" />
          </label>
          <label class="field">
            <span class="field-label-row"><span>${escapeHtml(slot.scheduleMode === "event" ? "Jusqu’à" : "Fin")}</span></span>
            <input class="text-input" data-slot-field="${escapeHtml(slot.scheduleMode === "event" ? "pendingUntil" : "endTime")}" type="text" value="${escapeHtml(slot.scheduleMode === "event" ? slot.pendingUntil : slot.endTime)}" />
          </label>
        </div>

        <label class="field">
          <span class="field-label-row"><span>Titre affiché</span></span>
          <input class="text-input" data-slot-field="title" type="text" value="${escapeHtml(slot.title || "")}" />
        </label>

        <label class="field">
          <span class="field-label-row"><span>Description</span></span>
          <textarea class="textarea-input" data-slot-field="description" rows="4">${escapeHtml(slot.description || "")}</textarea>
        </label>

        <div class="split-fields">
          <label class="field">
            <span class="field-label-row">
              <span>Mode source</span>
              ${buildHelpBubble("Aide sur le mode source", "Choisis entre une playlist .m3u et un dossier parcouru en mode random. Le preset associé à l’émission peut remplir ces champs automatiquement.", false)}
            </span>
            <select class="select-input" data-slot-field="sourceMode">
              ${sourceModeOptionsHtml}
            </select>
          </label>
          <label class="field">
            <span class="field-label-row"><span>Bibliothèque / preset</span></span>
            <select class="select-input" data-slot-field="sourcePath">
              ${buildSourcePresetOptions(slot)}
            </select>
          </label>
        </div>

        <label class="field">
          <span class="field-label-row"><span>Chemin source</span></span>
          <input class="text-input" data-slot-field="sourcePath" type="text" value="${escapeHtml(slot.sourcePath || "")}" />
        </label>

        <label class="field">
          <span class="field-label-row"><span>Notes</span></span>
          <textarea class="textarea-input" data-slot-field="notes" rows="4">${escapeHtml(slot.notes || "")}</textarea>
        </label>

        <div class="editor-actions">
          <button class="button button-quiet" type="button" data-slot-action="duplicate">Dupliquer</button>
          <button class="button button-danger" type="button" data-slot-action="delete">Supprimer</button>
        </div>
      </div>`;
  }

  function renderTagChips(tags, secondary) {
    if (!tags || !tags.length) {
      return '<div class="empty-state"><p>Aucun tag documenté pour cette émission.</p></div>';
    }
    return '<div class="tag-chip-list">' + tags.map((item) => (
      '<span class="tag-chip' + (secondary ? " secondary" : "") + '">' +
        escapeHtml(item.tag) +
        '<small>' + escapeHtml(String(item.occurrences || 0)) + "</small>" +
      "</span>"
    )).join("") + "</div>";
  }

  function formatMinutes(value) {
    const numeric = Number(value || 0);
    if (!numeric) return "0 min";
    if (numeric % 60 === 0) {
      return String(numeric / 60) + " h";
    }
    return String(numeric) + " min";
  }

  function renderGeneratorFacts(profile) {
    const config = profile.generatorConfig || {};
    const facts = [];

    if (config.poolName) {
      facts.push("Pool · " + config.poolName);
    }
    if (config.directoryPath) {
      facts.push("Dossier · " + config.directoryPath);
    }
    if (config.libraryRoot) {
      facts.push("Bibliothèque · " + config.libraryRoot);
    }
    if (config.durationMinSeconds || config.durationMaxSeconds) {
      const minLabel = config.durationMinSeconds ? formatMinutes(Math.round(config.durationMinSeconds / 60)) : "0 min";
      const maxLabel = config.durationMaxSeconds ? formatMinutes(Math.round(config.durationMaxSeconds / 60)) : "ou plus";
      facts.push("Durée · " + minLabel + " → " + maxLabel);
    }
    if (Array.isArray(config.artistIncludes) && config.artistIncludes.length) {
      facts.push("Artistes · " + config.artistIncludes.join(", "));
    }
    if (config.usesProfileTags) {
      facts.push("Tags documentaires actifs");
    }
    if (Array.isArray(config.extraDirectories) && config.extraDirectories.length) {
      facts.push("Dossiers additionnels · " + config.extraDirectories.join(", "));
    }

    if (!facts.length) {
      return '<div class="empty-state"><p>Aucune règle technique supplémentaire documentée.</p></div>';
    }

    return '<div class="tag-chip-list">' + facts.map((fact) => (
      '<span class="tag-chip secondary">' + escapeHtml(fact) + "</span>"
    )).join("") + "</div>";
  }

  function renderShowProfile() {
    const found = findSelectedSlotRef();
    if (!found || !found.slot.showId) {
      refs.profilePanelBody.innerHTML =
        '<div class="empty-state">' +
          "<h3>Pas encore de profil</h3>" +
          "<p>Associe une émission au créneau pour afficher sa définition et sa cartographie de tags.</p>" +
        "</div>";
      return;
    }

    const profile = getShowProfile(found.slot.showId);
    if (!profile) {
      refs.profilePanelBody.innerHTML =
        '<div class="empty-state">' +
          "<h3>Profil manquant</h3>" +
          "<p>Cette émission n’a pas encore de profil documentaire associé.</p>" +
        "</div>";
      return;
    }

    refs.profilePanelBody.innerHTML =
      '<div class="stack-gap">' +
        '<div class="info-card">' +
          "<strong>Logique éditoriale</strong>" +
          "<span>" + escapeHtml(profile.definitionLabel || "Non défini") + "</span>" +
          "<p>" + escapeHtml(profile.definitionSummary || "Aucun résumé.") + "</p>" +
        "</div>" +
        '<div class="info-card">' +
          "<strong>Stratégie de génération</strong>" +
          "<span>" + escapeHtml(profile.generatorLabel || "Non définie") + "</span>" +
          "<p>" + escapeHtml(profile.generatorSummary || "Aucun résumé technique.") + "</p>" +
        "</div>" +
        '<div><div class="field-label-row"><span>Règles machine</span></div>' + renderGeneratorFacts(profile) + "</div>" +
        '<div class="stack-gap">' +
          '<div><div class="field-label-row"><span>Tags principaux</span></div>' + renderTagChips(profile.primaryTags || [], false) + "</div>" +
          '<div><div class="field-label-row"><span>Tags secondaires</span></div>' + renderTagChips(profile.secondaryTags || [], true) + "</div>" +
        "</div>" +
      "</div>";
  }

  function renderTagLibrary() {
    const library = getTagLibrary();
    const items = getFilteredTagItems();

    if (store.selectedTagKey && !items.some((item) => (item.normalizedTag || item.rawTag || "") === store.selectedTagKey)) {
      store.selectedTagKey = "";
    }

    refs.tagLibraryPanelBody.innerHTML =
      '<p class="tag-library-meta">' +
        escapeHtml(String(items.length)) + " tag(s) affiché(s) · " +
        escapeHtml(String(library.trackCount || 0)) + " morceaux documentés" +
      "</p>" +
      (
        items.length
          ? '<div class="tag-library-list">' + items.map((item) => {
            const tagKey = item.normalizedTag || item.rawTag || "";
            const isActive = store.selectedTagKey === tagKey;
            return (
              '<button class="tag-library-item tag-library-button' + (isActive ? " is-active" : "") + '" type="button" data-tag-key="' + escapeHtml(tagKey) + '">' +
                "<h3>" + escapeHtml(item.normalizedTag || item.rawTag || "Tag") + "</h3>" +
                '<div class="tag-meta-row">' +
                  '<span class="tag-meta-pill">Occurrences · ' + escapeHtml(String(item.occurrences || 0)) + "</span>" +
                  (item.rawTag && item.rawTag !== item.normalizedTag
                    ? '<span class="tag-meta-pill">Tag brut · ' + escapeHtml(item.rawTag) + "</span>"
                    : "") +
                  (item.primaryShowTitle
                    ? '<span class="tag-meta-pill">Principal · ' + escapeHtml(item.primaryShowTitle) + "</span>"
                    : "") +
                "</div>" +
                ((item.secondaryShowTitles || []).length
                  ? "<p>Secondaires · " + escapeHtml(item.secondaryShowTitles.join(", ")) + "</p>"
                  : "") +
                (item.notes ? "<p>" + escapeHtml(item.notes) + "</p>" : "") +
              "</button>"
            );
          }).join("") + "</div>"
          : '<div class="empty-state"><h3>Aucun tag</h3><p>Essaie un autre filtre ou décoche la limitation aux tags liés.</p></div>'
      );
  }

  function renderTagTracks() {
    const library = getTagLibrary();
    const items = getFilteredTagItems();
    const byKey = {};
    (library.observedTags || []).forEach((item) => {
      const key = item.normalizedTag || item.rawTag || "";
      if (key) {
        byKey[key] = item;
      }
    });

    let activeTagKeys = [];
    let title = "Morceaux du genre";
    let subtitle = "Clique un tag ou tape une recherche pour voir les morceaux concernés.";

    if (store.selectedTagKey && byKey[store.selectedTagKey]) {
      activeTagKeys = [store.selectedTagKey];
      title = "Tag verrouillé · " + store.selectedTagKey;
      subtitle = "Affichage centré sur un seul tag sélectionné.";
    } else if (String(store.tagSearch || "").trim()) {
      activeTagKeys = Array.from(new Set(items.map((item) => item.normalizedTag || item.rawTag || "").filter(Boolean)));
      if (activeTagKeys.length === 1) {
        title = "Recherche · " + activeTagKeys[0];
        subtitle = "Tous les morceaux correspondant au tag recherché.";
      } else if (activeTagKeys.length > 1) {
        title = "Recherche multi-tags";
        subtitle = String(activeTagKeys.length) + " tags visibles, morceaux fusionnés sans doublons.";
      }
    }

    if (!activeTagKeys.length) {
      refs.tagTracksPanelBody.innerHTML =
        '<div class="empty-state">' +
          "<h3>Pas encore de morceaux ciblés</h3>" +
          "<p>" + escapeHtml(subtitle) + "</p>" +
        "</div>";
      return;
    }

    const recordsById = new Map((library.trackRecords || []).map((record) => [record.id, record]));
    const trackIds = [];
    const seen = new Set();

    activeTagKeys.forEach((tagKey) => {
      (library.tracksByTag && library.tracksByTag[tagKey] || []).forEach((trackId) => {
        if (seen.has(trackId) || !recordsById.has(trackId)) {
          return;
        }
        seen.add(trackId);
        trackIds.push(trackId);
      });
    });

    const tracks = trackIds
      .map((trackId) => recordsById.get(trackId))
      .filter(Boolean)
      .sort((left, right) => {
        const leftKey = [left.artist || "", left.album || "", left.title || "", left.filepath || ""].join(" ").toLowerCase();
        const rightKey = [right.artist || "", right.album || "", right.title || "", right.filepath || ""].join(" ").toLowerCase();
        return leftKey.localeCompare(rightKey, "fr");
      });

    refs.tagTracksPanelBody.innerHTML =
      '<div class="track-browser-toolbar">' +
        '<div>' +
          '<p class="tag-library-meta">' + escapeHtml(title) + "</p>" +
          '<p class="microcopy">' + escapeHtml(subtitle) + "</p>" +
        "</div>" +
        (store.selectedTagKey
          ? '<button class="button button-quiet panel-inline-action" type="button" data-track-browser-action="clear-selection">Retour à la recherche</button>'
          : "") +
      "</div>" +
      (
        tracks.length
          ? '<p class="tag-library-meta">' + escapeHtml(String(tracks.length)) + " morceau(x) affiché(s)</p>" +
            '<div class="track-library-list">' + tracks.map((track) => {
              const matchedTags = (track.normalizedGenres || []).filter((tag) => activeTagKeys.indexOf(tag) !== -1);
              const caption = [track.artist, track.album].filter(Boolean).join(" · ");
              return (
                '<article class="track-library-item">' +
                  '<div class="track-library-head">' +
                    '<div>' +
                      "<h3>" + escapeHtml(track.title || track.filename || "Morceau") + "</h3>" +
                      (caption ? '<p class="track-library-caption">' + escapeHtml(caption) + "</p>" : "") +
                    "</div>" +
                    '<span class="tag-meta-pill">' + escapeHtml(track.durationLabel || "00:00") + "</span>" +
                  "</div>" +
                  (track.filepath ? '<p class="track-library-path">' + escapeHtml(track.filepath) + "</p>" : "") +
                  (matchedTags.length
                    ? '<div class="tag-chip-list">' + matchedTags.map((tag) => (
                      '<span class="tag-chip secondary">' + escapeHtml(tag) + "</span>"
                    )).join("") + "</div>"
                    : "") +
                "</article>"
              );
            }).join("") + "</div>"
          : '<div class="empty-state"><h3>Aucun morceau</h3><p>Aucun morceau documenté pour ce tag.</p></div>'
      );
  }

  function renderDressing() {
    const items = store.state && store.state.settings && Array.isArray(store.state.settings.dressing)
      ? store.state.settings.dressing
      : [];

    refs.dressingPanelBody.innerHTML =
      items.length
        ? '<div class="dressing-grid">' + items.map((item) => (
          '<article class="dressing-card">' +
            "<h3>" + escapeHtml(item.label || item.id || "Habillage") + "</h3>" +
            "<p>" + escapeHtml(item.notes || "Aucune note.") + "</p>" +
            '<div class="stack-gap">' +
              '<label class="checkbox-row">' +
                '<input type="checkbox" data-dressing-id="' + escapeHtml(item.id) + '" data-dressing-field="enabled"' + (item.enabled ? " checked" : "") + " />" +
                "<span>Actif dans la grille</span>" +
              "</label>" +
              '<div class="triple-fields">' +
                '<label class="field">' +
                  '<span class="field-label-row"><span>Intervalle (min)</span></span>' +
                  '<input class="text-input" type="text" data-dressing-id="' + escapeHtml(item.id) + '" data-dressing-field="intervalMinutes" value="' + escapeHtml(item.intervalMinutes || "") + '" />' +
                "</label>" +
                '<label class="field">' +
                  '<span class="field-label-row"><span>Décalage (min)</span></span>' +
                  '<input class="text-input" type="text" data-dressing-id="' + escapeHtml(item.id) + '" data-dressing-field="offsetMinutes" value="' + escapeHtml(item.offsetMinutes || "") + '" />' +
                "</label>" +
                '<label class="field">' +
                  '<span class="field-label-row"><span>Priorité</span></span>' +
                  '<input class="text-input" type="text" data-dressing-id="' + escapeHtml(item.id) + '" data-dressing-field="priority" value="' + escapeHtml(item.priority || "") + '" />' +
                "</label>" +
              "</div>" +
              '<label class="field">' +
                '<span class="field-label-row"><span>Rattrapage</span></span>' +
                '<select class="select-input" data-dressing-id="' + escapeHtml(item.id) + '" data-dressing-field="catchupMode">' +
                  '<option value="until_next_trigger"' + (item.catchupMode === "until_next_trigger" ? " selected" : "") + '>Jusqu’au prochain déclenchement</option>' +
                  '<option value="fixed_window"' + (item.catchupMode === "fixed_window" ? " selected" : "") + '>Fenêtre fixe</option>' +
                "</select>" +
              "</label>" +
              '<label class="field">' +
                '<span class="field-label-row"><span>Mode source</span></span>' +
                '<input class="text-input" type="text" data-dressing-id="' + escapeHtml(item.id) + '" data-dressing-field="sourceMode" value="' + escapeHtml(item.sourceMode || "") + '" />' +
              "</label>" +
              '<label class="field">' +
                '<span class="field-label-row"><span>Chemin source</span></span>' +
                '<input class="text-input" type="text" data-dressing-id="' + escapeHtml(item.id) + '" data-dressing-field="sourcePath" value="' + escapeHtml(item.sourcePath || "") + '" />' +
              "</label>" +
              '<label class="field">' +
                '<span class="field-label-row"><span>Notes</span></span>' +
                '<textarea class="textarea-input" rows="3" data-dressing-id="' + escapeHtml(item.id) + '" data-dressing-field="notes">' + escapeHtml(item.notes || "") + "</textarea>" +
              "</label>" +
            "</div>" +
          "</article>"
        )).join("") + "</div>"
        : '<div class="empty-state"><h3>Pas d’habillage</h3><p>Aucun réglage disponible.</p></div>';
  }

  function renderRuntime() {
    const runtime = getRuntimeConfig();
    const rotationPolicy = getRotationPolicy();
    const pathRows = [
      [
        ["musicLibraryRoot", "Bibliothèque musique"],
        ["radioRoot", "Racine radio"],
      ],
      [
        ["poolsDir", "Dossier pools"],
        ["emissionsDir", "Dossier émissions"],
      ],
      [
        ["jinglesDir", "Dossier jingles"],
        ["reclamesDir", "Dossier réclames"],
      ],
      [
        ["logsDir", "Dossier logs"],
        ["webRoot", "Racine web"],
      ],
      [
        ["currentShowJson", "Current show JSON"],
        ["nowPlayingJson", "Now playing JSON"],
      ],
      [
        ["historyDir", "Dossier historique"],
      ],
    ];

    const renderRuntimeTextField = (label, value, attributes) => (
      `<label class="field">
        <span class="field-label-row"><span>${escapeHtml(label)}</span></span>
        <input class="text-input" type="text" ${attributes} value="${escapeHtml(value || "")}" />
      </label>`
    );

    const renderRuntimeCheckbox = (label, checked, attributes) => (
      `<label class="checkbox-row">
        <input type="checkbox" ${attributes}${checked ? " checked" : ""} />
        <span>${escapeHtml(label)}</span>
      </label>`
    );

    const outputCards = (runtime.outputs || []).map((output) => `
      <div class="runtime-card">
        <h3>${escapeHtml(String(output.id || "sortie").toUpperCase())}</h3>
        <div class="stack-gap">
          ${renderRuntimeCheckbox("Sortie active", Boolean(output.enabled), `data-output-id="${escapeHtml(output.id)}" data-output-field="enabled"`)}
          <div class="triple-fields">
            ${renderRuntimeTextField("Format", output.format, `data-output-id="${escapeHtml(output.id)}" data-output-field="format"`)}
            ${renderRuntimeTextField("Bitrate kbps", output.bitrateKbps, `data-output-id="${escapeHtml(output.id)}" data-output-field="bitrateKbps"`)}
            ${renderRuntimeCheckbox("Stéréo", Boolean(output.stereo), `data-output-id="${escapeHtml(output.id)}" data-output-field="stereo"`)}
          </div>
          <div class="split-fields">
            ${renderRuntimeTextField("Host", output.host, `data-output-id="${escapeHtml(output.id)}" data-output-field="host"`)}
            ${renderRuntimeTextField("Port", output.port, `data-output-id="${escapeHtml(output.id)}" data-output-field="port"`)}
          </div>
          <div class="split-fields">
            ${renderRuntimeTextField("Mount", output.mount, `data-output-id="${escapeHtml(output.id)}" data-output-field="mount"`)}
            ${renderRuntimeTextField("Mot de passe", output.password, `data-output-id="${escapeHtml(output.id)}" data-output-field="password"`)}
          </div>
          ${renderRuntimeTextField("Nom", output.name, `data-output-id="${escapeHtml(output.id)}" data-output-field="name"`)}
          ${renderRuntimeTextField("Description", output.description, `data-output-id="${escapeHtml(output.id)}" data-output-field="description"`)}
          <div class="split-fields">
            ${renderRuntimeTextField("Genre", output.genre, `data-output-id="${escapeHtml(output.id)}" data-output-field="genre"`)}
            ${renderRuntimeTextField("URL", output.url, `data-output-id="${escapeHtml(output.id)}" data-output-field="url"`)}
          </div>
        </div>
      </div>
    `).join("");

    refs.runtimePanelBody.innerHTML = `
      <div class="runtime-grid">
        <article class="runtime-card">
          <h3>Chemins système</h3>
          <p>Racines et sorties utilisées pour générer ensuite le script Liquidsoap et les fichiers auxiliaires.</p>
          <div class="stack-gap">
            ${pathRows.map((row) => `
              <div class="${row.length > 1 ? "split-fields" : "stack-gap"}">
                ${row.map(([fieldName, label]) => renderRuntimeTextField(
                  label,
                  runtime.paths[fieldName],
                  `data-runtime-path="${escapeHtml(fieldName)}"`
                )).join("")}
              </div>
            `).join("")}
          </div>
        </article>

        <article class="runtime-card">
          <h3>Entrée live</h3>
          <p>Paramètres nécessaires pour générer le bloc <code>input.harbor</code> du direct.</p>
          <div class="stack-gap">
            ${renderRuntimeCheckbox("Activer l’entrée live", Boolean(runtime.liveInput.enabled), 'data-live-field="enabled"')}
            <div class="split-fields">
              ${renderRuntimeTextField("Nom harbor", runtime.liveInput.harborName, 'data-live-field="harborName"')}
              ${renderRuntimeTextField("Port", runtime.liveInput.port, 'data-live-field="port"')}
            </div>
            ${renderRuntimeTextField("Mot de passe", runtime.liveInput.password, 'data-live-field="password"')}
            ${renderRuntimeCheckbox("Activer les métadonnées ICY", Boolean(runtime.liveInput.icy), 'data-live-field="icy"')}
          </div>
        </article>

        <article class="runtime-card">
          <h3>Sorties Icecast</h3>
          <p>Chaque sortie décrit un flux générable dans <code>radio.liq</code>. Tu peux en garder plusieurs.</p>
          <div class="output-grid">
            ${outputCards}
          </div>
        </article>

        <article class="runtime-card">
          <h3>Rotation anti-random</h3>
          <p>Cooldowns à transmettre ensuite au générateur de pools pour éviter les répétitions trop proches.</p>
          <div class="triple-fields">
            ${renderRuntimeTextField("Artiste (min)", rotationPolicy.artistCooldownMinutes, 'data-rotation-field="artistCooldownMinutes"')}
            ${renderRuntimeTextField("Album (min)", rotationPolicy.albumCooldownMinutes, 'data-rotation-field="albumCooldownMinutes"')}
            ${renderRuntimeTextField("Piste (min)", rotationPolicy.trackCooldownMinutes, 'data-rotation-field="trackCooldownMinutes"')}
          </div>
        </article>
      </div>
    `;
  }

  function renderPreview() {
    refs.previewJsonButton.classList.toggle("is-active", store.previewFormat === "json");
    refs.previewJsonlButton.classList.toggle("is-active", store.previewFormat === "jsonl");
    refs.exportPreview.textContent = store.previewFormat === "json" ? buildExportJson() : buildExportJsonl();
  }

  function renderAll() {
    renderToolbar();
    renderPlanner();
    renderSlotEditor();
    renderShowProfile();
    renderTagLibrary();
    renderTagTracks();
    renderDressing();
    renderRuntime();
    renderPreview();
    applyCollapsedPanels();
  }

  function getTrackElement(dayKey) {
    return refs.plannerGrid.querySelector('[data-day-track="' + dayKey + '"]');
  }

  function resolveStepFromPointer(dayKey, clientY) {
    const track = getTrackElement(dayKey);
    if (!track) return 0;
    const rect = track.getBoundingClientRect();
    const offsetY = clientY - rect.top;
    return clamp(Math.floor(offsetY / STEP_HEIGHT), 0, DAY_STEPS - 1);
  }

  function startCreateInteraction(dayKey, clientY) {
    const step = resolveStepFromPointer(dayKey, clientY);
    store.interaction = {
      type: "create",
      dayKey: dayKey,
      mode: store.creationMode,
      anchorStep: step,
      currentStep: step,
    };
    renderPlanner();
  }

  function startMoveInteraction(dayKey, mode, slotId, clientY) {
    const found = findSlotRef(dayKey, mode, slotId);
    if (!found) return;
    const extent = getSlotExtent(found.slot);
    const pointerStep = resolveStepFromPointer(dayKey, clientY);
    store.selected = { dayKey: dayKey, mode: mode, slotId: slotId };
    store.interaction = {
      type: "move",
      dayKey: dayKey,
      mode: mode,
      slotId: slotId,
      anchorStep: pointerStep,
      originStartStep: extent.startStep,
      originEndStep: extent.endStep,
      previewStartStep: extent.startStep,
      previewEndStep: extent.endStep,
      moved: false,
    };
    renderPlanner();
    renderSlotEditor();
    renderShowProfile();
  }

  function startResizeInteraction(dayKey, mode, slotId, edge) {
    const found = findSlotRef(dayKey, mode, slotId);
    if (!found) return;
    const extent = getSlotExtent(found.slot);
    store.selected = { dayKey: dayKey, mode: mode, slotId: slotId };
    store.interaction = {
      type: "resize",
      dayKey: dayKey,
      mode: mode,
      slotId: slotId,
      edge: edge,
      originStartStep: extent.startStep,
      originEndStep: extent.endStep,
      previewStartStep: extent.startStep,
      previewEndStep: extent.endStep,
      moved: false,
    };
    renderPlanner();
    renderSlotEditor();
    renderShowProfile();
  }

  function updateInteraction(clientY) {
    if (!store.interaction) return;

    if (store.interaction.type === "create") {
      store.interaction.currentStep = resolveStepFromPointer(store.interaction.dayKey, clientY);
      renderPlanner();
      return;
    }

    const step = resolveStepFromPointer(store.interaction.dayKey, clientY);
    if (store.interaction.type === "move") {
      const span = store.interaction.originEndStep - store.interaction.originStartStep;
      const delta = step - store.interaction.anchorStep;
      const start = clamp(store.interaction.originStartStep + delta, 0, DAY_STEPS - span);
      store.interaction.previewStartStep = start;
      store.interaction.previewEndStep = start + span;
      store.interaction.moved = store.interaction.moved || delta !== 0;
    }

    if (store.interaction.type === "resize") {
      if (store.interaction.edge === "start") {
        const start = clamp(step, 0, store.interaction.originEndStep - 1);
        store.interaction.previewStartStep = start;
        store.interaction.previewEndStep = store.interaction.originEndStep;
        store.interaction.moved = store.interaction.moved || start !== store.interaction.originStartStep;
      } else {
        const end = clamp(step + 1, store.interaction.originStartStep + 1, DAY_STEPS);
        store.interaction.previewStartStep = store.interaction.originStartStep;
        store.interaction.previewEndStep = end;
        store.interaction.moved = store.interaction.moved || end !== store.interaction.originEndStep;
      }
    }

    renderPlanner();
    renderSlotEditor();
  }

  function finishInteraction(cancelled) {
    if (!store.interaction) return;
    const interaction = store.interaction;
    store.interaction = null;

    if (cancelled) {
      renderAll();
      return;
    }

    if (interaction.type === "create") {
      const startStep = Math.min(interaction.anchorStep, interaction.currentStep);
      const endStep = Math.max(interaction.anchorStep, interaction.currentStep) + 1;
      const slot = buildDefaultSlot(interaction.mode, interaction.dayKey, startStep, endStep);
      const day = getStateDay(interaction.dayKey);
      if (interaction.mode === "event") {
        day.events.push(slot);
      } else {
        day.blocks.push(slot);
      }
      sortDay(interaction.dayKey);
      store.selected = { dayKey: interaction.dayKey, mode: interaction.mode, slotId: slot.id };
      markDirty(interaction.mode === "event" ? "Nouvelle émission créée." : "Nouveau bloc créé.");
      return;
    }

    if (!interaction.moved) {
      store.selected = { dayKey: interaction.dayKey, mode: interaction.mode, slotId: interaction.slotId };
      renderAll();
      return;
    }

    const found = findSlotRef(interaction.dayKey, interaction.mode, interaction.slotId);
    if (!found) {
      renderAll();
      return;
    }

    applyExtentToSlot(found.slot, interaction.previewStartStep, interaction.previewEndStep);
    sortDay(found.dayKey);
    store.selected = { dayKey: interaction.dayKey, mode: interaction.mode, slotId: interaction.slotId };
    markDirty(interaction.type === "move" ? "Créneau déplacé." : "Créneau redimensionné.");
  }

  function attachEvents() {
    document.addEventListener("click", (event) => {
      const toggleButton = event.target.closest("[data-panel-toggle]");
      if (toggleButton) {
        togglePanel(toggleButton.getAttribute("data-panel-toggle"));
      }
    });

    refs.currentGridButton.addEventListener("click", () => {
      loadCurrentGridPreset();
    });

    refs.blankGridButton.addEventListener("click", () => {
      loadBlankGridPreset();
    });

    refs.saveFileButton.addEventListener("click", () => {
      saveToServer().catch((error) => {
        updateStatus(String(error.message || error), "warning");
      });
    });

    refs.exportJsonButton.addEventListener("click", () => {
      downloadText("grille-programmes.json", "application/json", buildExportJson());
    });

    refs.exportJsonlButton.addEventListener("click", () => {
      downloadText("grille-programmes.jsonl", "application/x-ndjson", buildExportJsonl());
    });

    refs.createBlockModeButton.addEventListener("click", () => {
      store.creationMode = "block";
      renderToolbar();
    });

    refs.createEventModeButton.addEventListener("click", () => {
      store.creationMode = "event";
      renderToolbar();
    });

    refs.showFilterSelect.addEventListener("change", () => {
      store.filterKey = refs.showFilterSelect.value || "";
      renderPlanner();
    });

    refs.tagSearchInput.addEventListener("input", () => {
      store.tagSearch = refs.tagSearchInput.value || "";
      if (store.selectedTagKey && !String(store.tagSearch || "").trim()) {
        store.selectedTagKey = "";
      }
      renderTagLibrary();
      renderTagTracks();
    });

    refs.tagRelatedOnlyInput.addEventListener("change", () => {
      store.tagRelatedOnly = Boolean(refs.tagRelatedOnlyInput.checked);
      renderTagLibrary();
      renderTagTracks();
    });

    refs.tagLibraryPanelBody.addEventListener("click", (event) => {
      const tagButton = event.target.closest("[data-tag-key]");
      if (!tagButton) return;
      const tagKey = tagButton.getAttribute("data-tag-key") || "";
      store.selectedTagKey = store.selectedTagKey === tagKey ? "" : tagKey;
      renderTagLibrary();
      renderTagTracks();
    });

    refs.tagTracksPanelBody.addEventListener("click", (event) => {
      const actionButton = event.target.closest("[data-track-browser-action]");
      if (!actionButton) return;
      if (actionButton.getAttribute("data-track-browser-action") === "clear-selection") {
        store.selectedTagKey = "";
        renderTagLibrary();
        renderTagTracks();
      }
    });

    refs.previewJsonButton.addEventListener("click", () => {
      store.previewFormat = "json";
      renderPreview();
    });

    refs.previewJsonlButton.addEventListener("click", () => {
      store.previewFormat = "jsonl";
      renderPreview();
    });

    refs.importFileInput.addEventListener("change", () => {
      const file = refs.importFileInput.files && refs.importFileInput.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = function () {
        try {
          const parsed = JSON.parse(String(reader.result || "{}"));
          ensureStateShape(parsed);
          store.state = parsed;
          store.selected = null;
          store.selectedTagKey = "";
          markDirty("JSON importé dans le navigateur. Sauvegarde disque à lancer si besoin.");
        } catch (error) {
          updateStatus(String(error.message || error), "warning");
        } finally {
          refs.importFileInput.value = "";
        }
      };
      reader.readAsText(file, "utf-8");
    });

    refs.plannerGrid.addEventListener("pointerdown", (event) => {
      const handle = event.target.closest(".slot-handle");
      const slotButton = event.target.closest(".slot-card[data-slot-id]");
      const track = event.target.closest("[data-day-track]");

      if (handle && slotButton) {
        event.preventDefault();
        startResizeInteraction(
          slotButton.getAttribute("data-day-key"),
          slotButton.getAttribute("data-mode"),
          slotButton.getAttribute("data-slot-id"),
          handle.getAttribute("data-edge")
        );
        return;
      }

      if (slotButton) {
        event.preventDefault();
        startMoveInteraction(
          slotButton.getAttribute("data-day-key"),
          slotButton.getAttribute("data-mode"),
          slotButton.getAttribute("data-slot-id"),
          event.clientY
        );
        return;
      }

      if (track) {
        event.preventDefault();
        startCreateInteraction(track.getAttribute("data-day-track"), event.clientY);
      }
    });

    document.addEventListener("pointermove", (event) => {
      if (!store.interaction) return;
      event.preventDefault();
      updateInteraction(event.clientY);
    });

    document.addEventListener("pointerup", () => {
      finishInteraction(false);
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        finishInteraction(true);
      }
    });

    refs.slotEditorPanelBody.addEventListener("change", (event) => {
      const field = event.target.closest("[data-slot-field]");
      if (!field) return;
      updateSelectedSlotField(field.getAttribute("data-slot-field"), field.value);
    });

    refs.slotEditorPanelBody.addEventListener("click", (event) => {
      const button = event.target.closest("[data-slot-action]");
      if (!button) return;
      const action = button.getAttribute("data-slot-action");
      if (action === "duplicate") {
        duplicateSelectedSlot();
      }
      if (action === "delete") {
        if (!window.confirm("Supprimer ce créneau ?")) return;
        removeSelectedSlot();
      }
    });

    refs.dressingPanelBody.addEventListener("change", (event) => {
      const field = event.target.closest("[data-dressing-field]");
      if (!field) return;
      updateDressingField(
        field.getAttribute("data-dressing-id"),
        field.getAttribute("data-dressing-field"),
        field.type === "checkbox" ? field.checked : field.value,
        field.checked
      );
    });

    refs.runtimePanelBody.addEventListener("change", (event) => {
      const runtimePathField = event.target.closest("[data-runtime-path]");
      if (runtimePathField) {
        updateRuntimePath(runtimePathField.getAttribute("data-runtime-path"), runtimePathField.value);
        return;
      }

      const liveField = event.target.closest("[data-live-field]");
      if (liveField) {
        updateLiveField(
          liveField.getAttribute("data-live-field"),
          liveField.value,
          liveField.checked
        );
        return;
      }

      const outputField = event.target.closest("[data-output-id][data-output-field]");
      if (outputField) {
        updateOutputField(
          outputField.getAttribute("data-output-id"),
          outputField.getAttribute("data-output-field"),
          outputField.value,
          outputField.checked
        );
        return;
      }

      const rotationField = event.target.closest("[data-rotation-field]");
      if (rotationField) {
        updateRotationField(rotationField.getAttribute("data-rotation-field"), rotationField.value);
      }
    });

    window.addEventListener("beforeunload", (event) => {
      if (!store.dirty) return;
      event.preventDefault();
      event.returnValue = "";
    });
  }

  async function bootstrap() {
    updateStatus("Chargement de la grille…");
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Impossible de charger la grille.");
    }
    const payload = await response.json();
    if (!payload.ok) {
      throw new Error(payload.message || "Chargement impossible.");
    }
    setStateFromPayload(payload);
    if (!store.localSavedAt) {
      updateStatus("Grille chargée.", "success");
    }
  }

  loadUiPrefs();
  attachEvents();
  bootstrap().catch((error) => {
    updateStatus(String(error.message || error), "warning");
  });
})();
