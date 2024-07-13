// add visualizations for graphs
document.addEventListener("DOMContentLoaded", function () {
  const visualizations = JSON.parse(
    document.getElementById("visualizations").textContent
  );

  function getVegaTheme() {
    return window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "default";
  }

  function applyVegaTheme() {
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

  applyVegaTheme();

  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", applyVegaTheme);
});

// adjust text box height based on content
document.addEventListener("DOMContentLoaded", () => {
  const textareaEle = document.getElementById("messageinput");
  textareaEle.addEventListener("input", () => {
    textareaEle.style.height = "auto";
    textareaEle.style.height = `${textareaEle.scrollHeight}px`;
  });
});

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
  document.getElementById("stopMessage").addEventListener("click", function () {
    if (state.generating) {
      state.allowSwaps = false;
    }
  });
});
document.addEventListener("htmx:oobBeforeSwap", function (event) {
  var numMessages = document.getElementById("message-list").childElementCount;
  if (numMessages == 0) {
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
