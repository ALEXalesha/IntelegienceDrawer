from PIL import Image, ImageDraw, ImageFont

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# rounded black canvas
pad, rad = 18, 44
d.rounded_rectangle([pad, pad, S - pad, S - pad], radius=rad, fill=(20, 20, 22, 255))

# white brush stroke (a curve drawn as a thick polyline)
stroke = [(70, 165), (105, 95), (150, 150), (190, 80)]
d.line(stroke, fill=(245, 245, 245, 255), width=18, joint="curve")
for x, y in stroke:
    d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(245, 245, 245, 255))

# orange question mark, bottom-right
try:
    fnt = ImageFont.truetype("segoeui.ttf", 96)
except OSError:
    fnt = ImageFont.load_default()
d.text((150, 138), "?", font=fnt, fill=(255, 170, 40, 255))

sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save("drawguess.ico", sizes=sizes)
print("saved drawguess.ico")
