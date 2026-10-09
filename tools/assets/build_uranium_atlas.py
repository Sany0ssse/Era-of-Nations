"""Compile the code-defined U glyph and six unchanged frames into a DDS atlas.

This builds a game UI atlas. Existing upstream textures are never overwritten;
their decoded first-six frames must remain byte-identical in the new atlas.
"""
from pathlib import Path
import argparse,hashlib,json
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2]

def glyph():
    # A simple code-native U mark: no image generation or redrawn upstream art.
    icon=Image.new('RGBA',(27,27),(0,0,0,0));d=ImageDraw.Draw(icon)
    d.polygon([(4,5),(20,5),(24,9),(24,23),(8,23),(4,19)],fill=(44,55,60,255),outline=(135,159,166,255))
    d.polygon([(4,5),(20,5),(24,9),(8,9)],fill=(157,173,179,255))
    d.line([(9,12),(9,18),(11,21),(16,21),(18,18),(18,12)],fill=(207,225,211,255),width=2)
    return icon

def build(check=False):
    records={}
    for name in ('resources_strip','missing_resources_strip'):
        original=ROOT/'gfx/interface'/f'{name}.dds';before=Image.open(original).convert('RGBA')
        assert before.size==(162,27)
        out=Image.new('RGBA',(189,27));out.paste(before,(0,0));out.paste(glyph(),(162,0))
        destination=ROOT/'gfx/interface'/f'eon_{name}_uranium.dds'
        if not check:
            out.save(destination)
        decoded=Image.open(destination).convert('RGBA')
        assert decoded.size==(189,27)
        assert decoded.crop((0,0,162,27)).tobytes()==before.tobytes()
        assert decoded.crop((162,0,189,27)).tobytes()==glyph().tobytes()
        records[str(destination.relative_to(ROOT)).replace('\\','/')]=hashlib.sha256(destination.read_bytes()).hexdigest()
    print(json.dumps({'first_six_frames_unchanged':True,'atlas_size':[189,27],'sha256':records},indent=2))

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--check',action='store_true',help='Verify existing atlases without rewriting them')
    build(cli.parse_args().check)
