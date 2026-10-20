"""Extract supplied portraits; no generative reconstruction of occluded body parts."""
import argparse, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageOps
import numpy as np
from scipy.ndimage import label

ROOT = Path(__file__).resolve().parents[1]
IDS = ['sam_altman','mark_zuckerberg','tim_cook','sundar_pichai','dario_amodei','aravind_srinivas','ted_sarandos','jensen_huang']
# Hand-inspected head/upper-body boundaries in the supplied 2117 × 743 image.
BOXES = [(0,64,310,743),(282,99,563,743),(535,112,797,743),(797,118,1080,743),(1059,122,1330,743),(1310,120,1590,743),(1568,118,1833,743),(1810,102,2117,743)]

def extract(path):
    src = Image.open(path)
    rgba = src.convert('RGBA')
    report = {'original_mode': src.mode, 'size': src.size, 'alpha_present': src.mode == 'RGBA', 'method': 'background-connected neutral checker mask + inspected crops', 'limitations': 'Portraits overlap. Hidden shoulders are not reconstructed; small adjacent clothing fragments may remain.'}
    if src.mode != 'RGBA':
        # The attached checkerboard is baked into RGB. Flood only connected neutral
        # light background pixels, preserving enclosed silver hair and glasses.
        pixels = np.asarray(rgba).copy()
        rgb = pixels[:,:,:3].astype(int)
        neutral = (rgb.max(2)-rgb.min(2) < 20) & (rgb.min(2) > 105)
        h,w = neutral.shape
        # fromarray may share read-only storage; floodfill needs a writable copy.
        mask = Image.fromarray(np.where(neutral, 0, 255).astype('uint8')).copy()
        ImageDraw.floodfill(mask, (0,0), 128, thresh=0)
        bg = np.asarray(mask) == 128
        # Background pockets can be enclosed by overlapping shoulders. Remove
        # only large neutral components with the checkerboard's white/gray mix;
        # isolated gray hair highlights are retained.
        components,count=label(neutral)
        brightness=rgb.mean(2)
        ids=components.ravel()
        sizes=np.bincount(ids)
        whites=np.bincount(ids,weights=(brightness>245).ravel())
        grays=np.bincount(ids,weights=((brightness>160)&(brightness<215)).ravel())
        remove=(sizes>200)&(whites/np.maximum(sizes,1)>.3)&(grays/np.maximum(sizes,1)>.2)
        remove[0]=False
        bg |= remove[components]
        pixels[bg,3] = 0
        rgba = Image.fromarray(pixels)
    for id,box in zip(IDS,BOXES):
        crop = rgba.crop(box)
        for output in [ROOT/'assets'/'avatars',ROOT/'frontend'/'public'/'avatars']:
            output.mkdir(parents=True,exist_ok=True)
            portrait = ImageOps.contain(crop,(512,768),Image.Resampling.LANCZOS)
            canvas = Image.new('RGBA',(512,768)); canvas.alpha_composite(portrait,((512-portrait.width)//2,768-portrait.height))
            canvas.save(output/f'{id}.png',optimize=True)
            canvas.save(output/f'{id}.webp',quality=88)
            # Face-preserving circular crop: each full head fits the square.
            head = crop.crop((0,0,crop.width,min(crop.height,crop.width+35)))
            head = ImageOps.fit(head,(256,256),Image.Resampling.LANCZOS,centering=(.5,.35))
            circle = Image.new('L',(256,256)); ImageDraw.Draw(circle).ellipse((0,0,255,255),fill=255)
            alpha = np.minimum(np.asarray(head.getchannel('A')),np.asarray(circle))
            head.putalpha(Image.fromarray(alpha)); head.save(output/f'{id}_profile.png',optimize=True)
            head.resize((96,96),Image.Resampling.LANCZOS).save(output/f'{id}_thumb.webp',quality=88)
    (ROOT/'assets'/'extraction-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('image'); extract(parser.parse_args().image)
