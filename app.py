from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)
CORS(app)

# -------------------------
# Database Connection
# -------------------------
def get_db_connection():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    return conn

def query_db(query, args=(), one=False):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, args)
    rv = None
    try:
        if cur.description:  # If query returns rows
            rv = cur.fetchall()
    except Exception:
        pass
    conn.commit()
    cur.close()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def row_to_dict(row):
    date_str = row[2].strftime("%Y-%m-%d") if row[2] is not None else None
    return {"id": row[0], "name": row[1], "date": date_str, "status": row[3]}

def get_current_date_str():
    return datetime.now().strftime("%Y-%m-%d")

def parse_relative_date(word):
    today = datetime.now()
    if word.lower() == "today":
        return today.strftime("%Y-%m-%d")
    elif word.lower() == "tomorrow":
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif word.lower() == "yesterday":
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    return None

# -------------------------
# Serve frontend
# -------------------------
@app.route("/")
def index():
    return render_template("index.html")

# -------------------------
# API Routes
# -------------------------
@app.route("/tasks", methods=["GET"])
def get_tasks():
    rows = query_db("SELECT * FROM tasks ORDER BY id ASC")
    return jsonify([row_to_dict(r) for r in rows])

@app.route("/refresh", methods=["GET"])
def refresh_tasks():
    # same as /tasks, but separated for a dedicated refresh button
    rows = query_db("SELECT * FROM tasks ORDER BY id ASC")
    return jsonify([row_to_dict(r) for r in rows])

@app.route("/tasks", methods=["POST"])
def add_task():
    data = request.json
    name = data.get("name", "").strip()
    date = data.get("date", "")
    if not name:
        return jsonify({"error": "Task name cannot be empty"}), 400
    query_db("INSERT INTO tasks (name, date) VALUES (%s, %s)", (name, date))
    return jsonify({"message": "Task added successfully!"}), 201

@app.route("/tasks/<int:task_id>", methods=["PUT"])
def edit_task_route(task_id):
    data = request.json
    name = data.get("name", "").strip()
    date = data.get("date", "")

    if not name:
        return jsonify({"error": "Task name cannot be empty"}), 400

    task = query_db("SELECT * FROM tasks WHERE id=%s", (task_id,), one=True)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    query_db("UPDATE tasks SET name=%s, date=%s WHERE id=%s", (name, date, task_id))
    return jsonify({"message": "Task updated successfully!"})

@app.route("/tasks/<int:task_id>/complete", methods=["PUT"])
def complete_task(task_id):
    task = query_db("SELECT * FROM tasks WHERE id=%s", (task_id,), one=True)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    query_db("UPDATE tasks SET status='completed' WHERE id=%s", (task_id,))
    return jsonify({"message": "Task marked as completed!"})

@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    task = query_db("SELECT * FROM tasks WHERE id=%s", (task_id,), one=True)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    query_db("DELETE FROM tasks WHERE id=%s", (task_id,))
    return jsonify({"message": "Task deleted!"})

@app.route("/today", methods=["GET"])
def get_today():
    return jsonify({"today": get_current_date_str()})

