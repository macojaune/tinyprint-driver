"""Photo corrections, physical layout, memory-only preview and printable raster.

Preset parameter values follow the TinyPOS Photo & Artwork Studio. Filters use
Pillow; transport and thermal energy remain independent of these image settings.
"""
import math
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from protocol import WIDTH

DOTS_MM = 8
MAX_TICKET_ROWS = 12000
MAX_TOTAL_ROWS = 200000
PRESETS = {
    'custom': dict(dither='floyd',sharpness=0,contrast=1,brightness=1),
    'portrait': dict(dither='floyd',sharpness=1.2,contrast=1.12,brightness=1.08),
    'sharp': dict(dither='atkinson',sharpness=2,contrast=1.22,brightness=1.05),
    'balanced': dict(dither='floyd',sharpness=1,contrast=1.15,brightness=1.03),
    'high_contrast': dict(dither='atkinson',sharpness=1.5,contrast=1.38,brightness=1),
    'halftone': dict(dither='bayer',sharpness=1,contrast=1.2,brightness=1.02),
}


def resolve_render(options):
    options = dict(options)
    name = options.get('preset', 'custom')
    if name not in PRESETS:
        raise ValueError('Préréglage photo inconnu.')
    resolved = dict(PRESETS[name], preset=name, gain=1, strength=7, autocrop=False)
    resolved.update({k:v for k,v in options.items() if v is not None})
    if resolved['dither'] not in ('none','floyd','atkinson','bayer'):
        raise ValueError('Algorithme de tramage inconnu.')
    for key, lower, upper in [('sharpness',0,3),('contrast',.25,3),('brightness',.25,3),('gain',.25,4),('strength',1,7)]:
        value = float(resolved[key])
        if not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError(f'Réglage {key} hors limites.')
        resolved[key] = value
    return resolved


def source_image(source, autocrop=False):
    image = ImageOps.exif_transpose(source)
    if image.mode in ('RGBA','LA') or 'transparency' in image.info:
        rgba=image.convert('RGBA')
        background=Image.new('RGBA',image.size,'white')
        image=Image.alpha_composite(background,rgba)
    image=image.convert('L')
    image.info.clear()
    if autocrop:
        bounds=ImageChops.difference(image,Image.new('L',image.size,255)).point(lambda p:255 if p>10 else 0).getbbox()
        if bounds:
            image=image.crop(bounds)
    return image


