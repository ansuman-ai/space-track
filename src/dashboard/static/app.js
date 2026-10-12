/**
 * Spaceborne Rapid Disaster Assessment Platform — Layer 7
 * Operational Disaster Intelligence Visualizer.
 * Strict JSON data binding, manifest filtering, cloud-masked median S2 composite slider,
 * decluttered layers, and no-ground-access priority routing.
 */

// Bilingual Translation Dictionary (EN & NE)
const I18N = {
  en: {
    app_title: "Spaceborne Rapid Disaster Assessment",
    app_subtitle: "Operational SAR & Optical Damage Assessment & Isolation Routing",
    select_run: "Assessment:",
    show_all_runs: "All Runs (77)",
    loading_runs: "Loading assessments...",
    toggle_s2_slider: "Optical Before / After",
    sec1_title: "WHAT HAPPENED",
    sec2_title: "WHO IS CUT OFF",
    sec3_title: "WHAT TO REPAIR FIRST",
    sec4_title: "HOW SURE",
    event_date: "Event Date:",
    terrain_regime: "Terrain Regime:",
    image_dates_used: "Image Dates Used:",
    observed_area: "Observed Damage",
    inferred_area: "Inferred Hydraulic",
    permanent_water: "water mask (may include terrain shadow)",
    show_all_water: "Show All Water Bodies / Ponds",
    affected_buildings: "Buildings Affected",
    show_unverified_buildings: "Show Cloud-Unverified Buildings",
    affected_bridges: "Bridges Affected",
    roads_damaged: "Road Damage",
    roads_damaged_flat: "Road Impassability",
    no_ground_access_badge: "CRITICAL (NO GROUND ACCESS)",
    airdrop_only_label: "Air / Helicopter Only",
    airdrop_only_flat: "Boat / Helicopter Access",
    vehicle_cut_badge: "VEHICLE ACCESS SEVERED",
    vehicle_cut_desc: "Communities Isolated",
    mode_label: "Transport Mode:",
    scenario_label: "Damage Scenario:",
    vehicle: "Vehicle",
    walking: "Walking",
    optimistic: "Optimistic",
    pessimistic: "Pessimistic",
    settlement_list_title: "Cut-off Settlement Directory",
    loading_settlements: "Loading settlements...",
    highlight_repair_pkg: "Highlight Package on Map",
    critical_network_elements: "Critical Road / Bridge Elements:",
    validation_status_badge: "VALIDATION",
    optical_offset_label: "Optical Evidence Offset:",
    cloud_unverified_label: "Cloud-Unverified Infrastructure:",
    sensors_used: "Sensors Employed:",
    runtime: "Compute Runtime / RAM:",
    known_limits_title: "Known Scope & Scientific Limitations:",
    limit_shadow: "Permanent water mask: ~40% of Class-1 pixels on steep mountain slopes (>20°) represent radar and topographic shadow rather than open water bodies.",
    limit_revisit: "Sentinel SAR / MSI revisit interval (6–12 days); not a real-time telemetry stream.",
    limit_layover: "Steep topography radar layover & shadow actively masked using DEM look angles.",
    limit_osm: "Damage counts reflect pre-event OpenStreetMap inventory density.",
    limit_dl: "Pretrained AI models segment flood water only; debris surge mapped by physical SAR/optical change.",
    layers_and_legend: "Layers & Legend",
    basemap: "Basemap",
    dark_canvas: "Muted Canvas",
    satellite: "Satellite",
    osm_streets: "Light Canvas",
    hazard_extent: "Hazard & Inundation",
    observed_hazard: "Observed Damage / Flood (Class 2)",
    inferred_hazard: "Inferred Hydraulic Fill (Class 3)",
    infrastructure_damage: "Infrastructure Damage",
    affected_buildings_layer: "Affected Buildings",
    show_intact_buildings: "Show Intact Buildings",
    show_connected_settlements: "Show Connected Settlements",
    legend_destroyed: "Destroyed",
    legend_flooded: "Flooded / Impassable",
    legend_damaged: "Damaged / Possibly Damaged",
    legend_possibly_damaged: "Possibly damaged",
    legend_possibly_flooded: "Possibly flooded",
    legend_unverified: "Cloud-Unverified",
    road_network: "Roads (Destroyed / Damaged)",
    road_network_flat: "Roads (Flooded / Impassable)",
    bridges: "Bridges",
    isolation_routing: "Access & Repair",
    settlements_cutoff: "Cut-off Settlements",
    repair_package_1: "Repair Package 1 Links",
    loading_layer_data: "Loading geospatial data...",
    heli_only_badge: "Air / Helicopter Only",
    boat_heli_badge: "Boat / Helicopter Access",
    steep_valley: "Steep Mountain Valley",
    flat_floodplain: "Flat Floodplain"
  },
  ne: {
    app_title: "अन्तरिक्षीय द्रुत विपद् क्षति मूल्यांकन",
    app_subtitle: "स्याटेलाइट राडार तथा अप्टिकल क्षति नक्सांकन एवं पृथक बस्ती सञ्जाल",
    select_run: "मूल्यांकन:",
    show_all_runs: "सबै रनहरू (७७)",
    loading_runs: "मूल्यांकन लोड हुँदैछ...",
    toggle_s2_slider: "अप्टिकल अघि / पछि तुलना",
    sec1_title: "घटना विवरण",
    sec2_title: "सम्पर्कविहीन बस्तीहरू",
    sec3_title: "प्राथमिकता मर्मत योजना",
    sec4_title: "प्रमाणीकरण र विश्वसनीयता",
    event_date: "घटना मिति:",
    terrain_regime: "धरातलीय स्वरूप:",
    image_dates_used: "प्रयोग गरिएका छवि मिति:",
    observed_area: "प्रत्यक्ष क्षति क्षेत्र",
    inferred_area: "अनुमानित जलमग्न क्षेत्र",
    permanent_water: "जल आवरण (पहाडी छायाँ समावेश हुनसक्ने)",
    show_all_water: "सबै जल क्षेत्र / पोखरीहरू देखाउनुहोस्",
    affected_buildings: "प्रभावित भवनहरू",
    show_unverified_buildings: "बादलले ढाकिएका भवनहरू देखाउनुहोस्",
    affected_bridges: "प्रभावित पुलहरू",
    roads_damaged: "सडक क्षति",
    roads_damaged_flat: "सडक अवरोध / जलमग्न",
    no_ground_access_badge: "अति संवेदनशील (स्थलीय पहुँचविहीन)",
    airdrop_only_label: "हवाई / हेलिकप्टर मात्र",
    airdrop_only_flat: "डुङ्गा / हेलिकप्टर पहुँच",
    vehicle_cut_badge: "सवारी साधन पहुँच विच्छेद",
    vehicle_cut_desc: "सम्पर्कविहीन समुदायहरू",
    mode_label: "यातायात माध्यम:",
    scenario_label: "क्षति परिदृश्य:",
    vehicle: "सवारी साधन",
    walking: "पैदल",
    optimistic: "आशावादी",
    pessimistic: "निराशावादी",
    settlement_list_title: "सम्पर्कविहीन बस्तीहरूको विवरण",
    loading_settlements: "बस्तीहरू लोड हुँदैछ...",
    highlight_repair_pkg: "नक्सामा मर्मत प्याकेज देखाउनुहोस्",
    critical_network_elements: "प्रमुख सडक / पुल संरचनाहरू:",
    validation_status_badge: "प्रमाणीकरण",
    optical_offset_label: "अप्टिकल छवि अन्तर:",
    cloud_unverified_label: "बादलले ढाकिएका संरचनाहरू:",
    sensors_used: "प्रयोग गरिएका सेन्सर:",
    runtime: "प्रशोधन समय / र्याम:",
    known_limits_title: "वैज्ञानिक सीमाहरू:",
    limit_shadow: "स्थायी जल आवरण: भिरालो पहाडमा (>२०°) लगभग ४०% वर्ग-१ पिक्सेलहरू वास्तविक पानी नभई राडार र धरातलीय छायाँ हुन्।",
    limit_revisit: "सेन्टिनेल उपग्रह ६ देखि १२ दिनको अन्तरालमा मात्र उपलब्ध हुन्छ।",
    limit_layover: "भिरालो पहाडमा राडार छायाँ र लेओभर प्रभाव हटाइएको छ।",
    limit_osm: "क्षतिको संख्या पूर्व-विपद् ओपनस्ट्रिटम्याप विवरणमा निर्भर छ।",
    limit_dl: "एआई मोडलले बाढी मात्र पहिचान गर्दछ; गेग्रान बहाव भौतिक परिवर्तनद्वारा निकालिएको हो।",
    layers_and_legend: "तहहरू र संकेत",
    basemap: "पृष्ठभूमि नक्सा",
    dark_canvas: "गहिरो क्यानभास",
    satellite: "उपग्रह छवि",
    osm_streets: "उज्यालो क्यानभास",
    hazard_extent: "विपद् एवं जलमग्न क्षेत्र",
    observed_hazard: "प्रत्यक्ष क्षति / बाढी (वर्ग २)",
    inferred_hazard: "अनुमानित जलमग्न क्षेत्र (वर्ग ३)",
    infrastructure_damage: "पूर्वाधार क्षति",
    affected_buildings_layer: "प्रभावित भवनहरू",
    show_intact_buildings: "सुरक्षित भवनहरू देखाउनुहोस्",
    show_connected_settlements: "जोडिएका बस्तीहरू देखाउनुहोस्",
    legend_destroyed: "पूर्ण क्षतिग्रस्त",
    legend_flooded: "जलमग्न / अवरुद्ध",
    legend_damaged: "आंशिक क्षतिग्रस्त",
    legend_possibly_damaged: "आंशिक क्षतिग्रस्त हुनसक्ने",
    legend_possibly_flooded: "जलमग्न हुनसक्ने",
    legend_unverified: "बादलले ढाकिएको",
    road_network: "सडक सञ्जाल क्षति",
    road_network_flat: "सडक जलमग्न / अवरुद्ध",
    bridges: "पुलहरू",
    isolation_routing: "पहुँच तथा मर्मत",
    settlements_cutoff: "सम्पर्कविहीन बस्तीहरू",
    repair_package_1: "मर्मत प्याकेज १ खण्डहरू",
    loading_layer_data: "डाटा लोड हुँदैछ...",
    heli_only_badge: "हवाई / हेलिकप्टर मात्र",
    boat_heli_badge: "डुङ्गा / हेलिकप्टर पहुँच",
    steep_valley: "भिरालो हिमाली उपत्यका",
    flat_floodplain: "समथर तराई / बाढी मैदान"
  }
};

