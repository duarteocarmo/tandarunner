// add visualizastions for graphs
document.addEventListener("DOMContentLoaded", function () {
  const visualizations = JSON.parse(
    document.getElementById("visualizations").textContent
  );

  const vega_theme = "default";

  Object.keys(visualizations).forEach(function (key) {
    const spec = JSON.parse(visualizations[key]);
    vegaEmbed("#" + key, spec, {
      renderer: "svg",
      actions: false,
      theme: vega_theme,
    });
  });
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
  state.generating = true;

  const messageInput = document.getElementById("messageinput");
  const sendMessage = document.getElementById("sendMessage");

  messageInput.classList.add("loading");
  sendMessage.disabled = true;
  messageInput.disabled = true;

  if (!state.allowSwaps) {
    event.preventDefault();
  }

  if (event.detail.fragment.attributes === undefined) {
    state.allowSwaps = true;
    messageInput.classList.remove("loading");
    sendMessage.disabled = false;
    messageInput.disabled = false;
    messageInput.focus();
    state.generating = false;
  }
});
