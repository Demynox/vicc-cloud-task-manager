// Zentraler Status der Benutzeroberfläche.
// Die Tasks werden vom REST-API geladen und nicht direkt aus dem Storage.
const state = {
  tasks: [],
  filter: "all",
};

// Häufig verwendete HTML-Elemente werden einmal gesucht und gespeichert.
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


// Zeigt Status- oder Fehlermeldungen in der Benutzeroberfläche an.
function setMessage(text = "") {
  elements.message.textContent = text;
}


// Gemeinsame Hilfsfunktion für alle REST-API-Aufrufe.
async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  // DELETE liefert bei Erfolg HTTP 204 ohne Response Body.
  if (response.status === 204) {
    return null;
  }

  const data = await response.json().catch(() => ({}));

  // Nicht erfolgreiche HTTP-Antworten werden als Fehler behandelt.
  if (!response.ok) {
    throw new Error(
      data.error || `HTTP ${response.status}`
    );
  }

  return data;
}


// Formatiert ISO-Zeitstempel für die Schweizer Darstellung.
function formatDate(value) {
  if (!value) {
    return "";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("de-CH", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}


// Filtert die Aufgaben entsprechend der ausgewählten Ansicht.
function visibleTasks() {
  if (state.filter === "open") {
    return state.tasks.filter(
      (task) => !task.completed
    );
  }

  if (state.filter === "done") {
    return state.tasks.filter(
      (task) => task.completed
    );
  }

  return state.tasks;
}


// Aktualisiert die Anzahl offener, erledigter und gesamter Tasks.
function updateStats() {
  const done = state.tasks.filter(
    (task) => task.completed
  ).length;

  elements.done.textContent = done;
  elements.open.textContent = state.tasks.length - done;
  elements.total.textContent = state.tasks.length;
}


// Rendert die aktuelle Aufgabenliste im Browser.
function render() {
  elements.list.replaceChildren();

  const tasks = visibleTasks();

  for (const task of tasks) {
    const li = document.createElement("li");

    li.className =
      `task-item${task.completed ? " completed" : ""}`;

    // Checkbox zum Ändern des Erledigt-Status.
    const checkbox = document.createElement("input");

    checkbox.type = "checkbox";
    checkbox.className = "task-checkbox";
    checkbox.checked = task.completed;

    checkbox.setAttribute(
      "aria-label",
      `Aufgabe ${task.title} als erledigt markieren`
    );

    checkbox.addEventListener("change", async () => {
      checkbox.disabled = true;

      try {
        // Statusänderungen werden über PATCH an das REST-API gesendet.
        const updated = await api(
          `/api/tasks/${task.id}`,
          {
            method: "PATCH",
            body: JSON.stringify({
              completed: checkbox.checked,
            }),
          }
        );

        state.tasks = state.tasks.map(
          (item) =>
            item.id === task.id
              ? updated
              : item
        );

        setMessage();
        render();

      } catch (error) {
        // Bei einem Fehler wird die Checkbox auf
        // ihren vorherigen Zustand zurückgesetzt.
        checkbox.checked = !checkbox.checked;
        setMessage(error.message);

      } finally {
        checkbox.disabled = false;
      }
    });


    // Textinhalt des Tasks.
    const content = document.createElement("div");
    content.className = "task-content";

    const title = document.createElement("p");
    title.className = "task-title";
    title.textContent = task.title;

    const meta = document.createElement("p");
    meta.className = "task-meta";
    meta.textContent =
      `Erstellt: ${formatDate(task.created_at)}`;

    content.append(
      title,
      meta
    );


    // Button zum Löschen einer Aufgabe.
    const remove = document.createElement("button");

    remove.type = "button";
    remove.className = "delete-button";
    remove.textContent = "Löschen";

    remove.addEventListener("click", async () => {
      if (
        !window.confirm(
          `Aufgabe „${task.title}“ löschen?`
        )
      ) {
        return;
      }

      remove.disabled = true;

      try {
        await api(
          `/api/tasks/${task.id}`,
          {
            method: "DELETE",
          }
        );

        state.tasks = state.tasks.filter(
          (item) => item.id !== task.id
        );

        setMessage();
        render();

      } catch (error) {
        setMessage(error.message);
        remove.disabled = false;
      }
    });


    li.append(
      checkbox,
      content,
      remove
    );

    elements.list.append(li);
  }

  // Der Empty-State wird nur angezeigt,
  // wenn der aktuelle Filter keine Tasks enthält.
  elements.empty.hidden = tasks.length !== 0;

  updateStats();
}


// Lädt beim Start alle Tasks vom REST-API.
async function loadTasks() {
  try {
    state.tasks = await api("/api/tasks");

    setMessage();
    render();

  } catch (error) {
    setMessage(
      `Aufgaben konnten nicht geladen werden: ${error.message}`
    );
  }
}


// Prüft den Health-Endpunkt und zeigt das aktive Storage-Backend an.
async function checkHealth() {
  try {
    const health = await api("/api/health");

    elements.status.classList.remove("error");
    elements.status.classList.add("ok");

    elements.status
      .querySelector("span:last-child")
      .textContent = "Service online";

    elements.storage.textContent =
      `Speicher: ${health.storage}`;

  } catch (error) {
    elements.status.classList.remove("ok");
    elements.status.classList.add("error");

    elements.status
      .querySelector("span:last-child")
      .textContent = "Service gestört";

    elements.storage.textContent =
      "Speicher: nicht erreichbar";
  }
}


// Neue Tasks werden über das Formular erstellt.
elements.form.addEventListener(
  "submit",
  async (event) => {
    event.preventDefault();

    const title =
      elements.title.value.trim();

    if (!title) {
      return;
    }

    const submit =
      elements.form.querySelector(
        "button[type='submit']"
      );

    submit.disabled = true;

    try {
      // POST erstellt den neuen Task über das REST-API.
      const task = await api(
        "/api/tasks",
        {
          method: "POST",
          body: JSON.stringify({
            title,
          }),
        }
      );

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
  }
);


// Umschalten zwischen Alle, Offen und Erledigt.
for (const button of elements.filters) {
  button.addEventListener(
    "click",
    () => {
      state.filter =
        button.dataset.filter;

      elements.filters.forEach(
        (item) =>
          item.classList.toggle(
            "active",
            item === button
          )
      );

      render();
    }
  );
}


// Initiale Prüfung und Datenabfrage beim Laden der Seite.
checkHealth();
loadTasks();
