import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
MEMORY_DIR = BASE_DIR / "memory"
TASKS_DIR = BASE_DIR / "tasks"
LOGS_DIR = BASE_DIR / "logs"

STATE_FILE = MEMORY_DIR / "STATE.json"
PROJECT_FILE = MEMORY_DIR / "PROJECT.md"
RULES_FILE = MEMORY_DIR / "RULES.md"


def load_text(file_path):
    if file_path.exists():
        return file_path.read_text(encoding="utf-8-sig")
    return ""


def load_state():
    if not STATE_FILE.exists():
        return {}

    with open(STATE_FILE, "r", encoding="utf-8-sig") as file:
        return json.load(file)


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(
            state,
            file,
            ensure_ascii=False,
            indent=4
        )


def write_log(message):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    log_file = LOGS_DIR / "manager.log"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_file, "a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {message}\n")


def create_task(title, agent="unassigned"):
    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    task = {
        "id": timestamp,
        "title": title,
        "agent": agent,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }

    task_file = TASKS_DIR / f"{timestamp}.json"

    with open(task_file, "w", encoding="utf-8") as file:
        json.dump(
            task,
            file,
            ensure_ascii=False,
            indent=4
        )

    write_log(
        f"Task created: {title} | Agent: {agent}"
    )

    return task


def show_status():
    state = load_state()

    print()
    print("================================")
    print("       AI CONTROL MANAGER")
    print("================================")
    print()

    print("Project:")
    print(state.get("project", "Unknown"))

    print()
    print("Current phase:")
    print(state.get("current_phase", "Unknown"))

    print()
    print("Current goal:")
    print(state.get("current_goal", "Unknown"))

    print()
    print("Agents:")

    agents = state.get("agents", {})

    for key, agent in agents.items():
        print(
            f"- {agent.get('name', key)}"
            f" | Status: {agent.get('status', 'unknown')}"
        )

    print()
    print("Manager:")
    print(
        state.get("manager", {}).get(
            "status",
            "unknown"
        )
    )

    print()


def show_memory():
    print("\n=== PROJECT MEMORY ===\n")
    print(load_text(PROJECT_FILE))

    print("\n=== MANAGER RULES ===\n")
    print(load_text(RULES_FILE))


def menu():
    while True:

        print("""
==============================
AI MANAGER
==============================

1 - Show Status
2 - Show Memory
3 - Create Coding Task
4 - Create Blender Task
5 - Exit
""")

        choice = input("Select: ").strip()

        if choice == "1":
            show_status()

        elif choice == "2":
            show_memory()

        elif choice == "3":
            title = input(
                "Coding task: "
            ).strip()

            if title:
                task = create_task(
                    title,
                    "Coding Agent"
                )

                print(
                    f"\nCreated task: {task['id']}\n"
                )

        elif choice == "4":
            title = input(
                "Blender task: "
            ).strip()

            if title:
                task = create_task(
                    title,
                    "Designer Agent"
                )

                print(
                    f"\nCreated task: {task['id']}\n"
                )

        elif choice == "5":
            print("Manager stopped.")
            break

        else:
            print("Invalid option.")


if __name__ == "__main__":
    write_log("AI Manager started.")
    menu()