let currentLang = "en";
let currentRunId = null;
let currentRunData = null;

// Routing Filter State
let currentMode = "vehicle"; // "vehicle" | "walking"
let currentScenario = "optimistic"; // "optimistic" | "pessimistic"

// Map & Layer State
let map = null;
let baseLayers = {};
let activeBasemap = "offline";

let geojsonLayers = {
  hazards: null,
  buildings: null,
  roads: null,
  bridges: null,
  settlements: null,
  repair_packages: null
};

// S2 Before/After Overlay State
let s2OverlayActive = false;
let s2PreOverlay = null;
let s2PostOverlay = null;

// Initialize on Load
document.addEventListener("DOMContentLoaded", () => {
  initMap();
  initTabs();
  initProjectorRelief();
  initLanguageToggle();
  initLegendControls();
  initFilterControls();
  initS2Slider();
  initHistoryFilter();
  initPhase2Controls();
  initCopilot();
  initSitrepControls();
  loadRunsList();
});

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

function initProjectorRelief() {
  const btn = document.getElementById("btn-toggle-relief");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const mapEl = document.getElementById("map");
    mapEl.classList.toggle("projector-relief");
    btn.classList.toggle("active");
  });
}

function initMap() {
  map = L.map("map", {
    center: [28.0, 85.0],
    zoom: 9,
    zoomControl: false,
    attributionControl: true
  });

  L.control.zoom({ position: "bottomright" }).addTo(map);

  // Status bar cursor coordinates and zoom updates
  map.on("mousemove", (e) => {
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;
    const latDir = lat >= 0 ? "N" : "S";
    const lngDir = lng >= 0 ? "E" : "W";
    const elCoords = document.getElementById("status-cursor-coords");
    if (elCoords) {
      elCoords.textContent = `${Math.abs(lat).toFixed(4)}° ${latDir}, ${Math.abs(lng).toFixed(4)}° ${lngDir}`;
    }
  });

  map.on("zoomend", () => {
    const elZoom = document.getElementById("status-zoom");
    if (elZoom) {
      elZoom.textContent = `Zoom ${map.getZoom()}`;
    }
  });

  // Custom panes to ensure raster basemaps stay below vector overlays
  map.createPane("basemapImagePane");
  map.getPane("basemapImagePane").style.zIndex = 150;
  map.createPane("basemapVectorPane");
  map.getPane("basemapVectorPane").style.zIndex = 250;

  // 1. Offline Basemap: Copernicus DEM GLO-30 hillshade + OSM waterways + OSM roads + OSM place labels
  baseLayers.offline = L.layerGroup();

  // 2. Sentinel-2 True-Colour Composite basemap (offline composite from run cache)
  baseLayers.satellite = L.layerGroup();

  // 3. OpenStreetMap standard tiles (optional online layer only)
  baseLayers.osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  });

  baseLayers.offline.addTo(map);

  // Resize handler for full tile coverage
  window.addEventListener("resize", () => {
    map.invalidateSize();
  });
}

async function updateOfflineBasemap(runId, data) {
  baseLayers.offline.clearLayers();

  // 1. Copernicus DEM GLO-30 (30 m) Topographic Relief Hillshade
  try {
    const metaResp = await fetch(`/api/runs/${runId}/basemap/meta`);
    if (metaResp.ok) {
      const meta = await metaResp.json();
      if (meta.bounds) {
        const hillshade = L.imageOverlay(`/api/runs/${runId}/basemap/hillshade`, meta.bounds, {
          opacity: 1.0,
          interactive: false,
          className: "hillshade-overlay",
          pane: "basemapImagePane",
          attribution: 'Copernicus DEM GLO-30 (30 m) &copy; DLR e.V. 2010-2014 &copy; Airbus Defence and Space GmbH 2014-2018'
        });
        baseLayers.offline.addLayer(hillshade);
      }
    }
  } catch (e) {
    console.warn("Could not load hillshade:", e);
  }

  // 2. OSM Waterways (Rivers: thin, muted grey-blue clearly distinguishable from flood hazard)
  try {
    const riverResp = await fetch(`/api/runs/${runId}/basemap/waterways`);
    if (riverResp.ok) {
      const riverGeo = await riverResp.json();
      const riverLayer = L.geoJSON(riverGeo, {
        pane: "basemapVectorPane",
        style: {
          color: "#64748b",
          weight: 1.2,
          opacity: 0.65
        },
        interactive: false
      });
      baseLayers.offline.addLayer(riverLayer);
    }
  } catch (e) {
    console.warn("Could not load waterways:", e);
  }

  // 3. OSM Roads (Subtle baseline network)
  try {
    const roadsResp = await fetch(`/api/runs/${runId}/basemap/roads`);
    if (roadsResp.ok) {
      const roadsGeo = await roadsResp.json();
      const roadsLayer = L.geoJSON(roadsGeo, {
        pane: "basemapVectorPane",
        style: {
          color: "#94a3b8",
          weight: 1.0,
          opacity: 0.5
        },
        interactive: false
      });
      baseLayers.offline.addLayer(roadsLayer);
    }
  } catch (e) {
    console.warn("Could not load baseline roads:", e);
  }

  // 4. OSM Places (Devanagari + Latin typography with Noto fonts)
  try {
    const placesResp = await fetch(`/api/runs/${runId}/basemap/places`);
    if (placesResp.ok) {
      const placesGeo = await placesResp.json();
      const placesLayer = L.geoJSON(placesGeo, {
        pointToLayer: (feat, latlng) => {
          const props = feat.properties || {};
          const devName = props["name:ne"] || props["name:Deva"] || "";
          const latName = props["name:en"] || (devName ? props.name : "") || props.name || "";

          let html = "";
          if (devName && latName && devName !== latName) {
            html = `<div class="osm-place-label"><span class="place-dev">${devName}</span><span class="place-lat">${latName}</span></div>`;
          } else {
            const display = devName || latName || props.name || "Village";
            html = `<div class="osm-place-label"><span class="place-dev">${display}</span></div>`;
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
      baseLayers.offline.addLayer(placesLayer);
    }
  } catch (e) {
    console.warn("Could not load place labels:", e);
  }
}

function updateSatelliteBasemap(runId, data) {
  baseLayers.satellite.clearLayers();
  if (data && data.bbox && data.bbox.length === 4) {
    const [w, s, e, n] = data.bbox;
    const bounds = [[s, w], [n, e]];
    const s2Basemap = L.imageOverlay(`/api/runs/${runId}/s2-image?type=post`, bounds, {
      opacity: 1.0,
      interactive: false,
      pane: "basemapImagePane",
      attribution: 'Contains modified Copernicus Sentinel data &copy; ESA'
    });
    baseLayers.satellite.addLayer(s2Basemap);
  }
}

function initLanguageToggle() {
  const langBtn = document.getElementById("lang-btn");
  langBtn.addEventListener("click", () => {
    currentLang = currentLang === "en" ? "ne" : "en";
    applyTranslations();
    if (currentRunData) {
      updateSidePanel(currentRunData);
      updateSettlementsFilter();
    }
  });
}

function applyTranslations() {
  const dict = I18N[currentLang];
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    if (dict[key]) {
      el.textContent = dict[key];
    }
  });
}

function initHistoryFilter() {
  const chkAll = document.getElementById("chk-show-all-runs");
  chkAll.addEventListener("change", () => {
    loadRunsList();
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

  // Basemap switchers
  document.querySelectorAll('input[name="basemap"]').forEach(radio => {
    radio.addEventListener("change", (e) => {
      const selected = e.target.value;
      if (baseLayers[activeBasemap]) map.removeLayer(baseLayers[activeBasemap]);
      if (selected === "satellite" && currentRunId && currentRunData) {
        updateSatelliteBasemap(currentRunId, currentRunData);
      }
      if (selected === "offline" && currentRunId && currentRunData) {
        updateOfflineBasemap(currentRunId, currentRunData);
      }
      if (baseLayers[selected]) {
        baseLayers[selected].addTo(map);
        activeBasemap = selected;
      }
      map.invalidateSize();
    });
  });

  // Layer Visibility Checkboxes
  document.getElementById("layer-haz-obs").addEventListener("change", () => updateHazardFilter());
  document.getElementById("layer-haz-inf").addEventListener("change", () => updateHazardFilter());
  document.getElementById("layer-haz-perm").addEventListener("change", () => updateHazardFilter());
  document.getElementById("chk-all-water").addEventListener("change", () => updateHazardFilter());

  document.getElementById("layer-buildings").addEventListener("change", (e) => {
    if (geojsonLayers.buildings) {
      if (e.target.checked) map.addLayer(geojsonLayers.buildings);
      else map.removeLayer(geojsonLayers.buildings);
    }
  });

  document.getElementById("layer-intact-buildings").addEventListener("change", () => {
    if (currentRunId) loadBuildingsLayer(currentRunId);
  });

  document.getElementById("layer-unverified-buildings").addEventListener("change", () => {
    if (currentRunId) loadBuildingsLayer(currentRunId);
  });

  document.getElementById("chk-show-connected-settlements").addEventListener("change", () => {
    updateSettlementsFilter();
  });

  document.getElementById("layer-roads").addEventListener("change", (e) => {
    if (geojsonLayers.roads) {
      if (e.target.checked) map.addLayer(geojsonLayers.roads);
      else map.removeLayer(geojsonLayers.roads);
    }
  });

  document.getElementById("layer-bridges").addEventListener("change", (e) => {
    if (geojsonLayers.bridges) {
      if (e.target.checked) map.addLayer(geojsonLayers.bridges);
      else map.removeLayer(geojsonLayers.bridges);
    }
  });

  document.getElementById("layer-settlements").addEventListener("change", (e) => {
    if (geojsonLayers.settlements) {
      if (e.target.checked) map.addLayer(geojsonLayers.settlements);
      else map.removeLayer(geojsonLayers.settlements);
    }
  });

  document.getElementById("layer-repair-pkg").addEventListener("change", (e) => {
    if (geojsonLayers.repair_packages) {
      if (e.target.checked) map.addLayer(geojsonLayers.repair_packages);
      else map.removeLayer(geojsonLayers.repair_packages);
    }
  });
}

function initFilterControls() {
  const btnVeh = document.getElementById("btn-mode-vehicle");
  const btnWalk = document.getElementById("btn-mode-walking");
  const btnOpt = document.getElementById("btn-scen-opt");
  const btnPess = document.getElementById("btn-scen-pess");

  btnVeh.addEventListener("click", () => {
    currentMode = "vehicle";
    btnVeh.classList.add("active");
    btnWalk.classList.remove("active");
    updateSettlementsFilter();
  });

  btnWalk.addEventListener("click", () => {
    currentMode = "walking";
    btnWalk.classList.add("active");
    btnVeh.classList.remove("active");
    updateSettlementsFilter();
  });

  btnOpt.addEventListener("click", () => {
    currentScenario = "optimistic";
    btnOpt.classList.add("active");
    btnPess.classList.remove("active");
    updateSettlementsFilter();
  });

  btnPess.addEventListener("click", () => {
    currentScenario = "pessimistic";
    btnPess.classList.add("active");
    btnOpt.classList.remove("active");
    updateSettlementsFilter();
  });

  document.getElementById("btn-zoom-repair").addEventListener("click", () => {
    if (geojsonLayers.repair_packages && geojsonLayers.repair_packages.getLayers().length > 0) {
      map.fitBounds(geojsonLayers.repair_packages.getBounds(), { padding: [50, 50], maxZoom: 15 });
    }
  });
}

// ==========================================================================
// Runs List & Run Details Loader
// ==========================================================================
async function loadRunsList() {
  const select = document.getElementById("run-select");
  const showAll = document.getElementById("chk-show-all-runs").checked;

  try {
    const res = await fetch(`/api/runs?show_all=${showAll}`);
    const runs = await res.json();

    select.innerHTML = "";
    if (runs.length === 0) {
      select.innerHTML = `<option disabled selected>No assessments found</option>`;
      return;
    }

    runs.forEach(run => {
      const opt = document.createElement("option");
      opt.value = run.id;
      opt.textContent = run.label;
      select.appendChild(opt);
    });

    const urlParams = new URLSearchParams(window.location.search);
    const targetRun = urlParams.get("run");
    const initialRunId = targetRun && runs.some(r => r.id === targetRun) ? targetRun : runs[0].id;

    select.value = initialRunId;
    loadRun(initialRunId);

    select.onchange = (e) => {
      loadRun(e.target.value);
    };

  } catch (err) {
    console.error("Failed to load runs:", err);
    select.innerHTML = `<option disabled selected>Error loading assessments</option>`;
  }
}

async function loadRun(runId) {
  if (currentRunId === runId && currentRunData) return;
  currentRunId = runId;

  const url = new URL(window.location);
  url.searchParams.set("run", runId);
  window.history.replaceState({}, "", url);

  const spinner = document.getElementById("map-spinner");
  spinner.classList.remove("hidden");

  if (s2OverlayActive) toggleS2BeforeAfterSlider(false);

  try {
    const res = await fetch(`/api/runs/${runId}`);
    const data = await res.json();
    currentRunData = data;

    // Update dynamic footer year
    const attrSentinel = document.getElementById("attr-sentinel");
    const year = data.event_year || (data.event_date ? data.event_date.split("-")[0] : "2026");
    attrSentinel.textContent = `Contains modified Copernicus Sentinel data ${year}.`;

    // Update Side Panel
    updateSidePanel(data);

    // Clear old layers
    Object.keys(geojsonLayers).forEach(k => {
      if (geojsonLayers[k]) {
        map.removeLayer(geojsonLayers[k]);
        geojsonLayers[k] = null;
      }
    });

    // Concurrently load basemap and GeoJSON layers
    const promises = [];
    if (activeBasemap === "offline") {
      promises.push(updateOfflineBasemap(runId, data));
    } else if (activeBasemap === "satellite") {
      updateSatelliteBasemap(runId, data);
    }
    if (data.layers_available.hazards) promises.push(loadHazardsLayer(runId));
    if (data.layers_available.roads) promises.push(loadRoadsLayer(runId));
    if (data.layers_available.bridges) promises.push(loadBridgesLayer(runId));
    if (data.layers_available.buildings) promises.push(loadBuildingsLayer(runId));
    if (data.layers_available.settlements) promises.push(loadSettlementsLayer(runId));
    if (data.layers_available.repair_packages) promises.push(loadRepairPackagesLayer(runId));

    await Promise.all(promises);

    // Check custom view URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("lat") && urlParams.get("lng")) {
      const lat = parseFloat(urlParams.get("lat"));
      const lng = parseFloat(urlParams.get("lng"));
      const z = parseInt(urlParams.get("zoom") || "15");
      map.setView([lat, lng], z);
    } else {
      // Zoom to damaged area on load
      zoomToDamagedArea(data);
    }

    // Check slider URL parameter
    if (urlParams.get("slider") === "1") {
      toggleS2BeforeAfterSlider(true);
    }

  } catch (err) {
    console.error("Error loading run details:", err);
  } finally {
    spinner.classList.add("hidden");
    setTimeout(() => map.invalidateSize(), 150);
  }
}

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
      if (g === "Destroyed" || g === "Possibly damaged") damagedGroup.addLayer(l);
    });
  }

  if (damagedGroup.getLayers().length > 0) {
    map.fitBounds(damagedGroup.getBounds(), { padding: [40, 40], maxZoom: 15 });
  } else if (data.bbox && data.bbox.length === 4) {
    const [w, s, e, n] = data.bbox;
    map.fitBounds([[s, w], [n, e]], { padding: [40, 40], maxZoom: 14 });
  }
}

