# Commented out IPython magic to ensure Python compatibility.
from flask import Flask, request
from flask import send_file
import pickle
import torch
import numpy as np

import os
import glob
import urllib
import zipfile
import collections

from PIL import Image
from IPython.display import Image as DisplayImage
from IPython.display import Javascript
from IPython.core.display import display, HTML


INPUT_DIR = '/content/files'
STAGING_DIR = '/content/stage'
OUT_DIR = '/content/out'
CKPT_DIR = '/content/checkpoint'
DEFAULT_IMAGE_PREFIX = ('https://storage.googleapis.com/hific/clic2020/images/originals/')

File = collections.namedtuple('File', ['output_path', 'compressed_path',
                                       'num_bytes', 'bpp'])

_ = [os.makedirs(dir, exist_ok=True) for dir in (INPUT_DIR, STAGING_DIR, OUT_DIR,
                                                 CKPT_DIR)]
original_sizes = dict()


def get_default_image(output_dir, image_choice="portrait"):
    image_ID = dict(cafe="b1b8f33917a40c9d0b118ef801de67d4.png",
                    cat="4fa92b8ecb4ee46a942837447de1ac5c.png",
                    city="b98ec5b29d02ef65e57d23ef90660b4d.png",
                    clocktower="9cbf2594f339c0d3d0f0ea25c62af52b.png",
                    fresco="8181526d9f238726d3e1d3ec3cc56fb7.png",
                    islet="c6658d87c608b631f5cc3fb5a8d89731.png",
                    mountain="d3688a7285d7b2b81febe1cd72e6e22c.png",
                    pasta="f5be5054c01d8efc834d78a991356ad6.png",
                    pines="e903c4f4684100a6dbac1f0b9b4de760.png",
                    plaza="d78b363974ac79908b79012f48de715d.png",
                    portrait="ad249bba099568403dc6b97bc37f8d74.png",
                    shoreline="b9bad0c68eb9ce94e02e9698c8cc429a.png",
                    street="90b622e11ecc37edd42297427403ee81.png",
                    tundra="cc831c904a314a0e98530124526e930b.png",
                    )[image_choice]
                    
    default_image_url = os.path.join(DEFAULT_IMAGE_PREFIX, image_ID)
    output_path = os.path.join(output_dir, os.path.basename(default_image_url))
    print('Downloading', default_image_url, '\n->', output_path)
    urllib.request.urlretrieve(default_image_url, output_path)

def get_model_checkpoint(output_dir, model_ID, model_choice, alternative=False,
                         overwrite=False):
    output_path = os.path.join(output_dir, f'{model_choice.lower()}.pt')
    if overwrite is True:
        print('Overwriting file, if it exists.')
        !rm -v $output_path
    else:
        if os.path.exists(output_path):
            return output_path
    if alternative is True:
        !wget "https://zenodo.org/record/4026003/files/$model_ID" -O $output_path
    else:
        !wget -q --show-progress --load-cookies /tmp/cookies.txt "https://docs.google.com/uc?export=download&confirm=$(wget --quiet --save-cookies /tmp/cookies.txt --keep-session-cookies --no-check-certificate 'https://docs.google.com/uc?export=download&id=$model_ID' -O- | sed -rn 's/.*confirm=([0-9A-Za-z_]+).*/\1\n/p')&id=$model_ID" -O $output_path && rm -rf /tmp/cookies.txt

    return output_path

    # Enter choice to right
model_choice = 'HIFIC-low'

# Drive IDs
model_choices = {'HIFIC-low': '1hfFTkZbs_VOBmXQ-M4bYEPejrD76lAY9',
                 'HIFIC-med': '1QNoX0AGKTBkthMJGPfQI0dT0_tnysYUb',
                 'HIFIC-high': '1BFYpvhVIA_Ek2QsHBbKnaBE8wn1GhFyA'}

model_ID = model_choices[model_choice]
model_path = get_model_checkpoint(CKPT_DIR, model_ID, model_choice)
first_model_init = False

!git clone https://github.com/Justin-Tan/high-fidelity-generative-compression.git
# %cd high-fidelity-generative-compression/
from compress import prepare_model, prepare_dataloader, compress_and_save, load_and_decompress, compress_and_decompress

custom_image = False

# Choose default images from CLIC2020 dataset
# Skip if uploading custom images
default_image = "portrait"


get_default_image(INPUT_DIR, default_image)
    

all_files = os.listdir(INPUT_DIR)
scale_factor = 2 if len(all_files) == 1 else 4

for file_name in all_files:
  img = Image.open(os.path.join(INPUT_DIR, file_name))
  w, h = img.size
  img = img.resize((w // scale_factor, h // scale_factor))
  display(img)

SUPPORTED_EXT = {'.png', '.jpg'}

all_files = os.listdir(INPUT_DIR)
if not all_files:
    raise ValueError("Please upload/download images!")

def get_bpp(image_dimensions, num_bytes):
    w, h = image_dimensions
    return num_bytes * 8 / (w * h)

def has_alpha(img_p):
    im = Image.open(img_p)
    return im.mode == 'RGBA'

!rm -v $STAGING_DIR/*

for file_name in all_files:
    if os.path.isdir(file_name):
        continue
    if not any(file_name.endswith(ext) for ext in SUPPORTED_EXT):
        continue
    full_path = os.path.join(INPUT_DIR, file_name)
    if has_alpha(full_path) is True:
        continue
    
    file_name, _ = os.path.splitext(file_name)
    original_sizes[file_name] = os.path.getsize(full_path)
    output_path = os.path.join(OUT_DIR, f'{file_name}.png')
    !mv -v $full_path $STAGING_DIR

# Setup model
if first_model_init is False:
    model, args = prepare_model(model_path, STAGING_DIR)
    first_model_init = True

data_loader = prepare_dataloader(args, STAGING_DIR, OUT_DIR)
compress_and_save(model, args, data_loader, OUT_DIR)
all_outputs = []

for compressed_file in glob.glob(os.path.join(OUT_DIR, '*.hfc')):
    file_name, _ = os.path.splitext(compressed_file)
    output_path = os.path.join(OUT_DIR, f'{file_name}.jpg')

    # Model decode
    reconstruction = load_and_decompress(model, compressed_file, output_path)
    
    all_outputs.append(File(output_path=output_path,
                            compressed_path=compressed_file,
                            num_bytes=os.path.getsize(compressed_file),
                            bpp=get_bpp(Image.open(output_path).size, os.path.getsize(compressed_file))))
    

file_name, _ = os.path.splitext(file.output_path)
original_size = original_sizes[os.path.basename(file_name).split('_compressed')[0]]
display(Image.open(file.output_path))

app = Flask(__name__)

@app.route('/compressed', methods=['POST'])
def returnimage():
  return send_file(file_name, mimetype='image/jpg')

if __name__ == "__main__":
  app.run()
