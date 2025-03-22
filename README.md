# FFmpeg 2-Pass Tools

A collection of tools for working with FFmpeg, including two-pass encoding and EXIF data handling.

## System Dependencies

This package requires the following system tools to be installed:

- `ffmpeg`: For video processing
- `exiftool`: For EXIF data handling

### Installing System Dependencies

#### macOS
```bash
brew install ffmpeg exiftool
```

#### Ubuntu/Debian
```bash
sudo apt-get install ffmpeg exiftool
```

## Installation

### Via pip
```bash
pip install ffmpeg-2pass-tools
```

### For Development
```bash
git clone https://github.com/YoungCatChen/ffmpeg-2pass-tools.git
cd ffmpeg-2pass-tools
pip install -e ".[test]"  # Install with test dependencies
```

## Available Tools

- `burst-shots-into-live-photo`: Convert burst shots into live photos
- `ffmpeg-2pass-and-exif`: Perform two-pass FFmpeg encoding while handling EXIF data
- `get-ffmpeg-input-flags`: Get FFmpeg input flags

## License

MIT License