// ==========================================================================
// Executive Summary Sentence & Bridges Breakdown Formatters
// ==========================================================================
function buildExecutiveSummary(data, m, isFlat) {
  const b = m.buildings || {};
  const br = m.bridges || {};
  const cuts = m.cutoffs || {};
  const scenKey = currentScenario === "optimistic" ? "optimistic" : "pessimistic";
  const river = data.primary_river;

  let bldText = "";
  if (isFlat) {
    bldText = `${b.flooded || b.total_affected || 0} buildings flooded`;
  } else {
    if (b.destroyed > 0) {
      bldText = `${b.destroyed} buildings destroyed`;
    } else if (b.total_affected > 0) {
      bldText = `${b.total_affected} buildings affected`;
    } else {
      bldText = `0 buildings destroyed`;
    }
  }

  let brText = "";
  if (isFlat) {
    brText = `${br.flooded || 0} bridges flooded / impassable`;
  } else {
    if (br.destroyed > 0) {
      brText = `${br.destroyed} bridges destroyed`;
    } else if (br.possibly_damaged > 0) {
      brText = `${br.possibly_damaged} bridges possibly damaged`;
    } else {
      brText = `0 bridges destroyed`;
    }
  }

  const vehCut = cuts[`vehicle_${scenKey}`] !== undefined ? cuts[`vehicle_${scenKey}`] : (cuts.vehicle_pessimistic || cuts.vehicle_optimistic || 0);
  const noGround = cuts[`no_ground_access_${scenKey}`] !== undefined ? cuts[`no_ground_access_${scenKey}`] : (cuts.no_ground_access_pessimistic || cuts.no_ground_access_optimistic || 0);
  const cutText = `${vehCut} settlements cut off by road (${noGround} with no ground access)`;

  const riverText = river ? ` along ${river}` : "";

  return `${bldText}, ${brText}, ${cutText}${riverText}.`;
}

function formatBridgesSummary(br, isFlat) {
  const assessed = br.total_assessed || br.total_count || br.total_affected || 0;
  if (isFlat) {
    if (br.flooded > 0 && br.possibly_flooded > 0) {
      return `${br.flooded} flooded, ${br.possibly_flooded} possibly flooded (${assessed} assessed)`;
    } else if (br.flooded > 0) {
      return `${br.flooded} flooded / impassable (${assessed} assessed)`;
    } else {
      return `0 affected (${assessed} assessed)`;
    }
  } else {
    if (br.destroyed > 0 && br.possibly_damaged > 0) {
      return `${br.destroyed} destroyed, ${br.possibly_damaged} possibly damaged (${assessed} assessed)`;
    } else if (br.destroyed > 0) {
      return `${br.destroyed} destroyed (${assessed} assessed)`;
    } else if (br.possibly_damaged > 0) {
      return `${br.possibly_damaged} possibly damaged (${assessed} assessed)`;
    } else {
      return `0 affected (${assessed} assessed)`;
    }
  }
}

