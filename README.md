# ✎ᝰ Teneo-Node-BOT

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Made With ❤️](https://img.shields.io/badge/Made%20with-❤️-red.svg)](#)

Teneo Node BOT runner for multiple accounts.

> 🔁 Auto-runs multiple wallet accounts to interact with Teneo Node via WebSocket.

![Preview](https://github.com/user-attachments/assets/dcc5a9e9-1f6c-4f55-98b8-502b8223e788)

---
## ✎ᝰ File Struktur

```
.
├── main.py           # Main script
├── token.txt         # Tempat menyimpan token
├── requirements.txt  # Dependencies
└── README.md         # Dokumentasi
```


## ✎ᝰ Features

- ⚡ Async WebSocket client
- 🔐 Token-based authentication
- 🧠 Real-time rich terminal UI with `rich`
- 🔄 Auto reconnect
- 🧩 Easy to configure (just edit `token.txt`)

---

## ✎ᝰ Getting Started

### 🔧 1. Install Requirements

```bash
pip install -r requirements.txt
```
### 2. Edit Token File
Edit file token.txt dan masukkan token kamu, satu per baris.

### 3. Jalankan Bot
```bash
python main.py
```
or 
```bash
python3 main.py
```

## ✎ᝰ Troubleshooting
Pastikan menggunakan Python 3.7 atau lebih baru.

Jika mengalami error pada keyboard, coba jalankan dengan sudo (Linux/macOS).

Gunakan venv agar lingkungan Python tetap bersih:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## ✎ᝰ License
This project is licensed under the MIT License.

Made with ❤️ by iEpoy
