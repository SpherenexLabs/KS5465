function el(id){ return document.getElementById(id); }

const fbStatus = el("fbStatus");
const vLine = el("vLine");
const vDensity = el("vDensity");
const vCount = el("vCount");
const vOcc = el("vOcc");
const vTraffic = el("vTraffic");
const vStatus = el("vStatus");
const vMode = el("vMode");
const vSignal = el("vSignal");
const vGreenTime = el("vGreenTime");
const lampR = el("lampR");
const lampY = el("lampY");
const lampG = el("lampG");
const btnToggleMode = el("btnToggleMode");
const btnManualToasts = el("btnManualToasts");
const toast = el("toast");
const modal = el("modal");
const modalTitle = el("modalTitle");
const modalMsg = el("modalMsg");
const modalOk = el("modalOk");

function setLamp(signal){
  lampR.classList.remove("on");
  lampY.classList.remove("on");
  lampG.classList.remove("on");
  if(signal==="RED") lampR.classList.add("on");
  if(signal==="YELLOW") lampY.classList.add("on");
  if(signal==="GREEN") lampG.classList.add("on");
}

function showToast(msg){
  toast.textContent = msg;
  toast.classList.add("show");
  setTimeout(()=>toast.classList.remove("show"), 3500);
}

function showModal(title, msg){
  console.log("showModal called:", title, msg);
  if(!modal) {
    console.error("Modal element not found!");
    return;
  }
  modalTitle.textContent = title;
  modalMsg.textContent = msg;
  modal.classList.add("show");
  document.body.style.overflow = "hidden";
}

function hideModal(){
  if(!modal) return;
  modal.classList.remove("show");
  document.body.style.overflow = "";
}

if(modalOk) {
  modalOk.onclick = hideModal;
}

if(modal) {
  modal.onclick = (e) => {
    if(e.target === modal) {
      hideModal();
    }
  };
}

document.addEventListener('keydown', (e) => {
  if(e.key === 'Escape' && modal && modal.classList.contains('show')) {
    hideModal();
  }
});

function trafficLabelFromCount(count){
  const c = Number(count);
  if(!Number.isFinite(c) || c <= 0) return "No traffic";
  if(c <= 3) return "Low traffic";
  if(c <= 8) return "Moderate traffic";
  return "Heavy traffic";
}

let lastDensity = null;
let lastMode = null;
let activeMode = "A";
let controlsBound = false;
let currentSignal = null;

function normalizeSeconds(val){
  const n = Number(val);
  if(!Number.isFinite(n)) return null;
  return Math.max(0, Math.floor(n));
}

setTimeout(()=>{
  if(!controlsBound){
    setModeUI("A");
    bindButtons();
  }
}, 100);

const chart = new Chart(el("chart"), {
  type: "line",
  data: {
    labels: [],
    datasets: [
      { 
        label: "Density (0/1)", 
        data: [],
        borderColor: 'rgb(99, 102, 241)',
        backgroundColor: 'rgba(99, 102, 241, 0.1)',
        tension: 0.4,
        fill: true
      },
      { 
        label: "Vehicle Count", 
        data: [],
        borderColor: 'rgb(236, 72, 153)',
        backgroundColor: 'rgba(236, 72, 153, 0.1)',
        tension: 0.4,
        fill: true
      },
      { 
        label: "Occupancy %", 
        data: [],
        borderColor: 'rgb(20, 184, 166)',
        backgroundColor: 'rgba(20, 184, 166, 0.1)',
        tension: 0.4,
        fill: true
      }
    ]
  },
  options: { 
    responsive: true, 
    animation: { duration: 750 },
    interaction: {
      mode: 'index',
      intersect: false
    },
    plugins: {
      legend: {
        labels: {
          color: 'rgb(203, 213, 225)',
          font: {
            size: 12,
            weight: '600'
          }
        }
      }
    },
    scales: { 
      y: { 
        beginAtZero: true,
        grid: {
          color: 'rgba(255, 255, 255, 0.05)'
        },
        ticks: {
          color: 'rgb(148, 163, 184)'
        }
      },
      x: {
        grid: {
          color: 'rgba(255, 255, 255, 0.05)'
        },
        ticks: {
          color: 'rgb(148, 163, 184)',
          maxRotation: 45,
          minRotation: 45
        }
      }
    }
  }
});

