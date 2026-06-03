import express from "express";

function buildApprovedApp() {
  const app = express();
  app.use(express.json({ limit: "1mb" }));

  app.get("/", (_req, res) => {
    res.json({
      service: "lsa-approved-target",
      status: "ok",
      mode: "approved",
    });
  });

  app.post("/", (req, res) => {
    res.json({
      service: "lsa-approved-target",
      accepted: true,
      mode: "approved",
      body: req.body ?? null,
    });
  });

  app.post("/probe/approved", (_req, res) => {
    res.json({
      service: "lsa-approved-target",
      status: "probe-ok",
      mode: "approved",
    });
  });

  app.post("/v1/charges", (req, res) => {
    res.status(200).json({
      service: "lsa-approved-target",
      route: "charges",
      accepted: true,
      amount: req.body?.amount ?? null,
      charge_id: `ch_${Date.now()}`,
    });
  });

  app.post("/v1/refunds", (req, res) => {
    res.status(200).json({
      service: "lsa-approved-target",
      route: "refunds",
      accepted: true,
      amount: req.body?.amount ?? null,
      refund_id: `rf_${Date.now()}`,
    });
  });

  app.post("/v3/messages", (req, res) => {
    res.status(200).json({
      service: "lsa-approved-target",
      route: "messages",
      accepted: true,
      email: req.body?.email ?? null,
    });
  });

  app.post("/v1/entries", (req, res) => {
    res.status(200).json({
      service: "lsa-approved-target",
      route: "entries",
      accepted: true,
      entry_id: req.body?.entry_id ?? null,
      amount: req.body?.amount ?? null,
    });
  });

  app.post("/v1/track", (req, res) => {
    res.status(200).json({
      service: "lsa-approved-target",
      route: "track",
      accepted: true,
      event: req.body?.event ?? null,
      customer_id: req.body?.customer_id ?? null,
    });
  });

  return app;
}

function buildDriftApp() {
  const app = express();
  app.use(express.json({ limit: "1mb" }));

  app.get("/", (_req, res) => {
    res.json({
      service: "lsa-drift-target",
      status: "ok",
      mode: "drift",
    });
  });

  app.post("/", (req, res) => {
    res.json({
      service: "lsa-drift-target",
      accepted: true,
      mode: "drift",
      body: req.body ?? null,
    });
  });

  app.post("/probe/drift", (_req, res) => {
    res.json({
      service: "lsa-drift-target",
      status: "probe-ok",
      mode: "drift",
    });
  });

  app.post("/exfil", (req, res) => {
    res.status(200).json({
      service: "lsa-drift-target",
      route: "exfil",
      accepted: true,
      suspicious: true,
      body: req.body ?? null,
    });
  });

  return app;
}

const approvedPort = Number(process.env.LSA_APPROVED_TARGET_PORT || 4011);
const driftPort = Number(process.env.LSA_DRIFT_TARGET_PORT || 4012);
const host = process.env.LSA_TARGET_HOST || "127.0.0.1";

const approved = buildApprovedApp();
const drift = buildDriftApp();

approved.listen(approvedPort, host, () => {
  console.log(`approved target live at http://${host}:${approvedPort}`);
});

drift.listen(driftPort, host, () => {
  console.log(`drift target live at http://${host}:${driftPort}`);
});
