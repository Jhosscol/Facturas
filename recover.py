import json
import os
import re

logs = [
    r"C:\Users\natsu\.gemini\antigravity\brain\02f6a397-03c7-41de-bf68-54e102f3e930\.system_generated\logs\transcript.jsonl",
    r"C:\Users\natsu\.gemini\antigravity\brain\b9eb1c96-cf0e-4747-a32b-63f30ac90c7e\.system_generated\logs\transcript.jsonl"
]

files = {}

for log_path in logs:
    if not os.path.exists(log_path): continue
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
            except:
                continue
            
            # Extract from view_file outputs
            if data.get("type") == "VIEW_FILE" and data.get("status") == "DONE":
                content = data.get("content", "")
                if "File Path: " in content:
                    lines = content.splitlines()
                    filepath = ""
                    for l in lines:
                        if l.startswith("File Path: "):
                            filepath = l.split("`")[1].replace("file:///", "").replace("/", "\\")
                            break
                    if "src\\" in filepath and filepath.endswith(".py"):
                        # extract lines
                        file_lines = []
                        start_recording = False
                        for l in lines:
                            if l.startswith("The following code has been modified to include a line number"):
                                start_recording = True
                                continue
                            if l.startswith("The above content shows the entire"):
                                start_recording = False
                                continue
                            if start_recording:
                                # remove line number "123: "
                                parts = l.split(": ", 1)
                                if len(parts) >= 2 and parts[0].isdigit():
                                    file_lines.append(parts[1])
                                else:
                                    if l.strip() and l.split(":")[0].isdigit():
                                        file_lines.append(l.split(":", 1)[1][1:] if len(l.split(":", 1)) > 1 else "")
                                    else:
                                        file_lines.append(l)
                        
                        file_content = "\n".join(file_lines)
                        # Keep the longest version to avoid empty files
                        if len(file_content) > len(files.get(filepath, "")):
                            files[filepath] = file_content

            # Extract from write_to_file inputs
            if data.get("tool_calls"):
                for tc in data.get("tool_calls"):
                    if tc.get("name") == "write_to_file":
                        args = tc.get("args", {})
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except:
                                pass
                        if isinstance(args, dict):
                            filepath = args.get("TargetFile", "")
                            if "src\\" in filepath and filepath.endswith(".py"):
                                file_content = args.get("CodeContent", "")
                                if len(file_content) > len(files.get(filepath, "")):
                                    files[filepath] = file_content

for fp, content in files.items():
    out_path = fp
    if not os.path.exists(os.path.dirname(out_path)):
        os.makedirs(os.path.dirname(out_path))
    with open(out_path, "w", encoding="utf-8") as f:
        # replace the checkmark that caused the issue earlier
        content = content.replace("✓", "OK")
        f.write(content)
    print(f"Recovered {out_path} ({len(content)} bytes)")

