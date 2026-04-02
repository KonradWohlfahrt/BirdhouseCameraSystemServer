function showMessage(text, type = "info", duration = 3000) {
  const container = document.getElementById("notificationContainer");

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = text;

  container.appendChild(toast);

  setTimeout(() => toast.classList.add("show"), 50);

  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, duration);
}
function showSuccess(msg) { showMessage(msg, "success"); }
function showError(msg) { showMessage(msg, "error"); console.error(msg); }
function showWarning(msg) { showMessage(msg, "warning"); }