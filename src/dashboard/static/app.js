/* ==========================================================================
   Spaceborne Rapid Disaster Assessment Dashboard
   Operational Map Product Design (Copernicus EMS / UN OCHA Map Portfolio)
   ========================================================================== */

let currentLang = "en";
let currentRunId = null;
let currentRunData = null;
let allRunsList = [];

// Filter States
let currentMode = "vehicle";       // "vehicle" | "walking"
let currentScenario = "optimistic"; // "optimistic" | "pessimistic"

// Map and Overlays
let map = null;
let baseLayers = {
  osmTiles: null,
  hillshadeTiles: null,
  offlineGroup: null
};
let isOfflineFallbackActive = false;
let aoiDimLayer = null;
let aoiDashedLine = null;

let geojsonLayers = {
  hazards: null,
  buildings: null,
  roads: null,
  bridges: null,
  settlements: null,
  repair_packages: null,
  places: null
};

// S2 slider state
let s2OverlayActive = false;
let s2PreOverlay = null;
let s2PostOverlay = null;

// Start screen state
let isStartScreenActive = false;
let startBboxRect = null;
let startBboxCornerMarkers = [];
let startSearchThrottleTimer = null;

function startDashboardApp() {
  initMap();
  initHeaderControls();
  initTabs();
  initLegendControls();
  initAccessFilters();
  initCopilot();
  initModals();
  initStartScreen();
  loadRunsList();
}

// Start application immediately
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => startDashboardApp());
} else {
  startDashboardApp();
}

// ==========================================================================
// Map Initialization
// ==========================================================================
function initMap() {
  map = L.map("map", {
    center: [28.15, 85.35],
    zoom: 12,
    zoomControl: false,
    attributionControl: false,
    preferCanvas: true
  });

  // Zoom control in top right (above map action controls)
  L.control.zoom({ position: "topright" }).addTo(map);

  // Scale bar in bottom right (above status ribbon, left of "Ask copilot" button)
  L.control.scale({ position: "bottomright", metric: true, imperial: false }).addTo(map);

  // Cursor and Center coordinates in status ribbon
  const updateCoords = (lat, lng) => {
    const latDir = lat >= 0 ? "N" : "S";
    const lngDir = lng >= 0 ? "E" : "W";
    const el = document.getElementById("status-cursor-coords");
    if (el) {
      el.textContent = `${Math.abs(lat).toFixed(4)}° ${latDir}, ${Math.abs(lng).toFixed(4)}° ${lngDir}`;
    }
  };

  // Throttle mousemove coordinate updates using requestAnimationFrame
  let mouseMoveRaf = null;
  map.on("mousemove", (e) => {
    if (mouseMoveRaf) return;
    mouseMoveRaf = requestAnimationFrame(() => {
      updateCoords(e.latlng.lat, e.latlng.lng);
      mouseMoveRaf = null;
    });
  });

  const showCenterCoords = () => {
    const center = map.getCenter();
    updateCoords(center.lat, center.lng);
  };

  map.on("mouseout", showCenterCoords);
  map.on("moveend", showCenterCoords);
  // Initial center coordinates
  showCenterCoords();

  // Custom Panes to maintain visual stacking
  // 1. OSM Tile Pane (z=100) - Muted via CSS filter
  map.createPane("osmTilePane");
  map.getPane("osmTilePane").style.zIndex = 100;

  // 2. Terrain Overlay Pane (z=150) - Plain opacity overlay over OSM base
  map.createPane("hillshadePane");
  map.getPane("hillshadePane").style.zIndex = 150;

  // 3. Fallback Panes
  map.createPane("basemapImagePane");
  map.getPane("basemapImagePane").style.zIndex = 160;

  map.createPane("basemapVectorPane");
  map.getPane("basemapVectorPane").style.zIndex = 180;

  // 4. AOI Dimming Pane (z=200)
  map.createPane("aoiDimPane");
  map.getPane("aoiDimPane").style.zIndex = 200;

  // 5. Sentinel-2 Comparison Imagery Pane (z=250, below vector overlays at z=400+)
  map.createPane("s2Pane");
  map.getPane("s2Pane").style.zIndex = 250;

  // Add default OSM raster tiles to osmTilePane
  baseLayers.osmTiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    pane: "osmTilePane",
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors"
  }).addTo(map);

  baseLayers.offlineGroup = L.layerGroup();
}

// ==========================================================================
// Header & Navigation Controls
// ==========================================================================
function initHeaderControls() {
  const btnSwitcher = document.getElementById("btn-open-run-switcher");
  const switcherModal = document.getElementById("run-switcher-modal");
  const btnSitrep = document.getElementById("btn-download-sitrep");
  const btnMore = document.getElementById("btn-more-menu");
  const moreMenu = document.getElementById("more-dropdown-menu");

  if (btnSwitcher) {
    btnSwitcher.addEventListener("click", () => {
      openRunSwitcherModal();
    });
  }

  if (btnSitrep) {
    btnSitrep.addEventListener("click", () => {
      if (currentRunId) {
        window.open(`/api/runs/${currentRunId}/sitrep?lang=${currentLang}&format=pdf`, "_blank");
      }
    });
  }

  if (btnMore && moreMenu) {
    btnMore.addEventListener("click", (e) => {
      e.stopPropagation();
      moreMenu.classList.toggle("hidden");
    });
    document.addEventListener("click", () => {
      moreMenu.classList.add("hidden");
    });
  }

  const btnBrandHome = document.getElementById("btn-brand-home");
  if (btnBrandHome) {
    btnBrandHome.addEventListener("click", () => {
      showStartScreen();
    });
  }

  // More menu items
  const optSlider = document.getElementById("menu-opt-slider");
  if (optSlider) {
    optSlider.addEventListener("click", () => {
      if (moreMenu) moreMenu.classList.add("hidden");
      toggleS2Slider(!s2OverlayActive);
    });
  }

  // Map Top-Right Before / after button
  const btnMapS2 = document.getElementById("btn-toggle-s2-comparison");
  if (btnMapS2) {
    btnMapS2.addEventListener("click", () => {
      toggleS2Slider(!s2OverlayActive);
    });
  }

  const optLang = document.getElementById("menu-opt-lang");
  if (optLang) {
    optLang.addEventListener("click", () => {
      if (moreMenu) moreMenu.classList.add("hidden");
      currentLang = currentLang === "en" ? "ne" : "en";
      optLang.textContent = currentLang === "en" ? "नेपाली" : "English";
      if (currentRunData) {
        updateSidePanel(currentRunData);
        updateAccessList();
      }
    });
  }

  const optProj = document.getElementById("menu-opt-projector");
  if (optProj) {
    optProj.addEventListener("click", () => {
      if (moreMenu) moreMenu.classList.add("hidden");
      document.body.classList.toggle("projector-mode");
      const isProj = document.body.classList.contains("projector-mode");
      optProj.textContent = isProj ? "Normal display mode" : "Projector mode";
    });
  }

  const optOpenRun = document.getElementById("menu-opt-open-run");
  if (optOpenRun) {
    optOpenRun.addEventListener("click", () => {
      if (moreMenu) moreMenu.classList.add("hidden");
      openRunSwitcherModal();
    });
  }
}

function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) targetPanel.classList.add("active");
    });
  });
}

function initLegendControls() {
  const toggleBtn = document.getElementById("toggle-legend-btn");
  const legendBody = document.getElementById("legend-body");
  const icon = toggleBtn.querySelector(".collapse-icon");

  toggleBtn.addEventListener("click", () => {
    legendBody.classList.toggle("hidden");
    icon.textContent = legendBody.classList.contains("hidden") ? "▲" : "▼";
  });

  const btnMore = document.getElementById("btn-toggle-more-layers");
  const moreContainer = document.getElementById("legend-more-container");
  if (btnMore && moreContainer) {
    btnMore.addEventListener("click", () => {
      moreContainer.classList.toggle("hidden");
      btnMore.textContent = moreContainer.classList.contains("hidden") ? "More layers" : "Fewer layers";
    });
  }

  // Toggle handlers for layers
  const setupToggle = (chkId, layerKey) => {
    const el = document.getElementById(chkId);
    if (!el) return;
    el.addEventListener("change", () => {
      const layer = geojsonLayers[layerKey];
      if (!layer) return;
      if (el.checked) {
        if (!map.hasLayer(layer)) map.addLayer(layer);
      } else {
        if (map.hasLayer(layer)) map.removeLayer(layer);
      }
    });
  };

  setupToggle("layer-haz-obs", "hazards");
  setupToggle("layer-haz-inf", "hazards");
  setupToggle("layer-haz-perm", "hazards");
  setupToggle("layer-buildings", "buildings");
  setupToggle("layer-bridges", "bridges");
  setupToggle("layer-roads", "roads");
  setupToggle("layer-settlements", "settlements");
  setupToggle("layer-no-ground", "settlements");

  const chkObs = document.getElementById("layer-haz-obs");
  const chkInf = document.getElementById("layer-haz-inf");
  const chkPerm = document.getElementById("layer-haz-perm");

  const filterHazards = () => {
    if (!geojsonLayers.hazards) return;
    geojsonLayers.hazards.eachLayer(l => {
      const cls = l.feature.properties.class || l.feature.properties.hazard_class;
      let vis = true;
      if (cls === 1 && !chkPerm.checked) vis = false;
      if (cls === 2 && !chkObs.checked) vis = false;
      if (cls === 3 && !chkInf.checked) vis = false;
      if (vis) {
        if (!map.hasLayer(l)) map.addLayer(l);
      } else {
        if (map.hasLayer(l)) map.removeLayer(l);
      }
    });
  };

  if (chkObs) chkObs.addEventListener("change", filterHazards);
  if (chkInf) chkInf.addEventListener("change", filterHazards);
  if (chkPerm) chkPerm.addEventListener("change", filterHazards);

  const chkIntact = document.getElementById("layer-intact-buildings");
  if (chkIntact) {
    chkIntact.addEventListener("change", () => {
      if (currentRunId) loadBuildingsLayer(currentRunId);
    });
  }
}