function updateChart(logs){
  const last = logs.slice(-60);
  chart.data.labels = last.map(x=>{
    const d = new Date(x.ts || Date.now());
    return `${d.getHours()}:${String(d.getMinutes()).padStart(2,"0")}:${String(d.getSeconds()).padStart(2,"0")}`;
  });
  chart.data.datasets[0].data = last.map(x=> Number(x.Density ?? 0));
  chart.data.datasets[1].data = last.map(x=> Number(x.Count||0));
  chart.data.datasets[2].data = last.map(x=> Number(x.OccPct||0));
  chart.update();
}

async function apiPost(url, body){
  const r = await fetch(url, {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify(body||{})
  });
  if(!r.ok){
    const t = await r.text();
    throw new Error(t);
  }
  return r.json();
}

function setModeUI(mode){
  activeMode = mode === "M" ? "M" : "A";
  const displayText = activeMode === "M" ? "MANUAL" : "AUTO";
  const icon = activeMode === "M" ? "⚙️" : "⚡";
  
  const btnIcon = btnToggleMode.querySelector('.btnIcon');
  const btnText = btnToggleMode.querySelector('.btnText');
  
  if(btnIcon) btnIcon.textContent = icon;
  if(btnText) btnText.textContent = `Mode: ${displayText}`;
  
  btnToggleMode.classList.toggle("primary", activeMode === "A");
  btnToggleMode.classList.toggle("danger", activeMode === "M");
  vMode.textContent = `Mode: ${displayText}`;

  const isManual = activeMode === "M";
  [
    el("forceGreen"),
    el("forceYellow"),
    el("forceRed"),
    ...document.querySelectorAll("[data-line]")
  ].forEach(button=>{
    if(!button) return;
    button.disabled = !isManual;
    button.style.opacity = isManual ? "1" : "0.5";
  });
}

function bindButtons(){
  if(controlsBound) return;
  controlsBound = true;
  
  console.log("Binding buttons...");

  if(btnToggleMode) {
    btnToggleMode.onclick = async ()=>{
      console.log("Mode toggle clicked, current mode:", activeMode);
      const next = activeMode === "A" ? "M" : "A";
      btnToggleMode.disabled = true;
      
      // Optimistically update UI immediately
      setModeUI(next);
      
      try{
        await apiPost("/api/mode", { mode: next });
        const modeText = next === "A" ? "AUTO Mode" : "MANUAL Mode";
        const icon = next === "A" ? "⚡" : "⚙️";
        showToast(`${icon} Switched to ${modeText}`);
        console.log("Mode updated successfully to:", next);
      }catch(err){
        console.error("Mode toggle error:", err);
        // Revert UI on error
        const revert = next === "A" ? "M" : "A";
        setModeUI(revert);
        showModal("⚠️ Mode Update Failed", String(err.message || err));
      }finally{
        btnToggleMode.disabled = false;
      }
    };
  }

  const forceGreen = el("forceGreen");
  if(forceGreen) {
    forceGreen.onclick = async ()=>{
      console.log("Force GREEN clicked, activeMode:", activeMode);
      if(activeMode !== "M") {
        showToast("⚠️ Switch to MANUAL mode first");
        return;
      }
      try{
        await apiPost("/api/force", { signal:"GREEN" });
        showModal("🟢 Signal Override", "Traffic signal forced to GREEN in Manual mode.");
      }catch(err){
        console.error("Force GREEN error:", err);
        showModal("❌ Error", String(err.message || err));
      }
    };
  }
  
  const forceYellow = el("forceYellow");
  if(forceYellow) {
    forceYellow.onclick = async ()=>{
      console.log("Force YELLOW clicked, activeMode:", activeMode);
      if(activeMode !== "M") {
        showToast("⚠️ Switch to MANUAL mode first");
        return;
      }
      try{
        await apiPost("/api/force", { signal:"YELLOW" });
        showModal("🟡 Signal Override", "Traffic signal forced to YELLOW in Manual mode.");
      }catch(err){
        console.error("Force YELLOW error:", err);
        showModal("❌ Error", String(err.message || err));
      }
    };
  }
  
  const forceRed = el("forceRed");
  if(forceRed) {
    forceRed.onclick = async ()=>{
      console.log("Force RED clicked, activeMode:", activeMode);
      if(activeMode !== "M") {
        showToast("⚠️ Switch to MANUAL mode first");
        return;
      }
      try{
        await apiPost("/api/force", { signal:"RED" });
        showModal("🔴 Signal Override", "Traffic signal forced to RED in Manual mode.");
      }catch(err){
        console.error("Force RED error:", err);
        showModal("❌ Error", String(err.message || err));
      }
    };
  }

  document.querySelectorAll("[data-line]").forEach(btn=>{
    btn.onclick = async ()=>{
      console.log("Lane button clicked, activeMode:", activeMode);
      if(activeMode !== "M") {
        showToast("⚠️ Switch to MANUAL mode first");
        return;
      }
      const ln = Number(btn.getAttribute("data-line"));
      try{
        await apiPost("/api/force", { line: ln });
        showModal("🛣️ Lane Override", `Traffic lane forced to Lane ${ln} in Manual mode.`);
      }catch(err){
        console.error("Lane button error:", err);
        showModal("❌ Error", String(err.message || err));
      }
    };
  });
}