def layout(source_size, direction='vertical', count=3, size_mode='count', size_mm=None):
    width,height=source_size
    if width<1 or height<1 or direction not in ('vertical','horizontal'):
        raise ValueError('Dimensions ou sens de découpe invalides.')
    if size_mode=='count':
        if count<1:
            raise ValueError('Choisissez au moins un ticket.')
        if direction=='vertical':
            w=count*WIDTH; h=max(1,(height*w+width//2)//width)
        else:
            h=count*WIDTH; w=max(1,(width*h+height//2)//height)
    elif size_mode in ('width','height'):
        if size_mm is None or not math.isfinite(size_mm) or size_mm<=0:
            raise ValueError('Saisissez une dimension finale positive.')
        target=max(1,round(size_mm*DOTS_MM))
        if size_mode=='width':
            w=target; h=max(1,(height*w+width//2)//width)
        else:
            h=target; w=max(1,(width*h+height//2)//height)
        axis=w if direction=='vertical' else h
        count=(axis+WIDTH-1)//WIDTH
    else:
        raise ValueError('Mode de dimensionnement inconnu.')
    rows=h if direction=='vertical' else w
    if rows>MAX_TICKET_ROWS:
        raise ValueError(f'Chaque ticket ferait {rows/DOTS_MM/10:.1f} cm ; limite de calcul actuelle : {MAX_TICKET_ROWS/DOTS_MM/10:g} cm. Réduisez le format ou changez de sens.')
    if rows*count>MAX_TOTAL_ROWS:
        raise ValueError(f'Ce format demande {rows*count:,} lignes ; budget de génération : {MAX_TOTAL_ROWS:,}. Réduisez le format.')
    axis=w if direction=='vertical' else h
    content_last=axis-(count-1)*WIDTH
    paper=[count*WIDTH,h] if direction=='vertical' else [w,count*WIDTH]
    return dict(direction=direction,count=count,content_px=[w,h],paper_px=paper,
                size_mm=[w/DOTS_MM,h/DOTS_MM],paper_size_mm=[n/DOTS_MM for n in paper],
                rows_per_ticket=rows,total_rows=rows*count,last_content_mm=content_last/DOTS_MM,
                trim_mm=(WIDTH-content_last)/DOTS_MM,size_mode=size_mode,requested_mm=size_mm,
                upscale=round(max(w/width,h/height),2),source_px=[width,height])


def corrections(image, options):
    result=image.convert('L')
    sharp=options['sharpness']
    if sharp>.05:
        result=result.filter(ImageFilter.UnsharpMask(radius=1.5 if sharp<=1.5 else 2,percent=round(sharp*100),threshold=2))
    if options['contrast']!=1:
        result=ImageEnhance.Contrast(result).enhance(options['contrast'])
    if options['brightness']!=1:
        result=ImageEnhance.Brightness(result).enhance(options['brightness'])
    # Software compensation only: seven distinct levels, independent of heat.
    if options['strength']<7:
        result=ImageEnhance.Brightness(result).enhance(1+(7-options['strength'])*.03)
    if options['gain']!=1:
        gain=options['gain']
        result=result.point([min(255,round((v/255)**(1/gain)*255)) for v in range(256)])
    return result


def halftone(image, algorithm):
    if algorithm=='floyd':
        return image.convert('1',dither=Image.Dither.FLOYDSTEINBERG)
    if algorithm=='none':
        return image.point(lambda p:255 if p>=128 else 0,mode='1')
    if algorithm=='bayer':
        matrix=[[0]]
        while len(matrix)<8:
            n=len(matrix)
            matrix=[[4*matrix[y%n][x%n]+((0,2),(3,1))[y//n][x//n] for x in range(n*2)] for y in range(n*2)]
        tile=Image.frombytes('L',(8,8),bytes(round((v+.5)*255/64) for row in matrix for v in row))
        thresholds=Image.new('L',image.size)
        for y in range(0,image.height,8):
            for x in range(0,image.width,8):
                thresholds.paste(tile,(x,y))
        return ImageChops.subtract(image,thresholds).point(lambda p:255 if p>0 else 0,mode='1')
    width,height=image.size
    values=list(image.getdata()); out=bytearray(width*height)
    for y in range(height):
        for x in range(width):
            index=y*width+x
            old=max(0,min(255,values[index])); new=255 if old>127 else 0
            out[index]=new; error=(old-new)>>3
            for dx,dy in ((1,0),(2,0),(-1,1),(0,1),(1,1),(0,2)):
                nx,ny=x+dx,y+dy
                if 0<=nx<width and ny<height:
                    values[ny*width+nx]+=error
    return Image.frombytes('L',image.size,bytes(out)).convert('1')


def render_strips(source, plan, options):
    options=resolve_render(options)
    photo=source_image(source,options['autocrop'])
    photo=photo.resize(tuple(plan['content_px']),Image.Resampling.LANCZOS)
    photo=corrections(photo,options)
    w,h=photo.size; strips=[]
    for index in range(plan['count']):
        if plan['direction']=='vertical':
            region=photo.crop((index*WIDTH,0,min((index+1)*WIDTH,w),h))
            canvas=Image.new('L',(WIDTH,h),255);canvas.paste(region,(0,0))
            bitmap=halftone(canvas,options['dither'])
            if region.width<WIDTH:
                bitmap.paste(255,(region.width,0,WIDTH,h))
        else:
            region=photo.crop((0,index*WIDTH,w,min((index+1)*WIDTH,h)))
            canvas=Image.new('L',(w,WIDTH),255);canvas.paste(region,(0,0))
            bitmap=halftone(canvas.rotate(-90,expand=True),options['dither'])
            if region.height<WIDTH:
                bitmap.paste(255,(0,0,WIDTH-region.height,w))
        strips.append(bitmap)
    return strips


def preview_image(source, plan, options):
    """Reduced illustrative raster in memory; no full-size strip allocation or disk writes."""
    options=resolve_render(options)
    photo=source_image(source,options['autocrop'])
    scale=min(1,1400/max(plan['paper_px']))
    content=tuple(max(1,round(n*scale)) for n in plan['content_px'])
    photo=corrections(photo.resize(content,Image.Resampling.LANCZOS),options)
    photo=halftone(photo,options['dither']).convert('RGB')
    canvas=Image.new('RGB',tuple(max(1,round(n*scale)) for n in plan['paper_px']),'white')
    canvas.paste(photo,(0,0))
    draw=ImageDraw.Draw(canvas)
    for index in range(1,plan['count']):
        pos=round(index*WIDTH*scale)
        if plan['direction']=='vertical':
            draw.line((pos,0,pos,canvas.height),fill=(50,120,235),width=1)
        else:
            draw.line((0,pos,canvas.width,pos),fill=(50,120,235),width=1)
    return canvas