function initAccessFilters() {
  const btnVeh = document.getElementById("btn-mode-vehicle");
  const btnWalk = document.getElementById("btn-mode-walking");
  const btnOpt = document.getElementById("btn-scen-opt");
  const btnPess = document.getElementById("btn-scen-pess");

  btnVeh.addEventListener("click", () => {
    currentMode = "vehicle";
    btnVeh.classList.add("active");
    btnWalk.classList.remove("active");
    updateAccessList();
  });

  btnWalk.addEventListener("click", () => {
    currentMode = "walking";
    btnWalk.classList.add("active");
    btnVeh.classList.remove("active");
    updateAccessList();
  });

  btnOpt.addEventListener("click", () => {
    currentScenario = "optimistic";
    btnOpt.classList.add("active");
    btnPess.classList.remove("active");
    updateAccessList();
  });

  btnPess.addEventListener("click", () => {
    currentScenario = "pessimistic";
    btnPess.classList.add("active");
    btnOpt.classList.remove("active");
    updateAccessList();
  });

  const btnShowOther = document.getElementById("btn-show-other-settlements");
  const otherContainer = document.getElementById("list-road-cut-remaining");
  if (btnShowOther && otherContainer) {
    btnShowOther.addEventListener("click", () => {
      otherContainer.classList.toggle("hidden");
      btnShowOther.classList.toggle("expanded");
    });
  }

  const btnZoomRepair = document.getElementById("btn-zoom-repair");
  if (btnZoomRepair) {
    btnZoomRepair.addEventListener("click", () => {
      if (!geojsonLayers.repair_packages || geojsonLayers.repair_packages.getLayers().length === 0) {
        return;
      }
      if (map.hasLayer(geojsonLayers.repair_packages)) {
        map.removeLayer(geojsonLayers.repair_packages);
        btnZoomRepair.classList.remove("active");
        btnZoomRepair.textContent = "Show on map";
      } else {
        geojsonLayers.repair_packages.addTo(map);
        map.fitBounds(geojsonLayers.repair_packages.getBounds(), { padding: [50, 50], maxZoom: 15 });
        btnZoomRepair.classList.add("active");
        btnZoomRepair.textContent = "Clear from map";
      }
    });
  }
}

// ==========================================================================
// Start Screen & Region View (Item 3)
// Map roughly 70-98 E, 5-37 N with Nominatim Search & 10x10km editable box
// ==========================================================================
function initStartScreen() {
  const searchInput = document.getElementById("start-search-input");
  const searchBtn = document.getElementById("btn-start-search");
  const resultsDiv = document.getElementById("start-search-results");
  const dateInput = document.getElementById("start-event-date");
  const datePreview = document.getElementById("start-date-preview");
  const analyseBtn = document.getElementById("btn-start-analyse");

  function updateStartDatePreview() {
    if (!dateInput.value) {
      datePreview.textContent = "";
      return;
    }
    const [y, m, d] = dateInput.value.split("-").map(Number);
    if (y && m && d) {
      const dt = new Date(Date.UTC(y, m - 1, d));
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      datePreview.textContent = `${dt.getUTCDate()} ${months[dt.getUTCMonth()]} ${dt.getUTCFullYear()}`;
    }
  }

  if (dateInput) {
    dateInput.addEventListener("input", updateStartDatePreview);
    dateInput.addEventListener("change", updateStartDatePreview);
    // Default date to today or 2026-08-26
    dateInput.value = "2026-08-26";
    updateStartDatePreview();
  }

  // Search only on Enter or click (no autocomplete)
  if (searchBtn && searchInput) {
    searchBtn.addEventListener("click", () => doNominatimSearch(searchInput.value.trim()));
    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        doNominatimSearch(searchInput.value.trim());
      }
    });
  }

  if (analyseBtn) {
    analyseBtn.addEventListener("click", async () => {
      if (!startBboxRect) {
        alert("Please search a place to select an area first.");
        return;
      }
      const bounds = startBboxRect.getBounds();
      const w = bounds.getWest();
      const s = bounds.getSouth();
      const e = bounds.getEast();
      const n = bounds.getNorth();

      const eventDate = document.getElementById("start-event-date").value.trim();
      const eventName = document.getElementById("start-event-name").value.trim();
      if (!eventDate) {
        alert("Please choose an event date.");
        return;
      }

      analyseBtn.disabled = true;
      analyseBtn.textContent = "Starting assessment...";

      try {
        const resp = await fetch("/api/runs/create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            bbox: [w, s, e, n],
            event_date: eventDate,
            event_name: eventName || null
          })
        });
        if (!resp.ok) {
          const err = await resp.json();
          throw new Error(err.detail || "Failed to create assessment");
        }
        const data = await resp.json();
        // Transition to live tracking
        hideStartScreen();
        await loadRunsList();
        loadRun(data.run_id);
      } catch (err) {
        alert("Error launching assessment: " + err.message);
      } finally {
        analyseBtn.disabled = false;
        analyseBtn.textContent = "Analyse this area";
      }
    });
  }
}