// ==========================================================================
// Side Panel: 4 Operational Sections
// ==========================================================================
function updateSidePanel(data) {
  const dict = I18N[currentLang];
  const m = data.metrics || {};
  const isFlat = data.regime === "flat_floodplain";

  // HEADER TITLES & SUBTITLE ROW
  const titleEl = document.getElementById("run-main-title");
  if (titleEl) {
    titleEl.textContent = data.main_title || data.label || "Disaster Assessment";
  }

  const dateEl = document.getElementById("val-header-date");
  if (dateEl) dateEl.textContent = data.event_date || "—";

  const regimeEl = document.getElementById("val-header-regime");
  const regimeName = isFlat ? dict.flat_floodplain : dict.steep_valley;
  if (regimeEl) regimeEl.textContent = regimeName;

  const valBadgeEl = document.getElementById("val-header-validation");
  const statusStr = data.validation_status || "not validated against an official map (practice run)";
  if (valBadgeEl) {
    if (statusStr.includes("EMSR") || (!statusStr.includes("not validated") && !statusStr.includes("weak"))) {
      valBadgeEl.textContent = statusStr;
      valBadgeEl.classList.add("verified");
    } else {
      valBadgeEl.textContent = "Practice assessment (unvalidated)";
      valBadgeEl.classList.remove("verified");
    }
  }

  // 1-SENTENCE EXECUTIVE BRIEF (Strictly Data-Driven Template)
  const summaryBox = document.getElementById("summary-sentence-box");
  if (summaryBox) {
    summaryBox.textContent = buildExecutiveSummary(data, m, isFlat);
  }

  // DATA CALCULATIONS
  const areas = m.areas || {};
  const b = m.buildings || {};
  const br = m.bridges || {};
  const r = m.roads_km || {};
  const cuts = m.cutoffs || {};

  const scenKey = currentScenario === "optimistic" ? "optimistic" : "pessimistic";
  const noGroundCount = cuts[`no_ground_access_${scenKey}`] !== undefined ? cuts[`no_ground_access_${scenKey}`] : (cuts.no_ground_access_pessimistic || cuts.no_ground_access_optimistic || 0);
  const vehCutCount = cuts[`vehicle_${scenKey}`] !== undefined ? cuts[`vehicle_${scenKey}`] : (cuts.vehicle_pessimistic || cuts.vehicle_optimistic || 0);

  // 4 KEY NUMBERS (2x2 GRID)
  const kpiValB = document.getElementById("kpi-val-buildings");
  const kpiLblB = document.getElementById("kpi-lbl-buildings");
  if (kpiValB) kpiValB.textContent = isFlat ? (b.flooded || b.total_affected || 0) : (b.destroyed || 0);
  if (kpiLblB) kpiLblB.innerHTML = `<span class="dot-semantic dot-destroyed"></span><span>${isFlat ? "Buildings flooded" : "Buildings destroyed"}</span>`;

  const kpiValBr = document.getElementById("kpi-val-bridges");
  const kpiLblBr = document.getElementById("kpi-lbl-bridges");
  if (kpiValBr) kpiValBr.textContent = isFlat ? (br.flooded || 0) : (br.destroyed || 0);
  if (kpiLblBr) kpiLblBr.innerHTML = `<span class="dot-semantic dot-destroyed"></span><span>${formatBridgesSummary(br, isFlat)}</span>`;

  const kpiValS = document.getElementById("kpi-val-settlements");
  const kpiLblS = document.getElementById("kpi-lbl-settlements");
  if (kpiValS) kpiValS.textContent = vehCutCount;
  if (kpiLblS) kpiLblS.innerHTML = `<span class="dot-semantic dot-cutoff"></span><span>${vehCutCount} cut off (${noGroundCount} no ground)</span>`;

  const kpiValR = document.getElementById("kpi-val-roads");
  const kpiLblR = document.getElementById("kpi-lbl-roads");
  if (kpiValR) kpiValR.textContent = `${(r.destroyed_km !== undefined ? r.destroyed_km.toFixed(1) : "0.0")} km`;
  if (kpiLblR) kpiLblR.innerHTML = `<span class="dot-semantic dot-destroyed"></span><span>${isFlat ? "Roads impassable" : "Roads severed"}</span>`;

  // MICRO-LEGEND STATISTICS
  const legObs = document.getElementById("legend-stat-obs");
  if (legObs) legObs.textContent = `${(areas.observed_km2 !== undefined ? areas.observed_km2.toFixed(2) : "0.00")} km²`;
  const legInf = document.getElementById("legend-stat-inf");
  if (legInf) legInf.textContent = `${(areas.inferred_km2 !== undefined ? areas.inferred_km2.toFixed(2) : "0.00")} km²`;
  const legBld = document.getElementById("legend-stat-buildings");
  if (legBld) legBld.textContent = b.total_affected || 0;
  const legBr = document.getElementById("legend-stat-bridges");
  if (legBr) legBr.textContent = br.total_affected || 0;
  const legRd = document.getElementById("legend-stat-roads");
  if (legRd) legRd.textContent = `${(r.destroyed_km !== undefined ? r.destroyed_km.toFixed(1) : "0.0")} km`;
  const legCut = document.getElementById("legend-stat-cutoff-road");
  if (legCut) legCut.textContent = vehCutCount;
  const legNoG = document.getElementById("legend-stat-no-ground");
  if (legNoG) legNoG.textContent = noGroundCount;

  // TAB 1: IMPACT
  document.getElementById("val-event-date").textContent = data.event_date || "—";
  document.getElementById("val-regime").textContent = regimeName;
  document.getElementById("val-image-dates").textContent = data.image_dates_summary || "—";

  document.getElementById("val-area-obs").textContent = (areas.observed_km2 !== undefined ? areas.observed_km2.toFixed(2) : "0.00") + " km²";
  document.getElementById("val-area-inf").textContent = (areas.inferred_km2 !== undefined ? areas.inferred_km2.toFixed(2) : "0.00") + " km²";

  // Flat Terrain UI Label Adaptations
  const lblRoadsLayer = document.getElementById("lbl-roads-layer");
  const lblRoadsImpact = document.getElementById("lbl-roads-impact-title");
  const lblTagDestroyed = document.getElementById("lbl-tag-destroyed");
  const lblTagPossible = document.getElementById("lbl-tag-possible");
  const lblNoGroundDesc = document.getElementById("lbl-no-ground-desc");

  if (isFlat) {
    if (lblRoadsLayer) lblRoadsLayer.textContent = dict.road_network_flat;
    if (lblRoadsImpact) lblRoadsImpact.textContent = dict.roads_damaged_flat;
    if (lblTagDestroyed) lblTagDestroyed.textContent = dict.legend_flooded;
    if (lblTagPossible) lblTagPossible.textContent = dict.legend_possibly_flooded;
    if (lblNoGroundDesc) lblNoGroundDesc.textContent = dict.airdrop_only_flat;
  } else {
    if (lblRoadsLayer) lblRoadsLayer.textContent = dict.road_network;
    if (lblRoadsImpact) lblRoadsImpact.textContent = dict.roads_damaged;
    if (lblTagDestroyed) lblTagDestroyed.textContent = dict.legend_destroyed;
    if (lblTagPossible) lblTagPossible.textContent = dict.legend_possibly_damaged;
    if (lblNoGroundDesc) lblNoGroundDesc.textContent = dict.airdrop_only_label;
  }

  // Buildings Breakdown
  document.getElementById("val-b-affected").textContent = b.total_affected || 0;
  const bTags = document.getElementById("b-breakdown-tags");
  bTags.innerHTML = "";
  if (b.destroyed) bTags.innerHTML += `<span class="tag-pill tag-destroyed">Destroyed: <b>${b.destroyed}</b></span>`;
  if (b.damaged) bTags.innerHTML += `<span class="tag-pill tag-damaged">Damaged: <b>${b.damaged}</b></span>`;
  if (b.possibly_damaged) bTags.innerHTML += `<span class="tag-pill tag-damaged">Possibly damaged: <b>${b.possibly_damaged}</b></span>`;
  if (b.flooded) bTags.innerHTML += `<span class="tag-pill tag-flooded">Flooded: <b>${b.flooded}</b></span>`;
  if (b.possibly_flooded) bTags.innerHTML += `<span class="tag-pill tag-flooded">Possibly flooded: <b>${b.possibly_flooded}</b></span>`;
  if (!b.destroyed && !b.damaged && !b.possibly_damaged && !b.flooded && !b.possibly_flooded) {
    bTags.innerHTML = `<span class="tag-pill">0 affected buildings</span>`;
  }

  // Bridges Breakdown
  const valBrAff = document.getElementById("val-br-affected");
  if (valBrAff) valBrAff.textContent = formatBridgesSummary(br, isFlat);

  const brTags = document.getElementById("br-breakdown-tags");
  brTags.innerHTML = "";
  if (br.destroyed) brTags.innerHTML += `<span class="tag-pill tag-destroyed">Destroyed: <b>${br.destroyed}</b></span>`;
  if (br.possibly_damaged) brTags.innerHTML += `<span class="tag-pill tag-damaged">Possibly damaged: <b>${br.possibly_damaged}</b></span>`;
  if (br.flooded) brTags.innerHTML += `<span class="tag-pill tag-flooded">Flooded / impassable: <b>${br.flooded}</b></span>`;
  if (br.possibly_flooded) brTags.innerHTML += `<span class="tag-pill tag-flooded">Possibly flooded: <b>${br.possibly_flooded}</b></span>`;
  if (!br.destroyed && !br.possibly_damaged && !br.flooded && !br.possibly_flooded) {
    brTags.innerHTML = `<span class="tag-pill">0 affected bridges</span>`;
  }

  // Roads Breakdown
  document.getElementById("val-road-destroyed-km").textContent = (r.destroyed_km !== undefined ? r.destroyed_km.toFixed(1) : "0.0") + " km";
  document.getElementById("val-road-possible-km").textContent = (r.possibly_damaged_km !== undefined ? r.possibly_damaged_km.toFixed(1) : "0.0") + " km";

  // TAB 2: WHO IS CUT OFF
  document.getElementById("val-no-ground-count").textContent = noGroundCount;
  document.getElementById("val-vehicle-cut-count").textContent = vehCutCount;

  // TAB 3: WHAT TO REPAIR FIRST (Actionable Package Logic)
  const rp = m.repair_package_1 || {};
  const repHeadline = document.getElementById("repair-headline-text");
  const repSub = document.getElementById("repair-subtext");
  const repList = document.getElementById("repair-elements-list");

  if (rp.has_actionable_package && rp.element_count > 0) {
    repHeadline.textContent = `Repair Package ${rp.rank || 1}: Reconnects ${rp.reconnects_settlements} settlements / ${rp.reconnects_buildings} buildings`;
    let subMsg = `${rp.element_count} critical network link(s) prioritized for restoration`;
    if (rp.unconnectable_settlements_count > 0) {
      subMsg += ` (${rp.unconnectable_settlements_count} settlements lack repairable road elements)`;
    }
    repSub.textContent = subMsg;

    repList.innerHTML = "";
    rp.elements.forEach(elemId => {
      const li = document.createElement("li");
      li.className = "repair-elem-item";
      li.innerHTML = `<span>${elemId}</span><span>Critical Link</span>`;
      repList.appendChild(li);
    });
  } else {
    repHeadline.textContent = "No actionable road repair package identified";
    repSub.textContent = rp.unconnectable_settlements_count > 0
      ? `${rp.unconnectable_settlements_count} cut-off settlements have no drivable road network even before event (airdrop/foot access only)`
      : "No repairable road washouts found on network";
    repList.innerHTML = `<li class="empty-list-item">No specific road/bridge repairs found</li>`;
  }

  // TAB 4: HOW SURE (Validation & Provenance)
  const banner = document.getElementById("validation-banner");
  const bannerText = document.getElementById("banner-text");
  const bannerProv = document.getElementById("banner-provenance");

  bannerText.textContent = statusStr;
  bannerProv.textContent = `Source: ${data.validation_source_file || "run_summary.json"} [${data.validation_source_field || "validation_status"}]`;

  if (statusStr.includes("not validated") || statusStr.includes("weak")) {
    banner.classList.add("weak");
  } else {
    banner.classList.remove("weak");
  }

  document.getElementById("val-optical-offset").textContent = data.optical_evidence_note || "SAR backscatter only (cloud overcast)";
  document.getElementById("val-unverified-summary").textContent =
    `Buildings: ${b.unverified || 0} | Bridges: ${br.unverified || 0} | Roads: ${r.unverified_km !== undefined ? r.unverified_km.toFixed(1) : "0.0"} km`;

  const sensors = data.sensors_used ? data.sensors_used.join(", ") : "—";
  document.getElementById("val-sensors").textContent = sensors;

  const runtimeStr = data.total_duration_seconds ? `${data.total_duration_seconds}s` : "—";
  const ramStr = data.peak_ram_mb ? `${Number(data.peak_ram_mb).toFixed(0)} MB` : "—";
  document.getElementById("val-runtime-ram").textContent = `${runtimeStr} runtime | ${ramStr} peak RAM`;

  updateSettlementsFilter();
}

