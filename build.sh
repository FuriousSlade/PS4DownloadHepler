python -m easy_install pip && \
python -m pip install virtualenv && \
python -m virtualenv --no-site-packages venv && \
source  venv/bin/activate && \
python -m pip install --upgrade pip && \
python -m pip install -r requirements.txt && \
python -m PyInstaller --clean --onefile --windowed --noconfirm -i icon.icns -n PS4DownloadHepler ui.py