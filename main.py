# I rushed this alot, edit it if you need to.

import os
import sys
import json
import subprocess
import platform
from pathlib import Path
from datetime import datetime

from openai import OpenAI
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROMPT_FILE = BASE_DIR / "prompt.md"
CHATS_DIR = BASE_DIR / "chats"
ENV_FILE = BASE_DIR / ".env"

CHATS_DIR.mkdir(exist_ok=True)


def clear_screen():
    os.system("cls" if platform.system() == "Windows" else "clear")


def banner():
    print("\n  OpenAI CLI Chat Client\n")


def separator(title=""):
    if title:
        print(f"\n  -- {title} --")
    else:
        print()


def load_system_prompt():
    if PROMPT_FILE.exists():
        text = PROMPT_FILE.read_text().strip()
        lines = text.splitlines()
        content_lines = []
        for line in lines:
            if line.strip().startswith("# "):
                continue
            content_lines.append(line)
        return "\n".join(content_lines).strip()
    return "You are a helpful assistant."


def fetch_chat_models(client):
    try:
        models = client.models.list()
        chat_models = sorted([
            m.id for m in models.data
            if any(p in m.id for p in ["gpt-", "o1", "o3", "o4", "chatgpt"])
        ])
        return chat_models
    except Exception as e:
        print(f"\n  Could not fetch models: {e}")
        return ["gpt-4o-mini", "gpt-4o", "gpt-4", "gpt-3.5-turbo"]


def pick_model(client):
    separator("Available Models")
    models = fetch_chat_models(client)
    if not models:
        print("  No models found. Defaulting to gpt-4o-mini.")
        return "gpt-4o-mini"

    for i, m in enumerate(models, 1):
        print(f"  {i:>3}. {m}")

    print()
    while True:
        choice = input("  Select a model (number or name): ").strip()
        if not choice:
            continue

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                print(f"\n  Using model: {models[idx]}")
                return models[idx]
            print("  Invalid number. Try again.")
            continue

        if choice in models:
            print(f"\n  Using model: {choice}")
            return choice

        matches = [m for m in models if choice.lower() in m.lower()]
        if len(matches) == 1:
            print(f"\n  Using model: {matches[0]}")
            return matches[0]
        elif len(matches) > 1:
            print(f"  Multiple matches: {', '.join(matches)}")
        else:
            print("  Model not found. Try again.")


def save_chat(model, messages, chat_file=None):
    data = {
        "model": model,
        "saved_at": datetime.now().isoformat(),
        "messages": messages,
    }
    if chat_file is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        chat_file = CHATS_DIR / f"chat_{timestamp}.json"
    chat_file.write_text(json.dumps(data, indent=2))
    return chat_file


