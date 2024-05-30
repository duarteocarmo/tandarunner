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

// send stop message to server
const socket = new WebSocket("ws://" + window.location.host + "/ws/chat/");
document.addEventListener("DOMContentLoaded", function () {
  stop_button = document.getElementById("stopMessage");

  stop_button.addEventListener("click", function () {
    socket.send(JSON.stringify({ action: "stop" }));
    console.log("stop message sent");
  });
});
