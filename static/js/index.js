// tab switching
function setActiveTab(el) {
  document
    .querySelectorAll(".tab")
    .forEach((t) => t.classList.remove("active"));
  el.classList.add("active");
}

// vega chart rendering with theme support
function getVegaTheme() {
  return window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "default";
}

function renderVegaCharts() {
  const el = document.getElementById("visualizations");
  if (!el) return;

  const visualizations = JSON.parse(el.textContent);
  const vega_theme = getVegaTheme();
  Object.keys(visualizations).forEach(function (key) {
    const spec = JSON.parse(visualizations[key]);
    vegaEmbed("#" + key, spec, {
      renderer: "svg",
      actions: false,
      theme: vega_theme,
    });
  });
}

document.addEventListener("htmx:afterSettle", function (event) {
  renderVegaCharts();
});

window
  .matchMedia("(prefers-color-scheme: dark)")
  .addEventListener("change", renderVegaCharts);

// after sending message, clear input box and reset height
document.addEventListener("htmx:wsAfterSend", function () {
  document.getElementById("messageinput").value = "";
  document.getElementById("messageinput").style.height = "auto";
});

// scroll to bottom of chat after receiving a message
document.addEventListener("htmx:wsAfterMessage", function () {
  const chatUI = document.getElementById("message-list");
  chatUI.scrollTop = chatUI.scrollHeight;
});

// handle state and cancellation while generating
const state = {
  allowSwaps: true,
  generating: false,
};
document.addEventListener("DOMContentLoaded", function () {
  document.addEventListener("click", function (event) {
    if (event.target.id === "stopMessage" && state.generating) {
      state.allowSwaps = false;
    }
    if (event.target.id === "resetChat") {
      state.allowSwaps = true;
      state.generating = false;
    }
  });
});
document.addEventListener("htmx:oobBeforeSwap", function (event) {
  var messageList = document.getElementById("message-list");
  if (!messageList || messageList.childElementCount == 0) {
    return;
  }

  state.generating = true;

  const messageInput = document.getElementById("messageinput");
  const sendMessage = document.getElementById("sendMessage");

  sendMessage.disabled = true;
  messageInput.disabled = true;

  if (!state.allowSwaps) {
    event.preventDefault();
  }

  if (event.detail.fragment.attributes === undefined) {
    state.allowSwaps = true;
    sendMessage.disabled = false;
    messageInput.disabled = false;
    messageInput.focus();
    state.generating = false;
  }
});