// ==========================================================================
// Geospatial Layer Styling & Decluttering
// ==========================================================================
async function loadHazardsLayer(runId) {
  try {
    const res = await fetch(`/api/runs/${runId}/layer/hazards`);
    const geojson = await res.json();

    geojsonLayers.hazards = L.geoJSON(geojson, {
      style: (feature) => {
        const cls = feature.properties.class || feature.properties.hazard_class;
        if (cls === 1) {
          return { color: "#2563eb", fillColor: "#2563eb", fillOpacity: 0.45, weight: 1 };
        } else if (cls === 2) {
          return { color: "#b91c1c", fillColor: "#dc2626", fillOpacity: 0.6, weight: 1.5 };
        } else if (cls === 3) {
          return { color: "#c2410c", fillColor: "#ea580c", fillOpacity: 0.45, weight: 1.5 };
        }
        return { color: "#38bdf8", fillOpacity: 0.3, weight: 1 };
      },
      onEachFeature: (feature, l) => {
        const p = feature.properties;
        const clsName = p.class === 1 ? "Class 1: Permanent Water" : p.class === 2 ? "Class 2: Observed Hazard" : "Class 3: Inferred Fill";
        l.bindPopup(`
          <div class="popup-title">${clsName}</div>
          <table class="popup-table">
            <tr><td class="prop-name">Sub-label:</td><td class="prop-val">${p.sub_label || "Hazard"}</td></tr>
            <tr><td class="prop-name">Area:</td><td class="prop-val">${p.area_m2 ? (p.area_m2 / 1e4).toFixed(2) + " ha" : "—"}</td></tr>
          </table>
        `);
      }
    });

    geojsonLayers.hazards.addTo(map);
    updateHazardFilter();
  } catch (err) {
    console.error("Error loading hazards:", err);
  }
}

function updateHazardFilter() {
  if (!geojsonLayers.hazards) return;
  const showObs = document.getElementById("layer-haz-obs").checked;
  const showInf = document.getElementById("layer-haz-inf").checked;
  const showPerm = document.getElementById("layer-haz-perm").checked;
  const showAllWater = document.getElementById("chk-all-water").checked;

  geojsonLayers.hazards.eachLayer(l => {
    const p = l.feature.properties;
    const cls = p.class || p.hazard_class;
    let visible = true;

    if (cls === 1) {
      if (!showPerm) visible = false;
      // Declutter minor ponds (Item 6): only show bodies >= 5000 m² unless showAllWater is checked
      else if (!showAllWater && p.area_m2 && p.area_m2 < 5000) visible = false;
    }
    if (cls === 2 && !showObs) visible = false;
    if (cls === 3 && !showInf) visible = false;

    if (visible) {
      if (!map.hasLayer(l)) map.addLayer(l);
    } else {
      if (map.hasLayer(l)) map.removeLayer(l);
    }
  });
}

