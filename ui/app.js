const apiBaseInput = document.getElementById("apiBase");
const vendorIdInput = document.getElementById("vendorId");
const llmProviderSelect = document.getElementById("llmProvider");
const ollamaBaseUrlInput = document.getElementById("ollamaBaseUrl");
const ollamaModelInput = document.getElementById("ollamaModel");
const contractInput = document.getElementById("contractFile");
const invoicesInput = document.getElementById("invoicesFile");
const usageInput = document.getElementById("usageFile");
const fileStatus = document.getElementById("fileStatus");
const ingestBtn = document.getElementById("ingestBtn");
const briefBtn = document.getElementById("briefBtn");
const output = document.getElementById("briefOutput");
const requestId = document.getElementById("requestId");
const draftEmail = document.getElementById("draftEmail");
const refreshToggle = document.getElementById("refreshToggle");
const checkHealth = document.getElementById("checkHealth");
const apiStatus = document.getElementById("apiStatus");

const runtimeConfig = window.RUNTIME_CONFIG || {};

const llmOptions = Array.isArray(runtimeConfig.LLM_OPTIONS)
  ? runtimeConfig.LLM_OPTIONS
  : [
      { value: "mock", label: "Mock (heuristic)" },
      { value: "ollama", label: "Ollama" },
    ];

llmOptions.forEach((option) => {
  const entry = document.createElement("option");
  entry.value = option.value;
  entry.textContent = option.label || option.value;
  llmProviderSelect.appendChild(entry);
});

const selectedFiles = {
  contract: null,
  invoices: null,
  usage: null,
};

function setFileStatus(message) {
  fileStatus.textContent = message;
}

function apiBase() {
  return apiBaseInput.value.replace(/\/$/, "");
}

function vendorId() {
  return vendorIdInput.value.trim() || "vendor_123";
}

function updateFromInputs() {
  selectedFiles.contract = contractInput.files[0] || selectedFiles.contract;
  selectedFiles.invoices = invoicesInput.files[0] || selectedFiles.invoices;
  selectedFiles.usage = usageInput.files[0] || selectedFiles.usage;

  const names = Object.entries(selectedFiles)
    .filter(([, value]) => Boolean(value))
    .map(([key, value]) => `${key}: ${value.name}`);
  setFileStatus(names.length ? names.join(" | ") : "No files selected yet.");
}

async function checkApiHealth() {
  apiStatus.textContent = "Checking...";
  try {
    const response = await fetch(`${apiBase()}/health`);
    if (!response.ok) {
      throw new Error("API unreachable");
    }
    const payload = await response.json();
    apiStatus.textContent = `OK (commit ${payload.commit || "unknown"})`;
  } catch (error) {
    apiStatus.textContent = "Not reachable";
  }
}

async function ingestFiles() {
  updateFromInputs();
  const formData = new FormData();
  if (selectedFiles.contract) {
    formData.append("contract", selectedFiles.contract);
  }
  if (selectedFiles.invoices) {
    formData.append("invoices", selectedFiles.invoices);
  }
  if (selectedFiles.usage) {
    formData.append("usage", selectedFiles.usage);
  }

  if ([...formData.keys()].length === 0) {
    setFileStatus("Please choose at least one file to ingest.");
    return;
  }

  ingestBtn.disabled = true;
  ingestBtn.textContent = "Uploading...";
  output.textContent = "Sending ingestion request...";

  try {
    const response = await fetch(
      `${apiBase()}/ingest?vendor_id=${encodeURIComponent(vendorId())}`,
      {
        method: "POST",
        body: formData,
      }
    );

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Ingestion failed");
    }
    output.textContent = JSON.stringify(payload, null, 2);
  } catch (error) {
    output.textContent = `Error: ${error.message}`;
  } finally {
    ingestBtn.disabled = false;
    ingestBtn.textContent = "Upload & ingest";
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function formatEmailBody(body) {
  if (!body) return "";
  const escaped = escapeHtml(body);
  return escaped.replace(/\n/g, "<br>");
}

async function generateBrief() {
  briefBtn.disabled = true;
  briefBtn.textContent = "Working...";
  output.textContent = "Running the agent...";
  draftEmail.innerHTML = '<p class="waiting">Running the agent...</p>';

  const llmProvider = llmProviderSelect.value || null;
  const ollamaBaseUrl = ollamaBaseUrlInput.value.trim() || null;
  const ollamaModel = ollamaModelInput.value.trim() || null;

  try {
    const response = await fetch(
      `${apiBase()}/renewal-brief?vendor_id=${encodeURIComponent(vendorId())}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          refresh: refreshToggle.checked,
          llm_provider: llmProvider,
          ollama_base_url: llmProvider === "ollama" ? ollamaBaseUrl : null,
          ollama_model: llmProvider === "ollama" ? ollamaModel : null,
        }),
      }
    );

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Brief generation failed");
    }

    output.textContent = JSON.stringify(payload, null, 2);
    requestId.textContent = payload.request_id || "Unknown";
    
    if (payload.brief && payload.brief.draft_email) {
      const email = payload.brief.draft_email;
      draftEmail.innerHTML = `
        <div class="email-subject">${escapeHtml(email.subject || "No subject")}</div>
        <div class="email-body">${formatEmailBody(email.body || "")}</div>
      `;
    } else {
      draftEmail.innerHTML = '<p class="waiting">No draft email in response.</p>';
    }
  } catch (error) {
    output.textContent = `Error: ${error.message}`;
    draftEmail.innerHTML = `<p class="error">Error: ${escapeHtml(error.message)}</p>`;
  } finally {
    briefBtn.disabled = false;
    briefBtn.textContent = "Generate brief";
  }
}

contractInput.addEventListener("change", updateFromInputs);
invoicesInput.addEventListener("change", updateFromInputs);
usageInput.addEventListener("change", updateFromInputs);
checkHealth.addEventListener("click", checkApiHealth);
ingestBtn.addEventListener("click", ingestFiles);
briefBtn.addEventListener("click", generateBrief);

if (runtimeConfig.API_BASE_URL) {
  apiBaseInput.value = runtimeConfig.API_BASE_URL;
}

if (runtimeConfig.DEFAULT_LLM_PROVIDER) {
  llmProviderSelect.value = runtimeConfig.DEFAULT_LLM_PROVIDER;
}

if (runtimeConfig.OLLAMA_BASE_URL) {
  ollamaBaseUrlInput.value = runtimeConfig.OLLAMA_BASE_URL;
}

if (runtimeConfig.OLLAMA_MODEL) {
  ollamaModelInput.value = runtimeConfig.OLLAMA_MODEL;
}
