from flask import Flask, request
import torch
from PIL import Image
from torchvision import transforms as T

model = torch.hub.load('baudm/parseq', 'parseq_tiny')
checkpoint = torch.load('parseq-tiny-securimage.ckpt', map_location=torch.device('cpu'))
model.load_state_dict(checkpoint['state_dict'])
parseq = model.eval()
img_transform = T.Compose([
            T.Resize(parseq.hparams.img_size, T.InterpolationMode.BICUBIC),
            T.ToTensor(),
            T.Normalize(0.5, 0.5)
        ])

app = Flask(__name__)

@app.route("/health")
def health():
    return "HEALTHY"

@app.route('/process', methods=['POST'])
def process():
    if 'file' not in request.files:
        return 'No file found', 400

    file = request.files['file']
    
    if file.filename == '':
        return 'No file selected', 400

    img = Image.open(file).convert('RGB')
    # Preprocess. Model expects a batch of images with shape: (B, C, H, W)
    img = img_transform(img).unsqueeze(0)

    logits = parseq(img)

    # Greedy decoding
    pred = logits.softmax(-1)
    label, confidence = parseq.tokenizer.decode(pred)
    return {'data': label[0]}, 200
