const title = document.querySelector("#panelTitle");
const description = document.querySelector("#panelDescription");
const preview = document.querySelector("#preview");
document.querySelector("#previewBtn").addEventListener("click", () => {
  preview.textContent = `${title.value.trim() || "Contact Support"}\n\n${description.value.trim() || "Choose the button below to open a support ticket."}\n\n[ Open Ticket ]`;
});
 
