# 1️⃣ Base image: Python 3.10
FROM python:3.10-slim

# 2️⃣ Ishchi papka
WORKDIR /app

# 3️⃣ Zarur system paketlar (C extension lar uchun)
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 4️⃣ Requirements nusxalash
COPY requirements.txt .

# 5️⃣ Python paketlarini o‘rnatish
RUN pip install --no-cache-dir -r requirements.txt

# 6️⃣ Bot kodi nusxalash
COPY . .

# 7️⃣ Botni ishga tushirish
CMD ["python", "bot.py"]
