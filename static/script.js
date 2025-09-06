document.addEventListener("DOMContentLoaded", () => {
  const taskList = document.getElementById("taskList");
  const taskInput = document.getElementById("taskInput");
  const taskDate = document.getElementById("taskDate");
  const addTaskBtn = document.getElementById("addTaskBtn");
  const searchInput = document.getElementById("searchInput");
  const scheduleList = document.getElementById("scheduleList");
  const filterDate = document.getElementById("filterDate");
  const refreshBtn = document.getElementById("refreshBtn");

  const chatInput = document.getElementById("chatInput");
  const sendChatBtn = document.getElementById("sendChatBtn");
  const chatBox = document.getElementById("chatBox");

  let tasks = [];
  let scheduleMode = "date"; // default mode
  let typingIndicator;

  // --- Fetch tasks from server ---
  async function fetchTasks() {
    const res = await fetch("/tasks");
    tasks = await res.json();
    renderTasks(tasks);
    renderScheduleTasks(tasks, scheduleMode);
  }

  // --- Render task list ---
  function renderTasks(tasksToRender) {
    taskList.innerHTML = "";

    if (tasksToRender.length === 0) {
      taskList.innerHTML = `<li style="text-align:center; font-style:italic;">No tasks yet. Add one above!</li>`;
      return;
    }

    tasksToRender.forEach(task => {
      const li = document.createElement("li");

      const span = document.createElement("span");
      span.textContent = `${task.id}. ${task.name} (${task.date || "No date"})`;
      if (task.status === "completed") span.classList.add("completed");
      li.appendChild(span);

      const btnDiv = document.createElement("div");

      // Complete button
      const completeBtn = document.createElement("button");
      completeBtn.textContent = "✅";
      if (task.status === "completed") {
        completeBtn.style.backgroundColor = "#999";
        completeBtn.disabled = true;
      }
      completeBtn.addEventListener("click", async () => {
        const res = await fetch(`/tasks/${task.id}/complete`, { method: "PUT" });
        const data = await res.json();
        if (!res.ok) return alert(data.error || "Failed to complete task");
        span.classList.add("completed");
        completeBtn.style.backgroundColor = "#999";
        completeBtn.disabled = true;
        renderScheduleTasks(tasks, scheduleMode); // update schedule
      });
      btnDiv.appendChild(completeBtn);

      // Delete button
      const deleteBtn = document.createElement("button");
      deleteBtn.textContent = "🗑️";
      deleteBtn.addEventListener("click", async () => {
        const res = await fetch(`/tasks/${task.id}`, { method: "DELETE" });
        const data = await res.json();
        if (!res.ok) return alert(data.error || "Failed to delete task");
        fetchTasks();
      });
      btnDiv.appendChild(deleteBtn);

      li.appendChild(btnDiv);
      taskList.appendChild(li);
    });
  }

  // --- Render schedule tasks ---
  function renderScheduleTasks(tasksToRender, mode = "date") {
    scheduleList.innerHTML = "";
    const today = new Date().toISOString().split("T")[0];
    let filtered = [];

    if (mode === "date") {
      const selectedDate = filterDate.value;
      if (!selectedDate) return; // show nothing if no date selected
      filtered = tasksToRender.filter(t => t.date === selectedDate);
    } else if (mode === "upcoming") {
      filtered = tasksToRender.filter(t => t.date && t.date >= today);
    }

    if (!filtered.length) {
      scheduleList.innerHTML = `<li style="text-align:center; font-style:italic;">No tasks found.</li>`;
      return;
    }

    filtered.forEach(t => {
      const li = document.createElement("li");
      li.textContent = `${t.id}. ${t.name} (${t.date}) [${t.status}]`;
      if (t.status === "completed") li.classList.add("completed");
      scheduleList.appendChild(li);
    });
  }

  // --- Add new task ---
  addTaskBtn.addEventListener("click", async () => {
    const name = taskInput.value.trim();
    const date = taskDate.value;
    if (!name) return alert("Please enter a task!");

    await fetch("/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, date })
    });

    taskInput.value = "";
    taskDate.value = "";
    fetchTasks(); // refresh tasks and schedule
  });

  // --- Search tasks ---
  searchInput.addEventListener("input", () => {
    const query = searchInput.value.toLowerCase();
    const filtered = tasks.filter(t => t.name.toLowerCase().includes(query));
    renderTasks(filtered);
    renderScheduleTasks(filtered, scheduleMode);
  });

  refreshBtn.addEventListener("click", async () => {
    const res = await fetch("/refresh");
    tasks = await res.json();
    renderTasks(tasks);
    renderScheduleTasks(tasks, scheduleMode);
  });

  // --- Schedule buttons ---
  window.viewSchedule = () => {
    if (!filterDate.value) return alert("Select a date to view schedule.");
    scheduleMode = "date";
    renderScheduleTasks(tasks, scheduleMode);
  };

  window.viewUpcoming = () => {
    filterDate.value = "";
    scheduleMode = "upcoming";
    renderScheduleTasks(tasks, scheduleMode);
  };

  filterDate.addEventListener("change", () => {
    scheduleMode = "date";
    renderScheduleTasks(tasks, scheduleMode);
  });

  // --- Chatbot interaction ---
  async function sendChat() {
    const message = chatInput.value.trim();
    if (!message) return;

    addChatMessage("user", message);
    chatInput.value = "";
    showTypingIndicator();

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }

      const data = await res.json();

      hideTypingIndicator();
      addChatMessage("bot", data.reply);

      // If the bot's reply indicates a successful action, refresh the tasks
      if (data.reply.startsWith("✅") || data.reply.startsWith("🗑️") || data.reply.startsWith("✏️")) {
        fetchTasks();
      }

    } catch (err) {
      hideTypingIndicator();
      console.error("Chat Error:", err);
      addChatMessage("bot", "⚠️ Error connecting to the server. Please check the console for details.");
    }
  }

  sendChatBtn.addEventListener("click", sendChat);
  chatInput.addEventListener("keypress", e => {
    if (e.key === "Enter") sendChat();
  });

  function addChatMessage(sender, text) {
    const msg = document.createElement("div");
    msg.className = sender === "user" ? "chat-user" : "chat-bot";
    msg.textContent = text;
    chatBox.appendChild(msg);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function showTypingIndicator() {
    typingIndicator = document.createElement("div");
    typingIndicator.className = "chat-bot typing";
    typingIndicator.textContent = "Masrurah is typing...";
    chatBox.appendChild(typingIndicator);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function hideTypingIndicator() {
    if (typingIndicator) {
      chatBox.removeChild(typingIndicator);
      typingIndicator = null;
    }
  }

  // --- Initial load ---
  fetchTasks();
});
