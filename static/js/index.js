// tab switching
function switchTab(tabName, el) {
  document
    .querySelectorAll(".tab")
    .forEach((t) => t.classList.remove("active"));
  el.classList.add("active");

  document.querySelectorAll("[id^='tab-']").forEach(function (pane) {
    if (pane.id === "tab-" + tabName) {
      pane.classList.remove("tab-pane-hidden");
    } else if (!pane.closest(".tab-bar")) {
      pane.classList.add("tab-pane-hidden");
    }
  });

  if (tabName === "graphs" && window._vegaThemeChanged) {
    window._vegaThemeChanged = false;
    renderVegaCharts();
  }
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
    spec.background = "transparent";
    vegaEmbed("#" + key, spec, {
      renderer: "svg",
      actions: false,
      theme: vega_theme,
    });
  });
}

document.addEventListener("htmx:afterSettle", function (event) {
  if (event.detail.target.id === "tab-graphs") {
    renderVegaCharts();
  }
});

window
  .matchMedia("(prefers-color-scheme: dark)")
  .addEventListener("change", function () {
    if (!document.getElementById("tab-graphs").classList.contains("tab-pane-hidden")) {
      renderVegaCharts();
    } else {
      // flag to re-render when graphs tab becomes visible
      window._vegaThemeChanged = true;
    }
  });

// auto-resize chat textarea
document.addEventListener("htmx:afterSettle", function (event) {
  if (event.detail.target.id === "tab-chat") {
    const textareaEle = document.getElementById("messageinput");
    if (textareaEle) {
      textareaEle.addEventListener("input", () => {
        textareaEle.style.height = "auto";
        textareaEle.style.height = textareaEle.scrollHeight + "px";
      });
    }
  }
});

// enable chat once graph data is loaded
document.addEventListener("htmx:afterSettle", function (event) {
  if (event.detail.target.id === "tab-graphs") {
    const textareaEle = document.getElementById("messageinput");
    const sendButton = document.getElementById("sendMessage");
    if (textareaEle) {
      textareaEle.placeholder = "Say something...";
      textareaEle.disabled = false;
    }
    if (sendButton) {
      sendButton.disabled = false;
    }
  }
});

// enable plan form once graph data is loaded
document.addEventListener("htmx:afterSettle", function (event) {
  if (event.detail.target.id === "tab-graphs") {
    var planGoal = document.getElementById("plan-goal");
    var planSubmit = document.getElementById("plan-submit");
    if (planGoal) planGoal.disabled = false;
    if (planSubmit) planSubmit.disabled = false;
  }
});

// after sending message, clear input box and reset height
document.addEventListener("htmx:wsAfterSend", function () {
  var chatInput = document.getElementById("messageinput");
  if (chatInput) {
    chatInput.value = "";
    chatInput.style.height = "auto";
  }
  var examples = document.getElementById("chat-examples");
  if (examples) examples.remove();
});

function sendExample(message) {
  var input = document.getElementById("messageinput");
  if (!input || input.disabled) return;
  input.value = message;
  document.getElementById("sendMessage").click();
}

// scroll to bottom of chat after receiving a message
document.addEventListener("htmx:wsAfterMessage", function () {
  var chatUI = document.getElementById("message-list");
  if (chatUI) chatUI.scrollTop = chatUI.scrollHeight;
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
