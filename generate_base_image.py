from PIL import Image, ImageDraw

# Create a 40x40 image for the mage base
img = Image.new('RGBA', (40, 40), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Draw a red tower base
draw.rectangle([5, 10, 35, 38], fill=(180, 40, 40), outline=(80, 20, 20), width=2)

# Draw tower top
draw.polygon([(3, 10), (20, 2), (37, 10)], fill=(150, 30, 30), outline=(80, 20, 20))

# Draw purple glowing windows
draw.rectangle([12, 15, 18, 22], fill=(150, 50, 200))
draw.rectangle([22, 15, 28, 22], fill=(150, 50, 200))
draw.rectangle([17, 28, 23, 35], fill=(150, 50, 200))

# Save
img.save('assets/mage_base.png')
print("Generated mage_base.png successfully!")