async function loadBuildingsLayer(runId) {
  try {
    const res = await fetch(`/api/runs/${runId}/layer/buildings`);
    const geojson = await res.json();
    const showIntact = document.getElementById("layer-intact-buildings").checked;
    const chkUnverified = document.getElementById("layer-unverified-buildings");
    const showUnverified = chkUnverified ? chkUnverified.checked : false;

    if (geojsonLayers.buildings) {
      map.removeLayer(geojsonLayers.buildings);
      geojsonLayers.buildings = null;
    }

    geojsonLayers.buildings = L.geoJSON(geojson, {
      filter: (feature) => {
        const grade = feature.properties.damage_grade || "Not affected";
        if (grade === "Not affected" && !showIntact) return false;
        if ((grade.includes("cloud") || grade.includes("Unknown")) && !showUnverified) return false;
        return true;
      },
      style: (feature) => {
        const grade = feature.properties.damage_grade || "Not affected";
        if (grade === "Destroyed") {
          return { color: "#b91c1c", fillColor: "#dc2626", fillOpacity: 0.85, weight: 1.5 };
        } else if (grade === "Flooded") {
          return { color: "#1d4ed8", fillColor: "#2563eb", fillOpacity: 0.85, weight: 1.5 };
        } else if (grade === "Damaged") {
          return { color: "#c2410c", fillColor: "#ea580c", fillOpacity: 0.85, weight: 1.5 };
        } else if (grade === "Possibly flooded") {
          return { color: "#0369a1", fillColor: "#0284c7", fillOpacity: 0.85, weight: 1.5 };
        } else if (grade === "Possibly damaged") {
          return { color: "#b45309", fillColor: "#d97706", fillOpacity: 0.8, weight: 1.5 };
        } else if (grade.includes("cloud") || grade.includes("Unknown")) {
          return { color: "#64748b", fillColor: "#64748b", fillOpacity: 0.25, weight: 0.8, dashArray: "3, 3" };
        }
        return { color: "#94a3b8", fillColor: "#cbd5e1", fillOpacity: 0.2, weight: 0.5 };
      },
      pointToLayer: (feature, latlng) => {
        const grade = feature.properties.damage_grade || "Not affected";
        let fill = "#64748b";
        let stroke = "#475569";
        let radius = 3;
        let opacity = 0.8;
        let fillOpacity = 0.7;

        if (grade === "Destroyed") {
          fill = "#dc2626";
          stroke = "#b91c1c";
          radius = 5.5;
          opacity = 1;
          fillOpacity = 0.9;
        } else if (grade === "Flooded") {
          fill = "#2563eb";
          stroke = "#1d4ed8";
          radius = 5.5;
          opacity = 1;
          fillOpacity = 0.9;
        } else if (grade === "Damaged") {
          fill = "#ea580c";
          stroke = "#c2410c";
          radius = 4.5;
          opacity = 1;
          fillOpacity = 0.85;
        } else if (grade === "Possibly flooded") {
          fill = "#0284c7";
          stroke = "#0369a1";
          radius = 4.5;
          opacity = 1;
          fillOpacity = 0.85;
        } else if (grade === "Possibly damaged") {
          fill = "#d97706";
          stroke = "#b45309";
          radius = 4;
          opacity = 0.9;
          fillOpacity = 0.8;
        } else if (grade.includes("cloud") || grade.includes("Unknown")) {
          fill = "#64748b";
          stroke = "#64748b";
          radius = 2.5;
          opacity = 0.5;
          fillOpacity = 0.4;
        }

        return L.circleMarker(latlng, {
          radius: radius,
          fillColor: fill,
          color: stroke,
          weight: 1.5,
          opacity: opacity,
          fillOpacity: fillOpacity
        });
      },
      onEachFeature: (feature, l) => {
        const p = feature.properties;
        const isFlat = currentRunData && currentRunData.regime === "flat_floodplain";
        let gradeDisplay = p.damage_grade || "Unknown";
        if (isFlat) {
          if (gradeDisplay === "Destroyed") gradeDisplay = "Flooded";
          else if (gradeDisplay === "Possibly damaged") gradeDisplay = "Possibly flooded";
        }

        l.bindPopup(`
          <div class="popup-title">Building: ${p.osm_id || "Structure"}</div>
          <table class="popup-table">
            <tr><td class="prop-name">Damage State:</td><td class="prop-val">${gradeDisplay}</td></tr>
            <tr><td class="prop-name">Evidence:</td><td class="prop-val">${p.evidence_type || "Observed"}</td></tr>
            <tr><td class="prop-name">Area:</td><td class="prop-val">${p.area_m2 ? p.area_m2.toFixed(1) + " m²" : "—"}</td></tr>
          </table>
        `);
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
    const res = await fetch(`/api/runs/${runId}/layer/roads`);
    const geojson = await res.json();
    const isFlat = currentRunData && currentRunData.regime === "flat_floodplain";

    geojsonLayers.roads = L.geoJSON(geojson, {
      style: (feature) => {
        const grade = feature.properties.damage_grade || "Not affected";
        if (grade === "Destroyed") {
          return { color: "#dc2626", weight: 3.5, opacity: 0.95 };
        } else if (grade === "Possibly damaged") {
          return { color: "#ea580c", weight: 2.5, opacity: 0.9 };
        } else if (grade.includes("cloud") || grade.includes("Unknown")) {
          return { color: "#64748b", weight: 2, opacity: 0.6, dashArray: "6, 6" };
        }
        return { color: "#334155", weight: 1, opacity: 0.3 };
      },
      onEachFeature: (feature, l) => {
        const p = feature.properties;
        let gradeDisplay = p.damage_grade || "Unknown";
        if (isFlat) {
          if (gradeDisplay === "Destroyed") gradeDisplay = "Flooded / Impassable";
          else if (gradeDisplay === "Possibly damaged") gradeDisplay = "Possibly flooded";
        }

        l.bindPopup(`
          <div class="popup-title">Road Segment: ${p.highway || "Road"}</div>
          <table class="popup-table">
            <tr><td class="prop-name">Status:</td><td class="prop-val">${gradeDisplay}</td></tr>
            <tr><td class="prop-name">Type:</td><td class="prop-val">${p.highway || "Road"}</td></tr>
            <tr><td class="prop-name">OSM Way:</td><td class="prop-val">${p.osm_id || "—"}</td></tr>
          </table>
        `);
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
        let color = "#475569";
        if (grade === "Destroyed" || grade === "Flooded / impassable") color = "#dc2626";
        else if (grade === "Possibly damaged" || grade === "Possibly flooded") color = "#ea580c";
        else if (grade.includes("cloud")) color = "#64748b";

        return L.circleMarker(latlng, {
          radius: 6,
          fillColor: color,
          color: "#ffffff",
          weight: 1.5,
          opacity: 1,
          fillOpacity: 0.9
        });
      },
      onEachFeature: (feature, l) => {
        const p = feature.properties;
        l.bindPopup(`
          <div class="popup-title">Bridge: ${p.osm_id || "Structure"}</div>
          <table class="popup-table">
            <tr><td class="prop-name">Grade:</td><td class="prop-val">${p.damage_grade || "Unknown"}</td></tr>
            <tr><td class="prop-name">Rule:</td><td class="prop-val">${p.rule_triggered || "Proximity"}</td></tr>
          </table>
        `);
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
        const p = feature.properties;
        const coords = feature.geometry.coordinates;
        const { mainLabel, subCoords } = formatSettlementLabel(p, coords);

        const scenKey = currentScenario === "optimistic" ? "opt" : "pess";
        const vCut = p[`vehicle_status_${scenKey}`] === "cut_off";
        const wCut = p[`walking_status_${scenKey}`] === "cut_off";
        const isFlat = currentRunData && currentRunData.regime === "flat_floodplain";
        const noGroundAccess = vCut && wCut;

        const heliText = isFlat ? "BOAT / HELICOPTER ACCESS" : "AIR / HELICOPTER ONLY";

        l.bindPopup(`
          <div class="popup-title">${mainLabel}</div>
          <div class="settlement-sub-coords font-mono" style="margin-bottom:4px">${subCoords}</div>
          <table class="popup-table">
            <tr><td class="prop-name">Buildings:</td><td class="prop-val">${p.building_count || 0}</td></tr>
            <tr><td class="prop-name">Vehicle Access:</td><td class="prop-val">${vCut ? "<span style='color:#ef4444;font-weight:700'>CUT OFF</span>" : "Connected"}</td></tr>
            <tr><td class="prop-name">Walking Access:</td><td class="prop-val">${wCut ? "<span style='color:#ef4444;font-weight:700'>CUT OFF</span>" : "Connected"}</td></tr>
            ${noGroundAccess ? `<tr><td colspan="2" style="padding-top:4px"><span class="chip-heli">${heliText}</span></td></tr>` : ""}
          </table>
        `);
      }
    });

    if (document.getElementById("layer-settlements").checked) {
      geojsonLayers.settlements.addTo(map);
    }

    updateSettlementsFilter();
  } catch (err) {
    console.error("Error loading settlements:", err);
  }
}

// Settlement Label Formatter (Item 7: Never show raw IDs, "Near <place> (<dist> km)", lat/lon in smaller text)
function formatSettlementLabel(p, coords) {
  const name = p.name || "";
  const lon = coords[0];
  const lat = coords[1];
  const subCoords = `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E`;

  if (name.includes("nearest named place: ")) {
    let parts = name.split("nearest named place: ")[1];
    if (parts.endsWith(")")) parts = parts.slice(0, -1);
    return { mainLabel: `Near ${parts}`, subCoords };
  }

  if (name.startsWith("Place node/") || name.startsWith("node/") || name.startsWith("Cluster")) {
    if (p.nearest_named_place && p.dist_to_named_place_km !== undefined) {
      return { mainLabel: `Near ${p.nearest_named_place} (${p.dist_to_named_place_km.toFixed(1)} km)`, subCoords };
    }
    return { mainLabel: `Settlement near ${subCoords}`, subCoords };
  }

  const cleanName = name.split("(")[0].strip ? name.split("(")[0].strip() : name.split("(")[0].trim();
  return { mainLabel: cleanName || "Settlement", subCoords };
}

function getSettlementMarkerStyle(p) {
  const isCut = checkSettlementCutoff(p);
  const scenKey = currentScenario === "optimistic" ? "opt" : "pess";
  const vCut = p[`vehicle_status_${scenKey}`] === "cut_off";
  const wCut = p[`walking_status_${scenKey}`] === "cut_off";
  const heli = vCut && wCut;

  if (isCut) {
    if (heli) {
      return {
        radius: 8.5,
        fillColor: "#7f1d1d",
        color: "#fecaca",
        weight: 2,
        opacity: 1,
        fillOpacity: 0.95
      };
    }
    return {
      radius: 7,
      fillColor: "#dc2626",
      color: "#ffffff",
      weight: 1.5,
      opacity: 1,
      fillOpacity: 0.9
    };
  } else {
    return {
      radius: 4,
      fillColor: "#16a34a",
      color: "#ffffff",
      weight: 1,
      opacity: 0.7,
      fillOpacity: 0.6
    };
  }
}

function checkSettlementCutoff(props) {
  const scenKey = currentScenario === "optimistic" ? "opt" : "pess";
  if (currentMode === "vehicle") {
    return props[`vehicle_status_${scenKey}`] === "cut_off";
  } else {
    return props[`walking_status_${scenKey}`] === "cut_off";
  }
}

function updateSettlementsFilter() {
  if (!geojsonLayers.settlements) return;

  const listEl = document.getElementById("settlements-list");
  const countBadge = document.getElementById("directory-count-badge");
  const showConnected = document.getElementById("chk-show-connected-settlements").checked;
  const isFlat = currentRunData && currentRunData.regime === "flat_floodplain";

  listEl.innerHTML = "";
  const cutoffs = [];
  let noGroundTotal = 0;
  let vehicleCutTotal = 0;

  geojsonLayers.settlements.eachLayer(l => {
    const feat = l.feature;
    const p = feat.properties;
    const scenKey = currentScenario === "optimistic" ? "opt" : "pess";
    const vCut = p[`vehicle_status_${scenKey}`] === "cut_off";
    const wCut = p[`walking_status_${scenKey}`] === "cut_off";

    if (vCut && wCut) noGroundTotal++;
    if (vCut) vehicleCutTotal++;

    const isCut = checkSettlementCutoff(p);
    l.setStyle(getSettlementMarkerStyle(p));

    // Declutter (Item 6): Show only cut-off settlements by default on map
    if (!isCut && !showConnected) {
      if (map.hasLayer(l)) map.removeLayer(l);
    } else {
      if (!map.hasLayer(l) && document.getElementById("layer-settlements").checked) map.addLayer(l);
    }

    if (isCut) {
      cutoffs.push(feat);
    }
  });

  const elNoGround = document.getElementById("val-no-ground-count");
  if (elNoGround) elNoGround.textContent = noGroundTotal;
  const elVehCut = document.getElementById("val-vehicle-cut-count");
  if (elVehCut) elVehCut.textContent = vehicleCutTotal;
  if (countBadge) countBadge.textContent = `${cutoffs.length} items`;

  // Sync micro-legend and KPI settlement counts
  const legCut = document.getElementById("legend-stat-cutoff-road");
  if (legCut) legCut.textContent = vehicleCutTotal;
  const legNoG = document.getElementById("legend-stat-no-ground");
  if (legNoG) legNoG.textContent = noGroundTotal;

  const kpiValS = document.getElementById("kpi-val-settlements");
  const kpiLblS = document.getElementById("kpi-lbl-settlements");
  if (kpiValS) kpiValS.textContent = vehicleCutTotal;
  if (kpiLblS) kpiLblS.innerHTML = `<span class="dot-semantic dot-cutoff"></span><span>${vehicleCutTotal} cut off (${noGroundTotal} no ground)</span>`;

  if (cutoffs.length === 0) {
    listEl.innerHTML = `<li class="empty-list-item">No cut-off settlements under current transport filter.</li>`;
    return;
  }

  // Sort descending by building count
  cutoffs.sort((a, b) => (b.properties.building_count || 0) - (a.properties.building_count || 0));

  cutoffs.forEach(feat => {
    const p = feat.properties;
    const coords = feat.geometry.coordinates;
    const { mainLabel, subCoords } = formatSettlementLabel(p, coords);

    const scenKey = currentScenario === "optimistic" ? "opt" : "pess";
    const vCut = p[`vehicle_status_${scenKey}`] === "cut_off";
    const wCut = p[`walking_status_${scenKey}`] === "cut_off";
    const heliOnly = vCut && wCut;
    const heliText = isFlat ? "Boat / Helicopter" : "Helicopter Only";

    const li = document.createElement("li");
    li.className = "settlement-item";
    li.innerHTML = `
      <div class="settlement-item-head">
        <span class="settlement-name">${mainLabel}</span>
        <span class="settlement-bld font-mono">${p.building_count || 0} bld</span>
      </div>
      <div class="settlement-sub-coords font-mono">${subCoords}</div>
      <div class="settlement-status-bar">
        <span class="status-chip ${vCut ? 'chip-cutoff' : 'chip-connected'}">Veh: ${vCut ? 'CUT' : 'OK'}</span>
        <span class="status-chip ${wCut ? 'chip-cutoff' : 'chip-connected'}">Walk: ${wCut ? 'CUT' : 'OK'}</span>
        ${heliOnly ? `<span class="status-chip chip-heli">${heliText}</span>` : ""}
      </div>
    `;

    li.addEventListener("click", () => {
      map.setView([coords[1], coords[0]], 15);
      geojsonLayers.settlements.eachLayer(layer => {
        if (layer.feature === feat) {
          if (!map.hasLayer(layer)) map.addLayer(layer);
          layer.openPopup();
        }
      });
    });

    listEl.appendChild(li);
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

    const roadsRes = await fetch(`/api/runs/${runId}/layer/roads`);
    const roadsGeo = await roadsRes.json();

    const repairFeatures = roadsGeo.features.filter(f => pkgElems.has(f.properties.osm_id));

    geojsonLayers.repair_packages = L.geoJSON({ type: "FeatureCollection", features: repairFeatures }, {
      style: {
        color: "#38bdf8",
        weight: 5,
        opacity: 0.95
      },
      onEachFeature: (feature, l) => {
        l.bindPopup(`
          <div class="popup-title" style="color:#38bdf8">Repair Package Priority Element</div>
          <table class="popup-table">
            <tr><td class="prop-name">OSM Way:</td><td class="prop-val">${feature.properties.osm_id}</td></tr>
            <tr><td class="prop-name">Type:</td><td class="prop-val">${feature.properties.highway}</td></tr>
          </table>
        `);
      }
    });

    if (document.getElementById("layer-repair-pkg").checked) {
      geojsonLayers.repair_packages.addTo(map);
    }
  } catch (err) {
    console.error("Error loading repair packages layer:", err);
  }
}

// ==========================================================================
// Sentinel-2 Cloud-Masked Median Composite Split Slider (Item 8)
// ==========================================================================
function initS2Slider() {
  const toggleBtn = document.getElementById("btn-toggle-s2-slider");
  const closeBtn = document.getElementById("btn-close-s2-slider");
  const sliderBar = document.getElementById("s2-slider-bar");
  const rangeInput = document.getElementById("s2-range-slider");
  const zoomDamageBtn = document.getElementById("btn-zoom-damage-slider");

  toggleBtn.addEventListener("click", () => {
    toggleS2BeforeAfterSlider(!s2OverlayActive);
  });

  closeBtn.addEventListener("click", () => {
    toggleS2BeforeAfterSlider(false);
  });

  rangeInput.addEventListener("input", (e) => {
    updateS2SplitClip(e.target.value);
  });

  if (zoomDamageBtn) {
    zoomDamageBtn.addEventListener("click", () => {
      if (currentRunData) zoomToDamagedArea(currentRunData);
    });
  }
}

async function toggleS2BeforeAfterSlider(activate) {
  const toggleBtn = document.getElementById("btn-toggle-s2-slider");
  const sliderBar = document.getElementById("s2-slider-bar");
  s2OverlayActive = activate;

  if (!activate) {
    sliderBar.classList.add("hidden");
    toggleBtn.classList.remove("active");
    if (s2PreOverlay) { map.removeLayer(s2PreOverlay); s2PreOverlay = null; }
    if (s2PostOverlay) { map.removeLayer(s2PostOverlay); s2PostOverlay = null; }
    return;
  }

  if (!currentRunData || !currentRunData.bbox || currentRunData.bbox.length !== 4) return;

  const [w, s, e, n] = currentRunData.bbox;
  const bounds = [[s, w], [n, e]];

  try {
    const metaRes = await fetch(`/api/runs/${currentRunId}/s2-meta`);
    const s2Meta = await metaRes.json();

    document.getElementById("s2-pre-date").textContent = s2Meta.pre ? s2Meta.pre.date_range : "PRE";
    document.getElementById("s2-post-date").textContent = s2Meta.post ? s2Meta.post.date_range : "POST";

    sliderBar.classList.remove("hidden");
    toggleBtn.classList.add("active");

    // Base: Pre-Event Cloud-Masked Median Composite
    s2PreOverlay = L.imageOverlay(`/api/runs/${currentRunId}/s2-image?type=pre`, bounds, {
      opacity: 1.0,
      interactive: false,
      zIndex: 500
    }).addTo(map);

    // Top: Post-Event Cloud-Masked Median Composite
    s2PostOverlay = L.imageOverlay(`/api/runs/${currentRunId}/s2-image?type=post`, bounds, {
      opacity: 1.0,
      interactive: false,
      zIndex: 510
    }).addTo(map);

    updateS2SplitClip(document.getElementById("s2-range-slider").value);

  } catch (err) {
    console.error("Failed to load S2 composites:", err);
  }
}

function updateS2SplitClip(val) {
  if (!s2PostOverlay) return;
  const imgElement = s2PostOverlay.getElement();
  if (imgElement) {
    imgElement.style.clipPath = `inset(0 0 0 ${val}%)`;
  }
}

// ==========================================================================
// PHASE 2: Live Disaster Assessment Pipeline Execution & Progressive Layers
// ==========================================================================
let activePollInterval = null;
let liveRunStartTime = null;
let liveLoadedLayers = new Set();
let liveDrawRect = null;

function initPhase2Controls() {
  const btnNewRun = document.getElementById("btn-new-run");
  const modal = document.getElementById("new-run-modal");
  const btnClose = document.getElementById("btn-close-modal");
  const btnCancel = document.getElementById("btn-cancel-new-run");
  const form = document.getElementById("new-run-form");
  const btnDraw = document.getElementById("btn-draw-bbox");
  const btnCancelDraw = document.getElementById("btn-cancel-draw");
  const drawBanner = document.getElementById("draw-bbox-banner");
  const btnMinimize = document.getElementById("btn-minimize-progress");
  const progressWidget = document.getElementById("live-progress-widget");

  if (!btnNewRun || !modal) return;

  btnNewRun.addEventListener("click", () => {
    modal.classList.remove("hidden");
    document.getElementById("new-run-error").classList.add("hidden");
  });

  const closeModal = () => modal.classList.add("hidden");
  btnClose.addEventListener("click", closeModal);
  btnCancel.addEventListener("click", closeModal);

  if (btnMinimize && progressWidget) {
    btnMinimize.addEventListener("click", () => {
      progressWidget.classList.add("hidden");
    });
  }

  // Preset Buttons
  document.querySelectorAll(".btn-preset").forEach(btn => {
    btn.addEventListener("click", () => {
      const p = btn.getAttribute("data-preset");
      if (p === "trishuli") {
        document.getElementById("input-event-name").value = "Trishuli Monsoon Assessment";
        document.getElementById("input-event-date").value = "2026-08-26";
        document.getElementById("input-bbox-w").value = "85.3000";
        document.getElementById("input-bbox-s").value = "28.1000";
        document.getElementById("input-bbox-e").value = "85.4200";
        document.getElementById("input-bbox-n").value = "28.2500";
      } else if (p === "melamchi") {
        document.getElementById("input-event-name").value = "Melamchi Debris Flow Assessment";
        document.getElementById("input-event-date").value = "2021-06-15";
        document.getElementById("input-bbox-w").value = "85.5300";
        document.getElementById("input-bbox-s").value = "27.8000";
        document.getElementById("input-bbox-e").value = "85.6200";
        document.getElementById("input-bbox-n").value = "27.9500";
      } else if (p === "assam") {
        document.getElementById("input-event-name").value = "Assam Flood Inundation Assessment";
        document.getElementById("input-event-date").value = "2024-07-02";
        document.getElementById("input-bbox-w").value = "92.6500";
        document.getElementById("input-bbox-s").value = "26.5000";
        document.getElementById("input-bbox-e").value = "93.1500";
        document.getElementById("input-bbox-n").value = "26.9000";
      }
    });
  });

  // Interactive BBox Drawing on Map
  if (btnDraw) {
    btnDraw.addEventListener("click", () => {
      modal.classList.add("hidden");
      drawBanner.classList.remove("hidden");

      let startLatLng = null;
      let isDrawing = false;
      map.dragging.disable();

      const onMouseDown = (e) => {
        isDrawing = true;
        startLatLng = e.latlng;
        if (liveDrawRect) map.removeLayer(liveDrawRect);
        liveDrawRect = L.rectangle([startLatLng, startLatLng], {
          color: "#38bdf8",
          weight: 2,
          dashArray: "5, 5",
          fillOpacity: 0.15
        }).addTo(map);
      };

      const onMouseMove = (e) => {
        if (!isDrawing || !startLatLng) return;
        liveDrawRect.setBounds(L.latLngBounds(startLatLng, e.latlng));
      };

      const onMouseUp = () => {
        if (!isDrawing) return;
        isDrawing = false;
        map.off("mousedown", onMouseDown);
        map.off("mousemove", onMouseMove);
        map.off("mouseup", onMouseUp);
        map.dragging.enable();
        drawBanner.classList.add("hidden");

        if (liveDrawRect) {
          const bounds = liveDrawRect.getBounds();
          const w = bounds.getWest().toFixed(4);
          const s = bounds.getSouth().toFixed(4);
          const e = bounds.getEast().toFixed(4);
          const n = bounds.getNorth().toFixed(4);

          document.getElementById("input-bbox-w").value = w;
          document.getElementById("input-bbox-s").value = s;
          document.getElementById("input-bbox-e").value = e;
          document.getElementById("input-bbox-n").value = n;
        }
        modal.classList.remove("hidden");
      };

      map.on("mousedown", onMouseDown);
      map.on("mousemove", onMouseMove);
      map.on("mouseup", onMouseUp);

      btnCancelDraw.onclick = () => {
        isDrawing = false;
        map.off("mousedown", onMouseDown);
        map.off("mousemove", onMouseMove);
        map.off("mouseup", onMouseUp);
        map.dragging.enable();
        if (liveDrawRect) { map.removeLayer(liveDrawRect); liveDrawRect = null; }
        drawBanner.classList.add("hidden");
        modal.classList.remove("hidden");
      };
    });
  }

  // Form Submit
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const errBox = document.getElementById("new-run-error");
    errBox.classList.add("hidden");

    const eventName = document.getElementById("input-event-name").value.trim();
    const eventDate = document.getElementById("input-event-date").value.trim();
    const w = parseFloat(document.getElementById("input-bbox-w").value);
    const s = parseFloat(document.getElementById("input-bbox-s").value);
    const eLon = parseFloat(document.getElementById("input-bbox-e").value);
    const n = parseFloat(document.getElementById("input-bbox-n").value);

    if (isNaN(w) || isNaN(s) || isNaN(eLon) || isNaN(n)) {
      errBox.textContent = "Please provide valid numeric coordinates for all 4 bounding box bounds.";
      errBox.classList.remove("hidden");
      return;
    }

    if (w >= eLon || s >= n) {
      errBox.textContent = "Invalid bounding box: West must be < East and South must be < North.";
      errBox.classList.remove("hidden");
      return;
    }

    const submitBtn = document.getElementById("btn-submit-new-run");
    submitBtn.disabled = true;
    submitBtn.innerHTML = "<span>⏳</span> Launching...";

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
        const errData = await resp.json();
        throw new Error(errData.detail || "Failed to start assessment");
      }

      const resData = await resp.json();
      modal.classList.add("hidden");
      startLiveMonitoring(resData.run_id, [w, s, eLon, n], eventName, eventDate);

    } catch (err) {
      errBox.textContent = err.message || "Failed to start pipeline";
      errBox.classList.remove("hidden");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span class="btn-icon">🚀</span> Start Assessment Pipeline';
    }
  });
}

