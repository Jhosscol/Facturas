import requests, os, sys

def main():
    url = 'http://127.0.0.1:8000/facturas/'
    file_path = os.path.abspath('factura.png')
    if not os.path.isfile(file_path):
        print('File not found:', file_path)
        sys.exit(1)
    with open(file_path, 'rb') as f:
        files = {'archivo': ('factura.png', f, 'image/png')}
        resp = requests.post(url, files=files)
        print('Status:', resp.status_code)
        print('Response:', resp.text)

if __name__ == '__main__':
    main()
