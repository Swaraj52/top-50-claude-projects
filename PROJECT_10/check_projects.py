import json
with open(r"C:\Users\Swayam Naik\TOP-50-CLAUDE-PROJECTS\PROJECT_10\projects.json") as f:
    data = json.load(f)
    for item in data:
        if "10" in str(item.get("project", "")) or "foundry" in str(item.get("name", "")).lower():
            print(f"Project: {item.get('project')} - {item.get('name')} - progress: {item.get('progress')}")