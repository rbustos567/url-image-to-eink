## Installation
```bash
git clone https://github.com/rbustos567/url-image-to-eink.git
cd url-image-to-eink
chmod +x install.sh
sudo ./install.sh
```
## Usage Examples
### Generate a local preview using a local jpg file
```bash
python3 url_jpg_to_eink.py /home/pi/photos/my_photo.jpg -o /tmp/eink_preview.png
```
### Using a local jpg file to send it directly to the connected Waveshare screen with WARNING logging
```bash
python3 url_jpg_to_eink.py ~/photos/street.jpg --gamma 1.2 --contrast 1.7 --display --log-level WARNING
```
### Using remote URL with DEBUG logging sending to a file
```bash
python3 url_jpg_to_eink.py "https://picsum.photos/800/480" -o /tmp/eink_preview.png --display --log-level DEBUG --log-file 20260907-1.log
```
