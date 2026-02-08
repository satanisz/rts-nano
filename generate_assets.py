from PIL import Image, ImageDraw

# Create resource image (15x15)
resource_img = Image.new('RGBA', (15, 15), (0, 0, 0, 0))
draw = ImageDraw.Draw(resource_img)

# Draw yellow crystal/ore
draw.polygon([(7, 2), (12, 7), (10, 13), (5, 13), (3, 7)], fill=(255, 215, 0), outline=(200, 170, 0))
draw.polygon([(7, 2), (9, 5), (7, 8), (5, 5)], fill=(255, 255, 150))  # Highlight

resource_img.save('assets/resource.png')
print("Generated resource.png successfully!")

# Create unit image (20x20)
unit_img = Image.new('RGBA', (20, 20), (0, 0, 0, 0))
draw = ImageDraw.Draw(unit_img)

# Draw blue character/unit
draw.ellipse([5, 3, 15, 13], fill=(70, 130, 220), outline=(40, 80, 160))  # Body
draw.ellipse([7, 5, 13, 11], fill=(100, 160, 255))  # Highlight
draw.rectangle([7, 12, 9, 17], fill=(70, 130, 220))  # Left leg
draw.rectangle([11, 12, 13, 17], fill=(70, 130, 220))  # Right leg

unit_img.save('assets/unit.png')
print("Generated unit.png successfully!")