def list_saved_chats():
    return sorted(
        CHATS_DIR.glob("chat_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )


def load_chat(chat_file):
    data = json.loads(chat_file.read_text())
    return data["model"], data["messages"]


def pick_saved_chat():
    files = list_saved_chats()
    if not files:
        print("\n  No saved chats found.")
        return None

    separator("Saved Chats")
    for i, f in enumerate(files, 1):
        data = json.loads(f.read_text())
        model = data.get("model", "unknown")
        saved_at = data.get("saved_at", "unknown")
        msg_count = len(data.get("messages", []))

        preview = ""
        for m in data.get("messages", []):
            if m["role"] == "user":
                preview = m["content"][:60].replace("\n", " ")
                break

        print(f"  {i}. [{model}] {saved_at}  ({msg_count} msgs)")
        if preview:
            print(f"     \"{preview}{'…' if len(preview) >= 60 else ''}\"")

    print(f"\n  0. Cancel")
    while True:
        choice = input("\n  Select a chat: ").strip()
        if choice == "0":
            return None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                model, messages = load_chat(files[idx])
                print(f"\n  Loaded chat ({len(messages)} messages, model: {model})")
                return model, messages, files[idx]
        print("  Invalid choice.")


def print_help():
    print()
    print("  Commands:")
    print("    /help       Show this help")
    print("    /save       Save the current chat")
    print("    /load       Load a previously saved chat")
    print("    /model      Switch to a different model")
    print("    /prompt     Open prompt.md for editing")
    print("    /reload     Reload the system prompt")
    print("    /history    Show conversation history")
    print("    /clear      Clear chat and start fresh")
    print("    /quit       Save and exit")
    print()


def open_in_editor(filepath):
    editor = os.environ.get("EDITOR", "nano")
    try:
        subprocess.run([editor, str(filepath)])
    except FileNotFoundError:
        for fallback in ["nano", "vim", "vi", "code", "open"]:
            try:
                subprocess.run([fallback, str(filepath)])
                return
            except FileNotFoundError:
                continue
        print(f"  Could not open editor. Edit manually: {filepath}")


def show_history(messages):
    separator("Conversation History")
    for msg in messages:
        role = msg["role"].upper()
        content = msg["content"]
        if role == "SYSTEM":
            print(f"  [SYSTEM] {content[:100]}{'…' if len(content) > 100 else ''}")
        elif role == "USER":
            print(f"\n  You: {content}")
        elif role == "ASSISTANT":
            print(f"\n  AI:  {content}")
    print()


def stream_response(client, model, messages):
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        print("\n  AI: ", end="", flush=True)
        full_response = []
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                print(delta.content, end="", flush=True)
                full_response.append(delta.content)
        print("\n")
        return "".join(full_response)
    except Exception as e:
        print(f"\n  Error: {e}\n")
        return ""


def chat_loop(client, model, messages, chat_file=None):
    system_prompt = load_system_prompt()

    if not messages:
        messages.append({"role": "system", "content": system_prompt})

    separator(f"Chatting with {model}")
    print("  Type your message and press Enter. Use /help for commands.\n")

    user_msgs = [m for m in messages if m["role"] == "user"]
    if user_msgs:
        print("  (Resumed — showing last exchange)")
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user":
                print(f"\n  You: {messages[i]['content']}")
                if i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                    print(f"\n  AI:  {messages[i + 1]['content']}")
                break
        print()

    while True:
        try:
            user_input = input("  You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n")
            user_input = "/quit"

        if not user_input:
            continue

        if user_input.startswith("/"):
            cmd = user_input.lower().split()[0]

            if cmd == "/help":
                print_help()

            elif cmd == "/save":
                chat_file = save_chat(model, messages, chat_file)
                print(f"  Chat saved to {chat_file.name}")

            elif cmd == "/load":
                result = pick_saved_chat()
                if result:
                    model, messages, chat_file = result
                    separator(f"Chatting with {model}")
                    show_history(messages)

            elif cmd == "/model":
                model = pick_model(client)
                separator(f"Chatting with {model}")

            elif cmd == "/prompt":
                print(f"  Opening {PROMPT_FILE}...")
                open_in_editor(PROMPT_FILE)
                print("  Prompt file closed. Use /reload to apply changes.")

            elif cmd == "/reload":
                new_prompt = load_system_prompt()
                if messages and messages[0]["role"] == "system":
                    messages[0]["content"] = new_prompt
                else:
                    messages.insert(0, {"role": "system", "content": new_prompt})
                print("  System prompt reloaded from prompt.md")

            elif cmd == "/history":
                show_history(messages)

            elif cmd == "/clear":
                messages.clear()
                system_prompt = load_system_prompt()
                messages.append({"role": "system", "content": system_prompt})
                chat_file = None
                print("  Chat cleared. Starting fresh.\n")

            elif cmd == "/quit":
                if len(messages) > 1:
                    save_input = input("  Save chat before quitting? (y/n): ").strip().lower()
                    if save_input in ("y", "yes"):
                        chat_file = save_chat(model, messages, chat_file)
                        print(f"  Chat saved to {chat_file.name}")
                print("\n  Goodbye!\n")
                sys.exit(0)

            else:
                print(f"  Unknown command: {cmd}. Type /help for options.")

            continue

        messages.append({"role": "user", "content": user_input})

        response_text = stream_response(client, model, messages)
        if response_text:
            messages.append({"role": "assistant", "content": response_text})


def main():
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("\n  OPENAI_API_KEY not found.")
        print("  Set it in your environment or in cli_client/.env")
        api_key = input("\n  Enter your API key: ").strip()
        if not api_key:
            print("  No API key provided. Exiting.")
            sys.exit(1)
        os.environ["OPENAI_API_KEY"] = api_key

    client = OpenAI(api_key=api_key)

    clear_screen()
    banner()

    saved = list_saved_chats()
    messages = []
    chat_file = None
    model = ""

    if saved:
        print("\n  1. New chat")
        print("  2. Resume a saved chat")
        choice = input("\n  Choice: ").strip()
        if choice == "2":
            result = pick_saved_chat()
            if result:
                model, messages, chat_file = result

    if not model:
        model = pick_model(client)

    chat_loop(client, model, messages, chat_file)


if __name__ == "__main__":
    main()
