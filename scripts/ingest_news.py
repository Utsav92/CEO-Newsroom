import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from validate_sources import main
import asyncio
if __name__=='__main__': asyncio.run(main())
