"""Generate a small launcher for users running Jupyter locally."""
import json
from pathlib import Path

cells=[]
def md(text): cells.append({'cell_type':'markdown','metadata':{},'source':text.splitlines(True)})
def code(text): cells.append({'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],'source':text.splitlines(True)})
md('''# Stillwater — launch your travel agent website
Open this notebook in the extracted **Travel-agent** folder, beside `app.py`.
Run the cells in order. The website will open in a browser on your Mac.

This update replaces stale destination/tier constraints, clarifies subjective budgets,
answers recorded season questions directly, and presents recommendations as a shortlist.
The API model used by this application is the `LLM_MODEL` value configured below;
it can differ from the model label shown in your chat application.
''')
code('''from pathlib import Path
assert Path("app.py").is_file(), "Move this notebook into the folder containing app.py first."
print("Project folder:", Path.cwd())
print("Project version:", Path("VERSION").read_text().strip() if Path("VERSION").is_file() else "older build")
''')
code('''%pip install -r requirements.lock
''')
md('''## Configure your API model
Enter a model ID accepted by your API provider. The default endpoint is OpenAI.
Your key is hidden and kept only in this kernel's environment. It is not written into
notebook outputs or files. Running chat or the optional model evaluation makes API calls
that may incur charges. No model calls are made by the launcher itself.
''')
code('''import os
from getpass import getpass
from dotenv import load_dotenv

load_dotenv(override=False)
os.environ["LLM_PROVIDER"] = "openai"
current_model = os.environ.get("LLM_MODEL", "gpt-4.1")
os.environ["LLM_MODEL"] = input(f"API model ID [{current_model}]: ").strip() or current_model
os.environ.setdefault("OPENAI_BASE_URL", "https://api.openai.com/v1")
if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass("Your API key (hidden): ")
if not os.environ["OPENAI_API_KEY"].strip():
    raise ValueError("An API key is required for chat.")
os.environ["ALLOW_PAID_API"] = "true"
os.environ["EMBEDDING_MODEL"] = ""
print("Configured application model:", os.environ["LLM_MODEL"])
print("API key present:", bool(os.environ.get("OPENAI_API_KEY")))
''')
md('''## Open the website
This stops only a website process previously started by this notebook, selects a free
port, waits for the HTTP health check, and opens a browser tab. Hosted notebooks need
an appropriate server preview/proxy rather than this local browser link.
''')
code('''import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from IPython.display import display, HTML

if "website" in globals() and website.poll() is None:
    website.terminate()
    website.wait(timeout=10)
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
url = f"http://127.0.0.1:{port}"
log_path = Path(f"website-{port}.log")
with log_path.open("w") as log:
    website = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         f"--server.port={port}", "--server.address=127.0.0.1",
         "--server.headless=true", "--browser.gatherUsageStats=false"],
        stdout=log, stderr=subprocess.STDOUT,
    )
for _ in range(60):
    if website.poll() is not None:
        raise RuntimeError(log_path.read_text())
    try:
        with urllib.request.urlopen(url + "/_stcore/health", timeout=1) as response:
            ready = response.status == 200
    except OSError:
        ready = False
    if ready:
        display(HTML(f'<a href="{url}" target="_blank">Open your Travel Agent website</a>'))
        webbrowser.open_new_tab(url)
        print("Website server ready. Start a New Conversation for testing this update.")
        break
    time.sleep(1)
else:
    website.terminate()
    raise RuntimeError("Website did not start in time.\\n" + log_path.read_text())
''')
md('''## Try the reported scenarios in the website
1. Ask for a **high-end hotel in Japan**, then change to **luxury hotels in Dubai**.
   Dubai has only **two** source records labeled **Top Luxury**; a shorter list is correct.
2. Say **my budget is low**. The agent should ask for a comfortable nightly USD range,
   without guessing a number. Supply a number, or ask to compare options without a ceiling.
3. Ask **when is peak season for Raffles Dubai Palm Hotel?**
   The record lists **June, July, August, September**. Other hotels can have missing months;
   those should be reported as unknown, not inferred from the sampling date.
4. Ask follow-ups about the first/second recommendation, compare prices, or change an amenity.

The deterministic regression tests validate tool/memory contracts, not real model
language understanding. Test your actual model here before judging conversational quality.
''')
md('''## Optional: automated checks (no model calls)
''')
code('''subprocess.run([sys.executable, "-m", "pytest", "-q"], check=True)
''')
md('''## Optional: record the reported scenarios using your real API model
Running the next cell makes API calls using the configured key and may incur charges.
Inspect the JSON traces in `evaluation/runs/` afterwards. The runner leaves rubric scores
unassigned until reviewed; it does not invent a quality score for you.
''')
code('''subprocess.run([
    sys.executable, "-m", "evaluation.run", "--split", "regression",
    "--output", "evaluation/runs/reported-regressions.json"
], check=True)
''')
md('''## Stop the website when finished
''')
code('''if "website" in globals() and website.poll() is None:
    website.terminate()
    website.wait(timeout=10)
    print("Website stopped.")
''')
notebook={'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
          'language_info':{'name':'python','version':'3.12'}},'nbformat':4,'nbformat_minor':5}
for i,cell in enumerate(cells): cell['id']=f'stillwater-{i}'
Path('Start_Travel_Agent.ipynb').write_text(json.dumps(notebook,indent=2,ensure_ascii=False))
