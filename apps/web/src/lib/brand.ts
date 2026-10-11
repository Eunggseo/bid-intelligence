// CLIENT Bid Assistant — single-tenant, chatbot-only MVP for Road Construction Company.
// This is NOT the multi-tenant platform (that's Plumb). It's CLIENT's internal copilot:
// ask about plans, gotchas, quantities, bid history, competitors — cited to the source.
export const BRAND = {
  name: "CLIENT Bidding Intelligence",
  short: "CLIENT",
  tagline: "Ask the plans.",
  mark: "◆",
  company: "Road Construction Company.",
  blurb: "Your estimating copilot — reads the plan set, flags the gotchas, cites every figure.",
  // The signed-in estimator (single-tenant MVP → hardcoded for now; driven by login later).
  user: { name: "Adam", initial: "A" },
};