function startLiveMonitoring(runId, bbox, eventName, eventDate) {
  if (activePollInterval) clearInterval(activePollInterval);
  liveRunStartTime = Date.now();
  liveLoadedLayers.clear();

  const widget = document.getElementById("live-progress-widget");
  const cardTitle = document.getElementById("progress-card-title");
  const metaDesc = document.getElementById("progress-meta-desc");
  const readyTags = document.getElementById("progress-ready-tags");
  const fill = document.getElementById("progress-bar-fill");
  const msg = document.getElementById("progress-current-msg");
  const pulse = document.getElementById("progress-pulse-dot");

  widget.classList.remove("hidden");
  cardTitle.textContent = eventName || "Disaster Assessment Pipeline";
  metaDesc.textContent = `Date: ${eventDate} | BBox: [${bbox.join(", ")}]`;
  readyTags.innerHTML = "";
  fill.style.width = "5%";
  fill.style.background = "linear-gradient(90deg, #38bdf8, #60a5fa)";
  msg.textContent = "Initializing pipeline execution...";
  pulse.style.background = "#38bdf8";

  // Reset Stepper
  ["l0", "l1", "l2", "l4", "l5"].forEach(k => {
    const el = document.getElementById(`step-${k}`);
    if (el) el.className = "step-item";
  });
  ["l0-l1", "l1-l2", "l2-l4", "l4-l5"].forEach(k => {
    const el = document.getElementById(`line-${k}`);
    if (el) el.className = "step-line";
  });
  document.getElementById("step-l0").className = "step-item active";

  // Zoom map to bounding box
  const [w, s, e, n] = bbox;
  map.fitBounds([[s, w], [n, e]], { padding: [50, 50], maxZoom: 14 });

  // Draw assessment bounds
  if (liveDrawRect) map.removeLayer(liveDrawRect);
  liveDrawRect = L.rectangle([[s, w], [n, e]], {
    color: "#38bdf8",
    weight: 2,
    dashArray: "4, 4",
    fillOpacity: 0.05
  }).addTo(map);

  activePollInterval = setInterval(async () => {
    const elapsedSec = Math.floor((Date.now() - liveRunStartTime) / 1000);
    const mins = String(Math.floor(elapsedSec / 60)).padStart(2, "0");
    const secs = String(elapsedSec % 60).padStart(2, "0");
    document.getElementById("progress-elapsed").textContent = `${mins}:${secs}`;

    try {
      const resp = await fetch(`/api/runs/${runId}/status`);
      if (!resp.ok) return;
      const statusData = await resp.json();

      fill.style.width = `${Math.max(5, statusData.progress_pct || 5)}%`;
      msg.textContent = statusData.current_step || "Processing...";

      // Update Stepper
      const stage = statusData.stage || "";
      if (stage.includes("L1")) {
        setStepDone("l0");
        setStepActive("l1");
        setLineDone("l0-l1");
      } else if (stage.includes("L2")) {
        setStepDone("l0"); setStepDone("l1");
        setStepActive("l2");
        setLineDone("l0-l1"); setLineDone("l1-l2");
      } else if (stage.includes("L4")) {
        setStepDone("l0"); setStepDone("l1"); setStepDone("l2");
        setStepActive("l4");
        setLineDone("l0-l1"); setLineDone("l1-l2"); setLineDone("l2-l4");
      } else if (stage.includes("L5")) {
        setStepDone("l0"); setStepDone("l1"); setStepDone("l2"); setStepDone("l4");
        setStepActive("l5");
        setLineDone("l0-l1"); setLineDone("l1-l2"); setLineDone("l2-l4"); setLineDone("l4-l5");
      }

      // Progressive Layer Rendering on Map
      const outs = statusData.outputs || {};
      if (outs.hazard_polygons_geojson && !liveLoadedLayers.has("hazards")) {
        liveLoadedLayers.add("hazards");
        loadHazardsLayer(runId);
        addReadyTag("✓ Hazard Extent Ready");
      }
      if (outs.buildings_graded_geojson && !liveLoadedLayers.has("buildings")) {
        liveLoadedLayers.add("buildings");
        loadBuildingsLayer(runId);
        addReadyTag("✓ Buildings Graded");
      }
      if (outs.roads_graded_geojson && !liveLoadedLayers.has("roads")) {
        liveLoadedLayers.add("roads");
        loadRoadsLayer(runId);
        addReadyTag("✓ Roads Graded");
      }
      if (outs.settlements_geojson && !liveLoadedLayers.has("settlements")) {
        liveLoadedLayers.add("settlements");
        loadSettlementsLayer(runId);
        addReadyTag("✓ Settlements Evaluated");
      }

      // Check Completion
      if (statusData.is_finished) {
        clearInterval(activePollInterval);
        activePollInterval = null;

        if (statusData.status === "COMPLETED") {
          ["l0", "l1", "l2", "l4", "l5"].forEach(setStepDone);
          ["l0-l1", "l1-l2", "l2-l4", "l4-l5"].forEach(setLineDone);
          cardTitle.textContent = "✓ Assessment Completed";
          pulse.style.background = "#10b981";
          fill.style.background = "#10b981";
          fill.style.width = "100%";
          addReadyTag("✓ Complete");
          
          await loadRunsList();
          const select = document.getElementById("run-select");
          select.value = runId;
          loadRun(runId);

        } else if (statusData.status === "DEGRADED") {
          ["l0", "l1", "l2", "l4", "l5"].forEach(setStepDone);
          ["l0-l1", "l1-l2", "l2-l4", "l4-l5"].forEach(setLineDone);
          cardTitle.textContent = "⚠️ Completed (DEGRADED)";
          pulse.style.background = "#f59e0b";
          fill.style.background = "#f59e0b";
          fill.style.width = "100%";
          msg.textContent = "Optical imagery cloud-obscured; SAR fallback used.";
          addReadyTag("⚠️ Degraded");

          await loadRunsList();
          const select = document.getElementById("run-select");
          select.value = runId;
          loadRun(runId);

        } else if (statusData.status === "FAILED") {
          cardTitle.textContent = "✕ Assessment Failed";
          pulse.style.background = "#ef4444";
          fill.style.background = "#ef4444";
          msg.textContent = statusData.error || "Analysis failed.";
        }
      }

    } catch (e) {
      console.warn("Poll error:", e);
    }
  }, 1500);
}

