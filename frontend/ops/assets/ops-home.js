const els={apiKey:document.getElementById("api-key"),notice:document.getElementById("notice"),ready:document.getElementById("stat-ready"),blockers:document.getElementById("stat-blockers"),ownerTeams:document.getElementById("stat-owner-teams"),alerts:document.getElementById("stat-alerts"),refreshBtn:document.getElementById("refresh-btn")};
const keyStore="lsa-ops-api-key";
const statState={blockers:0,ownerTeams:0,alerts:0};
const core=window.LSAOps;
core.restoreApiKey(els.apiKey,keyStore);

function setNotice(t,c=""){core.setNotice(els.notice,t,c,"notice")}

async function load(){
  setNotice("Loading status...");
  try{
    const [readiness,alerts]=await Promise.all([
      core.fetchJson("/maintenance/control-plane-deployment-readiness",els.apiKey,keyStore),
      core.fetchJson("/control-plane-alerts?limit=50",els.apiKey,keyStore),
    ]);
    els.ready.textContent=readiness.ready?"yes":"no";
    core.animateNumber(els.blockers,statState,"blockers",readiness.blockers.length||0);
    core.animateNumber(els.ownerTeams,statState,"ownerTeams",readiness.blocked_owner_team_count||0);
    core.animateNumber(els.alerts,statState,"alerts",(alerts||[]).filter(a=>a.status!=="healthy").length);
    core.pulse('.stat,.card,.hero,.nav',10,50,560);
    setNotice("Status loaded.","good");
  }catch(e){
    setNotice(String(e.message||e),"bad");
  }
}

els.refreshBtn.addEventListener("click",load);
load();
