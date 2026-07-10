const DEFAULT_HOOK_URL = "https://getspm.com/v1/agent-memory-hooks/openclaw";

export default async function handler(event) {
  if (event?.type !== "message" || !["received", "sent"].includes(event?.action)) {
    return;
  }
  if (event.action === "sent" && event?.context?.success === false) {
    return;
  }
  const token = String(process.env.SPM_AGENT_TOKEN || "").trim();
  if (!token) {
    console.warn("[spm-memory] SPM_AGENT_TOKEN is not configured; event was not persisted");
    return;
  }
  const endpoint = String(process.env.SPM_AGENT_HOOK_URL || DEFAULT_HOOK_URL).trim();
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json"
      },
      body: JSON.stringify(event),
      signal: AbortSignal.timeout(75000)
    });
    if (!response.ok) {
      const detail = (await response.text()).slice(0, 1000);
      console.warn(`[spm-memory] lifecycle capture failed (${response.status}): ${detail}`);
    }
  } catch (error) {
    console.warn(`[spm-memory] lifecycle capture unavailable: ${String(error)}`);
  }
}
