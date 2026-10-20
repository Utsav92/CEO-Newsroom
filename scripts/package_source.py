"""Package source, pinned dependencies, assets and built UI; exclude credentials/data."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
EXCLUDE={'node_modules','.venv','data','output','.playwright-cli','__pycache__','.pytest_cache','.git','.vercel'}
def main():
    output=ROOT.parent/'CEO-Newsroom-source.zip'
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for path in ROOT.rglob('*'):
            if not path.is_file(): continue
            relative=path.relative_to(ROOT)
            if any(p in EXCLUDE for p in relative.parts): continue
            if path.name.startswith('.env') and path.name!='.env.example': continue
            if path.suffix in {'.pyc','.db','.sqlite','.mp3'}: continue
            z.write(path,Path('CEO-Newsroom')/relative)
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        assert not any('/data/' in n or '/node_modules/' in n or n.endswith('.env.local') for n in z.namelist())
        print(f'Packaged {len(z.namelist())} files; {output.stat().st_size:,} bytes: {output}')
if __name__=='__main__': main()
