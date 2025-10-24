document.addEventListener("DOMContentLoaded", () => {
  const API_BASE = "http://127.0.0.1:5000";

  let sessionId = null;
  let gptMessages = [];
  let countdownTimer = null;

  const chatContainer = document.getElementById("chatContainer");
  const chatBox = document.getElementById("chatBox");
  const sendBtn = document.getElementById("sendBtn");
  const userInput = document.getElementById("userInput");
  const chatToggle = document.getElementById("chatToggle");
  const chatWidget = document.getElementById("chatWidget");
  const closeChat = document.getElementById("closeChat");

  console.log("Chat toggle:", chatToggle);
  console.log("Chat widget:", chatWidget);
  console.log("Close chat:", closeChat);

  initializeChat();

  function initializeChat() {
    console.log("Initializing chat...");
    
    localStorage.removeItem("chatOpen");
    localStorage.removeItem("sessionId");
    localStorage.removeItem("agentName");
    localStorage.removeItem("chatMessages");
    localStorage.removeItem("gptMessages");

    resetChatUI();
    
    autoStartChat();
  }

  function resetChatUI() {
    console.log("Resetting chat UI...");
    
    chatWidget.classList.remove('open');
    chatToggle.style.display = 'block';
  
    chatContainer.classList.add("d-none");
    chatBox.innerHTML = "Starting chat with Nabeel Ahmad...";
    
    gptMessages = [];
    sessionId = null;
    clearCountdownTimer();
  }

  async function autoStartChat() {
    console.log("Auto starting chat with Agent 1...");
    
    try {
      const res = await fetch(`${API_BASE}/initialize_session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_name: "Nabeel Ahmad" }),
      });

      if (!res.ok) throw new Error("Failed to create session");
      const data = await res.json();
      
      sessionId = data.session_id;
      const initialMessage = data.ai_response;

      console.log("Session created:", sessionId);
      console.log("Initial message:", initialMessage);

      chatContainer.classList.remove("d-none");
      
      chatBox.innerHTML = "";
      gptMessages = [];

      appendMessage("assistant", initialMessage);
      
      gptMessages = [
        { role: "assistant", content: initialMessage }
      ];

      localStorage.setItem("sessionId", sessionId);
      localStorage.setItem("agentName", "Nabeel Ahmad");
      localStorage.setItem("chatMessages", JSON.stringify([
        { role: "assistant", text: initialMessage }
      ]));
      localStorage.setItem("gptMessages", JSON.stringify(gptMessages));

      console.log("Chat auto-started successfully");

    } catch (err) {
      console.error("Error auto-starting chat:", err);
      chatBox.innerHTML = "Error starting chat with Nabeel Ahmad. Please check backend connection.";
    }
  }

  function clearCountdownTimer() {
    if (countdownTimer) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
  }

  function startCountdownTimer() {
    let countdown = 20;
    
    const countdownDiv = document.createElement("div");
    countdownDiv.className = "countdown message";
    countdownDiv.id = "countdownTimer";
    countdownDiv.innerHTML = `<b>SYSTEM:</b><br>Chat will close automatically in <span id="countdownNumber">${countdown}</span> seconds...`;
    chatBox.appendChild(countdownDiv);
    
    chatBox.scrollTop = chatBox.scrollHeight;
    
    userInput.disabled = true;
    sendBtn.disabled = true;
    
    countdownTimer = setInterval(() => {
      countdown--;
      const countdownElement = document.getElementById("countdownNumber");
      
      if (countdownElement) {
        countdownElement.textContent = countdown;
      }
      
      if (countdown <= 0) {
        clearCountdownTimer();
        closeChatWidget();
      }
    }, 1000);
  }

  function openChat() {
    console.log("Opening chat widget...");
    chatWidget.classList.add('open');
    chatToggle.style.display = 'none';
    localStorage.setItem("chatOpen", "true");
    
    restoreChat();
  }

  function restoreChat() {
    console.log("Restoring chat...");
    
    const savedChat = JSON.parse(localStorage.getItem("chatMessages") || "[]");
    sessionId = localStorage.getItem("sessionId") || null;
    gptMessages = JSON.parse(localStorage.getItem("gptMessages") || "[]");

    if (sessionId) {
      chatContainer.classList.remove("d-none");
      console.log("Session restored:", sessionId);
    }
    
    if (sessionId && savedChat.length > 0) {
      chatBox.innerHTML = "";
      savedChat.forEach(msg => appendMessage(msg.role, msg.text, false));
      console.log("Messages restored:", savedChat.length);
    } else if (!sessionId) {
      console.log("No session found, auto-starting...");
      autoStartChat();
    }

    setTimeout(() => {
      chatBox.scrollTop = chatBox.scrollHeight;
    }, 100);
  }

  function closeChatWidget() {
    console.log("Closing chat widget...");
    
    clearCountdownTimer();
    
    chatWidget.classList.remove('open');
    chatToggle.style.display = 'block';
    localStorage.setItem("chatOpen", "false");
    
    userInput.disabled = false;
    sendBtn.disabled = false;
  }

  sendBtn.addEventListener("click", async () => {
    const text = userInput.value.trim();
    if (!text || !sessionId) {
      console.log("Cannot send - no text or session:", { text, sessionId });
      return;
    }

    console.log("Sending message:", text);
    appendMessage("user", text);
    userInput.value = "";

    gptMessages.push({ role: "user", content: text });

    try {
      const res = await fetch(`${API_BASE}/chat_with_ai`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: gptMessages,
          session_id: sessionId,
          agent_name: "Nabeel Ahmad"
        }),
      });

      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      
      const data = await res.json();
      const reply = data.response || "No response received.";
      
      console.log("Received reply:", reply);
      
      if (reply.includes("CONVERSATION SUMMARY:") || reply.includes("Thank you for providing")) {
        appendMessage("assistant", reply);
        gptMessages.push({ role: "assistant", content: reply });
        
        setTimeout(() => {
          startCountdownTimer();
        }, 1000);
      } else {
        appendMessage("assistant", reply);
        gptMessages.push({ role: "assistant", content: reply });
      }
    } catch (err) {
      console.error("Error sending message:", err);
      appendMessage("assistant", "⚠️ Error communicating with backend.");
    }
  });

  userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      sendBtn.click();
    }
  });

  function appendMessage(role, text, save = true) {
    console.log("Appending message:", { role, text });
    
    if (chatBox.innerHTML === "Starting chat with Agent 1..." || chatBox.innerHTML === "Chat will appear here once started.") {
      chatBox.innerHTML = "";
    }
    
    const div = document.createElement("div");
    div.className = `${role} message`;
    
    const label = role === "user" ? "AGENT" : "QUARTZ AI";
    div.innerHTML = `<b>${label}:</b><br>${text.replace(/\n/g, "<br>")}`;
    chatBox.appendChild(div);

    chatBox.scrollTop = chatBox.scrollHeight;

    if (save) {
      const saved = JSON.parse(localStorage.getItem("chatMessages") || "[]");
      saved.push({ role, text });
      localStorage.setItem("chatMessages", JSON.stringify(saved));
      localStorage.setItem("gptMessages", JSON.stringify(gptMessages));
    }
  }

  chatToggle.addEventListener("click", function() {
    console.log("Chat toggle clicked!");
    openChat();
  });

  closeChat.addEventListener("click", function(e) {
    console.log("Close chat clicked!");
    e.preventDefault();
    e.stopPropagation();
    closeChatWidget();
  });

  const wasChatOpen = localStorage.getItem("chatOpen") === "true";
  console.log("Was chat previously open?", wasChatOpen);
  
  if (wasChatOpen) {
    openChat();
  }

  console.log("Chat initialization complete!");
});