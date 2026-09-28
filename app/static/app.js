const state = {
  tasks: [],
  filter: "all",
};

const elements = {
  form: document.querySelector("#taskForm"),
  title: document.querySelector("#taskTitle"),
  list: document.querySelector("#taskList"),
  empty: document.querySelector("#emptyState"),
  message: document.querySelector("#message"),
  open: document.querySelector("#openCount"),
  done: document.querySelector("#doneCount"),
  total: document.querySelector("#totalCount"),
  filters: [...document.querySelectorAll(".filter-button")],
  status: document.querySelector("#serviceStatus"),
  storage: document.querySelector("#storageInfo"),
};

function setMessage(text = "") {
  elements.message.textContent = text;
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (response.status === 204) return null;

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("de-CH", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function visibleTasks() {
  if (state.filter === "open") return state.tasks.filter((task) => !task.completed);
  if (state.filter === "done") return state.tasks.filter((task) => task.completed);
  return state.tasks;
}

function updateStats() {
  const done = state.tasks.filter((task) => task.completed).length;
  elements.done.textContent = done;
  elements.open.textContent = state.tasks.length - done;
  elements.total.textContent = state.tasks.length;
}

function render() {
  elements.list.replaceChildren();
  const tasks = visibleTasks();

  for (const task of tasks) {
    const li = document.createElement("li");
    li.className = `task-item${task.completed ? " completed" : ""}`;

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "task-checkbox";
    checkbox.checked = task.completed;
    checkbox.setAttribute("aria-label", `Aufgabe ${task.title} als erledigt markieren`);
    checkbox.addEventListener("change", async () => {
      checkbox.disabled = true;
      try {
        const updated = await api(`/api/tasks/${task.id}`, {
          method: "PATCH",
          body: JSON.stringify({ completed: checkbox.checked }),
        });
        state.tasks = state.tasks.map((item) => item.id === task.id ? updated : item);
        setMessage();
        render();
      } catch (error) {
        checkbox.checked = !checkbox.checked;
        setMessage(error.message);
      } finally {
        checkbox.disabled = false;
      }
    });

    const content = document.createElement("div");
    content.className = "task-content";

    const title = document.createElement("p");
    title.className = "task-title";
    title.textContent = task.title;

    const meta = document.createElement("p");
    meta.className = "task-meta";
    meta.textContent = `Erstellt: ${formatDate(task.created_at)}`;

    content.append(title, meta);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "delete-button";
    remove.textContent = "Löschen";
    remove.addEventListener("click", async () => {
      if (!window.confirm(`Aufgabe „${task.title}“ löschen?`)) return;
      remove.disabled = true;
      try {
        await api(`/api/tasks/${task.id}`, { method: "DELETE" });
        state.tasks = state.tasks.filter((item) => item.id !== task.id);
        setMessage();
        render();
      } catch (error) {
        setMessage(error.message);
        remove.disabled = false;
      }
    });

    li.append(checkbox, content, remove);
    elements.list.append(li);
  }

  elements.empty.hidden = tasks.length !== 0;
  updateStats();
}

async function loadTasks() {
  try {
    state.tasks = await api("/api/tasks");
    setMessage();
    render();
  } catch (error) {
    setMessage(`Aufgaben konnten nicht geladen werden: ${error.message}`);
  }
}

async function checkHealth() {
  try {
    const health = await api("/api/health");
    elements.status.classList.remove("error");
    elements.status.classList.add("ok");
    elements.status.querySelector("span:last-child").textContent = "Service online";
    elements.storage.textContent = `Speicher: ${health.storage}`;
  } catch (error) {
    elements.status.classList.remove("ok");
    elements.status.classList.add("error");
    elements.status.querySelector("span:last-child").textContent = "Service gestört";
    elements.storage.textContent = "Speicher: nicht erreichbar";
  }
}

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = elements.title.value.trim();
  if (!title) return;

  const submit = elements.form.querySelector("button[type='submit']");
  submit.disabled = true;

  try {
    const task = await api("/api/tasks", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
    state.tasks.unshift(task);
    elements.title.value = "";
    elements.title.focus();
    setMessage();
    render();
  } catch (error) {
    setMessage(error.message);
  } finally {
    submit.disabled = false;
  }
});

for (const button of elements.filters) {
  button.addEventListener("click", () => {
    state.filter = button.dataset.filter;
    elements.filters.forEach((item) => item.classList.toggle("active", item === button));
    render();
  });
}

checkHealth();
loadTasks();