if(btnManualToasts) {
  btnManualToasts.onclick = ()=> {
    console.log("Test Alert clicked");
    showToast("🔔 This is a test notification alert!");
    showModal("🔔 Test Modal", "This is a test modal alert popup. Everything is working correctly!");
  };
}

async function startFirebaseWatch(){
  console.log("[FB] Starting Firebase watch...");
  const wait = (ms)=>new Promise(r=>setTimeout(r,ms));
  for(let i=0;i<60;i++){
    if(window.__FB__) break;
    await wait(100);
  }
  if(!window.__FB__){
    fbStatus.textContent = "Firebase: SDK not loaded";
    console.error("[FB] Firebase SDK failed to load");
    return;
  }

  console.log("[FB] Firebase SDK loaded successfully");
  const { db, ref, onValue, query, limitToLast } = window.__FB__;
  console.log("[FB] Attempting to connect to Traffic_Manage...");

  const root = ref(db, "Traffic_Manage");
  onValue(root, (snap)=>{
    const v = snap.val();
    console.log("[FB] Data received:", v);
    
    if(!v){
      fbStatus.textContent = "Firebase: No data (check rules)";
      console.warn("[FB] No data at Traffic_Manage - check Database Rules");
      return;
    }
    
    fbStatus.textContent = "Firebase: Connected";

    const mode = (v.Mode || "A").toUpperCase();
    const line = v.Line ?? "-";
    const density = v.Density ?? "-";
    const rawCount = v.Count;
    const countNum = Number(rawCount);
    const count = Number.isFinite(countNum) ? countNum : 0;
    const occ = v.OccPct ?? "-";
    const signal = (v.Signal || "RED").toUpperCase();
    const trafficLabel = trafficLabelFromCount(count);
    const systemStatus = v.Status || trafficLabel;
    const seconds = normalizeSeconds(v.Seconds ?? v.TimeLeft);

    // Only update UI if mode actually changed
    if(mode !== activeMode){
      console.log(`Mode synced from Firebase: ${activeMode} -> ${mode}`);
      setModeUI(mode);
    }
    
    vLine.textContent = line;
    vDensity.textContent = density;
    vCount.textContent = count;
    vOcc.textContent = (typeof occ === "number") ? `${occ.toFixed(1)} %` : `${occ}`;
    vSignal.textContent = signal;
    if(signal !== currentSignal){
      currentSignal = signal;
    }
    vGreenTime.textContent = (seconds === null) ? "-" : `${seconds} s`;
    vStatus.textContent = systemStatus;
    vTraffic.textContent = trafficLabel;

    setLamp(signal);

    bindButtons();
    
    // Only show mode change toast if this wasn't triggered by user action
    if(mode !== lastMode){
      lastMode = mode;
    }

    if(lastDensity !== null && Number(density) !== Number(lastDensity)){
      if(Number(density) === 1){
        showModal("Heavy Traffic Alert", `Line ${line} is experiencing heavy traffic congestion. System automatically allocating more green time.`);
      }
    }
    lastDensity = density;
  }, (err)=>{
    const errMsg = err?.code || err?.message || "Permission denied";
    fbStatus.textContent = `Firebase: ${errMsg}`;
    console.error("[FB] Connection error:", err);
    
    if(errMsg.includes("permission") || errMsg.includes("denied")){
      setTimeout(()=>{
        showModal("Firebase Rules Required", 'Database read blocked. Please go to Firebase Console -> Realtime Database -> Rules and set: { "rules": { ".read": true, ".write": true } }');
      }, 1000);
    }
  });

  const logsQ = query(ref(db, "Traffic_Manage/Logs"), limitToLast(200));
  onValue(logsQ, (snap)=>{
    const obj = snap.val() || {};
    const arr = Object.values(obj).sort((a,b)=>(a.ts||0)-(b.ts||0));
    updateChart(arr);
  }, ()=>{});
}

startFirebaseWatch();