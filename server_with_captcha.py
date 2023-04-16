from flask import Flask, request
import requests
from bs4 import BeautifulSoup
import torch
from PIL import Image
from torchvision import transforms as T
from io import BytesIO

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

@app.route('/origin')
def origin():
    query = request.args.get('query')
    res = requests.get('https://www.jne.co.id/ajax/origin?query={}'.format(query), headers={
        'X-Requested-With': 'XMLHttpRequest'
    })
    return res.json()['suggestions']


@app.route('/destination')
def destination():
    query = request.args.get('query')
    res = requests.get('https://www.jne.co.id/ajax/destination?query={}'.format(query), headers={
        'X-Requested-With': 'XMLHttpRequest'
    })
    return res.json()['suggestions']

@app.route('/tariff', methods=['POST'])
def tariff():
    request_json = request.json
    origin_code = request_json['origin_code']
    dest_code = request_json['dest_code']
    weight = request_json['weight']

    s = requests.Session()

    initial_page = s.get("https://www.jne.co.id/id/tracking/tarif")
    initial_soup = BeautifulSoup(initial_page.content, 'html.parser')

    captcha_image_url = initial_soup.select("img#captcha_image")[0]['src']
    captcha_image = s.get(captcha_image_url)

    img = Image.open(BytesIO(captcha_image.content)).convert('RGB')
    # Preprocess. Model expects a batch of images with shape: (B, C, H, W)
    img = img_transform(img).unsqueeze(0)

    logits = parseq(img)

    # Greedy decoding
    pred = logits.softmax(-1)
    label, confidence = parseq.tokenizer.decode(pred)
    captcha = label[0]

    token = initial_soup.select('input[name="_token"]')[0]['value'] 

    data = {
        '_token': token,
        'origin_code': origin_code,
        'dest_code': dest_code,
        'weight': weight,
        'captcha': captcha
    }

    result_page = s.post('https://www.jne.co.id/id/tracking/tarif', data=data)

    soup = BeautifulSoup(result_page.content, 'html.parser')

    table = soup.find_all("table")[1]

    tbody_rows = table.tbody.find_all('tr')

    keys = ["nama_layanan", "jenis_kiriman", "tarif", "estimasi"]

    data = []
    for row in tbody_rows:
        values = [cell.text for cell in row.find_all('td')]
        item = {keys[i]: values[i] for i in range(len(keys))}
        data.append(item)
    return data