# -------------------------
# Chatbot Endpoint
# -------------------------
SYSTEM_PROMPT = """
You are chatbot, a friendly, encouraging, and slightly humorous AI assistant for a to-do list application. Your personality is cheerful and helpful.

**Your Primary Goal:** Help users manage their tasks by using your available tools.

**How to Behave:**
1.  **Be Conversational:** When the user starts a conversation (e.g., "Hello", "How are you?") or asks a question about you or the app, respond in a friendly and natural way.
2.  **Use Tools with JSON:** When the user asks you to perform an action on a task (add, edit, complete, delete, show), you **must** respond *only* with a single, clean JSON object representing the function call. Do not add any other text, explanations, or conversational filler before or after the JSON object.
3.  **Provide Detailed Help:** If the user asks for "help" or "what can you do?", provide a detailed and friendly explanation of your capabilities and give examples for each command.

**Tool Call Example:**
If the user says: "add a task to buy milk for tomorrow"
Your response **must** be:
```json
{
  "function": "addTask",
  "parameters": {
    "description": "buy milk",
    "due_date": "tomorrow"
  }
}
```

**Available Tools:**
- `addTask(description: string, due_date: string | null)`: Adds a new task.
- `editTask(task_id: int, new_description: string, new_due_date: string | null)`: Edits an existing task.
- `completeTask(task_id: int)`: Marks a task as complete.
- `deleteTask(task_id: int)`: Deletes a task.
- `showTasks(due_date: string)`: Shows tasks for a specific date.
- `getCurrentDate()`: Returns the current date.

**Important Rules:**
- **JSON Only for Tools:** When using a tool, your entire response must be the JSON object. Nothing else.
- **Understand Dates:** You can understand relative dates like "today", "tomorrow", and "yesterday".
- **Be Friendly in Conversation:** For any non-tool response, let your cheerful personality shine!
"""

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "").strip()
    if not user_message:
        return jsonify({"reply": "Please enter a message."})

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = f"{SYSTEM_PROMPT}\n\nUser: {user_message}"

        response = model.generate_content(prompt)
        reply_text = response.text.strip() if hasattr(response, "text") else str(response)

        # Try to parse JSON tool call
        try:
            import json
            json_start_index = reply_text.find('{')
            json_end_index = reply_text.rfind('}')

            if json_start_index != -1 and json_end_index != -1 and json_end_index > json_start_index:
                json_str = reply_text[json_start_index:json_end_index+1]
                func_json = json.loads(json_str)
                func_name = func_json.get("function")
                params = func_json.get("parameters", {})

                if func_name == "addTask":
                    desc = params.get("description")
                    due = params.get("due_date", None)
                    due_parsed = parse_relative_date(due) if due else None
                    query_db("INSERT INTO tasks (name, date) VALUES (%s, %s)", (desc, due_parsed))
                    reply_text = f"✅ On it! I've added '{desc}' to your list for {due_parsed or 'no date'}."

                elif func_name == "editTask":
                    task_id = params.get("task_id")
                    new_desc = params.get("new_description")
                    new_due = params.get("new_due_date", None)
                    new_due_parsed = parse_relative_date(new_due) if new_due else None
                    task = query_db("SELECT * FROM tasks WHERE id=%s", (task_id,), one=True)
                    if not task:
                        reply_text = f"🤔 Hmm, I couldn't find task #{task_id}."
                    else:
                        query_db("UPDATE tasks SET name=%s, date=%s WHERE id=%s", (new_desc, new_due_parsed, task_id))
                        reply_text = f"✏️ All set! Task #{task_id} is now '{new_desc}' for {new_due_parsed or 'no date'}."

                elif func_name == "completeTask":
                    task_id = params.get("task_id")
                    query_db("UPDATE tasks SET status='completed' WHERE id=%s", (task_id,))
                    reply_text = f"✅ Great job! I've marked task #{task_id} as completed."

                elif func_name == "deleteTask":
                    task_id = params.get("task_id")
                    query_db("DELETE FROM tasks WHERE id=%s", (task_id,))
                    reply_text = f"🗑️ Poof! Task #{task_id} has been deleted."

                elif func_name == "showTasks":
                    due = params.get("due_date")
                    due_parsed = parse_relative_date(due) if due else get_current_date_str()
                    rows = query_db("SELECT * FROM tasks WHERE date=%s ORDER BY id ASC", (due_parsed,))
                    if not rows:
                        reply_text = f"🎉 You have no tasks for {due_parsed}! Time for a break?"
                    else:
                        tasks_str = "\n".join([f"- {row[0]}. {row[1]} [{row[3]}]" for row in rows])
                        reply_text = f"Here are your tasks for {due_parsed}:\n{tasks_str}"

                elif func_name == "getCurrentDate":
                    today = get_current_date_str()
                    reply_text = f"📅 Today is {today}. Let's make it a productive day!"

        except json.JSONDecodeError:
            pass

    except Exception as e:
        reply_text = f"⚠️ Oh no! I ran into an error: {str(e)}"

    return jsonify({"reply": reply_text})

# -------------------------
# Run App
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)
