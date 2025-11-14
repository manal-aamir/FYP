// Wrap ALL JavaScript in the Office.onReady initializer
Office.onReady((info) => {
    
  // === Globals ===
  const API_BASE_URL = "http://127.0.0.1:5001";
  const textArea = document.getElementById("inputText");
  const outputEl = document.getElementById("output");
  const jsonOutputEl = document.getElementById("raw-json-output");
  const loaderEl = document.getElementById("loader");
  const statusBadge = document.getElementById("status-badge");
  const tabs = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");
  let lastRawJson = { "status": "No analysis run yet." };

  // === Word Add-in Specific Logic ===
  if (info.host === Office.HostType.Word) {
      console.log("Running inside Word. Initializing selection handler.");
      
      // Function to get Word's current selection and update our textbox
      async function syncSelection() {
          try {
              await Word.run(async (context) => {
                  const selection = context.document.getSelection();
                  selection.load("text"); // Ask Word to load the text of the selection
                  await context.sync(); // Wait for Word to respond
                  
                  // Update the textbox with the selected text
                  if (selection.text.trim() !== "") {
                      textArea.value = selection.text;
                  } else {
                      // If selection is empty, clear the box
                      textArea.value = "";
                      textArea.placeholder = "— (empty selection) —";
                  }
              });
          } catch (error) {
              console.error("Error syncing selection:", error);
          }
      }

      // Add an event listener to Word.
      // This fires every time the user clicks or highlights something new.
      Office.context.document.addHandlerAsync(
          Office.EventType.DocumentSelectionChanged,
          syncSelection,
          (asyncResult) => {
              if (asyncResult.status === Office.AsyncResultStatus.Failed) {
                  console.error("Failed to add selection handler: " + asyncResult.error.message);
              } else {
                  console.log("Selection handler added successfully.");
              }
          }
      );
      
      // Run it once right at the start
      syncSelection();
  } else {
      // If not in Word (e.g., in a browser), skip Word-specific logic
      console.log("Not running in Word. Selection sync disabled.");
  }

  // === API Helper ===
  async function post(action, text, extra = {}) {
      
      // Check if text is empty BEFORE sending to server
      if (!text || text.trim() === "") {
          showError("The text box is empty. Please select text in Word or type something to analyze.");
          lastRawJson = { "error": "Input text was empty." };
          updateJsonTab();
          return null; // Stop the function here
      }

      setLoading(true);
      try {
          const res = await fetch(`${API_BASE_URL}/process`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ action, text, ...extra })
          });
          if (!res.ok) {
              const errData = await res.json();
              throw new Error(errData.error || `Server error: ${res.status}`);
          }
          const data = await res.json();
          lastRawJson = data; // Save raw JSON
          return data;
      } catch (error) {
          console.error("Fetch error:", error);
          lastRawJson = { "error": error.message };
          showError(error.message);
          return null; // Return null on error
      } finally {
          setLoading(false);
          updateJsonTab(); // Update JSON tab regardless of outcome
      }
  }

  // === UI Helpers ===
  function setLoading(state = true) {
      loaderEl.style.display = state ? "block" : "none";
      if (state) {
          outputEl.innerHTML = ""; // Clear previous results
          activateTab("summary"); // Switch to summary tab
      }
  }

  function activateTab(tabId) {
      tabs.forEach(tab => {
          const isActive = tab.getAttribute('data-tab') === tabId;
          tab.classList.toggle('active', isActive);
      });
      tabContents.forEach(content => {
          content.classList.toggle('hidden', content.id !== tabId);
      });
  }
  
  function showError(message) {
      outputEl.innerHTML = `
          <h3 style="color: var(--accent-red);">Error</h3>
          <pre>${message}</pre>
      `;
      activateTab("summary");
  }

  function updateJsonTab() {
      jsonOutputEl.textContent = JSON.stringify(lastRawJson, null, 2);
  }

  // === Event Listeners ===

  // Tab Switching
  tabs.forEach(tab => {
      tab.addEventListener("click", () => {
          activateTab(tab.getAttribute('data-tab'));
      });
  });
  
  // Clear Button
  document.getElementById("clearBtn").addEventListener("click", () => {
      textArea.value = "";
      outputEl.innerHTML = '<p class="placeholder">Select an action to see the results here.</p>';
      lastRawJson = { "status": "Cleared." };
      updateJsonTab();
      activateTab("summary");
  });

  // === Action Button Click Handlers ===

  // 1. Expand Acronyms
  document.getElementById("btnExpand").onclick = async () => {
      const data = await post("expand", textArea.value);
      if (!data) return;

      outputEl.innerHTML = `
          <h3>Acronym Expansion</h3>
          <pre>${data.result || "(no change)"}</pre>
      `;
      if (document.getElementById("replaceCheck").checked) {
          textArea.value = data.result;
          // Also update Word
          replaceSelectionInWord(data.result);
      }
  };

  // 2. Format Citations
  document.getElementById("btnCitation").onclick = async () => {
      const data = await post("citation", textArea.value, { style: "apa" });
      if (!data) return;
      
      outputEl.innerHTML = `
          <h3>Citation Formatting</h3>
          <h4>Detected: ${data.detected || "N/A"}</h4>
          <pre>${data.result || "(no change)"}</pre>
      `;
      if (document.getElementById("replaceCheck").checked) {
          textArea.value = data.result;
          // Also update Word
          replaceSelectionInWord(data.result);
      }
  };

  // 3. Rewrite Section [MODIFIED]
  document.getElementById("btnRewrite").onclick = async () => {
      const data = await post("rewrite", textArea.value);
      if (!data) return;

      // Helper function to create an "Accept" button
      const createAcceptButton = (rewriteType, rewriteText) => {
          const btn = document.createElement('button');
          btn.className = 'small-btn';
          btn.innerHTML = `✅ Accept ${rewriteType}`;
          btn.onclick = () => {
              textArea.value = rewriteText;
              outputEl.innerHTML = `<h3>Rewrite Applied (${rewriteType})</h3><pre>${rewriteText}</pre>`;
              if (document.getElementById("replaceCheck").checked) {
                  replaceSelectionInWord(rewriteText);
              }
          };
          return btn;
      };

      // Build the new HTML output
      let html = `
          <h3>Rewrite Suggestions</h3>
          <h4>Original:</h4>
          <pre>${data.original || ""}</pre>
          
          <h4 style="color: var(--accent-purple);">Professional:</h4>
          <pre class="suggestion">${data.professional || "(No suggestion)"}</pre>
          <div class="buttons" id="btn-container-pro"></div>
          
          <h4 style="color: var(--accent-green);">Concise:</h4>
          <pre class="suggestion">${data.concise || "(No suggestion)"}</pre>
          <div class="buttons" id="btn-container-con"></div>
          
          <h4 style="color: var(--accent-blue);">Simpler:</h4>
          <pre class="suggestion">${data.simpler || "(No suggestion)"}</pre>
          <div class="buttons" id="btn-container-sim"></div>
      `;
      
      outputEl.innerHTML = html;

      // Add the buttons to the DOM
      if (data.professional && !data.professional.startsWith("Error:")) {
          document.getElementById("btn-container-pro").appendChild(
              createAcceptButton("Professional", data.professional)
          );
      }
      if (data.concise && !data.concise.startsWith("Error:")) {
          document.getElementById("btn-container-con").appendChild(
              createAcceptButton("Concise", data.concise)
          );
      }
      if (data.simpler && !data.simpler.startsWith("Error:")) {
          document.getElementById("btn-container-sim").appendChild(
              createAcceptButton("Simpler", data.simpler)
          );
      }
  };

  // 4. Check Consistency
  document.getElementById("btnConsistency").onclick = async () => {
      const data = await post("consistency", textArea.value);
      if (!data) return;

      const results = data.consistency_results || [];
      const report = data.issues_report || "No inconsistencies detected.";
      const suggestion = data.suggested_rewrite;

      let html = `<h3>Consistency Check</h3><pre>${report}</pre>`;
      
      // Build table of contradictions
      const contradictions = results.filter(r => r.label === "CONTRADICTION");
      if (contradictions.length > 0) {
          html += `<table>
                      <tr>
                          <th>Sentence 1</th>
                          <th>Sentence 2</th>
                          <th>Verdict</th>
                      </tr>`;
          for (const r of contradictions) {
              html += `<tr>
                          <td>${r.sentence1}</td>
                          <td>${r.sentence2}</td>
                          <td style="color: var(--accent-red); font-weight: 500;">${r.verdict}</td>
                       </tr>`;
          }
          html += `</table>`;
      }

      // Add suggestion box if it exists
      if (suggestion && !suggestion.startsWith("Error:")) {
          html += `
              <h3 style="margin-top: 24px;">Suggested Fix</h3>
              <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 12px;">
                  The AI has generated a revised version to resolve the inconsistencies:
              </p>
              <pre class="suggestion" id="rewrite-suggestion">${suggestion.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</pre>
              <div class="buttons">
                  <button id="acceptFixBtn" class="small-btn">✅ Accept Fix</button>
              </div>
          `;
      }

      outputEl.innerHTML = html;

      // Add event listener for the new "Accept Fix" button
      const acceptFixBtn = document.getElementById("acceptFixBtn");
      if (acceptFixBtn) {
          acceptFixBtn.onclick = () => {
              textArea.value = suggestion;
              outputEl.innerHTML = `<h3>Rewrite Applied</h3><pre>${suggestion}</pre>`;
              // Also update Word
              if (document.getElementById("replaceCheck").checked) {
                  replaceSelectionInWord(suggestion);
              }
          };
      }
  };
  
  // === Function to write text back to Word ===
  async function replaceSelectionInWord(text) {
      if (info.host === Office.HostType.Word) {
          try {
              await Word.run(async (context) => {
                  const selection = context.document.getSelection();
                  selection.insertText(text, Word.InsertLocation.replace);
                  await context.sync();
              });
          } catch (error) {
              console.error("Error replacing text in Word:", error);
          }
      }
  }

  // === Server Connection Check ===
  async function checkConnection() {
      try {
          // We check the root URL, which is handled by app.py
          const response = await fetch(`${API_BASE_URL}/`); 
          if (response.ok) {
              statusBadge.textContent = "Online";
              statusBadge.classList.remove("offline");
              statusBadge.classList.add("online");
          } else {
              throw new Error("Server not reachable");
          }
      } catch (error) {
          statusBadge.textContent = "Offline";
          statusBadge.classList.remove("online");
          statusBadge.classList.add("offline");
      }
  }
  
  // Check connection on page load
  checkConnection();
  // And check every 10 seconds
  setInterval(checkConnection, 10000);

}); // End of Office.onReady wrapper// Wrap ALL JavaScript in the Office.onReady initializer
Office.onReady((info) => {
    
    // === Globals ===
    const API_BASE_URL = "http://127.0.0.1:5001";
    const textArea = document.getElementById("inputText");
    const outputEl = document.getElementById("output");
    const jsonOutputEl = document.getElementById("raw-json-output");
    const loaderEl = document.getElementById("loader");
    const statusBadge = document.getElementById("status-badge");
    const tabs = document.querySelectorAll(".tab-btn");
    const tabContents = document.querySelectorAll(".tab-content");
    let lastRawJson = { "status": "No analysis run yet." };

    // === Word Add-in Specific Logic ===
    if (info.host === Office.HostType.Word) {
        console.log("Running inside Word. Initializing selection handler.");
        
        // Function to get Word's current selection and update our textbox
        async function syncSelection() {
            try {
                await Word.run(async (context) => {
                    const selection = context.document.getSelection();
                    selection.load("text"); // Ask Word to load the text of the selection
                    await context.sync(); // Wait for Word to respond
                    
                    // Update the textbox with the selected text
                    if (selection.text.trim() !== "") {
                        textArea.value = selection.text;
                    } else {
                        // If selection is empty, clear the box
                        textArea.value = "";
                        textArea.placeholder = "— (empty selection) —";
                    }
                });
            } catch (error) {
                console.error("Error syncing selection:", error);
            }
        }

        // Add an event listener to Word.
        // This fires every time the user clicks or highlights something new.
        Office.context.document.addHandlerAsync(
            Office.EventType.DocumentSelectionChanged,
            syncSelection,
            (asyncResult) => {
                if (asyncResult.status === Office.AsyncResultStatus.Failed) {
                    console.error("Failed to add selection handler: " + asyncResult.error.message);
                } else {
                    console.log("Selection handler added successfully.");
                }
            }
        );
        
        // Run it once right at the start
        syncSelection();
    } else {
        // If not in Word (e.g., in a browser), skip Word-specific logic
        console.log("Not running in Word. Selection sync disabled.");
    }

    // === API Helper ===
    async function post(action, text, extra = {}) {
        
        // Check if text is empty BEFORE sending to server
        if (!text || text.trim() === "") {
            showError("The text box is empty. Please select text in Word or type something to analyze.");
            lastRawJson = { "error": "Input text was empty." };
            updateJsonTab();
            return null; // Stop the function here
        }

        setLoading(true);
        try {
            const res = await fetch(`${API_BASE_URL}/process`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action, text, ...extra })
            });
            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || `Server error: ${res.status}`);
            }
            const data = await res.json();
            lastRawJson = data; // Save raw JSON
            return data;
        } catch (error) {
            console.error("Fetch error:", error);
            lastRawJson = { "error": error.message };
            showError(error.message);
            return null; // Return null on error
        } finally {
            setLoading(false);
            updateJsonTab(); // Update JSON tab regardless of outcome
        }
    }

    // === UI Helpers ===
    function setLoading(state = true) {
        loaderEl.style.display = state ? "block" : "none";
        if (state) {
            outputEl.innerHTML = ""; // Clear previous results
            activateTab("summary"); // Switch to summary tab
        }
    }

    function activateTab(tabId) {
        tabs.forEach(tab => {
            const isActive = tab.getAttribute('data-tab') === tabId;
            tab.classList.toggle('active', isActive);
        });
        tabContents.forEach(content => {
            content.classList.toggle('hidden', content.id !== tabId);
        });
    }
    
    function showError(message) {
        outputEl.innerHTML = `
            <h3 style="color: var(--accent-red);">Error</h3>
            <pre>${message}</pre>
        `;
        activateTab("summary");
    }

    function updateJsonTab() {
        jsonOutputEl.textContent = JSON.stringify(lastRawJson, null, 2);
    }

    // === Event Listeners ===

    // Tab Switching
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            activateTab(tab.getAttribute('data-tab'));
        });
    });
    
    // Clear Button
    document.getElementById("clearBtn").addEventListener("click", () => {
        textArea.value = "";
        outputEl.innerHTML = '<p class="placeholder">Select an action to see the results here.</p>';
        lastRawJson = { "status": "Cleared." };
        updateJsonTab();
        activateTab("summary");
    });

    // === Action Button Click Handlers ===

    // 1. Expand Acronyms
    document.getElementById("btnExpand").onclick = async () => {
        const data = await post("expand", textArea.value);
        if (!data) return;

        outputEl.innerHTML = `
            <h3>Acronym Expansion</h3>
            <pre>${data.result || "(no change)"}</pre>
        `;
        if (document.getElementById("replaceCheck").checked) {
            textArea.value = data.result;
            // Also update Word
            replaceSelectionInWord(data.result);
        }
    };

    // 2. Format Citations
    document.getElementById("btnCitation").onclick = async () => {
        const data = await post("citation", textArea.value, { style: "apa" });
        if (!data) return;
        
        outputEl.innerHTML = `
            <h3>Citation Formatting</h3>
            <h4>Detected: ${data.detected || "N/A"}</h4>
            <pre>${data.result || "(no change)"}</pre>
        `;
        if (document.getElementById("replaceCheck").checked) {
            textArea.value = data.result;
            // Also update Word
            replaceSelectionInWord(data.result);
        }
    };

    // 3. Rewrite Section [MODIFIED]
    document.getElementById("btnRewrite").onclick = async () => {
        const data = await post("rewrite", textArea.value);
        if (!data) return;

        // Helper function to create an "Accept" button
        const createAcceptButton = (rewriteType, rewriteText) => {
            const btn = document.createElement('button');
            btn.className = 'small-btn';
            btn.innerHTML = `✅ Accept ${rewriteType}`;
            btn.onclick = () => {
                textArea.value = rewriteText;
                outputEl.innerHTML = `<h3>Rewrite Applied (${rewriteType})</h3><pre>${rewriteText}</pre>`;
                if (document.getElementById("replaceCheck").checked) {
                    replaceSelectionInWord(rewriteText);
                }
            };
            return btn;
        };

        // Build the new HTML output
        let html = `
            <h3>Rewrite Suggestions</h3>
            <h4>Original:</h4>
            <pre>${data.original || ""}</pre>
            
            <h4 style="color: var(--accent-purple);">Professional:</h4>
            <pre class="suggestion">${data.professional || "(No suggestion)"}</pre>
            <div class="buttons" id="btn-container-pro"></div>
            
            <h4 style="color: var(--accent-green);">Concise:</h4>
            <pre class="suggestion">${data.concise || "(No suggestion)"}</pre>
            <div class="buttons" id="btn-container-con"></div>
            
            <h4 style="color: var(--accent-blue);">Simpler:</h4>
            <pre class="suggestion">${data.simpler || "(No suggestion)"}</pre>
            <div class="buttons" id="btn-container-sim"></div>
        `;
        
        outputEl.innerHTML = html;

        // Add the buttons to the DOM
        if (data.professional && !data.professional.startsWith("Error:")) {
            document.getElementById("btn-container-pro").appendChild(
                createAcceptButton("Professional", data.professional)
            );
        }
        if (data.concise && !data.concise.startsWith("Error:")) {
            document.getElementById("btn-container-con").appendChild(
                createAcceptButton("Concise", data.concise)
            );
        }
        if (data.simpler && !data.simpler.startsWith("Error:")) {
            document.getElementById("btn-container-sim").appendChild(
                createAcceptButton("Simpler", data.simpler)
            );
        }
    };

    // 4. Check Consistency
    document.getElementById("btnConsistency").onclick = async () => {
        const data = await post("consistency", textArea.value);
        if (!data) return;

        const results = data.consistency_results || [];
        const report = data.issues_report || "No inconsistencies detected.";
        const suggestion = data.suggested_rewrite;

        let html = `<h3>Consistency Check</h3><pre>${report}</pre>`;
        
        // Build table of contradictions
        const contradictions = results.filter(r => r.label === "CONTRADICTION");
        if (contradictions.length > 0) {
            html += `<table>
                        <tr>
                            <th>Sentence 1</th>
                            <th>Sentence 2</th>
                            <th>Verdict</th>
                        </tr>`;
            for (const r of contradictions) {
                html += `<tr>
                            <td>${r.sentence1}</td>
                            <td>${r.sentence2}</td>
                            <td style="color: var(--accent-red); font-weight: 500;">${r.verdict}</td>
                         </tr>`;
            }
            html += `</table>`;
        }

        // Add suggestion box if it exists
        if (suggestion && !suggestion.startsWith("Error:")) {
            html += `
                <h3 style="margin-top: 24px;">Suggested Fix</h3>
                <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 12px;">
                    The AI has generated a revised version to resolve the inconsistencies:
                </p>
                <pre class="suggestion" id="rewrite-suggestion">${suggestion.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</pre>
                <div class="buttons">
                    <button id="acceptFixBtn" class="small-btn">✅ Accept Fix</button>
                </div>
            `;
        }

        outputEl.innerHTML = html;

        // Add event listener for the new "Accept Fix" button
        const acceptFixBtn = document.getElementById("acceptFixBtn");
        if (acceptFixBtn) {
            acceptFixBtn.onclick = () => {
                textArea.value = suggestion;
                outputEl.innerHTML = `<h3>Rewrite Applied</h3><pre>${suggestion}</pre>`;
                // Also update Word
                if (document.getElementById("replaceCheck").checked) {
                    replaceSelectionInWord(suggestion);
                }
            };
        }
    };
    
    // === Function to write text back to Word ===
    async function replaceSelectionInWord(text) {
        if (info.host === Office.HostType.Word) {
            try {
                await Word.run(async (context) => {
                    const selection = context.document.getSelection();
                    selection.insertText(text, Word.InsertLocation.replace);
                    await context.sync();
                });
            } catch (error) {
                console.error("Error replacing text in Word:", error);
            }
        }
    }

    // === Server Connection Check ===
    async function checkConnection() {
        try {
            // We check the root URL, which is handled by app.py
            const response = await fetch(`${API_BASE_URL}/`); 
            if (response.ok) {
                statusBadge.textContent = "Online";
                statusBadge.classList.remove("offline");
                statusBadge.classList.add("online");
            } else {
                throw new Error("Server not reachable");
            }
        } catch (error) {
            statusBadge.textContent = "Offline";
            statusBadge.classList.remove("online");
            statusBadge.classList.add("offline");
        }
    }
    
    // Check connection on page load
    checkConnection();
    // And check every 10 seconds
    setInterval(checkConnection, 10000);

}); // End of Office.onReady wrapper