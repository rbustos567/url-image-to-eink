## Installation
```bash
git clone https://github.com/rbustos567/url-image-to-eink.git
cd url-image-to-eink
chmod +x install.sh
sudo ./install.sh
```
## Usage Examples
### Generate a local preview
```bash
python3 url_jpg_to_eink.py "https://picsum.photos/800/480" --width 800 --height 480 --output /tmp/random_eink.png
```
### Send directly to the connected Waveshare screen
```bash
python3 url_jpg_to_eink.py "https://picsum.photos/800/480" --width 800 --height 480 --model epd7in5_V2 --display
```
