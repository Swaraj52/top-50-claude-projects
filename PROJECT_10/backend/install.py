import subprocess
result = subprocess.run(["-m", "pip", "install", "-q", "-r", "requirements.txt"], cwd=r"C:\Users\Swayam Naik\TOP-50-CLAUDE-PROJECTS\PROJECT_10\backend", capture_output=True, text=True)
print("STDOUT:", result.stdout[-500:])
print("STDERR:", result.stderr[-500:])
print("Return code:", result.returncode)