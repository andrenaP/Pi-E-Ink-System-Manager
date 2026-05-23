chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "unlockSelection",
      title: "🔓 Unlock Text Selection on this page",
      contexts: ["page", "selection"],
    });

    chrome.contextMenus.create({
      id: "sendToEink",
      title: "📤 Send selected text to E-Ink",
      contexts: ["selection"],
    });
  });
});

// Handle Toolbar Icon Click (Sends the Entire Page)
chrome.action.onClicked.addListener((tab) => {
  console.log("Toolbar icon clicked. Scraping full page...");

  chrome.scripting
    .executeScript({
      target: { tabId: tab.id },
      func: () => document.body.innerText, // Grabs all visible text natively
    })
    .then((results) => {
      if (results && results[0] && results[0].result) {
        sendToEink(results[0].result);
      } else {
        console.error("Could not extract page text.");
      }
    });
});

// Handle Context Menu Clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "unlockSelection") {
    chrome.scripting
      .insertCSS({
        target: { tabId: tab.id },
        css: "* { user-select: text !important; -webkit-user-select: text !important; pointer-events: auto !important; }",
      })
      .then(() => console.log("Page CSS unlocked!"));
  }

  if (info.menuItemId === "sendToEink") {
    chrome.scripting
      .executeScript({
        target: { tabId: tab.id },
        func: () => window.getSelection().toString(),
      })
      .then((results) => {
        if (results && results[0] && results[0].result) {
          sendToEink(results[0].result);
        }
      });
  }
});

// Core Sending Logic
function sendToEink(text) {
  // CHANGE THIS TO YOUR E-INK DEVICE IP ON YOUR WI-FI
  const targetUrl = "http://xxx.xxx.xxx.xxx:8080/receive";

  fetch(targetUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text: text }),
  })
    .then((response) => {
      if (!response.ok) throw new Error("Server error: " + response.status);
      console.log("Successfully pushed text to E-ink!");
    })
    .catch((err) => console.error("Failed to send:", err));
}