function setStepActive(id) {
  const el = document.getElementById(`step-${id}`);
  if (el) el.className = "step-item active";
}

function setStepDone(id) {
  const el = document.getElementById(`step-${id}`);
  if (el) el.className = "step-item completed";
}

function setLineDone(id) {
  const el = document.getElementById(`line-${id}`);
  if (el) el.className = "step-line completed";
}

function addReadyTag(text) {
  const container = document.getElementById("progress-ready-tags");
  if (!container) return;
  const tag = document.createElement("span");
  tag.className = "tag-ready";
  tag.textContent = text;
  container.appendChild(tag);
}

/* ==========================================
   PHASE 3: COPILOT & SITREP INTERACTION
   ========================================== */
function initSitrepControls() {
  const dropdownWrap = document.getElementById("sitrep-dropdown-wrap");
  const btn = document.getElementById("btn-download-sitrep");
  const menu = document.getElementById("sitrep-menu");
  const linkEn = document.getElementById("link-sitrep-en");
  const linkNe = document.getElementById("link-sitrep-ne");
  const tabEn = document.getElementById("tab-sitrep-en-btn");
  const tabNe = document.getElementById("tab-sitrep-ne-btn");

  if (btn && menu) {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      menu.classList.toggle("hidden");
    });

    document.addEventListener("click", () => {
      menu.classList.add("hidden");
    });
  }

  function downloadSitrep(lang) {
    if (!currentRunId) {
      alert("Please select a disaster assessment run first.");
      return;
    }
    const url = `/api/runs/${currentRunId}/sitrep?lang=${lang}&format=pdf`;
    window.open(url, "_blank");
  }

  if (linkEn) linkEn.addEventListener("click", (e) => { e.preventDefault(); downloadSitrep("en"); });
  if (linkNe) linkNe.addEventListener("click", (e) => { e.preventDefault(); downloadSitrep("ne"); });
  if (tabEn) tabEn.addEventListener("click", (e) => { e.preventDefault(); downloadSitrep("en"); });
  if (tabNe) tabNe.addEventListener("click", (e) => { e.preventDefault(); downloadSitrep("ne"); });
}

function initCopilot() {
  const form = document.getElementById("copilot-form");
  const input = document.getElementById("copilot-input");
  const chips = document.querySelectorAll(".copilot-chip");
  const sourcesToggle = document.getElementById("copilot-sources-toggle");
  const sourcesContent = document.getElementById("copilot-sources-content");

  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      const q = chip.getAttribute("data-q");
      if (input) input.value = q;
      askCopilot(q);
    });
  });

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = input.value.trim();
      if (!q) return;
      askCopilot(q);
    });
  }

  if (sourcesToggle && sourcesContent) {
    sourcesToggle.addEventListener("click", () => {
      sourcesContent.classList.toggle("hidden");
      const icon = sourcesToggle.querySelector(".sources-toggle-icon");
      if (icon) {
        icon.textContent = sourcesContent.classList.contains("hidden") ? "▶" : "▼";
      }
    });
  }
}

async function askCopilot(question) {
  if (!currentRunId) {
    alert("Please select an assessment run first.");
    return;
  }

  const answerBox = document.getElementById("copilot-answer-text");
  const runLabelEl = document.getElementById("copilot-run-label");
  const engineLabelEl = document.getElementById("copilot-engine-label");
  const badgeEl = document.getElementById("copilot-mode-badge");
  const countEl = document.getElementById("copilot-source-count");
  const listEl = document.getElementById("copilot-sources-list");
  const sendBtn = document.getElementById("copilot-send-btn");

  if (sendBtn) {
    sendBtn.disabled = true;
    sendBtn.textContent = "Thinking...";
  }

  if (answerBox) {
    answerBox.textContent = `Consulting copilot on "${question}"...`;
  }

  try {
    const res = await fetch(`/api/runs/${currentRunId}/copilot/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question })
    });

    const data = await res.json();

    if (runLabelEl) runLabelEl.textContent = `Run: ${data.run_label || currentRunId}`;
    if (engineLabelEl) {
      const provStr = data.provider === "offline" ? "Offline rule engine" : `${data.provider}/${data.model}`;
      engineLabelEl.textContent = `Path: ${data.answer_path || "offline"} (${provStr})`;
    }

    if (badgeEl) {
      if (data.provider === "offline" || (data.answer && data.answer.includes("[ANSWERED IN OFFLINE MODE]"))) {
        badgeEl.textContent = "Offline verified";
        badgeEl.style.background = "#f1f5f9";
        badgeEl.style.color = "#475569";
      } else {
        badgeEl.textContent = `${data.provider}`;
        badgeEl.style.background = "#dbeafe";
        badgeEl.style.color = "#1e40af";
      }
    }

    if (answerBox) {
      answerBox.textContent = data.answer || "No response received.";
    }

    // Populate sources accordion
    const sources = data.sources || [];
    if (countEl) countEl.textContent = sources.length;
    if (listEl) {
      listEl.innerHTML = "";
      if (sources.length === 0) {
        const li = document.createElement("li");
        li.textContent = "General assessed boundaries (processed outputs)";
        listEl.appendChild(li);
      } else {
        sources.forEach(s => {
          const li = document.createElement("li");
          const valStr = s.value !== undefined ? ` = ${s.value}${s.unit && s.unit !== "count" ? " " + s.unit : ""}` : "";
          li.textContent = `${s.file} [${s.field}]${valStr}`;
          listEl.appendChild(li);
        });
      }
    }

  } catch (err) {
    console.error("Copilot error:", err);
    if (answerBox) {
      answerBox.textContent = `[ANSWERED IN OFFLINE MODE]\nError querying copilot: ${err.message}`;
    }
  } finally {
    if (sendBtn) {
      sendBtn.disabled = false;
      sendBtn.textContent = "Ask";
    }
  }
}
