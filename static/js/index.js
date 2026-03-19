// tab switching
function setActiveTab(el) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  el.classList.add("active");
}

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
