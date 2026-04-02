const settingsModal = document.getElementById("settingsModal");
function openSettingsModal() {
    settingsModal.style.display = "flex";
}
function closeSettingsModal() {
    settingsModal.style.display = "none";
}
settingsModal.onclick = function(e) {
    if (e.target === settingsModal) closeSettingsModal();
}