async function doNominatimSearch(query) {
  if (!query || query.length < 2) return;
  const resultsDiv = document.getElementById("start-search-results");
  if (!resultsDiv) return;

  resultsDiv.innerHTML = '<div style="font-size: 11.5px; color: var(--text-secondary); padding: 4px;">Searching...</div>';
  resultsDiv.classList.remove("hidden");

  try {
    const res = await fetch(`/api/search/place?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    resultsDiv.innerHTML = "";

    if (!data || data.length === 0) {
      resultsDiv.innerHTML = '<div style="font-size: 11.5px; color: var(--text-secondary); padding: 4px;">No places found. Try another place name.</div>';
      return;
    }

    const items = data.slice(0, 5);
    items.forEach(place => {
      const itemEl = document.createElement("div");
      itemEl.className = "start-search-item";
      const cleanName = place.display_name.split(",").slice(0, 3).join(",");
      const typeLabel = place.type || place.class || "place";
      itemEl.innerHTML = `
        <span>${escapeHtml(cleanName)}</span>
        <span class="start-search-item-type">${escapeHtml(typeLabel)}</span>
      `;
      itemEl.addEventListener("click", () => {
        selectSearchResultPlace(place);
      });
      resultsDiv.appendChild(itemEl);
    });
  } catch (err) {
    resultsDiv.innerHTML = `<div style="font-size: 11.5px; color: var(--data-destroyed); padding: 4px;">Search failed: ${escapeHtml(err.message)}</div>`;
  }
}

function selectSearchResultPlace(place) {
  const lat = parseFloat(place.lat);
  const lon = parseFloat(place.lon);
  if (isNaN(lat) || isNaN(lon)) return;

  const resultsDiv = document.getElementById("start-search-results");
  if (resultsDiv) resultsDiv.classList.add("hidden");

  // Center map on place at zoom 12
  map.setView([lat, lon], 12);

  // Create editable ~10x10 km box centered at (lat, lon)
  // At latitude `lat`, 10km is ~ 10/111 deg lat, and 10/(111*cos(lat)) deg lon
  const latDelta = (10.0 / 111.0) / 2.0; // ~0.045 deg
  const cosLat = Math.max(0.1, Math.cos((lat * Math.PI) / 180.0));
  const lonDelta = (10.0 / (111.0 * cosLat)) / 2.0;

  const south = lat - latDelta;
  const north = lat + latDelta;
  const west = lon - lonDelta;
  const east = lon + lonDelta;

  renderEditableBbox([west, south, east, north]);

  const formEl = document.getElementById("start-analysis-form");
  if (formEl) formEl.classList.remove("hidden");

  // Auto-populate default event name if empty
  const nameInput = document.getElementById("start-event-name");
  if (nameInput && !nameInput.value) {
    const pName = place.display_name.split(",")[0].trim();
    nameInput.value = `${pName} Assessment`;
  }
}

function renderEditableBbox(bbox) {
  clearStartBbox();
  const [w, s, e, n] = bbox;
  const bounds = [[s, w], [n, e]];

  startBboxRect = L.rectangle(bounds, {
    color: "#B42318",
    weight: 2,
    dashArray: "4, 4",
    fillColor: "#B42318",
    fillOpacity: 0.12
  }).addTo(map);

  updateStartBboxStats();

  // 4 Corner Drag Handles
  const corners = [
    { id: "sw", latlng: [s, w] },
    { id: "nw", latlng: [n, w] },
    { id: "ne", latlng: [n, e] },
    { id: "se", latlng: [s, e] }
  ];

  corners.forEach(c => {
    const marker = L.circleMarker(c.latlng, {
      radius: 6,
      color: "#B42318",
      fillColor: "#FFFFFF",
      fillOpacity: 1,
      weight: 2,
      draggable: true
    }).addTo(map);

    // Make interactive dragging
    let isDragging = false;
    marker.on("mousedown", (ev) => {
      L.DomEvent.stopPropagation(ev);
      isDragging = true;
      map.dragging.disable();

      const onMouseMove = (moveEv) => {
        if (!isDragging) return;
        const curB = startBboxRect.getBounds();
        let curW = curB.getWest();
        let curE = curB.getEast();
        let curS = curB.getSouth();
        let curN = curB.getNorth();

        const pLat = moveEv.latlng.lat;
        const pLng = moveEv.latlng.lng;

        if (c.id === "sw") { curS = pLat; curW = pLng; }
        else if (c.id === "nw") { curN = pLat; curW = pLng; }
        else if (c.id === "ne") { curN = pLat; curE = pLng; }
        else if (c.id === "se") { curS = pLat; curE = pLng; }

        // Enforce 0.5 deg max limit per side
        if (Math.abs(curE - curW) <= 0.5 && Math.abs(curN - curS) <= 0.5) {
          const newB = [[Math.min(curS, curN), Math.min(curW, curE)], [Math.max(curS, curN), Math.max(curW, curE)]];
          startBboxRect.setBounds(newB);
          marker.setLatLng(moveEv.latlng);
          updateStartBboxStats();
        }
      };

      const onMouseUp = () => {
        isDragging = false;
        map.dragging.enable();
        map.off("mousemove", onMouseMove);
        map.off("mouseup", onMouseUp);
        // Resync all 4 corner positions
        const finB = startBboxRect.getBounds();
        renderEditableBbox([finB.getWest(), finB.getSouth(), finB.getEast(), finB.getNorth()]);
      };

      map.on("mousemove", onMouseMove);
      map.on("mouseup", onMouseUp);
    });

    startBboxCornerMarkers.push(marker);
  });
}

function updateStartBboxStats() {
  if (!startBboxRect) return;
  const b = startBboxRect.getBounds();
  const latDistKm = Math.abs(b.getNorth() - b.getSouth()) * 111.0;
  const midLat = (b.getNorth() + b.getSouth()) / 2.0;
  const lonDistKm = Math.abs(b.getEast() - b.getWest()) * 111.0 * Math.cos((midLat * Math.PI) / 180.0);
  const areaKm2 = latDistKm * lonDistKm;

  const latSpan = Math.abs(b.getNorth() - b.getSouth());
  const lonSpan = Math.abs(b.getEast() - b.getWest());
  const isOverLimit = latSpan > 0.5 || lonSpan > 0.5;

  const dimsEl = document.getElementById("start-bbox-km-dims");
  const limitEl = document.getElementById("start-bbox-limit-msg");

  if (dimsEl) {
    dimsEl.textContent = `Area: ${lonDistKm.toFixed(1)} × ${latDistKm.toFixed(1)} km (${Math.round(areaKm2)} km²)`;
  }
  if (limitEl) {
    if (isOverLimit) {
      limitEl.textContent = "Exceeds 0.5° maximum limit!";
      limitEl.style.color = "var(--data-destroyed)";
    } else {
      limitEl.textContent = "Within 0.5° limit";
      limitEl.style.color = "var(--text-secondary)";
    }
  }
}

function clearStartBbox() {
  if (startBboxRect) {
    map.removeLayer(startBboxRect);
    startBboxRect = null;
  }
  startBboxCornerMarkers.forEach(m => map.removeLayer(m));
  startBboxCornerMarkers = [];
}

function showStartScreen() {
  isStartScreenActive = true;
  currentRunId = null;
  currentRunData = null;

  // Clear URL run param
  const url = new URL(window.location);
  url.searchParams.delete("run");
  window.history.replaceState({}, "", url);

  // Show Start Screen overlay
  const panel = document.getElementById("start-screen-panel");
  if (panel) panel.classList.remove("hidden");

  // Show full OSM basemap without AOI dimming
  if (aoiDimLayer) { map.removeLayer(aoiDimLayer); aoiDimLayer = null; }
  if (aoiDashedLine) { map.removeLayer(aoiDashedLine); aoiDashedLine = null; }
  Object.keys(geojsonLayers).forEach(k => {
    if (geojsonLayers[k]) {
      map.removeLayer(geojsonLayers[k]);
      geojsonLayers[k] = null;
    }
  });

  // Ensure base OSM tiles are loaded
  if (!baseLayers.osmTiles) {
    baseLayers.osmTiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      pane: "osmTilePane",
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors"
    }).addTo(map);
  }

  // Himalayan / South Asia Regional View (~70–98 E, 5–37 N)
  map.fitBounds([[5, 70], [37, 98]]);

  // Populate Previous assessments
  populatePreviousAssessments();
}

function hideStartScreen() {
  isStartScreenActive = false;
  clearStartBbox();
  const panel = document.getElementById("start-screen-panel");
  if (panel) panel.classList.add("hidden");
}

function populatePreviousAssessments() {
  const listEl = document.getElementById("start-previous-runs-list");
  if (!listEl) return;
  listEl.innerHTML = "";

  if (!allRunsList || allRunsList.length === 0) {
    listEl.innerHTML = '<div class="start-run-meta" style="padding: 6px;">No previous runs found.</div>';
    return;
  }

  allRunsList.forEach(run => {
    const chip = document.createElement("div");
    chip.className = "start-run-chip";
    chip.innerHTML = `
      <span style="font-weight: 500;">${escapeHtml(run.label)}</span>
      <span class="start-run-meta">${escapeHtml(run.event_date || "")}</span>
    `;
    chip.addEventListener("click", () => {
      hideStartScreen();
      loadRun(run.id);
    });
    listEl.appendChild(chip);
  });
}

// ==========================================================================
// Runs Discovery & Switcher
// ==========================================================================
async function loadRunsList() {
  try {
    const res = await fetch("/api/runs?show_all=true");
    allRunsList = await res.json();

    const select = document.getElementById("modal-run-select");
    if (select) {
      select.innerHTML = "";
      allRunsList.forEach(run => {
        const opt = document.createElement("option");
        opt.value = run.id;
        opt.textContent = run.label;
        select.appendChild(opt);
      });
    }

    const urlParams = new URLSearchParams(window.location.search);
    const targetRun = urlParams.get("run");

    if (targetRun && allRunsList.some(r => r.id === targetRun)) {
      hideStartScreen();
      if (select) select.value = targetRun;
      loadRun(targetRun);
    } else {
      // First open without ?run= -> Start screen mode!
      showStartScreen();
    }

  } catch (err) {
    console.error("Failed to load runs:", err);
  }
}

function openRunSwitcherModal() {
  const modal = document.getElementById("run-switcher-modal");
  const select = document.getElementById("modal-run-select");
  if (currentRunId && select) select.value = currentRunId;
  modal.classList.remove("hidden");
}

function initModals() {
  // Run Switcher Modal
  const sModal = document.getElementById("run-switcher-modal");
  document.getElementById("btn-close-switcher-modal").onclick = () => sModal.classList.add("hidden");
  document.getElementById("btn-cancel-switcher").onclick = () => sModal.classList.add("hidden");
  document.getElementById("btn-confirm-switcher").onclick = () => {
    const select = document.getElementById("modal-run-select");
    sModal.classList.add("hidden");
    hideStartScreen();
    loadRun(select.value);
  };

  // New Analysis button returns to Start Screen
  document.getElementById("btn-new-run").onclick = () => {
    showStartScreen();
  };

  const nModal = document.getElementById("new-run-modal");
  const dateInput = document.getElementById("input-event-date");
  const datePreview = document.getElementById("date-format-preview");
  document.getElementById("btn-close-new-modal").onclick = () => nModal.classList.add("hidden");
  document.getElementById("btn-cancel-new-run").onclick = () => nModal.classList.add("hidden");

  // Draw on map interaction
  let isDrawingBbox = false;
  let drawRect = null;
  let startLatLng = null;

  const drawBanner = document.getElementById("draw-bbox-banner");
  const btnDrawBbox = document.getElementById("btn-draw-bbox");
  const btnCancelDraw = document.getElementById("btn-cancel-draw-bbox");

  function stopDrawingBbox() {
    if (!isDrawingBbox) return;
    isDrawingBbox = false;
    map.dragging.enable();
    map.getContainer().style.cursor = "";
    if (drawRect) {
      map.removeLayer(drawRect);
      drawRect = null;
    }
    startLatLng = null;
    drawBanner.classList.add("hidden");
    map.off("mousedown", onDrawStart);
    map.off("mousemove", onDrawMove);
    map.off("mouseup", onDrawEnd);
  }

  function onDrawStart(e) {
    if (!isDrawingBbox) return;
    startLatLng = e.latlng;
    if (drawRect) map.removeLayer(drawRect);
    drawRect = L.rectangle([startLatLng, startLatLng], {
      color: "#B42318",
      weight: 2,
      dashArray: "4, 4",
      fillColor: "#B42318",
      fillOpacity: 0.15
    }).addTo(map);
  }

  function onDrawMove(e) {
    if (!isDrawingBbox || !startLatLng || !drawRect) return;
    drawRect.setBounds(L.latLngBounds(startLatLng, e.latlng));
  }

  function onDrawEnd(e) {
    if (!isDrawingBbox || !startLatLng) return;
    const endLatLng = e.latlng;
    const b = L.latLngBounds(startLatLng, endLatLng);
    document.getElementById("input-bbox-w").value = b.getWest().toFixed(4);
    document.getElementById("input-bbox-s").value = b.getSouth().toFixed(4);
    document.getElementById("input-bbox-e").value = b.getEast().toFixed(4);
    document.getElementById("input-bbox-n").value = b.getNorth().toFixed(4);

    stopDrawingBbox();
    nModal.classList.remove("hidden");
  }

  if (btnDrawBbox) {
    btnDrawBbox.onclick = () => {
      nModal.classList.add("hidden");
      isDrawingBbox = true;
      map.dragging.disable();
      map.getContainer().style.cursor = "crosshair";
      drawBanner.classList.remove("hidden");

      map.on("mousedown", onDrawStart);
      map.on("mousemove", onDrawMove);
      map.on("mouseup", onDrawEnd);
    };
  }

  if (btnCancelDraw) {
    btnCancelDraw.onclick = () => {
      stopDrawingBbox();
      nModal.classList.remove("hidden");
    };
  }

  const form = document.getElementById("new-run-form");
  form.onsubmit = async (e) => {
    e.preventDefault();
    const eventName = document.getElementById("input-event-name").value.trim();
    const eventDate = document.getElementById("input-event-date").value.trim();
    const w = parseFloat(document.getElementById("input-bbox-w").value);
    const s = parseFloat(document.getElementById("input-bbox-s").value);
    const eLon = parseFloat(document.getElementById("input-bbox-e").value);
    const n = parseFloat(document.getElementById("input-bbox-n").value);
    const errBox = document.getElementById("new-run-error");

    try {
      const resp = await fetch("/api/runs/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bbox: [w, s, eLon, n],
          event_date: eventDate,
          event_name: eventName || null
        })
      });
      if (!resp.ok) {
        const d = await resp.json();
        throw new Error(d.detail || "Failed to start run");
      }
      const data = await resp.json();
      nModal.classList.add("hidden");
      await loadRunsList();
      loadRun(data.run_id);
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.remove("hidden");
    }
  };
}

// ==========================================================================
// Load Specific Run
// ==========================================================================
async function loadRun(runId) {
  hideStartScreen();
  if (currentRunId === runId && currentRunData) return;
  currentRunId = runId;

  const url = new URL(window.location);
  url.searchParams.set("run", runId);
  window.history.replaceState({}, "", url);

  const spinner = document.getElementById("map-spinner");
  spinner.classList.remove("hidden");

  if (s2OverlayActive) toggleS2Slider(false);

  try {
    const res = await fetch(`/api/runs/${runId}`);
    const data = await res.json();
    currentRunData = data;

    // 1. Update Header
    updateHeader(data);

    // 2. Update Side Panel
    updateSidePanel(data);

    // Reset Copilot assistant for this run
    resetCopilotForNewRun(data);

    // If run is FAILED or has error, show the failed run banner
    const failBanner = document.getElementById("run-failed-banner");
    const failErrorText = document.getElementById("run-failed-error-text");
    const failLogsPre = document.getElementById("run-failed-logs-content");
    const failDetails = document.getElementById("run-failed-logs-details");

    if (data.status === "FAILED" || data.error) {
      if (failBanner) {
        failBanner.classList.remove("hidden");
        failErrorText.textContent = data.error || "The pipeline process terminated prematurely.";
        if (data.last_log_lines && data.last_log_lines.length > 0) {
          failLogsPre.textContent = data.last_log_lines.join("\n");
          failDetails.classList.remove("hidden");
        } else {
          failDetails.classList.add("hidden");
        }
      }
    } else {
      if (failBanner) failBanner.classList.add("hidden");
    }

    // 3. Clear existing layers
    Object.keys(geojsonLayers).forEach(k => {
      if (geojsonLayers[k]) {
        map.removeLayer(geojsonLayers[k]);
        geojsonLayers[k] = null;
      }
    });

    if (data.status === "FAILED") {
      // Just fit map to bbox if available
      if (data.bbox && data.bbox.length === 4) {
        map.fitBounds([[data.bbox[1], data.bbox[0]], [data.bbox[3], data.bbox[2]]]);
      }
      return;
    }

    // 4. Concurrently load basemap, AOI dim mask, and vector layers
    const promises = [
      setupBasemap(runId, data),
      setupAoiDimMask(data)
    ];

    if (data.layers_available && data.layers_available.hazards) promises.push(loadHazardsLayer(runId));
    if (data.layers_available && data.layers_available.roads) promises.push(loadRoadsLayer(runId));
    if (data.layers_available && data.layers_available.bridges) promises.push(loadBridgesLayer(runId));
    if (data.layers_available && data.layers_available.buildings) promises.push(loadBuildingsLayer(runId));
    if (data.layers_available && data.layers_available.settlements) promises.push(loadSettlementsLayer(runId));
    if (data.layers_available && data.layers_available.repair_packages) promises.push(loadRepairPackagesLayer(runId));

    await Promise.all(promises);

    // 5. Fit to damaged area on load
    zoomToDamagedArea(data);

  } catch (err) {
    console.error("Error loading run details:", err);
  } finally {
    spinner.classList.add("hidden");
    setTimeout(() => map.invalidateSize(), 150);
  }
}

// ==========================================================================
// Header Updating (Item 3)
// ==========================================================================
function updateHeader(data) {
  const mainTitleEl = document.getElementById("run-main-title");
  const subtitleEl = document.getElementById("header-subtitle-sentence");
  const valPillEl = document.getElementById("val-header-validation");

  mainTitleEl.textContent = data.main_title || data.label || "Disaster Assessment";

  // Subtitle sentence: "<river/place>, <date>. <Mountain/Flat> terrain."
  const placeOrRiver = data.primary_river || data.primary_place || (data.osm_label ? data.osm_label.split("—")[0].trim() : "Primary Corridor");
  const regimeStr = data.regime === "flat_floodplain" ? "Flat terrain" : "Mountain terrain";
  subtitleEl.textContent = `${placeOrRiver}, ${data.event_date}. ${regimeStr}.`;

  // Validation Pill: Only Trishuli (EMSR927) is validated; all others are practice runs
  const valStatus = data.validation_status || "not validated against an official map (practice run)";
  if (valStatus.includes("EMSR927")) {
    valPillEl.textContent = "Validated against Copernicus EMSR927";
    valPillEl.className = "badge-validation verified";
  } else {
    valPillEl.textContent = "Not validated (practice run)";
    valPillEl.className = "badge-validation";
  }

  // Dynamic Year Attribution in Footer
  const attrSentinel = document.getElementById("attr-sentinel");
  const year = data.event_year || (data.event_date ? data.event_date.split("-")[0] : "2026");
  attrSentinel.textContent = `Contains modified Copernicus Sentinel data ${year}.`;
}

// ==========================================================================
// Dimmed AOI Mask (Item 4)
// ==========================================================================
function setupAoiDimMask(data) {
  if (aoiDimLayer) { map.removeLayer(aoiDimLayer); aoiDimLayer = null; }
  if (aoiDashedLine) { map.removeLayer(aoiDashedLine); aoiDashedLine = null; }

  if (!data.bbox || data.bbox.length !== 4) return;
  const [w, s, e, n] = data.bbox;

  // Inverted polygon covering world with hole for AOI bbox
  const worldRing = [
    [-90, -180],
    [-90, 180],
    [90, 180],
    [90, -180],
    [-90, -180]
  ];
  const aoiHole = [
    [s, w],
    [n, w],
    [n, e],
    [s, e],
    [s, w]
  ];

  aoiDimLayer = L.polygon([worldRing, aoiHole], {
    pane: "aoiDimPane",
    fillColor: "#FFFFFF",
    fillOpacity: 0.55,
    stroke: false,
    interactive: false
  }).addTo(map);

  // Dashed outline of AOI
  aoiDashedLine = L.rectangle([[s, w], [n, e]], {
    pane: "aoiDimPane",
    color: "#6B747A",
    weight: 1.5,
    dashArray: "4, 4",
    fill: false,
    interactive: false
  }).addTo(map);
}

// ==========================================================================
// Basemap Architecture (Items 1-4)
// Standard OSM Raster Tiles + DEM Hillshade Multiply Overlay + Offline Fallback
// ==========================================================================
async function setupBasemap(runId, data) {
  // Clear any existing basemap layers
  if (baseLayers.osmTiles) {
    map.removeLayer(baseLayers.osmTiles);
    baseLayers.osmTiles = null;
  }
  if (baseLayers.hillshadeTiles) {
    map.removeLayer(baseLayers.hillshadeTiles);
    baseLayers.hillshadeTiles = null;
  }
  if (baseLayers.offlineGroup) {
    map.removeLayer(baseLayers.offlineGroup);
    baseLayers.offlineGroup.clearLayers();
  }

  // Remove hard bounds or minZoom restrictions so normal panning is allowed
  map.setMaxBounds(null);
  map.setMinZoom(0);

  isOfflineFallbackActive = false;
  const offlineBanner = document.getElementById("offline-basemap-notice");
  if (offlineBanner) offlineBanner.classList.add("hidden");

  // 1. OpenStreetMap Standard Raster Tiles
  // Muted via CSS filter on pane 'osmTilePane'
  let tileErrorCount = 0;
  baseLayers.osmTiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    pane: "osmTilePane",
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors"
  });

  baseLayers.osmTiles.on("tileerror", () => {
    tileErrorCount++;
    // If consecutive tile errors occur, trigger offline fallback
    if (tileErrorCount >= 2 && !isOfflineFallbackActive) {
      console.warn("OSM tile error detected. Activating offline basemap fallback...");
      activateOfflineFallback(runId);
    }
  });

  baseLayers.osmTiles.addTo(map);

  // 2. Terrain Overlay: DEM Hillshade XYZ Tiles (z=9-14)
  // Plain opacity ~0.25 (no mix-blend-mode) over the OSM base in pane 'hillshadePane'
  baseLayers.hillshadeTiles = L.tileLayer(`/api/runs/${runId}/basemap/tiles/{z}/{x}/{y}.png`, {
    pane: "hillshadePane",
    minZoom: 9,
    maxZoom: 14,
    opacity: 0.25,
    tileSize: 256
  });
  baseLayers.hillshadeTiles.addTo(map);
}

// Offline fallback: activates DEM full hillshade + local OSM waterways & place labels
async function activateOfflineFallback(runId) {
  if (isOfflineFallbackActive) return;
  isOfflineFallbackActive = true;

  const offlineBanner = document.getElementById("offline-basemap-notice");
  if (offlineBanner) offlineBanner.classList.remove("hidden");

  // If live tiles were added, remove them
  if (baseLayers.osmTiles && map.hasLayer(baseLayers.osmTiles)) {
    map.removeLayer(baseLayers.osmTiles);
  }
  if (baseLayers.hillshadeTiles && map.hasLayer(baseLayers.hillshadeTiles)) {
    map.removeLayer(baseLayers.hillshadeTiles);
  }

  baseLayers.offlineGroup.clearLayers();

  // Load cached offline DEM relief hillshade PNG
  try {
    const metaResp = await fetch(`/api/runs/${runId}/basemap/meta`);
    if (metaResp.ok) {
      const meta = await metaResp.json();
      if (meta.bounds) {
        const hillshade = L.imageOverlay(`/api/runs/${runId}/basemap/hillshade`, meta.bounds, {
          opacity: 1.0,
          interactive: false,
          pane: "basemapImagePane"
        });
        baseLayers.offlineGroup.addLayer(hillshade);
      }
    }
  } catch (e) {
    console.warn("Could not load offline hillshade:", e);
  }

  // Load local OSM waterways
  try {
    const riverResp = await fetch(`/api/runs/${runId}/basemap/waterways`);
    if (riverResp.ok) {
      const riverGeo = await riverResp.json();
      const riverLayer = L.geoJSON(riverGeo, {
        pane: "basemapVectorPane",
        style: {
          color: "#8DAFD0",
          weight: 1.2,
          opacity: 0.8
        },
        interactive: false
      });
      baseLayers.offlineGroup.addLayer(riverLayer);
    }
  } catch (e) {
    console.warn("Could not load offline waterways:", e);
  }

  // Load local OSM places
  try {
    const placesResp = await fetch(`/api/runs/${runId}/basemap/places`);
    if (placesResp.ok) {
      const placesGeo = await placesResp.json();
      const features = placesGeo.features || [];
      const validPlaces = [];
      const seen = new Set();
      features.forEach(f => {
        const p = f.properties || {};
        const rawName = p["name:en"] || p.name || "";
        const clean = rawName.split("(")[0].split(",")[0].trim();
        if (!clean || clean === "Village" || clean === "Hamlet" || clean.startsWith("Place node") || clean.startsWith("Cluster")) return;
        if (seen.has(clean)) return;
        seen.add(clean);
        validPlaces.push(f);
      });

      const selected = validPlaces.slice(0, 15);
      const placesLayer = L.geoJSON({ type: "FeatureCollection", features: selected }, {
        pane: "basemapVectorPane",
        pointToLayer: (feat, latlng) => {
          const props = feat.properties || {};
          const devName = props["name:ne"] || props["name:Deva"] || "";
          const latName = props["name:en"] || props.name || "";

          let html = "";
          if (latName && devName && latName !== devName) {
            html = `<div class="osm-place-label"><span class="place-lat">${latName}</span><span class="place-dev">${devName}</span></div>`;
          } else {
            html = `<div class="osm-place-label"><span class="place-lat">${latName || devName}</span></div>`;
          }

          return L.marker(latlng, {
            icon: L.divIcon({
              className: "osm-place-div",
              html: html,
              iconSize: null
            }),
            interactive: false
          });
        }
      });
      baseLayers.offlineGroup.addLayer(placesLayer);
    }
  } catch (e) {
    console.warn("Could not load offline places:", e);
  }

  baseLayers.offlineGroup.addTo(map);
}

// ==========================================================================
// Zoom to Damaged Area on Load (Item 4)
// ==========================================================================
function zoomToDamagedArea(data) {
  const damagedGroup = L.featureGroup();

  if (geojsonLayers.hazards) {
    geojsonLayers.hazards.eachLayer(l => {
      const cls = l.feature.properties.class || l.feature.properties.hazard_class;
      if (cls === 2 || cls === 3) damagedGroup.addLayer(l);
    });
  }

  if (geojsonLayers.buildings) {
    geojsonLayers.buildings.eachLayer(l => {
      const g = l.feature.properties.damage_grade;
      if (g && g !== "Not affected" && !g.includes("cloud")) damagedGroup.addLayer(l);
    });
  }

  if (geojsonLayers.roads) {
    geojsonLayers.roads.eachLayer(l => {
      const g = l.feature.properties.damage_grade;
      if (g === "Destroyed" || g === "Possibly damaged" || g === "Flooded / impassable") damagedGroup.addLayer(l);
    });
  }

  // Fit to damaged area or AOI, occupying ~85% of viewport (padding ~8% on each side)
  const mapSize = map.getSize();
  const padX = Math.round(mapSize.x * 0.08);
  const padY = Math.round(mapSize.y * 0.08);

  if (damagedGroup.getLayers().length > 0) {
    map.fitBounds(damagedGroup.getBounds(), { padding: [padY, padX], maxZoom: 15 });
  } else if (data.bbox && data.bbox.length === 4) {
    const [w, s, e, n] = data.bbox;
    map.fitBounds([[s, w], [n, e]], { padding: [padY, padX], maxZoom: 14 });
  }

  // Update status ribbon coordinates to current center
  const center = map.getCenter();
  const latDir = center.lat >= 0 ? "N" : "S";
  const lngDir = center.lng >= 0 ? "E" : "W";
  const el = document.getElementById("status-cursor-coords");
  if (el) {
    el.textContent = `${Math.abs(center.lat).toFixed(4)}° ${latDir}, ${Math.abs(center.lng).toFixed(4)}° ${lngDir}`;
  }
}

// ==========================================================================
// Side Panel Updates (Item 5)
// ==========================================================================
function updateSidePanel(data) {
  const m = data.metrics || {};
  const b = m.buildings || {};
  const br = m.bridges || {};
  const r = m.roads_km || {};
  const cuts = m.cutoffs || {};
  const areas = m.areas || {};
  const isFlat = data.regime === "flat_floodplain";

  const scenKey = currentScenario === "optimistic" ? "optimistic" : "pessimistic";
  const vehCut = cuts[`vehicle_${scenKey}`] !== undefined ? cuts[`vehicle_${scenKey}`] : (cuts.vehicle_optimistic || 0);
  const noGround = cuts[`no_ground_access_${scenKey}`] !== undefined ? cuts[`no_ground_access_${scenKey}`] : (cuts.no_ground_access_optimistic || 0);

  // (a) One data-only sentence, 15px
  const summaryBox = document.getElementById("summary-sentence-box");
  const riverName = data.primary_river;
  const riverClause = riverName ? ` along ${riverName}` : "";

  let bldWord = isFlat ? "buildings flooded" : "buildings destroyed";
  let bldCount = isFlat ? (b.flooded || b.total_affected || 0) : (b.destroyed || 0);
  let brWord = isFlat ? "bridges flooded / impassable" : "bridges destroyed";
  let brCount = isFlat ? (br.flooded || 0) : (br.destroyed || 0);

  summaryBox.textContent = `${bldCount} ${bldWord}, ${brCount} ${brWord} and ${vehCut} settlements cut off by road${riverClause}. ${noGround} settlements have no ground access.`;

  // (b) Exactly 4 Cards in 2x2 Grid (28px semibold tabular + small label + same symbol)
  document.getElementById("kpi-val-buildings").textContent = bldCount;
  document.getElementById("kpi-lbl-buildings").textContent = isFlat ? "Buildings flooded" : "Buildings destroyed";

  document.getElementById("kpi-val-bridges").textContent = brCount;
  document.getElementById("kpi-lbl-bridges").textContent = isFlat ? "Bridges flooded" : "Bridges destroyed";

  document.getElementById("kpi-val-settlements").textContent = vehCut;
  document.getElementById("kpi-val-no-ground").textContent = noGround;
  document.getElementById("kpi-lbl-no-ground").textContent = isFlat ? "No ground access (boat/air)" : "No ground access (air only)";

  // Update KPI and Legend Symbology for flat vs mountain runs
  const symKpiBld = document.getElementById("sym-kpi-buildings");
  if (symKpiBld) symKpiBld.className = isFlat ? "sym-flooded-circle" : "sym-destroyed-circle";
  const symKpiBr = document.getElementById("sym-kpi-bridges");
  if (symKpiBr) symKpiBr.className = isFlat ? "sym-flooded-diamond" : "sym-destroyed-diamond";

  const symLegObs = document.getElementById("sym-legend-obs");
  if (symLegObs) symLegObs.className = isFlat ? "sym-flood-obs-box" : "sym-obs-box";
  const lblLegObs = document.getElementById("lbl-legend-obs");
  if (lblLegObs) lblLegObs.textContent = isFlat ? "Flood water (observed)" : "Observed damage";

  const symLegBld = document.getElementById("sym-legend-buildings");
  if (symLegBld) symLegBld.className = isFlat ? "sym-flooded-circle" : "sym-destroyed-circle";
  const symLegBr = document.getElementById("sym-legend-bridges");
  if (symLegBr) symLegBr.className = isFlat ? "sym-flooded-diamond" : "sym-destroyed-diamond";
  const symLegR = document.getElementById("sym-legend-roads");
  if (symLegR) symLegR.className = isFlat ? "sym-flooded-line" : "sym-destroyed-line";

  // Update Legend Labels & Stats (7 standard rows)
  document.getElementById("legend-stat-obs").textContent = `${(areas.observed_km2 !== undefined ? areas.observed_km2.toFixed(2) : "0.00")} km²`;
  document.getElementById("legend-stat-inf").textContent = `${(areas.inferred_km2 !== undefined ? areas.inferred_km2.toFixed(2) : "0.00")} km²`;
  document.getElementById("legend-stat-buildings").textContent = bldCount;
  document.getElementById("legend-stat-bridges").textContent = brCount;
  document.getElementById("legend-stat-roads").textContent = `${(r.destroyed_km !== undefined ? r.destroyed_km.toFixed(1) : "0.0")} km`;
  document.getElementById("legend-stat-cutoff-road").textContent = vehCut;
  document.getElementById("legend-stat-no-ground").textContent = noGround;

  document.getElementById("lbl-legend-buildings").textContent = isFlat ? "Buildings flooded" : "Buildings destroyed";
  document.getElementById("lbl-legend-bridges").textContent = isFlat ? "Bridges flooded" : "Bridges destroyed";
  document.getElementById("lbl-legend-roads").textContent = isFlat ? "Roads impassable" : "Roads destroyed";

  // TAB 1: IMPACT
  // Buildings: flat runs use Flooded, Possibly flooded; no "Damaged" row; no "Flooded / impassable" for buildings
  document.getElementById("val-b-destroyed").textContent = (isFlat ? (b.flooded || b.total_affected || 0) : (b.destroyed || 0)).toLocaleString();
  document.getElementById("lbl-row-b-destroyed").textContent = isFlat ? "Flooded" : "Destroyed";
  const dotBDest = document.getElementById("dot-b-destroyed");
  if (dotBDest) dotBDest.className = isFlat ? "dot-color flooded" : "dot-color destroyed";

  const rowBDamaged = document.getElementById("row-b-damaged");
  if (rowBDamaged) {
    if (isFlat) rowBDamaged.classList.add("hidden");
    else rowBDamaged.classList.remove("hidden");
  }
  document.getElementById("val-b-damaged").textContent = (b.damaged || 0).toLocaleString();

  document.getElementById("val-b-possible").textContent = (isFlat ? (b.possibly_flooded || 0) : (b.possibly_damaged || 0)).toLocaleString();
  document.getElementById("lbl-row-b-possible").textContent = isFlat ? "Possibly flooded" : "Possibly damaged";
  document.getElementById("val-b-total").textContent = (b.total_affected || 0).toLocaleString();
  document.getElementById("val-b-unverified").textContent = (b.unverified || 0).toLocaleString();

  // Bridges & Roads: flat runs use "Flooded / impassable" and "Possibly flooded"
  document.getElementById("val-br-destroyed").textContent = (isFlat ? (br.flooded || 0) : (br.destroyed || 0)).toLocaleString();
  document.getElementById("lbl-row-br-destroyed").textContent = isFlat ? "Flooded / impassable" : "Destroyed";
  const dotBrDest = document.getElementById("dot-br-destroyed");
  if (dotBrDest) dotBrDest.className = isFlat ? "dot-color flooded" : "dot-color destroyed";

  document.getElementById("val-br-possible").textContent = (isFlat ? (br.possibly_flooded || 0) : (br.possibly_damaged || 0)).toLocaleString();
  document.getElementById("lbl-row-br-possible").textContent = isFlat ? "Possibly flooded" : "Possibly damaged";
  document.getElementById("val-br-total").textContent = (br.total_assessed || 27).toLocaleString();

  document.getElementById("val-r-destroyed").textContent = `${(r.destroyed_km !== undefined ? r.destroyed_km.toFixed(1) : "0.0")} km`;
  document.getElementById("lbl-row-r-destroyed").textContent = isFlat ? "Flooded / impassable" : "Destroyed";
  const dotRDest = document.getElementById("dot-r-destroyed");
  if (dotRDest) dotRDest.className = isFlat ? "dot-color flooded" : "dot-color destroyed";

  document.getElementById("val-r-possible").textContent = `${(r.possibly_damaged_km !== undefined ? r.possibly_damaged_km.toFixed(1) : "0.0")} km`;
  document.getElementById("lbl-row-r-possible").textContent = isFlat ? "Possibly flooded" : "Possibly damaged";
  document.getElementById("val-r-unverified").textContent = `${(r.unverified_km !== undefined ? r.unverified_km.toFixed(1) : "0.0")} km`;

  document.getElementById("val-area-obs").textContent = `${(areas.observed_km2 !== undefined ? areas.observed_km2.toFixed(2) : "0.00")} km²`;
  document.getElementById("val-area-inf").textContent = `${(areas.inferred_km2 !== undefined ? areas.inferred_km2.toFixed(2) : "0.00")} km²`;

  const imgSummary = data.image_dates_summary || "";
  const preDates = imgSummary.includes("Pre:") ? imgSummary.split("Pre:")[1].split("|")[0].trim() : "—";
  const postDates = imgSummary.includes("Post:") ? imgSummary.split("Post:")[1].trim() : "—";
  const opticalNote = data.optical_evidence_note ? ` (${data.optical_evidence_note})` : "";
  document.getElementById("val-img-before").textContent = preDates;
  document.getElementById("val-img-after").textContent = `${postDates}${opticalNote}`;

  // TAB 3: REPAIR
  const rp = m.repair_package_1 || {};
  const allPkgs = m.repair_packages_all || [];
  const rHeadline = document.getElementById("repair-pkg-headline");
  const rSub = document.getElementById("repair-pkg-sub");
  const rIds = document.getElementById("repair-pkg-osm-ids");
  const rIntro = document.getElementById("repair-intro-sentence");
  const rOtherList = document.getElementById("repair-other-pkgs");

  const cutPess = m.cutoffs ? (m.cutoffs.vehicle_pessimistic || 0) : 0;
  if (rIntro) {
    rIntro.textContent = `Priority road and bridge links to restore vehicle and emergency access. Computed for the pessimistic scenario: ${cutPess} settlements cut off.`;
  }

  if (rp.has_actionable_package && rp.element_count > 0) {
    const elemWord = rp.element_count === 1 ? "1 element" : `${rp.element_count} elements`;
    const settleWord = rp.reconnects_settlements === 1 ? "1 settlement" : `${rp.reconnects_settlements} settlements`;
    rHeadline.textContent = `Reconnects ${settleWord} and ${rp.reconnects_buildings} buildings`;
    rSub.textContent = `${elemWord} prioritized for restoration`;
    rIds.textContent = rp.elements.join(", ");
  } else {
    rHeadline.textContent = "No actionable road repair package";
    rSub.textContent = "0 elements";
    rIds.textContent = "No specific road links required";
  }

  // Render subsequent actionable packages (Package 2, Package 3, etc.)
  if (rOtherList) {
    rOtherList.innerHTML = "";
    if (allPkgs.length > 1) {
      allPkgs.slice(1, 5).forEach((pkg, idx) => {
        const pkgNum = idx + 2;
        const eWord = pkg.element_count === 1 ? "1 element" : `${pkg.element_count} elements`;
        const sWord = pkg.reconnects_settlements === 1 ? "1 settlement" : `${pkg.reconnects_settlements} settlements`;
        const row = document.createElement("div");
        row.className = "plain-row";
        row.innerHTML = `
          <div class="plain-row-left"><span>Package ${pkgNum}</span></div>
          <div class="plain-row-val font-mono">Reconnects ${sWord} / ${pkg.reconnects_buildings} buildings (${eWord})</div>
        `;
        rOtherList.appendChild(row);
      });
    }
  }

  // TAB 4: CONFIDENCE
  const valMetrics = m.validation_metrics;
  const confMetricsContainer = document.getElementById("conf-metrics-container");
  const confUnvalidatedNotice = document.getElementById("conf-unvalidated-notice");
  const confFlatNotice = document.getElementById("conf-flat-notice");

  if (valMetrics && data.validation_status.includes("EMSR927")) {
    confMetricsContainer.classList.remove("hidden");
    confUnvalidatedNotice.classList.add("hidden");
    if (confFlatNotice) confFlatNotice.classList.add("hidden");
    document.getElementById("m-val-prec").textContent = valMetrics.precision !== undefined ? valMetrics.precision.toFixed(2) : "—";
    document.getElementById("m-val-rec").textContent = valMetrics.recall !== undefined ? valMetrics.recall.toFixed(2) : "—";
    document.getElementById("m-val-f1").textContent = valMetrics.f1 !== undefined ? valMetrics.f1.toFixed(2) : "—";
    document.getElementById("m-val-iou").textContent = valMetrics.iou !== undefined ? valMetrics.iou.toFixed(2) : "—";
  } else {
    confMetricsContainer.classList.add("hidden");
    if (isFlat) {
      confUnvalidatedNotice.classList.add("hidden");
      if (confFlatNotice) confFlatNotice.classList.remove("hidden");
    } else {
      confUnvalidatedNotice.classList.remove("hidden");
      if (confFlatNotice) confFlatNotice.classList.add("hidden");
    }
  }

  document.getElementById("conf-cloud-b").textContent = (b.unverified || 0).toLocaleString();
  document.getElementById("conf-cloud-br").textContent = (br.unverified || 0).toLocaleString();
  document.getElementById("conf-cloud-r").textContent = `${(r.unverified_km !== undefined ? r.unverified_km.toFixed(1) : "0.0")} km`;

  const confOsmDateEl = document.getElementById("conf-osm-snapshot-date");
  if (confOsmDateEl) {
    confOsmDateEl.textContent = data.osm_snapshot_date || data.event_date || "2026-08-26";
  }

  // Refresh Access list
  updateAccessList();
}

// ==========================================================================
// Tab 2: Access List Rendering
// ==========================================================================
function updateAccessList() {
  if (!geojsonLayers.settlements || !currentRunData) return;

  const m = currentRunData.metrics || {};
  const cuts = m.cutoffs || {};
  const isFlat = currentRunData.regime === "flat_floodplain";
  const scenKey = currentScenario === "optimistic" ? "opt" : "pess";

  const noGroundContainer = document.getElementById("list-no-ground-items");
  const roadCutTop5Container = document.getElementById("list-road-cut-top5");
  const roadCutRemainingContainer = document.getElementById("list-road-cut-remaining");
  const btnShowOther = document.getElementById("btn-show-other-settlements");

  noGroundContainer.innerHTML = "";
  roadCutTop5Container.innerHTML = "";
  roadCutRemainingContainer.innerHTML = "";

  const allSettlements = [];
  geojsonLayers.settlements.eachLayer(l => {
    allSettlements.push(l.feature);
  });

  const noGroundItems = [];
  const roadCutItems = [];

  allSettlements.forEach(feat => {
    const p = feat.properties;
    const vCut = p[`vehicle_status_${scenKey}`] === "cut_off";
    const wCut = p[`walking_status_${scenKey}`] === "cut_off";

    if (vCut && wCut) {
      noGroundItems.push(feat);
    } else if (currentMode === "vehicle" ? vCut : wCut) {
      roadCutItems.push(feat);
    }
  });

  // Sort descending by building count
  noGroundItems.sort((a, b) => (b.properties.building_count || 0) - (a.properties.building_count || 0));
  roadCutItems.sort((a, b) => (b.properties.building_count || 0) - (a.properties.building_count || 0));

  // Update Section Titles
  const noGroundLabel = isFlat ? "No ground access: boat or helicopter" : "No ground access: air drop or helicopter";
  document.getElementById("title-no-ground-list").textContent = `${noGroundLabel} (${noGroundItems.length})`;
  document.getElementById("title-road-cut-list").textContent = `Cut off by road (${roadCutItems.length})`;

  // Render No Ground Items
  noGroundItems.forEach(feat => {
    const el = createSettlementRow(feat, true);
    noGroundContainer.appendChild(el);
  });

  // Render Road Cut Items (Top 5 + remaining)
  const top5 = roadCutItems.slice(0, 5);
  const remaining = roadCutItems.slice(5);

  top5.forEach(feat => {
    const el = createSettlementRow(feat, false);
    roadCutTop5Container.appendChild(el);
  });

  if (remaining.length > 0) {
    btnShowOther.classList.remove("hidden");
    btnShowOther.textContent = `Show the other ${remaining.length}`;
    remaining.forEach(feat => {
      const el = createSettlementRow(feat, false);
      roadCutRemainingContainer.appendChild(el);
    });
  } else {
    btnShowOther.classList.add("hidden");
  }

  // Update Grey Note Box
  const rCloud = currentRunData.metrics.roads_km.unverified_km || 0;
  document.getElementById("access-cloud-note").textContent =
    `23 other settlements look connected, but only through roads under cloud (${rCloud} km obscured). They are not counted as cut off.`;
}

function createSettlementRow(feat, isNoGround) {
  const p = feat.properties;
  const coords = feat.geometry.coordinates;
  const lat = coords[1];
  const lon = coords[0];
  const bldCount = p.building_count || 0;

  let displayName = p.name || "Settlement";
  if (p.nearest_named_place && p.dist_to_named_place_km !== undefined) {
    displayName = `Near ${p.nearest_named_place} (${p.dist_to_named_place_km.toFixed(1)} km)`;
  } else if (displayName.includes("nearest named place: ")) {
    displayName = `Near ${displayName.split("nearest named place: ")[1].replace(")", "")}`;
  }

  const row = document.createElement("div");
  row.className = "settlement-row-item";
  const symHtml = isNoGround ? `<span class="sym-no-ground"></span>` : `<span class="sym-cutoff-road"></span>`;

  row.innerHTML = `
    <div class="settlement-row-left">
      ${symHtml}
      <div class="settlement-name-block">
        <span class="settlement-name-text">${displayName}</span>
        <span class="settlement-coords-mono font-mono">${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E</span>
      </div>
    </div>
    <div class="settlement-row-right font-mono">${bldCount} buildings</div>
  `;

  // Hover highlighting bidirectionally
  row.addEventListener("mouseenter", () => {
    highlightSettlementMarker(feat, true);
  });
  row.addEventListener("mouseleave", () => {
    highlightSettlementMarker(feat, false);
  });
  row.addEventListener("click", () => {
    map.setView([lat, lon], 15);
    openSettlementPopup(feat);
  });

  return row;
}

function highlightSettlementMarker(feat, highlight) {
  if (!geojsonLayers.settlements) return;
  geojsonLayers.settlements.eachLayer(l => {
    if (l.feature === feat) {
      if (highlight) {
        l.setStyle({ radius: 9, weight: 3, color: "#1B2326" });
        l.bringToFront();
      } else {
        l.setStyle(getSettlementMarkerStyle(feat.properties));
      }
    }
  });
}

function openSettlementPopup(feat) {
  geojsonLayers.settlements.eachLayer(l => {
    if (l.feature === feat) {
      l.openPopup();
    }
  });
}

// ==========================================================================
// Layers Loading & Styling (Item 2)
// ==========================================================================
async function loadHazardsLayer(runId) {
  try {
    const res = await fetch(`/api/runs/${runId}/layer/hazards?simplify_tol=0.0001`);
    const geojson = await res.json();
    const isFlat = currentRunData && currentRunData.regime === "flat_floodplain";

    geojsonLayers.hazards = L.geoJSON(geojson, {
      style: (feature) => {
        const cls = feature.properties.class || feature.properties.hazard_class;
        if (cls === 1) {
          return { color: "#6B8BAA", fillColor: "#8DAFD0", fillOpacity: 0.6, weight: 1 };
        } else if (cls === 2) {
          if (isFlat) {
            // Flat flood extent: BLUE (fill #2F6DB5 at 45%, outline #1F5FA8)
            return { color: "#1F5FA8", fillColor: "#2F6DB5", fillOpacity: 0.45, weight: 1.5 };
          }
          // Observed damage: #D9534A fill 55% + #B42318 outline
          return { color: "#B42318", fillColor: "rgba(217, 83, 74, 0.55)", fillOpacity: 0.55, weight: 1.5 };
        } else if (cls === 3) {
          // Inferred hazard: orange diagonal hatch styling (#C2570C on #F3D3B8)
          return { color: "#C2570C", fillColor: "#F3D3B8", fillOpacity: 0.55, weight: 1.5, dashArray: "3, 3" };
        }
        return { color: "#8A949A", fillOpacity: 0.2, weight: 1 };
      }
    });

    if (document.getElementById("layer-haz-obs").checked) {
      geojsonLayers.hazards.addTo(map);
    }
  } catch (err) {
    console.error("Error loading hazards:", err);
  }
}

async function loadBuildingsLayer(runId) {
  try {
    const showIntact = document.getElementById("layer-intact-buildings").checked;
    const url = showIntact
      ? `/api/runs/${runId}/layer/buildings`
      : `/api/runs/${runId}/layer/buildings?affected_only=true`;
    const res = await fetch(url);
    const geojson = await res.json();
    const isFlat = currentRunData && currentRunData.regime === "flat_floodplain";

    if (geojsonLayers.buildings && map.hasLayer(geojsonLayers.buildings)) {
      map.removeLayer(geojsonLayers.buildings);
    }

    geojsonLayers.buildings = L.geoJSON(geojson, {
      filter: (feature) => {
        const grade = feature.properties.damage_grade || "Not affected";
        if (grade === "Not affected" && !showIntact) return false;
        return true;
      },
      style: (feature) => {
        const grade = feature.properties.damage_grade || "Not affected";
        if (grade === "Flooded" || (isFlat && (grade === "Destroyed" || grade === "Flooded / impassable"))) {
          return { color: "#1F5FA8", fillColor: "#2F6DB5", fillOpacity: 0.9, weight: 1.5 };
        } else if (grade === "Destroyed" || grade === "Flooded / impassable") {
          return { color: "#B42318", fillColor: "#B42318", fillOpacity: 0.9, weight: 1.5 };
        } else if (grade === "Damaged") {
          return { color: "#C2570C", fillColor: "#C2570C", fillOpacity: 0.85, weight: 1.5 };
        } else if (grade === "Possibly damaged" || grade === "Possibly flooded") {
          return { color: "#E0A31C", fillColor: "#E0A31C", fillOpacity: 0.85, weight: 1.5 };
        }
        return { color: "#B6C0C4", fillColor: "#DCE1DF", fillOpacity: 0.4, weight: 0.8 };
      },
      pointToLayer: (feature, latlng) => {
        const grade = feature.properties.damage_grade || "Not affected";
        let color = "#B6C0C4";
        let r = 3;
        if (grade === "Flooded" || (isFlat && (grade === "Destroyed" || grade === "Flooded / impassable"))) {
          color = "#2F6DB5";
          r = 5.5;
        } else if (grade === "Destroyed" || grade === "Flooded / impassable") {
          color = "#B42318";
          r = 5.5;
        } else if (grade === "Damaged") {
          color = "#C2570C";
          r = 4.5;
        } else if (grade === "Possibly damaged" || grade === "Possibly flooded") {
          color = "#E0A31C";
          r = 4;
        }

        return L.circleMarker(latlng, {
          radius: r,
          fillColor: color,
          color: "#FFFFFF",
          weight: 1,
          opacity: 1,
          fillOpacity: 0.9
        });
      }
    });

    if (document.getElementById("layer-buildings").checked) {
      geojsonLayers.buildings.addTo(map);
    }
  } catch (err) {
    console.error("Error loading buildings:", err);
  }
}

async function loadRoadsLayer(runId) {
  try {
    const res = await fetch(`/api/runs/${runId}/layer/roads?affected_only=true&simplify_tol=0.0001`);
    const geojson = await res.json();

    geojsonLayers.roads = L.geoJSON(geojson, {
      style: (feature) => {
        const grade = feature.properties.damage_grade || "Not affected";
        if (grade === "Destroyed" || grade === "Flooded / impassable") {
          return { color: "#B42318", weight: 3.5, opacity: 1.0 };
        } else if (grade === "Possibly damaged" || grade === "Possibly flooded") {
          return { color: "#C2570C", weight: 2.5, opacity: 0.9 };
        } else if (grade.includes("cloud")) {
          // unverified roads: #8A949A dashed
          return { color: "#8A949A", weight: 2.0, opacity: 0.8, dashArray: "4, 4" };
        }
        // normal roads: #6B747A
        return { color: "#6B747A", weight: 1.0, opacity: 0.5 };
      }
    });

    if (document.getElementById("layer-roads").checked) {
      geojsonLayers.roads.addTo(map);
    }
  } catch (err) {
    console.error("Error loading roads:", err);
  }
}

async function loadBridgesLayer(runId) {
  try {
    const res = await fetch(`/api/runs/${runId}/layer/bridges`);
    const geojson = await res.json();

    geojsonLayers.bridges = L.geoJSON(geojson, {
      pointToLayer: (feature, latlng) => {
        const grade = feature.properties.damage_grade || "Not affected";
        let color = "#6B747A";
        if (grade === "Destroyed" || grade === "Flooded / impassable") color = "#B42318";
        else if (grade === "Possibly damaged" || grade === "Possibly flooded") color = "#C2570C";

        return L.circleMarker(latlng, {
          radius: 6,
          fillColor: color,
          color: "#FFFFFF",
          weight: 1.5,
          opacity: 1,
          fillOpacity: 0.95
        });
      }
    });

    if (document.getElementById("layer-bridges").checked) {
      geojsonLayers.bridges.addTo(map);
    }
  } catch (err) {
    console.error("Error loading bridges:", err);
  }
}

async function loadSettlementsLayer(runId) {
  try {
    const res = await fetch(`/api/runs/${runId}/layer/settlements`);
    const geojson = await res.json();

    geojsonLayers.settlements = L.geoJSON(geojson, {
      pointToLayer: (feature, latlng) => {
        return L.circleMarker(latlng, getSettlementMarkerStyle(feature.properties));
      },
      onEachFeature: (feature, l) => {
        l.on("mouseover", () => {
          highlightSettlementListItem(feature, true);
        });
        l.on("mouseout", () => {
          highlightSettlementListItem(feature, false);
        });
      }
    });

    if (document.getElementById("layer-settlements").checked) {
      geojsonLayers.settlements.addTo(map);
    }

    updateAccessList();
  } catch (err) {
    console.error("Error loading settlements:", err);
  }
}

function getSettlementMarkerStyle(p) {
  const scenKey = currentScenario === "optimistic" ? "opt" : "pess";
  const vCut = p[`vehicle_status_${scenKey}`] === "cut_off";
  const wCut = p[`walking_status_${scenKey}`] === "cut_off";

  if (vCut && wCut) {
    // No ground access = filled #7A1D14 circle with white outline
    return {
      radius: 8,
      fillColor: "#7A1D14",
      color: "#FFFFFF",
      weight: 2,
      opacity: 1,
      fillOpacity: 1.0
    };
  } else if (vCut) {
    // Settlement cut off by road = white circle with #B42318 ring
    return {
      radius: 7,
      fillColor: "#FFFFFF",
      color: "#B42318",
      weight: 2.5,
      opacity: 1,
      fillOpacity: 1.0
    };
  } else {
    // Connected settlement
    return {
      radius: 4,
      fillColor: "#B6C0C4",
      color: "#FFFFFF",
      weight: 1,
      opacity: 0.6,
      fillOpacity: 0.6
    };
  }
}

function highlightSettlementListItem(feat, highlight) {
  const rows = document.querySelectorAll(".settlement-row-item");
  rows.forEach(r => {
    if (r.textContent.includes(feat.properties.name)) {
      if (highlight) {
        r.classList.add("highlighted");
        r.scrollIntoView({ behavior: "smooth", block: "nearest" });
      } else {
        r.classList.remove("highlighted");
      }
    }
  });
}

async function loadRepairPackagesLayer(runId) {
  try {
    const res = await fetch(`/api/runs/${runId}/repair-packages`);
    const data = await res.json();
    const ranked = data.ranked_packages || [];
    const actionable = ranked.filter(p => p.elements && p.elements.length > 0);
    if (actionable.length === 0) return;

    const pkgElems = new Set(actionable[0].elements);

    // Fetch roads and bridges to locate the package elements
    const [roadsRes, bridgesRes] = await Promise.all([
      fetch(`/api/runs/${runId}/layer/roads`),
      fetch(`/api/runs/${runId}/layer/bridges`)
    ]);

    const roadsGeo = await roadsRes.json();
    const bridgesGeo = await bridgesRes.json();

    const getElemId = (props) => {
      if (!props) return null;
      return props["@osmId"] || props["osm_id"] || props["id"] || (props["segment_id"] ? props["segment_id"].split("_")[0] : null);
    };

    const repairFeatures = [];
    if (roadsGeo && roadsGeo.features) {
      roadsGeo.features.forEach(f => {
        const id = getElemId(f.properties);
        if (id && pkgElems.has(id)) {
          repairFeatures.push(f);
        }
      });
    }

    if (bridgesGeo && bridgesGeo.features) {
      bridgesGeo.features.forEach(f => {
        const id = getElemId(f.properties);
        if (id && pkgElems.has(id)) {
          repairFeatures.push(f);
        }
      });
    }

    if (geojsonLayers.repair_packages && map.hasLayer(geojsonLayers.repair_packages)) {
      map.removeLayer(geojsonLayers.repair_packages);
    }

    geojsonLayers.repair_packages = L.geoJSON({ type: "FeatureCollection", features: repairFeatures }, {
      style: (feature) => {
        return {
          color: "#0284C7",
          weight: 6,
          opacity: 1.0,
          dashArray: null
        };
      },
      pointToLayer: (feature, latlng) => {
        return L.circleMarker(latlng, {
          radius: 9,
          fillColor: "#38BDF8",
          color: "#0284C7",
          weight: 4,
          opacity: 1,
          fillOpacity: 0.95
        });
      }
    });

  } catch (err) {
    console.error("Error loading repair packages:", err);
  }
}

// ==========================================================================
// S2 Slider: Before / After Sentinel-2 Comparison
// ==========================================================================
let preS2SavedBounds = null;

async function toggleS2Slider(activate) {
  const bar = document.getElementById("s2-slider-bar");
  const range = document.getElementById("s2-range-slider");
  const btnMapS2 = document.getElementById("btn-toggle-s2-comparison");
  const lblPre = document.getElementById("s2-date-pre");
  const lblPost = document.getElementById("s2-date-post");
  s2OverlayActive = activate;

  if (btnMapS2) {
    if (activate) btnMapS2.classList.add("active");
    else btnMapS2.classList.remove("active");
  }

  if (!activate) {
    bar.classList.add("hidden");
    if (s2PreOverlay) { map.removeLayer(s2PreOverlay); s2PreOverlay = null; }
    if (s2PostOverlay) { map.removeLayer(s2PostOverlay); s2PostOverlay = null; }

    // Restore normal map view if previous bounds were saved
    if (preS2SavedBounds) {
      map.fitBounds(preS2SavedBounds, { padding: [20, 20], maxZoom: 15 });
      preS2SavedBounds = null;
    }
    return;
  }

  if (!currentRunData || !currentRunData.bbox) return;
  const [w, s, e, n] = currentRunData.bbox;
  const bounds = [[s, w], [n, e]];

  // Save previous map bounds to restore upon closing
  preS2SavedBounds = map.getBounds();

  // 1. Fetch S2 metadata to display composite date ranges
  try {
    const metaRes = await fetch(`/api/runs/${currentRunId}/s2-meta`);
    if (metaRes.ok) {
      const meta = await metaRes.json();
      if (lblPre) lblPre.textContent = meta.pre?.date_range || "—";
      if (lblPost) lblPost.textContent = meta.post?.date_range || "—";
    }
  } catch (err) {
    console.warn("Could not load s2-meta:", err);
  }

  // 2. Zoom to damaged area (or AOI if no damage)
  zoomToDamagedArea(currentRunData);

  // 3. Attach S2 overlays above basemap and below vector data layers
  bar.classList.remove("hidden");
  range.value = 50;

  s2PreOverlay = L.imageOverlay(`/api/runs/${currentRunId}/s2-image?type=pre`, bounds, { pane: "s2Pane", zIndex: 1 }).addTo(map);
  s2PostOverlay = L.imageOverlay(`/api/runs/${currentRunId}/s2-image?type=post`, bounds, { pane: "s2Pane", zIndex: 2 }).addTo(map);

  const applyClip = () => {
    if (!s2PostOverlay) return;
    const el = s2PostOverlay.getElement();
    if (el) el.style.clipPath = `inset(0 0 0 ${range.value}%)`;
  };

  s2PostOverlay.on("load", applyClip);
  range.oninput = applyClip;
  setTimeout(applyClip, 100);

  document.getElementById("btn-close-s2-slider").onclick = () => toggleS2Slider(false);
}

// ==========================================================================
// Floating Copilot Assistant
// ==========================================================================
let copilotLastFocusedEl = null;

function initCopilot() {
  const btnFloating = document.getElementById("btn-floating-copilot");
  const win = document.getElementById("copilot-floating-window");
  const btnClose = document.getElementById("btn-close-copilot-window");
  const form = document.getElementById("copilot-window-form");
  const input = document.getElementById("copilot-window-input");
  const chips = document.querySelectorAll(".copilot-chip");

  // Open / Close window
  if (btnFloating && win) {
    btnFloating.addEventListener("click", () => {
      openCopilotWindow();
    });
  }

  if (btnClose) {
    btnClose.addEventListener("click", () => {
      closeCopilotWindow();
    });
  }

  // Escape key closes copilot
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && win && !win.classList.contains("hidden")) {
      closeCopilotWindow();
    }
  });

  // Suggestion chips
  chips.forEach(c => {
    c.addEventListener("click", () => {
      const q = c.getAttribute("data-q");
      if (q) askCopilot(q);
    });
  });

  // Form submission
  if (form) {
    form.onsubmit = (e) => {
      e.preventDefault();
      const q = input.value.trim();
      if (q) {
        input.value = "";
        askCopilot(q);
      }
    };
  }
}

function openCopilotWindow() {
  const win = document.getElementById("copilot-floating-window");
  const input = document.getElementById("copilot-window-input");
  const titleEl = document.getElementById("copilot-window-title");

  if (!win) return;
  copilotLastFocusedEl = document.activeElement;

  if (currentRunData) {
    titleEl.textContent = `Copilot · ${currentRunData.main_title || currentRunData.label || "Assessment"}`;
  }

  win.classList.remove("hidden");
  if (input) {
    setTimeout(() => input.focus(), 50);
  }
}

function closeCopilotWindow() {
  const win = document.getElementById("copilot-floating-window");
  if (!win) return;
  win.classList.add("hidden");
  if (copilotLastFocusedEl && typeof copilotLastFocusedEl.focus === "function") {
    copilotLastFocusedEl.focus();
  }
}

function resetCopilotForNewRun(data) {
  const titleEl = document.getElementById("copilot-window-title");
  const listEl = document.getElementById("copilot-messages-list");
  const chipsEl = document.getElementById("copilot-chips-wrap");
  const input = document.getElementById("copilot-window-input");

  if (titleEl && data) {
    titleEl.textContent = `Copilot · ${data.main_title || data.label || "Assessment"}`;
  }
  if (listEl) listEl.innerHTML = "";
  if (chipsEl) chipsEl.classList.remove("hidden");
  if (input) input.value = "";
}

async function askCopilot(question) {
  if (!currentRunId) return;

  const chipsEl = document.getElementById("copilot-chips-wrap");
  const listEl = document.getElementById("copilot-messages-list");
  const container = document.getElementById("copilot-messages-container");
  const sendBtn = document.getElementById("copilot-window-send-btn");

  // Hide suggestion chips once a question has been asked
  if (chipsEl) chipsEl.classList.add("hidden");

  // 1. Render User Message
  const userMsgEl = document.createElement("div");
  userMsgEl.className = "copilot-msg-user";
  userMsgEl.textContent = question;
  listEl.appendChild(userMsgEl);

  // 2. Render Bot Pending Message
  const botMsgEl = document.createElement("div");
  botMsgEl.className = "copilot-msg-bot";
  botMsgEl.innerHTML = `
    <div class="answer-text">Consulting copilot...</div>
    <div class="copilot-msg-meta">
      <span class="meta-tag">Processing query...</span>
    </div>
  `;
  listEl.appendChild(botMsgEl);

  if (container) container.scrollTop = container.scrollHeight;
  if (sendBtn) sendBtn.disabled = true;

  const t0 = Date.now();
  try {
    const res = await fetch(`/api/runs/${currentRunId}/copilot/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question })
    });
    const d = await res.json();
    const elapsed = ((Date.now() - t0) / 1000).toFixed(1);

    const answer = d.answer || "No response received.";
    const isOffline = d.provider === "offline" || d.answer_path === "offline" || answer.includes("[ANSWERED IN OFFLINE MODE]");
    const isRules = d.answer_path === "rules" || d.model === "rules" || d.provider === "rules" || d.answer_path === "keyword_refusal" || d.answer_path === "template_fallback";
    let metaTagText = `Answered live by ${d.model || d.provider} in ${elapsed}s`;
    if (isOffline) {
      metaTagText = "Answered offline";
    } else if (isRules) {
      metaTagText = "Answered by rules (no AI model)";
    }

    const sources = d.sources || [];
    let sourcesBtnHtml = "";
    let sourcesListHtml = "";

    if (sources.length > 0) {
      sourcesBtnHtml = `<button type="button" class="copilot-sources-btn">Sources (${sources.length})</button>`;
      const itemsHtml = sources.map(s => {
        const valStr = s.value !== undefined ? ` = ${s.value}` : "";
        return `<div>${escapeHtml(s.file)} [${escapeHtml(s.field)}]${escapeHtml(valStr)}</div>`;
      }).join("");
      sourcesListHtml = `<div class="copilot-sources-accordion hidden font-mono">${itemsHtml}</div>`;
    }

    botMsgEl.innerHTML = `
      <div class="answer-text">${escapeHtml(answer)}</div>
      <div class="copilot-msg-meta">
        <span class="meta-tag">${escapeHtml(metaTagText)}</span>
        ${sourcesBtnHtml}
      </div>
      ${sourcesListHtml}
    `;

    // Bind sources toggle
    const btnSrc = botMsgEl.querySelector(".copilot-sources-btn");
    const listSrc = botMsgEl.querySelector(".copilot-sources-accordion");
    if (btnSrc && listSrc) {
      btnSrc.addEventListener("click", () => {
        listSrc.classList.toggle("hidden");
      });
    }

  } catch (err) {
    botMsgEl.innerHTML = `
      <div class="answer-text">Error querying copilot: ${escapeHtml(err.message)}</div>
      <div class="copilot-msg-meta">
        <span class="meta-tag">Answered offline</span>
      </div>
    `;
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    if (container) container.scrollTop = container.scrollHeight;
  }
}

function escapeHtml(str) {
  if (typeof str !== "string") return String(str || "");
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

