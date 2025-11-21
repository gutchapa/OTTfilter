# App Icons for PWA

You need to create two icon files:
- `icon-192.png` (192x192 pixels)
- `icon-512.png` (512x512 pixels)

## Quick Way to Create Icons:

### Option 1: Use an online tool
1. Go to https://realfavicongenerator.net/
2. Upload your logo/design
3. Download the icons and place them here

### Option 2: Convert the SVG
Use the provided `icon.svg` file:
```bash
# If you have ImageMagick:
convert icon.svg -resize 192x192 icon-192.png
convert icon.svg -resize 512x512 icon-512.png

# Or use an online SVG to PNG converter
```

### Option 3: Use a design tool
Create icons with:
- Black background (#000000)
- "OTT" text in white
- Film strip or movie-related imagery
- Ensure the design is clear at small sizes (192px)

## Icon Guidelines:
- Use simple, recognizable designs
- High contrast for visibility
- Test on both light and dark backgrounds
- Make it square (1:1 aspect ratio)
