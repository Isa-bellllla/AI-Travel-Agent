"""Create a source/data archive, excluding credentials, caches, venv and Git metadata."""
import argparse
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TOP_FILES={'VERSION','.env.example','.gitignore','README.md','app.py','requirements.txt','requirements.lock',
           'cleaned_hotels.csv','Travel_AI_Agent_Evaluation_Rubric_v1.docx','Start_Travel_Agent.ipynb','.streamlit/config.toml'}
DIRS={'travel_agent','evaluation','tests','scripts','docs','assets'}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',default='/workspace/artifacts/Travel-agent.zip')
    out=Path(parser.parse_args().output).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
    files=[ROOT/p for p in sorted(TOP_FILES)]
    for directory in sorted(DIRS):
        files.extend(p for p in sorted((ROOT/directory).rglob('*')) if p.is_file()
                     and '__pycache__' not in p.parts and '.cache' not in p.parts and 'runs' not in p.relative_to(ROOT/directory).parts)
    files=[p for p in files if p.resolve()!=out and p.suffix not in ['.pyc','.zip'] and p.name!='.env']
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
        for p in files: archive.write(p,Path('Travel-agent')/p.relative_to(ROOT))
    with zipfile.ZipFile(out) as archive:
        assert archive.testzip() is None
        assert not any('/.env'==name[-5:] or '/.venv/' in name or '/.git/' in name for name in archive.namelist())
        print(f'{out}: {len(archive.namelist())} files; {out.stat().st_size:,} bytes; archive integrity verified')

if __name__=='__main__': main()
